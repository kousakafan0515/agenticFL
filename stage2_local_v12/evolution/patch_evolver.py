"""Role-preserving Client A evolution with a whole-client 3-delete/1-add quota."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import re
import signal
import threading
import time
from pathlib import Path
from typing import Any

from stage2_local_v12.clients.skillbank_loader import EXPECTED_ROLES, SKILL_FIELDS, TASK_TYPE_LABELS, parse_bank
from stage2_local_v12.runtime.banks import canonical_bytes, file_hash, write_json
from stage2_local_v12.evolution.teacher_api import _local_evolution_config
from stage2_local_v12.evolution.local_round2_evolver import (
    EvolutionError,
    now,
    object_hash,
    parse_json_object,
)


ROLES = EXPECTED_ROLES["A"]
ROLE_RULES = {
    "Planner": "Only learn goal decomposition, subtask ordering, and plan repair. Never assign environment actions to Planner.",
    "Executor": "Only learn local execution, observation-based decisions, exact ALFWorld action forms, and recovery inside the assigned subtask.",
}
TASK_LABELS = tuple(TASK_TYPE_LABELS.values())
MAX_FIELD_CHARACTERS = 900
MAX_FINDING_RECOMMENDATION_CHARACTERS = 600
MAX_FINDING_SKILL_IDS = 12
MAX_FINDING_EVIDENCE_REFS = 16
MAX_FINAL_PATCH_RECOVERY_ATTEMPTS = 2


class TeacherResponseBudgetError(EvolutionError):
    """Raised after bounded retries for an empty or length-truncated response."""


class TeacherWallClockTimeout(TimeoutError):
    """Raised when one synchronous Teacher request exceeds its wall-clock budget."""


@contextlib.contextmanager
def _wall_clock_deadline(seconds: float):
    if not hasattr(signal, "SIGALRM") or threading.current_thread() is not threading.main_thread():
        yield
        return

    def timeout_handler(signum: int, frame: Any) -> None:
        raise TeacherWallClockTimeout(f"Teacher request exceeded {seconds:g} seconds wall-clock time")

    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.setitimer(signal.ITIMER_REAL, max(float(seconds), 0.001))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, previous_timer[0], previous_timer[1])


def _usage_dict(response: Any) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
    }


def _next_attempt_path(prefix: Path) -> Path:
    index = 1
    while True:
        candidate = prefix.parent / f"{prefix.name}_response_{index:02d}.json"
        if not candidate.exists():
            return candidate
        index += 1


def call_json_recorded(
    config: Any,
    messages: list[dict[str, str]],
    args: argparse.Namespace,
    attempt_prefix: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Call the Teacher while preserving every response before validation."""
    from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

    recoverable = (APIConnectionError, APITimeoutError, InternalServerError, RateLimitError, TeacherWallClockTimeout)
    response_attempt = 0
    budget_failures = 0
    transport_failures = 0
    while True:
        response_attempt += 1
        path = _next_attempt_path(attempt_prefix)
        request_record = {
            "schema_version": "stage2_local_v9.teacher_response_attempt.v1",
            "attempt_kind": attempt_prefix.name,
            "response_attempt_within_call": response_attempt,
            "requested_model": config.model,
            "requested_max_tokens": args.max_tokens,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "messages_sha256": object_hash(messages),
            "message_character_count": sum(len(row.get("content", "")) for row in messages),
            "started_at_utc": now(),
        }
        try:
            with _wall_clock_deadline(args.timeout):
                response = config.client(timeout=args.timeout).chat.completions.create(
                    model=config.model,
                    messages=messages,
                    temperature=0,
                    seed=args.seed,
                    max_tokens=args.max_tokens,
                    response_format={"type": "json_object"},
                    stream=False,
                    extra_body={"thinking": {"type": "disabled"}},
                )
        except recoverable as exc:
            transport_failures += 1
            write_json(path, {
                **request_record,
                "status": "transport_error",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "completed_at_utc": now(),
            })
            if transport_failures > args.retries:
                raise
            time.sleep(min(2 ** transport_failures, 15))
            continue

        choices = list(getattr(response, "choices", None) or [])
        choice = choices[0] if choices else None
        finish_reason = getattr(choice, "finish_reason", None) if choice is not None else None
        message = getattr(choice, "message", None) if choice is not None else None
        raw = getattr(message, "content", None) if message is not None else None
        reasoning = getattr(message, "reasoning_content", None) if message is not None else None
        record = {
            **request_record,
            "status": "response_received",
            "response_model": getattr(response, "model", None),
            "choice_count": len(choices),
            "finish_reason": finish_reason,
            "raw_model_output": raw,
            "model_reasoning": reasoning or "",
            "usage": _usage_dict(response),
            "completed_at_utc": now(),
        }
        if not choices or finish_reason == "length":
            budget_failures += 1
            record["status"] = "empty_choices" if not choices else "length_truncated"
            write_json(path, record)
            if budget_failures <= args.truncation_retries:
                continue
            raise TeacherResponseBudgetError(
                f"Teacher response {record['status']} after {budget_failures} bounded attempts; "
                f"last record: {path}"
            )
        try:
            value = parse_json_object(raw or "")
        except (EvolutionError, json.JSONDecodeError) as exc:
            record["status"] = "json_parse_error"
            record["validation_error"] = str(exc)
            write_json(path, record)
            raise EvolutionError(f"Teacher JSON parse failed; response record: {path}: {exc}") from exc
        record["status"] = "parsed"
        write_json(path, record)
        return value, {
            "raw_model_output": raw or "",
            "model_reasoning": reasoning or "",
            "finish_reason": finish_reason,
            "usage": {
                **record["usage"],
                "response_attempts": response_attempt,
                "transport_failures": transport_failures,
                "requested_max_tokens": args.max_tokens,
                "requested_model": config.model,
                "response_model": record["response_model"],
            },
            "response_attempt_record": str(path),
            "completed_at": record["completed_at_utc"],
        }


