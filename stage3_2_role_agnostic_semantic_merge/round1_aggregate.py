"""D-094 first role-agnostic seven-bucket semantic aggregation.

The script is fail-closed and resumable. It never runs ALFWorld evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from stage3_federation.aggregation_api import AggregationAPIConfig


ROOT = Path(__file__).resolve().parents[1]
TASK_LABELS = (
    "简单取放", "台灯观察", "清洗后放置", "加热后放置", "冷却后放置", "双物品放置",
)
BUCKETS = ("general", *TASK_LABELS)
SKILL_FIELDS = {
    "Procedure or Local Strategy": ("title", "principle", "when_to_apply"),
    "Failure Lesson": ("title", "description", "why_it_happens", "how_to_avoid"),
}
INPUT_SKILL_FIELDS = {
    "Procedure or Local Strategy": ("title", "principle", "when_to_apply"),
    # The frozen v9 banks intentionally have no title on Failure Lesson records.
    # The aggregation model creates a role-neutral title in the normalized output.
    "Failure Lesson": ("description", "why_it_happens", "how_to_avoid"),
}
ROLE_TOKENS = (
    "planner", "executor", "critic", "supervisor", "search worker", "operation worker",
)
EXPECTED_COUNTS = {"A": 46, "B": 42, "C": 63}
DEFAULT_BANKS = {
    "A": ROOT / "stage2_local_v9/runs/client_a_generation_01_20261013_r1/B1_skillbank.json",
    "B": ROOT / "stage2_local_v9/runs/client_b_generation_01_20261013_r3/B1_skillbank.json",
    "C": ROOT / "stage2_local_v9/runs/client_c_generation_01_20261013_r3/B1_skillbank.json",
}
EXPERIMENT_ID = "v9-b1-role-agnostic-semantic-global-round1"
SCHEMA_VERSION = "stage3_2.role_agnostic_semantic_global.v1"


class AggregationError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def object_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _manifest_identity_without_display_paths(value: dict[str, Any]) -> dict[str, Any]:
    """Compare run identity across Windows and WSL without trusting path spelling."""
    cleaned = json.loads(json.dumps(value))
    for item in cleaned.get("inputs", {}).values():
        if isinstance(item, dict):
            item.pop("path", None)
    return cleaned


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _semantic_skill(raw: dict[str, Any], context: str) -> dict[str, Any]:
    skill_type = raw.get("type")
    fields = INPUT_SKILL_FIELDS.get(skill_type)
    if fields is None:
        raise AggregationError(f"{context}: unsupported type {skill_type!r}")
    result = {"type": skill_type}
    for field in fields:
        value = raw.get(field)
        if not isinstance(value, str) or not value.strip():
            raise AggregationError(f"{context}: missing {field}")
        if len(value) > 900:
            raise AggregationError(f"{context}: {field} exceeds 900 characters")
        result[field] = value.strip()
    return result


def load_initial_adds(bank_paths: dict[str, Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    adds: list[dict[str, Any]] = []
    manifest_inputs: dict[str, Any] = {}
    for client in ("A", "B", "C"):
        path = bank_paths[client]
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("generation") != 1 or payload.get("target_client") != client:
            raise AggregationError(f"{path}: expected frozen Client {client} B1")
        active = payload.get("active_skillbanks")
        if not isinstance(active, dict) or not active:
            raise AggregationError(f"{path}: missing active_skillbanks")
        client_count = 0
        for role, repository in active.items():
            general = repository.get("general")
            task_specific = repository.get("task_specific")
            if not isinstance(general, list) or not isinstance(task_specific, dict):
                raise AggregationError(f"{path}/{role}: malformed repository")
            if set(task_specific) != set(TASK_LABELS):
                raise AggregationError(f"{path}/{role}: task labels do not match the six frozen labels")
            for bucket, rows in (("general", general), *task_specific.items()):
                if not isinstance(rows, list):
                    raise AggregationError(f"{path}/{role}/{bucket}: expected list")
                for index, raw in enumerate(rows, 1):
                    if not isinstance(raw, dict):
                        raise AggregationError(f"{path}/{role}/{bucket}/{index}: expected object")
                    skill_id = raw.get("skill_id")
                    if not isinstance(skill_id, str) or not skill_id:
                        raise AggregationError(f"{path}/{role}/{bucket}/{index}: missing skill_id")
                    semantic = _semantic_skill(raw, f"{path}/{role}/{bucket}/{skill_id}")
                    source_key = f"{client}/{role}/{bucket}/{skill_id}"
                    adds.append({
                        "operation": "ADD",
                        "base_global_hash": object_hash({"general": [], "task_specific": {label: [] for label in TASK_LABELS}}),
                        "source_client": client,
                        "source_role": role,
                        "source_skill_id": skill_id,
                        "source_skill_key": source_key,
                        "bucket": bucket,
                        "skill": semantic,
                    })
                    client_count += 1
        if client_count != EXPECTED_COUNTS[client]:
            raise AggregationError(f"Client {client} expected {EXPECTED_COUNTS[client]} skills, got {client_count}")
        manifest_inputs[client] = {
            "path": str(path), "file_sha256": file_hash(path), "skill_count": client_count,
        }
    keys = [row["source_skill_key"] for row in adds]
    if len(adds) != 151 or len(set(keys)) != 151:
        raise AggregationError(f"expected 151 unique initial ADDs, got {len(adds)} rows/{len(set(keys))} keys")
    return adds, manifest_inputs


def bucket_inputs(adds: list[dict[str, Any]], bucket: str) -> list[dict[str, Any]]:
    return [
        {
            "source_skill_key": row["source_skill_key"],
            "source_client": row["source_client"],
            "source_role": row["source_role"],
            "skill": row["skill"],
        }
        for row in adds if row["bucket"] == bucket
    ]


def system_prompt() -> str:
    return """You are the server aggregation model for a controlled federated-skill baseline.
