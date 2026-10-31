"""Validate and materialize originalFL local ADD/UPDATE/REPLACE/NONE operations."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any


OPERATIONS = {"ADD", "UPDATE", "REPLACE", "NONE"}
BODY_FIELDS = ("title", "trigger", "procedure", "avoid")
WORD_RE = re.compile(r"[A-Za-z]+(?:[-'][A-Za-z]+)*")


class LocalOperationError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def content_hash(skill: dict[str, Any]) -> str:
    body = {field: skill[field] for field in BODY_FIELDS}
    return "sha256:" + hashlib.sha256(canonical_bytes(body)).hexdigest()


def _scope(bank: dict[str, Any], kind: str, task_type: str | None) -> list[dict[str, Any]]:
    if kind == "general":
        value = bank.get("general_skills")
    elif kind == "task_specific" and task_type in {str(index) for index in range(1, 7)}:
        sections = bank.get("task_specific_skills")
        value = sections.get(task_type) if isinstance(sections, dict) else None
    else:
        raise LocalOperationError("Invalid scope")
    if not isinstance(value, list) or len(value) > 2:
        raise LocalOperationError("Scope must be a list with at most two skills")
    return value


def allowed_operations(bank: dict[str, Any], kind: str, task_type: str | None = None) -> list[str]:
    skills = _scope(bank, kind, task_type)
    allowed = ["NONE"]
    if skills:
        allowed.append("UPDATE")
    if len(skills) < 2:
        allowed.append("ADD")
    else:
        allowed.append("REPLACE")
    return sorted(allowed)


def _validate_body(skill: Any) -> dict[str, Any]:
    if not isinstance(skill, dict) or set(skill) != set(BODY_FIELDS):
        raise LocalOperationError(f"skill keys must be exactly {list(BODY_FIELDS)}")
    if not isinstance(skill["title"], str) or not 3 <= len(WORD_RE.findall(skill["title"])) <= 12:
        raise LocalOperationError("title must contain 3-12 English words")
    if not isinstance(skill["trigger"], str) or not 6 <= len(WORD_RE.findall(skill["trigger"])) <= 30:
        raise LocalOperationError("trigger must contain 6-30 English words")
    if not isinstance(skill["procedure"], list) or not 2 <= len(skill["procedure"]) <= 10:
        raise LocalOperationError("procedure must contain 2-10 items")
    if not isinstance(skill["avoid"], list) or len(skill["avoid"]) > 3:
        raise LocalOperationError("avoid must contain 0-3 items")
    fields = [skill["title"], skill["trigger"], *skill["procedure"], *skill["avoid"]]
    if not all(isinstance(value, str) and value.strip() for value in fields):
        raise LocalOperationError("all skill fields must contain non-empty strings")
    if len(WORD_RE.findall(" ".join(fields))) > 100:
        raise LocalOperationError("skill must contain at most 100 English words")
    return deepcopy(skill)


def _new_skill_id(client_id: str, body: dict[str, Any], active_ids: set[str]) -> str:
    base = f"{client_id.lower()}_skill_{content_hash(body).removeprefix('sha256:')[:12]}"
    if base not in active_ids:
        return base
    suffix = 2
    while f"{base}_{suffix}" in active_ids:
        suffix += 1
    return f"{base}_{suffix}"


def apply_operation(
    bank: dict[str, Any], proposal: dict[str, Any], *, kind: str, task_type: str | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    if set(proposal) != {"operation", "target_skill_id", "reason", "skill"}:
        raise LocalOperationError("proposal keys are invalid")
    operation = proposal["operation"]
    if operation not in OPERATIONS or operation not in allowed_operations(bank, kind, task_type):
        raise LocalOperationError(f"Operation {operation!r} is not allowed in the current scope")
    reason = proposal["reason"]
    if not isinstance(reason, str) or not 8 <= len(WORD_RE.findall(reason)) <= 40:
        raise LocalOperationError("reason must contain 8-40 English words")

    result = deepcopy(bank)
    skills = _scope(result, kind, task_type)
    target = proposal["target_skill_id"]
    body = proposal["skill"]
    if operation == "NONE":
        if target is not None or body is not None:
            raise LocalOperationError("NONE requires null target_skill_id and skill")
        return result, {"operation": "NONE", "changed": False}

    if operation == "ADD":
        if target is not None:
            raise LocalOperationError("ADD requires null target_skill_id")
    else:
        if not isinstance(target, str) or target not in {row.get("skill_id") for row in skills}:
            raise LocalOperationError(f"{operation} requires an exact active target_skill_id")
    validated_body = _validate_body(body)
    candidate_hash = content_hash(validated_body)
    if candidate_hash in {content_hash(row) for row in skills if row.get("skill_id") != target}:
        raise LocalOperationError("candidate duplicates another active skill")

    active_ids = {row.get("skill_id") for row in skills if isinstance(row.get("skill_id"), str)}
    replaced_skill_id: str | None = None
    if operation == "ADD":
        new_id = _new_skill_id(str(bank.get("client_id", "client")), validated_body, active_ids)
        skills.append({"skill_id": new_id, "version": 1, **validated_body})
    elif operation == "UPDATE":
        index = next(index for index, row in enumerate(skills) if row.get("skill_id") == target)
        old = skills[index]
        new_id = target
        skills[index] = {"skill_id": target, "version": int(old.get("version", 1)) + 1, **validated_body}
    else:
        index = next(index for index, row in enumerate(skills) if row.get("skill_id") == target)
        replaced_skill_id = target
        active_ids.remove(target)
        new_id = _new_skill_id(str(bank.get("client_id", "client")), validated_body, active_ids)
        skills[index] = {"skill_id": new_id, "version": 1, **validated_body}

    if len(skills) > 2:
        raise LocalOperationError("operation exceeded scope capacity")
    return result, {
        "operation": operation,
        "changed": True,
        "selected_skill_id": new_id,
        "replaced_skill_id": replaced_skill_id,
        "candidate_content_hash": candidate_hash,
    }


def passes_local_admission(
    operation: str,
    *,
    rescues: int,
    harms: int,
    per_task_type_net: dict[str, int],
    api_clean: bool,
) -> bool:
    if operation not in OPERATIONS - {"NONE"} or not api_clean:
        return False
    minimum_net = 2 if operation == "REPLACE" else 1
    return rescues - harms >= minimum_net and min(per_task_type_net.values(), default=0) >= -1
