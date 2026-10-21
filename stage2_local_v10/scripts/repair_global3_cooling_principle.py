"""D-126: audit and repair one frozen Global3 aggregation field only."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from originalFL.banks import file_hash, object_hash, write_json
from stage3_2_role_agnostic_semantic_merge.round1_aggregate import (
    AggregationError, bucket_inputs, parse_json_object, utc_now,
    validate_model_output,
)


MANIFEST_SHA = "sha256:32f2d58bd62bd34f271c9ef1d5638326b35100ec6e288c3c4c39479847d4becc"
UPLOAD_SHA = "sha256:c2657e0e25d709639b84dff60e3c65803e87b3d87ce904d1be933aba1f76cde9"
ATTEMPT_SHAS = (
    "sha256:d7d9cf9992a486c3184d6f935f5c68ae1f55eb0749dc3c2c8489d4c05ea21bb4",
    "sha256:6cd4175b3bab3d7037700de16deedd3a68891cbacad4477a5d957504de595d4d",
    "sha256:c17eb5392b04d7d3ae6e1cb6fafbbf8833378fd0068e35e83991bf39595682cd",
)
BUCKET = "冷却后放置"
FIELD = "principle"
INDEX = 2  # zero-based skills[3]
REPLACEMENT = (
    "Search high-probability locations first: the cooling container, countertops, "
    "stove burners, dining table, cabinets, drawers, and shelves. Prefer visible "
    "surfaces before closed-container sweeps; open containers as needed and track "
    "visited locations. Reaching a closed container is not inspection: its contents "
    "remain unverified until opened. If the target is absent from the first expected "
    "location, continue a bounded search of plausible surfaces and containers rather "
    "than declaring failure. When found on an accessible surface, take it and proceed. "
    "If a reasonable broad search finds nothing, reassess feasibility or absence "
    "instead of checking unrelated receptacles. Do not repeat an identical broad "
    "search after obvious receptacles are exhausted; raise uncertainty when feasibility "
    "is doubtful."
)


def compress_one_field(original: dict, inputs: list[dict], replacement: str = REPLACEMENT) -> tuple[dict, list[str]]:
    _, prior_errors = validate_model_output(original, inputs)
    if prior_errors != ["skills[3].principle exceeds 900 characters"]:
        raise AggregationError(f"unexpected original validation errors: {prior_errors}")
    old = original["skills"][INDEX][FIELD]
    if not isinstance(old, str) or len(old) <= 900 or not replacement or len(replacement) > 900 or len(replacement) >= len(old):
        raise AggregationError("replacement is not a bounded compression of the overlong field")
    updated = copy.deepcopy(original)
    updated["skills"][INDEX][FIELD] = replacement
    control = copy.deepcopy(updated)
    control["skills"][INDEX][FIELD] = old
    if control != original:
        raise AggregationError("candidate changed more than the permitted field")
    cleaned, errors = validate_model_output(updated, inputs)
    if errors:
        raise AggregationError(f"repaired output failed full validation: {errors}")
    if cleaned != updated["skills"]:
        raise AggregationError("validation normalization unexpectedly changed candidate")
    return updated, prior_errors


def prepare(root: Path) -> tuple[dict, dict, dict]:
    manifest_path = root / "input_manifest.json"
    upload_path = root / "uploaded_local_b3.json"
    if file_hash(manifest_path) != MANIFEST_SHA or file_hash(upload_path) != UPLOAD_SHA:
        raise AggregationError("Global3 frozen input hash mismatch")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    upload = json.loads(upload_path.read_text(encoding="utf-8"))
    if manifest.get("round_index") != 3 or manifest.get("source_generation") != 6 or manifest.get("input_skill_count") != 280:
        raise AggregationError("Global3 manifest identity mismatch")
    inputs = bucket_inputs(upload["skills"], BUCKET)
    if len(inputs) != 28:
        raise AggregationError("cooling bucket input count changed")
    bucket_dir = root / "buckets"
    accepted = sorted(path.name for path in bucket_dir.glob("*.accepted.json"))
    if accepted != ["general.accepted.json", "task_01.accepted.json", "task_02.accepted.json", "task_03.accepted.json", "task_04.accepted.json"]:
        raise AggregationError("completed bucket set changed")
    for name in ("task_05.accepted.json", "task_05.record.json", "task_05.manual_repair_audit.json"):
        if (bucket_dir / name).exists():
            raise AggregationError(f"refusing to overwrite {name}")
    attempts = [bucket_dir / f"task_05.attempt_{index:02d}.json" for index in (1, 2, 3)]
    if tuple(file_hash(path) for path in attempts) != ATTEMPT_SHAS:
        raise AggregationError("one of the three raw attempts changed")
    record = json.loads(attempts[-1].read_text(encoding="utf-8"))
    original = parse_json_object(record["raw_model_output"])
    updated, prior_errors = compress_one_field(original, inputs)
    old = original["skills"][INDEX][FIELD]
    audit_path = bucket_dir / "task_05.manual_repair_audit.json"
    accepted_path = bucket_dir / "task_05.accepted.json"
    audit = {
        "decision": "D-126", "kind": "single_field_human_reviewed_compression",
        "bucket": BUCKET, "source_attempt": str(attempts[-1]),
        "source_attempt_hashes": list(ATTEMPT_SHAS),
        "input_manifest_sha256": MANIFEST_SHA, "uploaded_local_b3_sha256": UPLOAD_SHA,
        "previous_accepted_bucket_hashes": {name: file_hash(bucket_dir / name) for name in accepted},
        "field_path": "skills[3].principle", "old_text": old, "new_text": REPLACEMENT,
        "old_length": len(old), "new_length": len(REPLACEMENT),
        "original_validation_errors": prior_errors,
        "repaired_validation_errors": [], "non_target_fields_unchanged": True,
        "full_validation_passed": True, "input_skill_count": len(inputs),
        "output_skill_count": len(updated["skills"]),
        "accepted_object_sha256": object_hash(updated),
        "prepared_at": utc_now(),
    }
    accepted_record = {
        "bucket": BUCKET, "input_skill_count": len(inputs),
        "output_skill_count": len(updated["skills"]),
        "accepted_attempt_file": str(attempts[-1]),
        "manual_repair_audit_file": str(audit_path),
        "manual_repair_scope": "skills[3].principle_only",
        "usage": record["usage"],
    }
    return audit, updated, accepted_record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    audit, updated, accepted_record = prepare(args.output_root)
    if args.apply:
        bucket_dir = args.output_root / "buckets"
        write_json(bucket_dir / "task_05.manual_repair_audit.json", audit)
        write_json(bucket_dir / "task_05.accepted.json", updated)
        write_json(bucket_dir / "task_05.record.json", accepted_record)
    print(json.dumps({"status": "applied" if args.apply else "checked", "old_length": audit["old_length"], "new_length": audit["new_length"], "full_validation_passed": True, "accepted_object_sha256": audit["accepted_object_sha256"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