You receive exactly one bucket of skills gathered from multiple clients and agent roles.
Create a role-agnostic consolidated bucket by merging semantic duplicates, combining complementary evidence, and resolving wording conflicts conservatively.

Hard rules:
1. Return one JSON object only: {\"skills\": [...]}.
2. Every output skill must be either:
   {\"type\":\"Procedure or Local Strategy\",\"title\":str,\"principle\":str,\"when_to_apply\":str,\"source_skill_keys\":[str,...]}
   or {\"type\":\"Failure Lesson\",\"title\":str,\"description\":str,\"why_it_happens\":str,\"how_to_avoid\":str,\"source_skill_keys\":[str,...]}.
3. Account for every input source_skill_key exactly once across all output source_skill_keys. Do not invent a key and do not omit one.
4. Output no more skills than the input count. Prefer consolidation, but retain separate skills when their semantics are materially different.
5. Write role-neutral reusable knowledge. Do not name or instruct Planner, Executor, Critic, Supervisor, Search Worker, or Operation Worker. Agent permissions and output formats are controlled elsewhere.
6. Keep each string field at most 900 characters. Do not include evidence IDs in prose.
7. Do not create unsupported environment facts. When inputs conflict, state a conservative conditional rule grounded in observations.
8. Do not emit markdown fences, commentary, IDs, scores, or fields outside the declared schema."""


def user_prompt(bucket: str, rows: list[dict[str, Any]], prior_errors: list[str] | None = None) -> str:
    label = "General (must transfer across all six task families)" if bucket == "general" else f"Task-specific: {bucket}"
    payload = {
        "bucket": label,
        "input_skill_count": len(rows),
        "input_source_skill_keys": [row["source_skill_key"] for row in rows],
        "input_skills": rows,
        "instruction": "Return the complete consolidated bucket as JSON. All source keys must be assigned exactly once.",
    }
    if prior_errors:
        payload["previous_attempt_validation_errors"] = prior_errors
        payload["repair_instruction"] = "Regenerate the complete bucket from the original inputs and correct every listed error."
    return json.dumps(payload, ensure_ascii=False)


def parse_json_object(text: str) -> dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        value = "\n".join(lines).strip()
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise AggregationError("model output must be one JSON object")
    return parsed


def validate_model_output(value: dict[str, Any], inputs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    errors: list[str] = []
    if set(value) != {"skills"}:
        errors.append("top-level keys must be exactly ['skills']")
    raw_skills = value.get("skills")
    if not isinstance(raw_skills, list):
        return [], errors + ["skills must be a list"]
    if not raw_skills:
        errors.append("skills must not be empty")
    if len(raw_skills) > len(inputs):
        errors.append(f"output count {len(raw_skills)} exceeds input count {len(inputs)}")
    allowed_sources = {row["source_skill_key"] for row in inputs}
    seen_sources: list[str] = []
    semantic_hashes: set[str] = set()
    cleaned: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_skills, 1):
        context = f"skills[{index}]"
        if not isinstance(raw, dict):
            errors.append(f"{context} must be an object")
            continue
        skill_type = raw.get("type")
        fields = SKILL_FIELDS.get(skill_type)
        if fields is None:
            errors.append(f"{context} has unsupported type {skill_type!r}")
            continue
        expected_keys = {"type", "source_skill_keys", *fields}
        if set(raw) != expected_keys:
            errors.append(f"{context} keys must be exactly {sorted(expected_keys)}")
        item: dict[str, Any] = {"type": skill_type}
        for field in fields:
            field_value = raw.get(field)
            if not isinstance(field_value, str) or not field_value.strip():
                errors.append(f"{context}.{field} must be non-empty text")
                continue
            if len(field_value) > 900:
                errors.append(f"{context}.{field} exceeds 900 characters")
            lowered = field_value.casefold()
            matched = [
                token for token in ROLE_TOKENS
                if re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", lowered)
            ]
            if matched:
                errors.append(f"{context}.{field} names forbidden role(s): {matched}")
            item[field] = field_value.strip()
        sources = raw.get("source_skill_keys")
        if not isinstance(sources, list) or not sources or not all(isinstance(key, str) for key in sources):
            errors.append(f"{context}.source_skill_keys must be a non-empty string list")
            sources = []
        item["source_skill_keys"] = sources
        seen_sources.extend(sources)
        semantic = {key: item.get(key) for key in ("type", *fields)}
        semantic_hash = object_hash(semantic)
        if semantic_hash in semantic_hashes:
            errors.append(f"{context} exactly duplicates another output skill")
        semantic_hashes.add(semantic_hash)
        cleaned.append(item)
    seen_set = set(seen_sources)
    missing = sorted(allowed_sources - seen_set)
    unknown = sorted(seen_set - allowed_sources)
    duplicates = sorted({key for key in seen_sources if seen_sources.count(key) > 1})
    if missing:
        errors.append(f"missing source_skill_keys: {missing}")
    if unknown:
        errors.append(f"unknown source_skill_keys: {unknown}")
    if duplicates:
        errors.append(f"source_skill_keys assigned more than once: {duplicates}")
    return cleaned, errors


def call_model(config: "AggregationAPIConfig", messages: list[dict[str, str]], args: argparse.Namespace) -> tuple[str, str, dict[str, Any]]:
    from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

    recoverable = (APITimeoutError, APIConnectionError, InternalServerError, RateLimitError)
    for attempt in range(args.transport_retries + 1):
        try:
            response = config.client(timeout=args.timeout).chat.completions.create(
                model=config.model, messages=messages, temperature=0, seed=args.seed,
                max_tokens=args.max_tokens, stream=False,
            )
            if not response.choices:
                raise AggregationError("DeepSeek returned no choices")
            choice = response.choices[0]
            if getattr(choice, "finish_reason", None) == "length":
                raise AggregationError("DeepSeek response was truncated at max_tokens")
            message = choice.message
            reasoning = getattr(message, "reasoning_content", None)
            if reasoning is None:
                reasoning = (getattr(message, "model_extra", None) or {}).get("reasoning_content", "")
            usage = getattr(response, "usage", None)
            return message.content or "", reasoning or "", {
                "requested_model": config.model,
                "response_model": getattr(response, "model", None),
                "finish_reason": getattr(choice, "finish_reason", None),
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
                "transport_attempts": attempt + 1,
            }
        except recoverable:
            if attempt == args.transport_retries:
                raise
            time.sleep(min(2 ** (attempt + 1), 15))
    raise AssertionError("unreachable")


def bucket_slug(bucket: str) -> str:
    return "general" if bucket == "general" else f"task_{TASK_LABELS.index(bucket) + 1:02d}"


def run(args: argparse.Namespace) -> dict[str, Any]:
    args.output_root.mkdir(parents=True, exist_ok=True)
    bank_paths = {client: Path(getattr(args, f"bank_{client.lower()}")) for client in ("A", "B", "C")}
    adds, inputs = load_initial_adds(bank_paths)
    identity = {
        "experiment_id": EXPERIMENT_ID,
        "round_index": 1,
        "inputs": inputs,
        "input_add_count": len(adds),
        "input_adds_hash": object_hash(adds),
        "buckets": {bucket: len(bucket_inputs(adds, bucket)) for bucket in BUCKETS},
        "model": "deepseek-flash",
        "endpoint_origin": "https://api.deepseek.com",
        "temperature": 0,
        "seed": args.seed,
        "max_tokens": args.max_tokens,
    }
    manifest_path = args.output_root / "input_manifest.json"
    adds_path = args.output_root / "initial_add_patch.json"
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if _manifest_identity_without_display_paths(existing) != _manifest_identity_without_display_paths(identity):
            raise AggregationError("refusing resume: input manifest identity changed")
    else:
        write_json(manifest_path, identity)
    if adds_path.exists():
        if json.loads(adds_path.read_text(encoding="utf-8")) != {"operations": adds}:
            raise AggregationError("refusing resume: initial ADD patch changed")
    else:
        write_json(adds_path, {"operations": adds})
    if args.prepare_only:
        return {"status": "prepared", **identity}

    from stage3_federation.aggregation_api import AggregationAPIConfig

    config = AggregationAPIConfig.from_env()
    descriptor = config.descriptor()
    if descriptor["provider"] != "deepseek_official" or descriptor["endpoint_origin"] != "https://api.deepseek.com":
        raise AggregationError(f"DeepSeek official endpoint required, got {descriptor}")
    if config.model != "deepseek-flash":
        raise AggregationError(f"deepseek-flash required, got {config.model}")

    bucket_results: dict[str, list[dict[str, Any]]] = {}
    records: list[dict[str, Any]] = []
    for bucket in BUCKETS:
        rows = bucket_inputs(adds, bucket)
        slug = bucket_slug(bucket)
        accepted_path = args.output_root / "buckets" / f"{slug}.accepted.json"
        record_path = args.output_root / "buckets" / f"{slug}.record.json"
        if accepted_path.exists() and record_path.exists():
            accepted = json.loads(accepted_path.read_text(encoding="utf-8"))
            cleaned, errors = validate_model_output(accepted, rows)
            if errors:
                raise AggregationError(f"resume bucket {bucket} is invalid: {errors}")
            bucket_results[bucket] = cleaned
            records.append(json.loads(record_path.read_text(encoding="utf-8")))
            print(f"RESUME {bucket}: {len(rows)} -> {len(cleaned)}", flush=True)
            continue
        prior_errors: list[str] | None = None
        prior_attempts = sorted((args.output_root / "buckets").glob(f"{slug}.attempt_*.json"))
        attempt_offset = len(prior_attempts)
        for retry_index in range(1, args.schema_attempts + 1):
            model_attempt = attempt_offset + retry_index
            print(f"CALL {bucket}: input={len(rows)} schema_attempt={retry_index}/{args.schema_attempts} artifact_attempt={model_attempt}", flush=True)
            raw, reasoning, usage = call_model(
                config,
                [
                    {"role": "system", "content": system_prompt()},
                    {"role": "user", "content": user_prompt(bucket, rows, prior_errors)},
                ],
                args,
            )
            attempt_path = args.output_root / "buckets" / f"{slug}.attempt_{model_attempt:02d}.json"
            write_json(attempt_path, {
                "bucket": bucket, "attempt": model_attempt, "raw_model_output": raw,
                "model_reasoning": reasoning, "usage": usage, "completed_at": utc_now(),
            })
            try:
                parsed = parse_json_object(raw)
                cleaned, errors = validate_model_output(parsed, rows)
            except (json.JSONDecodeError, AggregationError) as exc:
                cleaned, errors = [], [f"JSON/schema parse error: {exc}"]
            if not errors:
                accepted = {"skills": cleaned}
                write_json(accepted_path, accepted)
                record = {
                    "bucket": bucket,
                    "input_skill_count": len(rows),
                    "output_skill_count": len(cleaned),
                    "input_source_count": len(rows),
                    "accounted_source_count": sum(len(skill["source_skill_keys"]) for skill in cleaned),
                    "model_attempts": model_attempt,
                    "accepted_attempt_file": str(attempt_path),
                    "accepted_output_hash": object_hash(accepted),
                    "usage": usage,
                }
                write_json(record_path, record)
                bucket_results[bucket] = cleaned
                records.append(record)
                print(f"ACCEPT {bucket}: {len(rows)} -> {len(cleaned)}", flush=True)
                break
            prior_errors = errors
            print(f"REJECT {bucket}: {errors}", flush=True)
        else:
            raise AggregationError(f"bucket {bucket} exhausted {args.schema_attempts} schema attempts")

    general: list[dict[str, Any]] = []
    task_specific: dict[str, list[dict[str, Any]]] = {label: [] for label in TASK_LABELS}
    for bucket in BUCKETS:
        target = general if bucket == "general" else task_specific[bucket]
        prefix = "G" if bucket == "general" else f"T{TASK_LABELS.index(bucket) + 1}"
        for index, skill in enumerate(bucket_results[bucket], 1):
            target.append({"global_skill_id": f"{prefix}_{index:03d}", **skill})
    output_count = len(general) + sum(len(rows) for rows in task_specific.values())
    if output_count > len(adds):
        raise AggregationError(f"global output {output_count} exceeds 151 input ADDs")
    global_bank = {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": EXPERIMENT_ID,
        "round_index": 1,
        "aggregation_mode": "role_agnostic_seven_bucket_semantic_merge",
        "capacity": {
            "maximum_total_skills": 151,
            "current_total_skills": output_count,
            "future_client_local_policy": "per_client_per_round_add_lte_floor_distinct_delete_div_3",
            "round1_bootstrap_exempt": True,
        },
        "general": general,
        "task_specific": task_specific,
        "source_input": {
            "initial_add_count": len(adds),
            "initial_add_patch_sha256": file_hash(adds_path),
            "input_manifest_sha256": file_hash(manifest_path),
        },
        "aggregation_model": descriptor,
        "server_evaluation": None,
    }
    global_bank["live_global_hash"] = object_hash({"general": general, "task_specific": task_specific})
    global_path = args.output_root / "global_skillbank.json"
    write_json(global_path, global_bank)
    downloads = {}
    raw = global_path.read_bytes()
    for client in ("A", "B", "C"):
        destination = args.output_root / "downloads" / f"client_{client}" / "global_skillbank.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        downloads[client] = {"path": str(destination), "file_sha256": file_hash(destination)}
    hashes = {row["file_sha256"] for row in downloads.values()} | {file_hash(global_path)}
    if len(hashes) != 1:
        raise AggregationError("client download copies are not byte-identical")
    summary = {
        "status": "complete",
        "completed_at": utc_now(),
        "experiment_id": EXPERIMENT_ID,
        "input_skill_count": len(adds),
        "output_skill_count": output_count,
        "bucket_counts": {
            bucket: {"input": len(bucket_inputs(adds, bucket)), "output": len(bucket_results[bucket])}
            for bucket in BUCKETS
        },
        "global_skillbank": {
            "path": str(global_path), "file_sha256": file_hash(global_path),
            "live_global_hash": global_bank["live_global_hash"],
        },
        "downloads": downloads,
        "server_evaluation_performed": False,
        "client_evaluation_started": False,
        "records": records,
    }
    write_json(args.output_root / "summary.json", summary)
    return summary


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("--bank-a", type=Path, default=DEFAULT_BANKS["A"])
    value.add_argument("--bank-b", type=Path, default=DEFAULT_BANKS["B"])
    value.add_argument("--bank-c", type=Path, default=DEFAULT_BANKS["C"])
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
