"""Generate one client's role-agnostic B2 patch under the D-096 3-delete/1-add rule."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from client_code.skillbank_loader import EXPECTED_ROLES, SKILL_FIELDS, TASK_TYPE_LABELS, parse_bank
from originalFL.banks import file_hash, write_json


TASK_LABELS = tuple(TASK_TYPE_LABELS.values())
MAX_FIELD_CHARACTERS = 900
ROLE_TOKENS = ("planner", "executor", "critic", "supervisor", "search worker", "operation worker")


class EvolutionError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def object_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            text = text[start:end + 1]
    value = json.loads(text)
    if not isinstance(value, dict):
        raise EvolutionError("Teacher output must be one JSON object")
    return value


def validate_skill(raw: Any, context: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise EvolutionError(f"{context}: skill must be an object")
    skill_type = raw.get("type")
    fields = SKILL_FIELDS.get(skill_type)
    if fields is None:
        raise EvolutionError(f"{context}: unsupported type {skill_type!r}")
    skill = {"type": skill_type}
    for field in fields:
        value = raw.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > MAX_FIELD_CHARACTERS:
            raise EvolutionError(f"{context}: invalid {field}")
        lowered = value.casefold()
        if any(re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", lowered) for token in ROLE_TOKENS):
            raise EvolutionError(f"{context}: role-specific wording is forbidden")
        skill[field] = value.strip()
    return skill


def extract_base_repository(parent: dict[str, Any], client: str) -> dict[str, Any]:
    parse_bank(parent, client)
    active = parent["active_skillbanks"]
    repositories = [active[role] for role in EXPECTED_ROLES[client]]
    if any(repository != repositories[0] for repository in repositories[1:]):
        raise EvolutionError("all runtime roles must map the identical Global repository")
    return json.loads(json.dumps(repositories[0], ensure_ascii=False))


def flatten_repository(repository: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    skills: dict[str, dict[str, Any]] = {}
    buckets: dict[str, str] = {}
    for bucket, rows in [("general", repository["general"]), *repository["task_specific"].items()]:
        for row in rows:
            skill_id = row.get("skill_id")
            if not isinstance(skill_id, str) or not skill_id or skill_id in skills:
                raise EvolutionError(f"invalid or duplicate base skill ID: {skill_id!r}")
            skills[skill_id] = validate_skill(row, f"base/{bucket}/{skill_id}")
            buckets[skill_id] = bucket
    return skills, buckets


def validate_and_apply_patch(
    value: dict[str, Any], repository: dict[str, Any], client: str, round_index: int = 2,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, int]]:
    if set(value) != {"operations"} or not isinstance(value.get("operations"), list):
        raise EvolutionError("top-level output must be exactly {'operations': [...]} ")
    base_skills, base_buckets = flatten_repository(repository)
    operations: list[dict[str, Any]] = []
    touched: set[str] = set()
    add_rows: list[dict[str, Any]] = []
    delete_count = 0
    for index, raw in enumerate(value["operations"], 1):
        if not isinstance(raw, dict):
            raise EvolutionError(f"operation {index}: must be an object")
        operation = str(raw.get("operation", "")).upper()
        evidence_refs = raw.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs or any(not isinstance(x, str) or not x for x in evidence_refs):
            raise EvolutionError(f"operation {index}: evidence_refs must be a non-empty string list")
        if operation in {"DELETE", "UPDATE"}:
            target = raw.get("target_skill_id")
            if target not in base_skills:
                raise EvolutionError(f"operation {index}: unknown target_skill_id {target!r}")
            if target in touched:
                raise EvolutionError(f"operation {index}: target {target!r} is modified more than once")
            touched.add(target)
            if operation == "DELETE":
                delete_count += 1
                operations.append({"operation": "DELETE", "target_skill_id": target, "evidence_refs": evidence_refs})
            else:
                bucket = raw.get("bucket")
                if bucket not in ("general", *TASK_LABELS):
                    raise EvolutionError(f"operation {index}: invalid bucket {bucket!r}")
                skill = validate_skill(raw.get("skill"), f"operation {index}/UPDATE")
                operations.append({"operation": "UPDATE", "target_skill_id": target, "bucket": bucket, "skill": skill, "evidence_refs": evidence_refs})
        elif operation == "ADD":
            bucket = raw.get("bucket")
            if bucket not in ("general", *TASK_LABELS):
                raise EvolutionError(f"operation {index}: invalid bucket {bucket!r}")
            skill = validate_skill(raw.get("skill"), f"operation {index}/ADD")
            row = {"operation": "ADD", "bucket": bucket, "skill": skill, "evidence_refs": evidence_refs}
            operations.append(row)
            add_rows.append(row)
        else:
            raise EvolutionError(f"operation {index}: unsupported operation {operation!r}")
    add_count = len(add_rows)
    if add_count > delete_count // 3:
        raise EvolutionError(f"3-delete/1-add violation: DELETE={delete_count}, ADD={add_count}")

    result: dict[str, Any] = {"general": [], "task_specific": {label: [] for label in TASK_LABELS}}
    updates = {row["target_skill_id"]: row for row in operations if row["operation"] == "UPDATE"}
    deletes = {row["target_skill_id"] for row in operations if row["operation"] == "DELETE"}
    source_rows = repository["general"] + sum((repository["task_specific"][label] for label in TASK_LABELS), [])
    for row in source_rows:
        skill_id = row["skill_id"]
        if skill_id in deletes:
            continue
        bucket = base_buckets[skill_id]
        if skill_id in updates:
            patch = updates[skill_id]
            bucket = patch["bucket"]
            clean = {"skill_id": skill_id, "version": int(row.get("version", 1)) + 1, **patch["skill"]}
            clean["source_skill_keys"] = list(row.get("source_skill_keys") or [])
        else:
            clean = json.loads(json.dumps(row, ensure_ascii=False))
        (result["general"] if bucket == "general" else result["task_specific"][bucket]).append(clean)
    for add_index, patch in enumerate(add_rows, 1):
        skill_id = f"{client}_R{round_index}_ADD_{add_index:03d}"
        clean = {"skill_id": skill_id, "version": 1, **patch["skill"], "source_skill_keys": [f"{client}/round_{round_index}/add/{skill_id}"]}
        bucket = patch["bucket"]
        (result["general"] if bucket == "general" else result["task_specific"][bucket]).append(clean)
    final_rows = result["general"] + sum((result["task_specific"][label] for label in TASK_LABELS), [])
    semantic_hashes = [object_hash({k: v for k, v in row.items() if k in {"type", *SKILL_FIELDS[row["type"]]}}) for row in final_rows]
    if len(set(semantic_hashes)) != len(semantic_hashes):
        raise EvolutionError("candidate contains exact semantic duplicates")
    counts = {"base": len(base_skills), "delete": delete_count, "add": add_count, "update": len(updates), "candidate": len(final_rows)}
    if counts["candidate"] != counts["base"] - counts["delete"] + counts["add"]:
        raise EvolutionError("candidate count is inconsistent with patch")
    return result, operations, counts


def compact_episode(episode: dict[str, Any]) -> dict[str, Any]:
    events = list(episode.get("environment_events") or [])
    informative = [row for row in events if any(token in str(row.get("observation", "")).casefold() for token in ("nothing happens", "can't", "cannot", "closed", "invalid", "not holding"))]
    selected, seen = [], set()
    for row in events[:4] + informative[:6] + events[-6:]:
        key = (row.get("step"), row.get("action"), row.get("observation"))
        if key not in seen:
            seen.add(key)
            selected.append({"step": row.get("step"), "action": row.get("action"), "observation": str(row.get("observation", ""))[:700]})
    role_evidence = {}
    for role, rows in (episode.get("role_evidence") or {}).items():
        chosen = list(rows or [])[:2] + list(rows or [])[-2:]
        role_evidence[role] = [{k: (str(v)[:900] if isinstance(v, str) else v) for k, v in row.items()} for row in chosen]
    return {"evidence_ref": episode.get("evidence_ref"), "goal": episode.get("goal"), "success": episode.get("success"), "terminal_reason": episode.get("terminal_reason"), "environment_events": selected, "role_evidence": role_evidence}


def validate_findings(value: dict[str, Any]) -> list[dict[str, Any]]:
    if set(value) != {"findings"}:
        raise EvolutionError("family output must contain exactly one findings field")
    findings = value.get("findings")
    if not isinstance(findings, list) or len(findings) > 8:
        count = len(findings) if isinstance(findings, list) else None
        raise EvolutionError(f"findings must be a list with at most 8 items; got {count}")
    if any(not isinstance(row, dict) for row in findings):
        raise EvolutionError("every finding must be an object")
    return findings


def normalize_known_json_mode_wrapper(
    value: dict[str, Any], expected_field: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Remove only the exact observed JSON-mode type marker and record the change."""
    keys = set(value)
    if keys == {expected_field}:
        return value, None
    if keys == {expected_field, "type"} and value.get("type") == "json_object":
        normalized = {expected_field: value[expected_field]}
        return normalized, {
            "policy": "remove_exact_known_json_mode_type_wrapper.v1",
            "original_top_level_keys": sorted(keys),
            "removed_field": {"type": "json_object"},
            "normalized_top_level_keys": [expected_field],
            "normalized_object_sha256": object_hash(normalized),
        }
    return value, None


