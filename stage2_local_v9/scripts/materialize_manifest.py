"""Materialize the v9 manifest from the exact frozen v6 task cohorts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from originalFL.build_task_manifests import canonical_bytes, object_hash


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "stage2_local_v6/artifacts/manifests/client_a_generation_01.json"
SOURCE_SHA256 = "c97719544c442a4e52079adc1a41cc43427cd780b50367638760b9bde45a7fba"
EXPERIMENT_ID = "stage2-local-v9-v6-no-capacity-control"


def build() -> dict:
    raw = SOURCE.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != SOURCE_SHA256:
        raise RuntimeError(
            f"frozen v6 manifest changed; expected {SOURCE_SHA256}, got {actual}"
        )
    body = json.loads(raw.decode("utf-8"))
    body["experiment_id"] = EXPERIMENT_ID
    body["derived_from_manifest"] = {
        "path": "stage2_local_v6/artifacts/manifests/client_a_generation_01.json",
        "file_sha256": f"sha256:{SOURCE_SHA256}",
        "relationship": "identical training and validation task cohorts",
    }
    body["invariants"]["v6_task_cohorts_reused_for_control"] = True
    content = {key: value for key, value in body.items() if key not in {"generated_at", "manifest_content_hash"}}
    body["manifest_content_hash"] = object_hash(content)
    return body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "stage2_local_v9/artifacts/manifests/client_a_generation_01.json",
    )
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    body = build()
    encoded = canonical_bytes(body) + b"\n"
    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != encoded:
            raise SystemExit("v9 manifest does not match its frozen v6-derived definition")
        print(json.dumps({"status": "pass", "manifest_content_hash": body["manifest_content_hash"]}, indent=2))
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists() and args.output.read_bytes() != encoded:
        raise SystemExit(f"refusing to overwrite different manifest: {args.output}")
    args.output.write_bytes(encoded)
    print(json.dumps({"status": "written", "output": str(args.output), "manifest_content_hash": body["manifest_content_hash"]}, indent=2))


if __name__ == "__main__":
    main()
