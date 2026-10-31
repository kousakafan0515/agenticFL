"""Downlink one v10 Global and validate it on all three frozen client suites."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from stage2_local_v12.runtime.banks import file_hash, write_json
from stage2_local_v12.federation.downlink import expected_bank, materialize
from stage2_local_v12.evolution.role_evolver import now
from stage2_local_v12.orchestration.run_local_round import complete_summary


ROOT = Path(__file__).resolve().parents[2]


def run(args: argparse.Namespace) -> dict:
    state_path = args.run_root / "controller_state.json"
    global_round = args.global_round or args.generation
    identity = {"schema_version": "stage2_local_v10.global_validation_controller.v1", "generation": args.generation, "global_round": global_round, "global_bank_file_sha256": file_hash(args.global_bank), "experiment_id": args.experiment_id, "stop_after": f"Global{global_round}_three_client_validation"}
    if state_path.exists():
        if not args.resume:
            raise RuntimeError("existing Global validation state requires --resume")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if any(state.get(key) != value for key, value in identity.items()) or state.get("status") not in {"failed", "running"}:
            raise RuntimeError("Global validation resume identity mismatch")
        state.setdefault("resume_events", []).append({"time": now(), "from_client": state.get("current_client")})
    else:
        if args.resume or (args.run_root.exists() and any(args.run_root.iterdir())):
            raise RuntimeError("fresh Global validation root must be empty")
        args.run_root.mkdir(parents=True, exist_ok=True)
        state = {**identity, "status": "running", "current_client": "A", "completed_clients": [], "started_at": now()}
    state["status"] = "running"
    write_json(state_path, state)
    try:
        def validate_client(client: str) -> dict:
            lower = client.lower()
            client_root = args.run_root / f"client_{client}"
            bank_path = client_root / "replacement_skillbank.json"
            if bank_path.exists():
                bank = json.loads(bank_path.read_text(encoding="utf-8"))
                expected = expected_bank(args.global_bank, client, args.generation, file_hash(args.global_bank), args.experiment_id, global_round=global_round)
                if bank != expected:
                    raise RuntimeError(f"Client {client} frozen Global replacement mismatch")
            else:
                materialize(args.global_bank, bank_path, client, args.generation, file_hash(args.global_bank), args.experiment_id, global_round=global_round)
            validation_root = client_root / "validation"
            summary_path = validation_root / "summary.json"
            if not summary_path.exists():
                if validation_root.exists() and any(validation_root.iterdir()):
                    raise RuntimeError(f"Client {client} partial validation; audit and resume that phase separately")
                manifest = ROOT / "stage2_local_v12" / "assets" / "manifests" / f"client_{lower}_generation_01.json"
                command = [str(args.python), "-m", f"stage2_local_v12.runtime.phase_runner_{lower}", "--phase", "validation", "--generation", str(args.generation), "--manifest", str(manifest), "--bank", str(bank_path), "--output-root", str(validation_root), "--data-root", str(args.data_root), "--python", str(args.python)]
                if client == "A":
                    command.extend(["--max-control-retries", "12"])
                subprocess.run(command, cwd=ROOT, check=True)
            summary = complete_summary(summary_path, client, args.generation, "validation")
            lock_path = validation_root / "source_lock.json"
            manifest = ROOT / "stage2_local_v12" / "assets" / "manifests" / f"client_{lower}_generation_01.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.exists() else {}
            if lock.get("bank_file_sha256") != file_hash(bank_path) or lock.get("manifest_file_sha256") != file_hash(manifest):
                raise RuntimeError(f"Client {client} validation did not use frozen Global copy")
            return {"success_count": summary["success_count"], "result_file_sha256": summary["result_file_sha256"], "replacement_bank_file_sha256": file_hash(bank_path)}

        if args.parallel_clients:
            state["current_client"] = "ABC_parallel"
            write_json(state_path, state)
            errors = []
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = {pool.submit(validate_client, client): client for client in "ABC"}
                for future in as_completed(futures):
                    client = futures[future]
                    try:
                        result = future.result()
                    except BaseException as exc:
                        errors.append((client, exc))
                    else:
                        state.setdefault("results", {})[client] = result
                        if client not in state["completed_clients"]:
                            state["completed_clients"].append(client)
                        write_json(state_path, state)
            if errors:
                raise RuntimeError("parallel Global validation failed: " + "; ".join(f"{client}: {exc}" for client, exc in errors))
        else:
            for client in "ABC":
                state["current_client"] = client
                write_json(state_path, state)
                state.setdefault("results", {})[client] = validate_client(client)
                if client not in state["completed_clients"]:
                    state["completed_clients"].append(client)
                write_json(state_path, state)
        state.update(status="complete", current_client=None, completed_at=now(), pooled_success_count=sum(item["success_count"] for item in state["results"].values()))
        write_json(state_path, state)
        return state
    except BaseException as exc:
        state.update(status="failed", error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc(), failed_at=now())
        write_json(state_path, state)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--global-bank", type=Path, required=True)
    parser.add_argument("--generation", type=int, required=True)
    parser.add_argument("--global-round", type=int, help="Global index when it differs from local bank generation")
    parser.add_argument("--parallel-clients", action="store_true")
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