def oversized_skill_fields(value: dict[str, Any]) -> list[dict[str, Any]]:
    """Return every non-empty skill text field that exceeds the hard schema limit."""
    operations = value.get("operations")
    if not isinstance(operations, list):
        return []
    targets: list[dict[str, Any]] = []
    for operation_index, operation in enumerate(operations):
        if not isinstance(operation, dict) or operation.get("operation") not in {"UPDATE", "ADD"}:
            continue
        skill = operation.get("skill")
        if not isinstance(skill, dict) or skill.get("type") not in SKILL_FIELDS:
            continue
        for field in SKILL_FIELDS[skill["type"]]:
            text = skill.get(field)
            if isinstance(text, str) and text.strip() and len(text) > MAX_FIELD_CHARACTERS:
                targets.append({
                    "operation_index": operation_index,
                    "operation_number": operation_index + 1,
                    "operation": operation.get("operation"),
                    "target_skill_id": operation.get("target_skill_id"),
                    "field": field,
                    "original_length": len(text),
                })
    return targets


def validate_compression_only(
    previous: dict[str, Any], candidate: dict[str, Any],
    targets: list[dict[str, Any]], target_max: int,
) -> None:
    """Require exact structural equality except for the listed compressed fields."""
    if not targets:
        raise EvolutionError("field compression requires at least one oversized field")
    before = copy.deepcopy(previous)
    after = copy.deepcopy(candidate)
    for target in targets:
        index = int(target["operation_index"])
        field = str(target["field"])
        try:
            prior_text = before["operations"][index]["skill"][field]
            revised_text = after["operations"][index]["skill"][field]
        except (KeyError, IndexError, TypeError) as exc:
            raise EvolutionError(f"compression target disappeared: operation {index + 1}/{field}") from exc
        if not isinstance(revised_text, str) or not revised_text.strip() or len(revised_text) > target_max:
            length = len(revised_text) if isinstance(revised_text, str) else None
            raise EvolutionError(f"compressed operation {index + 1}/{field} must be 1..{target_max} characters; got {length}")
        if revised_text == prior_text:
            raise EvolutionError(f"compression target was unchanged: operation {index + 1}/{field}")
        before["operations"][index]["skill"][field] = "<COMPRESSED_FIELD>"
        after["operations"][index]["skill"][field] = "<COMPRESSED_FIELD>"
    if before != after:
        raise EvolutionError("field compression changed content outside the authorized fields")


