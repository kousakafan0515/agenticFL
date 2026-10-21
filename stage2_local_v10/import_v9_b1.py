"""Audit and copy frozen v9 B0->B1 results as explicitly labelled v10 seeds.

This does not rewrite the v9 experiment identity, source locks, or scores. The
imported files can seed v10 B2 / Global1, but remain v9 B0/B1 observations.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any

from client_code.skillbank_loader import EXPECTED_ROLES, parse_bank
from originalFL.banks import file_hash, write_json
from stage3_2_role_agnostic_semantic_merge.local_round2_evolver import parse_json_object
from stage2_local_v10.materialize_assets import EXPERIMENT_ID
from stage2_local_v10.role_evolver import repository_rows


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "stage2_local_v10.imported_v9_b0_b1_seed.v1"
SOURCES = {
    "A": ("client_a_generation_01_20261013_r1", "84218a56b828fe08b81bd476c62d32950f61764b13390e957fd22c430bf24db4"),
    "B": ("client_b_generation_01_20261013_r3", "4e42c1ff6d63a913279fe9405f67b753bebb42c98a4c78fe2c03d08d6f80a1b1"),
    "C": ("client_c_generation_01_20261013_r3", "4702aeac4b6b7b759b1868d124ec8209616806eb16e3a0f2fbc3eacbc006da5d"),
}
COPIED_FILES = (
    "B0_validation/result.json", "B0_validation/summary.json", "B0_validation/source_lock.json",
    "B0_training/result.json", "B0_training/summary.json", "B0_training/source_lock.json",
    "B0_training/evidence.json", "B1_skillbank.json", "B1_teacher_record.json",
    "B1_teacher_record.checkpoint.json", "B1_validation/result.json",
    "B1_validation/summary.json", "B1_validation/source_lock.json",
)


def source_root(client: str) -> Path:
    return ROOT / "stage2_local_v9" / "runs" / SOURCES[client][0]


def inspect_source(client: str) -> dict[str, Any]:
    """Check the original evidence before any destination file is written."""
    source = source_root(client)
    manifest9 = ROOT / "stage2_local_v9" / "artifacts" / "manifests" / f"client_{client.lower()}_generation_01.json"
    manifest10 = ROOT / "stage2_local_v10" / "artifacts" / "manifests" / f"client_{client.lower()}_generation_01.json"
    m9 = json.loads(manifest9.read_text(encoding="utf-8"))
    m10 = json.loads(manifest10.read_text(encoding="utf-8"))
    if m10.get("experiment_id") != EXPERIMENT_ID or any(m9.get(key) != m10.get(key) for key in ("task_types", "training", "validation")):
        raise RuntimeError(f"Client {client}: v9/v10 frozen task cohorts differ")
    bank_path = source / "B1_skillbank.json"
    if file_hash(bank_path) != "sha256:" + SOURCES[client][1]:
        raise RuntimeError(f"Client {client}: frozen v9 B1 hash changed")
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    parse_bank(bank, client)
    if bank.get("generation") != 1 or bank.get("target_client") != client or bank.get("experiment_id") != m9.get("experiment_id"):
        raise RuntimeError(f"Client {client}: B1 origin identity mismatch")
    for directory, generation, phase in (("B0_validation", 0, "validation"), ("B0_training", 1, "training"), ("B1_validation", 1, "validation")):
        root = source / directory
        summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
        lock = json.loads((root / "source_lock.json").read_text(encoding="utf-8"))
        expected = {"status": "complete", "client": client, "generation": generation, "phase": phase, "task_count": 134, "api_clean": True}
        if any(summary.get(key) != value for key, value in expected.items()):
            raise RuntimeError(f"Client {client}: incomplete {directory}")
        if summary.get("result_file_sha256") != file_hash(root / "result.json") or lock.get("manifest_file_sha256") != file_hash(manifest9):
            raise RuntimeError(f"Client {client}: {directory} result or cohort lock changed")
        expected_bank_hash = file_hash(bank_path) if directory == "B1_validation" else None
        if lock.get("bank_file_sha256") != expected_bank_hash:
            raise RuntimeError(f"Client {client}: {directory} bank lock changed")
    evidence_path = source / "B0_training" / "evidence.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if evidence.get("client_id") != client or evidence.get("generation") != 1 or evidence.get("experiment_id") != m9.get("experiment_id") or len(evidence.get("episodes") or []) != 134:
        raise RuntimeError(f"Client {client}: B0 training evidence identity mismatch")
    teacher = json.loads((source / "B1_teacher_record.json").read_text(encoding="utf-8"))
    descriptor = teacher.get("teacher_endpoint") or {}
    if (teacher.get("teacher_model") != "deepseek-flash" or descriptor.get("provider") != "deepseek_official"
            or descriptor.get("endpoint_origin") != "https://api.deepseek.com"
            or teacher.get("evidence_file_sha256") != file_hash(evidence_path)
            or bank.get("evidence_file_sha256") != file_hash(evidence_path)):
        raise RuntimeError(f"Client {client}: B1 Teacher or evidence provenance mismatch")
    family_records = [row for row in teacher.get("records", []) if row.get("stage") == "family_analysis"]
    if len(family_records) != len(EXPECTED_ROLES[client]) * 6 or len({(row.get("role"), row.get("task_type_id")) for row in family_records}) != len(family_records):
        raise RuntimeError(f"Client {client}: missing or duplicate family analyses")
    candidate_count = 0
    for row in family_records:
        if row.get("role") not in EXPECTED_ROLES[client] or row.get("task_type_id") not in range(1, 7):
            raise RuntimeError(f"Client {client}: unknown candidate role or task type")
        candidates = parse_json_object(row.get("raw_model_output") or "").get("candidates")
        if not isinstance(candidates, list) or len(candidates) > 4 or any(
            not isinstance(item, dict) or item.get("action") != "ADD" or item.get("source_skill_ids") not in (None, [])
            for item in candidates
        ):
            raise RuntimeError(f"Client {client}: v9 candidates violate v10 empty-B0 ADD rule")
        candidate_count += len(candidates)
    paths = {relative: file_hash(source / relative) for relative in COPIED_FILES}
    return {
        "schema_version": SCHEMA, "classification": "imported_v9_seed_not_native_v10_B1",
        "client": client, "origin_experiment_id": m9["experiment_id"],
        "source_run": str(source), "source_manifest": str(manifest9),
        "source_manifest_sha256": file_hash(manifest9), "v10_manifest": str(manifest10),
        "v10_manifest_sha256": file_hash(manifest10), "cohort_equal": True,
        "family_analysis_count": len(family_records), "add_candidate_count": candidate_count,
        "non_add_candidate_count": 0,
        "role_skill_counts": {role: len(repository_rows(bank["active_skillbanks"][role])) for role in EXPECTED_ROLES[client]},
        "validation_success": {phase: json.loads((source / phase / "summary.json").read_text(encoding="utf-8"))["success_count"] for phase in ("B0_validation", "B1_validation")},
        "files": paths,
    }


def verify_import(client_root: Path, client: str) -> dict[str, Any]:
    manifest_path = client_root / "import_manifest.json"
    imported = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = inspect_source(client)
    def portable_path(value: str) -> str:
        normalized = value.replace("\\", "/")
        match = re.fullmatch(r"([A-Za-z]):/(.*)", normalized)
        return f"/mnt/{match.group(1).lower()}/{match.group(2)}" if match else normalized

    path_fields = {"source_run", "source_manifest", "v10_manifest"}
    if any(imported.get(key) != value for key, value in source.items() if key not in path_fields) or any(
        not isinstance(imported.get(key), str) or portable_path(imported[key]) != portable_path(source[key]) for key in path_fields
    ) or set(imported) != set(source):
        raise RuntimeError(f"Client {client}: import manifest no longer matches frozen v9 source")
    for relative, expected_hash in imported["files"].items():
        if file_hash(client_root / relative) != expected_hash:
            raise RuntimeError(f"Client {client}: imported {relative} bytes changed")
    return imported


def verify_imported_seed(bank_path: Path, validation_path: Path, client: str) -> dict[str, Any]:
    """Guard the only allowed v9 B1 seed layout for later v10 controllers."""
    client_root = bank_path.parent
    if bank_path != client_root / "B1_skillbank.json" or validation_path != client_root / "B1_validation" / "summary.json":
        raise RuntimeError(f"Client {client}: imported seed paths must match the frozen layout")
    manifest = verify_import(client_root, client)
    if manifest["files"]["B1_skillbank.json"] != file_hash(bank_path):
        raise RuntimeError(f"Client {client}: imported B1 seed hash mismatch")
    return manifest


def import_all(destination: Path) -> dict[str, Any]:
    if destination.exists():
        raise RuntimeError(f"refusing to overwrite existing import root: {destination}")
    inspections = {client: inspect_source(client) for client in "ABC"}
    destination.mkdir(parents=True)
    for client, manifest in inspections.items():
        target = destination / f"client_{client}"
        for relative in COPIED_FILES:
            path = target / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_root(client) / relative, path)
            if file_hash(path) != manifest["files"][relative]:
                raise RuntimeError(f"Client {client}: copied {relative} hash mismatch")
        write_json(target / "import_manifest.json", manifest)
        verify_import(target, client)
    return {"status": "imported_v9_seed", "root": str(destination), "clients": {client: {"B0": item["validation_success"]["B0_validation"], "B1": item["validation_success"]["B1_validation"], "role_skill_counts": item["role_skill_counts"], "add_candidates": item["add_candidate_count"]} for client, item in inspections.items()}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        print(json.dumps({"status": "verified", "clients": {client: verify_import(args.destination / f"client_{client}", client)["validation_success"] for client in "ABC"}}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(import_all(args.destination), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
