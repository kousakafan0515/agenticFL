"""Materialize a fully validated local bank from a frozen patch using reviewed field-only replacements."""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any

from originalFL.banks import file_hash, write_json
from stage3_2_role_agnostic_semantic_merge.local_round2_evolver import (
    MAX_FIELD_CHARACTERS,
    ROLE_TOKENS,
    SKILL_FIELDS,
    extract_base_repository,
    now,
    object_hash,
    parse_json_object,
    validate_and_apply_patch,
)


MANUAL_TARGET_MAX = 650


def invalid_skill_fields(frozen_patch: dict[str, Any], dropped_numbers: set[int]) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for operation_index, operation in enumerate(frozen_patch.get("operations") or []):
        operation_number = operation_index + 1
        if operation_number in dropped_numbers or operation.get("operation") not in {"UPDATE", "ADD"}:
            continue
        skill = operation.get("skill") or {}
        for field in SKILL_FIELDS.get(skill.get("type"), ()):
            text = skill.get(field)
            role_words = [
                token for token in ROLE_TOKENS
                if isinstance(text, str) and re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", text.casefold())
            ]
            if not isinstance(text, str) or not text.strip() or len(text) > MAX_FIELD_CHARACTERS or role_words:
                targets.append({
                    "operation_index": operation_index,
                    "operation_number": operation_number,
                    "operation": operation.get("operation"),
                    "target_skill_id": operation.get("target_skill_id"),
                    "field": field,
                    "original_length": len(text) if isinstance(text, str) else None,
                    "invalid_reasons": (["empty_or_non_string"] if not isinstance(text, str) or not text.strip() else [])
                    + (["over_900_characters"] if isinstance(text, str) and len(text) > MAX_FIELD_CHARACTERS else [])
                    + ([f"forbidden_role_word:{word}" for word in role_words]),
                })
    return targets


