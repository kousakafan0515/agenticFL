"""Train on one complete Global bank, evolve one local bank, validate, and stop."""

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
TASK_LABELS = tuple(TASK_TYPE_LABELS.values())
ORDER_REFERENCES = {
    "A": {p: ROOT / f"stage2_local_v9/runs/client_a_generation_01_20261013_r1/B0_{p}/result.json" for p in ("training", "validation")},
    "B": {p: ROOT / f"stage2_local_v9/runs/client_b_generation_01_20261013_r3/B0_{p}/result.json" for p in ("training", "validation")},
    "C": {p: ROOT / f"stage2_local_v9/runs/client_c_generation_01_20261013_r3/B0_{p}/result.json" for p in ("training", "validation")},
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def logical_repository(bank: dict[str, Any], client: str, expected_count: int) -> dict[str, Any]:
    parse_bank(bank, client)
    repositories = [bank["active_skillbanks"][role] for role in EXPECTED_ROLES[client]]
    if any(repository != repositories[0] for repository in repositories[1:]):
        raise RuntimeError("Global runtime roles do not contain identical repositories")
    repository = repositories[0]
    rows = repository["general"] + sum((repository["task_specific"][label] for label in TASK_LABELS), [])
    if len(rows) != expected_count:
        raise RuntimeError(f"Global bank must contain {expected_count} logical skills, got {len(rows)}")
    return repository


def materialize_local_runtime(source: Path, client: str, destination: Path, generation: int, base_count: int, experiment_id: str) -> dict[str, Any]:
    value = json.loads(source.read_text(encoding="utf-8"))
    if value.get("schema_version") != "stage3_2.local_role_agnostic_bank.v1" or value.get("client") != client or value.get("generation") != generation:
        raise RuntimeError(f"invalid local B{generation} identity")
    policy = value.get("capacity_policy") or {}
    if policy.get("base_count") != base_count or policy.get("quota_passed") is not True or policy.get("add_count", 0) > policy.get("delete_count", 0) // 3:
        raise RuntimeError(f"invalid local B{generation} capacity audit")
    repository = {"general": value["general"], "task_specific": value["task_specific"]}
    rows = repository["general"] + sum((repository["task_specific"][label] for label in TASK_LABELS), [])
    if len(rows) != policy.get("candidate_count"):
        raise RuntimeError("local candidate count mismatch")
    runtime = {
        "bank_schema_version": "stage3_2.client_local_validation_runtime.v1",
        "experiment_id": experiment_id, "source_client": client, "target_client": client,
        "generation": generation, "aggregation_mode": "complete_local_role_agnostic_runtime_view",
        "source_local_file_sha256": file_hash(source),
        "source_local_live_repository_sha256": value.get("live_repository_sha256"),
        "capacity_policy": policy,
        "role_mapping_policy": "identical_complete_local_repository_for_every_client_role",
        "active_skillbanks": {role: json.loads(json.dumps(repository, ensure_ascii=False)) for role in EXPECTED_ROLES[client]},
    }
    parse_bank(runtime, client)
    runtime["live_repository_sha256"] = object_hash({"client": client, "source_local_live_repository_sha256": value.get("live_repository_sha256"), "active_skillbanks": runtime["active_skillbanks"]})
    write_json(destination, runtime)
    return runtime


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--client", choices=tuple("ABC"), required=True)
    p.add_argument("--generation", type=int, required=True, choices=(4, 5))
    p.add_argument("--base-count", type=int, required=True)
    p.add_argument("--run-root", type=Path, required=True)
    p.add_argument("--parent-bank", type=Path, required=True)
    p.add_argument("--global-validation-summary", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--data-root", type=Path, required=True)
    p.add_argument("--python", type=Path, default=Path(sys.executable))
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()
    client, generation, global_generation = args.client, args.generation, args.generation - 1
    experiment_id = f"v9-global{global_generation}-to-local-b{generation}"
    state_path = args.run_root / "controller_state.json"
    gate = json.loads(args.global_validation_summary.read_text(encoding="utf-8"))
    expected_gate = {"status": "complete", "client": client, "generation": global_generation, "phase": "validation", "task_count": 134, "api_clean": True}
    if any(gate.get(k) != v for k, v in expected_gate.items()):
        raise SystemExit(f"complete API-clean Global{global_generation} validation required")
    parent = json.loads(args.parent_bank.read_text(encoding="utf-8"))
    logical_repository(parent, client, args.base_count)
    if args.resume:
        if not state_path.is_file():
            raise SystemExit("resume requires controller_state.json")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("client") != client or state.get("generation") != generation or state.get("status") not in {"running", "failed"} or state.get("parent_bank_file_sha256") != file_hash(args.parent_bank):
            raise SystemExit("resume controller identity mismatch")
        state["status"] = "running"
        state.setdefault("resume_events", []).append({"resumed_at": now(), "from_step": state.get("current_step")})
    else:
        if args.run_root.exists():
            raise SystemExit(f"refusing to overwrite run root: {args.run_root}")
        args.run_root.mkdir(parents=True)
        state = {"schema_version": "stage3_2.global_to_local_controller.v1", "client": client, "generation": generation, "status": "running", "current_step": f"Global{global_generation}_training_for_B{generation}", "completed_steps": [], "started_at": now(), "stop_after": f"B{generation}_validation", "parent": f"Global SkillBank{global_generation}", "parent_bank_file_sha256": file_hash(args.parent_bank), "global_validation_summary_sha256": file_hash(args.global_validation_summary), "base_count": args.base_count, "capacity_policy": "three_distinct_deletes_per_add_whole_client_bank"}
    write_json(state_path, state)
    phase_module = f"stage2_local_v9.scripts.run_client_{client.lower()}_phase"

    def run_phase(phase: str, bank: Path, output: Path) -> dict[str, Any]:
        summary_path = output / "summary.json"
        if not summary_path.is_file():
            command = [str(args.python), "-m", phase_module, "--phase", phase, "--generation", str(generation), "--manifest", str(args.manifest), "--bank", str(bank), "--output-root", str(output), "--data-root", str(args.data_root), "--python", str(args.python)]
            if client == "A":
                command.extend(["--max-control-retries", "12"])
            if output.exists():
                result = output / "result.json"
                if not args.resume or not result.is_file():
                    raise RuntimeError(f"incomplete {phase} requires explicit resume and partial result")
                command.extend(["--resume-partial", "--resume-order-reference", str(ORDER_REFERENCES[client][phase])])
            subprocess.run(command, cwd=ROOT, check=True)
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        expected = {"status": "complete", "phase": phase, "generation": generation, "client": client, "task_count": 134, "api_clean": True}
        if any(summary.get(k) != v for k, v in expected.items()):
            raise RuntimeError(f"invalid complete {phase} summary")
        return summary

    train_step = f"Global{global_generation}_training_for_B{generation}"
    teacher_step, validation_step = f"B{generation}_teacher", f"B{generation}_validation"
    try:
        training_root = args.run_root / train_step
        training = run_phase("training", args.parent_bank, training_root)
        if train_step not in state["completed_steps"]:
            state["completed_steps"].append(train_step)
        state["current_step"] = teacher_step
        write_json(state_path, state)
        local_bank, patch, record = (args.run_root / f"B{generation}_skillbank.json", args.run_root / f"B{generation}_patch.json", args.run_root / f"B{generation}_teacher_record.json")
        if any(x.exists() for x in (local_bank, patch, record)) and not all(x.exists() for x in (local_bank, patch, record)):
            raise RuntimeError("incomplete frozen local outputs")
        if not local_bank.exists():
            subprocess.run([str(args.python), "-m", "stage3_2_role_agnostic_semantic_merge.local_round2_evolver", "--client", client, "--evidence", str(training_root / "evidence.json"), "--parent-bank", str(args.parent_bank), "--output", str(local_bank), "--record-output", str(record), "--patch-output", str(patch), "--generation", str(generation), "--expected-base-count", str(args.base_count), "--parent-label", f"Global SkillBank{global_generation}", "--experiment-id", experiment_id], cwd=ROOT, check=True)
        local_value = json.loads(local_bank.read_text(encoding="utf-8"))
        if local_value.get("client") != client or local_value.get("generation") != generation or local_value.get("capacity_policy", {}).get("quota_passed") is not True:
            raise RuntimeError("invalid local identity or capacity policy")
        if teacher_step not in state["completed_steps"]:
            state["completed_steps"].append(teacher_step)
        state["current_step"] = validation_step
        write_json(state_path, state)
        runtime = args.run_root / f"B{generation}_runtime_skillbank.json"
        if not runtime.exists():
            materialize_local_runtime(local_bank, client, runtime, generation, args.base_count, experiment_id)
        validation = run_phase("validation", runtime, args.run_root / validation_step)
        state.update({"status": "complete", "current_step": None, "completed_steps": [train_step, teacher_step, validation_step], "completed_at": now(), "results": {"training_success": training["success_count"], "training_result_sha256": training["result_file_sha256"], "training_evidence_sha256": training["evidence_file_sha256"], "local_bank_file_sha256": file_hash(local_bank), "patch_file_sha256": file_hash(patch), "capacity_policy": local_value["capacity_policy"], "validation_success": validation["success_count"], "validation_result_sha256": validation["result_file_sha256"], "validation_api_clean": validation["api_clean"]}})
        write_json(state_path, state)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    except BaseException as exc:
        state.update({"status": "failed", "failed_at_step": state.get("current_step"), "error_type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc(), "failed_at": now()})
        write_json(state_path, state)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
