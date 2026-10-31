"""Materialize and verify Client A/B/C runtime views of the D-094 Global bank.

The server download remains role-agnostic and byte-identical.  Runtime views only
duplicate the same seven buckets under each client's required role names so the
existing frozen client executors can consume the complete replacement bank.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from stage2_local_v12.clients.skillbank_loader import EXPECTED_ROLES, TASK_TYPE_LABELS, parse_bank


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_GLOBAL_SHA256 = "c55e5db60cccfcf011c633550c39cac268799972150eb34216ba442cf4ee6939"
EXPECTED_GLOBAL_SCHEMA = "stage3_2.role_agnostic_semantic_global.v1"
EXPECTED_GLOBAL_SKILLS = 43
TASK_LABELS = tuple(TASK_TYPE_LABELS.values())


class ReplacementError(RuntimeError):
    pass


def normalize_sha256(value: str) -> str:
    """Accept a bare digest or one sha256: prefix and return the bare digest."""
    if not isinstance(value, str):
        raise ReplacementError("SHA-256 value must be a string")
    normalized = value.strip().lower()
    if normalized.startswith("sha256:"):
        normalized = normalized[len("sha256:"):]
    if normalized.startswith("sha256:") or re.fullmatch(r"[0-9a-f]{64}", normalized) is None:
        raise ReplacementError(f"invalid SHA-256 value: {value!r}")
    return normalized


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def object_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _runtime_skill(raw: dict[str, Any]) -> dict[str, Any]:
    skill_type = raw.get("type")
    base = {
        "skill_id": raw.get("global_skill_id"),
        "type": skill_type,
        "source_skill_keys": raw.get("source_skill_keys"),
    }
    if skill_type == "Procedure or Local Strategy":
        fields = ("title", "principle", "when_to_apply")
    elif skill_type == "Failure Lesson":
        # The frozen client loader's Failure Lesson schema has no title field.
        fields = ("description", "why_it_happens", "how_to_avoid")
    else:
        raise ReplacementError(f"unsupported Global skill type: {skill_type!r}")
    for field in fields:
        value = raw.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ReplacementError(f"{base['skill_id']}: missing {field}")
        base[field] = value.strip()
    if not isinstance(base["skill_id"], str) or not base["skill_id"]:
        raise ReplacementError("Global skill is missing global_skill_id")
    sources = base["source_skill_keys"]
    if not isinstance(sources, list) or not sources or any(not isinstance(item, str) or not item for item in sources):
        raise ReplacementError(f"{base['skill_id']}: malformed source_skill_keys")
    return base


def load_global(
    path: Path,
    *,
    expected_sha256: str = EXPECTED_GLOBAL_SHA256,
    expected_skills: int = EXPECTED_GLOBAL_SKILLS,
    expected_round_index: int = 1,
) -> dict[str, Any]:
    actual = file_sha256(path)
    expected = normalize_sha256(expected_sha256)
    if actual != expected:
        raise ReplacementError(f"Global file hash mismatch: expected {expected}, got {actual}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != EXPECTED_GLOBAL_SCHEMA:
        raise ReplacementError(f"unexpected Global schema: {value.get('schema_version')!r}")
    if value.get("round_index") != expected_round_index:
        raise ReplacementError(
            f"expected Global round {expected_round_index}, got {value.get('round_index')!r}"
        )
    general = value.get("general")
    specific = value.get("task_specific")
    if not isinstance(general, list) or not isinstance(specific, dict) or set(specific) != set(TASK_LABELS):
        raise ReplacementError("Global seven-bucket layout is malformed")
    rows = general + sum((specific[label] for label in TASK_LABELS), [])
    if len(rows) != expected_skills:
        raise ReplacementError(f"expected {expected_skills} Global skills, got {len(rows)}")
    ids = [row.get("global_skill_id") for row in rows]
    if len(set(ids)) != len(ids) or any(not isinstance(item, str) or not item for item in ids):
        raise ReplacementError("Global skill IDs must be non-empty and unique")
    return value


def materialize_client(
    global_bank: dict[str, Any],
    client: str,
    destination: Path,
    *,
    expected_sha256: str = EXPECTED_GLOBAL_SHA256,
    expected_skills: int = EXPECTED_GLOBAL_SKILLS,
    experiment_id: str = "v9-b1-role-agnostic-semantic-global-round1-client-validation",
    generation: int = 1,
) -> dict[str, Any]:
    expected_sha256 = normalize_sha256(expected_sha256)
    if client not in EXPECTED_ROLES:
        raise ReplacementError(f"unsupported client: {client}")
    repository = {
        "general": [_runtime_skill(row) for row in global_bank["general"]],
        "task_specific": {
            label: [_runtime_skill(row) for row in global_bank["task_specific"][label]]
            for label in TASK_LABELS
        },
    }
    bank = {
        "bank_schema_version": "stage3_2.client_complete_global_replacement.v1",
        "experiment_id": experiment_id,
        "source_client": client,
        "target_client": client,
        "generation": generation,
        "aggregation_mode": "complete_role_agnostic_global_replacement_runtime_view",
        "source_global_file_sha256": "sha256:" + expected_sha256,
        "source_global_live_hash": global_bank.get("live_global_hash"),
        "role_mapping_policy": "identical_complete_global_repository_for_every_client_role",
        "active_skillbanks": {
            role: json.loads(json.dumps(repository, ensure_ascii=False))
            for role in EXPECTED_ROLES[client]
        },
    }
    parsed = parse_bank(bank, client)
    expected = expected_skills * len(EXPECTED_ROLES[client])
    if len(parsed) != expected:
        raise ReplacementError(f"Client {client}: expected {expected} role-mapped skills, got {len(parsed)}")
    role_states = {
        role: bank["active_skillbanks"][role]
        for role in EXPECTED_ROLES[client]
    }
    hashes = {object_hash(state) for state in role_states.values()}
    if len(hashes) != 1:
        raise ReplacementError(f"Client {client}: role repositories are not identical")
    bank["live_repository_sha256"] = object_hash({
        "source_global_live_hash": global_bank.get("live_global_hash"),
        "client": client,
        "role_mapping_policy": bank["role_mapping_policy"],
        "active_skillbanks": bank["active_skillbanks"],
    })
    write_json(destination, bank)
    return {
        "client": client,
        "roles": list(EXPECTED_ROLES[client]),
        "logical_global_skill_count": expected_skills,
        "runtime_role_mapped_skill_count": len(parsed),
        "per_role_repository_hash": next(iter(hashes)),
        "replacement_bank": str(destination),
        "replacement_bank_file_sha256": "sha256:" + file_sha256(destination),
        "replacement_live_repository_sha256": bank["live_repository_sha256"],
    }


def materialize(
    global_path: Path,
    output_root: Path,
    *,
    expected_sha256: str = EXPECTED_GLOBAL_SHA256,
    expected_skills: int = EXPECTED_GLOBAL_SKILLS,
    expected_round_index: int = 1,
    experiment_id: str = "v9-b1-role-agnostic-semantic-global-round1-client-validation",
    generation: int = 1,
) -> dict[str, Any]:
    global_bank = load_global(
        global_path,
        expected_sha256=expected_sha256,
        expected_skills=expected_skills,
        expected_round_index=expected_round_index,
    )
    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "replacement_manifest.json"
    if manifest_path.exists():
        raise ReplacementError(f"refusing to overwrite existing replacement run: {manifest_path}")
    clients = {
        client: materialize_client(
            global_bank,
            client,
            output_root / f"client_{client}" / "replacement_skillbank.json",
            expected_sha256=expected_sha256,
            expected_skills=expected_skills,
            experiment_id=experiment_id,
            generation=generation,
        )
        for client in ("A", "B", "C")
    }
    manifest = {
        "schema_version": "stage3_2.client_global_replacement_manifest.v1",
        "experiment_id": experiment_id,
        "source_global": str(global_path),
        "source_global_file_sha256": "sha256:" + file_sha256(global_path),
        "source_global_live_hash": global_bank.get("live_global_hash"),
        "logical_global_skill_count": expected_skills,
        "injection_policy": "Global General plus matching task-specific bucket for every client role",
        "historical_b1_files_modified": False,
        "training_or_teacher_enabled": False,
        "clients": clients,
    }
    write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--global-bank", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--expected-sha256", default=EXPECTED_GLOBAL_SHA256)
    parser.add_argument("--expected-skills", type=int, default=EXPECTED_GLOBAL_SKILLS)
    parser.add_argument("--expected-round-index", type=int, default=1)
    parser.add_argument(
        "--experiment-id",
        default="v9-b1-role-agnostic-semantic-global-round1-client-validation",
    )
    parser.add_argument("--generation", type=int, default=1)
    args = parser.parse_args()
    print(json.dumps(materialize(
        args.global_bank,
        args.output_root,
        expected_sha256=args.expected_sha256,
        expected_skills=args.expected_skills,
        expected_round_index=args.expected_round_index,
        experiment_id=args.experiment_id,
        generation=args.generation,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
