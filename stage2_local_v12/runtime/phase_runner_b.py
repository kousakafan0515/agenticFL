"""Run one frozen 134-task Client-A training or validation phase."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from stage2_local_v12.runtime.banks import canonical_bytes, file_hash, write_json
from stage2_local_v12.runtime.paired_evaluator import FIXED_ARGS, task_type
from stage2_local_v12.runtime.runtime_adapter import build_adapter
from stage2_local_v12.runtime.training_runner import sanitize_episode


ROOT = Path(__file__).resolve().parents[2]
MODEL = "qwen3.6-flash"
API_MARKERS = ("apierror", "authenticationerror", "ratelimiterror", "timeout", "arrearage", "overdue-payment")


def command(
    args: argparse.Namespace,
    tasks: list[str],
    adapter: dict[str, str] | None,
    run_output_root: Path,
) -> list[str]:
    cmd = [
        str(args.python), str(ROOT / "stage2_local_v12/clients/alfworld_client_b.py"),
        "--api-key-env", args.api_key_env, "--base-url", args.base_url,
        "--model", args.model, "--data-dir", str(args.data_root), "--split", "train",
        "--games-per-type", "1", "--task-types", "1", "2", "3", "4", "5", "6",
        "--max-steps", "50", "--history-window-turns", "10", "--request-timeout", "60",
        "--transport-retries", "3", "--generation-seed", "1234", "--send-disable-thinking",
        "--output", str(run_output_root / "result.json"),
        "--trace-file", str(run_output_root / "trace.jsonl"),
    ]
    if args.max_control_retries is not None:
        cmd.extend(["--max-control-retries", str(args.max_control_retries)])
    for task in tasks:
        cmd.extend(["--only-game-file", str(args.data_root / "json_2.1.1" / "train" / task / "game.tw-pddl")])
    if adapter is None:
        cmd.extend(["--skill-mode", "none"])
    else:
        cmd.extend(["--skill-mode", "global", "--skillbank", adapter["skillbank"], "--skill-manifest", adapter["manifest"], "--skill-capacity-profile", adapter["capacity_profile"]])
    cmd.extend(FIXED_ARGS["B"])
    return cmd


def execution_order(tasks: list[str]) -> list[str]:
    """Match the client's deterministic task-type loop and per-type path sort."""
    return [
        task
        for index in range(1, 7)
        for task in sorted((row for row in tasks if task_type(row) == index), key=str.casefold)
    ]


def task_from_game_file(value: str) -> str:
    normalized = str(value).replace("\\", "/")
    marker = "/json_2.1.1/train/"
    suffix = "/game.tw-pddl"
    if marker not in normalized or not normalized.endswith(suffix):
        raise ValueError(f"unexpected train game path: {value}")
    return normalized.split(marker, 1)[1][:-len(suffix)]


