"""Run Client A from its original B1 through B5 under D-104 patch evolution."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from client_code.skillbank_loader import parse_bank
from originalFL.banks import file_hash, write_json
from originalFL.round1_evolver import _local_evolution_config


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_B1_HASH = "sha256:84218a56b828fe08b81bd476c62d32950f61764b13390e957fd22c430bf24db4"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def complete_summary(path: Path, phase: str, generation: int) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = {"status": "complete", "phase": phase, "generation": generation, "client": "A", "task_count": 134, "api_clean": True}
    for key, target in expected.items():
        if value.get(key) != target:
            raise RuntimeError(f"invalid {phase} B{generation} summary: {key}={value.get(key)!r}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--initial-b1", type=Path, required=True)
    parser.add_argument("--initial-b1-training", type=Path, required=True)
    parser.add_argument("--initial-b1-validation", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if file_hash(args.initial_b1) != EXPECTED_B1_HASH:
        raise SystemExit("original Client A B1 hash mismatch")
    b1 = json.loads(args.initial_b1.read_text(encoding="utf-8"))
    parse_bank(b1, "A")
    if int(b1.get("generation", -1)) != 1:
        raise SystemExit("initial parent must be B1")
    initial_training = complete_summary(args.initial_b1_training / "summary.json", "training", 2)
    complete_summary(args.initial_b1_validation / "summary.json", "validation", 1)
    if initial_training["success_count"] != 92:
        raise SystemExit("frozen B1 training result changed")
    if not os.environ.get("DASHSCOPE_API_KEY"):
        raise SystemExit("DASHSCOPE_API_KEY is missing")
    teacher = _local_evolution_config()
    descriptor = teacher.descriptor()
    if teacher.model != "deepseek-flash" or descriptor.get("provider") != "deepseek_official" or descriptor.get("endpoint_origin") != "https://api.deepseek.com":
        raise SystemExit("DeepSeek official deepseek-flash Teacher is required")

    if args.preflight_only:
        models = teacher.client(timeout=30).models.list()
        if "deepseek-flash" not in {row.id for row in models.data}:
            raise RuntimeError("deepseek-flash is unavailable")
        from stage2_local_v9.client_a_patch_evolver import call_json_recorded
        probe_args = argparse.Namespace(
            timeout=90.0, retries=2, truncation_retries=1, seed=1234, max_tokens=64,
        )
        with tempfile.TemporaryDirectory(prefix="v9_patch3_json_probe_") as probe_directory:
            probe_value, _ = call_json_recorded(
                teacher,
                [
                    {"role": "system", "content": "Return exactly one compact JSON object."},
                    {"role": "user", "content": 'Return this JSON object: {"status":"ok"}'},
                ],
                probe_args,
                Path(probe_directory) / "json_output_probe",
            )
        if probe_value != {"status": "ok"}:
            raise RuntimeError(f"unexpected DeepSeek JSON-output preflight response: {probe_value!r}")
        with tempfile.TemporaryDirectory(prefix="v9_patch3_preflight_") as temporary:
            subprocess.run([
                str(args.python), "-m", "stage2_local_v9.scripts.run_client_a_phase",
                "--phase", "training", "--generation", "2", "--manifest", str(args.manifest),
                "--bank", str(args.initial_b1), "--output-root", temporary,
                "--data-root", str(args.data_root), "--python", str(args.python), "--dry-run",
            ], cwd=ROOT, check=True)
        print(json.dumps({"status": "preflight_ok", "parent": str(args.initial_b1), "parent_hash": EXPECTED_B1_HASH, "reused_b1_training_success": 92, "stop_after": "B5_validation", "teacher": descriptor, "json_output_probe": "ok"}, ensure_ascii=False))
        return 0

    run_root = args.run_root.resolve()
    state_path = run_root / "controller_state.json"
    if state_path.exists() and not args.resume:
        raise SystemExit("refusing to overwrite controller state")
    if args.resume and not state_path.exists():
        raise SystemExit("resume requires controller state")
    if not args.resume:
        if run_root.exists() and any(run_root.iterdir()):
            raise SystemExit("fresh run root must be empty")
        run_root.mkdir(parents=True, exist_ok=True)
        state: dict[str, Any] = {
            "schema_version": "stage2_local_v9.client_a_patch3_controller.v1",
            "status": "running", "started_at_utc": now(), "current_step": "preflight",
            "completed_steps": ["B1_training_reused"],
            "initial_b1_path": str(args.initial_b1), "initial_b1_file_sha256": EXPECTED_B1_HASH,
            "initial_b1_training_path": str(args.initial_b1_training),
            "initial_b1_training_result_sha256": initial_training["result_file_sha256"],
            "capacity_policy": "whole_client_three_distinct_deletes_per_add",
            "task_model": "qwen3.6-flash", "teacher_model": "deepseek-flash",
            "teacher_endpoint": descriptor,
            "stage_order": [
                "B2_teacher", "B2_validation", "B2_training",
                "B3_teacher", "B3_validation", "B3_training",
                "B4_teacher", "B4_validation", "B4_training",
                "B5_teacher", "B5_validation",
            ],
            "stop_policy": "stop on first error; stop after B5 validation",
        }
    else:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("status") != "failed" or state.get("initial_b1_file_sha256") != EXPECTED_B1_HASH:
            raise SystemExit("resume state is not a matching failed run")
        state.setdefault("failure_history", []).append({
            key: state.get(key)
            for key in ("failed_at_step", "error_type", "error", "traceback", "failed_at_utc")
        })
        state.setdefault("resume_events", []).append({"resumed_at_utc": now(), "from_step": state.get("failed_at_step")})
        state["status"] = "running"
        for key in ("failed_at_step", "error_type", "error", "traceback", "failed_at_utc"):
            state.pop(key, None)
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

    phase_module = "stage2_local_v9.scripts.run_client_a_phase"
    try:
        for generation in range(2, 6):
            parent = args.initial_b1 if generation == 2 else run_root / f"B{generation - 1}_skillbank.json"
            training_root = args.initial_b1_training if generation == 2 else run_root / f"B{generation - 1}_training"
            bank = run_root / f"B{generation}_skillbank.json"
            patch = run_root / f"B{generation}_patch.json"
            record = run_root / f"B{generation}_teacher_record.json"
            validation_root = run_root / f"B{generation}_validation"

            if bank.exists() != patch.exists() or bank.exists() != record.exists():
                raise RuntimeError(f"incomplete frozen B{generation} Teacher outputs")
            if not bank.exists():
                run_step(f"B{generation}_teacher", [
                    str(args.python), "-m", "stage2_local_v9.client_a_patch_evolver",
                    "--generation", str(generation), "--evidence", str(training_root / "evidence.json"),
                    "--parent-bank", str(parent), "--output", str(bank),
                    "--patch-output", str(patch), "--record-output", str(record),
                ])
            bank_payload = json.loads(bank.read_text(encoding="utf-8"))
            parse_bank(bank_payload, "A")
            if int(bank_payload.get("generation", -1)) != generation:
                raise RuntimeError(f"wrong B{generation} generation")
            policy = bank_payload.get("capacity_policy") or {}
            if policy.get("quota_passed") is not True or policy.get("add_count", 0) > policy.get("delete_count", 0) // 3:
                raise RuntimeError(f"B{generation} quota audit failed")

            validation_summary_path = validation_root / "summary.json"
            if validation_summary_path.exists():
                validation_summary = complete_summary(validation_summary_path, "validation", generation)
            else:
                command = [
                    str(args.python), "-m", phase_module, "--phase", "validation",
                    "--generation", str(generation), "--manifest", str(args.manifest),
                    "--bank", str(bank), "--output-root", str(validation_root),
                    "--data-root", str(args.data_root), "--python", str(args.python),
                ]
                if validation_root.exists():
                    reference = args.initial_b1_validation / "result.json" if generation == 2 else run_root / f"B{generation - 1}_validation/result.json"
                    command.extend(["--resume-partial", "--resume-order-reference", str(reference)])
                run_step(f"B{generation}_validation", command)
                validation_summary = complete_summary(validation_summary_path, "validation", generation)

            state.setdefault("generations", {})[str(generation)] = {
                "parent_bank_file_sha256": file_hash(parent),
                "training_success_count": complete_summary(training_root / "summary.json", "training", generation)["success_count"],
                "patch_file_sha256": file_hash(patch), "bank_file_sha256": file_hash(bank),
                "bank_live_repository_sha256": bank_payload["live_repository_sha256"],
                "capacity_policy": policy,
                "validation_success_count": validation_summary["success_count"],
                "validation_result_file_sha256": validation_summary["result_file_sha256"],
            }
            write_json(state_path, state)
            if generation == 5:
                continue

            next_training_root = run_root / f"B{generation}_training"
            next_summary = next_training_root / "summary.json"
            if next_summary.exists():
                complete_summary(next_summary, "training", generation + 1)
            else:
                command = [
                    str(args.python), "-m", phase_module, "--phase", "training",
                    "--generation", str(generation + 1), "--manifest", str(args.manifest),
                    "--bank", str(bank), "--output-root", str(next_training_root),
                    "--data-root", str(args.data_root), "--python", str(args.python),
                ]
                if next_training_root.exists():
                    reference = args.initial_b1_training / "result.json" if generation == 2 else run_root / f"B{generation - 1}_training/result.json"
                    command.extend(["--resume-partial", "--resume-order-reference", str(reference)])
                run_step(f"B{generation}_training", command)
                complete_summary(next_summary, "training", generation + 1)

        state["status"] = "complete"
        state["current_step"] = None
        state["stopped_after"] = "B5_validation"
        state["completed_at_utc"] = now()
        write_json(state_path, state)
        return 0
    except BaseException as exc:
        state["status"] = "failed"
        state["failed_at_step"] = state.get("current_step")
        state["error_type"] = type(exc).__name__
        state["error"] = str(exc)
        state["traceback"] = traceback.format_exc()
        state["failed_at_utc"] = now()
        write_json(state_path, state)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
