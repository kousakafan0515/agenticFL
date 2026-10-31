"""Build the V12 migration manifest; not imported by the runtime."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
V12 = ROOT / "stage2_local_v12"
OUTPUT = V12 / "provenance" / "SOURCE_MANIFEST.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def origin(relative: str) -> dict[str, str]:
    name = Path(relative).name
    if relative.startswith("clients/"):
        return {"relationship": "adapted internal copy", "source": f"client_code/{name}"}
    if relative.startswith("runtime/phase_runner_"):
        return {"relationship": "static materialization", "source": "v6 phase runner plus audited v9 client overlay"}
    if relative.startswith("evolution/bootstrap_bank_"):
        return {"relationship": "static materialization", "source": "stage2_local_v10.bootstrap_b1.v10_source"}
    if relative.startswith("runtime/"):
        return {"relationship": "adapted internal copy", "source": f"originalFL/{name}"}
    if relative.startswith("assets/manifests/"):
        return {"relationship": "byte-identical frozen asset", "source": f"stage2_local_v10/artifacts/manifests/{name}"}
    if relative.startswith("assets/templates/"):
        return {"relationship": "byte-identical frozen asset", "source": f"stage2_local_v10/templates/{name}"}
    if relative.startswith("assets/seeds/"):
        suffix = relative.split("assets/seeds/", 1)[1]
        return {"relationship": "byte-identical frozen seed", "source": f"stage2_local_v10/runs/{suffix}"}
    return {"relationship": "V12 migration source", "source": "see D-127 and file history"}


def main() -> None:
    entries = []
    for path in sorted(V12.rglob("*")):
        if not path.is_file() or path == OUTPUT or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        relative = path.relative_to(V12).as_posix()
        entries.append({"path": relative, "sha256": sha256(path), "bytes": path.stat().st_size, **origin(relative)})
    payload = {
        "schema_version": "stage2_local_v12.source_manifest.v1",
        "implementation_id": "stage2-local-v12-self-contained-v1",
        "protocol_id": "stage2-local-v10-role-partitioned-patch3",
        "file_count": len(entries),
        "files": entries,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
