"""Run originalFL Local or Server paired ALFWorld validation.

This is the explicit expensive boundary.  Importing it or using --dry-run does
not call a model.  A real run requires the named API-key environment variable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from stage2_local_v12.runtime.banks import bank_hash, file_hash, write_json
from stage2_local_v12.runtime.runtime_adapter import build_adapter


ROOT = Path(__file__).resolve().parents[2]
CLIENT_SCRIPTS = {
    client: ROOT / "stage2_local_v12" / "clients" / f"alfworld_client_{client.lower()}.py"
    for client in "ABC"
}
FIXED_ARGS = {
    "A": ["--operation-card", "--operation-card-mode", "weak"],
    "B": ["--operation-card-mode", "weak"],
    "C": ["--operation-card-mode", "weak"],
}
TYPE_PREFIX = {
    "pick_and_place_simple": 1, "look_at_obj_in_light": 2,
    "pick_clean_then_place_in_recep": 3, "pick_heat_then_place_in_recep": 4,
    "pick_cool_then_place_in_recep": 5, "pick_two_obj_and_place": 6,
}
API_MARKERS = ("apierror", "authenticationerror", "ratelimiterror", "timeout", "arrearage", "overdue-payment")


class EvaluationError(RuntimeError):
    pass


def task_type(task_id: str) -> int:
    prefix = task_id.split("-", 1)[0]
    if prefix not in TYPE_PREFIX:
        raise EvaluationError(f"Cannot derive task type from {task_id}")
    return TYPE_PREFIX[prefix]


def _command(args: argparse.Namespace, client: str, task_id: str, adapter: dict[str, str],
             output: Path, trace: Path) -> list[str]:
    game = args.data_root / "json_2.1.1" / "train" / task_id / "game.tw-pddl"
    return [
        str(args.python), str(CLIENT_SCRIPTS[client]), "--api-key-env", args.api_key_env,
        "--base-url", args.base_url, "--model", args.model, "--data-dir", str(args.data_root),
        "--split", "train", "--games-per-type", "1", "--task-types", str(task_type(task_id)),
        "--only-game-file", str(game), "--max-steps", "50", "--history-window-turns", "10",
        "--request-timeout", "60", "--transport-retries", "3", "--generation-seed", str(args.seed),
        "--send-disable-thinking", "--skill-mode", "global", "--skillbank", adapter["skillbank"],
        "--skill-manifest", adapter["manifest"], "--skill-capacity-profile", adapter["capacity_profile"],
        "--output", str(output), "--trace-file", str(trace), *FIXED_ARGS[client],
    ]


def _read_success(path: Path, expected_game: Path) -> bool:
    payload = json.loads(path.read_text(encoding="utf-8"))
    episodes = payload.get("episodes")
    if not isinstance(episodes, list) or len(episodes) != 1:
        raise EvaluationError(f"Expected one episode in {path}")
    episode = episodes[0]
    if Path(str(episode.get("game_file"))).as_posix() != expected_game.as_posix():
        raise EvaluationError(f"Result game mismatch in {path}")
    rendered = json.dumps(payload, ensure_ascii=False).casefold()
    if any(marker in rendered for marker in API_MARKERS):
        raise EvaluationError(f"API failure marker in {path}")
    return bool(episode.get("success"))


def _run_condition(args: argparse.Namespace, client: str, task_id: str, condition: str,
                   adapter: dict[str, str], pair_root: Path) -> bool:
    condition_root = pair_root / condition
    output = condition_root / "result.json"
    trace = condition_root / "trace.jsonl"
    log = condition_root / "process.log"
    expected_game = args.data_root / "json_2.1.1" / "train" / task_id / "game.tw-pddl"
    if output.is_file():
        return _read_success(output, expected_game)
    condition_root.mkdir(parents=True, exist_ok=True)
    command = _command(args, client, task_id, adapter, output, trace)
    if args.dry_run:
        write_json(condition_root / "command.json", {"command": command})
        return False
    with log.open("w", encoding="utf-8") as handle:
        completed = subprocess.run(command, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT)
    if completed.returncode != 0:
        raise EvaluationError(f"Client {client} exited {completed.returncode}; see {log}")
    return _read_success(output, expected_game)


def _run_pair(args: argparse.Namespace, client: str, task_id: str, adapters: dict[str, dict[str, str]]) -> dict[str, Any]:
    pair_key = hashlib.sha256(f"{client}|{task_id}|{args.seed}".encode()).hexdigest()[:12]
    pair_root = args.output_root / "pairs" / client / pair_key
    order = ["parent", "candidate"] if int(pair_key[:2], 16) % 2 == 0 else ["candidate", "parent"]
    values: dict[str, bool] = {}
    for condition in order:
        values[condition] = _run_condition(args, client, task_id, condition, adapters[condition], pair_root)
    return {
        "task_id": task_id, "task_type_id": task_type(task_id), "api_clean": True,
        "parent_success": values["parent"], "candidate_success": values["candidate"],
        "condition_order": order,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run originalFL paired validation")
    parser.add_argument("--scope", choices=("local", "server"), required=True)
    parser.add_argument("--client", choices=tuple("ABC"), help="required for local scope")
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--parent-bank", type=Path, required=True)
    parser.add_argument("--candidate-bank", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--model", default="qwen3.6-flash")
    parser.add_argument("--base-url", default="https://dashscope.aliyuncs.com/compatible-mode/v1")
    parser.add_argument("--api-key-env", default="DASHSCOPE_API_KEY")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.scope == "local" and args.client is None:
        raise SystemExit("--client is required for local scope")
    if not args.dry_run and not os.environ.get(args.api_key_env):
        raise SystemExit(f"{args.api_key_env} is missing")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    parent = json.loads(args.parent_bank.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate_bank.read_text(encoding="utf-8"))
    clients = (args.client,) if args.scope == "local" else tuple("ABC")
    task_ids = (
        manifest["clients"][args.client]["local_validation_core_tasks"]
        if args.scope == "local" else manifest["server_validation"]["tasks"]
    )
    all_outcomes: dict[str, list[dict[str, Any]]] = {}
    for client in clients:
        adapters = {
            "parent": build_adapter(parent, client, args.output_root / "adapters" / client / "parent"),
            "candidate": build_adapter(candidate, client, args.output_root / "adapters" / client / "candidate"),
        }
        all_outcomes[client] = [_run_pair(args, client, task_id, adapters) for task_id in task_ids]
    if args.dry_run:
        print(json.dumps({"status": "dry_run", "pairs_planned": len(task_ids) * len(clients) * 2}, indent=2))
        return
    if args.scope == "local":
        result = {
            "schema_version": 1, "scope": "local", "client_id": args.client,
            "round_index": args.round, "parent_local_bank_sha256": bank_hash(parent),
            "candidate_local_bank_sha256": bank_hash(candidate), "outcomes": all_outcomes[args.client],
        }
    else:
        result = {
            "schema_version": 1, "scope": "server", "round_index": args.round,
            "parent_global_bank_sha256": bank_hash(parent),
            "candidate_global_bank_sha256": bank_hash(candidate), "clients": all_outcomes,
        }
    result["runtime_lock"] = {
        "model": args.model, "base_url": args.base_url, "seed": args.seed,
        "manifest_sha256": file_hash(args.manifest),
        "parent_bank_file_sha256": file_hash(args.parent_bank),
        "candidate_bank_file_sha256": file_hash(args.candidate_bank),
        "client_runtime_sha256": {client: file_hash(CLIENT_SCRIPTS[client]) for client in clients},
    }
    write_json(args.output, result)
    print(json.dumps({"status": "complete", "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()
