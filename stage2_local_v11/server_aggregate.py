"""Merge complete v11 per-role local SkillBanks into one seven-bucket Global.

No server evaluation and no patch transport. Every role upload is a distinct,
auditable source, while the output remains role agnostic.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from client_code.skillbank_loader import EXPECTED_ROLES, parse_bank
from originalFL.banks import file_hash, write_json
from stage2_local_v11.import_v9_b1 import verify_imported_seed
from stage2_local_v11.materialize_assets import EXPERIMENT_ID
from stage2_local_v11.role_evolver import SCHEMA, TASK_LABELS, repository_rows
from stage3_2_role_agnostic_semantic_merge.round1_aggregate import (
    BUCKETS, AggregationError, _semantic_skill, bucket_inputs, bucket_slug,
    call_model, object_hash, parse_json_object, system_prompt, user_prompt,
    utc_now, validate_model_output,
)
from stage3_2_role_agnostic_semantic_merge.round2_aggregate import add_upstream_lineage


GLOBAL_SCHEMA = "stage3_2.role_agnostic_semantic_global.v1"


def load_initial_uploads(bank_paths: dict[str, Path], validation_paths: dict[str, Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """B1 is open-build: no DELETE credit or predetermined 151-skill count."""
    rows: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {}
    for client in "ABC":
        bank_path, validation_path = bank_paths[client], validation_paths[client]
        bank = json.loads(bank_path.read_text(encoding="utf-8"))
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        if bank.get("generation") != 1 or bank.get("target_client") != client:
            raise AggregationError(f"{bank_path}: expected Client {client} B1")
        if bank.get("experiment_id") == EXPERIMENT_ID:
            origin = "native_v11_B1"
            import_hash = None
        else:
            imported = verify_imported_seed(bank_path, validation_path, client)
            origin = imported["classification"]
            import_hash = file_hash(bank_path.parent / "import_manifest.json")
        expected = {"status": "complete", "client": client, "generation": 1, "phase": "validation", "task_count": 134, "api_clean": True}
        if any(validation.get(key) != value for key, value in expected.items()):
            raise AggregationError(f"{validation_path}: complete API-clean B1 validation required")
        lock_path = validation_path.parent / "source_lock.json"
        if not lock_path.exists() or json.loads(lock_path.read_text(encoding="utf-8")).get("bank_file_sha256") != file_hash(bank_path):
            raise AggregationError(f"{validation_path}: B1 validation bank hash mismatch")
        parse_bank(bank, client)
        repositories = bank["active_skillbanks"]
        if set(repositories) != set(EXPECTED_ROLES[client]):
            raise AggregationError(f"{bank_path}: role set mismatch")
        count = 0
        for role in EXPECTED_ROLES[client]:
            repository = repositories[role]
            seen: set[str] = set()
            for bucket, skills in (("general", repository["general"]), *repository["task_specific"].items()):
                for raw in skills:
                    skill_id = raw["skill_id"]
                    if skill_id in seen:
                        raise AggregationError(f"{bank_path}/{role}: duplicate role-local skill ID")
                    seen.add(skill_id)
                    key = f"{client}/{role}/{bucket}/{skill_id}"
                    rows.append({"source_skill_key": key, "source_client": client, "source_role": role, "source_skill_id": skill_id, "bucket": bucket, "skill": _semantic_skill(raw, f"{bank_path}/{role}/{skill_id}"), "upstream_source_skill_keys": [key]})
                    count += 1
        manifest[client] = {"bank_path": str(bank_path), "bank_file_sha256": file_hash(bank_path), "validation_path": str(validation_path), "validation_file_sha256": file_hash(validation_path), "validation_source_lock_sha256": file_hash(lock_path), "origin_kind": origin, "import_manifest_sha256": import_hash, "uploaded_role_skill_instances": count}
    keys = [row["source_skill_key"] for row in rows]
    if len(set(keys)) != len(keys):
        raise AggregationError("duplicate B1 source keys")
    return rows, manifest


def load_role_uploads(bank_paths: dict[str, Path], validation_paths: dict[str, Path], generation: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    manifest: dict[str, Any] = {}
    for client in "ABC":
        bank_path, validation_path = bank_paths[client], validation_paths[client]
        bank = json.loads(bank_path.read_text(encoding="utf-8"))
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
        if bank.get("schema_version") != SCHEMA or bank.get("client") != client or bank.get("generation") != generation:
            raise AggregationError(f"{bank_path}: expected v11 Client {client} B{generation}")
        expected = {"status": "complete", "client": client, "generation": generation, "phase": "validation", "task_count": 134, "api_clean": True}
        if any(validation.get(key) != value for key, value in expected.items()):
            raise AggregationError(f"{validation_path}: complete API-clean local validation required")
        source_lock_path = validation_path.parent / "source_lock.json"
        if not source_lock_path.exists():
            raise AggregationError(f"{validation_path}: validation source lock missing")
        source_lock = json.loads(source_lock_path.read_text(encoding="utf-8"))
        if source_lock.get("bank_file_sha256") != file_hash(bank_path):
            raise AggregationError(f"{validation_path}: validation did not use the uploaded bank bytes")
        parse_bank(bank, client)
        repositories = bank.get("active_skillbanks")
        if not isinstance(repositories, dict) or set(repositories) != set(EXPECTED_ROLES[client]):
            raise AggregationError(f"{bank_path}: missing or extra role repositories")
        policy = bank.get("capacity_policy") or {}
        if policy.get("scope") != "per_role_per_round" or policy.get("quota_passed") is not True or set(policy.get("per_role") or {}) != set(repositories):
            raise AggregationError(f"{bank_path}: per-role capacity audit missing")
        source_count = 0
        for role in EXPECTED_ROLES[client]:
            repository = repositories[role]
            skills = repository_rows(repository)
            count = policy["per_role"][role]
            if count.get("candidate") != len(skills) or count.get("quota_passed") is not True or count.get("add", 0) > count.get("delete", 0) // 3 or count.get("candidate") != count.get("base", -1) - count.get("delete", 0) + count.get("add", 0):
                raise AggregationError(f"{bank_path}/{role}: invalid role-local quota or count")
            seen: set[str] = set()
            for bucket, skill_rows in (("general", repository["general"]), *repository["task_specific"].items()):
                for raw in skill_rows:
                    skill_id = raw.get("skill_id") if isinstance(raw, dict) else None
                    if not isinstance(skill_id, str) or not skill_id or skill_id in seen:
                        raise AggregationError(f"{bank_path}/{role}: invalid or duplicate skill ID")
                    seen.add(skill_id)
                    lineage = raw.get("source_skill_keys")
                    if not isinstance(lineage, list) or not lineage or any(not isinstance(key, str) or not key for key in lineage):
                        raise AggregationError(f"{bank_path}/{role}/{skill_id}: malformed lineage")
                    rows.append({
                        "source_skill_key": f"{client}/{role}/{bucket}/{skill_id}",
                        "source_client": client, "source_role": role,
                        "source_skill_id": skill_id, "bucket": bucket,
                        "skill": _semantic_skill(raw, f"{bank_path}/{role}/{skill_id}"),
                        "upstream_source_skill_keys": sorted(set(lineage)),
                    })
                    source_count += 1
        manifest[client] = {"bank_path": str(bank_path), "bank_file_sha256": file_hash(bank_path), "validation_path": str(validation_path), "validation_file_sha256": file_hash(validation_path), "validation_source_lock_sha256": file_hash(source_lock_path), "role_skill_count": {role: policy["per_role"][role]["candidate"] for role in EXPECTED_ROLES[client]}, "uploaded_role_skill_instances": source_count}
    keys = [row["source_skill_key"] for row in rows]
    if len(set(keys)) != len(keys):
        raise AggregationError("duplicate role-qualified source keys")
    return rows, manifest


def run(args: argparse.Namespace) -> dict[str, Any]:
    bank_paths = {client: Path(getattr(args, f"bank_{client.lower()}")) for client in "ABC"}
    validation_paths = {client: Path(getattr(args, f"validation_{client.lower()}")) for client in "ABC"}
    rows, inputs = load_initial_uploads(bank_paths, validation_paths) if args.round_index == 1 else load_role_uploads(bank_paths, validation_paths, args.round_index)
    input_mode = "three_open_b1_role_banks" if args.round_index == 1 else "complete_client_banks_with_role_provenance"
    identity = {"schema_version": "stage2_local_v11.server_input.v1", "experiment_id": args.experiment_id, "round_index": args.round_index, "input_mode": input_mode, "inputs": inputs, "input_skill_count": len(rows), "input_rows_hash": object_hash(rows), "buckets": {bucket: len(bucket_inputs(rows, bucket)) for bucket in BUCKETS}, "model": "deepseek-flash", "endpoint_origin": "https://api.deepseek.com", "seed": args.seed, "max_tokens": args.max_tokens, "server_evaluation": None}
    args.output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_root / "input_manifest.json"
    upload_path = args.output_root / f"uploaded_local_b{args.round_index}.json"
    if manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding="utf-8")) != identity:
            raise AggregationError("refusing resume: server input identity changed")
    else:
        write_json(manifest_path, identity)
    upload = {"skills": rows}
    if upload_path.exists():
        if json.loads(upload_path.read_text(encoding="utf-8")) != upload:
            raise AggregationError("refusing resume: complete role uploads changed")
    else:
        write_json(upload_path, upload)
    if args.prepare_only:
        return {"status": "prepared", **identity}
    existing_summary = args.output_root / "summary.json"
    if existing_summary.exists():
        frozen = json.loads(existing_summary.read_text(encoding="utf-8"))
        if frozen.get("status") != "complete" or frozen.get("round_index") != args.round_index:
            raise AggregationError("existing server summary has incompatible identity")
        frozen_global = Path(frozen["global_skillbank"]["path"])
        if not frozen_global.exists() or file_hash(frozen_global) != frozen["global_skillbank"]["file_sha256"]:
            raise AggregationError("completed Global output is missing or changed")
        return frozen

    from stage3_federation.aggregation_api import AggregationAPIConfig
    config = AggregationAPIConfig.from_env()
    descriptor = config.descriptor()
    if config.model != "deepseek-flash" or descriptor.get("provider") != "deepseek_official" or descriptor.get("endpoint_origin") != "https://api.deepseek.com":
        raise AggregationError("DeepSeek official deepseek-flash required")
    buckets: dict[str, list[dict[str, Any]]] = {}
    records: list[dict[str, Any]] = []
    for bucket in BUCKETS:
        inputs_for_bucket = bucket_inputs(rows, bucket)
        source_rows = [row for row in rows if row["bucket"] == bucket]
        slug = bucket_slug(bucket)
        if not inputs_for_bucket:
            buckets[bucket] = []
            records.append({"bucket": bucket, "input_skill_count": 0, "output_skill_count": 0, "model_calls": 0})
            continue
        accepted_path = args.output_root / "buckets" / f"{slug}.accepted.json"
        record_path = args.output_root / "buckets" / f"{slug}.record.json"
        if accepted_path.exists() and record_path.exists():
            accepted = json.loads(accepted_path.read_text(encoding="utf-8"))
            cleaned, errors = validate_model_output(accepted, inputs_for_bucket)
            if errors:
                raise AggregationError(f"invalid frozen {bucket} bucket: {errors}")
            buckets[bucket] = add_upstream_lineage(cleaned, source_rows)
            records.append(json.loads(record_path.read_text(encoding="utf-8")))
            continue
        prior_errors = None
        for attempt in range(1, args.schema_attempts + 1):
            raw, reasoning, usage = call_model(config, [{"role": "system", "content": system_prompt()}, {"role": "user", "content": user_prompt(bucket, inputs_for_bucket, prior_errors)}], args)
            attempt_path = args.output_root / "buckets" / f"{slug}.attempt_{attempt:02d}.json"
            if attempt_path.exists():
                raise AggregationError(f"refusing to overwrite aggregation attempt {attempt_path}")
            write_json(attempt_path, {"bucket": bucket, "attempt": attempt, "raw_model_output": raw, "model_reasoning": reasoning, "usage": usage, "completed_at": utc_now()})
            try:
                cleaned, errors = validate_model_output(parse_json_object(raw), inputs_for_bucket)
            except (json.JSONDecodeError, AggregationError) as exc:
                cleaned, errors = [], [f"JSON/schema error: {exc}"]
            if not errors:
                accepted = {"skills": cleaned}
                write_json(accepted_path, accepted)
                record = {"bucket": bucket, "input_skill_count": len(inputs_for_bucket), "output_skill_count": len(cleaned), "accepted_attempt_file": str(attempt_path), "usage": usage}
                write_json(record_path, record)
                buckets[bucket] = add_upstream_lineage(cleaned, source_rows)
                records.append(record)
                break
            prior_errors = errors
        else:
            raise AggregationError(f"{bucket}: schema attempt limit reached")
    general: list[dict[str, Any]] = []
    specific: dict[str, list[dict[str, Any]]] = {label: [] for label in TASK_LABELS}
    for bucket in BUCKETS:
        target = general if bucket == "general" else specific[bucket]
        prefix = "G" if bucket == "general" else f"T{TASK_LABELS.index(bucket) + 1}"
        for index, skill in enumerate(buckets[bucket], 1):
            target.append({"global_skill_id": f"{prefix}_{index:03d}", **skill})
    count = len(general) + sum(len(group) for group in specific.values())
    if count > len(rows):
        raise AggregationError("Global output exceeds uploaded role instances")
    global_bank = {"schema_version": GLOBAL_SCHEMA, "v11_protocol": "role_partitioned_local_to_role_agnostic_global.v1", "experiment_id": args.experiment_id, "round_index": args.round_index, "aggregation_mode": "complete_role_banks_seven_bucket_semantic_merge", "general": general, "task_specific": specific, "capacity": {"server_maximum_total_skills": None, "current_total_skills": count, "future_client_local_policy": "per_role_add_lte_floor_distinct_delete_div_3"}, "source_input": {"uploaded_role_skill_instance_count": len(rows), "uploaded_banks_sha256": file_hash(upload_path), "input_manifest_sha256": file_hash(manifest_path)}, "aggregation_model": descriptor, "server_evaluation": None}
    global_bank["live_global_hash"] = object_hash({"general": general, "task_specific": specific})
    output_path = args.output_root / f"global_skillbank{args.round_index}.json"
    if output_path.exists():
        raise AggregationError(f"refusing to overwrite Global output {output_path}")
    write_json(output_path, global_bank)
    summary = {"status": "complete", "round_index": args.round_index, "input_skill_count": len(rows), "output_skill_count": count, "global_skillbank": {"path": str(output_path), "file_sha256": file_hash(output_path), "live_global_hash": global_bank["live_global_hash"]}, "server_evaluation_performed": False, "records": records}
    write_json(args.output_root / "summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round-index", type=int, required=True)
    parser.add_argument("--experiment-id", required=True)
    for client in "abc":
        parser.add_argument(f"--bank-{client}", type=Path, required=True)
        parser.add_argument(f"--validation-{client}", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--max-tokens", type=int, default=16000)
    parser.add_argument("--timeout", type=float, default=240)
    parser.add_argument("--transport-retries", type=int, default=3)
    parser.add_argument("--schema-attempts", type=int, default=3)
    args = parser.parse_args()
    if args.round_index < 1:
        parser.error("round-index must be at least 1")
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
