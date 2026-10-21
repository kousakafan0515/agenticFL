"""Client A v11 independent B1-to-B5 chain with per-role quotas."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import traceback
from pathlib import Path

from client_code.skillbank_loader import parse_bank
from originalFL.banks import file_hash, write_json
from stage2_local_v11.import_v9_b1 import verify_imported_seed
from stage2_local_v11.materialize_assets import EXPERIMENT_ID
from stage2_local_v11.role_evolver import now
from stage2_local_v11.run_local_round import complete_summary


ROOT = Path(__file__).resolve().parents[1]


def run(args: argparse.Namespace) -> dict:
    initial = json.loads(args.initial_b1.read_text(encoding="utf-8"))
    parse_bank(initial, "A")
    if initial.get("generation") != 1:
        raise RuntimeError("independent v11 parent must be B1")
    if initial.get("experiment_id") != EXPERIMENT_ID:
        verify_imported_seed(args.initial_b1, args.initial_b1_validation_summary, "A")
    complete_summary(args.initial_b1_validation_summary, "A", 1, "validation")
    state_path = args.run_root / "controller_state.json"
    identity = {"schema_version": "stage2_local_v11.independent_to_b5.v1", "initial_b1_file_sha256": file_hash(args.initial_b1), "initial_b1_validation_summary_sha256": file_hash(args.initial_b1_validation_summary), "stop_after": "B5_validation", "capacity_policy": "per_role_three_distinct_deletes_per_add"}
    if state_path.exists():
        if not args.resume:
            raise RuntimeError("existing v11 independent state requires --resume")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if any(state.get(key) != value for key, value in identity.items()) or state.get("status") not in {"failed", "running"}:
            raise RuntimeError("v11 independent resume identity mismatch")
        state.setdefault("resume_events", []).append({"time": now(), "from_round": state.get("current_round")})
    else:
        if args.resume or (args.run_root.exists() and any(args.run_root.iterdir())):
            raise RuntimeError("new v11 independent run root must be empty")
        args.run_root.mkdir(parents=True, exist_ok=True)
        state = {**identity, "status": "running", "current_round": 2, "completed_rounds": [], "started_at": now()}
    state["status"] = "running"
    write_json(state_path, state)
    try:
        for generation in range(2, 6):
            parent = args.initial_b1 if generation == 2 else args.run_root / f"round_B{generation-1}" / f"B{generation-1}_skillbank.json"
            parent_validation = args.initial_b1_validation_summary if generation == 2 else args.run_root / f"round_B{generation-1}" / "validation" / "summary.json"
            output = args.run_root / f"round_B{generation}"
            controller = output / "controller_state.json"
            if controller.exists():
                frozen = json.loads(controller.read_text(encoding="utf-8"))
                if frozen.get("status") == "complete":
                    complete_summary(output / "validation" / "summary.json", "A", generation, "validation")
                    if generation not in state["completed_rounds"]:
                        state["completed_rounds"].append(generation)
                        write_json(state_path, state)
                    continue
                if not args.resume:
                    raise RuntimeError(f"round B{generation} incomplete; explicit --resume required")
            state["current_round"] = generation
            write_json(state_path, state)
            command = [str(args.python), "-m", "stage2_local_v11.run_local_round", "--client", "A", "--generation", str(generation), "--parent-kind", "independent", "--parent-bank", str(parent), "--parent-validation-summary", str(parent_validation), "--run-root", str(output), "--manifest", str(args.manifest), "--data-root", str(args.data_root), "--experiment-id", args.experiment_id, "--python", str(args.python)]
            if generation == 2 and args.initial_b1_training_root:
                command.extend(["--reuse-training-root", str(args.initial_b1_training_root)])
            if controller.exists():
                command.append("--resume")
            subprocess.run(command, cwd=ROOT, check=True)
            complete_summary(output / "validation" / "summary.json", "A", generation, "validation")
            state["completed_rounds"].append(generation)
            write_json(state_path, state)
        state.update(status="complete", current_round=None, completed_at=now())
        write_json(state_path, state)
        return state
    except BaseException as exc:
        state.update(status="failed", error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc(), failed_at=now())
        write_json(state_path, state)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial-b1", type=Path, required=True)
    parser.add_argument("--initial-b1-validation-summary", type=Path, required=True)
    parser.add_argument("--initial-b1-training-root", type=Path)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
