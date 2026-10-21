"""Run one client's Global1 training and generate local role-agnostic B2, then stop."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

from originalFL.banks import file_hash, write_json


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_RUNS = {
    "A": ROOT / "stage2_local_v9/runs/client_a_generation_01_20261013_r1/B0_training/result.json",
    "B": ROOT / "stage2_local_v9/runs/client_b_generation_01_20261013_r3/B0_training/result.json",
    "C": ROOT / "stage2_local_v9/runs/client_c_generation_01_20261013_r3/B0_training/result.json",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", choices=("A", "B", "C"), required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--parent-bank", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    client = args.client
    state_path = args.run_root / "controller_state.json"
    if args.resume:
        if not state_path.is_file():
            raise SystemExit("resume requires controller_state.json")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("client") != client or state.get("status") not in {"running", "failed"}:
            raise SystemExit("resume controller identity mismatch")
        state["status"] = "running"
        state.setdefault("resume_events", []).append({"resumed_at": now(), "from_step": state.get("current_step")})
    else:
        if args.run_root.exists():
            raise SystemExit(f"refusing to overwrite run root: {args.run_root}")
        args.run_root.mkdir(parents=True)
        state = {"schema_version": 1, "client": client, "status": "running", "current_step": "B1_training_for_B2", "completed_steps": [], "started_at": now(), "stop_after": "B2_teacher"}
    write_json(state_path, state)
    phase_module = f"stage2_local_v9.scripts.run_client_{client.lower()}_phase"
    training_root = args.run_root / "B1_training_for_B2"
    try:
        summary_path = training_root / "summary.json"
        if not summary_path.is_file():
            command = [str(args.python), "-m", phase_module, "--phase", "training", "--generation", "2", "--manifest", str(args.manifest), "--bank", str(args.parent_bank), "--output-root", str(training_root), "--data-root", str(args.data_root), "--python", str(args.python)]
            if client == "A":
                # Malformed Executor replies do not consume environment actions. Bound
                # that loop so the episode becomes a recorded failure instead of a
                # LangGraph process-level recursion failure.
                command.extend(["--max-control-retries", "12"])
            if training_root.exists():
                if not args.resume or not (training_root / "result.json").is_file():
                    raise RuntimeError("incomplete training requires explicit --resume and a partial result")
                command.extend(["--resume-partial", "--resume-order-reference", str(REFERENCE_RUNS[client])])
            subprocess.run(command, cwd=ROOT, check=True)
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        expected = {"status": "complete", "phase": "training", "generation": 2, "client": client, "task_count": 134, "api_clean": True}
        if any(summary.get(key) != value for key, value in expected.items()):
            raise RuntimeError(f"invalid complete training summary: {summary}")
        if "B1_training_for_B2" not in state["completed_steps"]:
            state["completed_steps"].append("B1_training_for_B2")
        state["current_step"] = "B2_teacher"
        write_json(state_path, state)
        bank = args.run_root / "B2_skillbank.json"
        record = args.run_root / "B2_teacher_record.json"
        patch = args.run_root / "B2_patch.json"
        if any(path.exists() for path in (bank, record, patch)) and not all(path.exists() for path in (bank, record, patch)):
            raise RuntimeError("incomplete frozen B2 outputs")
        if not bank.exists():
            subprocess.run([str(args.python), "-m", "stage3_2_role_agnostic_semantic_merge.local_round2_evolver", "--client", client, "--evidence", str(training_root / "evidence.json"), "--parent-bank", str(args.parent_bank), "--output", str(bank), "--record-output", str(record), "--patch-output", str(patch)], cwd=ROOT, check=True)
        b2 = json.loads(bank.read_text(encoding="utf-8"))
        if b2.get("client") != client or b2.get("generation") != 2 or not b2.get("capacity_policy", {}).get("quota_passed"):
            raise RuntimeError("invalid B2 identity or capacity policy")
        state.update({"status": "complete", "current_step": None, "completed_steps": ["B1_training_for_B2", "B2_teacher"], "completed_at": now(), "results": {"training_success": summary["success_count"], "training_result_sha256": summary["result_file_sha256"], "training_evidence_sha256": summary["evidence_file_sha256"], "b2_file_sha256": file_hash(bank), "patch_file_sha256": file_hash(patch), "capacity_policy": b2["capacity_policy"]}})
        write_json(state_path, state)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    except BaseException as exc:
        state.update({"status": "failed", "failed_at_step": state.get("current_step"), "error_type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc(), "failed_at": now()})
        write_json(state_path, state)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