def apply_compression_replacements(
    previous: dict[str, Any], response: dict[str, Any],
    targets: list[dict[str, Any]], target_max: int,
) -> dict[str, Any]:
    """Apply an exact replacement table to a copy of the frozen patch."""
    if set(response) != {"replacements"} or not isinstance(response.get("replacements"), list):
        raise EvolutionError("compression response must contain exactly one replacements list")
    expected = {(int(row["operation_number"]), str(row["field"])) for row in targets}
    replacements: dict[tuple[int, str], str] = {}
    for index, row in enumerate(response["replacements"], 1):
        if not isinstance(row, dict) or set(row) != {"operation_number", "field", "text"}:
            raise EvolutionError(f"replacement {index} must contain exactly operation_number, field, and text")
        key = (row["operation_number"], row["field"])
        if key not in expected or key in replacements:
            raise EvolutionError(f"replacement {index} is unknown or duplicated: {key!r}")
        text = row["text"]
        if not isinstance(text, str) or not text.strip() or len(text) > target_max:
            length = len(text) if isinstance(text, str) else None
            raise EvolutionError(f"replacement {index} text must be 1..{target_max} characters; got {length}")
        replacements[key] = text.strip()
    if set(replacements) != expected:
        raise EvolutionError(f"replacement set mismatch: expected {sorted(expected)}, got {sorted(replacements)}")
    candidate = copy.deepcopy(previous)
    for (operation_number, field), text in replacements.items():
        candidate["operations"][operation_number - 1]["skill"][field] = text
    return candidate


