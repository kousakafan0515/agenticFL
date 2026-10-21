"""B1-anchored per-role capacity policy for v9 generations B2 and later."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable


CAPACITY_POLICY_SCHEMA = "stage2_local_v9.b1_role_capacity.v1"
CAPACITY_POLICY_NAME = "fixed_per_role_from_b1"


def role_skill_count(repository: dict[str, Any]) -> int:
    general = repository.get("general")
    task_specific = repository.get("task_specific")
    if not isinstance(general, list) or not isinstance(task_specific, dict):
        raise RuntimeError("invalid role repository while counting B1 capacity")
    if any(not isinstance(rows, list) for rows in task_specific.values()):
        raise RuntimeError("invalid task-specific repository while counting B1 capacity")
    return len(general) + sum(len(rows) for rows in task_specific.values())


def resolve_b1_capacity_policy(
    parent_bank: dict[str, Any],
    generation: int,
    roles: Iterable[str],
    parent_bank_file_sha256: str,
) -> dict[str, Any] | None:
    """Derive the policy at B2, then validate and inherit it for B3+."""

    role_names = tuple(roles)
    repositories = parent_bank.get("active_skillbanks")
    if not isinstance(repositories, dict) or set(repositories) != set(role_names):
        raise RuntimeError("parent bank roles do not match the capacity-policy roles")
    if generation == 1:
        return None
    if generation < 1:
        raise RuntimeError("generation must be positive")

    if generation == 2:
        policy = {
            "schema_version": CAPACITY_POLICY_SCHEMA,
            "policy": CAPACITY_POLICY_NAME,
            "anchor_generation": 1,
            "anchor_bank_file_sha256": parent_bank_file_sha256,
            "role_capacities": {
                role: role_skill_count(repositories[role]) for role in role_names
            },
        }
    else:
        raw_policy = parent_bank.get("capacity_policy")
        if not isinstance(raw_policy, dict):
            raise RuntimeError("B3+ parent bank is missing the frozen B1 capacity policy")
        policy = deepcopy(raw_policy)

    expected_keys = {
        "schema_version",
        "policy",
        "anchor_generation",
        "anchor_bank_file_sha256",
        "role_capacities",
    }
    if set(policy) != expected_keys:
        raise RuntimeError("invalid B1 capacity-policy fields")
    if policy["schema_version"] != CAPACITY_POLICY_SCHEMA:
        raise RuntimeError("invalid B1 capacity-policy schema")
    if policy["policy"] != CAPACITY_POLICY_NAME or policy["anchor_generation"] != 1:
        raise RuntimeError("invalid B1 capacity-policy identity")
    anchor_hash = policy["anchor_bank_file_sha256"]
    if not isinstance(anchor_hash, str) or not anchor_hash.startswith("sha256:"):
        raise RuntimeError("invalid B1 capacity anchor hash")
    capacities = policy["role_capacities"]
    if not isinstance(capacities, dict) or set(capacities) != set(role_names):
        raise RuntimeError("B1 capacity roles do not match the current client roles")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in capacities.values()):
        raise RuntimeError("B1 role capacities must be non-negative integers")
    for role in role_names:
        if role_skill_count(repositories[role]) > capacities[role]:
            raise RuntimeError(f"parent bank exceeds frozen B1 capacity for {role}")
    return policy


def role_capacity_context(
    policy: dict[str, Any] | None,
    role: str,
    parent_repository: dict[str, Any],
) -> dict[str, int] | None:
    if policy is None:
        return None
    capacity = policy["role_capacities"][role]
    parent_count = role_skill_count(parent_repository)
    if parent_count > capacity:
        raise RuntimeError(f"parent bank exceeds frozen B1 capacity for {role}")
    return {
        "maximum_total_skills": capacity,
        "parent_skill_count": parent_count,
        "available_add_slots": capacity - parent_count,
    }


def enforce_role_capacity(
    repository: dict[str, Any],
    role: str,
    policy: dict[str, Any] | None,
) -> int:
    count = role_skill_count(repository)
    if policy is not None:
        capacity = policy["role_capacities"][role]
        if count > capacity:
            raise RuntimeError(
                f"Teacher exceeded frozen B1 capacity for {role}: {count} > {capacity}"
            )
    return count
