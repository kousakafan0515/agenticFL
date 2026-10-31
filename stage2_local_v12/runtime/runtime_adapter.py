"""Convert one logical originalFL bank into the existing client runtime format.

The originalFL bank is deliberately role-agnostic.  For this baseline the same
two General plus two matching task skills are exposed to every role of a
client.  Role permissions and action formats remain controlled by each
client's base prompt.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from stage2_local_v12.clients.skillbank_loader import (
    BLIND_GLOBAL_RENDERER_VERSION, COLLABORATOR_RENDERER_VERSION,
    EXPECTED_ROLES, TASK_TYPE_LABELS, SkillBankLoader, bank_hash as loader_bank_hash,
    build_capacity_profile, file_hash as loader_file_hash, parse_bank,
)
from stage2_local_v12.runtime.banks import bank_hash as logical_bank_hash, write_json


def _runtime_skill(skill: dict[str, Any], priority: int, source_key: str) -> dict[str, Any]:
    procedure = " ".join(str(item).strip() for item in skill["procedure"])
    avoids = " ".join(f"Avoid: {str(item).strip()}" for item in skill.get("avoid", []))
    principle = " ".join(value for value in (procedure, avoids) if value)
    return {
        "skill_id": skill.get("skill_id") or skill["global_skill_id"],
        "type": "Procedure or Local Strategy",
        "title": skill["title"],
        "principle": principle,
        "when_to_apply": skill["trigger"],
        "source_skill_keys": [source_key],
        "runtime_priority": priority,
    }


def build_adapter(logical_bank: dict[str, Any], client_id: str, output_dir: Path) -> dict[str, str]:
    if client_id not in EXPECTED_ROLES:
        raise ValueError("client_id must be A, B, or C")
    if logical_bank.get("schema_version") == "patchFL.global_role_repository.v1":
        return _build_global_repository_adapter(logical_bank, client_id, output_dir)
    if "active_skillbanks" in logical_bank:
        renderer = (
            BLIND_GLOBAL_RENDERER_VERSION
            if logical_bank.get("bank_schema_version") == "stage3_2.client_complete_global_replacement.v1"
            else COLLABORATOR_RENDERER_VERSION
        )
        return _build_role_repository_adapter(logical_bank, client_id, output_dir, renderer)
    active: dict[str, Any] = {}
    for role in EXPECTED_ROLES[client_id]:
        def identity(skill: dict[str, Any]) -> str:
            return str(skill.get("skill_id") or skill["global_skill_id"])

        general = [
            _runtime_skill(skill, index, f"originalFL/{client_id}/general/{identity(skill)}")
            for index, skill in enumerate(logical_bank.get("general_skills", []), start=1)
        ]
        task_specific: dict[str, list[dict[str, Any]]] = {}
        for task_type, label in TASK_TYPE_LABELS.items():
            rows = logical_bank.get("task_specific_skills", {}).get(str(task_type), [])
            task_specific[label] = [
                _runtime_skill(
                    skill, len(general) + index,
                    f"originalFL/{client_id}/task_specific/{task_type}/{identity(skill)}",
                )
                for index, skill in enumerate(rows, start=1)
            ]
        active[role] = {"general": general, "task_specific": task_specific}
    logical_hash = logical_bank_hash(logical_bank)
    bank_doc = {
        "bank_schema_version": "originalFL.runtime_adapter.v1",
        "target_client": client_id,
        "aggregation_mode": "originalFL_complete_snapshot",
        "global_pool_hash": logical_hash,
        "active_skillbanks": active,
    }
    bank_path = output_dir / "runtime_skillbank.json"
    manifest_path = output_dir / "runtime_manifest.json"
    profile_path = output_dir / "runtime_capacity_profile.json"
    write_json(bank_path, bank_doc)
    semantic_hash = loader_bank_hash(parse_bank(bank_doc, client_id))
    manifest = {
        "manifest_schema_version": "stage3_1.global_adapter_bank_manifest.v1",
        "target_client": client_id,
        "aggregation_mode": "originalFL_complete_snapshot",
        "global_pool_hash": logical_hash,
        "global_pool_file_sha256": logical_hash,
        "global_adapter_bank_file_sha256": loader_file_hash(bank_path),
        "global_adapter_bank_hash": semantic_hash,
        "source_input_set_hash": logical_hash,
    }
    write_json(manifest_path, manifest)
    loader = SkillBankLoader(
        mode="global", expected_client_id=client_id, bank_path=bank_path,
        manifest_path=manifest_path, enforce_capacity=False,
    )
    write_json(profile_path, build_capacity_profile(loader))
    SkillBankLoader(
        mode="global", expected_client_id=client_id, bank_path=bank_path,
        manifest_path=manifest_path, capacity_profile_path=profile_path,
    )
    return {
        "skillbank": str(bank_path), "manifest": str(manifest_path),
        "capacity_profile": str(profile_path), "logical_bank_sha256": logical_hash,
        "runtime_bank_sha256": semantic_hash,
    }


def _build_role_repository_adapter(
    bank_doc: dict[str, Any],
    client_id: str,
    output_dir: Path,
    renderer_version: str = COLLABORATOR_RENDERER_VERSION,
) -> dict[str, str]:
    """Wrap a PatchFL v3 role-isolated repository for the existing client loader."""
    skills = parse_bank(bank_doc, client_id)
    semantic_hash = loader_bank_hash(skills)
    bank_path = output_dir / "runtime_skillbank.json"
    manifest_path = output_dir / "runtime_manifest.json"
    profile_path = output_dir / "runtime_capacity_profile.json"
    write_json(bank_path, bank_doc)
    manifest = {
        "manifest_schema_version": "stage3_1.global_adapter_bank_manifest.v1",
        "target_client": client_id,
        "aggregation_mode": "patchFL_v3_complete_role_repository",
        "global_pool_hash": semantic_hash,
        "global_pool_file_sha256": loader_file_hash(bank_path),
        "global_adapter_bank_file_sha256": loader_file_hash(bank_path),
        "global_adapter_bank_hash": semantic_hash,
        "source_input_set_hash": semantic_hash,
    }
    write_json(manifest_path, manifest)
    loader = SkillBankLoader(
        mode="global", expected_client_id=client_id, bank_path=bank_path,
        manifest_path=manifest_path, enforce_capacity=False,
        renderer_version=renderer_version,
    )
    write_json(profile_path, build_capacity_profile(loader))
    SkillBankLoader(
        mode="global", expected_client_id=client_id, bank_path=bank_path,
        manifest_path=manifest_path, capacity_profile_path=profile_path,
        renderer_version=renderer_version,
    )
    return {
        "skillbank": str(bank_path), "manifest": str(manifest_path),
        "capacity_profile": str(profile_path), "logical_bank_sha256": semantic_hash,
        "runtime_bank_sha256": semantic_hash,
    }


def _build_global_repository_adapter(repository: dict[str, Any], client_id: str, output_dir: Path) -> dict[str, str]:
    """Create a local runtime view from one byte-identical downloaded Global.

    This is not a server projection: every client stores the same complete
    repository.  The view only satisfies the existing role-shaped prompt
    loader at execution time.
    """
    roles = repository.get("role_partitions")
    if not isinstance(roles, dict):
        raise ValueError("Global repository requires role_partitions")
    missing = [role for role in EXPECTED_ROLES[client_id] if role not in roles]
    if missing:
        raise ValueError(f"Global repository lacks runtime roles: {missing}")
    bank_doc = {
        "bank_schema_version": "patchFL.role_repository.v3",
        "experiment_id": repository.get("experiment_id"),
        "source_client": client_id,
        "target_client": client_id,
        "aggregation_mode": "local_runtime_view_of_complete_global_download",
        "global_repository_sha256": repository.get("live_repository_sha256"),
        "round_index": repository.get("round_index"),
        "active_skillbanks": {role: roles[role] for role in EXPECTED_ROLES[client_id]},
        "tombstones": repository.get("tombstones", []),
    }
    result = _build_role_repository_adapter(bank_doc, client_id, output_dir)
    result["downloaded_global_repository_sha256"] = str(repository.get("live_repository_sha256"))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an originalFL runtime adapter")
    parser.add_argument("--bank", type=Path, required=True)
    parser.add_argument("--client", choices=tuple(EXPECTED_ROLES), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build_adapter(json.loads(args.bank.read_text(encoding="utf-8")), args.client, args.output_dir), indent=2))


if __name__ == "__main__":
    main()
