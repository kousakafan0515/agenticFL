"""SkillBank snapshot helpers for the executable originalFL protocol."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from stage2_local_v12.runtime.local_operations import BODY_FIELDS, content_hash
from stage2_local_v12.runtime.server_selector import TASK_TYPES, validate_snapshot


PROTOCOL_ID = "originalFL-v1"


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


def bank_content(bank: dict[str, Any]) -> dict[str, Any]:
    return {
        "general_skills": bank["general_skills"],
        "task_specific_skills": bank["task_specific_skills"],
    }


def bank_hash(bank: dict[str, Any]) -> str:
    return object_hash(bank_content(bank))


def empty_global() -> dict[str, Any]:
    bank = {
        "schema_version": 1,
        "experiment_id": PROTOCOL_ID,
        "selection_policy": "initial_empty_global",
        "general_skills": [],
        "task_specific_skills": {task_type: [] for task_type in TASK_TYPES},
        "operations_from_previous": [],
    }
    bank["global_bank_sha256"] = bank_hash(bank)
    return bank


def _download_skill(row: dict[str, Any]) -> dict[str, Any]:
    skill_id = row.get("global_skill_id") or row.get("skill_id")
    if not isinstance(skill_id, str) or not skill_id:
        raise ValueError("Global skill lacks an identity")
    return {
        "skill_id": skill_id,
        "version": int(row.get("version", 1)),
        **{field: deepcopy(row[field]) for field in BODY_FIELDS},
    }


def download_global(global_bank: dict[str, Any], client_id: str, round_index: int) -> dict[str, Any]:
    """Materialize the complete downlink as a client-local parent snapshot."""
    if client_id not in {"A", "B", "C"}:
        raise ValueError("client_id must be A, B, or C")
    task_sections = global_bank.get("task_specific_skills")
    if not isinstance(task_sections, dict):
        raise ValueError("Global task_specific_skills is invalid")
    local = {
        "schema_version": 1,
        "experiment_id": PROTOCOL_ID,
        "round_id": round_index,
        "client_id": client_id,
        "parent_global_bank_sha256": global_bank["global_bank_sha256"],
        "general_skills": [_download_skill(row) for row in global_bank.get("general_skills", [])],
        "task_specific_skills": {
            task_type: [_download_skill(row) for row in task_sections.get(task_type, [])]
            for task_type in TASK_TYPES
        },
        "created_at": utc_now(),
    }
    return finalize_local(local)


def finalize_local(bank: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(bank)
    for skill in result.get("general_skills", []):
        skill["content_hash"] = content_hash(skill)
    for skills in result.get("task_specific_skills", {}).values():
        for skill in skills:
            skill["content_hash"] = content_hash(skill)
    result["local_bank_sha256"] = bank_hash(result)
    validate_local(result)
    return result


def validate_local(bank: dict[str, Any]) -> None:
    validate_snapshot(bank)
    expected = bank_hash(bank)
    if bank.get("local_bank_sha256") != expected:
        raise ValueError("local_bank_sha256 mismatch")
    parent = bank.get("parent_global_bank_sha256")
    if not isinstance(parent, str) or not parent.startswith("sha256:"):
        raise ValueError("parent_global_bank_sha256 is required")
    for skill in bank.get("general_skills", []):
        if skill.get("content_hash") != content_hash(skill):
            raise ValueError("skill content_hash mismatch")
    for skills in bank.get("task_specific_skills", {}).values():
        for skill in skills:
            if skill.get("content_hash") != content_hash(skill):
                raise ValueError("skill content_hash mismatch")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
