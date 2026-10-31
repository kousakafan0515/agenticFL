"""Verify or copy the bundled frozen v9 B0->B1 seeds used by V10/V12."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from stage2_local_v12.clients.skillbank_loader import EXPECTED_ROLES, parse_bank
from stage2_local_v12.runtime.banks import file_hash, write_json
from stage2_local_v12.evolution.local_round2_evolver import parse_json_object
from stage2_local_v12.evolution.role_evolver import repository_rows


ROOT = Path(__file__).resolve().parents[2]
BUNDLED_SEED = ROOT / "stage2_local_v12" / "assets" / "seeds" / "imported_v9_b0_to_b1_20261018_r1"
SCHEMA = "stage2_local_v10.imported_v9_b0_b1_seed.v1"
B1_HASHES = {
    "A": "sha256:84218a56b828fe08b81bd476c62d32950f61764b13390e957fd22c430bf24db4",
    "B": "sha256:4e42c1ff6d63a913279fe9405f67b753bebb42c98a4c78fe2c03d08d6f80a1b1",
    "C": "sha256:4702aeac4b6b7b759b1868d124ec8209616806eb16e3a0f2fbc3eacbc006da5d",
}


def verify_import(client_root: Path, client: str) -> dict[str, Any]:
    imported = json.loads((client_root / "import_manifest.json").read_text(encoding="utf-8"))
    if imported.get("schema_version") != SCHEMA or imported.get("client") != client:
        raise RuntimeError(f"Client {client}: imported seed manifest identity mismatch")
    files = imported.get("files")
    if not isinstance(files, dict) or not files:
        raise RuntimeError(f"Client {client}: imported seed file manifest missing")
    for relative, expected_hash in files.items():
        path = client_root / relative
        if not path.is_file() or file_hash(path) != expected_hash:
            raise RuntimeError(f"Client {client}: imported {relative} bytes changed")
    bank_path = client_root / "B1_skillbank.json"
    if file_hash(bank_path) != B1_HASHES[client]:
        raise RuntimeError(f"Client {client}: bundled B1 hash changed")
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    parse_bank(bank, client)
    if bank.get("generation") != 1 or bank.get("target_client") != client:
        raise RuntimeError(f"Client {client}: B1 origin identity mismatch")
    for directory, generation, phase in (
        ("B0_validation", 0, "validation"),
        ("B0_training", 1, "training"),
        ("B1_validation", 1, "validation"),
    ):
        summary = json.loads((client_root / directory / "summary.json").read_text(encoding="utf-8"))
        expected = {
            "status": "complete", "client": client, "generation": generation,
            "phase": phase, "task_count": 134, "api_clean": True,
        }
        if any(summary.get(key) != value for key, value in expected.items()):
            raise RuntimeError(f"Client {client}: incomplete {directory}")
    evidence = json.loads((client_root / "B0_training" / "evidence.json").read_text(encoding="utf-8"))
    if evidence.get("client_id") != client or len(evidence.get("episodes") or []) != 134:
        raise RuntimeError(f"Client {client}: B0 training evidence mismatch")
    teacher = json.loads((client_root / "B1_teacher_record.json").read_text(encoding="utf-8"))
    descriptor = teacher.get("teacher_endpoint") or {}
    if teacher.get("teacher_model") != "deepseek-flash" or descriptor.get("provider") != "deepseek_official":
        raise RuntimeError(f"Client {client}: B1 Teacher identity mismatch")
    family_records = [row for row in teacher.get("records", []) if row.get("stage") == "family_analysis"]
    if len(family_records) != len(EXPECTED_ROLES[client]) * 6:
        raise RuntimeError(f"Client {client}: family analysis count mismatch")
    for row in family_records:
        candidates = parse_json_object(row.get("raw_model_output") or "").get("candidates")
        if not isinstance(candidates, list) or len(candidates) > 4 or any(
            not isinstance(item, dict) or item.get("action") != "ADD" for item in candidates
        ):
            raise RuntimeError(f"Client {client}: B1 candidate rule mismatch")
    imported["verified_role_skill_counts"] = {
        role: len(repository_rows(bank["active_skillbanks"][role]))
        for role in EXPECTED_ROLES[client]
    }
    return imported


def verify_imported_seed(bank_path: Path, validation_path: Path, client: str) -> dict[str, Any]:
    client_root = bank_path.parent
    if bank_path != client_root / "B1_skillbank.json" or validation_path != client_root / "B1_validation" / "summary.json":
        raise RuntimeError(f"Client {client}: imported seed paths must match the frozen layout")
    manifest = verify_import(client_root, client)
    if file_hash(bank_path) != B1_HASHES[client]:
        raise RuntimeError(f"Client {client}: imported B1 seed hash mismatch")
    return manifest


def import_all(destination: Path) -> dict[str, Any]:
    if destination.exists():
        raise RuntimeError(f"refusing to overwrite existing import root: {destination}")
    for client in "ABC":
        verify_import(BUNDLED_SEED / f"client_{client}", client)
    shutil.copytree(BUNDLED_SEED, destination)
    clients = {
        client: verify_import(destination / f"client_{client}", client)["validation_success"]
        for client in "ABC"
    }
    write_json(destination / "v12_copy_record.json", {
        "status": "copied_from_bundled_seed", "source": str(BUNDLED_SEED), "clients": clients,
    })
    return {"status": "copied", "root": str(destination), "clients": clients}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, default=BUNDLED_SEED)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = (
        {
            "status": "verified",
            "clients": {
                client: verify_import(args.destination / f"client_{client}", client)["validation_success"]
                for client in "ABC"
            },
        }
        if args.check else import_all(args.destination)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
