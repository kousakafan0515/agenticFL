"""Run one PatchFL v3 private six-task batch and emit sanitized evolver evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from stage2_local_v12.runtime.banks import canonical_bytes, file_hash, write_json
from stage2_local_v12.runtime.paired_evaluator import CLIENT_SCRIPTS, FIXED_ARGS, ROOT, task_type
from stage2_local_v12.runtime.runtime_adapter import build_adapter


GOAL_RE = re.compile(r"Your task is to:\s*(.+?)(?:\n|$)", re.IGNORECASE)
PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/]|/mnt/)[^\s]+|\btrial_[A-Za-z0-9_]+\b|\bgame\.tw-pddl\b", re.IGNORECASE)


class TrainingError(RuntimeError):
    pass


def _clean(value: Any) -> str:
    return " ".join(PATH_RE.sub("<redacted>", str(value or "")).split())


def _events(value: Any, found: list[tuple[int, str, str]], order: list[int]) -> None:
    if isinstance(value, dict):
        action, observation = value.get("action"), value.get("observation")
        if isinstance(action, str) and isinstance(observation, str):
            order[0] += 1
            index = value.get("global_step")
            found.append((int(index) if isinstance(index, int) else 10**6 + order[0], action, observation))
        for child in value.values():
            _events(child, found, order)
    elif isinstance(value, list):
        for child in value:
            _events(child, found, order)


def _role_evidence(episode: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    roles: dict[str, list[dict[str, Any]]] = {}

    def add(role: str, row: dict[str, Any]) -> None:
        roles.setdefault(role, []).append({key: _clean(value) for key, value in row.items()})

    planner = episode.get("planner")
    if isinstance(planner, dict) and isinstance(planner.get("output"), str):
        add("Planner", {"phase": "initial_plan", "model_output": planner["output"]})
    for step in episode.get("steps", []):
        if not isinstance(step, dict):
            continue
        worker = step.get("worker")
        if worker == "SEARCH":
            role = "Search Worker"
        elif worker == "OPERATION":
            role = "Operation Worker"
        else:
            role = "Executor"
        model_output = step.get("model_output")
        if not isinstance(model_output, str):
            calls = step.get("worker_calls")
            if isinstance(calls, list) and calls and isinstance(calls[-1], dict):
                model_output = calls[-1].get("model_output")
        add(role, {
            "step": step.get("global_step", step.get("action_step", step.get("step", "unknown"))),
            "model_output": model_output or "",
            "action": step.get("action", step.get("raw_action", "")),
            "observation": step.get("observation", ""),
        })
    for call in episode.get("critic_calls", []):
        if isinstance(call, dict):
            add("Critic", {
                "after_step": call.get("after_step", "unknown"),
                "model_output": call.get("model_output", call.get("note", "")),
            })
    for call in episode.get("supervisor_calls", []):
        if isinstance(call, dict):
            add("Supervisor", {
                "trigger": (call.get("control") or {}).get("trigger", "unknown"),
                "model_output": call.get("model_output", ""),
            })
    return roles


def _skill_injection_evidence(episode: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for role, audit in (episode.get("skill_injections") or {}).items():
        if not isinstance(role, str) or not isinstance(audit, dict):
            continue
        injected_keys = list(audit.get("injected_skill_keys") or [])
        if not injected_keys:
            continue
        display = audit.get("display_id_map") or {}
        result[role] = {
            "skillbank_hash": audit.get("skillbank_hash"),
            "injected_skill_keys": injected_keys,
            "injected_skills": {
                display_id: {
                    key: row.get(key)
                    for key in ("target_skill_key", "canonical_content_hash", "type", "scope", "task_type")
                }
                for display_id, row in display.items()
                if isinstance(display_id, str) and isinstance(row, dict)
            },
        }
    return result


def sanitize_episode(episode: dict[str, Any], evidence_ref: str) -> dict[str, Any]:
    found: list[tuple[int, str, str]] = []
    _events(episode, found, [0])
    unique: list[tuple[int, str, str]] = []
    seen: set[tuple[int, str, str]] = set()
    for item in sorted(found, key=lambda row: row[0]):
        if item not in seen:
            seen.add(item)
            unique.append(item)
    initial = str(episode.get("initial_observation") or "")
    goal = GOAL_RE.search(initial)
    result = {
        "evidence_ref": evidence_ref,
        "task_type_id": int(episode["task_type_id"]),
        "goal": _clean(goal.group(1) if goal else "unknown goal"),
        "success": bool(episode.get("success")),
        "terminal_reason": _clean(episode.get("terminal_reason", episode.get("termination_reason", "unknown"))),
        "environment_actions_total": len(unique),
        "environment_events": [
            {"step": index, "action": _clean(action), "observation": _clean(observation)}
            for index, (_, action, observation) in enumerate(unique, start=1)
        ],
        "role_evidence": _role_evidence(episode),
    }
    injections = _skill_injection_evidence(episode)
    if injections:
        result["skill_injections"] = injections
    return result


def _command(args: argparse.Namespace, client: str, task_ids: list[str], adapter: dict[str, str] | None, output: Path, trace: Path) -> list[str]:
    type_counts: dict[int, int] = {}
    for task_id in task_ids:
        type_id = task_type(task_id)
        type_counts[type_id] = type_counts.get(type_id, 0) + 1
    if len(set(type_counts.values())) != 1:
        raise TrainingError(f"one-process batches require equal tasks per type, got {type_counts}")
    command = [
        str(args.python), str(CLIENT_SCRIPTS[client]), "--api-key-env", args.api_key_env,
        "--base-url", args.base_url, "--model", args.model, "--data-dir", str(args.data_root),
        "--split", "train", "--games-per-type", str(next(iter(type_counts.values()))),
        "--task-types", *[str(type_id) for type_id in sorted(type_counts)],
        "--max-steps", "50", "--history-window-turns", "10",
        "--request-timeout", "60", "--transport-retries", "3", "--generation-seed", str(args.seed),
        "--send-disable-thinking", "--output", str(output), "--trace-file", str(trace),
    ]
    for task_id in task_ids:
        game = args.data_root / "json_2.1.1" / "train" / task_id / "game.tw-pddl"
        command.extend(["--only-game-file", str(game)])
    if adapter is None:
        command.extend(["--skill-mode", "none"])
    else:
        command.extend([
            "--skill-mode", "global", "--skillbank", adapter["skillbank"],
            "--skill-manifest", adapter["manifest"],
            "--skill-capacity-profile", adapter["capacity_profile"],
        ])
    command.extend(FIXED_ARGS[client])
    return command


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect one originalFL private training batch")
    parser.add_argument("--client", choices=tuple("ABC"), required=True)
    parser.add_argument("--experiment-id", default="patchFL-v3")
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--cycle", type=int, required=True)
    parser.add_argument("--batch", type=int, required=True)
    parser.add_argument("--bank", type=Path, default=None)
    parser.add_argument("--cold-start", action="store_true")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--model", default="qwen3.6-flash")
    parser.add_argument("--base-url", default="https://dashscope.aliyuncs.com/compatible-mode/v1")
    parser.add_argument("--api-key-env", default="DASHSCOPE_API_KEY")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--episode-limit", type=int, default=None, help="Smoke-only prefix limit; never use its evidence for evolution")
    args = parser.parse_args()
    if not args.dry_run and not os.environ.get(args.api_key_env):
        raise SystemExit(f"{args.api_key_env} is missing")
    if args.cold_start:
        if (args.round, args.cycle, args.batch) != (1, 1, 1) or args.bank is not None:
            raise TrainingError("cold start is allowed only for Round 1/Cycle 1/Batch 1 with no bank")
    elif args.bank is None:
        raise TrainingError("non-cold-start batches require --bank")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    stages = manifest["clients"][args.client]["local_evolution"]["stages"]
    task_ids = stages[args.round - 1]["cycles"][args.cycle - 1]["batches"][args.batch - 1]["tasks"]
    if len(task_ids) != 6:
        raise TrainingError("frozen v3 local batch must contain exactly 6 tasks")
    if args.episode_limit is not None:
        if args.episode_limit < 1 or args.episode_limit > 6:
            raise TrainingError("--episode-limit must be between 1 and 6")
        task_ids = task_ids[: args.episode_limit]
    bank = json.loads(args.bank.read_text(encoding="utf-8")) if args.bank else None
    adapter = build_adapter(bank, args.client, args.output_root / "adapter") if bank else None
    batch_root = args.output_root / "batch_runtime"
    result_path, trace_path, log_path = batch_root / "result.json", batch_root / "trace.jsonl", batch_root / "process.log"
    batch_root.mkdir(parents=True, exist_ok=True)
    command = _command(args, args.client, task_ids, adapter, result_path, trace_path)
    if args.dry_run:
        write_json(batch_root / "command.json", {"command": command})
    elif not result_path.is_file():
        with log_path.open("w", encoding="utf-8") as handle:
            completed = subprocess.run(command, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT)
        if completed.returncode != 0:
            raise TrainingError(f"training batch exited {completed.returncode}; see {log_path}")
    if args.dry_run:
        print(json.dumps({"status": "dry_run", "episodes_planned": len(task_ids)}, indent=2))
        return
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    episodes = payload.get("episodes", [])
    if len(episodes) != len(task_ids):
        raise TrainingError(f"expected {len(task_ids)} episodes in {result_path}, got {len(episodes)}")
    by_task: dict[str, dict[str, Any]] = {}
    for episode in episodes:
        game_file = str(episode.get("game_file", "")).replace("\\", "/")
        matches = [task_id for task_id in task_ids if game_file.endswith(f"/train/{task_id}/game.tw-pddl")]
        if len(matches) != 1 or matches[0] in by_task:
            raise TrainingError(f"cannot uniquely match episode game file: {game_file}")
        by_task[matches[0]] = episode
    sanitized = [
        sanitize_episode(
            by_task[task_id],
            f"{args.experiment_id}/round_{args.round}/cycle_{args.cycle}/batch_{args.batch}/client_{args.client}/episode_{index}",
        )
        for index, task_id in enumerate(task_ids, start=1)
    ]
    if args.episode_limit is not None:
        write_json(args.output, {
            "schema_version": 1, "experiment_id": "patchFL-v3-smoke",
            "client_id": args.client, "round_index": args.round, "cycle_index": args.cycle,
            "batch_index": args.batch, "episodes": sanitized, "usable_for_evolution": False,
        })
        print(json.dumps({"status": "smoke_complete", "output": str(args.output)}, indent=2))
        return
    document = {
        "schema_version": 2, "experiment_id": args.experiment_id, "client_id": args.client,
        "round_index": args.round, "cycle_index": args.cycle, "batch_index": args.batch,
        "episodes": sanitized, "usable_for_evolution": True,
        "source_lock": {
            "bank_file_sha256": file_hash(args.bank) if args.bank else None,
            "cold_start": args.cold_start, "manifest_sha256": file_hash(args.manifest),
            "model": args.model, "base_url": args.base_url, "seed": args.seed,
        },
    }
    document["evidence_sha256"] = "sha256:" + hashlib.sha256(canonical_bytes(document)).hexdigest()
    write_json(args.output, document)
    print(json.dumps({"status": "complete", "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
