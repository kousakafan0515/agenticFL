"""Freeze role-mapped runtime views for validating each client's local B2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from client_code.skillbank_loader import EXPECTED_ROLES, TASK_TYPE_LABELS, parse_bank
from originalFL.banks import file_hash
from stage3_2_role_agnostic_semantic_merge.client_global_validation import object_hash, write_json


TASK_LABELS = tuple(TASK_TYPE_LABELS.values())
B2_SCHEMA = "stage3_2.local_role_agnostic_bank.v1"


class B2ValidationError(RuntimeError):
    pass


def validate_local_b2(value: dict[str, Any], client: str) -> dict[str, Any]:
    if value.get("schema_version") != B2_SCHEMA or value.get("client") != client or value.get("generation") != 2:
        raise B2ValidationError(f"Client {client}: invalid local B2 identity")
    general = value.get("general")
    specific = value.get("task_specific")
    if not isinstance(general, list) or not isinstance(specific, dict) or set(specific) != set(TASK_LABELS):
        raise B2ValidationError(f"Client {client}: malformed seven-bucket B2")
    rows = general + sum((specific[label] for label in TASK_LABELS), [])
    ids = [row.get("skill_id") for row in rows]
    if any(not isinstance(skill_id, str) or not skill_id for skill_id in ids) or len(ids) != len(set(ids)):
        raise B2ValidationError(f"Client {client}: B2 skill IDs must be unique")
    policy = value.get("capacity_policy") or {}
    expected_count = policy.get("candidate_count")
    if not policy.get("quota_passed") or policy.get("base_count") != 43 or expected_count != len(rows):
        raise B2ValidationError(f"Client {client}: invalid B2 capacity audit")
    if policy.get("add_count", 0) > policy.get("delete_count", 0) // 3:
        raise B2ValidationError(f"Client {client}: 3-delete/1-add quota violation")
    return {"general": general, "task_specific": specific}


def materialize_client(source: Path, client: str, destination: Path) -> dict[str, Any]:
    b2 = json.loads(source.read_text(encoding="utf-8"))
    repository = validate_local_b2(b2, client)
    bank = {
        "bank_schema_version": "stage3_2.client_local_b2_validation_runtime.v1",
        "experiment_id": "v9-local-b2-client-validation",
        "source_client": client,
        "target_client": client,
        "generation": 2,
        "aggregation_mode": "complete_local_role_agnostic_b2_runtime_view",
        "source_b2_file_sha256": file_hash(source),
        "source_b2_live_repository_sha256": b2.get("live_repository_sha256"),
        "capacity_policy": b2["capacity_policy"],
        "role_mapping_policy": "identical_complete_local_b2_repository_for_every_client_role",
        "active_skillbanks": {
            role: json.loads(json.dumps(repository, ensure_ascii=False))
            for role in EXPECTED_ROLES[client]
        },
    }
    parsed = parse_bank(bank, client)
    expected = b2["capacity_policy"]["candidate_count"] * len(EXPECTED_ROLES[client])
    if len(parsed) != expected:
        raise B2ValidationError(f"Client {client}: expected {expected} mapped skills, got {len(parsed)}")
    role_hashes = {object_hash(bank["active_skillbanks"][role]) for role in EXPECTED_ROLES[client]}
    if len(role_hashes) != 1:
        raise B2ValidationError(f"Client {client}: runtime role repositories differ")
    bank["live_repository_sha256"] = object_hash({
        "client": client,
        "source_b2_live_repository_sha256": b2.get("live_repository_sha256"),
        "active_skillbanks": bank["active_skillbanks"],
    })
    write_json(destination, bank)
    return {
        "client": client,
        "source_b2": str(source),
        "source_b2_file_sha256": file_hash(source),
        "logical_skill_count": b2["capacity_policy"]["candidate_count"],
        "roles": list(EXPECTED_ROLES[client]),
        "per_role_repository_hash": next(iter(role_hashes)),
        "runtime_bank": str(destination),
        "runtime_bank_file_sha256": file_hash(destination),
        "capacity_policy": b2["capacity_policy"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    manifest_path = args.output_root / "validation_input_manifest.json"
    if manifest_path.exists():
        raise SystemExit(f"refusing to overwrite validation inputs: {manifest_path}")
    clients = {
        client: materialize_client(
            args.source_root / f"client_{client}" / "B2_skillbank.json",
            client,
            args.output_root / f"client_{client}" / "runtime_skillbank.json",
        )
        for client in ("A", "B", "C")
    }
    manifest = {
        "schema_version": "stage3_2.local_b2_validation_inputs.v1",
        "experiment_id": "v9-local-b2-client-validation",
        "evaluation_policy": "each client validates its own complete local B2 on its frozen 134-task validation cohort",
        "teacher_feedback": False,
        "next_generation_enabled": False,
        "clients": clients,
    }
    write_json(manifest_path, manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