def next_resume_root(output_root: Path) -> Path:
    parent = output_root / "resume_segments"
    parent.mkdir(parents=True, exist_ok=True)
    attempt = 1
    while (parent / f"attempt_{attempt:03d}").exists():
        attempt += 1
    path = parent / f"attempt_{attempt:03d}"
    path.mkdir()
    return path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("training", "validation"), required=True)
    parser.add_argument("--generation", type=int, required=True)
    parser.add_argument("--manifest", type=Path, default=ROOT / "stage2_local_v12/assets/manifests/client_b_generation_01.json")
    parser.add_argument("--bank", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--base-url", default="https://dashscope.aliyuncs.com/compatible-mode/v1")
    parser.add_argument("--api-key-env", default="DASHSCOPE_API_KEY")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume-partial", action="store_true")
    parser.add_argument("--resume-order-reference", type=Path)
    parser.add_argument("--max-control-retries", type=int)
    args = parser.parse_args()
    if args.generation < 0:
        raise SystemExit("generation must be non-negative")
    if args.phase == "training" and args.generation < 1:
        raise SystemExit("training generation must be at least 1")
    if args.generation == 0 and args.bank:
        raise SystemExit("B0 validation must use the empty SkillBank")
    if args.generation > 0 and not args.bank and not (args.phase == "training" and args.generation == 1):
        raise SystemExit("non-empty generation requires --bank")
    if args.model != MODEL:
        raise SystemExit(f"new experiment requires {MODEL}, got {args.model}")
    if not args.dry_run and not os.environ.get(args.api_key_env):
        raise SystemExit(f"{args.api_key_env} is missing")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    tasks = list(manifest[args.phase]["tasks"])
    if len(tasks) != 134 or len({task_type(task) for task in tasks}) != 6:
        raise SystemExit("phase manifest must contain the frozen 134-task six-type cohort")
    args.output_root.mkdir(parents=True, exist_ok=True)
    adapter = None
    bank_payload = None
    if args.bank:
        bank_payload = json.loads(args.bank.read_text(encoding="utf-8"))
        expected_bank_generation = args.generation - 1 if args.phase == "training" else args.generation
        if int(bank_payload.get("generation", -1)) != expected_bank_generation:
            raise SystemExit(
                f"{args.phase} generation {args.generation} requires B{expected_bank_generation}, "
                f"got B{bank_payload.get('generation')}"
            )
        adapter = build_adapter(bank_payload, "B", args.output_root / "adapter")
    grouped = {index: [task for task in tasks if task_type(task) == index] for index in range(1, 7)}
    ordered_tasks = execution_order(tasks)
    source_lock = {
        "experiment_id": manifest["experiment_id"], "client": "B", "phase": args.phase,
        "generation": args.generation,
        "manifest_file_sha256": file_hash(args.manifest), "manifest_content_hash": manifest["manifest_content_hash"],
        "bank_file_sha256": file_hash(args.bank) if args.bank else None,
        "bank_live_repository_sha256": bank_payload.get("live_repository_sha256") if bank_payload else None,
        "model": MODEL, "temperature": 0, "seed": 1234, "thinking": False,
    }
    existing_payload = None
    tasks_to_run = ordered_tasks
    run_output_root = args.output_root
    if args.resume_partial:
        if not args.resume_order_reference:
            raise SystemExit("partial resume requires --resume-order-reference")
        reference_payload = json.loads(args.resume_order_reference.read_text(encoding="utf-8"))
        try:
            reference_tasks = [task_from_game_file(row["game_file"]) for row in reference_payload["episodes"]]
        except (KeyError, TypeError, ValueError) as exc:
            raise SystemExit(f"partial resume cannot read reference task order: {exc}") from exc
        if len(reference_tasks) != 134 or len(set(reference_tasks)) != 134 or set(reference_tasks) != set(tasks):
            raise SystemExit("partial resume order reference is not the same frozen 134-task cohort")
        ordered_tasks = reference_tasks
        if (args.output_root / "summary.json").exists():
            raise SystemExit("partial resume refused: phase already has a complete summary")
        result_path = args.output_root / "result.json"
        lock_path = args.output_root / "source_lock.json"
        if not result_path.exists() or not lock_path.exists():
            raise SystemExit("partial resume requires existing result.json and source_lock.json")
        existing_lock = json.loads(lock_path.read_text(encoding="utf-8"))
        if existing_lock != source_lock:
            raise SystemExit("partial resume source lock mismatch")
        existing_payload = json.loads(result_path.read_text(encoding="utf-8"))
        existing_episodes = list(existing_payload.get("episodes") or [])
        if not 0 < len(existing_episodes) < len(ordered_tasks):
            raise SystemExit(f"partial resume requires 1-133 complete episodes, got {len(existing_episodes)}")
        try:
            completed_tasks = [task_from_game_file(row["game_file"]) for row in existing_episodes]
        except (KeyError, TypeError, ValueError) as exc:
            raise SystemExit(f"partial resume cannot identify completed task order: {exc}") from exc
        if completed_tasks != ordered_tasks[:len(completed_tasks)]:
            raise SystemExit("partial resume completed episodes are not the frozen execution-order prefix")
        tasks_to_run = ordered_tasks[len(completed_tasks):]
        if not args.dry_run:
            run_output_root = next_resume_root(args.output_root)
    cmd = command(args, tasks_to_run, adapter, run_output_root)
    if not args.resume_partial:
        write_json(args.output_root / "command.json", {"command": cmd})
        write_json(args.output_root / "source_lock.json", source_lock)
    elif not args.dry_run:
        write_json(run_output_root / "command.json", {"command": cmd})
        write_json(run_output_root / "source_lock.json", source_lock)
        write_json(run_output_root / "resume_lock.json", {
            "completed_episode_count": len(existing_payload["episodes"]),
            "remaining_episode_count": len(tasks_to_run),
            "frozen_execution_order": ordered_tasks,
            "order_reference": str(args.resume_order_reference),
            "order_reference_file_sha256": file_hash(args.resume_order_reference),
            "runtime_guard_amendment": {"max_control_retries": args.max_control_retries},
        })
    if args.dry_run:
        print(json.dumps({
            "status": "dry_run", "phase": args.phase, "generation": args.generation,
            "tasks": len(tasks), "completed_tasks": len(existing_payload["episodes"]) if existing_payload else 0,
            "remaining_tasks": len(tasks_to_run),
            "family_counts": {str(k): len(v) for k, v in grouped.items()}, "model": MODEL,
        }, indent=2))
        return
    log = run_output_root / "process.log"
    with log.open("w", encoding="utf-8") as handle:
        completed = subprocess.run(cmd, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT)
    if completed.returncode != 0:
        raise SystemExit(f"Client B exited {completed.returncode}; see {log}")
    segment_result_path = run_output_root / "result.json"
    payload = json.loads(segment_result_path.read_text(encoding="utf-8"))
    if existing_payload is not None:
        segment_episodes = list(payload.get("episodes") or [])
        try:
            segment_tasks = [task_from_game_file(row["game_file"]) for row in segment_episodes]
        except (KeyError, TypeError, ValueError) as exc:
            raise SystemExit(f"partial resume cannot identify resumed task order: {exc}") from exc
        if len(segment_tasks) != len(set(segment_tasks)) or set(segment_tasks) != set(tasks_to_run):
            raise SystemExit("partial resume segment does not match the frozen remaining task set")
        episode_by_task = dict(zip(segment_tasks, segment_episodes))
        segment_episodes = [episode_by_task[task] for task in tasks_to_run]
        merged_payload = dict(existing_payload)
        merged_payload["episodes"] = list(existing_payload["episodes"]) + segment_episodes
        merged_payload["finished_at"] = payload.get("finished_at")
        merged_payload.setdefault("resume_segments", []).append({
            "relative_directory": str(run_output_root.relative_to(args.output_root)).replace("\\", "/"),
            "completed_before": len(existing_payload["episodes"]),
            "episodes_added": len(segment_episodes),
            "segment_result_file_sha256": file_hash(segment_result_path),
        })
        write_json(args.output_root / "result.json", merged_payload)
        payload = merged_payload
    result_path = args.output_root / "result.json"
    episodes = payload.get("episodes") or []
    if len(episodes) != 134:
        raise SystemExit(f"expected 134 episodes, got {len(episodes)}")
    rendered = json.dumps(payload, ensure_ascii=False).casefold()
    if any(marker in rendered for marker in API_MARKERS):
        raise SystemExit("API failure marker found in result")
    summary = {
        "status": "complete", "phase": args.phase, "generation": args.generation, "client": "B", "model": MODEL,
        "task_count": 134, "success_count": sum(bool(row.get("success")) for row in episodes), "api_clean": True,
        "result_file_sha256": file_hash(result_path),
    }
    if args.phase == "training":
        evidence = {
            "schema_version": 1, "experiment_id": manifest["experiment_id"], "client_id": "B",
            "generation": args.generation,
            "parent_bank": f"B{args.generation - 1}",
            "parent_bank_file_sha256": file_hash(args.bank) if args.bank else None,
            "parent_live_repository_sha256": bank_payload.get("live_repository_sha256") if bank_payload else None,
            "episodes": [
                sanitize_episode(row, f"{manifest['experiment_id']}/generation_{args.generation:02d}/client_B/episode_{index:03d}")
                for index, row in enumerate(episodes, 1)
            ],
        }
        evidence["evidence_sha256"] = "sha256:" + hashlib.sha256(canonical_bytes(evidence)).hexdigest()
        write_json(args.output_root / "evidence.json", evidence)
        summary["evidence_file_sha256"] = file_hash(args.output_root / "evidence.json")
    write_json(args.output_root / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
