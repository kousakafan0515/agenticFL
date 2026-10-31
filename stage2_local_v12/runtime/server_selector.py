"""Deterministic, outcome-blind selector for the originalFL Global SkillBank."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


TASK_TYPES = tuple(str(index) for index in range(1, 7))
BODY_FIELDS = ("title", "trigger", "procedure", "avoid")
DEFAULT_SALT = "originalFL-v1-server-reservoir"


class SelectionError(ValueError):
    pass


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def object_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def scopes() -> list[tuple[str, str | None]]:
    return [("general", None)] + [("task_specific", task_type) for task_type in TASK_TYPES]


def scope_key(kind: str, task_type: str | None) -> str:
    return "general" if kind == "general" else f"task_specific:{task_type}"


def _scope_skills(snapshot: dict[str, Any], kind: str, task_type: str | None) -> list[dict[str, Any]]:
    if kind == "general":
        value = snapshot.get("general_skills")
    else:
        sections = snapshot.get("task_specific_skills")
        if not isinstance(sections, dict):
            raise SelectionError("task_specific_skills must be an object")
        value = sections.get(str(task_type))
    if not isinstance(value, list):
        raise SelectionError(f"Missing list for {scope_key(kind, task_type)}")
    return value


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    client = snapshot.get("client_id")
    if client not in {"A", "B", "C"}:
        raise SelectionError("client_id must be A, B, or C")
    total = 0
    seen_ids: set[str] = set()
    for kind, task_type in scopes():
        values = _scope_skills(snapshot, kind, task_type)
        if len(values) > 2:
            raise SelectionError(f"{client}/{scope_key(kind, task_type)} exceeds capacity 2")
        total += len(values)
        for skill in values:
            skill_id = skill.get("skill_id")
            if not isinstance(skill_id, str) or not skill_id or skill_id in seen_ids:
                raise SelectionError(f"{client} has a missing or duplicate skill_id")
            seen_ids.add(skill_id)
            if set(BODY_FIELDS) - set(skill):
                raise SelectionError(f"{client}/{skill_id} lacks a body field")
            if not isinstance(skill.get("procedure"), list) or not isinstance(skill.get("avoid"), list):
                raise SelectionError(f"{client}/{skill_id} procedure and avoid must be lists")
    if total > 14:
        raise SelectionError(f"{client} exceeds total capacity 14")


def _content(kind: str, task_type: str | None, skill: dict[str, Any]) -> dict[str, Any]:
    return {
        "scope": kind,
        "task_type_id": task_type,
        **{field: skill[field] for field in BODY_FIELDS},
    }


def select_global(
    snapshots: list[dict[str, Any]], *, salt: str = DEFAULT_SALT, previous: dict[str, Any] | None = None
) -> dict[str, Any]:
    if {snapshot.get("client_id") for snapshot in snapshots} != {"A", "B", "C"} or len(snapshots) != 3:
        raise SelectionError("Exactly one complete snapshot from each of A, B, and C is required")
    for snapshot in snapshots:
        validate_snapshot(snapshot)

    candidates: dict[tuple[str, str | None], dict[str, dict[str, Any]]] = defaultdict(dict)
    for snapshot in sorted(snapshots, key=lambda value: value["client_id"]):
        client = snapshot["client_id"]
        for kind, task_type in scopes():
            for skill in _scope_skills(snapshot, kind, task_type):
                content = _content(kind, task_type, skill)
                content_hash = object_hash(content)
                bucket = candidates[(kind, task_type)]
                if content_hash not in bucket:
                    bucket[content_hash] = {
                        "global_skill_id": "global_" + content_hash.removeprefix("sha256:")[:16],
                        **content,
                        "canonical_content_hash": content_hash,
                        "sources": [],
                    }
                bucket[content_hash]["sources"].append(
                    {
                        "client_id": client,
                        "skill_id": skill["skill_id"],
                        "version": skill.get("version", 1),
                    }
                )

    selected_by_scope: dict[str, list[dict[str, Any]]] = {}
    dedup_counts: dict[str, dict[str, int]] = {}
    for kind, task_type in scopes():
        key = scope_key(kind, task_type)
        rows = list(candidates[(kind, task_type)].values())
        for row in rows:
            row["sources"] = sorted(row["sources"], key=lambda value: (value["client_id"], value["skill_id"]))
            row["source_client_count"] = len({source["client_id"] for source in row["sources"]})
            digest_input = f"{salt}|{key}|{row['canonical_content_hash']}".encode("utf-8")
            row["selection_digest"] = "sha256:" + hashlib.sha256(digest_input).hexdigest()
        rows.sort(key=lambda row: (-row["source_client_count"], row["selection_digest"]))
        selected_by_scope[key] = rows[:2]
        dedup_counts[key] = {"input": sum(len(row["sources"]) for row in rows), "unique": len(rows), "selected": len(rows[:2])}

    output = {
        "schema_version": 1,
        "experiment_id": "originalFL-v1",
        "selection_salt": salt,
        "selection_policy": "exact_dedup_then_source_support_then_deterministic_hash_top2_per_scope",
        "general_skills": selected_by_scope["general"],
        "task_specific_skills": {
            task_type: selected_by_scope[f"task_specific:{task_type}"] for task_type in TASK_TYPES
        },
        "dedup_and_selection_counts": dedup_counts,
    }
    output["global_bank_sha256"] = object_hash(
        {"general_skills": output["general_skills"], "task_specific_skills": output["task_specific_skills"]}
    )
    output["operations_from_previous"] = classify_operations(previous, output)
    return output


def _global_scope(bank: dict[str, Any] | None, kind: str, task_type: str | None) -> list[dict[str, Any]]:
    if bank is None:
        return []
    return bank.get("general_skills", []) if kind == "general" else bank.get("task_specific_skills", {}).get(str(task_type), [])


def classify_operations(previous: dict[str, Any] | None, current: dict[str, Any]) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    for kind, task_type in scopes():
        key = scope_key(kind, task_type)
        before = _global_scope(previous, kind, task_type)
        after = _global_scope(current, kind, task_type)
        before_by_hash = {row["canonical_content_hash"]: row for row in before}
        after_by_hash = {row["canonical_content_hash"]: row for row in after}
        if set(before_by_hash) == set(after_by_hash):
            operations.append({"scope": key, "operation": "NONE"})
            continue
        removed = [before_by_hash[value] for value in sorted(set(before_by_hash) - set(after_by_hash))]
        added = [after_by_hash[value] for value in sorted(set(after_by_hash) - set(before_by_hash))]
        remaining_removed = list(removed)
        for row in added:
            source_keys = {(item["client_id"], item["skill_id"]) for item in row["sources"]}
            update_index = next(
                (
                    index
                    for index, old in enumerate(remaining_removed)
                    if source_keys & {(item["client_id"], item["skill_id"]) for item in old["sources"]}
                ),
                None,
            )
            if update_index is not None:
                old = remaining_removed.pop(update_index)
                operation = "UPDATE"
                replaced_hash = old["canonical_content_hash"]
            elif len(before) >= 2 and remaining_removed:
                old = remaining_removed.pop(0)
                operation = "REPLACE"
                replaced_hash = old["canonical_content_hash"]
            else:
                operation = "ADD"
                replaced_hash = None
            operations.append(
                {
                    "scope": key,
                    "operation": operation,
                    "selected_content_hash": row["canonical_content_hash"],
                    "replaced_content_hash": replaced_hash,
                }
            )
    return operations


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an originalFL Global SkillBank from three complete snapshots")
    parser.add_argument("--client-bank", action="append", type=Path, required=True)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--salt", default=DEFAULT_SALT)
    args = parser.parse_args()
    snapshots = [json.loads(path.read_text(encoding="utf-8")) for path in args.client_bank]
    previous = json.loads(args.previous.read_text(encoding="utf-8")) if args.previous else None
    result = select_global(snapshots, salt=args.salt, previous=previous)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result["global_bank_sha256"])


if __name__ == "__main__":
    main()
