"""D-101 semantic aggregation of three complete local B2 SkillBanks.

The server consumes the complete post-patch banks, groups their skills into the
same seven role-agnostic buckets as Round 1, and produces Global SkillBank2.
The run is fail-closed and resumable at bucket boundaries.  It never evaluates
or distributes the resulting bank.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from stage2_local_v12.federation.round1_aggregate import (
    BUCKETS,
    TASK_LABELS,
    AggregationError,
    _manifest_identity_without_display_paths,
    _semantic_skill,
    bucket_slug,
    call_model,
    file_hash,
    object_hash,
    parse_json_object,
    system_prompt,
    user_prompt,
    utc_now,
    validate_model_output,
    write_json,
)


ROOT = Path(__file__).resolve().parents[2]
LOCAL_RUN_ROOT = ROOT / "stage2_local_v12/runs/round2_inputs"
DEFAULT_BANKS = {
    client: LOCAL_RUN_ROOT / f"client_{client}/B2_skillbank.json"
    for client in ("A", "B", "C")
}
DEFAULT_PATCHES = {
    client: LOCAL_RUN_ROOT / f"client_{client}/B2_patch.json"
    for client in ("A", "B", "C")
}
EXPERIMENT_ID = "v9-local-b2-role-agnostic-semantic-global-round2"
SCHEMA_VERSION = "stage3_2.role_agnostic_semantic_global.v1"
EXPECTED_CLIENT_SKILLS = 41
EXPECTED_TOTAL_SKILLS = 123
EXPECTED_PARENT_LIVE_HASH = (
    "sha256:cb673281b217312fcd7c2a6d453295c46970e028fa7012a1c2cf3c29db6b3253"
)


def _repository_live_hash(payload: dict[str, Any]) -> str:
    return object_hash({
        "general": payload["general"],
        "task_specific": payload["task_specific"],
    })


def load_local_b2(
    bank_paths: dict[str, Path], patch_paths: dict[str, Path]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    manifest_inputs: dict[str, Any] = {}
    parent_live_hashes: set[str] = set()

    for client in ("A", "B", "C"):
        bank_path = bank_paths[client]
        patch_path = patch_paths[client]
        bank = json.loads(bank_path.read_text(encoding="utf-8"))
        patch = json.loads(patch_path.read_text(encoding="utf-8"))
        if bank.get("schema_version") != "stage3_2.local_role_agnostic_bank.v1":
            raise AggregationError(f"{bank_path}: unexpected schema")
        if bank.get("client") != client or bank.get("generation") != 2:
            raise AggregationError(f"{bank_path}: expected Client {client} B2")
        if patch.get("schema_version") != "stage3_2.local_net_patch.v1":
            raise AggregationError(f"{patch_path}: unexpected patch schema")
        if patch.get("client") != client or patch.get("round_index") != 2:
            raise AggregationError(f"{patch_path}: expected Client {client} Round 2 patch")

        capacity = bank.get("capacity_policy")
        counts = patch.get("counts")
        if not isinstance(capacity, dict) or not isinstance(counts, dict):
            raise AggregationError(f"Client {client}: missing capacity audit")
        expected_counts = {"base": 43, "delete": 3, "add": 1, "candidate": 41}
        for key, expected in expected_counts.items():
            if capacity.get(f"{key}_count") != expected and key != "base":
                raise AggregationError(f"Client {client}: invalid bank {key} count")
            if capacity.get("base_count") != expected and key == "base":
                raise AggregationError(f"Client {client}: invalid bank base count")
            if counts.get(key) != expected:
                raise AggregationError(f"Client {client}: invalid patch {key} count")
        if capacity.get("update_count") != counts.get("update"):
            raise AggregationError(f"Client {client}: update count mismatch")
        if capacity.get("quota_passed") is not True:
            raise AggregationError(f"Client {client}: local quota did not pass")

        general = bank.get("general")
        task_specific = bank.get("task_specific")
        if not isinstance(general, list) or not isinstance(task_specific, dict):
            raise AggregationError(f"{bank_path}: malformed repository")
        if set(task_specific) != set(TASK_LABELS):
            raise AggregationError(f"{bank_path}: task labels do not match")

        seen_ids: set[str] = set()
        client_count = 0
        for bucket, skills in (("general", general), *task_specific.items()):
            if not isinstance(skills, list):
                raise AggregationError(f"{bank_path}/{bucket}: expected list")
            for index, raw in enumerate(skills, 1):
                if not isinstance(raw, dict):
                    raise AggregationError(f"{bank_path}/{bucket}/{index}: expected object")
                skill_id = raw.get("skill_id")
                if not isinstance(skill_id, str) or not skill_id:
                    raise AggregationError(f"{bank_path}/{bucket}/{index}: missing skill_id")
                if skill_id in seen_ids:
                    raise AggregationError(f"{bank_path}: duplicate skill_id {skill_id}")
                seen_ids.add(skill_id)
                upstream = raw.get("source_skill_keys")
                if not isinstance(upstream, list) or not upstream or not all(
                    isinstance(key, str) and key for key in upstream
                ):
                    raise AggregationError(f"{bank_path}/{bucket}/{skill_id}: bad lineage")
                semantic = _semantic_skill(raw, f"{bank_path}/{bucket}/{skill_id}")
                rows.append({
                    "source_skill_key": f"{client}/{bucket}/{skill_id}",
                    "source_client": client,
                    "source_skill_id": skill_id,
                    "bucket": bucket,
                    "skill": semantic,
                    "upstream_source_skill_keys": sorted(set(upstream)),
                })
                client_count += 1
        if client_count != EXPECTED_CLIENT_SKILLS:
            raise AggregationError(
                f"Client {client} expected {EXPECTED_CLIENT_SKILLS} skills, got {client_count}"
            )

        parent_live_hash = patch.get("base_live_repository_sha256")
        if parent_live_hash is not None:
            parent_live_hashes.add(parent_live_hash)
        manifest_inputs[client] = {
            "bank_path": str(bank_path),
            "bank_file_sha256": file_hash(bank_path),
            "bank_live_hash": _repository_live_hash(bank),
            "patch_path": str(patch_path),
            "patch_file_sha256": file_hash(patch_path),
            "patch_base_bank_file_sha256": patch.get("base_bank_file_sha256"),
            "patch_candidate_live_repository_sha256": patch.get(
                "candidate_live_repository_sha256"
            ),
            "skill_count": client_count,
            "patch_counts": counts,
            "quota_passed": True,
        }
        if manifest_inputs[client]["bank_live_hash"] != patch.get(
            "candidate_live_repository_sha256"
        ):
            raise AggregationError(f"Client {client}: B2 bank and patch candidate hash differ")

    keys = [row["source_skill_key"] for row in rows]
    if len(rows) != EXPECTED_TOTAL_SKILLS or len(set(keys)) != EXPECTED_TOTAL_SKILLS:
        raise AggregationError(
            f"expected {EXPECTED_TOTAL_SKILLS} unique B2 instances, "
            f"got {len(rows)} rows/{len(set(keys))} keys"
        )
    return rows, manifest_inputs


def bucket_inputs(rows: list[dict[str, Any]], bucket: str) -> list[dict[str, Any]]:
    return [
        {
            "source_skill_key": row["source_skill_key"],
            "source_client": row["source_client"],
            "source_skill_id": row["source_skill_id"],
            "skill": row["skill"],
        }
        for row in rows
        if row["bucket"] == bucket
    ]


def add_upstream_lineage(
    outputs: list[dict[str, Any]], rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    lineage = {row["source_skill_key"]: row["upstream_source_skill_keys"] for row in rows}
    enriched = []
    for output in outputs:
        upstream = sorted({
            key
            for source in output["source_skill_keys"]
            for key in lineage[source]
        })
        enriched.append({**output, "upstream_source_skill_keys": upstream})
    return enriched


def run(args: argparse.Namespace) -> dict[str, Any]:
    args.output_root.mkdir(parents=True, exist_ok=True)
    bank_paths = {c: Path(getattr(args, f"bank_{c.lower()}")) for c in ("A", "B", "C")}
    patch_paths = {c: Path(getattr(args, f"patch_{c.lower()}")) for c in ("A", "B", "C")}
    rows, inputs = load_local_b2(bank_paths, patch_paths)
    identity = {
        "experiment_id": EXPERIMENT_ID,
        "round_index": 2,
        "input_mode": "three_complete_post_patch_local_b2_banks",
        "inputs": inputs,
        "input_skill_count": len(rows),
        "input_rows_hash": object_hash(rows),
        "buckets": {bucket: len(bucket_inputs(rows, bucket)) for bucket in BUCKETS},
        "model": "deepseek-flash",
        "endpoint_origin": "https://api.deepseek.com",
        "temperature": 0,
        "seed": args.seed,
        "max_tokens": args.max_tokens,
        "server_evaluation": None,
        "automatic_downlink": False,
    }
    manifest_path = args.output_root / "input_manifest.json"
    uploads_path = args.output_root / "uploaded_local_b2.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if _manifest_identity_without_display_paths(existing) != _manifest_identity_without_display_paths(identity):
            raise AggregationError("refusing resume: input manifest identity changed")
    else:
        write_json(manifest_path, identity)
    upload_payload = {"skills": rows}
    if uploads_path.exists():
        if json.loads(uploads_path.read_text(encoding="utf-8")) != upload_payload:
            raise AggregationError("refusing resume: uploaded B2 inputs changed")
    else:
        write_json(uploads_path, upload_payload)
    if args.prepare_only:
        return {"status": "prepared", **identity}

    from stage2_local_v12.federation.aggregation_api import AggregationAPIConfig

    config = AggregationAPIConfig.from_env()
    descriptor = config.descriptor()
    if descriptor["provider"] != "deepseek_official" or descriptor["endpoint_origin"] != "https://api.deepseek.com":
        raise AggregationError(f"DeepSeek official endpoint required, got {descriptor}")
    if config.model != "deepseek-flash":
        raise AggregationError(f"deepseek-flash required, got {config.model}")

    bucket_results: dict[str, list[dict[str, Any]]] = {}
    records: list[dict[str, Any]] = []
    for bucket in BUCKETS:
        model_rows = bucket_inputs(rows, bucket)
        source_rows = [row for row in rows if row["bucket"] == bucket]
        slug = bucket_slug(bucket)
        accepted_path = args.output_root / "buckets" / f"{slug}.accepted.json"
        record_path = args.output_root / "buckets" / f"{slug}.record.json"
        if accepted_path.exists() and record_path.exists():
            accepted = json.loads(accepted_path.read_text(encoding="utf-8"))
            cleaned, errors = validate_model_output(accepted, model_rows)
            if errors:
                raise AggregationError(f"resume bucket {bucket} is invalid: {errors}")
            bucket_results[bucket] = add_upstream_lineage(cleaned, source_rows)
            records.append(json.loads(record_path.read_text(encoding="utf-8")))
            print(f"RESUME {bucket}: {len(model_rows)} -> {len(cleaned)}", flush=True)
            continue

        prior_errors: list[str] | None = None
        prior_attempts = sorted((args.output_root / "buckets").glob(f"{slug}.attempt_*.json"))
        attempt_offset = len(prior_attempts)
        for retry_index in range(1, args.schema_attempts + 1):
            model_attempt = attempt_offset + retry_index
            print(
                f"CALL {bucket}: input={len(model_rows)} "
                f"schema_attempt={retry_index}/{args.schema_attempts} "
                f"artifact_attempt={model_attempt}",
                flush=True,
            )
            raw, reasoning, usage = call_model(
                config,
                [
                    {"role": "system", "content": system_prompt()},
                    {"role": "user", "content": user_prompt(bucket, model_rows, prior_errors)},
                ],
                args,
            )
            attempt_path = args.output_root / "buckets" / f"{slug}.attempt_{model_attempt:02d}.json"
            write_json(attempt_path, {
                "bucket": bucket,
                "attempt": model_attempt,
                "raw_model_output": raw,
                "model_reasoning": reasoning,
                "usage": usage,
                "completed_at": utc_now(),
            })
            try:
                parsed = parse_json_object(raw)
                cleaned, errors = validate_model_output(parsed, model_rows)
            except (json.JSONDecodeError, AggregationError) as exc:
                cleaned, errors = [], [f"JSON/schema parse error: {exc}"]
            if not errors:
                accepted = {"skills": cleaned}
                write_json(accepted_path, accepted)
                record = {
                    "bucket": bucket,
                    "input_skill_count": len(model_rows),
                    "output_skill_count": len(cleaned),
                    "input_source_count": len(model_rows),
                    "accounted_source_count": sum(
                        len(skill["source_skill_keys"]) for skill in cleaned
                    ),
                    "model_attempts": model_attempt,
                    "accepted_attempt_file": str(attempt_path),
                    "accepted_output_hash": object_hash(accepted),
                    "usage": usage,
                }
                write_json(record_path, record)
                bucket_results[bucket] = add_upstream_lineage(cleaned, source_rows)
                records.append(record)
                print(f"ACCEPT {bucket}: {len(model_rows)} -> {len(cleaned)}", flush=True)
                break
            prior_errors = errors
            print(f"REJECT {bucket}: {errors}", flush=True)
        else:
            raise AggregationError(
                f"bucket {bucket} exhausted {args.schema_attempts} schema attempts"
            )

    general: list[dict[str, Any]] = []
    task_specific: dict[str, list[dict[str, Any]]] = {label: [] for label in TASK_LABELS}
    for bucket in BUCKETS:
        target = general if bucket == "general" else task_specific[bucket]
        prefix = "G" if bucket == "general" else f"T{TASK_LABELS.index(bucket) + 1}"
        for index, skill in enumerate(bucket_results[bucket], 1):
            target.append({"global_skill_id": f"{prefix}_{index:03d}", **skill})
    output_count = len(general) + sum(len(items) for items in task_specific.values())
    if output_count > len(rows):
        raise AggregationError("global output exceeds uploaded B2 input count")

    global_bank = {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "round_index": 2,
        "parent": "Global SkillBank1",
        "aggregation_mode": "complete_local_b2_role_agnostic_seven_bucket_semantic_merge",
        "capacity": {
            "server_maximum_total_skills": None,
            "current_total_skills": output_count,
            "future_client_local_policy": "per_client_per_round_add_lte_floor_distinct_delete_div_3",
            "server_merge_creates_delete_credit": False,
        },
        "general": general,
        "task_specific": task_specific,
        "source_input": {
            "uploaded_skill_instance_count": len(rows),
            "uploaded_local_b2_sha256": file_hash(uploads_path),
            "input_manifest_sha256": file_hash(manifest_path),
        },
        "aggregation_model": descriptor,
        "server_evaluation": None,
        "downlink_materialized": False,
    }
    global_bank["live_global_hash"] = object_hash({
        "general": general,
        "task_specific": task_specific,
    })
    global_path = args.output_root / "global_skillbank2.json"
    write_json(global_path, global_bank)
    summary = {
        "status": "complete",
        "completed_at": utc_now(),
        "experiment_id": EXPERIMENT_ID,
        "input_skill_count": len(rows),
        "output_skill_count": output_count,
        "bucket_counts": {
            bucket: {
                "input": len(bucket_inputs(rows, bucket)),
                "output": len(bucket_results[bucket]),
            }
            for bucket in BUCKETS
        },
        "global_skillbank2": {
            "path": str(global_path),
            "file_sha256": file_hash(global_path),
            "live_global_hash": global_bank["live_global_hash"],
        },
        "server_evaluation_performed": False,
        "downlink_materialized": False,
        "client_evaluation_started": False,
        "records": records,
    }
    write_json(args.output_root / "summary.json", summary)
    return summary


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    for client in ("A", "B", "C"):
        value.add_argument(f"--bank-{client.lower()}", type=Path, default=DEFAULT_BANKS[client])
        value.add_argument(f"--patch-{client.lower()}", type=Path, default=DEFAULT_PATCHES[client])
    value.add_argument("--output-root", type=Path, required=True)
    value.add_argument("--prepare-only", action="store_true")
    value.add_argument("--timeout", type=float, default=240.0)
    value.add_argument("--max-tokens", type=int, default=16000)
    value.add_argument("--seed", type=int, default=1234)
    value.add_argument("--transport-retries", type=int, default=3)
    value.add_argument("--schema-attempts", type=int, default=3)
    return value


def main() -> int:
    args = parser().parse_args()
    result = run(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
