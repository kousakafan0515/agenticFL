"""Create one Client-A SkillBank generation from the complete 134-task evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

from stage2_local_v12.clients.skillbank_loader import EXPECTED_ROLES, SKILL_FIELDS, TASK_TYPE_LABELS, parse_bank
from stage2_local_v12.runtime.banks import canonical_bytes, file_hash, write_json
from stage2_local_v12.evolution.teacher_api import _local_evolution_config
from stage2_local_v12.evolution.capacity_policy import (
    enforce_role_capacity, resolve_b1_capacity_policy, role_capacity_context, role_skill_count,
)


ROOT = Path(__file__).resolve().parents[2]
ROLES = EXPECTED_ROLES["A"]
ROLE_RULES = {
    "Planner": "Only learn goal decomposition, subtask ordering, and plan repair. Never assign environment actions to Planner.",
    "Executor": "Only learn local execution, observation-based decisions, exact ALFWorld action forms, and recovery inside the assigned subtask.",
}
MAX_SKILL_FIELD_CHARACTERS = 900
SCHEMA_REPAIR_TARGET_CHARACTERS = 760
MAX_SCHEMA_REPAIR_ATTEMPTS = 4


def json_object(raw: str) -> dict[str, Any]:
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
        raise ValueError("Teacher output is not a JSON object")
    return value


def compact_episode(episode: dict[str, Any], role: str) -> dict[str, Any]:
    events = list(episode.get("environment_events") or [])
    if episode.get("success"):
        selected = events
    else:
        informative = [row for row in events if any(token in str(row.get("observation", "")).casefold() for token in (
            "can't", "cannot", "nothing happens", "closed", "not holding", "invalid", "not a valid", "already",
        ))]
        selected = (events[:4] + informative + events[-6:])
    deduped, seen = [], set()
    for row in selected:
        key = (row.get("step"), row.get("action"), row.get("observation"))
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    role_rows = list((episode.get("role_evidence") or {}).get(role) or [])
    if role == "Planner":
        role_rows = role_rows[:2]
    else:
        role_rows = role_rows[:4] + role_rows[-4:]
    return {
        "evidence_ref": episode.get("evidence_ref"),
        "goal": episode.get("goal"),
        "success": episode.get("success"),
        "terminal_reason": episode.get("terminal_reason"),
        "environment_events": deduped,
        "role_evidence": role_rows,
    }


def call_json(config: Any, messages: list[dict[str, str]], args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any]]:
    errors = []
    for repair in range(3):
        recoverable = (APITimeoutError, APIConnectionError, InternalServerError, RateLimitError)
        for transport_attempt in range(args.retries + 1):
            try:
                response = config.client(timeout=args.timeout).chat.completions.create(
                    model=config.model, messages=messages, temperature=0,
                    seed=args.seed + repair, max_tokens=args.max_tokens, stream=False,
                    extra_body={"thinking": {"type": "disabled"}},
                )
                if getattr(response, "model", None) != config.model:
                    raise RuntimeError(f"response model drift: {getattr(response, 'model', None)}")
                if not response.choices or getattr(response.choices[0], "finish_reason", None) == "length":
                    raise RuntimeError("Teacher response missing or truncated")
                message = response.choices[0].message
                raw = message.content or ""
                reasoning = getattr(message, "reasoning_content", None) or ""
                usage_obj = getattr(response, "usage", None)
                usage = {
                    "prompt_tokens": getattr(usage_obj, "prompt_tokens", None),
                    "completion_tokens": getattr(usage_obj, "completion_tokens", None),
                    "total_tokens": getattr(usage_obj, "total_tokens", None),
                    "transport_attempts": transport_attempt + 1,
                    "requested_model": config.model,
                    "response_model": getattr(response, "model", None),
                    "thinking": False,
                }
                break
            except recoverable:
                if transport_attempt == args.retries:
                    raise
                time.sleep(min(2 ** (transport_attempt + 1), 15))
        try:
            return json_object(raw), {"raw_model_output": raw, "model_reasoning": reasoning, "usage": usage, "format_attempt": repair + 1}
        except (ValueError, json.JSONDecodeError) as exc:
            errors.append(str(exc))
            messages = messages + [{"role": "assistant", "content": raw}, {"role": "user", "content": "Return only one valid JSON object matching the requested schema. No markdown or explanation."}]
    raise RuntimeError("Teacher returned invalid JSON after repairs: " + "; ".join(errors))


def validate_skill(skill: Any) -> dict[str, str]:
    if not isinstance(skill, dict):
        raise ValueError("skill must be an object")
    skill_type = skill.get("type")
    if skill_type in {"Procedure", "Local Strategy", "Procedure / Local Strategy"}:
        skill_type = "Procedure or Local Strategy"
    fields = SKILL_FIELDS.get(skill_type)
    if fields is None or any(field not in skill for field in fields):
        raise ValueError("skill has invalid type or fields")
    result = {"type": skill_type}
    for field in fields:
        value = skill.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > MAX_SKILL_FIELD_CHARACTERS:
            raise ValueError(f"invalid skill field {field}")
        result[field] = value.strip()
    return result


def merged_bank_validation_errors(value: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    rows_by_scope = [("general", None, value.get("general"))]
    rows_by_scope.extend(
        ("task_specific", label, (value.get("task_specific") or {}).get(label))
        for label in TASK_TYPE_LABELS.values()
    )
    for scope, label, rows in rows_by_scope:
        if not isinstance(rows, list):
            errors.append({"scope": scope, "task_label": label, "error": "skill collection is not a list"})
            continue
        for index, skill in enumerate(rows):
            try:
                validate_skill(skill)
            except ValueError as exc:
                errors.append({"scope": scope, "task_label": label, "index": index, "error": str(exc)})
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--parent-bank", type=Path, required=True)
    parser.add_argument("--generation", type=int, required=True)
    parser.add_argument("--teacher-model", required=True)
    parser.add_argument("--teacher-provider", choices=("deepseek_official",), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--record-output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--max-tokens", type=int, default=8000)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()
    if args.generation < 1:
        raise SystemExit("v9 evolver requires generation >= 1")
    if args.output.exists() or args.record_output.exists():
        raise SystemExit("refusing to overwrite a frozen Teacher output")
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    episodes = list(evidence.get("episodes") or [])
    if evidence.get("client_id") != "A" or int(evidence.get("generation", -1)) != args.generation or len(episodes) != 134:
        raise SystemExit(f"Teacher requires complete Client A generation-{args.generation} evidence with 134 episodes")
    parent_bank = json.loads(args.parent_bank.read_text(encoding="utf-8"))
    parse_bank(parent_bank, "A")
    if int(parent_bank.get("generation", -1)) != args.generation - 1:
        raise SystemExit(f"generation {args.generation} requires parent B{args.generation - 1}")
    if args.generation > 1 and evidence.get("parent_bank_file_sha256") != file_hash(args.parent_bank):
        raise SystemExit("evidence parent-bank file hash mismatch")
    config = _local_evolution_config()
    teacher_descriptor = config.descriptor()
    if config.model != args.teacher_model:
        raise SystemExit(f"Teacher requires {args.teacher_model}, got {config.model}")
    if teacher_descriptor.get("provider") != args.teacher_provider:
        raise SystemExit(f"Teacher requires {args.teacher_provider}, got {teacher_descriptor.get('provider')}")

    evidence_hash = file_hash(args.evidence)
    parent_bank_hash = file_hash(args.parent_bank)
    capacity_policy = resolve_b1_capacity_policy(
        parent_bank, args.generation, ROLES, parent_bank_hash
    )
    checkpoint_path = args.record_output.with_suffix(".checkpoint.json")
    records: list[dict[str, Any]] = []
    candidates: dict[str, dict[str, list[dict[str, Any]]]] = {role: {} for role in ROLES}
    merged_values: dict[str, dict[str, Any]] = {}
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if (
            checkpoint.get("evidence_file_sha256") != evidence_hash
            or checkpoint.get("parent_bank_file_sha256") != parent_bank_hash
            or checkpoint.get("generation") != args.generation
            or checkpoint.get("teacher_model") != config.model
            or checkpoint.get("teacher_endpoint") != teacher_descriptor
            or checkpoint.get("capacity_policy") != capacity_policy
        ):
            raise SystemExit("Teacher checkpoint identity mismatch")
        candidates = checkpoint.get("candidates") or candidates
        merged_values = checkpoint.get("merged_values") or {}
        records = checkpoint.get("records") or []

    def save_checkpoint() -> None:
        write_json(checkpoint_path, {
            "schema_version": 1, "evidence_file_sha256": evidence_hash,
            "parent_bank_file_sha256": parent_bank_hash, "generation": args.generation,
            "teacher_model": config.model, "teacher_endpoint": teacher_descriptor,
            "maximum_skill_field_characters": MAX_SKILL_FIELD_CHARACTERS,
            "capacity_policy": capacity_policy,
            "candidates": candidates,
            "merged_values": merged_values, "records": records,
        })

    for role in ROLES:
        for type_id, label in TASK_TYPE_LABELS.items():
            if label in candidates.get(role, {}):
                continue
            rows = [compact_episode(row, role) for row in episodes if int(row["task_type_id"]) == type_id]
            prompt = {
                "client": "A", "role": role, "role_boundary": ROLE_RULES[role],
                "parent_role_bank": parent_bank["active_skillbanks"][role],
                "task_type": label, "trajectory_count": len(rows), "trajectories": rows,
                "instruction": "B0 is empty. Propose 0-4 evidence-grounded ADD candidates only. There are no parent skills to retain, update, delete or merge. The later full-bank synthesis may deduplicate overlapping ADD ideas. Do not copy object instance IDs. Return JSON only.",
                "output_schema": {"candidates": [{"action": "ADD", "source_skill_ids": ["existing IDs when applicable"], "scope": "general or task_specific", "type": "Procedure or Local Strategy | Failure Lesson", "title/principle/when_to_apply OR description/why_it_happens/how_to_avoid": "required for non-DELETE actions", "evidence_refs": ["refs"]}]},
            }
            value, record = call_json(config, [{"role": "system", "content": "You are a conservative ALFWorld SkillBank evidence analyst."}, {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}], args)
            rows_out = value.get("candidates")
            if not isinstance(rows_out, list) or len(rows_out) > 4:
                validation_error = (
                    f"candidates must be a list, got {type(rows_out).__name__}"
                    if not isinstance(rows_out, list)
                    else f"candidates must contain at most 4 entries, got {len(rows_out)}"
                )
                records.append({
                    "stage": "family_analysis_invalid",
                    "role": role,
                    "task_type_id": type_id,
                    "task_label": label,
                    "validation_error": validation_error,
                    "candidate_container_type": type(rows_out).__name__,
                    "candidate_count": len(rows_out) if isinstance(rows_out, list) else None,
                    **record,
                })
                save_checkpoint()
                raise RuntimeError(f"invalid candidate list for {role}/{label}: {validation_error}")
            if any(not isinstance(row, dict) or row.get('action') != 'ADD' or row.get('source_skill_ids') not in (None, []) for row in rows_out):
                raise RuntimeError(f'B0 candidate must be ADD with no parent IDs: {role}/{label}')
            candidates[role][label] = rows_out
            records.append({"stage": "family_analysis", "role": role, "task_type_id": type_id, "task_label": label, **record})
            save_checkpoint()

    bank = {
        "bank_schema_version": "patchFL.role_repository.v3",
        "experiment_id": evidence["experiment_id"], "source_client": "A", "target_client": "A",
        "generation": args.generation, "parent_bank": f"B{args.generation - 1}",
        "parent_bank_file_sha256": parent_bank_hash,
        "parent_live_repository_sha256": parent_bank.get("live_repository_sha256"),
        "teacher_model": config.model,
        "teacher_endpoint": teacher_descriptor,
        "maximum_skill_field_characters": MAX_SKILL_FIELD_CHARACTERS,
        "active_skillbanks": {},
    }
    if capacity_policy is not None:
        bank["capacity_policy"] = capacity_policy
    for role in ROLES:
        capacity_context = role_capacity_context(
            capacity_policy, role, parent_bank["active_skillbanks"][role]
        )
        if capacity_context is None:
            capacity_instruction = (
                "B1 is the open-ended bootstrap generation: it has no fixed total skill "
                "capacity. Keep every distinct evidence-grounded skill while deduplicating overlaps."
            )
            role_capacity = None
        else:
            role_capacity = capacity_context["maximum_total_skills"]
            capacity_instruction = (
                f"This role has a fixed B1-derived capacity of {role_capacity} skills. "
                f"The parent contains {capacity_context['parent_skill_count']} skills, leaving "
                f"{capacity_context['available_add_slots']} direct ADD slots. ADD is allowed "
                "without deletion while the complete returned bank stays within the fixed capacity. "
                "At capacity, DELETE or MERGE existing content before ADD. Never borrow capacity "
                "from another role and never exceed the fixed capacity."
            )
        if role not in merged_values:
            prompt = {
                "client": "A", "role": role, "role_boundary": ROLE_RULES[role],
                "parent_role_bank": parent_bank["active_skillbanks"][role],
                "family_candidates": candidates[role],
                "instruction": "Construct the complete next-generation role bank by jointly applying the six-family evidence to the frozen parent role bank. The parent B0 bank is empty. Construct new skills only from evidence-grounded ADD candidates. Deduplicate and synthesize overlapping candidate ideas; do not retain, update, delete, or merge an old skill. General must transfer across task families; otherwise place it under exactly one task-specific Chinese label. " + capacity_instruction + " Return the complete bank, not a patch. Return JSON only; do not assign IDs. The only allowed type strings are 'Procedure or Local Strategy' and 'Failure Lesson'.",
                "capacity_policy": capacity_context,
                "allowed_task_labels": list(TASK_TYPE_LABELS.values()),
                "output_schema": {"general": [{"type": "...", "required skill fields": "..."}], "task_specific": {label: [{"type": "...", "required skill fields": "..."}] for label in TASK_TYPE_LABELS.values()}},
            }
            value, record = call_json(config, [{"role": "system", "content": "You are the final conservative ALFWorld SkillBank merger."}, {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}], args)
            merged_values[role] = value
            records.append({"stage": "final_merge", "role": role, **record})
            save_checkpoint()
        value = merged_values[role]
        if set(value) != {"general", "task_specific"} or set(value.get("task_specific", {})) != set(TASK_TYPE_LABELS.values()):
            raise RuntimeError(f"invalid merged bank shape for {role}")
        if role_capacity is not None:
            prior_b1_capacity_repairs = sum(
                1 for row in records
                if row.get("stage") == "b1_capacity_repair" and row.get("role") == role
            )
            for capacity_repair_index in range(prior_b1_capacity_repairs, 2):
                skill_count = role_skill_count(value)
                if skill_count <= role_capacity:
                    break
                repair_prompt = {
                    "client": "A", "role": role, "role_boundary": ROLE_RULES[role],
                    "current_merged_bank": value,
                    "maximum_total_skills": role_capacity,
                    "current_skill_count": skill_count,
                    "instruction": "The complete role bank exceeds its fixed B1-derived capacity. Remove or merge the least useful overlapping content until the total is at most the stated maximum. Do not add new claims. Preserve the exact top-level shape and all six task-specific labels. Return JSON only; do not assign IDs.",
                }
                value, capacity_repair_record = call_json(
                    config,
                    [{"role": "system", "content": "You are repairing a B1-derived capacity violation without mechanical trimming."}, {"role": "user", "content": json.dumps(repair_prompt, ensure_ascii=False)}],
                    args,
                )
                if set(value) != {"general", "task_specific"} or set(value.get("task_specific", {})) != set(TASK_TYPE_LABELS.values()):
                    raise RuntimeError(f"invalid B1-capacity-repaired bank shape for {role}")
                merged_values[role] = value
                records.append({
                    "stage": "b1_capacity_repair", "role": role,
                    "repair_index": capacity_repair_index + 1,
                    "maximum_total_skills": role_capacity,
                    "previous_skill_count": skill_count,
                    **capacity_repair_record,
                })
                save_checkpoint()
            enforce_role_capacity(value, role, capacity_policy)
        prior_schema_repairs = sum(
            1 for row in records
            if row.get("stage") == "schema_repair"
            and row.get("role") == role
            and row.get("maximum_field_characters") == MAX_SKILL_FIELD_CHARACTERS
        )
        for repair_index in range(prior_schema_repairs, MAX_SCHEMA_REPAIR_ATTEMPTS):
            validation_errors = merged_bank_validation_errors(value)
            if not validation_errors:
                break
            list_lengths = {
                "general": len(value["general"]),
                **{label: len(value["task_specific"][label]) for label in TASK_TYPE_LABELS.values()},
            }
            repair_prompt = {
                "client": "A", "role": role, "role_boundary": ROLE_RULES[role],
                "current_merged_bank": value,
                "validation_errors": validation_errors,
                "instruction": f"Repair only the listed schema violations. Preserve every skill's meaning, list membership, list order, and the exact number of entries in every list. Do not add, delete, merge, or reorder skills and do not introduce new claims. Every required text field must be a non-empty string of at most {MAX_SKILL_FIELD_CHARACTERS} characters. For each listed overlong field, rewrite it concisely to at most {SCHEMA_REPAIR_TARGET_CHARACTERS} characters so there is clear margin below the hard limit. Preserve the exact top-level shape, all six task-specific labels, and use only the type strings 'Procedure or Local Strategy' and 'Failure Lesson'. Return JSON only; do not assign IDs.",
                "required_list_lengths": list_lengths,
                "maximum_field_characters": MAX_SKILL_FIELD_CHARACTERS,
                "repair_target_characters": SCHEMA_REPAIR_TARGET_CHARACTERS,
            }
            repaired, repair_record = call_json(config, [{"role": "system", "content": "You are repairing schema-only violations in an ALFWorld SkillBank without changing its semantics."}, {"role": "user", "content": json.dumps(repair_prompt, ensure_ascii=False)}], args)
            if set(repaired) != {"general", "task_specific"} or set(repaired.get("task_specific", {})) != set(TASK_TYPE_LABELS.values()):
                raise RuntimeError(f"invalid schema-repaired bank shape for {role}")
            repaired_lengths = {
                "general": len(repaired["general"]),
                **{label: len(repaired["task_specific"][label]) for label in TASK_TYPE_LABELS.values()},
            }
            if repaired_lengths != list_lengths:
                raise RuntimeError(f"schema repair changed list lengths for {role}")
            value = repaired
            merged_values[role] = value
            records.append({
                "stage": "schema_repair", "role": role, "repair_index": repair_index + 1,
                "maximum_field_characters": MAX_SKILL_FIELD_CHARACTERS,
                "repair_target_characters": SCHEMA_REPAIR_TARGET_CHARACTERS,
                "validation_errors": validation_errors, **repair_record,
            })
            save_checkpoint()
        field_alias_normalizations = []
        for alias_scope, alias_label, alias_rows in (
            [("general", None, value["general"])]
            + [("task_specific", label, value["task_specific"][label]) for label in TASK_TYPE_LABELS.values()]
        ):
            for alias_index, alias_row in enumerate(alias_rows, 1):
                if alias_row.get("type") != "Failure Lesson":
                    continue
                description = alias_row.get("description")
                principle = alias_row.get("principle")
                other_fields_valid = all(
                    isinstance(alias_row.get(field), str)
                    and alias_row[field].strip()
                    and len(alias_row[field]) <= MAX_SKILL_FIELD_CHARACTERS
                    for field in ("why_it_happens", "how_to_avoid")
                )
                if (
                    (not isinstance(description, str) or not description.strip())
                    and isinstance(principle, str)
                    and principle.strip()
                    and len(principle) <= MAX_SKILL_FIELD_CHARACTERS
                    and other_fields_valid
                ):
                    alias_row["description"] = principle
                    field_alias_normalizations.append({
                        "scope": alias_scope,
                        "task_label": alias_label,
                        "index": alias_index,
                        "type": "Failure Lesson",
                        "source_field": "principle",
                        "target_field": "description",
                    })
        if field_alias_normalizations:
            merged_values[role] = value
            records.append({
                "stage": "deterministic_schema_field_alias_normalization",
                "role": role,
                "normalizations": field_alias_normalizations,
                "policy": "copy existing principle verbatim into missing Failure Lesson description only when the other declared fields are valid",
            })
            save_checkpoint()
        type_normalizations = []
        for normalization_scope, normalization_label, normalization_rows in (
            [("general", None, value["general"])]
            + [("task_specific", label, value["task_specific"][label]) for label in TASK_TYPE_LABELS.values()]
        ):
            for normalization_index, normalization_row in enumerate(normalization_rows, 1):
                declared_fields = SKILL_FIELDS.get(normalization_row.get("type"))
                declared_valid = declared_fields is not None and all(
                    isinstance(normalization_row.get(field), str)
                    and normalization_row[field].strip()
                    and len(normalization_row[field]) <= MAX_SKILL_FIELD_CHARACTERS
                    for field in declared_fields
                )
                if declared_valid:
                    continue
                valid_types = [
                    skill_type
                    for skill_type, fields in SKILL_FIELDS.items()
                    if all(
                        isinstance(normalization_row.get(field), str)
                        and normalization_row[field].strip()
                        and len(normalization_row[field]) <= MAX_SKILL_FIELD_CHARACTERS
                        for field in fields
                    )
                ]
                if len(valid_types) == 1:
                    previous_type = normalization_row.get("type")
                    normalization_row["type"] = valid_types[0]
                    type_normalizations.append({
                        "scope": normalization_scope,
                        "task_label": normalization_label,
                        "index": normalization_index,
                        "from_type": previous_type,
                        "to_type": valid_types[0],
                    })
        if type_normalizations:
            merged_values[role] = value
            records.append({
                "stage": "deterministic_schema_type_normalization",
                "role": role,
                "normalizations": type_normalizations,
                "policy": "change only an invalid declared type when exactly one complete legal field set exists",
            })
            save_checkpoint()
        remaining_errors = merged_bank_validation_errors(value)
        if remaining_errors:
            raise RuntimeError(f"Teacher schema repair failed for {role}: {remaining_errors}")
        enforce_role_capacity(value, role, capacity_policy)
        numbered, next_id = {"general": [], "task_specific": {label: [] for label in TASK_TYPE_LABELS.values()}}, 1
        for scope, label, rows in [("general", None, value["general"])] + [("task_specific", label, value["task_specific"][label]) for label in TASK_TYPE_LABELS.values()]:
            if not isinstance(rows, list):
                raise RuntimeError(f"invalid merged skill list for {role}/{label or scope}")
            for raw_skill in rows:
                skill = {"skill_id": f"skill_{next_id:03d}", "version": 1, **validate_skill(raw_skill)}
                next_id += 1
                (numbered["general"] if scope == "general" else numbered["task_specific"][label]).append(skill)
        bank["active_skillbanks"][role] = numbered
    parse_bank(bank, "A")
    bank["evidence_file_sha256"] = file_hash(args.evidence)
    bank["live_repository_sha256"] = "sha256:" + hashlib.sha256(canonical_bytes(bank["active_skillbanks"])).hexdigest()
    write_json(args.output, bank)
    write_json(args.record_output, {
        "schema_version": 1, "experiment_id": evidence["experiment_id"], "client_id": "A", "generation": args.generation,
        "teacher_model": config.model, "temperature": 0, "seed": args.seed,
        "teacher_endpoint": teacher_descriptor,
        "maximum_skill_field_characters": MAX_SKILL_FIELD_CHARACTERS,
        "capacity_policy": capacity_policy,
        "parent_bank_file_sha256": parent_bank_hash,
        "evidence_file_sha256": file_hash(args.evidence), "records": records,
    })
    print(json.dumps({"status": "complete", "bank": str(args.output), "teacher_model": config.model, "skills_by_role": {role: sum(len(rows) for rows in bank["active_skillbanks"][role]["task_specific"].values()) + len(bank["active_skillbanks"][role]["general"]) for role in ROLES}}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