def apply_reviewed_replacements(
    frozen_patch: dict[str, Any], repair_spec: dict[str, Any], target_max: int = MANUAL_TARGET_MAX,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[int]]:
    if set(repair_spec) != {"replacements", "drop_add_operation_numbers"}:
        raise ValueError("repair spec must contain exactly replacements and drop_add_operation_numbers")
    dropped = repair_spec["drop_add_operation_numbers"]
    if not isinstance(dropped, list) or any(not isinstance(number, int) for number in dropped) or len(dropped) != len(set(dropped)):
        raise ValueError("drop_add_operation_numbers must be a unique integer list")
    operations = frozen_patch.get("operations") or []
    for number in dropped:
        if number < 1 or number > len(operations) or operations[number - 1].get("operation") != "ADD":
            raise ValueError(f"only existing ADD operations may be dropped; got {number}")
    dropped_set = set(dropped)
    targets = invalid_skill_fields(frozen_patch, dropped_set)
    expected = {(row["operation_number"], row["field"]) for row in targets}
    replacements: dict[tuple[int, str], str] = {}
    rows = repair_spec["replacements"]
    if not isinstance(rows, list):
        raise ValueError("replacements must be a list")
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict) or set(row) != {"operation_number", "field", "text"}:
            raise ValueError(f"replacement {index} has invalid fields")
        key = (row["operation_number"], row["field"])
        text = row["text"]
        if key not in expected or key in replacements:
            raise ValueError(f"replacement {index} is unknown or duplicated: {key!r}")
        if not isinstance(text, str) or not text.strip() or len(text) > target_max:
            raise ValueError(f"replacement {index} must be 1..{target_max} characters")
        replacements[key] = text.strip()
    if set(replacements) != expected:
        raise ValueError(f"replacement set mismatch: expected {sorted(expected)}, got {sorted(replacements)}")

    candidate = copy.deepcopy(frozen_patch)
    for (operation_number, field), text in replacements.items():
        candidate["operations"][operation_number - 1]["skill"][field] = text
    before = copy.deepcopy(frozen_patch)
    after = copy.deepcopy(candidate)
    for target in targets:
        index, field = target["operation_index"], target["field"]
        before["operations"][index]["skill"][field] = "<REVIEWED_FIELD>"
        after["operations"][index]["skill"][field] = "<REVIEWED_FIELD>"
    if before != after:
        raise ValueError("manual repair changed content outside reviewed fields")
    for number in sorted(dropped, reverse=True):
        del candidate["operations"][number - 1]
    return candidate, targets, sorted(dropped)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", choices=("B", "C"), required=True)
    parser.add_argument("--generation", type=int, default=3)
    parser.add_argument("--expected-base-count", type=int, default=44)
    parser.add_argument("--parent-label")
    parser.add_argument("--experiment-id")
    parser.add_argument("--parent-bank", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--source-attempt", type=Path, required=True)
    parser.add_argument("--replacements", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--patch-output", type=Path, required=True)
    parser.add_argument("--record-output", type=Path, required=True)
    parser.add_argument("--audit-output", type=Path, required=True)
    args = parser.parse_args()
    parent_label = args.parent_label or f"Global SkillBank{args.generation - 1}"
    experiment_id = args.experiment_id or f"v9-global{args.generation - 1}-to-local-b{args.generation}"

    destinations = (args.output, args.patch_output, args.record_output, args.audit_output)
    if any(path.exists() for path in destinations):
        raise SystemExit("refusing to overwrite manual-repair output")

    parent = json.loads(args.parent_bank.read_text(encoding="utf-8"))
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    checkpoint = json.loads(args.checkpoint.read_text(encoding="utf-8"))
    attempt_record = json.loads(args.source_attempt.read_text(encoding="utf-8"))
    replacements = json.loads(args.replacements.read_text(encoding="utf-8"))

    if evidence.get("client_id") != args.client or evidence.get("generation") != args.generation:
        raise SystemExit("evidence identity mismatch")
    if len(evidence.get("episodes") or []) != 134:
        raise SystemExit("complete 134-episode evidence is required")
    if evidence.get("parent_bank_file_sha256") != file_hash(args.parent_bank):
        raise SystemExit("evidence parent-bank hash mismatch")
    identity = {
        "client": args.client,
        "evidence_file_sha256": file_hash(args.evidence),
        "parent_bank_file_sha256": file_hash(args.parent_bank),
    }
    if any(checkpoint.get(key) != value for key, value in identity.items()):
        raise SystemExit("checkpoint identity mismatch")

    repository = extract_base_repository(parent, args.client)
    base_count = len(repository["general"]) + sum(len(rows) for rows in repository["task_specific"].values())
    if base_count != args.expected_base_count:
        raise SystemExit(f"expected {args.expected_base_count} base skills, got {base_count}")

    frozen_patch = parse_json_object(str(attempt_record.get("raw_model_output") or ""))
    candidate_patch, targets, dropped_operations = apply_reviewed_replacements(frozen_patch, replacements)
    candidate_repository, operations, counts = validate_and_apply_patch(
        candidate_patch, repository, args.client, args.generation
    )

    bank = {
        "schema_version": "stage3_2.local_role_agnostic_bank.v1",
        "experiment_id": experiment_id,
        "client": args.client,
        "generation": args.generation,
        "parent": parent_label,
        "parent_bank_file_sha256": file_hash(args.parent_bank),
        "evidence_file_sha256": file_hash(args.evidence),
        "capacity_policy": {
            "policy": "three_distinct_deletes_per_add",
            "delete_count": counts["delete"],
            "add_count": counts["add"],
            "update_count": counts["update"],
            "base_count": args.expected_base_count,
            "candidate_count": counts["candidate"],
            "quota_passed": counts["add"] <= counts["delete"] // 3,
        },
        "general": candidate_repository["general"],
        "task_specific": candidate_repository["task_specific"],
        "teacher": checkpoint.get("teacher"),
    }
    bank["live_repository_sha256"] = object_hash({"general": bank["general"], "task_specific": bank["task_specific"]})
    patch_doc = {
        "schema_version": "stage3_2.local_net_patch.v1",
        "client": args.client,
        "round_index": args.generation,
        "base_bank_file_sha256": file_hash(args.parent_bank),
        "counts": counts,
        "operations": operations,
        "candidate_live_repository_sha256": bank["live_repository_sha256"],
    }
    audit = {
        "schema_version": "stage3_2.reviewed_field_only_repair.v1",
        "client": args.client,
        "generation": args.generation,
        "policy": "human_reviewed_targeted_compression_no_teacher_call",
        "parent": parent_label,
        "experiment_id": experiment_id,
        "source_attempt": str(args.source_attempt),
        "source_attempt_file_sha256": file_hash(args.source_attempt),
        "source_patch_object_sha256": object_hash(frozen_patch),
        "frozen_checkpoint": str(args.checkpoint),
        "frozen_checkpoint_file_sha256": file_hash(args.checkpoint),
        "replacement_spec": str(args.replacements),
        "replacement_spec_file_sha256": file_hash(args.replacements),
        "authorized_fields": targets,
        "dropped_add_operation_numbers": dropped_operations,
        "target_max_characters": MANUAL_TARGET_MAX,
        "candidate_patch_object_sha256": object_hash(candidate_patch),
        "complete_validation": {
            "schema_and_field_limits": True,
            "role_neutral_wording": True,
            "targets_exist_and_are_unique": True,
            "three_delete_one_add_quota": True,
            "candidate_count_arithmetic": True,
            "exact_semantic_duplicate_check": True,
        },
        "counts": counts,
        "completed_at": now(),
    }
    write_json(args.patch_output, patch_doc)
    write_json(args.output, bank)
    write_json(args.audit_output, audit)
    write_json(args.record_output, {
        "schema_version": 1,
        **identity,
        "teacher": checkpoint.get("teacher"),
        "generation": args.generation,
        "capacity_policy": bank["capacity_policy"],
        "patch_file_sha256": file_hash(args.patch_output),
        "bank_file_sha256": file_hash(args.output),
        "records": [{
            "stage": "final_patch_human_reviewed_field_compression",
            "audit_file": str(args.audit_output),
            "audit_file_sha256": file_hash(args.audit_output),
            "counts": counts,
            "completed_at": audit["completed_at"],
        }],
    })
    print(json.dumps({"status": "complete", "client": args.client, "counts": counts}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
