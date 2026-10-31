"""Verify the frozen, self-contained V10-compatible V12 assets."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "stage2_local_v12" / "assets"
EXPERIMENT_ID = "stage2-local-v10-role-partitioned-patch3"
IMPLEMENTATION_ID = "stage2-local-v12-self-contained-v1"
PROTOCOL_ID = EXPERIMENT_ID
LOCKS = {
    "A": {
        "manifest": "bf6e368f688ccdbe7f9d6d43809ba7571a17910f4ef44e7468d4229dca88cee9",
        "empty_b0": "ee7d1341f002a595c8b5d9f7537bb5e54fc2d1f13f91721cdb659797794577e3",
    },
    "B": {
        "manifest": "a1940aed56c5648b46dc03a0cb3a5769a76a7b146825bd3760f99ea22147a8ce",
        "empty_b0": "d8051d7ad86588eb4d0d38b5a27e9460544d1c6592c0cd9ed3799f3e15751994",
    },
    "C": {
        "manifest": "fcce17dfeeac800fe76a47e3efcc1baee1238e4e36d16a8c6ebd20bbdb6b9535",
        "empty_b0": "eaddca0ba6c45b418adef28da045af87b32e7033cd985de3565cc0226d1d383d",
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def materialize(check: bool = False) -> dict:
    """Compatibility name retained for controllers; V12 assets are immutable."""
    result: dict[str, dict[str, str]] = {}
    for client in "ABC":
        lower = client.lower()
        paths = {
            "manifest": ASSETS / "manifests" / f"client_{lower}_generation_01.json",
            "empty_b0": ASSETS / "templates" / f"client_{lower}_B0_empty_skillbank.json",
        }
        for kind, path in paths.items():
            if not path.is_file() or _sha256(path) != LOCKS[client][kind]:
                raise RuntimeError(f"Client {client}: frozen V12 {kind} missing or changed: {path}")
        manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
        bank = json.loads(paths["empty_b0"].read_text(encoding="utf-8"))
        if manifest.get("experiment_id") != EXPERIMENT_ID or bank.get("experiment_id") != EXPERIMENT_ID:
            raise RuntimeError(f"Client {client}: frozen V10 protocol identity changed")
        result[client] = {
            "manifest": str(paths["manifest"]),
            "empty_b0": str(paths["empty_b0"]),
            "manifest_sha256": "sha256:" + LOCKS[client]["manifest"],
            "empty_b0_sha256": "sha256:" + LOCKS[client]["empty_b0"],
        }
    return {
        "status": "checked",
        "implementation_id": IMPLEMENTATION_ID,
        "protocol_id": PROTOCOL_ID,
        "clients": result,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="retained for V10 CLI compatibility")
    parser.parse_args()
    print(json.dumps(materialize(check=True), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