def call_json(
    config: Any, messages: list[dict[str, str]], args: argparse.Namespace,
    expected_field: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError
    recoverable = (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError)
    for attempt in range(args.retries + 1):
        try:
            response = config.client(timeout=args.timeout).chat.completions.create(model=config.model, messages=messages, temperature=0, seed=args.seed, max_tokens=args.max_tokens, stream=False, response_format={"type": "json_object"}, extra_body={"thinking": {"type": "disabled"}})
            if not response.choices or getattr(response.choices[0], "finish_reason", None) == "length":
                raise EvolutionError("Teacher response missing or truncated")
            message = response.choices[0].message
            raw = message.content or ""
            usage = getattr(response, "usage", None)
            parsed = parse_json_object(raw)
            parsed, normalization_audit = normalize_known_json_mode_wrapper(parsed, expected_field)
            record = {"raw_model_output": raw, "model_reasoning": getattr(message, "reasoning_content", None) or "", "usage": {"prompt_tokens": getattr(usage, "prompt_tokens", None), "completion_tokens": getattr(usage, "completion_tokens", None), "total_tokens": getattr(usage, "total_tokens", None), "transport_attempts": attempt + 1, "requested_model": config.model, "response_model": getattr(response, "model", None)}, "completed_at": now()}
            if normalization_audit is not None:
                record["normalization_audit"] = normalization_audit
            return parsed, record
        except recoverable:
            if attempt == args.retries:
                raise
            time.sleep(min(2 ** (attempt + 1), 15))
    raise AssertionError("unreachable")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", choices=("A", "B", "C"), required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--parent-bank", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--record-output", type=Path, required=True)
    parser.add_argument("--patch-output", type=Path, required=True)
    parser.add_argument("--generation", type=int, default=2)
    parser.add_argument("--expected-base-count", type=int, default=43)
    parser.add_argument("--parent-label", default="Global SkillBank1")
    parser.add_argument("--experiment-id", default="v9-global1-to-local-b2")
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--max-tokens", type=int, default=16000)
    parser.add_argument("--timeout", type=float, default=240)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--schema-attempts", type=int, default=3)
    parser.add_argument("--family-schema-attempts", type=int, default=3)
    parser.add_argument("--field-compression-attempts", type=int, default=2)
    parser.add_argument("--field-compression-target", type=int, default=760)
    parser.add_argument("--replacement-compression-attempts", type=int, default=2)
    parser.add_argument("--sanitized-compression-attempts", type=int, default=2)
    parser.add_argument("--sanitized-compression-target", type=int, default=650)
    args = parser.parse_args()
    if any(path.exists() for path in (args.output, args.record_output, args.patch_output)):
        raise SystemExit("refusing to overwrite frozen B2/record/patch output")
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    parent = json.loads(args.parent_bank.read_text(encoding="utf-8"))
    if evidence.get("client_id") != args.client or evidence.get("generation") != args.generation or len(evidence.get("episodes") or []) != 134:
        raise SystemExit(f"complete Client generation-{args.generation} training evidence with 134 episodes is required")
    if evidence.get("parent_bank_file_sha256") != file_hash(args.parent_bank):
        raise SystemExit("evidence parent-bank hash mismatch")
    repository = extract_base_repository(parent, args.client)
    base_skills, _ = flatten_repository(repository)
    if len(base_skills) != args.expected_base_count:
        raise SystemExit(f"{args.parent_label} must contain {args.expected_base_count} skills, got {len(base_skills)}")
    from originalFL.round1_evolver import _local_evolution_config

    config = _local_evolution_config()
    descriptor = config.descriptor()
    if config.model != "deepseek-flash" or descriptor.get("provider") != "deepseek_official" or descriptor.get("endpoint_origin") != "https://api.deepseek.com":
        raise SystemExit("DeepSeek official deepseek-flash Teacher is required")
    checkpoint_path = args.record_output.with_suffix(".checkpoint.json")
    identity = {"client": args.client, "evidence_file_sha256": file_hash(args.evidence), "parent_bank_file_sha256": file_hash(args.parent_bank), "teacher": descriptor}
    checkpoint = {**identity, "family_findings": {}, "records": []}
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if any(checkpoint.get(k) != v for k, v in identity.items()):
            raise SystemExit("Teacher checkpoint identity mismatch")
    episodes = evidence["episodes"]
    for type_id, label in TASK_TYPE_LABELS.items():
        if label in checkpoint["family_findings"]:
            continue
        rows = [compact_episode(row) for row in episodes if int(row["task_type_id"]) == type_id]
        prior_invalid = [record for record in checkpoint["records"] if record.get("stage") == "family_analysis_invalid" and record.get("task_label") == label]
        if len(prior_invalid) >= args.family_schema_attempts:
            raise EvolutionError(f"family analysis repair budget exhausted for {label}")
        accepted_findings = None
        for attempt in range(len(prior_invalid) + 1, args.family_schema_attempts + 1):
            if attempt == 1:
                prompt = {"client": args.client, "task_type": label, "trajectory_count": len(rows), "trajectories": rows, "current_global_general": repository["general"], "current_task_skills": repository["task_specific"][label], "instruction": "Analyze all trajectories against the shared role-agnostic bank. Return up to 8 concise evidence-grounded findings for KEEP/UPDATE/DELETE/MOVE/ADD consideration. Do not decide quota or emit a final patch. The response_format setting is transport metadata: return exactly one JSON object whose only top-level field is findings; never copy type, schema, name, or another wrapper field into the response body.", "output_schema": {"findings": [{"recommendation": "...", "affected_skill_ids": ["..."], "evidence_refs": ["..."]}]}}
                system = "You are a conservative ALFWorld shared SkillBank evidence analyst."
            else:
                latest = prior_invalid[-1] if prior_invalid else checkpoint["records"][-1]
                prompt = {"client": args.client, "task_type": label, "invalid_previous_output": latest.get("raw_model_output"), "validation_error": latest.get("validation_error"), "instruction": "Repair the previous response without adding new claims. Consolidate overlapping findings and return at most 8 findings. Preserve evidence references for retained claims. Return exactly one JSON object with only a findings list.", "output_schema": {"findings": [{"recommendation": "...", "affected_skill_ids": ["..."], "evidence_refs": ["..."]}]}}
                system = "You repair a family-analysis schema violation without re-analyzing trajectories."
            value, record = call_json(config, [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}], args, "findings")
            try:
                accepted_findings = validate_findings(value)
                checkpoint["family_findings"][label] = accepted_findings
                checkpoint["records"].append({"stage": "family_analysis" if attempt == 1 else "family_analysis_repair", "task_label": label, "attempt": attempt, **record})
                write_json(checkpoint_path, checkpoint)
                break
            except EvolutionError as exc:
                invalid_record = {"stage": "family_analysis_invalid", "task_label": label, "attempt": attempt, "validation_error": str(exc), **record}
                checkpoint["records"].append(invalid_record)
                prior_invalid.append(invalid_record)
                write_json(checkpoint_path, checkpoint)
        if accepted_findings is None:
            raise EvolutionError(f"invalid findings for {label} after {args.family_schema_attempts} attempts")
    rejected_patches = [record for record in checkpoint["records"] if record.get("stage") == "final_patch_rejected"]
    prior_errors: list[str] = list(rejected_patches[-1].get("validation_errors") or []) if rejected_patches else []
    accepted_repository = None
    accepted_operations = None
    accepted_counts = None
    for attempt in range(len(rejected_patches) + 1, args.schema_attempts + 1):
        prompt = {"client": args.client, "base_skill_count": args.expected_base_count, "base_repository": repository, "family_findings": checkpoint["family_findings"], "hard_policy": {"add_lte_floor_distinct_delete_div_3": True, "quota_scope": "whole client bank across General and six task buckets", "update_neither_consumes_nor_creates_quota": True, "merge_encoding": "UPDATE one surviving target and DELETE absorbed targets"}, "instruction": f"Return the complete evidence-grounded net patch from {args.parent_label} to this client's B{args.generation}. Use DELETE and UPDATE only on existing IDs. ADD creates a new skill. Skills may move between buckets through UPDATE. Do not emit KEEP/NONE/MERGE. Prefer UPDATE or DELETE over speculative ADD. Return exactly one JSON object whose only top-level field is operations; never copy type, schema, name, or another wrapper field into the response body.", "operation_schema": {"operations": [{"operation": "DELETE", "target_skill_id": "existing ID", "evidence_refs": ["..."]}, {"operation": "UPDATE", "target_skill_id": "existing ID", "bucket": "general or one Chinese task label", "skill": "one valid skill object", "evidence_refs": ["..."]}, {"operation": "ADD", "bucket": "general or one Chinese task label", "skill": "one valid skill object", "evidence_refs": ["..."]}]}, "previous_validation_errors": prior_errors}
        value, record = call_json(config, [{"role": "system", "content": "You are the final conservative role-agnostic SkillBank patch composer. Obey the 3-delete/1-add rule exactly."}, {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}], args, "operations")
        attempt_path = args.record_output.parent / f"B{args.generation}_patch_attempt_{attempt:02d}.json"
        if attempt_path.exists():
            raise EvolutionError(f"refusing to overwrite patch attempt: {attempt_path}")
        write_json(attempt_path, {"attempt": attempt, **record})
        try:
            accepted_repository, accepted_operations, accepted_counts = validate_and_apply_patch(value, repository, args.client, args.generation)
            checkpoint["records"].append({"stage": "final_patch", "attempt": attempt, "counts": accepted_counts, **record})
            break
        except EvolutionError as exc:
            prior_errors = [str(exc)]
            checkpoint["records"].append({"stage": "final_patch_rejected", "attempt": attempt, "validation_errors": prior_errors, **record})
            write_json(checkpoint_path, checkpoint)

    rejected_patches = [record for record in checkpoint["records"] if record.get("stage") == "final_patch_rejected"]
    if accepted_repository is None and rejected_patches:
        latest_rejected = rejected_patches[-1]
        previous_value = parse_json_object(str(latest_rejected.get("raw_model_output") or ""))
        previous_value, prior_normalization = normalize_known_json_mode_wrapper(previous_value, "operations")
        targets = oversized_skill_fields(previous_value)
        compression_records = [record for record in checkpoint["records"] if record.get("stage") in {"final_patch_field_compression", "final_patch_field_compression_rejected"}]
        for compression_attempt in range(len(compression_records) + 1, args.field_compression_attempts + 1):
            if not targets:
                break
            prompt = {
                "invalid_previous_output": previous_value,
                "authorized_fields": targets,
                "hard_target_characters": args.field_compression_target,
                "instruction": (
                    "Compress only the listed oversized skill text fields to at most the hard target. "
                    "Preserve their operational meaning and critical conditions. Every operation, operation order, "
                    "target ID, bucket, evidence reference, skill type, and every unlisted field must remain exactly unchanged. "
                    "Do not add, delete, reorder, or otherwise rewrite operations. Return exactly one JSON object whose only "
                    "top-level field is operations; never copy transport metadata into the body."
                ),
            }
            value, record = call_json(
                config,
                [
                    {"role": "system", "content": "You perform a loss-minimizing, field-only compression repair. No other edit is authorized."},
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
                args,
                "operations",
            )
            attempt_path = args.record_output.parent / f"B{args.generation}_patch_compression_{compression_attempt:02d}.json"
            if attempt_path.exists():
                raise EvolutionError(f"refusing to overwrite compression attempt: {attempt_path}")
            audit = {
                "attempt": compression_attempt,
                "source_patch_object_sha256": object_hash(previous_value),
                "authorized_fields": targets,
                "target_max_characters": args.field_compression_target,
                **record,
            }
            write_json(attempt_path, audit)
            try:
                validate_compression_only(previous_value, value, targets, args.field_compression_target)
                accepted_repository, accepted_operations, accepted_counts = validate_and_apply_patch(value, repository, args.client, args.generation)
                checkpoint["records"].append({"stage": "final_patch_field_compression", "attempt": compression_attempt, "counts": accepted_counts, **audit})
                write_json(checkpoint_path, checkpoint)
                break
            except EvolutionError as exc:
                prior_errors = [str(exc)]
                checkpoint["records"].append({"stage": "final_patch_field_compression_rejected", "attempt": compression_attempt, "validation_errors": prior_errors, **audit})
                write_json(checkpoint_path, checkpoint)

        replacement_records = [record for record in checkpoint["records"] if record.get("stage") in {"final_patch_replacement_compression", "final_patch_replacement_compression_rejected"}]
        for replacement_attempt in range(len(replacement_records) + 1, args.replacement_compression_attempts + 1):
            if accepted_repository is not None or not targets:
                break
            requested = []
            for target in targets:
                source_text = previous_value["operations"][target["operation_index"]]["skill"][target["field"]]
                requested.append({**target, "source_text": source_text})
            prompt = {
                "fields_to_compress": requested,
                "hard_target_characters": args.field_compression_target,
                "instruction": (
                    "Return one replacement for every listed field. Preserve its operational meaning and critical conditions, "
                    "but make text at most the hard target. Do not return the patch or any unlisted content. Return exactly one "
                    "JSON object whose only top-level field is replacements. Each replacement must contain exactly "
                    "operation_number, field, and text."
                ),
                "output_schema": {"replacements": [{"operation_number": 1, "field": "principle", "text": "compressed text"}]},
            }
            value, record = call_json(
                config,
                [
                    {"role": "system", "content": "You compress only the supplied text fields and return a minimal replacement table."},
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
                args,
                "replacements",
            )
            attempt_path = args.record_output.parent / f"B{args.generation}_patch_replacement_compression_{replacement_attempt:02d}.json"
            if attempt_path.exists():
                raise EvolutionError(f"refusing to overwrite replacement compression attempt: {attempt_path}")
            audit = {
                "attempt": replacement_attempt,
                "source_patch_object_sha256": object_hash(previous_value),
                "authorized_fields": targets,
                "target_max_characters": args.field_compression_target,
                **record,
            }
            write_json(attempt_path, audit)
            try:
                candidate_value = apply_compression_replacements(previous_value, value, targets, args.field_compression_target)
                validate_compression_only(previous_value, candidate_value, targets, args.field_compression_target)
                accepted_repository, accepted_operations, accepted_counts = validate_and_apply_patch(candidate_value, repository, args.client, args.generation)
                checkpoint["records"].append({"stage": "final_patch_replacement_compression", "attempt": replacement_attempt, "counts": accepted_counts, **audit})
                write_json(checkpoint_path, checkpoint)
                break
            except EvolutionError as exc:
                prior_errors = [str(exc)]
                checkpoint["records"].append({"stage": "final_patch_replacement_compression_rejected", "attempt": replacement_attempt, "validation_errors": prior_errors, **audit})
                write_json(checkpoint_path, checkpoint)

        sanitized_records = [record for record in checkpoint["records"] if record.get("stage") in {"final_patch_sanitized_compression", "final_patch_sanitized_compression_rejected"}]
        for sanitized_attempt in range(len(sanitized_records) + 1, args.sanitized_compression_attempts + 1):
            if accepted_repository is not None or not targets:
                break
            requested = []
            for target in targets:
                source_text = previous_value["operations"][target["operation_index"]]["skill"][target["field"]]
                requested.append({**target, "source_text": source_text})
            prompt = {
                "fields_to_compress": requested,
                "hard_target_characters": args.sanitized_compression_target,
                "forbidden_role_words": list(ROLE_TOKENS),
                "instruction": (
                    "Return one concise replacement for every listed field. Each text must be at most the hard target, must not "
                    "contain any forbidden role word, and must preserve the environment procedure, success checks, and recovery steps. "
                    "Do not return the patch or any unlisted content. Return exactly one JSON object whose only top-level field is "
                    "replacements; each item contains exactly operation_number, field, and text."
                ),
                "output_schema": {"replacements": [{"operation_number": 1, "field": "principle", "text": "concise role-neutral text"}]},
            }
            value, record = call_json(
                config,
                [
                    {"role": "system", "content": "Produce short, role-neutral field replacements only. Obey the character ceiling for every item."},
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
                args,
                "replacements",
            )
            attempt_path = args.record_output.parent / f"B{args.generation}_patch_sanitized_compression_{sanitized_attempt:02d}.json"
            if attempt_path.exists():
                raise EvolutionError(f"refusing to overwrite sanitized compression attempt: {attempt_path}")
            audit = {
                "attempt": sanitized_attempt,
                "source_patch_object_sha256": object_hash(previous_value),
                "authorized_fields": targets,
                "target_max_characters": args.sanitized_compression_target,
                "forbidden_role_words": list(ROLE_TOKENS),
                **record,
            }
            write_json(attempt_path, audit)
            try:
                candidate_value = apply_compression_replacements(previous_value, value, targets, args.sanitized_compression_target)
                validate_compression_only(previous_value, candidate_value, targets, args.sanitized_compression_target)
                accepted_repository, accepted_operations, accepted_counts = validate_and_apply_patch(candidate_value, repository, args.client, args.generation)
                checkpoint["records"].append({"stage": "final_patch_sanitized_compression", "attempt": sanitized_attempt, "counts": accepted_counts, **audit})
                write_json(checkpoint_path, checkpoint)
                break
            except EvolutionError as exc:
                prior_errors = [str(exc)]
                checkpoint["records"].append({"stage": "final_patch_sanitized_compression_rejected", "attempt": sanitized_attempt, "validation_errors": prior_errors, **audit})
                write_json(checkpoint_path, checkpoint)
    if accepted_repository is None or accepted_operations is None or accepted_counts is None:
        raise EvolutionError(f"Teacher exhausted patch repairs: {prior_errors}")
    bank = {"schema_version": "stage3_2.local_role_agnostic_bank.v1", "experiment_id": args.experiment_id, "client": args.client, "generation": args.generation, "parent": args.parent_label, "parent_bank_file_sha256": file_hash(args.parent_bank), "evidence_file_sha256": file_hash(args.evidence), "capacity_policy": {"policy": "three_distinct_deletes_per_add", "delete_count": accepted_counts["delete"], "add_count": accepted_counts["add"], "update_count": accepted_counts["update"], "base_count": args.expected_base_count, "candidate_count": accepted_counts["candidate"], "quota_passed": accepted_counts["add"] <= accepted_counts["delete"] // 3}, "general": accepted_repository["general"], "task_specific": accepted_repository["task_specific"], "teacher": descriptor}
    bank["live_repository_sha256"] = object_hash({"general": bank["general"], "task_specific": bank["task_specific"]})
    patch_doc = {"schema_version": "stage3_2.local_net_patch.v1", "client": args.client, "round_index": args.generation, "base_bank_file_sha256": file_hash(args.parent_bank), "counts": accepted_counts, "operations": accepted_operations, "candidate_live_repository_sha256": bank["live_repository_sha256"]}
    write_json(args.patch_output, patch_doc)
    write_json(args.output, bank)
    write_json(args.record_output, {"schema_version": 1, **identity, "generation": args.generation, "capacity_policy": bank["capacity_policy"], "patch_file_sha256": file_hash(args.patch_output), "bank_file_sha256": file_hash(args.output), "records": checkpoint["records"]})
    write_json(checkpoint_path, checkpoint)
    print(json.dumps({"status": "complete", "client": args.client, "generation": args.generation, "counts": accepted_counts, "bank": str(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
