"""Aggregate three complete same-generation local SkillBanks into one Global bank."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from stage3_2_role_agnostic_semantic_merge.round1_aggregate import (
    BUCKETS, TASK_LABELS, AggregationError, _manifest_identity_without_display_paths,
    _semantic_skill, bucket_slug, call_model, file_hash, object_hash, parse_json_object,
    system_prompt, user_prompt, utc_now, validate_model_output, write_json,
)
from stage3_2_role_agnostic_semantic_merge.round2_aggregate import (
    add_upstream_lineage, bucket_inputs,
)

SCHEMA_VERSION = "stage3_2.role_agnostic_semantic_global.v1"


def load_local_banks(bank_paths: dict[str, Path], validation_paths: dict[str, Path], generation: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {}
    for client in "ABC":
        bank_path, validation_path = bank_paths[client], validation_paths[client]
        bank = json.loads(bank_path.read_text(encoding="utf-8"))
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        if bank.get("schema_version") != "stage3_2.local_role_agnostic_bank.v1" or bank.get("client") != client or bank.get("generation") != generation:
            raise AggregationError(f"{bank_path}: expected Client {client} B{generation}")
        required = {"status": "complete", "client": client, "generation": generation, "phase": "validation", "task_count": 134, "api_clean": True}
        if any(validation.get(key) != value for key, value in required.items()):
            raise AggregationError(f"{validation_path}: complete API-clean B{generation} validation required")
        capacity = bank.get("capacity_policy") or {}
        if capacity.get("quota_passed") is not True or capacity.get("add_count", 0) > capacity.get("delete_count", 0) // 3:
            raise AggregationError(f"Client {client}: local quota audit failed")
        general, specific = bank.get("general"), bank.get("task_specific")
        if not isinstance(general, list) or not isinstance(specific, dict) or set(specific) != set(TASK_LABELS):
            raise AggregationError(f"{bank_path}: malformed seven-bucket repository")
        seen: set[str] = set()
        count = 0
        for bucket, skills in (("general", general), *specific.items()):
            for index, raw in enumerate(skills, 1):
                skill_id = raw.get("skill_id") if isinstance(raw, dict) else None
                if not isinstance(skill_id, str) or not skill_id or skill_id in seen:
                    raise AggregationError(f"{bank_path}/{bucket}/{index}: invalid or duplicate skill_id")
                seen.add(skill_id)
                upstream = raw.get("source_skill_keys")
                if not isinstance(upstream, list) or not upstream or any(not isinstance(key, str) or not key for key in upstream):
                    raise AggregationError(f"{bank_path}/{bucket}/{skill_id}: malformed lineage")
                rows.append({
                    "source_skill_key": f"{client}/{bucket}/{skill_id}", "source_client": client,
                    "source_skill_id": skill_id, "bucket": bucket,
                    "skill": _semantic_skill(raw, f"{bank_path}/{bucket}/{skill_id}"),
                    "upstream_source_skill_keys": sorted(set(upstream)),
                })
                count += 1
        if count != capacity.get("candidate_count"):
            raise AggregationError(f"Client {client}: repository/capacity count mismatch")
        manifest[client] = {
            "bank_path": str(bank_path), "bank_file_sha256": file_hash(bank_path),
            "bank_live_hash": object_hash({"general": general, "task_specific": specific}),
            "validation_summary_path": str(validation_path),
            "validation_summary_sha256": file_hash(validation_path), "skill_count": count,
            "capacity_policy": capacity,
        }
    keys = [row["source_skill_key"] for row in rows]
    if len(keys) != len(set(keys)):
        raise AggregationError("uploaded source keys are not unique")
    return rows, manifest


def run(args: argparse.Namespace) -> dict[str, Any]:
    args.output_root.mkdir(parents=True, exist_ok=True)
    banks = {c: Path(getattr(args, f"bank_{c.lower()}")) for c in "ABC"}
    validations = {c: Path(getattr(args, f"validation_{c.lower()}")) for c in "ABC"}
    rows, inputs = load_local_banks(banks, validations, args.round_index)
    experiment_id = args.experiment_id or f"v9-local-b{args.round_index}-semantic-global{args.round_index}"
    identity = {
        "experiment_id": experiment_id, "round_index": args.round_index,
        "input_mode": f"three_complete_local_b{args.round_index}_skillbanks",
        "inputs": inputs, "input_skill_count": len(rows), "input_rows_hash": object_hash(rows),
        "buckets": {b: len(bucket_inputs(rows, b)) for b in BUCKETS},
        "model": "deepseek-flash", "endpoint_origin": "https://api.deepseek.com",
        "temperature": 0, "seed": args.seed, "max_tokens": args.max_tokens,
        "server_evaluation": None, "automatic_downlink": False,
    }
    manifest_path = args.output_root / "input_manifest.json"
    uploads_path = args.output_root / f"uploaded_local_b{args.round_index}.json"
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        if _manifest_identity_without_display_paths(old) != _manifest_identity_without_display_paths(identity):
            raise AggregationError("refusing resume: input manifest identity changed")
    else:
        write_json(manifest_path, identity)
    upload = {"skills": rows}
    if uploads_path.exists() and json.loads(uploads_path.read_text(encoding="utf-8")) != upload:
        raise AggregationError("refusing resume: uploaded complete banks changed")
    if not uploads_path.exists():
        write_json(uploads_path, upload)
    if args.prepare_only:
        return {"status": "prepared", **identity}

    from stage3_federation.aggregation_api import AggregationAPIConfig
    config = AggregationAPIConfig.from_env()
    descriptor = config.descriptor()
    if descriptor.get("provider") != "deepseek_official" or descriptor.get("endpoint_origin") != "https://api.deepseek.com" or config.model != "deepseek-flash":
        raise AggregationError(f"DeepSeek official deepseek-flash required, got {descriptor}")
    bucket_results: dict[str, list[dict[str, Any]]] = {}
    records: list[dict[str, Any]] = []
    for bucket in BUCKETS:
        model_rows, source_rows, slug = bucket_inputs(rows, bucket), [r for r in rows if r["bucket"] == bucket], bucket_slug(bucket)
        accepted_path = args.output_root / "buckets" / f"{slug}.accepted.json"
        record_path = args.output_root / "buckets" / f"{slug}.record.json"
        if accepted_path.exists() and record_path.exists():
            accepted = json.loads(accepted_path.read_text(encoding="utf-8"))
            cleaned, errors = validate_model_output(accepted, model_rows)
            if errors:
                raise AggregationError(f"resume bucket {bucket} invalid: {errors}")
            bucket_results[bucket] = add_upstream_lineage(cleaned, source_rows)
            records.append(json.loads(record_path.read_text(encoding="utf-8")))
            continue
        prior_errors: list[str] | None = None
        offset = len(list((args.output_root / "buckets").glob(f"{slug}.attempt_*.json")))
        for retry in range(1, args.schema_attempts + 1):
            attempt = offset + retry
            raw, reasoning, usage = call_model(config, [{"role": "system", "content": system_prompt()}, {"role": "user", "content": user_prompt(bucket, model_rows, prior_errors)}], args)
            attempt_path = args.output_root / "buckets" / f"{slug}.attempt_{attempt:02d}.json"
            write_json(attempt_path, {"bucket": bucket, "attempt": attempt, "raw_model_output": raw, "model_reasoning": reasoning, "usage": usage, "completed_at": utc_now()})
            try:
                parsed = parse_json_object(raw)
                cleaned, errors = validate_model_output(parsed, model_rows)
            except (json.JSONDecodeError, AggregationError) as exc:
                cleaned, errors = [], [f"JSON/schema parse error: {exc}"]
            if not errors:
                accepted = {"skills": cleaned}
                write_json(accepted_path, accepted)
                record = {"bucket": bucket, "input_skill_count": len(model_rows), "output_skill_count": len(cleaned), "input_source_count": len(model_rows), "accounted_source_count": sum(len(s["source_skill_keys"]) for s in cleaned), "model_attempts": attempt, "accepted_attempt_file": str(attempt_path), "accepted_output_hash": object_hash(accepted), "usage": usage}
                write_json(record_path, record)
                bucket_results[bucket] = add_upstream_lineage(cleaned, source_rows)
                records.append(record)
                break
            prior_errors = errors
        else:
            raise AggregationError(f"bucket {bucket} exhausted schema attempts")

    general: list[dict[str, Any]] = []
    specific: dict[str, list[dict[str, Any]]] = {label: [] for label in TASK_LABELS}
    for bucket in BUCKETS:
        target = general if bucket == "general" else specific[bucket]
        prefix = "G" if bucket == "general" else f"T{TASK_LABELS.index(bucket)+1}"
        for index, skill in enumerate(bucket_results[bucket], 1):
            target.append({"global_skill_id": f"{prefix}_{index:03d}", **skill})
    output_count = len(general) + sum(map(len, specific.values()))
    if output_count > len(rows):
        raise AggregationError("global output exceeds uploaded inputs")
    global_bank = {
        "schema_version": SCHEMA_VERSION, "experiment_id": experiment_id,
        "round_index": args.round_index, "parent": f"three local B{args.round_index} SkillBanks",
        "aggregation_mode": "three_complete_local_banks_role_agnostic_seven_bucket_semantic_merge",
        "capacity": {"server_maximum_total_skills": None, "current_total_skills": output_count, "future_client_local_policy": "per_client_per_round_add_lte_floor_distinct_delete_div_3", "server_merge_creates_delete_credit": False},
        "general": general, "task_specific": specific,
        "source_input": {"uploaded_skill_instance_count": len(rows), "uploaded_banks_sha256": file_hash(uploads_path), "input_manifest_sha256": file_hash(manifest_path)},
        "aggregation_model": descriptor, "server_evaluation": None, "downlink_materialized": False,
    }
    global_bank["live_global_hash"] = object_hash({"general": general, "task_specific": specific})
    global_path = args.output_root / f"global_skillbank{args.round_index}.json"
    write_json(global_path, global_bank)
    summary = {"status": "complete", "completed_at": utc_now(), "experiment_id": experiment_id, "round_index": args.round_index, "input_skill_count": len(rows), "output_skill_count": output_count, "bucket_counts": {b: {"input": len(bucket_inputs(rows, b)), "output": len(bucket_results[b])} for b in BUCKETS}, "global_skillbank": {"path": str(global_path), "file_sha256": file_hash(global_path), "live_global_hash": global_bank["live_global_hash"]}, "server_evaluation_performed": False, "downlink_materialized": False, "records": records}
    write_json(args.output_root / "summary.json", summary)
    return summary


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--round-index", type=int, required=True, choices=(3, 4, 5))
    for c in "ABC":
        p.add_argument(f"--bank-{c.lower()}", type=Path, required=True)
        p.add_argument(f"--validation-{c.lower()}", type=Path, required=True)
    p.add_argument("--output-root", type=Path, required=True)
    p.add_argument("--experiment-id")
    p.add_argument("--prepare-only", action="store_true")
    p.add_argument("--timeout", type=float, default=240.0)
    p.add_argument("--max-tokens", type=int, default=16000)
    p.add_argument("--seed", type=int, default=1234)
    p.add_argument("--transport-retries", type=int, default=3)
    p.add_argument("--schema-attempts", type=int, default=3)
    return p


def main() -> int:
    print(json.dumps(run(parser().parse_args()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
