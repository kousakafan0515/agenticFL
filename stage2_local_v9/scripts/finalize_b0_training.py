"""Finalize a complete v9 empty-B0 training result without rerunning episodes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from originalFL.banks import canonical_bytes, file_hash, write_json
from originalFL.training_runner import sanitize_episode
from stage2_local_v6.scripts.run_client_a_phase import (
    API_MARKERS,
    MODEL,
    execution_order,
    task_from_game_file,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result_path = args.output_root / "result.json"
    lock_path = args.output_root / "source_lock.json"
    if (args.output_root / "summary.json").exists() or (args.output_root / "evidence.json").exists():
        raise SystemExit("refusing to overwrite existing B0 training finalization")
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    source_lock = json.loads(lock_path.read_text(encoding="utf-8"))
    expected_lock = {
        "experiment_id": manifest["experiment_id"],
        "client": "A",
        "phase": "training",
        "generation": 1,
        "manifest_file_sha256": file_hash(args.manifest),
        "manifest_content_hash": manifest["manifest_content_hash"],
        "bank_file_sha256": None,
        "bank_live_repository_sha256": None,
        "model": MODEL,
        "temperature": 0,
        "seed": 1234,
        "thinking": False,
    }
    if source_lock != expected_lock:
        raise SystemExit("B0 training source lock mismatch")

    episodes = list(payload.get("episodes") or [])
    if len(episodes) != 134:
        raise SystemExit(f"expected 134 B0 training episodes, got {len(episodes)}")
    actual_tasks = [task_from_game_file(row["game_file"]) for row in episodes]
    expected_tasks = execution_order(list(manifest["training"]["tasks"]))
    if set(actual_tasks) != set(expected_tasks) or len(set(actual_tasks)) != 134:
        raise SystemExit("B0 training episodes do not match the frozen 134-task cohort")
    rendered = json.dumps(payload, ensure_ascii=False).casefold()
    if any(marker in rendered for marker in API_MARKERS):
        raise SystemExit("API failure marker found in B0 training result")

    evidence = {
        "schema_version": 1,
        "experiment_id": manifest["experiment_id"],
        "client_id": "A",
        "generation": 1,
        "parent_bank": "B0",
        "parent_bank_file_sha256": None,
        "parent_live_repository_sha256": None,
        "episodes": [
            sanitize_episode(
                row,
                f"{manifest['experiment_id']}/generation_01/client_A/episode_{index:03d}",
            )
            for index, row in enumerate(episodes, 1)
        ],
    }
    evidence["evidence_sha256"] = "sha256:" + hashlib.sha256(canonical_bytes(evidence)).hexdigest()
    write_json(args.output_root / "evidence.json", evidence)
    summary = {
        "status": "complete",
        "phase": "training",
        "generation": 1,
        "client": "A",
        "model": MODEL,
        "task_count": 134,
        "success_count": sum(bool(row.get("success")) for row in episodes),
        "api_clean": True,
        "result_file_sha256": file_hash(result_path),
        "evidence_file_sha256": file_hash(args.output_root / "evidence.json"),
    }
    write_json(args.output_root / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