def normalize_known_json_mode_wrapper(
    value: dict[str, Any], expected_field: str,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Remove only DeepSeek's exact, known JSON-mode wrapper marker."""
    expected_keys = {expected_field}
    actual_keys = set(value)
    if actual_keys == expected_keys:
        return value, None
    if actual_keys == expected_keys | {"type"} and value.get("type") == "json_object":
        normalized = {expected_field: value[expected_field]}
        return normalized, {
            "policy": "remove_exact_known_json_mode_type_wrapper.v1",
            "original_top_level_keys": sorted(actual_keys),
            "removed_field": {"type": "json_object"},
            "normalized_top_level_keys": [expected_field],
            "normalized_object_sha256": object_hash(normalized),
        }
    return value, None


def record_normalization_audit(record: dict[str, Any], audit: dict[str, Any]) -> None:
    """Write a separate audit record without altering the raw response record."""
    source = Path(record["response_attempt_record"])
    prefix = source.parent / f"{source.stem}_normalization"
    destination = _next_attempt_path(prefix)
    payload = {
        "schema_version": "stage2_local_v9.teacher_response_normalization.v1",
        "source_response_attempt_record": str(source),
        "source_response_attempt_file_sha256": file_hash(source),
        **audit,
        "completed_at_utc": now(),
    }
    write_json(destination, payload)
    record["normalization"] = audit
    record["normalization_audit_record"] = str(destination)


def validate_family_findings(
    value: dict[str, Any],
    allowed_evidence_refs: set[str],
    allowed_skill_ids: set[str],
) -> list[dict[str, Any]]:
    if set(value) != {"findings"}:
        raise EvolutionError("family output must contain exactly one findings field")
    findings = value.get("findings")
    if not isinstance(findings, list) or len(findings) > 8:
        count = len(findings) if isinstance(findings, list) else None
        raise EvolutionError(f"findings must be a list with at most 8 items; got {count}")
    clean: list[dict[str, Any]] = []
    for index, row in enumerate(findings, 1):
        if not isinstance(row, dict) or set(row) != {"recommendation", "affected_skill_ids", "evidence_refs"}:
            raise EvolutionError(f"finding {index}: invalid fields")
        recommendation = row["recommendation"]
        if not isinstance(recommendation, str) or not recommendation.strip() or len(recommendation) > MAX_FINDING_RECOMMENDATION_CHARACTERS:
            raise EvolutionError(
                f"finding {index}: recommendation must be 1-{MAX_FINDING_RECOMMENDATION_CHARACTERS} characters"
            )
        skill_ids = row["affected_skill_ids"]
        if not isinstance(skill_ids, list) or len(skill_ids) > MAX_FINDING_SKILL_IDS or any(
            not isinstance(skill_id, str) or skill_id not in allowed_skill_ids for skill_id in skill_ids
        ):
            raise EvolutionError(f"finding {index}: affected_skill_ids are invalid")
        refs = row["evidence_refs"]
        if not isinstance(refs, list) or not refs or len(refs) > MAX_FINDING_EVIDENCE_REFS or any(
            not isinstance(ref, str) or ref not in allowed_evidence_refs for ref in refs
        ):
            raise EvolutionError(f"finding {index}: evidence_refs are invalid")
        clean.append({
            "recommendation": recommendation.strip(),
            "affected_skill_ids": list(skill_ids),
            "evidence_refs": list(refs),
        })
    return clean


def validate_skill(raw: Any, context: str) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise EvolutionError(f"{context}: skill must be an object")
    skill_type = raw.get("type")
    if skill_type in {"Procedure", "Local Strategy", "Procedure / Local Strategy"}:
        skill_type = "Procedure or Local Strategy"
    fields = SKILL_FIELDS.get(skill_type)
    if fields is None:
        raise EvolutionError(f"{context}: unsupported type {skill_type!r}")
    result = {"type": skill_type}
    for field in fields:
        value = raw.get(field)
        if not isinstance(value, str) or not value.strip():
            raise EvolutionError(f"{context}: missing {field}")
        if len(value) > MAX_FIELD_CHARACTERS:
            raise EvolutionError(f"{context}: {field} exceeds {MAX_FIELD_CHARACTERS} characters")
        result[field] = value.strip()
    return result


def compact_episode(episode: dict[str, Any], role: str) -> dict[str, Any]:
    events = list(episode.get("environment_events") or [])
    informative = [
        row for row in events
        if any(token in str(row.get("observation", "")).casefold() for token in (
            "can't", "cannot", "nothing happens", "closed", "not holding", "invalid", "already",
        ))
    ]
    selected, seen = [], set()
    for row in events[:4] + informative[:8] + events[-6:]:
        key = (row.get("step"), row.get("action"), row.get("observation"))
        if key in seen:
            continue
        seen.add(key)
        selected.append({
            "step": row.get("step"),
            "action": row.get("action"),
            "observation": str(row.get("observation", ""))[:900],
        })
    role_rows = list((episode.get("role_evidence") or {}).get(role) or [])
    role_rows = role_rows[:2] if role == "Planner" else role_rows[:4] + role_rows[-4:]
    return {
        "evidence_ref": episode.get("evidence_ref"),
        "goal": episode.get("goal"),
        "success": episode.get("success"),
        "terminal_reason": episode.get("terminal_reason"),
        "environment_events": selected,
        "role_evidence": role_rows,
    }


def flatten_parent(parent: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for role in ROLES:
        repository = parent["active_skillbanks"][role]
        for bucket, rows in (("general", repository["general"]), *repository["task_specific"].items()):
            for raw in rows:
                skill_id = raw.get("skill_id")
                key = (role, skill_id)
                if not isinstance(skill_id, str) or not skill_id or key in result:
                    raise EvolutionError(f"invalid or duplicate parent target {key!r}")
                result[key] = {"bucket": bucket, "raw": raw, "skill": validate_skill(raw, f"parent/{role}/{bucket}/{skill_id}")}
    return result


def allowed_target_ids_by_role(parent: dict[str, Any]) -> dict[str, list[str]]:
    """Return the exact role-scoped target allowlist for DELETE and UPDATE."""
    flattened = flatten_parent(parent)
    return {
        role: sorted(skill_id for candidate_role, skill_id in flattened if candidate_role == role)
        for role in ROLES
    }


def unknown_target_pairs(value: dict[str, Any], parent: dict[str, Any]) -> list[dict[str, Any]]:
    """Describe only DELETE/UPDATE targets absent from the current role repository."""
    base = flatten_parent(parent)
    operations = value.get("operations") if isinstance(value, dict) else None
    if not isinstance(operations, list):
        return []
    invalid: list[dict[str, Any]] = []
    for index, row in enumerate(operations, 1):
        if not isinstance(row, dict) or str(row.get("operation", "")).upper() not in {"DELETE", "UPDATE"}:
            continue
        pair = (row.get("target_role"), row.get("target_skill_id"))
        if pair not in base:
            invalid.append({
                "operation_number": index,
                "operation": str(row.get("operation", "")).upper(),
                "target_role": row.get("target_role"),
                "target_skill_id": row.get("target_skill_id"),
            })
    return invalid


def validate_delete_update_stage(
    value: dict[str, Any], parent: dict[str, Any], allowed_evidence_refs: set[str], generation: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, int], dict[str, int]]:
    """Validate a stage-one patch that may contain only DELETE and UPDATE."""
    operations = value.get("operations") if isinstance(value, dict) else None
    if not isinstance(value, dict) or set(value) != {"operations"} or not isinstance(operations, list):
        raise EvolutionError("stage one output must be exactly {'operations': [...]} ")
    forbidden = [
        index for index, row in enumerate(operations, 1)
        if not isinstance(row, dict) or str(row.get("operation", "")).upper() not in {"DELETE", "UPDATE"}
    ]
    if forbidden:
        raise EvolutionError(f"stage one permits only DELETE/UPDATE; invalid operation numbers={forbidden}")
    return validate_and_apply_patch(value, parent, allowed_evidence_refs, generation)


def combine_split_patch(
    base_operations: list[dict[str, Any]], add_value: dict[str, Any], max_add: int,
) -> dict[str, Any]:
    """Combine frozen DELETE/UPDATE operations with a bounded ADD-only response."""
    operations = add_value.get("operations") if isinstance(add_value, dict) else None
    if not isinstance(add_value, dict) or set(add_value) != {"operations"} or not isinstance(operations, list):
        raise EvolutionError("stage two output must be exactly {'operations': [...]} ")
    forbidden = [
        index for index, row in enumerate(operations, 1)
        if not isinstance(row, dict) or str(row.get("operation", "")).upper() != "ADD"
    ]
    if forbidden:
        raise EvolutionError(f"stage two permits only ADD; invalid operation numbers={forbidden}")
    if len(operations) > max_add:
        raise EvolutionError(f"stage two ADD count {len(operations)} exceeds computed max_add={max_add}")
    return {"operations": json.loads(json.dumps(base_operations + operations, ensure_ascii=False))}


def _next_skill_id(existing: set[str]) -> str:
    maximum = 0
    for skill_id in existing:
        match = re.fullmatch(r"skill_(\d+)", skill_id)
        if match:
            maximum = max(maximum, int(match.group(1)))
    while True:
        maximum += 1
        candidate = f"skill_{maximum:03d}"
        if candidate not in existing:
            existing.add(candidate)
            return candidate


def validate_and_apply_patch(
    value: dict[str, Any], parent: dict[str, Any], allowed_evidence_refs: set[str], generation: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, int], dict[str, int]]:
    if set(value) != {"operations"} or not isinstance(value.get("operations"), list):
        raise EvolutionError("top-level output must be exactly {'operations': [...]} ")
    base = flatten_parent(parent)
    touched: set[tuple[str, str]] = set()
    operations: list[dict[str, Any]] = []
    delete_count = 0
    add_count = 0
    update_count = 0

    for index, raw in enumerate(value["operations"], 1):
        if not isinstance(raw, dict):
            raise EvolutionError(f"operation {index}: must be an object")
        operation = str(raw.get("operation", "")).upper()
        evidence_refs = raw.get("evidence_refs")
        if not isinstance(evidence_refs, list) or not evidence_refs or any(
            not isinstance(ref, str) or ref not in allowed_evidence_refs for ref in evidence_refs
        ):
            raise EvolutionError(f"operation {index}: evidence_refs must be non-empty and belong to this generation")
        if operation in {"DELETE", "UPDATE"}:
            role = raw.get("target_role")
            target = raw.get("target_skill_id")
            key = (role, target)
            if role not in ROLES or key not in base:
                raise EvolutionError(f"operation {index}: unknown target {key!r}")
            if key in touched:
                raise EvolutionError(f"operation {index}: target {key!r} modified more than once")
            touched.add(key)
            if operation == "DELETE":
                delete_count += 1
                operations.append({
                    "operation": "DELETE", "target_role": role,
                    "target_skill_id": target, "evidence_refs": evidence_refs,
                })
            else:
                bucket = raw.get("bucket")
                if bucket not in ("general", *TASK_LABELS):
                    raise EvolutionError(f"operation {index}: invalid bucket {bucket!r}")
                skill = validate_skill(raw.get("skill"), f"operation {index}/UPDATE")
                update_count += 1
                operations.append({
                    "operation": "UPDATE", "target_role": role,
                    "target_skill_id": target, "bucket": bucket,
                    "skill": skill, "evidence_refs": evidence_refs,
                })
        elif operation == "ADD":
            role = raw.get("role")
            bucket = raw.get("bucket")
            if role not in ROLES:
                raise EvolutionError(f"operation {index}: invalid ADD role {role!r}")
            if bucket not in ("general", *TASK_LABELS):
                raise EvolutionError(f"operation {index}: invalid bucket {bucket!r}")
            skill = validate_skill(raw.get("skill"), f"operation {index}/ADD")
            add_count += 1
            operations.append({
                "operation": "ADD", "role": role, "bucket": bucket,
                "skill": skill, "evidence_refs": evidence_refs,
            })
        else:
            raise EvolutionError(f"operation {index}: unsupported operation {operation!r}")
    if add_count > delete_count // 3:
        raise EvolutionError(f"3-delete/1-add violation: DELETE={delete_count}, ADD={add_count}")

    candidate = json.loads(json.dumps(parent["active_skillbanks"], ensure_ascii=False))
    deletes = {(row["target_role"], row["target_skill_id"]) for row in operations if row["operation"] == "DELETE"}
    updates = {(row["target_role"], row["target_skill_id"]): row for row in operations if row["operation"] == "UPDATE"}
    for role in ROLES:
        rebuilt = {"general": [], "task_specific": {label: [] for label in TASK_LABELS}}
        repository = parent["active_skillbanks"][role]
        for bucket, rows in (("general", repository["general"]), *repository["task_specific"].items()):
            for row in rows:
                key = (role, row["skill_id"])
                if key in deletes:
                    continue
                destination = bucket
                if key in updates:
                    patch = updates[key]
                    destination = patch["bucket"]
                    clean = {
                        "skill_id": row["skill_id"],
                        "version": int(row.get("version", 1)) + 1,
                        **patch["skill"],
                    }
                else:
                    clean = json.loads(json.dumps(row, ensure_ascii=False))
                (rebuilt["general"] if destination == "general" else rebuilt["task_specific"][destination]).append(clean)
        candidate[role] = rebuilt

    existing_ids = {
        role: {skill_id for candidate_role, skill_id in base if candidate_role == role}
        for role in ROLES
    }
    for row in operations:
        if row["operation"] != "ADD":
            continue
        role = row["role"]
        skill_id = _next_skill_id(existing_ids[role])
        clean = {"skill_id": skill_id, "version": 1, **row["skill"]}
        bucket = row["bucket"]
        (candidate[role]["general"] if bucket == "general" else candidate[role]["task_specific"][bucket]).append(clean)
        row["assigned_skill_id"] = skill_id

    counts_by_role: dict[str, int] = {}
    for role in ROLES:
        repository = candidate[role]
        all_rows = repository["general"] + sum((repository["task_specific"][label] for label in TASK_LABELS), [])
        counts_by_role[role] = len(all_rows)
        hashes = [object_hash(validate_skill(row, f"candidate/{role}/{row['skill_id']}")) for row in all_rows]
        if len(hashes) != len(set(hashes)):
            raise EvolutionError(f"candidate contains exact semantic duplicates in {role}")
    counts = {
        "base": len(base), "delete": delete_count, "update": update_count,
        "add": add_count, "candidate": sum(counts_by_role.values()),
    }
    if counts["candidate"] != counts["base"] - delete_count + add_count:
        raise EvolutionError("candidate count does not match patch arithmetic")
    return candidate, operations, counts, counts_by_role


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--parent-bank", type=Path, required=True)
    parser.add_argument("--generation", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--record-output", type=Path, required=True)
    parser.add_argument("--patch-output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--max-tokens", type=int, default=16000)
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--truncation-retries", type=int, default=2)
    parser.add_argument("--schema-attempts", type=int, default=3)
    parser.add_argument("--family-schema-attempts", type=int, default=3)
    parser.add_argument("--final-recovery-attempts", type=int, default=MAX_FINAL_PATCH_RECOVERY_ATTEMPTS)
    args = parser.parse_args()
    if args.truncation_retries not in range(0, 3):
        raise SystemExit("truncation-retries must be 0, 1, or 2")
    if args.final_recovery_attempts not in range(0, MAX_FINAL_PATCH_RECOVERY_ATTEMPTS + 1):
        raise SystemExit(
            f"final-recovery-attempts must be between 0 and {MAX_FINAL_PATCH_RECOVERY_ATTEMPTS}"
        )
    if args.generation not in range(2, 6):
        raise SystemExit("generation must be B2 through B5")
    if any(path.exists() for path in (args.output, args.record_output, args.patch_output)):
        raise SystemExit("refusing to overwrite frozen bank/record/patch output")

    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    parent = json.loads(args.parent_bank.read_text(encoding="utf-8"))
    episodes = list(evidence.get("episodes") or [])
    if evidence.get("client_id") != "A" or int(evidence.get("generation", -1)) != args.generation or len(episodes) != 134:
        raise SystemExit(f"complete Client A generation-{args.generation} evidence with 134 episodes is required")
    parse_bank(parent, "A")
    if int(parent.get("generation", -1)) != args.generation - 1:
        raise SystemExit(f"generation {args.generation} requires parent B{args.generation - 1}")
    if evidence.get("parent_bank_file_sha256") != file_hash(args.parent_bank):
        raise SystemExit("evidence parent-bank hash mismatch")
    allowed_refs = {row.get("evidence_ref") for row in episodes}
    if None in allowed_refs or len(allowed_refs) != 134:
        raise SystemExit("evidence must contain 134 unique evidence refs")

    config = _local_evolution_config()
    descriptor = config.descriptor()
    if config.model != "deepseek-flash" or descriptor.get("provider") != "deepseek_official" or descriptor.get("endpoint_origin") != "https://api.deepseek.com":
        raise SystemExit("DeepSeek official deepseek-flash Teacher is required")
    checkpoint_path = args.record_output.with_suffix(".checkpoint.json")
    identity = {
        "schema_version": "stage2_local_v9.client_a_patch_checkpoint.v1",
        "generation": args.generation,
        "evidence_file_sha256": file_hash(args.evidence),
        "parent_bank_file_sha256": file_hash(args.parent_bank),
        "teacher": descriptor,
        "policy": "whole_client_three_distinct_deletes_per_add",
    }
    checkpoint: dict[str, Any] = {**identity, "family_findings": {role: {} for role in ROLES}, "records": []}
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if any(checkpoint.get(key) != value for key, value in identity.items()):
            raise SystemExit("Teacher checkpoint identity mismatch")
    attempt_root = args.record_output.parent / f"B{args.generation}_teacher_attempts"
    attempt_root.mkdir(parents=True, exist_ok=True)

    for role in ROLES:
        for type_id, label in TASK_TYPE_LABELS.items():
            if label in checkpoint["family_findings"][role]:
                continue
            trajectories = [compact_episode(row, role) for row in episodes if int(row["task_type_id"]) == int(type_id)]
            prior_invalid = [
                record for record in checkpoint["records"]
                if record.get("stage") == "family_analysis_invalid" and record.get("role") == role and record.get("task_label") == label
            ]
            accepted = None
            role_repository = parent["active_skillbanks"][role]
            role_skill_ids = {
                row["skill_id"]
                for _, rows in (("general", role_repository["general"]), *role_repository["task_specific"].items())
                for row in rows
            }
            family_refs = {row["evidence_ref"] for row in trajectories}
            for invalid in reversed(prior_invalid):
                try:
                    previous_value = parse_json_object(invalid.get("raw_model_output", ""))
                    previous_value, normalization = normalize_known_json_mode_wrapper(previous_value, "findings")
                    if normalization is None:
                        continue
                    recovered = validate_family_findings(previous_value, family_refs, role_skill_ids)
                except (EvolutionError, json.JSONDecodeError, KeyError, TypeError):
                    continue
                source_record = {
                    "response_attempt_record": invalid["response_attempt_record"],
                }
                record_normalization_audit(source_record, normalization)
                accepted = recovered
                checkpoint["family_findings"][role][label] = accepted
                checkpoint["records"].append({
                    "stage": "family_analysis_recovered_from_checkpoint",
                    "role": role,
                    "task_label": label,
                    "source_invalid_attempt": invalid.get("attempt"),
                    "source_response_attempt_record": invalid["response_attempt_record"],
                    "normalization": normalization,
                    "normalization_audit_record": source_record["normalization_audit_record"],
                    "completed_at": now(),
                })
                write_json(checkpoint_path, checkpoint)
                break
            if accepted is not None:
                continue
            for attempt in range(len(prior_invalid) + 1, args.family_schema_attempts + 1):
                record = None
                prompt = {
                    "client": "A", "role": role, "role_boundary": ROLE_RULES[role],
                    "task_type": label, "trajectory_count": len(trajectories),
                    "trajectories": trajectories,
                    "parent_role_bank": parent["active_skillbanks"][role],
                    "hard_output_limits": {
                        "maximum_findings": 8,
                        "maximum_recommendation_characters": MAX_FINDING_RECOMMENDATION_CHARACTERS,
                        "maximum_affected_skill_ids_per_finding": MAX_FINDING_SKILL_IDS,
                        "maximum_evidence_refs_per_finding": MAX_FINDING_EVIDENCE_REFS,
                    },
                    "instruction": "Analyze all trajectories against this frozen role bank. Return at most 8 concise evidence-grounded findings for KEEP/UPDATE/DELETE/MOVE/ADD consideration. Do not emit the final patch. Every evidence ref must come from the supplied trajectories. Return exactly one JSON object whose only top-level key is findings. The API response_format type=json_object is a transport setting: do not copy type, schema, name, or any wrapper field into the response body. Obey every text and list limit.",
                    "output_schema": {"findings": [{"recommendation": "...", "affected_skill_ids": ["..."], "evidence_refs": ["..."]}]},
                }
                if prior_invalid:
                    prompt["previous_validation_error"] = prior_invalid[-1]["validation_error"]
                try:
                    value, record = call_json_recorded(
                        config,
                        [{"role": "system", "content": "You are a conservative role-bounded ALFWorld SkillBank evidence analyst. Always return one compact JSON object."}, {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}],
                        args,
                        attempt_root / f"family_{role.replace(' ', '_')}_task_{int(type_id):02d}_schema_{attempt:02d}",
                    )
                    value, normalization = normalize_known_json_mode_wrapper(value, "findings")
                    if normalization is not None:
                        record_normalization_audit(record, normalization)
                    accepted = validate_family_findings(value, family_refs, role_skill_ids)
                    checkpoint["family_findings"][role][label] = accepted
                    checkpoint["records"].append({"stage": "family_analysis", "role": role, "task_label": label, "attempt": attempt, **record})
                    write_json(checkpoint_path, checkpoint)
                    break
                except TeacherResponseBudgetError:
                    raise
                except EvolutionError as exc:
                    invalid = {"stage": "family_analysis_invalid", "role": role, "task_label": label, "attempt": attempt, "validation_error": str(exc)}
                    if record is not None:
                        invalid.update(record)
                    checkpoint["records"].append(invalid)
                    prior_invalid.append(invalid)
                    write_json(checkpoint_path, checkpoint)
            if accepted is None:
                raise EvolutionError(f"family analysis repair exhausted for {role}/{label}")

    accepted_candidate = accepted_operations = accepted_counts = accepted_role_counts = None
    target_allowlist = allowed_target_ids_by_role(parent)
    prior_rejected = [
        record for record in checkpoint["records"] if record.get("stage") == "final_patch_rejected"
    ]
    prior_errors: list[str] = list(prior_rejected[-1].get("validation_errors") or []) if prior_rejected else []
    # D-115 supersedes monolithic final synthesis. Keep this legacy block for
    # audit readability, but never execute it for new or resumed generations.
    for attempt in range(1, 1):
        record = None
        prompt = {
            "client": "A", "generation": args.generation,
            "parent_bank": parent["active_skillbanks"],
            "allowed_target_ids_by_role": target_allowlist,
            "role_boundaries": ROLE_RULES,
            "family_findings": checkpoint["family_findings"],
            "hard_policy": {
                "quota_scope": "one shared quota across Planner, Executor, General, and all six task buckets",
                "add_lte_floor_distinct_delete_div_3": True,
                "update_neither_consumes_nor_creates_quota": True,
                "update_may_move_bucket_only_within_the_same_role": True,
                "merge_encoding": "UPDATE one surviving target plus DELETE each absorbed target",
                "no_fixed_role_or_total_capacity": True,
            },
            "instruction": "Return the complete net patch only. For every DELETE or UPDATE, the exact (target_role, target_skill_id) pair must occur in allowed_target_ids_by_role; skill IDs are role-local and the same text under another role is not a valid target. ADD must name role and bucket. Do not emit KEEP/NONE/MERGE. Prefer UPDATE or DELETE over speculative ADD. Preserve role boundaries and ground every operation in supplied evidence. Return exactly one JSON object whose only top-level key is operations. The API response_format type=json_object is a transport setting: do not copy type, schema, name, or any wrapper field into the response body.",
            "operation_schema": {"operations": [
                {"operation": "DELETE", "target_role": "Planner|Executor", "target_skill_id": "existing ID", "evidence_refs": ["..."]},
                {"operation": "UPDATE", "target_role": "Planner|Executor", "target_skill_id": "existing ID", "bucket": "general or one Chinese task label", "skill": "one valid skill object", "evidence_refs": ["..."]},
                {"operation": "ADD", "role": "Planner|Executor", "bucket": "general or one Chinese task label", "skill": "one valid skill object", "evidence_refs": ["..."]},
            ]},
            "previous_validation_errors": prior_errors,
        }
        try:
            value, record = call_json_recorded(
                config,
                [{"role": "system", "content": "You are the final conservative Client A SkillBank patch composer. Obey the whole-client 3-delete/1-add quota exactly. Always return one compact JSON object."}, {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}],
                args,
                attempt_root / f"final_patch_schema_{attempt:02d}",
            )
            value, normalization = normalize_known_json_mode_wrapper(value, "operations")
            if normalization is not None:
                record_normalization_audit(record, normalization)
            attempt_path = args.record_output.parent / f"B{args.generation}_patch_attempt_{attempt:02d}.json"
            if attempt_path.exists():
                raise EvolutionError(f"refusing to overwrite frozen final patch attempt: {attempt_path}")
            write_json(attempt_path, {"attempt": attempt, **record})
            accepted_candidate, accepted_operations, accepted_counts, accepted_role_counts = validate_and_apply_patch(
                value, parent, allowed_refs, args.generation
            )
            checkpoint["records"].append({"stage": "final_patch", "attempt": attempt, "counts": accepted_counts, "counts_by_role": accepted_role_counts, **record})
            break
        except TeacherResponseBudgetError:
            raise
        except EvolutionError as exc:
            prior_errors = [str(exc)]
            rejected = {"stage": "final_patch_rejected", "attempt": attempt, "validation_errors": prior_errors}
            if record is not None:
                rejected.update(record)
            checkpoint["records"].append(rejected)
            write_json(checkpoint_path, checkpoint)

    # A failed run may be resumed after the standard attempts are frozen. Recovery is
    # deliberately limited to final synthesis: family findings and the old responses
    # remain byte-for-byte unchanged, while the prompt exposes the current role-scoped
    # allowlist and labels any stale role/ID pairs as forbidden historical output.
    if False and accepted_candidate is None and len(prior_rejected) >= args.schema_attempts and args.final_recovery_attempts:
        latest_attempt_path = args.record_output.parent / f"B{args.generation}_patch_attempt_{args.schema_attempts:02d}.json"
        if not latest_attempt_path.exists():
            raise EvolutionError(f"missing frozen final patch attempt for bounded recovery: {latest_attempt_path}")
        latest_attempt = json.loads(latest_attempt_path.read_text(encoding="utf-8"))
        latest_value = parse_json_object(latest_attempt.get("raw_model_output", ""))
        latest_value, _ = normalize_known_json_mode_wrapper(latest_value, "operations")
        forbidden_pairs = unknown_target_pairs(latest_value, parent)
        existing_recoveries = [
            record for record in checkpoint["records"]
            if record.get("stage") in {"final_patch_recovery", "final_patch_recovery_rejected"}
        ]
        recovery_errors = list(prior_errors)
        for recovery_attempt in range(len(existing_recoveries) + 1, args.final_recovery_attempts + 1):
            record = None
            recovery_prompt = {
                "client": "A",
                "generation": args.generation,
                "recovery_scope": "final patch synthesis only; do not redo family analysis",
                "parent_bank": parent["active_skillbanks"],
                "allowed_target_ids_by_role": target_allowlist,
                "forbidden_historical_target_pairs": forbidden_pairs,
                "role_boundaries": ROLE_RULES,
                "family_findings": checkpoint["family_findings"],
                "hard_policy": {
                    "quota_scope": "one shared quota across Planner, Executor, General, and all six task buckets",
                    "add_lte_floor_distinct_delete_div_3": True,
                    "update_neither_consumes_nor_creates_quota": True,
                    "update_may_move_bucket_only_within_the_same_role": True,
                    "merge_encoding": "UPDATE one surviving target plus DELETE each absorbed target",
                    "no_fixed_role_or_total_capacity": True,
                },
                "previous_validation_errors": recovery_errors,
                "instruction": "Generate a fresh complete net patch from the frozen findings. Do not copy any forbidden historical target pair. Every DELETE or UPDATE must use an exact role/ID pair from allowed_target_ids_by_role; IDs are role-local. Enforce ADD <= floor(distinct DELETE / 3). ADD must name role and bucket. Do not emit KEEP/NONE/MERGE. Return exactly one JSON object whose only top-level key is operations. The API response_format type=json_object is a transport setting: do not copy wrapper fields into the body.",
                "operation_schema": {"operations": [
                    {"operation": "DELETE", "target_role": "Planner|Executor", "target_skill_id": "current role-scoped ID", "evidence_refs": ["..."]},
                    {"operation": "UPDATE", "target_role": "Planner|Executor", "target_skill_id": "current role-scoped ID", "bucket": "general or one Chinese task label", "skill": "one valid skill object", "evidence_refs": ["..."]},
                    {"operation": "ADD", "role": "Planner|Executor", "bucket": "general or one Chinese task label", "skill": "one valid skill object", "evidence_refs": ["..."]},
                ]},
            }
            try:
                value, record = call_json_recorded(
                    config,
                    [{"role": "system", "content": "You repair only the final Client A SkillBank patch using the current role-scoped target allowlist. Always return one compact JSON object."}, {"role": "user", "content": json.dumps(recovery_prompt, ensure_ascii=False)}],
                    args,
                    attempt_root / f"final_patch_recovery_{recovery_attempt:02d}",
                )
                value, normalization = normalize_known_json_mode_wrapper(value, "operations")
                if normalization is not None:
                    record_normalization_audit(record, normalization)
                recovery_path = args.record_output.parent / f"B{args.generation}_patch_recovery_attempt_{recovery_attempt:02d}.json"
                if recovery_path.exists():
                    raise EvolutionError(f"refusing to overwrite frozen final patch recovery attempt: {recovery_path}")
                write_json(recovery_path, {
                    "recovery_attempt": recovery_attempt,
                    "source_frozen_patch_attempt": str(latest_attempt_path),
                    "source_frozen_patch_attempt_file_sha256": file_hash(latest_attempt_path),
                    "allowed_target_ids_by_role": target_allowlist,
                    "forbidden_historical_target_pairs": forbidden_pairs,
                    **record,
                })
                accepted_candidate, accepted_operations, accepted_counts, accepted_role_counts = validate_and_apply_patch(
                    value, parent, allowed_refs, args.generation
                )
                checkpoint["records"].append({
                    "stage": "final_patch_recovery",
                    "recovery_attempt": recovery_attempt,
                    "counts": accepted_counts,
                    "counts_by_role": accepted_role_counts,
                    "source_frozen_patch_attempt": str(latest_attempt_path),
                    "forbidden_historical_target_pairs": forbidden_pairs,
                    **record,
                })
                write_json(checkpoint_path, checkpoint)
                break
            except TeacherResponseBudgetError:
                raise
            except EvolutionError as exc:
                recovery_errors = [str(exc)]
                rejected = {
                    "stage": "final_patch_recovery_rejected",
                    "recovery_attempt": recovery_attempt,
                    "validation_errors": recovery_errors,
                    "source_frozen_patch_attempt": str(latest_attempt_path),
                    "forbidden_historical_target_pairs": forbidden_pairs,
                }
                if record is not None:
                    rejected.update(record)
                checkpoint["records"].append(rejected)
                write_json(checkpoint_path, checkpoint)
    # D-115 split synthesis. Stage one freezes DELETE/UPDATE after role-local
    # validation. Code then computes the only ADD budget exposed to stage two.
    split_state = checkpoint.setdefault("split_final", {})
    base_operations = split_state.get("base_operations")
    base_counts = split_state.get("base_counts")
    if base_operations is not None:
        _, checked_operations, checked_counts, _ = validate_delete_update_stage(
            {"operations": base_operations}, parent, allowed_refs, args.generation
        )
        if checked_operations != base_operations or checked_counts != base_counts:
            raise EvolutionError("frozen split-base checkpoint failed deterministic revalidation")
    else:
        rejected_base = [r for r in checkpoint["records"] if r.get("stage") == "split_final_base_rejected"]
        base_errors = list(rejected_base[-1].get("validation_errors") or []) if rejected_base else []
        for attempt in range(len(rejected_base) + 1, args.schema_attempts + 1):
            record = None
            prompt = {
                "client": "A", "generation": args.generation, "stage": "DELETE_UPDATE_ONLY",
                "parent_bank": parent["active_skillbanks"],
                "allowed_target_ids_by_role": target_allowlist,
                "role_boundaries": ROLE_RULES,
                "family_findings": checkpoint["family_findings"],
                "hard_policy": {
                    "allowed_operations": ["DELETE", "UPDATE"],
                    "forbid_add_in_this_stage": True,
                    "target_pairs_must_match_the_exact_role_allowlist": True,
                    "each_target_may_be_modified_at_most_once": True,
                    "update_may_move_bucket_only_within_the_same_role": True,
                },
                "previous_validation_errors": base_errors,
                "instruction": "Return only DELETE/UPDATE operations. Do not emit ADD, KEEP, NONE, or MERGE. Every (target_role,target_skill_id) pair must occur in that exact role's allowlist. Ground every operation in supplied evidence. Return exactly one JSON object whose only top-level key is operations.",
                "operation_schema": {"operations": [
                    {"operation": "DELETE", "target_role": "Planner|Executor", "target_skill_id": "ID from that role", "evidence_refs": ["..."]},
                    {"operation": "UPDATE", "target_role": "Planner|Executor", "target_skill_id": "ID from that role", "bucket": "general or task label", "skill": "valid skill", "evidence_refs": ["..."]},
                ]},
            }
            try:
                value, record = call_json_recorded(
                    config,
                    [{"role": "system", "content": "Compose stage one of the Client A patch: DELETE and UPDATE only, using exact role-local IDs."},
                     {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}],
                    args, attempt_root / f"split_base_schema_{attempt:02d}",
                )
                value, normalization = normalize_known_json_mode_wrapper(value, "operations")
                if normalization is not None:
                    record_normalization_audit(record, normalization)
                attempt_path = args.record_output.parent / f"B{args.generation}_patch_split_base_attempt_{attempt:02d}.json"
                if attempt_path.exists():
                    raise EvolutionError(f"refusing to overwrite frozen split-base attempt: {attempt_path}")
                write_json(attempt_path, {"attempt": attempt, "stage": "DELETE_UPDATE_ONLY", **record})
                _, base_operations, base_counts, base_role_counts = validate_delete_update_stage(
                    value, parent, allowed_refs, args.generation
                )
                split_state.update({
                    "base_operations": base_operations, "base_counts": base_counts,
                    "base_counts_by_role": base_role_counts, "base_accepted_attempt": attempt,
                    "base_attempt_file": str(attempt_path),
                    "base_attempt_file_sha256": file_hash(attempt_path),
                    "max_add": base_counts["delete"] // 3,
                })
                checkpoint["records"].append({"stage": "split_final_base", "attempt": attempt, "counts": base_counts, "counts_by_role": base_role_counts, "max_add": split_state["max_add"], **record})
                write_json(checkpoint_path, checkpoint)
                break
            except TeacherResponseBudgetError:
                raise
            except EvolutionError as exc:
                base_errors = [str(exc)]
                rejected = {"stage": "split_final_base_rejected", "attempt": attempt, "validation_errors": base_errors}
                if record is not None:
                    rejected.update(record)
                checkpoint["records"].append(rejected)
                write_json(checkpoint_path, checkpoint)
        if base_operations is None:
            raise EvolutionError(f"split DELETE/UPDATE stage exhausted: {base_errors}")

    max_add = int(split_state["max_add"])
    if max_add == 0:
        accepted_candidate, accepted_operations, accepted_counts, accepted_role_counts = validate_and_apply_patch(
            {"operations": base_operations}, parent, allowed_refs, args.generation
        )
        checkpoint["records"].append({"stage": "split_final_add_skipped", "max_add": 0, "counts": accepted_counts, "counts_by_role": accepted_role_counts, "completed_at": now()})
        write_json(checkpoint_path, checkpoint)
    else:
        rejected_add = [r for r in checkpoint["records"] if r.get("stage") == "split_final_add_rejected"]
        add_errors = list(rejected_add[-1].get("validation_errors") or []) if rejected_add else []
        for attempt in range(len(rejected_add) + 1, args.schema_attempts + 1):
            record = None
            prompt = {
                "client": "A", "generation": args.generation, "stage": "ADD_ONLY",
                "program_computed_max_add": max_add,
                "accepted_delete_update_operations": base_operations,
                "family_findings": checkpoint["family_findings"],
                "role_boundaries": ROLE_RULES,
                "hard_policy": {"allowed_operations": ["ADD"], "maximum_add_operations": max_add, "zero_add_operations_are_allowed": True},
                "previous_validation_errors": add_errors,
                "instruction": f"Return zero to {max_add} evidence-grounded ADD operations only. The DELETE/UPDATE stage is frozen; do not repeat or alter it. Prefer an empty list over speculative ADD. Return exactly one JSON object whose only top-level key is operations.",
                "operation_schema": {"operations": [{"operation": "ADD", "role": "Planner|Executor", "bucket": "general or task label", "skill": "valid skill", "evidence_refs": ["..."]}]},
            }
            try:
                value, record = call_json_recorded(
                    config,
                    [{"role": "system", "content": f"Compose stage two of the Client A patch: at most {max_add} ADD operations and no other operation type."},
                     {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}],
                    args, attempt_root / f"split_add_schema_{attempt:02d}",
                )
                value, normalization = normalize_known_json_mode_wrapper(value, "operations")
                if normalization is not None:
                    record_normalization_audit(record, normalization)
                attempt_path = args.record_output.parent / f"B{args.generation}_patch_split_add_attempt_{attempt:02d}.json"
                if attempt_path.exists():
                    raise EvolutionError(f"refusing to overwrite frozen split-add attempt: {attempt_path}")
                write_json(attempt_path, {"attempt": attempt, "stage": "ADD_ONLY", "program_computed_max_add": max_add, **record})
                combined = combine_split_patch(base_operations, value, max_add)
                accepted_candidate, accepted_operations, accepted_counts, accepted_role_counts = validate_and_apply_patch(
                    combined, parent, allowed_refs, args.generation
                )
                split_state.update({"add_accepted_attempt": attempt, "add_attempt_file": str(attempt_path), "add_attempt_file_sha256": file_hash(attempt_path), "final_counts": accepted_counts})
                checkpoint["records"].append({"stage": "split_final_add", "attempt": attempt, "max_add": max_add, "counts": accepted_counts, "counts_by_role": accepted_role_counts, **record})
                write_json(checkpoint_path, checkpoint)
                break
            except TeacherResponseBudgetError:
                raise
            except EvolutionError as exc:
                add_errors = [str(exc)]
                rejected = {"stage": "split_final_add_rejected", "attempt": attempt, "max_add": max_add, "validation_errors": add_errors}
                if record is not None:
                    rejected.update(record)
                checkpoint["records"].append(rejected)
                write_json(checkpoint_path, checkpoint)
        if accepted_candidate is None:
            raise EvolutionError(f"split ADD stage exhausted: {add_errors}")

    bank = {
        "bank_schema_version": "patchFL.role_repository.v3",
        "experiment_id": "stage2-local-v9-client-a-b1-patch3-evolution",
        "source_client": "A", "target_client": "A",
        "generation": args.generation, "parent_bank": f"B{args.generation - 1}",
        "parent_bank_file_sha256": file_hash(args.parent_bank),
        "parent_live_repository_sha256": parent.get("live_repository_sha256"),
        "teacher_model": config.model, "teacher_endpoint": descriptor,
        "maximum_skill_field_characters": MAX_FIELD_CHARACTERS,
        "capacity_policy": {
            "policy": "whole_client_three_distinct_deletes_per_add",
            "base_count": accepted_counts["base"], "delete_count": accepted_counts["delete"],
            "update_count": accepted_counts["update"], "add_count": accepted_counts["add"],
            "candidate_count": accepted_counts["candidate"],
            "quota_passed": accepted_counts["add"] <= accepted_counts["delete"] // 3,
            "counts_by_role": accepted_role_counts,
        },
        "active_skillbanks": accepted_candidate,
        "evidence_file_sha256": file_hash(args.evidence),
    }
    bank["live_repository_sha256"] = "sha256:" + hashlib.sha256(canonical_bytes(bank["active_skillbanks"])).hexdigest()
    parse_bank(bank, "A")
    write_json(args.output, bank)
    patch = {
        "schema_version": "stage2_local_v9.client_a_net_patch.v1",
        "client": "A", "round_index": args.generation,
        "base_bank_file_sha256": file_hash(args.parent_bank),
        "counts": accepted_counts, "counts_by_role": accepted_role_counts,
        "operations": accepted_operations,
        "candidate_live_repository_sha256": bank["live_repository_sha256"],
    }
    write_json(args.patch_output, patch)
    write_json(args.record_output, {
        "schema_version": 1, **identity,
        "capacity_policy": bank["capacity_policy"],
        "patch_file_sha256": file_hash(args.patch_output),
        "bank_file_sha256": file_hash(args.output),
        "records": checkpoint["records"],
    })
    write_json(checkpoint_path, checkpoint)
    print(json.dumps({"status": "complete", "generation": args.generation, "counts": accepted_counts, "counts_by_role": accepted_role_counts}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
