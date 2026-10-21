"""One synchronous v11 round: Global k -> local B(k+1) -> Global k+1.

Requires a completed, hash-bound Global k three-client validation. Runs no
server evaluation; after aggregation it validates the new Global on clients.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import traceback
from pathlib import Path

from originalFL.banks import file_hash, write_json
from stage2_local_v11.downlink import expected_bank
from stage2_local_v11.role_evolver import now
from stage2_local_v11.run_local_round import complete_summary


ROOT = Path(__file__).resolve().parents[1]


def run(args: argparse.Namespace) -> dict:
    if args.global_generation not in range(1, 5):
        raise RuntimeError("v11 round must start at Global1..Global4 and stop by Global5")
    next_generation = args.global_generation + 1
    prior_controller = json.loads((args.global_validation_root / "controller_state.json").read_text(encoding="utf-8"))
    if prior_controller.get("status") != "complete" or prior_controller.get("generation") != args.global_generation or prior_controller.get("global_bank_file_sha256") != file_hash(args.global_bank) or prior_controller.get("experiment_id") != args.experiment_id:
        raise RuntimeError("complete Global parent validation with matching bank hash required")
    state_path = args.run_root / "controller_state.json"
    identity = {"schema_version": "stage2_local_v11.federated_round_controller.v1", "global_generation": args.global_generation, "next_generation": next_generation, "parent_global_file_sha256": file_hash(args.global_bank), "parent_validation_controller_sha256": file_hash(args.global_validation_root / "controller_state.json"), "experiment_id": args.experiment_id, "stop_after": f"Global{next_generation}_three_client_validation"}
    if state_path.exists():
        if not args.resume:
            raise RuntimeError("existing v11 federated round requires --resume")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if any(state.get(key) != value for key, value in identity.items()) or state.get("status") not in {"failed", "running"}:
            raise RuntimeError("v11 federated resume identity mismatch")
        state.setdefault("resume_events", []).append({"time": now(), "from_step": state.get("current_step")})
    else:
        if args.resume or (args.run_root.exists() and any(args.run_root.iterdir())):
            raise RuntimeError("fresh v11 federated round root must be empty")
        args.run_root.mkdir(parents=True, exist_ok=True)
        state = {**identity, "status": "running", "current_step": "local_A", "completed_steps": [], "started_at": now()}
    state["status"] = "running"
    write_json(state_path, state)
    try:
        local_roots: dict[str, Path] = {}
        for client in "ABC":
            prior_client = args.global_validation_root / f"client_{client}"
            prior_bank = prior_client / "replacement_skillbank.json"
            prior_summary = prior_client / "validation" / "summary.json"
            complete_summary(prior_summary, client, args.global_generation, "validation")
            bank = json.loads(prior_bank.read_text(encoding="utf-8"))
            if bank != expected_bank(args.global_bank, client, args.global_generation, file_hash(args.global_bank), args.experiment_id):
                raise RuntimeError(f"Client {client} parent Global copy mismatch")
            lock_path = prior_client / "validation" / "source_lock.json"
            if json.loads(lock_path.read_text(encoding="utf-8")).get("bank_file_sha256") != file_hash(prior_bank):
                raise RuntimeError(f"Client {client} parent Global validation bank mismatch")
            local_root = args.run_root / f"client_{client}_local_B{next_generation}"
            local_roots[client] = local_root
            controller = local_root / "controller_state.json"
            if controller.exists() and json.loads(controller.read_text(encoding="utf-8")).get("status") == "complete":
                complete_summary(local_root / "validation" / "summary.json", client, next_generation, "validation")
            else:
                state["current_step"] = f"local_{client}"
                write_json(state_path, state)
                manifest = ROOT / "stage2_local_v11" / "artifacts" / "manifests" / f"client_{client.lower()}_generation_01.json"
                command = [str(args.python), "-m", "stage2_local_v11.run_local_round", "--client", client, "--generation", str(next_generation), "--parent-kind", "global", "--parent-bank", str(prior_bank), "--parent-validation-summary", str(prior_summary), "--run-root", str(local_root), "--manifest", str(manifest), "--data-root", str(args.data_root), "--experiment-id", args.experiment_id, "--python", str(args.python)]
                if controller.exists():
                    command.append("--resume")
                subprocess.run(command, cwd=ROOT, check=True)
            if f"local_{client}" not in state["completed_steps"]:
                state["completed_steps"].append(f"local_{client}")
                write_json(state_path, state)
        aggregate_root = args.run_root / f"Global{next_generation}_aggregation"
        global_bank = aggregate_root / f"global_skillbank{next_generation}.json"
        if not global_bank.exists():
            state["current_step"] = "aggregate"
            write_json(state_path, state)
            command = [str(args.python), "-m", "stage2_local_v11.server_aggregate", "--round-index", str(next_generation), "--experiment-id", args.experiment_id, "--output-root", str(aggregate_root)]
            for client in "ABC":
                command.extend([f"--bank-{client.lower()}", str(local_roots[client] / f"B{next_generation}_skillbank.json"), f"--validation-{client.lower()}", str(local_roots[client] / "validation" / "summary.json")])
            subprocess.run(command, cwd=ROOT, check=True)
        summary = json.loads((aggregate_root / "summary.json").read_text(encoding="utf-8"))
        if summary.get("status") != "complete" or summary.get("round_index") != next_generation or summary.get("global_skillbank", {}).get("file_sha256") != file_hash(global_bank):
            raise RuntimeError("frozen v11 server aggregation identity mismatch")
        if "aggregate" not in state["completed_steps"]:
            state["completed_steps"].append("aggregate")
            write_json(state_path, state)
        validation_root = args.run_root / f"Global{next_generation}_validation"
        validation_controller = validation_root / "controller_state.json"
        if not validation_controller.exists() or json.loads(validation_controller.read_text(encoding="utf-8")).get("status") != "complete":
            state["current_step"] = "global_validation"
            write_json(state_path, state)
            command = [str(args.python), "-m", "stage2_local_v11.run_global_validation", "--global-bank", str(global_bank), "--generation", str(next_generation), "--experiment-id", args.experiment_id, "--run-root", str(validation_root), "--data-root", str(args.data_root), "--python", str(args.python)]
            if validation_controller.exists():
                command.append("--resume")
            subprocess.run(command, cwd=ROOT, check=True)
        global_validation = json.loads(validation_controller.read_text(encoding="utf-8"))
        if global_validation.get("status") != "complete" or global_validation.get("global_bank_file_sha256") != file_hash(global_bank):
            raise RuntimeError("Global validation identity mismatch")
        state.update(status="complete", current_step=None, completed_at=now(), global_bank_file_sha256=file_hash(global_bank), global_bank_path=str(global_bank), global_validation_root=str(validation_root), global_validation_success=global_validation["pooled_success_count"])
        write_json(state_path, state)
        return state
    except BaseException as exc:
        state.update(status="failed", error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc(), failed_at=now())
        write_json(state_path, state)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--global-generation", type=int, required=True)
    parser.add_argument("--global-bank", type=Path, required=True)
    parser.add_argument("--global-validation-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
