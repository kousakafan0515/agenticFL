"""Freeze v10 manifests and empty B0 templates from byte-locked v9 assets."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from originalFL.build_task_manifests import canonical_bytes, object_hash


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT_ID = "stage2-local-v10-role-partitioned-patch3"
SOURCE_HASHES = {
    "A": ("f2ff004126692a04629b92198f8979ad0b451359fab8ba61b96de73409b81733", "22d7d014b23da4ec2168a59c2f6b3286ab14ae150a97269c168b24cf4a723419"),
    "B": ("66c1cfd111a286eaf2ff114d7ffb12eab23bebda4e65c224ee2f8e1f2af7e450", "d7028da45a84b066cf5a3356f50de027450f580ef91b3169ca54cfa9933ee309"),
    "C": ("8030fc279eb6e58f8b031592c18acd307d5b6e4ef39893b0aa3962c47ef73b78", "0b4bf4e9a3bb381be4cb218e92517f1dd1cce7652fc75ffc9b39073a2f25c518"),
}


def _read_locked(path: Path, expected: str) -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise RuntimeError(f"v9 source asset changed: {path}")
    return json.loads(raw.decode("utf-8"))


def build(client: str) -> tuple[dict, dict]:
    lower = client.lower()
    manifest_path = ROOT / "stage2_local_v9" / "artifacts" / "manifests" / f"client_{lower}_generation_01.json"
    bank_name = "B0_empty_skillbank.json" if client == "A" else f"client_{lower}_B0_empty_skillbank.json"
    bank_path = ROOT / "stage2_local_v9" / "templates" / bank_name
    manifest_hash, bank_hash = SOURCE_HASHES[client]
    manifest = _read_locked(manifest_path, manifest_hash)
    bank = _read_locked(bank_path, bank_hash)
    manifest["experiment_id"] = EXPERIMENT_ID
    manifest["derived_from_manifest"] = {"path": str(manifest_path.relative_to(ROOT)).replace("\\", "/"), "file_sha256": "sha256:" + manifest_hash, "relationship": "identical frozen 134 training and 134 validation tasks; v10 protocol identity"}
    manifest["invariants"]["v10_role_partitioned_teacher"] = True
    manifest["invariants"]["v10_per_role_patch3_quota"] = True
    content = {key: value for key, value in manifest.items() if key not in {"generated_at", "manifest_content_hash"}}
    manifest["manifest_content_hash"] = object_hash(content)
    bank["experiment_id"] = EXPERIMENT_ID
    return manifest, bank


def materialize(check: bool = False) -> dict:
    result = {}
    for client in "ABC":
        lower = client.lower()
        manifest, bank = build(client)
        paths = {
            "manifest": ROOT / "stage2_local_v10" / "artifacts" / "manifests" / f"client_{lower}_generation_01.json",
            "empty_b0": ROOT / "stage2_local_v10" / "templates" / f"client_{lower}_B0_empty_skillbank.json",
        }
        values = {"manifest": manifest, "empty_b0": bank}
        for kind, path in paths.items():
            encoded = canonical_bytes(values[kind]) + b"\n"
            if path.exists():
                if path.read_bytes() != encoded:
                    raise RuntimeError(f"refusing to replace changed v10 {kind}: {path}")
            elif check:
                raise RuntimeError(f"missing v10 {kind}: {path}")
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(encoded)
        result[client] = {"manifest": str(paths["manifest"]), "empty_b0": str(paths["empty_b0"]), "manifest_content_hash": manifest["manifest_content_hash"]}
    return {"status": "checked" if check else "materialized", "clients": result}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    print(json.dumps(materialize(check=args.check), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
