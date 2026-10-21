"""Materialize Client B/C manifests and explicit empty B0 repositories."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from client_code.skillbank_loader import EXPECTED_ROLES, TASK_TYPE_LABELS, parse_bank
from originalFL.banks import canonical_bytes
from originalFL.build_task_manifests import object_hash
from stage2_local_v9.scripts.materialize_manifest import ROOT, build as build_a_manifest


CLIENTS = ("B", "C")


def experiment_id(client: str) -> str:
    return f"stage2-local-v9-client-{client.lower()}-v6-no-capacity-control"


def build_manifest(client: str) -> dict:
    if client not in CLIENTS:
        raise ValueError(client)
    body = build_a_manifest()
    body["experiment_id"] = experiment_id(client)
    body["target_client"] = client
    body["derived_from_manifest"] = {
        "path": "stage2_local_v9/artifacts/manifests/client_a_generation_01.json",
        "relationship": "identical frozen training and validation task cohorts; client-specific execution",
    }
    body["invariants"]["target_client"] = client
    content = {key: value for key, value in body.items() if key not in {"generated_at", "manifest_content_hash"}}
    body["manifest_content_hash"] = object_hash(content)
    return body


def build_empty_bank(client: str) -> dict:
    if client not in CLIENTS:
        raise ValueError(client)
    empty_role = lambda: {
        "general": [],
        "task_specific": {label: [] for label in TASK_TYPE_LABELS.values()},
    }
    bank = {
        "bank_schema_version": "patchFL.role_repository.v3",
        "experiment_id": experiment_id(client),
        "source_client": client,
        "target_client": client,
        "generation": 0,
        "parent_bank": None,
        "maximum_skill_field_characters": 900,
        "active_skillbanks": {role: empty_role() for role in EXPECTED_ROLES[client]},
    }
    parse_bank(bank, client)
    return bank


def destinations(client: str) -> tuple[Path, Path]:
    lower = client.lower()
    return (
        ROOT / f"stage2_local_v9/artifacts/manifests/client_{lower}_generation_01.json",
        ROOT / f"stage2_local_v9/templates/client_{lower}_B0_empty_skillbank.json",
    )


def encoded(value: dict) -> bytes:
    return canonical_bytes(value) + b"\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = {}
    for client in CLIENTS:
        manifest_path, bank_path = destinations(client)
        expected = ((manifest_path, encoded(build_manifest(client))), (bank_path, encoded(build_empty_bank(client))))
        for path, payload in expected:
            if args.check:
                if not path.is_file() or path.read_bytes() != payload:
                    raise SystemExit(f"asset mismatch: {path}")
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.exists() and path.read_bytes() != payload:
                    raise SystemExit(f"refusing to overwrite different asset: {path}")
                path.write_bytes(payload)
        report[client] = {"manifest": str(manifest_path), "empty_b0": str(bank_path)}
    print(json.dumps({"status": "pass" if args.check else "written", "clients": report}, indent=2))


if __name__ == "__main__":
    main()
