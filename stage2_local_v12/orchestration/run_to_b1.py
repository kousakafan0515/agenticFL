"""Create a fresh v10 B1 from empty B0 and stop after B1 validation."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import traceback
from pathlib import Path

from stage2_local_v12.clients.skillbank_loader import parse_bank
from stage2_local_v12.runtime.banks import file_hash, write_json
from stage2_local_v12.evolution.role_evolver import now
from stage2_local_v12.orchestration.run_local_round import complete_summary


ROOT = Path(__file__).resolve().parents[2]


def run(args: argparse.Namespace) -> dict:
    lower = args.client.lower()
    manifest = ROOT / "stage2_local_v12" / "assets" / "manifests" / f"client_{lower}_generation_01.json"
    empty_b0 = ROOT / "stage2_local_v12" / "assets" / "templates" / f"client_{lower}_B0_empty_skillbank.json"
    if not manifest.is_file() or not empty_b0.is_file():
        raise RuntimeError("v10 assets missing; run materialize_assets first")
    parse_bank(json.loads(empty_b0.read_text(encoding="utf-8")), args.client)
    state_path = args.run_root / "controller_state.json"
    identity = {"schema_version": "stage2_local_v10.bootstrap_controller.v1", "client": args.client, "manifest_file_sha256": file_hash(manifest), "empty_b0_file_sha256": file_hash(empty_b0), "stop_after": "B1_validation"}
    if state_path.exists():
        if not args.resume:
            raise RuntimeError("existing v10 B1 controller requires --resume")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if any(state.get(key) != value for key, value in identity.items()) or state.get("status") not in {"failed", "running"}:
            raise RuntimeError("v10 B1 resume identity mismatch")
        state.setdefault("resume_events", []).append({"time": now(), "from_step": state.get("current_step")})
    else:
        if args.resume or (args.run_root.exists() and any(args.run_root.iterdir())):
            raise RuntimeError("fresh v10 B1 root must be empty")
        args.run_root.mkdir(parents=True, exist_ok=True)
        state = {**identity, "status": "running", "current_step": "B0_validation", "completed_steps": [], "started_at": now()}
    state["status"] = "running"
    write_json(state_path, state)
    phase_module = f"stage2_local_v12.runtime.phase_runner_{lower}"

    def phase(name: str, phase_kind: str, generation: int, bank: Path | None) -> dict:
        directory = args.run_root / name
        summary = directory / "summary.json"
        if not summary.exists():
            if directory.exists() and any(directory.iterdir()):
                raise RuntimeError(f"partial {name}; use separately audited phase-level resume before restarting controller")
            state["current_step"] = name
            write_json(state_path, state)
            command = [str(args.python), "-m", phase_module, "--phase", phase_kind, "--generation", str(generation), "--manifest", str(manifest), "--data-root", str(args.data_root), "--output-root", str(directory), "--python", str(args.python)]
            if bank is not None:
                command.extend(["--bank", str(bank)])
            subprocess.run(command, cwd=ROOT, check=True)
        result = complete_summary(summary, args.client, generation, phase_kind)
        lock_path = directory / "source_lock.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.exists() else {}
        if lock.get("manifest_file_sha256") != file_hash(manifest) or (bank is not None and lock.get("bank_file_sha256") != file_hash(bank)):
            raise RuntimeError(f"{name}: frozen manifest or bank source lock mismatch")
        if name not in state["completed_steps"]:
            state["completed_steps"].append(name)
            write_json(state_path, state)
        return result

    try:
        validation0 = phase("B0_validation", "validation", 0, None)
        training0 = phase("B0_training", "training", 1, None)
        bank = args.run_root / "B1_skillbank.json"
        record = args.run_root / "B1_teacher_record.json"
        if bank.exists() != record.exists():
            raise RuntimeError("partial B1 Teacher outputs preserved; repair before resume")
        if not bank.exists():
            state["current_step"] = "B1_teacher"
            write_json(state_path, state)
            subprocess.run([str(args.python), "-m", "stage2_local_v12.evolution.bootstrap_b1", "--client", args.client, "--generation", "1", "--teacher-model", "deepseek-flash", "--teacher-provider", "deepseek_official", "--evidence", str(args.run_root / "B0_training" / "evidence.json"), "--parent-bank", str(empty_b0), "--output", str(bank), "--record-output", str(record)], cwd=ROOT, check=True)
        payload = json.loads(bank.read_text(encoding="utf-8"))
        parse_bank(payload, args.client)
        if payload.get("generation") != 1 or payload.get("experiment_id") != "stage2-local-v10-role-partitioned-patch3":
            raise RuntimeError("B1 identity mismatch")
        if "B1_teacher" not in state["completed_steps"]:
            state["completed_steps"].append("B1_teacher")
            write_json(state_path, state)
        validation1 = phase("B1_validation", "validation", 1, bank)
        state.update(status="complete", current_step=None, completed_at=now(), results={"B0_validation_success": validation0["success_count"], "B0_training_success": training0["success_count"], "B1_bank_file_sha256": file_hash(bank), "B1_validation_success": validation1["success_count"]})
        write_json(state_path, state)
        return state
    except BaseException as exc:
        state.update(status="failed", error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc(), failed_at=now())
        write_json(state_path, state)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", choices=tuple("ABC"), required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
