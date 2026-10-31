"""Copy one complete seven-bucket Global into every local role partition."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

from stage2_local_v12.clients.skillbank_loader import EXPECTED_ROLES, TASK_TYPE_LABELS, parse_bank
from stage2_local_v12.runtime.banks import file_hash, write_json
from stage2_local_v12.evolution.role_evolver import repository_rows
from stage2_local_v12.federation.client_global_validation import _runtime_skill, normalize_sha256, object_hash


def expected_bank(global_path: Path, client: str, generation: int, expected_sha256: str, experiment_id: str, *, global_round: int | None = None) -> dict[str, Any]:
    """Compute the entire frozen downlink for initial creation or resume verification."""
    expected = normalize_sha256(expected_sha256)
    if file_hash(global_path).removeprefix("sha256:").lower() != expected:
        raise RuntimeError("Global file SHA-256 mismatch")
    global_bank = json.loads(global_path.read_text(encoding="utf-8"))
    if (global_bank.get("schema_version") != "stage3_2.role_agnostic_semantic_global.v1"
            or global_bank.get("v10_protocol") != "role_partitioned_local_to_role_agnostic_global.v1"
            or global_bank.get("experiment_id") != experiment_id
            or global_bank.get("round_index") != (generation if global_round is None else global_round)):
        raise RuntimeError("v10 Global protocol, experiment identity or round mismatch")
    labels = tuple(TASK_TYPE_LABELS.values())
    if not isinstance(global_bank.get("general"), list) or not isinstance(global_bank.get("task_specific"), dict) or set(global_bank["task_specific"]) != set(labels):
        raise RuntimeError("Global must have exactly seven buckets")
    repository = {"general": [_runtime_skill(row) for row in global_bank["general"]], "task_specific": {label: [_runtime_skill(row) for row in global_bank["task_specific"][label]] for label in labels}}
    count = len(repository_rows(repository))
    if not count:
        raise RuntimeError("empty Global SkillBank")
    bank = {"bank_schema_version": "stage2_local_v10.complete_global_role_copy.v1", "experiment_id": experiment_id, "source_client": client, "target_client": client, "generation": generation, "source_global_round": generation if global_round is None else global_round, "source_global_file_sha256": "sha256:" + expected, "source_global_live_hash": global_bank.get("live_global_hash"), "role_mapping_policy": "identical_full_global_repository_copied_to_each_role", "active_skillbanks": {role: copy.deepcopy(repository) for role in EXPECTED_ROLES[client]}}
    parse_bank(bank, client)
    if len({object_hash(value) for value in bank["active_skillbanks"].values()}) != 1:
        raise RuntimeError("role copies are not identical")
    bank["live_repository_sha256"] = object_hash(bank["active_skillbanks"])
    return bank


def materialize(global_path: Path, output: Path, client: str, generation: int, expected_sha256: str, experiment_id: str, *, global_round: int | None = None) -> dict[str, Any]:
    if output.exists():
        raise RuntimeError(f"refusing to overwrite existing downlink: {output}")
    bank = expected_bank(global_path, client, generation, expected_sha256, experiment_id, global_round=global_round)
    write_json(output, bank)
    return {"status": "complete", "client": client, "roles": list(EXPECTED_ROLES[client]), "skills_per_role": len(repository_rows(next(iter(bank["active_skillbanks"].values())))), "global_sha256": normalize_sha256(expected_sha256), "output": str(output), "output_sha256": file_hash(output)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--global-bank", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--client", choices=tuple("ABC"), required=True)
    parser.add_argument("--generation", type=int, required=True)
    parser.add_argument("--global-round", type=int)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(args.global_bank, args.output, args.client, args.generation, args.expected_sha256, args.experiment_id, global_round=args.global_round), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
