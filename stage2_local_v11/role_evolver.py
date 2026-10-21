"""Shared, auditable two-stage Teacher for one bank per client role.

The same entry point serves independent local evolution and Global-to-local
evolution. It never calls an external model at import time.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from client_code.skillbank_loader import EXPECTED_ROLES, TASK_TYPE_LABELS, parse_bank
from originalFL.banks import file_hash, write_json
from originalFL.round1_evolver import _local_evolution_config
from stage2_local_v9.client_a_patch_evolver import (
    call_json_recorded, compact_episode, normalize_known_json_mode_wrapper,
    record_normalization_audit, validate_family_findings, validate_skill,
)
from stage3_2_role_agnostic_semantic_merge.local_round2_evolver import (
    EvolutionError, now, object_hash,
)
from stage2_local_v9.scripts.client_overlay import ROLE_RULES as BC_ROLE_RULES


TASK_LABELS = tuple(TASK_TYPE_LABELS.values())
ROLE_RULES = {
    "A": {
        "Planner": "Learn goal decomposition, subtask ordering and plan repair; do not assign environment actions.",
        "Executor": "Learn observation-grounded execution, exact ALFWorld actions and recovery within assigned subtasks.",
    },
    **BC_ROLE_RULES,
}
SCHEMA = "stage2_local_v11.role_partitioned_bank.v1"
V9_TEACHER_HELPER_SHA256 = "b3af122879255db372fec2944c60c663d877ccb68698d49f2ae1e6ebbac289a2"


def repository_rows(repository: dict[str, Any]) -> list[dict[str, Any]]:
    if set(repository) != {"general", "task_specific"} or set(repository["task_specific"]) != set(TASK_LABELS):
        raise EvolutionError("role repository must have exactly seven buckets")
    rows = list(repository["general"])
    for label in TASK_LABELS:
        rows.extend(repository["task_specific"][label])
    return rows


def role_patch(
    parent: dict[str, Any], role: str, value: dict[str, Any],
    allowed_refs: set[str], client: str, generation: int,
    *, allowed_operations: set[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, int]]:
    """Validate and apply one role's net patch; quota cannot cross roles."""
    if set(value) != {"operations"} or not isinstance(value["operations"], list):
        raise EvolutionError("top-level output must be exactly {'operations': [...]}")
    base_rows = repository_rows(parent)
    base: dict[str, tuple[str, dict[str, Any]]] = {}
    for bucket, rows in (("general", parent["general"]), *parent["task_specific"].items()):
        for row in rows:
            skill_id = row.get("skill_id")
            if not isinstance(skill_id, str) or not skill_id or skill_id in base:
                raise EvolutionError(f"{role}: invalid or duplicate parent ID {skill_id!r}")
            validate_skill(row, f"{role}/parent/{skill_id}")
            base[skill_id] = (bucket, row)
    if len(base) != len(base_rows):
        raise EvolutionError(f"{role}: parent count mismatch")
    touched: set[str] = set()
    clean_ops: list[dict[str, Any]] = []
    counts = {"base": len(base), "delete": 0, "update": 0, "add": 0}
    for index, raw in enumerate(value["operations"], 1):
        if not isinstance(raw, dict):
            raise EvolutionError(f"{role}/operation {index}: object required")
        operation = raw.get("operation")
        if operation not in {"DELETE", "UPDATE", "ADD"} or (allowed_operations is not None and operation not in allowed_operations):
            raise EvolutionError(f"{role}/operation {index}: forbidden operation {operation!r}")
        refs = raw.get("evidence_refs")
        if not isinstance(refs, list) or not refs or any(not isinstance(ref, str) or ref not in allowed_refs for ref in refs):
            raise EvolutionError(f"{role}/operation {index}: evidence refs must belong to this training round")
        if operation in {"DELETE", "UPDATE"}:
            if raw.get("target_role") != role:
                raise EvolutionError(f"{role}/operation {index}: target role mismatch")
            target = raw.get("target_skill_id")
            if target not in base or target in touched:
                raise EvolutionError(f"{role}/operation {index}: unknown or repeated target {target!r}")
            touched.add(target)
            clean = {"operation": operation, "target_role": role, "target_skill_id": target, "evidence_refs": list(refs)}
            if operation == "UPDATE":
                if raw.get("bucket") not in ("general", *TASK_LABELS):
                    raise EvolutionError(f"{role}/operation {index}: invalid bucket")
                clean.update(bucket=raw["bucket"], skill=validate_skill(raw.get("skill"), f"{role}/UPDATE/{target}"))
            counts[operation.lower()] += 1
        else:
            if raw.get("role") != role or raw.get("bucket") not in ("general", *TASK_LABELS):
                raise EvolutionError(f"{role}/operation {index}: ADD role or bucket mismatch")
            clean = {"operation": "ADD", "role": role, "bucket": raw["bucket"], "skill": validate_skill(raw.get("skill"), f"{role}/ADD/{index}"), "evidence_refs": list(refs)}
            counts["add"] += 1
        clean_ops.append(clean)
    if counts["add"] > counts["delete"] // 3:
        raise EvolutionError(f"{role}: ADD={counts['add']} exceeds floor(DELETE={counts['delete']}/3)")

    result = {"general": [], "task_specific": {label: [] for label in TASK_LABELS}}
    deletes = {op["target_skill_id"] for op in clean_ops if op["operation"] == "DELETE"}
    updates = {op["target_skill_id"]: op for op in clean_ops if op["operation"] == "UPDATE"}
    for bucket, rows in (("general", parent["general"]), *parent["task_specific"].items()):
        for row in rows:
            skill_id = row["skill_id"]
            if skill_id in deletes:
                continue
            destination = bucket
            output = copy.deepcopy(row)
            if skill_id in updates:
                patch = updates[skill_id]
                destination = patch["bucket"]
                output = {"skill_id": skill_id, "version": int(row.get("version", 1)) + 1, **patch["skill"]}
                if "source_skill_keys" in row:
                    output["source_skill_keys"] = copy.deepcopy(row["source_skill_keys"])
            (result["general"] if destination == "general" else result["task_specific"][destination]).append(output)
    existing = set(base)
    for index, op in enumerate((x for x in clean_ops if x["operation"] == "ADD"), 1):
        next_index = index
        while True:
            skill_id = f"{client}_B{generation}_{role.replace(' ', '_')}_ADD_{next_index:03d}"
            if skill_id not in existing:
                break
            next_index += 1
        existing.add(skill_id)
        output = {"skill_id": skill_id, "version": 1, **op["skill"], "source_skill_keys": [f"{client}/{role}/B{generation}/add/{skill_id}"]}
        bucket = op["bucket"]
        (result["general"] if bucket == "general" else result["task_specific"][bucket]).append(output)
        op["assigned_skill_id"] = skill_id
    rows = repository_rows(result)
    semantic_hashes = [object_hash(validate_skill(row, f"{role}/candidate/{row['skill_id']}")) for row in rows]
    if len(set(semantic_hashes)) != len(semantic_hashes):
        raise EvolutionError(f"{role}: exact duplicate skill content")
    counts["candidate"] = len(rows)
    if counts["candidate"] != counts["base"] - counts["delete"] + counts["add"]:
        raise EvolutionError(f"{role}: patch arithmetic mismatch")
    return result, clean_ops, counts


