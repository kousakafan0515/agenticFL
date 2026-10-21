"""Read-only guard for the frozen V10 Global2 validation prefixes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from originalFL.banks import file_hash, write_json
from stage2_local_v10.downlink import expected_bank
from stage2_local_v10.materialize_assets import EXPERIMENT_ID
from stage2_local_v6.scripts.run_client_a_phase import task_from_game_file


PREFIX_COUNTS = {"A": 88, "B": 103, "C": 105}
ROOT = Path(__file__).resolve().parents[2]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def audit(run_root: Path) -> dict:
    top = read_json(run_root / "controller_state.json")
    if top.get("status") != "failed" or top.get("current_step") != "validate_2":
        raise RuntimeError("expected failed validate_2 top controller")
    global_bank = run_root / "globals/Global2/aggregation/global_skillbank2.json"
    aggregation = read_json(run_root / "globals/Global2/aggregation/summary.json")
    global_hash = file_hash(global_bank)
    if aggregation.get("status") != "complete" or aggregation.get("global_skillbank", {}).get("file_sha256") != global_hash:
        raise RuntimeError("Global2 aggregate is incomplete or changed")
    validation_root = run_root / "globals/Global2/validation"
    state = read_json(validation_root / "controller_state.json")
    if state.get("status") != "failed" or state.get("global_round") != 2 or state.get("generation") != 4 or state.get("global_bank_file_sha256") != global_hash:
        raise RuntimeError("Global2 validation state identity mismatch")
    clients = {}
    for client, expected_prefix in PREFIX_COUNTS.items():
        lower = client.lower()
        base = validation_root / f"client_{client}"
        replacement = base / "replacement_skillbank.json"
        actual = read_json(replacement)
        expected = expected_bank(global_bank, client, 4, global_hash, EXPERIMENT_ID, global_round=2)
        if actual != expected:
            raise RuntimeError(f"Client {client}: replacement differs from frozen Global2")
        phase = base / "validation"
        if (phase / "summary.json").exists() or (phase / "resume_segments").exists():
            raise RuntimeError(f"Client {client}: existing summary or resume segment")
        manifest_path = ROOT / f"stage2_local_v10/artifacts/manifests/client_{lower}_generation_01.json"
        manifest = read_json(manifest_path)
        lock = read_json(phase / "source_lock.json")
        expected_lock = {
            "experiment_id": EXPERIMENT_ID, "client": client, "phase": "validation", "generation": 4,
            "manifest_file_sha256": file_hash(manifest_path), "manifest_content_hash": manifest["manifest_content_hash"],
            "bank_file_sha256": file_hash(replacement), "bank_live_repository_sha256": actual.get("live_repository_sha256"),
            "model": "qwen3.6-flash", "temperature": 0, "seed": 1234, "thinking": False,
        }
        if lock != expected_lock:
            raise RuntimeError(f"Client {client}: source lock differs from frozen input")
        prefix_path = phase / "result.json"
        prefix = read_json(prefix_path).get("episodes")
        if not isinstance(prefix, list) or len(prefix) != expected_prefix:
            raise RuntimeError(f"Client {client}: expected {expected_prefix} frozen episodes")
        reference_path = run_root / f"globals/Global1/validation/client_{client}/validation/result.json"
        reference = read_json(reference_path).get("episodes")
        reference_summary = read_json(reference_path.parent / "summary.json")
        if not isinstance(reference, list) or len(reference) != 134 or reference_summary.get("api_clean") is not True or reference_summary.get("result_file_sha256") != file_hash(reference_path):
            raise RuntimeError(f"Client {client}: Global1 reference is not frozen and API-clean")
        tasks = manifest["validation"]["tasks"]
        reference_order = [task_from_game_file(row["game_file"]) for row in reference]
        prefix_order = [task_from_game_file(row["game_file"]) for row in prefix]
        if len(set(reference_order)) != 134 or set(reference_order) != set(tasks) or prefix_order != reference_order[:expected_prefix]:
            raise RuntimeError(f"Client {client}: result is not an exact frozen-order prefix")
        if any(not isinstance(row.get("success"), bool) for row in prefix):
            raise RuntimeError(f"Client {client}: malformed prefix success field")
        clients[client] = {
            "completed_episodes": expected_prefix,
            "successful_episodes": sum(row["success"] for row in prefix),
            "remaining_episodes": 134 - expected_prefix,
            "prefix_result_file_sha256": file_hash(prefix_path),
            "source_lock_file_sha256": file_hash(phase / "source_lock.json"),
            "replacement_bank_file_sha256": file_hash(replacement),
            "manifest_file_sha256": file_hash(manifest_path),
            "reference_result_file_sha256": file_hash(reference_path),
        }
    return {"schema_version": "stage2_local_v10.global2_resume_audit.v1", "global_bank_file_sha256": global_hash, "clients": clients}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--audit-output", type=Path)
    args = parser.parse_args()
    result = audit(args.run_root)
    if args.audit_output:
        if args.audit_output.exists():
            raise SystemExit("refusing to overwrite existing Global2 resume audit")
        write_json(args.audit_output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
