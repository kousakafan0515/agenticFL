"""Run one Client B/C from empty B0 through frozen B1 validation, then stop."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from client_code.skillbank_loader import parse_bank
from originalFL.banks import file_hash, write_json
from originalFL.round1_evolver import _local_evolution_config
from stage2_local_v9.scripts.materialize_client_bc_assets import destinations


ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_TEACHER_MODEL = "deepseek-flash"
OFFICIAL_TEACHER_PROVIDER = "deepseek_official"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def complete_summary(path: Path, client: str, phase: str, generation: int) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    expected = {"status": "complete", "client": client, "phase": phase, "generation": generation, "task_count": 134, "api_clean": True}
    for key, value in expected.items():
        if payload.get(key) != value:
            raise RuntimeError(f"invalid {client} {phase} B{generation} summary: {key}={payload.get(key)!r}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", choices=("B", "C"), required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--resume-order-reference",
        type=Path,
        default=ROOT / "stage2_local_v9/runs/client_a_generation_01_20261013_r1/B0_validation/result.json",
    )
    args = parser.parse_args()
    client = args.client
    lower = client.lower()
    manifest, empty_b0 = destinations(client)
    phase_module = f"stage2_local_v9.scripts.run_client_{lower}_phase"
    evolver_module = f"stage2_local_v9.scripts.evolve_client_{lower}_bank"
    if not os.environ.get("DASHSCOPE_API_KEY"):
        raise SystemExit("DASHSCOPE_API_KEY is missing")
    teacher = _local_evolution_config()
    descriptor = teacher.descriptor()
    if teacher.model != OFFICIAL_TEACHER_MODEL or descriptor.get("provider") != OFFICIAL_TEACHER_PROVIDER:
        raise SystemExit("DeepSeek official deepseek-flash Teacher is required")
    if descriptor.get("endpoint_origin", "").rstrip("/") != "https://api.deepseek.com":
        raise SystemExit("DeepSeek official base URL is required")
    if not manifest.is_file() or not empty_b0.is_file():
        raise SystemExit("Client assets are missing; run materialize_client_bc_assets first")
    parse_bank(json.loads(empty_b0.read_text(encoding="utf-8")), client)
    if args.preflight_only:
        subprocess.run([str(args.python), "-m", phase_module, "--phase", "validation", "--generation", "0", "--manifest", str(manifest), "--output-root", str(args.run_root / "preflight"), "--data-root", str(args.data_root), "--python", str(args.python), "--dry-run"], cwd=ROOT, check=True)
        print(json.dumps({"status": "preflight_ok", "client": client, "stop_after": "B1_validation", "teacher": descriptor}, ensure_ascii=False))
        return
    run_root = args.run_root.resolve()
    state_path = run_root / "B0_to_B1_controller_state.json"
    if args.resume:
        if not state_path.is_file():
            raise SystemExit(f"resume requires controller state: {state_path}")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("client") != client or state.get("status") not in {"running", "failed"}:
            raise SystemExit("resume controller identity or state mismatch")
        if not args.resume_order_reference.is_file():
            raise SystemExit(f"resume order reference is missing: {args.resume_order_reference}")
        state.setdefault("resume_events", []).append({
            "resumed_at_utc": now(),
            "from_step": state.get("current_step"),
            "policy": "reuse complete summaries; resume a partial phase only when its episodes are the frozen-order prefix",
            "order_reference": str(args.resume_order_reference),
            "order_reference_file_sha256": file_hash(args.resume_order_reference),
        })
        state["status"] = "running"
        for key in ("failed_at_step", "error_type", "error", "traceback", "failed_at_utc"):
            state.pop(key, None)
    else:
        if run_root.exists() or state_path.exists():
            raise SystemExit(f"refusing to overwrite run root: {run_root}")
        run_root.mkdir(parents=True)
        state = {
            "schema_version": 1, "status": "running", "client": client,
            "started_at_utc": now(), "current_step": "preflight", "completed_steps": [],
            "task_model": "qwen3.6-flash", "teacher_model": OFFICIAL_TEACHER_MODEL,
            "teacher_endpoint": descriptor,
            "stage_order": ["B0_validation", "B0_training", "B1_teacher", "B1_validation"],
            "teacher_evidence_policy": "B0_training/evidence.json only; validation excluded",
            "stop_policy": "stop on first error; stop after B1 validation",
        }
    write_json(state_path, state)

    def run_step(name: str, command: list[str]) -> None:
        state["current_step"] = name
        state["updated_at_utc"] = now()
        write_json(state_path, state)
        subprocess.run(command, cwd=ROOT, check=True)
        if name not in state["completed_steps"]:
            state["completed_steps"].append(name)
        state["updated_at_utc"] = now()
        write_json(state_path, state)

    def run_phase(name: str, phase: str, generation: int, output_root: Path, bank: Path | None = None) -> dict[str, Any]:
        summary_path = output_root / "summary.json"
        if summary_path.is_file():
            summary = complete_summary(summary_path, client, phase, generation)
            if name not in state["completed_steps"]:
                state["completed_steps"].append(name)
                write_json(state_path, state)
            return summary
        command = [
            str(args.python), "-m", phase_module,
            "--phase", phase, "--generation", str(generation),
            "--output-root", str(output_root),
            "--manifest", str(manifest), "--data-root", str(args.data_root),
            "--python", str(args.python),
        ]
        if bank is not None:
            command.extend(["--bank", str(bank)])
        if output_root.exists():
            if not args.resume or not (output_root / "result.json").is_file():
                raise RuntimeError(f"incomplete phase cannot be reused without --resume and result.json: {output_root}")
            command.extend(["--resume-partial", "--resume-order-reference", str(args.resume_order_reference)])
        run_step(name, command)
        return complete_summary(summary_path, client, phase, generation)

    try:
        b0_validation = run_root / "B0_validation"
        validation0 = run_phase("B0_validation", "validation", 0, b0_validation)

        b0_training = run_root / "B0_training"
        training0 = run_phase("B0_training", "training", 1, b0_training)

        bank = run_root / "B1_skillbank.json"
        record = run_root / "B1_teacher_record.json"
        if bank.exists() != record.exists():
            raise RuntimeError("incomplete frozen B1 Teacher outputs")
        if not bank.exists():
            run_step("B1_teacher", [str(args.python), "-m", evolver_module, "--generation", "1", "--teacher-model", OFFICIAL_TEACHER_MODEL, "--teacher-provider", OFFICIAL_TEACHER_PROVIDER, "--evidence", str(b0_training / "evidence.json"), "--parent-bank", str(empty_b0), "--output", str(bank), "--record-output", str(record)])
        elif "B1_teacher" not in state["completed_steps"]:
            state["completed_steps"].append("B1_teacher")
            write_json(state_path, state)
        bank_payload = json.loads(bank.read_text(encoding="utf-8"))
        parse_bank(bank_payload, client)

        b1_validation = run_root / "B1_validation"
        validation1 = run_phase("B1_validation", "validation", 1, b1_validation, bank)
        state.update({
            "status": "complete", "current_step": None, "stopped_after": "B1_validation", "completed_at_utc": now(),
            "results": {
                "B0_validation_success": validation0["success_count"],
                "B0_training_success": training0["success_count"],
                "B0_training_evidence_file_sha256": training0["evidence_file_sha256"],
                "B1_bank_file_sha256": file_hash(bank),
                "B1_skills_by_role": {role: len(repo["general"]) + sum(len(rows) for rows in repo["task_specific"].values()) for role, repo in bank_payload["active_skillbanks"].items()},
                "B1_validation_success": validation1["success_count"],
            },
        })
        write_json(state_path, state)
    except BaseException as exc:
        state.update({"status": "failed", "failed_at_step": state.get("current_step"), "error_type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc(), "failed_at_utc": now()})
        write_json(state_path, state)
        raise


if __name__ == "__main__":
    main()
