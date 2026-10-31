"""Run one frozen 134-task v10 local round, stopping after local validation.

Use a Global downlink as the parent for federation or a previous local bank for
independent evolution. Existing complete phases are verified and reused.
Partial phases require an explicit, separately audited phase-level resume.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any

from stage2_local_v12.clients.skillbank_loader import EXPECTED_ROLES, parse_bank
from stage2_local_v12.runtime.banks import file_hash, write_json
from stage2_local_v12.orchestration.import_v9_b1 import verify_imported_seed
from stage2_local_v12.orchestration.materialize_assets import EXPERIMENT_ID
from stage2_local_v12.evolution.role_evolver import SCHEMA, now, repository_rows


ROOT = Path(__file__).resolve().parents[2]


def complete_summary(path: Path, client: str, generation: int, phase: str) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = {"status": "complete", "client": client, "generation": generation, "phase": phase, "task_count": 134, "api_clean": True}
    if any(value.get(key) != item for key, item in expected.items()):
        raise RuntimeError(f"{path}: complete API-clean {phase} summary required")
    return value


def run(args: argparse.Namespace) -> dict[str, Any]:
    parent = json.loads(args.parent_bank.read_text(encoding="utf-8"))
    parse_bank(parent, args.client)
    if parent.get("generation") != args.generation - 1:
        raise RuntimeError("parent bank generation must be B(n-1) or Global(n-1)")
    if args.parent_kind == "independent" and args.generation == 2 and parent.get("experiment_id") != EXPERIMENT_ID:
        verify_imported_seed(args.parent_bank, args.parent_validation_summary, args.client)
    if args.parent_kind == "global":
        repositories = [parent["active_skillbanks"][role] for role in EXPECTED_ROLES[args.client]]
        if any(repository != repositories[0] for repository in repositories[1:]):
            raise RuntimeError("Global downlink role copies must be identical")
        if not parent.get("source_global_file_sha256"):
            raise RuntimeError("Global downlink provenance missing")
    parent_summary = complete_summary(args.parent_validation_summary, args.client, args.generation - 1, "validation")
    parent_lock_path = args.parent_validation_summary.parent / "source_lock.json"
    if not parent_lock_path.exists() or json.loads(parent_lock_path.read_text(encoding="utf-8")).get("bank_file_sha256") != file_hash(args.parent_bank):
        raise RuntimeError("parent validation did not use the specified parent bank bytes")
    state_path = args.run_root / "controller_state.json"
    identity = {"schema_version": "stage2_local_v10.local_round_controller.v1", "client": args.client, "generation": args.generation, "parent_kind": args.parent_kind, "parent_bank_file_sha256": file_hash(args.parent_bank), "parent_validation_summary_sha256": file_hash(args.parent_validation_summary), "stop_after": f"B{args.generation}_validation"}
    if state_path.exists():
        if not args.resume:
            raise RuntimeError("existing v10 state requires --resume")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if any(state.get(key) != value for key, value in identity.items()) or state.get("status") not in {"failed", "running"}:
            raise RuntimeError("resume identity or state mismatch")
        state.setdefault("resume_events", []).append({"time": now(), "from_step": state.get("current_step")})
    else:
        if args.resume or (args.run_root.exists() and any(args.run_root.iterdir())):
            raise RuntimeError("fresh v10 output root must be empty; resume requires state")
        args.run_root.mkdir(parents=True, exist_ok=True)
        state = {**identity, "status": "running", "current_step": "training", "completed_steps": [], "started_at": now()}
    state["status"] = "running"
    write_json(state_path, state)
    phase_module = f"stage2_local_v12.runtime.phase_runner_{args.client.lower()}"

    def phase(name: str, bank_path: Path, directory: Path, generation: int) -> dict[str, Any]:
        summary_path = directory / "summary.json"
        if not summary_path.exists():
            if directory.exists() and any(directory.iterdir()):
                raise RuntimeError(f"partial {name} exists; use the phase-level frozen-prefix resume before restarting controller: {directory}")
            state["current_step"] = name
            write_json(state_path, state)
            command = [str(args.python), "-m", phase_module, "--phase", name, "--generation", str(generation), "--manifest", str(args.manifest), "--bank", str(bank_path), "--output-root", str(directory), "--data-root", str(args.data_root), "--python", str(args.python)]
            if args.client == "A":
                command.extend(["--max-control-retries", "12"])
            subprocess.run(command, cwd=ROOT, check=True)
        result = complete_summary(summary_path, args.client, generation, name)
        lock_path = directory / "source_lock.json"
        if not lock_path.exists():
            raise RuntimeError(f"{name}: source lock missing")
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        if lock.get("bank_file_sha256") != file_hash(bank_path) or lock.get("manifest_file_sha256") != file_hash(args.manifest):
            raise RuntimeError(f"{name}: bank or manifest source lock mismatch")
        if name not in state["completed_steps"]:
            state["completed_steps"].append(name)
            write_json(state_path, state)
        return result

    try:
        training_root = args.reuse_training_root or (args.run_root / "training")
        if args.reuse_training_root:
            training = complete_summary(training_root / "summary.json", args.client, args.generation, "training")
            evidence = json.loads((training_root / "evidence.json").read_text(encoding="utf-8"))
            if evidence.get("parent_bank_file_sha256") != file_hash(args.parent_bank):
                raise RuntimeError("reused training evidence parent hash mismatch")
            training_lock = json.loads((training_root / "source_lock.json").read_text(encoding="utf-8"))
            if training_lock.get("bank_file_sha256") != file_hash(args.parent_bank) or training_lock.get("manifest_file_sha256") != file_hash(args.manifest):
                raise RuntimeError("reused training bank or manifest source lock mismatch")
        else:
            training = phase("training", args.parent_bank, training_root, args.generation)
        output_bank = args.run_root / f"B{args.generation}_skillbank.json"
        patch = args.run_root / f"B{args.generation}_patch.json"
        record = args.run_root / f"B{args.generation}_teacher_record.json"
        if any(path.exists() for path in (output_bank, patch, record)) and not all(path.exists() for path in (output_bank, patch, record)):
            raise RuntimeError("partial Teacher outputs; preserve evidence and repair before resume")
        if not output_bank.exists():
            state["current_step"] = "teacher"
            write_json(state_path, state)
            subprocess.run([str(args.python), "-m", "stage2_local_v12.evolution.role_evolver", "--client", args.client, "--generation", str(args.generation), "--parent-kind", args.parent_kind, "--parent-bank", str(args.parent_bank), "--evidence", str(training_root / "evidence.json"), "--output", str(output_bank), "--patch-output", str(patch), "--record-output", str(record), "--experiment-id", args.experiment_id], cwd=ROOT, check=True)
        bank = json.loads(output_bank.read_text(encoding="utf-8"))
        if bank.get("schema_version") != SCHEMA or bank.get("parent_bank_file_sha256") != file_hash(args.parent_bank) or bank.get("capacity_policy", {}).get("quota_passed") is not True:
            raise RuntimeError("v10 Teacher output identity or quota invalid")
        parse_bank(bank, args.client)
        for role in EXPECTED_ROLES[args.client]:
            policy = bank["capacity_policy"]["per_role"][role]
            if policy["candidate"] != len(repository_rows(bank["active_skillbanks"][role])) or policy["add"] > policy["delete"] // 3:
                raise RuntimeError(f"{role}: local bank quota/count invalid")
        if "teacher" not in state["completed_steps"]:
            state["completed_steps"].append("teacher")
            write_json(state_path, state)
        validation = phase("validation", output_bank, args.run_root / "validation", args.generation)
        state.update(status="complete", current_step=None, completed_at=now(), training_success=training["success_count"], validation_success=validation["success_count"], output_bank_file_sha256=file_hash(output_bank), patch_file_sha256=file_hash(patch), validation_result_sha256=validation["result_file_sha256"])
        write_json(state_path, state)
        return state
    except BaseException as exc:
        state.update(status="failed", error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc(), failed_at=now())
        write_json(state_path, state)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", choices=tuple("ABC"), required=True)
    parser.add_argument("--generation", type=int, required=True)
    parser.add_argument("--parent-kind", choices=("independent", "global"), required=True)
    parser.add_argument("--parent-bank", type=Path, required=True)
    parser.add_argument("--parent-validation-summary", type=Path, required=True)
    parser.add_argument("--reuse-training-root", type=Path)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.generation < 2:
        parser.error("v10 post-B1 evolution starts at generation 2")
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
