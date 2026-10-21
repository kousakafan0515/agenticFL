"""Train on Global2, generate one client's local B3, validate it, then stop."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from client_code.skillbank_loader import EXPECTED_ROLES, TASK_TYPE_LABELS, parse_bank
from originalFL.banks import file_hash, write_json
from stage3_2_role_agnostic_semantic_merge.client_global_validation import object_hash


ROOT = Path(__file__).resolve().parents[1]
GENERATION = 3
BASE_COUNT = 44
TASK_LABELS = tuple(TASK_TYPE_LABELS.values())
ORDER_REFERENCES = {
    "A": {
        "training": ROOT / "stage2_local_v9/runs/client_a_generation_01_20261013_r1/B0_training/result.json",
        "validation": ROOT / "stage2_local_v9/runs/client_a_generation_01_20261013_r1/B0_validation/result.json",
    },
    "B": {
        "training": ROOT / "stage2_local_v9/runs/client_b_generation_01_20261013_r3/B0_training/result.json",
        "validation": ROOT / "stage2_local_v9/runs/client_b_generation_01_20261013_r3/B0_validation/result.json",
    },
    "C": {
        "training": ROOT / "stage2_local_v9/runs/client_c_generation_01_20261013_r3/B0_training/result.json",
        "validation": ROOT / "stage2_local_v9/runs/client_c_generation_01_20261013_r3/B0_validation/result.json",
    },
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def logical_repository(bank: dict[str, Any], client: str) -> dict[str, Any]:
    parse_bank(bank, client)
    repositories = [bank["active_skillbanks"][role] for role in EXPECTED_ROLES[client]]
    if any(repository != repositories[0] for repository in repositories[1:]):
        raise RuntimeError("Global2 runtime roles do not contain identical repositories")
    repository = repositories[0]
    rows = repository["general"] + sum((repository["task_specific"][label] for label in TASK_LABELS), [])
    if len(rows) != BASE_COUNT:
        raise RuntimeError(f"Global2 must contain {BASE_COUNT} logical skills, got {len(rows)}")
    return repository


def materialize_b3_runtime(source: Path, client: str, destination: Path) -> dict[str, Any]:
    b3 = json.loads(source.read_text(encoding="utf-8"))
    if b3.get("schema_version") != "stage3_2.local_role_agnostic_bank.v1" or b3.get("client") != client or b3.get("generation") != GENERATION:
        raise RuntimeError("invalid local B3 identity")
    policy = b3.get("capacity_policy") or {}
    if policy.get("base_count") != BASE_COUNT or not policy.get("quota_passed"):
        raise RuntimeError("invalid local B3 capacity audit")
    if policy.get("add_count", 0) > policy.get("delete_count", 0) // 3:
        raise RuntimeError("local B3 violates the three-delete/one-add quota")
    repository = {"general": b3["general"], "task_specific": b3["task_specific"]}
    rows = repository["general"] + sum((repository["task_specific"][label] for label in TASK_LABELS), [])
    if len(rows) != policy.get("candidate_count"):
        raise RuntimeError("local B3 candidate count mismatch")
    runtime = {
        "bank_schema_version": "stage3_2.client_local_b3_validation_runtime.v1",
        "experiment_id": "v9-global2-to-local-b3",
        "source_client": client,
        "target_client": client,
        "generation": GENERATION,
        "aggregation_mode": "complete_local_role_agnostic_b3_runtime_view",
        "source_b3_file_sha256": file_hash(source),
        "source_b3_live_repository_sha256": b3.get("live_repository_sha256"),
        "capacity_policy": policy,
        "role_mapping_policy": "identical_complete_local_b3_repository_for_every_client_role",
        "active_skillbanks": {
            role: json.loads(json.dumps(repository, ensure_ascii=False))
            for role in EXPECTED_ROLES[client]
        },
    }
    parse_bank(runtime, client)
    runtime["live_repository_sha256"] = object_hash({
        "client": client,
        "source_b3_live_repository_sha256": b3.get("live_repository_sha256"),
        "active_skillbanks": runtime["active_skillbanks"],
    })
    write_json(destination, runtime)
    return runtime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", choices=("A", "B", "C"), required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--parent-bank", type=Path, required=True)
    parser.add_argument("--global2-validation-summary", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    client = args.client
    state_path = args.run_root / "controller_state.json"
    validation_gate = json.loads(args.global2_validation_summary.read_text(encoding="utf-8"))
    if any((validation_gate.get("status") != "complete", validation_gate.get("client") != client, validation_gate.get("task_count") != 134, validation_gate.get("api_clean") is not True)):
        raise SystemExit("complete API-clean Global2 validation is required before local B3 evolution")
    parent = json.loads(args.parent_bank.read_text(encoding="utf-8"))
    logical_repository(parent, client)

    if args.resume:
        if not state_path.is_file():
            raise SystemExit("resume requires controller_state.json")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("client") != client or state.get("status") not in {"running", "failed"}:
            raise SystemExit("resume controller identity mismatch")
        if state.get("parent_bank_file_sha256") != file_hash(args.parent_bank):
            raise SystemExit("resume parent bank mismatch")
        state["status"] = "running"
        state.setdefault("resume_events", []).append({"resumed_at": now(), "from_step": state.get("current_step")})
    else:
        if args.run_root.exists():
            raise SystemExit(f"refusing to overwrite run root: {args.run_root}")
        args.run_root.mkdir(parents=True)
        state = {
            "schema_version": "stage3_2.global2_to_local_b3_controller.v1",
            "client": client,
            "status": "running",
            "current_step": "Global2_training_for_B3",
            "completed_steps": [],
            "started_at": now(),
            "stop_after": "B3_validation",
            "parent": "Global SkillBank2",
            "parent_bank_file_sha256": file_hash(args.parent_bank),
            "global2_validation_summary_sha256": file_hash(args.global2_validation_summary),
            "capacity_policy": "three_distinct_deletes_per_add_whole_client_bank",
        }
    write_json(state_path, state)

    phase_module = f"stage2_local_v9.scripts.run_client_{client.lower()}_phase"

    def run_phase(phase: str, bank: Path, output_root: Path) -> dict[str, Any]:
        summary_path = output_root / "summary.json"
        if not summary_path.is_file():
            command = [str(args.python), "-m", phase_module, "--phase", phase, "--generation", str(GENERATION), "--manifest", str(args.manifest), "--bank", str(bank), "--output-root", str(output_root), "--data-root", str(args.data_root), "--python", str(args.python)]
            if client == "A":
                command.extend(["--max-control-retries", "12"])
            if output_root.exists():
                result_path = output_root / "result.json"
                if not args.resume or not result_path.is_file():
                    raise RuntimeError(f"incomplete {phase} requires explicit resume and partial result")
                command.extend(["--resume-partial", "--resume-order-reference", str(ORDER_REFERENCES[client][phase])])
            subprocess.run(command, cwd=ROOT, check=True)
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        expected = {"status": "complete", "phase": phase, "generation": GENERATION, "client": client, "task_count": 134, "api_clean": True}
        if any(summary.get(key) != value for key, value in expected.items()):
            raise RuntimeError(f"invalid complete {phase} summary: {summary}")
        return summary

    try:
        training_root = args.run_root / "Global2_training_for_B3"
        training_summary = run_phase("training", args.parent_bank, training_root)
        if "Global2_training_for_B3" not in state["completed_steps"]:
            state["completed_steps"].append("Global2_training_for_B3")
        state["current_step"] = "B3_teacher"
        write_json(state_path, state)

        b3 = args.run_root / "B3_skillbank.json"
        patch = args.run_root / "B3_patch.json"
        record = args.run_root / "B3_teacher_record.json"
        if any(path.exists() for path in (b3, patch, record)) and not all(path.exists() for path in (b3, patch, record)):
            raise RuntimeError("incomplete frozen B3 outputs")
        if not b3.exists():
            subprocess.run([
                str(args.python), "-m", "stage3_2_role_agnostic_semantic_merge.local_round2_evolver",
                "--client", client,
                "--evidence", str(training_root / "evidence.json"),
                "--parent-bank", str(args.parent_bank),
                "--output", str(b3),
                "--record-output", str(record),
                "--patch-output", str(patch),
                "--generation", str(GENERATION),
                "--expected-base-count", str(BASE_COUNT),
                "--parent-label", "Global SkillBank2",
                "--experiment-id", "v9-global2-to-local-b3",
            ], cwd=ROOT, check=True)
        b3_value = json.loads(b3.read_text(encoding="utf-8"))
        if b3_value.get("client") != client or b3_value.get("generation") != GENERATION or not b3_value.get("capacity_policy", {}).get("quota_passed"):
            raise RuntimeError("invalid B3 identity or capacity policy")
        if "B3_teacher" not in state["completed_steps"]:
            state["completed_steps"].append("B3_teacher")
        state["current_step"] = "B3_validation"
        write_json(state_path, state)

        runtime_bank = args.run_root / "B3_runtime_skillbank.json"
        if not runtime_bank.exists():
            materialize_b3_runtime(b3, client, runtime_bank)
        validation_summary = run_phase("validation", runtime_bank, args.run_root / "B3_validation")
        state.update({
            "status": "complete",
            "current_step": None,
            "completed_steps": ["Global2_training_for_B3", "B3_teacher", "B3_validation"],
            "completed_at": now(),
            "results": {
                "training_success": training_summary["success_count"],
                "training_result_sha256": training_summary["result_file_sha256"],
                "training_evidence_sha256": training_summary["evidence_file_sha256"],
                "b3_file_sha256": file_hash(b3),
                "patch_file_sha256": file_hash(patch),
                "capacity_policy": b3_value["capacity_policy"],
                "validation_success": validation_summary["success_count"],
                "validation_result_sha256": validation_summary["result_file_sha256"],
                "validation_api_clean": validation_summary["api_clean"],
            },
        })
        write_json(state_path, state)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    except BaseException as exc:
        state.update({"status": "failed", "failed_at_step": state.get("current_step"), "error_type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc(), "failed_at": now()})
        write_json(state_path, state)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
