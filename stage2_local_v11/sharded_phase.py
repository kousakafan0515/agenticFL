"""Run one frozen V11 client phase in isolated ALFWorld task shards.

The default invocation is a read-only plan. ``--execute`` is the paid boundary.
This runner never changes the frozen cohort, parent bank, or downstream phase
format. Failed shards are preserved and are not retried automatically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from client_code.skillbank_loader import parse_bank
from originalFL.banks import canonical_bytes, file_hash, write_json
from originalFL.paired_evaluator import FIXED_ARGS, task_type
from originalFL.runtime_adapter import build_adapter
from originalFL.training_runner import sanitize_episode
from stage2_local_v6.scripts.run_client_a_phase import execution_order, task_from_game_file


ROOT = Path(__file__).resolve().parents[1]
MODEL = "qwen3.6-flash"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_MARKERS = ("apierror", "authenticationerror", "ratelimiterror", "timeout", "arrearage", "overdue-payment")


def partition(tasks: list[str], count: int) -> list[list[str]]:
    if not 1 <= count <= len(tasks):
        raise ValueError("shards must be between 1 and frozen task count")
    return [tasks[(i * len(tasks)) // count:((i + 1) * len(tasks)) // count] for i in range(count)]


def prepare(args: argparse.Namespace) -> tuple[dict[str, Any], list[list[str]], dict[str, Any] | None]:
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    tasks = list(manifest[args.phase]["tasks"])
    if len(tasks) != 134 or len(set(tasks)) != 134 or {task_type(task) for task in tasks} != set(range(1, 7)):
        raise RuntimeError("manifest must have 134 unique frozen tasks in six families")
    if not manifest.get("experiment_id", "").startswith("stage2-local-v11-"):
        raise RuntimeError("only V11 frozen manifests are accepted")
    if args.generation < 0 or (args.phase == "training" and args.generation < 1):
        raise RuntimeError("invalid phase/generation")
    if args.bank is None and not (args.generation == 0 and args.phase == "validation" or args.generation == 1 and args.phase == "training"):
        raise RuntimeError("this phase requires a parent SkillBank")
    if args.bank is not None and args.generation == 0:
        raise RuntimeError("B0 validation requires the empty bank")
    bank = None
    if args.bank is not None:
        bank = json.loads(args.bank.read_text(encoding="utf-8"))
        parse_bank(bank, args.client)
        expected = args.generation - 1 if args.phase == "training" else args.generation
        if bank.get("generation") != expected:
            raise RuntimeError(f"{args.phase} generation {args.generation} requires bank generation {expected}")
    pilot_tasks = getattr(args, "pilot_tasks", 134)
    if not 1 <= pilot_tasks <= 134 or not 1 <= args.shards <= pilot_tasks or not 1 <= args.max_workers <= args.shards:
        raise RuntimeError("require 1 <= max-workers <= shards <= pilot-tasks <= 134")
    if args.start_stagger_seconds < 0:
        raise RuntimeError("start stagger must be non-negative")
    frozen = ROOT / "stage2_local_v11" / "artifacts" / "manifests" / f"client_{args.client.lower()}_generation_01.json"
    if file_hash(args.manifest) != file_hash(frozen):
        raise RuntimeError("manifest bytes differ from the frozen V11 client manifest")
    frozen_order = execution_order(tasks)
    ordered = [frozen_order[(i * 134) // pilot_tasks] for i in range(pilot_tasks)] if pilot_tasks < 134 else frozen_order
    pieces = partition(ordered, args.shards)
    lock = {
        "experiment_id": manifest["experiment_id"], "client": args.client,
        "phase": args.phase, "generation": args.generation,
        "manifest_file_sha256": file_hash(args.manifest),
        "manifest_content_hash": manifest["manifest_content_hash"],
        "bank_file_sha256": file_hash(args.bank) if args.bank else None,
        "bank_live_repository_sha256": bank.get("live_repository_sha256") if bank else None,
        "model": MODEL, "temperature": 0, "seed": 1234, "thinking": False,
    }
    if pilot_tasks < 134:
        lock["pilot_task_count"] = pilot_tasks
        lock["pilot_task_order_sha256"] = "sha256:" + hashlib.sha256(canonical_bytes(ordered)).hexdigest()
    return lock, pieces, bank


def shard_command(args: argparse.Namespace, tasks: list[str], adapter: dict[str, str] | None, directory: Path) -> list[str]:
    command = [
        str(args.python), str(ROOT / "client_code" / f"alfworld_client_{args.client.lower()}.py"),
        "--api-key-env", args.api_key_env, "--base-url", BASE_URL,
        "--model", MODEL, "--data-dir", str(args.data_root), "--split", "train",
        "--games-per-type", "1", "--task-types", "1", "2", "3", "4", "5", "6",
        "--max-steps", "50", "--history-window-turns", "10", "--request-timeout", "60",
        "--transport-retries", "3", "--generation-seed", "1234", "--send-disable-thinking",
        "--output", str(directory / "result.json"), "--trace-file", str(directory / "trace.jsonl"),
    ]
    if args.client == "A":
        command.extend(["--max-control-retries", "12"])
    for task in tasks:
        command.extend(["--only-game-file", str(args.data_root / "json_2.1.1" / "train" / task / "game.tw-pddl")])
    if adapter is None:
        command.extend(["--skill-mode", "none"])
    else:
        command.extend(["--skill-mode", "global", "--skillbank", adapter["skillbank"],
                        "--skill-manifest", adapter["manifest"],
                        "--skill-capacity-profile", adapter["capacity_profile"]])
    return command + FIXED_ARGS[args.client]


def validated_shard(args: argparse.Namespace, index: int, tasks: list[str]) -> dict[str, Any]:
    path = args.output_root / "shards" / f"shard_{index:03d}" / "result.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("model") != MODEL or not isinstance(payload.get("episodes"), list):
        raise RuntimeError(f"invalid shard result identity: {path}")
    if len(payload["episodes"]) != len(tasks):
        raise RuntimeError(f"incomplete shard: {path}")
    if any(marker in json.dumps(payload, ensure_ascii=False).casefold() for marker in API_MARKERS):
        raise RuntimeError(f"API failure marker in {path}")
    actual = [task_from_game_file(episode["game_file"]) for episode in payload["episodes"]]
    if len(set(actual)) != len(actual) or set(actual) != set(tasks):
        raise RuntimeError(f"unexpected or duplicate task in {path}")
    return payload


def merge_results(args: argparse.Namespace, pieces: list[list[str]], lock: dict[str, Any]) -> dict[str, Any]:
    episodes: dict[str, dict[str, Any]] = {}
    first: dict[str, Any] | None = None
    starts: list[str] = []
    finishes: list[str] = []
    for index, tasks in enumerate(pieces, 1):
        path = args.output_root / "shards" / f"shard_{index:03d}" / "result.json"
        payload = validated_shard(args, index, tasks)
        for episode in payload["episodes"]:
            task = task_from_game_file(episode["game_file"])
            if task not in tasks or task in episodes:
                raise RuntimeError(f"unexpected or duplicate task in {path}: {task}")
            episodes[task] = episode
        first = first or payload
        if isinstance(payload.get("started_at"), str):
            starts.append(payload["started_at"])
        if isinstance(payload.get("finished_at"), str):
            finishes.append(payload["finished_at"])
    ordered = [task for piece in pieces for task in piece]
    if set(episodes) != set(ordered) or len(episodes) != len(ordered) or first is None:
        raise RuntimeError("shards do not cover the selected frozen tasks exactly once")
    merged = {"protocol": first.get("protocol"), "reproduction_assumptions": first.get("reproduction_assumptions"),
              "started_at": min(starts) if starts else None, "model": MODEL,
              "episodes": [episodes[task] for task in ordered], "finished_at": max(finishes) if finishes else None,
              "sharded_execution": {"shards": len(pieces), "execution_order_sha256": "sha256:" + hashlib.sha256(canonical_bytes(ordered)).hexdigest()}}
    write_json(args.output_root / "result.json", merged)
    summary = {"status": "complete" if len(ordered) == 134 else "pilot_complete", "phase": args.phase, "generation": args.generation,
               "client": args.client, "model": MODEL, "task_count": len(ordered),
               "success_count": sum(bool(e.get("success")) for e in merged["episodes"]),
               "api_clean": True, "result_file_sha256": file_hash(args.output_root / "result.json")}
    if args.phase == "training" and len(ordered) == 134:
        evidence = {"schema_version": 1, "experiment_id": lock["experiment_id"],
                    "client_id": args.client, "generation": args.generation,
                    "parent_bank": f"B{args.generation - 1}",
                    "parent_bank_file_sha256": lock["bank_file_sha256"],
                    "parent_live_repository_sha256": lock["bank_live_repository_sha256"],
                    "episodes": [sanitize_episode(e, f"{lock['experiment_id']}/generation_{args.generation:02d}/client_{args.client}/episode_{i:03d}")
                                 for i, e in enumerate(merged["episodes"], 1)]}
        evidence["evidence_sha256"] = "sha256:" + hashlib.sha256(canonical_bytes(evidence)).hexdigest()
        write_json(args.output_root / "evidence.json", evidence)
        summary["evidence_file_sha256"] = file_hash(args.output_root / "evidence.json")
    write_json(args.output_root / "summary.json", summary)
    return summary


def run(args: argparse.Namespace) -> dict[str, Any]:
    lock, pieces, _ = prepare(args)
    plan = {"schema_version": "stage2_local_v11.sharded_phase.v1", "source_lock": lock,
            "shards": [{"id": i, "tasks": tasks} for i, tasks in enumerate(pieces, 1)],
            "max_workers": args.max_workers, "start_stagger_seconds": args.start_stagger_seconds}
    if not args.execute:
        return {"status": "dry_run", "client": args.client, "phase": args.phase,
                "generation": args.generation, "task_count": sum(map(len, pieces)), "shard_count": len(pieces),
                "min_tasks_per_shard": min(map(len, pieces)), "max_tasks_per_shard": max(map(len, pieces)),
                "source_lock": lock, "paid_api_calls": 0}
    if args.output_root.exists() and any(args.output_root.iterdir()):
        raise RuntimeError("output root must be new and empty; partial runs need separate audit")
    if not os.environ.get(args.api_key_env):
        raise RuntimeError(f"{args.api_key_env} is missing")
    for tasks in pieces:
        for task in tasks:
            if not (args.data_root / "json_2.1.1" / "train" / task / "game.tw-pddl").is_file():
                raise RuntimeError(f"ALFWorld game missing: {task}")
    args.output_root.mkdir(parents=True, exist_ok=True)
    adapter = build_adapter(json.loads(args.bank.read_text(encoding="utf-8")), args.client, args.output_root / "adapter") if args.bank else None
    write_json(args.output_root / "execution_plan.json", plan)
    write_json(args.output_root / "source_lock.json", lock)
    write_json(args.output_root / "status.json", {"status": "running", "started_at": datetime.now(timezone.utc).isoformat(), "launched": 0})
    active: dict[int, tuple[subprocess.Popen, Any]] = {}
    next_index = 0
    completed = 0
    try:
        while completed < len(pieces):
            finished = [(i, pair) for i, pair in active.items() if pair[0].poll() is not None]
            for index, (process, handle) in finished:
                handle.close()
                del active[index]
                if process.returncode:
                    raise RuntimeError(f"shard {index} exited {process.returncode}; inspect its process.log")
                validated_shard(args, index, pieces[index - 1])
                completed += 1
            if completed == len(pieces):
                break
            while next_index < len(pieces) and len(active) < args.max_workers:
                for finished_index, (finished_process, finished_handle) in list(active.items()):
                    if finished_process.poll() is None:
                        continue
                    finished_handle.close()
                    del active[finished_index]
                    if finished_process.returncode:
                        raise RuntimeError(f"shard {finished_index} exited {finished_process.returncode}; inspect its process.log")
                    validated_shard(args, finished_index, pieces[finished_index - 1])
                    completed += 1
                index = next_index + 1
                directory = args.output_root / "shards" / f"shard_{index:03d}"
                directory.mkdir(parents=True)
                write_json(directory / "source_lock.json", {**lock, "shard_id": index, "tasks": pieces[next_index]})
                command = shard_command(args, pieces[next_index], adapter, directory)
                write_json(directory / "command.json", {"command": command})
                handle = (directory / "process.log").open("w", encoding="utf-8")
                try:
                    process = subprocess.Popen(command, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT)
                except BaseException:
                    handle.close()
                    raise
                active[index] = (process, handle)
                next_index += 1
                write_json(args.output_root / "status.json", {"status": "running", "launched": next_index, "completed": completed})
                if next_index < len(pieces) and args.start_stagger_seconds:
                    time.sleep(args.start_stagger_seconds)
            time.sleep(0.2)
        summary = merge_results(args, pieces, lock)
        write_json(args.output_root / "status.json", {"status": "complete", "launched": next_index,
                                                       "completed": completed, "summary_file_sha256": file_hash(args.output_root / "summary.json")})
        return summary
    except BaseException as exc:
        for process, _ in active.values():
            if process.poll() is None:
                process.terminate()
        for process, handle in active.values():
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            handle.close()
        write_json(args.output_root / "status.json", {"status": "failed", "error_type": type(exc).__name__,
                                                   "error": str(exc), "launched": next_index, "completed": completed})
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=tuple("ABC"), required=True)
    parser.add_argument("--phase", choices=("training", "validation"), required=True)
    parser.add_argument("--generation", type=int, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--bank", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--api-key-env", default="DASHSCOPE_API_KEY")
    parser.add_argument("--shards", type=int, default=2)
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--pilot-tasks", type=int, default=134,
                        help="evenly sampled frozen tasks; fewer than 134 yields a non-formal pilot result")
    parser.add_argument("--start-stagger-seconds", type=float, default=1.0)
    parser.add_argument("--execute", action="store_true", help="make paid Qwen API calls")
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