def combine_adds(base_operations: list[dict[str, Any]], value: dict[str, Any], max_add: int) -> dict[str, Any]:
    if set(value) != {"operations"} or not isinstance(value["operations"], list):
        raise EvolutionError("ADD stage must contain exactly an operations list")
    if len(value["operations"]) > max_add or any(not isinstance(row, dict) or row.get("operation") != "ADD" for row in value["operations"]):
        raise EvolutionError(f"ADD stage must contain 0..{max_add} ADD operations only")
    return {"operations": copy.deepcopy(base_operations) + copy.deepcopy(value["operations"])}


def _call_and_check(config: Any, prompt: dict[str, Any], system: str, args: argparse.Namespace, prefix: Path, expected: str) -> tuple[dict[str, Any], dict[str, Any]]:
    value, record = call_json_recorded(config, [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)}], args, prefix)
    value, audit = normalize_known_json_mode_wrapper(value, expected)
    if audit is not None:
        record_normalization_audit(record, audit)
    return value, record


def evolve(args: argparse.Namespace) -> dict[str, Any]:
    helper_path = Path(__file__).resolve().parents[1] / "stage2_local_v9" / "client_a_patch_evolver.py"
    if hashlib.sha256(helper_path.read_bytes()).hexdigest() != V9_TEACHER_HELPER_SHA256:
        raise EvolutionError("v11 frozen v9 Teacher helper changed")
    if any(path.exists() for path in (args.output, args.patch_output, args.record_output)):
        raise EvolutionError("refusing to overwrite existing v11 bank, patch or record")
    parent = json.loads(args.parent_bank.read_text(encoding="utf-8"))
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    parse_bank(parent, args.client)
    if parent.get("generation") != args.generation - 1:
        raise EvolutionError("parent bank generation mismatch")
    roles = EXPECTED_ROLES[args.client]
    if args.parent_kind == "global":
        if not parent.get("source_global_file_sha256"):
            raise EvolutionError("Global downlink provenance missing")
        repositories = [parent["active_skillbanks"][role] for role in roles]
        if any(repository != repositories[0] for repository in repositories[1:]):
            raise EvolutionError("Global downlink must copy the same seven-bucket bank to every role")
    if evidence.get("client_id") != args.client or evidence.get("generation") != args.generation or len(evidence.get("episodes") or []) != 134:
        raise EvolutionError("complete matching 134-episode training evidence is required")
    if evidence.get("parent_bank_file_sha256") != file_hash(args.parent_bank):
        raise EvolutionError("training evidence parent hash mismatch")
    episodes = evidence["episodes"]
    allowed_refs = {row.get("evidence_ref") for row in episodes}
    if None in allowed_refs or len(allowed_refs) != 134:
        raise EvolutionError("training evidence must contain 134 unique references")
    config = _local_evolution_config()
    descriptor = config.descriptor()
    if config.model != "deepseek-flash" or descriptor.get("provider") != "deepseek_official" or descriptor.get("endpoint_origin") != "https://api.deepseek.com":
        raise EvolutionError("DeepSeek official deepseek-flash Teacher required")
    checkpoint_path = args.record_output.with_suffix(".checkpoint.json")
    identity = {"schema_version": "stage2_local_v11.role_teacher_checkpoint.v1", "client": args.client, "generation": args.generation, "parent_kind": args.parent_kind, "parent_bank_file_sha256": file_hash(args.parent_bank), "evidence_file_sha256": file_hash(args.evidence), "teacher": descriptor}
    checkpoint = {**identity, "findings": {role: {} for role in roles}, "role_patches": {}, "records": []}
    if checkpoint_path.exists():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if any(checkpoint.get(key) != value for key, value in identity.items()):
            raise EvolutionError("Teacher checkpoint identity mismatch")
    attempts = args.record_output.parent / f"B{args.generation}_teacher_attempts"
    attempts.mkdir(parents=True, exist_ok=True)
    for role in roles:
        repository = parent["active_skillbanks"][role]
        ids = {row["skill_id"] for row in repository_rows(repository)}
        for type_id, label in TASK_TYPE_LABELS.items():
            if label in checkpoint["findings"][role]:
                continue
            trajectories = [compact_episode(row, role) for row in episodes if int(row["task_type_id"]) == type_id]
            family_refs = {row["evidence_ref"] for row in trajectories}
            rejected = [row for row in checkpoint["records"] if row.get("stage") == "family_rejected" and row.get("role") == role and row.get("task_type") == label]
            previous_error = rejected[-1]["error"] if rejected else None
            for attempt in range(len(rejected) + 1, args.schema_attempts + 1):
                prompt = {"client": args.client, "role": role, "role_boundary": ROLE_RULES[args.client][role], "task_type": label, "parent_role_bank": repository, "trajectories": trajectories, "maximum_findings": 8, "maximum_recommendation_characters": 600, "maximum_affected_skill_ids": 12, "maximum_evidence_refs": 16, "previous_validation_error": previous_error, "instruction": "Analyze this role's trajectories. Return 0-8 concise evidence-grounded findings for KEEP/UPDATE/DELETE/MOVE/ADD consideration. Do not emit patch operations. Return one JSON object with only findings; do not copy the response_format type=json_object transport setting."}
                value, record = _call_and_check(config, prompt, "Analyze one role and task family conservatively.", args, attempts / f"family_{role.replace(' ', '_')}_{type_id:02d}_schema_{attempt:02d}", "findings")
                try:
                    findings = validate_family_findings(value, family_refs, ids)
                    checkpoint["findings"][role][label] = findings
                    checkpoint["records"].append({"stage": "family", "role": role, "task_type": label, "attempt": attempt, **record})
                    write_json(checkpoint_path, checkpoint)
                    break
                except EvolutionError as exc:
                    previous_error = str(exc)
                    checkpoint["records"].append({"stage": "family_rejected", "role": role, "task_type": label, "attempt": attempt, "error": previous_error, **record})
                    write_json(checkpoint_path, checkpoint)
            else:
                raise EvolutionError(f"{role}/{label}: finding attempt limit reached")

        role_state = checkpoint["role_patches"].setdefault(role, {})
        base_ops = role_state.get("base_operations")
        if base_ops is not None:
            _, checked, base_counts = role_patch(repository, role, {"operations": base_ops}, allowed_refs, args.client, args.generation, allowed_operations={"DELETE", "UPDATE"})
            if checked != base_ops or base_counts != role_state.get("base_counts"):
                raise EvolutionError(f"{role}: frozen DELETE/UPDATE checkpoint changed")
        else:
            rejected = [row for row in checkpoint["records"] if row.get("stage") == "base_rejected" and row.get("role") == role]
            previous_error = rejected[-1]["error"] if rejected else None
            for attempt in range(len(rejected) + 1, args.schema_attempts + 1):
                prompt = {"client": args.client, "generation": args.generation, "role": role, "parent_role_bank": repository, "allowed_target_ids": sorted(ids), "family_findings": checkpoint["findings"][role], "role_boundary": ROLE_RULES[args.client][role], "previous_validation_error": previous_error, "instruction": "Return DELETE/UPDATE operations only. Each target_role must equal the supplied role and target_skill_id must belong to its allowlist. Each operation needs a real training evidence_ref. Do not emit ADD, KEEP, NONE, or MERGE. Return only one JSON object with operations."}
                value, record = _call_and_check(config, prompt, "Compose role-local DELETE/UPDATE operations only.", args, attempts / f"base_{role.replace(' ', '_')}_schema_{attempt:02d}", "operations")
                try:
                    _, base_ops, base_counts = role_patch(repository, role, value, allowed_refs, args.client, args.generation, allowed_operations={"DELETE", "UPDATE"})
                    role_state.update(base_operations=base_ops, base_counts=base_counts, max_add=base_counts["delete"] // 3)
                    checkpoint["records"].append({"stage": "base", "role": role, "attempt": attempt, "counts": base_counts, **record})
                    write_json(checkpoint_path, checkpoint)
                    break
                except EvolutionError as exc:
                    previous_error = str(exc)
                    checkpoint["records"].append({"stage": "base_rejected", "role": role, "attempt": attempt, "error": previous_error, **record})
                    write_json(checkpoint_path, checkpoint)
            else:
                raise EvolutionError(f"{role}: DELETE/UPDATE attempt limit reached")
        if "operations" in role_state:
            value = {"operations": role_state["operations"]}
            candidate, clean, counts = role_patch(repository, role, value, allowed_refs, args.client, args.generation)
            if counts != role_state.get("counts"):
                raise EvolutionError(f"{role}: frozen final role patch changed")
            continue
        max_add = role_state["max_add"]
        if max_add == 0:
            candidate, clean, counts = role_patch(repository, role, {"operations": base_ops}, allowed_refs, args.client, args.generation)
        else:
            rejected = [row for row in checkpoint["records"] if row.get("stage") == "add_rejected" and row.get("role") == role]
            previous_error = rejected[-1]["error"] if rejected else None
            for attempt in range(len(rejected) + 1, args.schema_attempts + 1):
                prompt = {"client": args.client, "generation": args.generation, "role": role, "max_add": max_add, "frozen_delete_update": base_ops, "family_findings": checkpoint["findings"][role], "role_boundary": ROLE_RULES[args.client][role], "previous_validation_error": previous_error, "instruction": f"Return 0 to {max_add} ADD operations for this role only. The DELETE/UPDATE stage is frozen. Prefer no ADD over speculative content. Return only one JSON object with operations."}
                value, record = _call_and_check(config, prompt, "Compose role-local ADD operations only.", args, attempts / f"add_{role.replace(' ', '_')}_schema_{attempt:02d}", "operations")
                try:
                    combined = combine_adds(base_ops, value, max_add)
                    candidate, clean, counts = role_patch(repository, role, combined, allowed_refs, args.client, args.generation)
                    checkpoint["records"].append({"stage": "add", "role": role, "attempt": attempt, "counts": counts, **record})
                    break
                except EvolutionError as exc:
                    previous_error = str(exc)
                    checkpoint["records"].append({"stage": "add_rejected", "role": role, "attempt": attempt, "error": previous_error, **record})
                    write_json(checkpoint_path, checkpoint)
            else:
                raise EvolutionError(f"{role}: ADD attempt limit reached")
        role_state.update(operations=clean, counts=counts, candidate_sha256=object_hash(candidate))
        write_json(checkpoint_path, checkpoint)

    role_repositories: dict[str, Any] = {}
    per_role: dict[str, Any] = {}
    for role in roles:
        repository = parent["active_skillbanks"][role]
        state = checkpoint["role_patches"][role]
        candidate, _, counts = role_patch(repository, role, {"operations": state["operations"]}, allowed_refs, args.client, args.generation)
        if object_hash(candidate) != state["candidate_sha256"] or counts != state["counts"]:
            raise EvolutionError(f"{role}: checkpoint candidate mismatch")
        role_repositories[role] = candidate
        per_role[role] = {**counts, "max_add": counts["delete"] // 3, "quota_passed": counts["add"] <= counts["delete"] // 3}
    bank = {"bank_schema_version": SCHEMA, "schema_version": SCHEMA, "experiment_id": args.experiment_id, "source_client": args.client, "target_client": args.client, "client": args.client, "generation": args.generation, "parent_kind": args.parent_kind, "parent_bank_file_sha256": file_hash(args.parent_bank), "evidence_file_sha256": file_hash(args.evidence), "active_skillbanks": role_repositories, "capacity_policy": {"scope": "per_role_per_round", "per_role": per_role, "quota_passed": all(row["quota_passed"] for row in per_role.values())}, "teacher": descriptor}
    bank["live_repository_sha256"] = object_hash(role_repositories)
    parse_bank(bank, args.client)
    patch = {"schema_version": "stage2_local_v11.role_patches.v1", "client": args.client, "generation": args.generation, "parent_bank_file_sha256": file_hash(args.parent_bank), "per_role": {role: {"operations": checkpoint["role_patches"][role]["operations"], "counts": per_role[role]} for role in roles}, "candidate_live_repository_sha256": bank["live_repository_sha256"]}
    write_json(args.patch_output, patch)
    write_json(args.output, bank)
    write_json(args.record_output, {"schema_version": "stage2_local_v11.teacher_record.v1", **identity, "capacity_policy": bank["capacity_policy"], "patch_file_sha256": file_hash(args.patch_output), "bank_file_sha256": file_hash(args.output), "records": checkpoint["records"]})
    return {"status": "complete", "client": args.client, "generation": args.generation, "capacity_policy": bank["capacity_policy"], "bank": str(args.output)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", choices=tuple("ABC"), required=True)
    parser.add_argument("--generation", type=int, required=True)
    parser.add_argument("--parent-kind", choices=("independent", "global"), required=True)
    parser.add_argument("--parent-bank", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--patch-output", type=Path, required=True)
    parser.add_argument("--record-output", type=Path, required=True)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--seed", type=int, default=1234)
    parser.add_argument("--max-tokens", type=int, default=16000)
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--truncation-retries", type=int, default=2)
    parser.add_argument("--schema-attempts", type=int, default=3)
    args = parser.parse_args()
    if args.generation < 2 or args.schema_attempts not in range(1, 4):
        parser.error("generation >=2 and schema-attempts 1..3 required")
    print(json.dumps(evolve(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
