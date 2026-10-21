"""Synchronous full-SkillBank baseline controller from local B3 through Global5 validation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from originalFL.banks import file_hash, write_json
from stage3_2_role_agnostic_semantic_merge.client_global_validation import materialize, normalize_sha256

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "stage3_2_role_agnostic_semantic_merge"
RUNS = STAGE / "runs"
CURRENT_B3 = RUNS / "v9_global2_to_local_b3_20261015_r1"
DATA_ROOT = ROOT / "alfworld_data"
PYTHON_DEFAULT = Path("/home/user0515/miniconda3/envs/stage3-alfworld/bin/python")
MANIFESTS = {c: ROOT / f"stage2_local_v9/artifacts/manifests/client_{c.lower()}_generation_01.json" for c in "ABC"}
ORDER_REFERENCES = {
    "A": ROOT / "stage2_local_v9/runs/client_a_generation_01_20261013_r1/B0_validation/result.json",
    "B": ROOT / "stage2_local_v9/runs/client_b_generation_01_20261013_r3/B0_validation/result.json",
    "C": ROOT / "stage2_local_v9/runs/client_c_generation_01_20261013_r3/B0_validation/result.json",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_complete_summary(path: Path, client: str, generation: int) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = {"status": "complete", "phase": "validation", "client": client, "generation": generation, "task_count": 134, "api_clean": True}
    if any(value.get(k) != v for k, v in expected.items()):
        raise RuntimeError(f"invalid complete summary: {path}")
    return value


def wait_for_initial_b3(state: dict[str, Any], state_path: Path, poll_seconds: int) -> None:
    state["current_step"] = "wait_local_B3_validations"
    write_json(state_path, state)
    paths = {c: CURRENT_B3 / f"client_{c}/B3_validation/summary.json" for c in "ABC"}
    while True:
        missing = [c for c, path in paths.items() if not path.is_file()]
        for c in missing:
            controller = CURRENT_B3 / f"client_{c}/controller_state.json"
            if controller.is_file():
                value = json.loads(controller.read_text(encoding="utf-8"))
                if value.get("status") == "failed":
                    raise RuntimeError(f"Client {c} local B3 controller failed: {value.get('error')}")
        if not missing:
            for c, path in paths.items():
                load_complete_summary(path, c, 3)
            state.setdefault("completed_steps", []).append("wait_local_B3_validations")
            write_json(state_path, state)
            return
        state["waiting_for_clients"] = missing
        state["updated_at"] = now()
        write_json(state_path, state)
        time.sleep(poll_seconds)


def round_paths(round_index: int) -> dict[str, Path]:
    if round_index == 3:
        local_root = CURRENT_B3
    else:
        local_root = RUNS / f"v9_global{round_index-1}_to_local_b{round_index}_20261015_r1"
    return {
        "local_root": local_root,
        "aggregation_root": RUNS / f"v9_local_b{round_index}_global{round_index}_20261015_r1",
        "global_validation_root": RUNS / f"v9_global{round_index}_client_validation_20261015_r1",
    }


def run_checked(command: list[str], log_root: Path, name: str) -> None:
    log_root.mkdir(parents=True, exist_ok=True)
    stdout_path, stderr_path = log_root / f"{name}.stdout.log", log_root / f"{name}.stderr.log"
    with stdout_path.open("ab") as stdout, stderr_path.open("ab") as stderr:
        completed = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr)
    if completed.returncode:
        raise RuntimeError(f"{name} failed with exit code {completed.returncode}; see {stderr_path}")


def aggregate(round_index: int, paths: dict[str, Path], python: Path) -> tuple[Path, dict[str, Any]]:
    root, local_root = paths["aggregation_root"], paths["local_root"]
    summary_path = root / "summary.json"
    command = [str(python), "-m", "stage3_2_role_agnostic_semantic_merge.federated_round_aggregate", "--round-index", str(round_index), "--output-root", str(root)]
    for c in "ABC":
        command += [f"--bank-{c.lower()}", str(local_root / f"client_{c}/B{round_index}_skillbank.json"), f"--validation-{c.lower()}", str(local_root / f"client_{c}/B{round_index}_validation/summary.json")]
    if not summary_path.is_file():
        run_checked(command, root, "aggregation")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if summary.get("status") != "complete" or summary.get("round_index") != round_index:
        raise RuntimeError(f"invalid Global{round_index} aggregation summary")
    global_path = root / f"global_skillbank{round_index}.json"
    if summary.get("global_skillbank", {}).get("file_sha256") != file_hash(global_path):
        raise RuntimeError(f"Global{round_index} hash mismatch")
    return global_path, summary


def ensure_materialized(global_path: Path, aggregation: dict[str, Any], paths: dict[str, Path], round_index: int) -> None:
    root = paths["global_validation_root"]
    manifest_path = root / "replacement_manifest.json"
    expected_hash = aggregation["global_skillbank"]["file_sha256"]
    count = aggregation["output_skill_count"]
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("source_global_file_sha256") != "sha256:" + normalize_sha256(expected_hash) or manifest.get("logical_global_skill_count") != count:
            raise RuntimeError(f"existing Global{round_index} downlink manifest identity mismatch")
        return
    materialize(global_path, root, expected_sha256=expected_hash, expected_skills=count, expected_round_index=round_index, experiment_id=f"v9-global{round_index}-client-validation", generation=round_index)


def validate_global(paths: dict[str, Path], round_index: int, python: Path) -> None:
    root = paths["global_validation_root"]
    processes: list[tuple[str, subprocess.Popen[Any], Any, Any]] = []
    for c in "ABC":
        client_root, output = root / f"client_{c}", root / f"client_{c}/validation"
        summary_path = output / "summary.json"
        if summary_path.is_file():
            load_complete_summary(summary_path, c, round_index)
            continue
        command = [str(python), "-m", f"stage2_local_v9.scripts.run_client_{c.lower()}_phase", "--phase", "validation", "--generation", str(round_index), "--manifest", str(MANIFESTS[c]), "--bank", str(client_root / "replacement_skillbank.json"), "--output-root", str(output), "--data-root", str(DATA_ROOT), "--python", str(python)]
        if c == "A":
            command += ["--max-control-retries", "12"]
        if output.exists():
            result = output / "result.json"
            if not result.is_file():
                raise RuntimeError(f"Global{round_index} Client {c} validation directory is incomplete without result")
            command += ["--resume-partial", "--resume-order-reference", str(ORDER_REFERENCES[c])]
        client_root.mkdir(parents=True, exist_ok=True)
        stdout, stderr = (client_root / "background.stdout.log").open("ab"), (client_root / "background.stderr.log").open("ab")
        processes.append((c, subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr), stdout, stderr))
    failures = []
    for c, process, stdout, stderr in processes:
        code = process.wait()
        stdout.close(); stderr.close()
        if code:
            failures.append(f"Client {c} exit {code}")
    if failures:
        raise RuntimeError(f"Global{round_index} validation failed: {failures}")
    for c in "ABC":
        load_complete_summary(root / f"client_{c}/validation/summary.json", c, round_index)


def evolve_local(next_generation: int, previous_paths: dict[str, Path], python: Path) -> None:
    global_generation = next_generation - 1
    parent_root = previous_paths["global_validation_root"]
    run_root = RUNS / f"v9_global{global_generation}_to_local_b{next_generation}_20261015_r1"
    processes: list[tuple[str, subprocess.Popen[Any], Any, Any]] = []
    for c in "ABC":
        client_root = run_root / f"client_{c}"
        state_path = client_root / "controller_state.json"
        if state_path.is_file():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state.get("status") == "complete":
                continue
            raise RuntimeError(f"Client {c} B{next_generation} has existing non-complete state; explicit audited resume required")
        command = [str(python), "-m", "stage3_2_role_agnostic_semantic_merge.run_global_to_local", "--client", c, "--generation", str(next_generation), "--base-count", str(json.loads((parent_root / "replacement_manifest.json").read_text(encoding="utf-8"))["logical_global_skill_count"]), "--run-root", str(client_root), "--parent-bank", str(parent_root / f"client_{c}/replacement_skillbank.json"), "--global-validation-summary", str(parent_root / f"client_{c}/validation/summary.json"), "--manifest", str(MANIFESTS[c]), "--data-root", str(DATA_ROOT), "--python", str(python)]
        run_root.mkdir(parents=True, exist_ok=True)
        stdout, stderr = (run_root / f"client_{c}.stdout.log").open("ab"), (run_root / f"client_{c}.stderr.log").open("ab")
        processes.append((c, subprocess.Popen(command, cwd=ROOT, stdout=stdout, stderr=stderr), stdout, stderr))
    failures = []
    for c, process, stdout, stderr in processes:
        code = process.wait()
        stdout.close(); stderr.close()
        if code:
            failures.append(f"Client {c} exit {code}")
    if failures:
        raise RuntimeError(f"local B{next_generation} chain failed: {failures}")
    for c in "ABC":
        state = json.loads((run_root / f"client_{c}/controller_state.json").read_text(encoding="utf-8"))
        if state.get("status") != "complete":
            raise RuntimeError(f"Client {c} B{next_generation} did not complete")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--controller-root", type=Path, required=True)
    p.add_argument("--python", type=Path, default=PYTHON_DEFAULT)
    p.add_argument("--poll-seconds", type=int, default=30)
    p.add_argument("--resume", action="store_true")
    args = p.parse_args()
    state_path = args.controller_root / "controller_state.json"
    args.controller_root.mkdir(parents=True, exist_ok=True)
    if state_path.exists():
        if not args.resume:
            raise SystemExit("existing Global5 controller requires explicit --resume")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("schema_version") != "stage3_2.full_skillbank_to_global5_controller.v1" or state.get("status") != "failed":
            raise SystemExit("resume requires the matching failed Global5 controller")
        failure = {key: state.get(key) for key in ("failed_at_step", "error_type", "error", "traceback", "failed_at")}
        state.setdefault("failure_history", []).append(failure)
        state.setdefault("resume_events", []).append({"resumed_at": now(), "from_step": state.get("failed_at_step")})
        for key in failure:
            state.pop(key, None)
        state["status"] = "running"
    else:
        if args.resume:
            raise SystemExit("--resume requires an existing controller state")
        state = {"schema_version": "stage3_2.full_skillbank_to_global5_controller.v1", "status": "running", "current_step": "wait_local_B3_validations", "completed_steps": [], "started_at": now(), "stop_after": "Global5_client_validation", "communication": "complete_skillbanks_only", "server_evaluation": None}
    write_json(state_path, state)
    def complete_step(name: str) -> None:
        if name not in state["completed_steps"]:
            state["completed_steps"].append(name)
    try:
        if "wait_local_B3_validations" not in state["completed_steps"]:
            wait_for_initial_b3(state, state_path, args.poll_seconds)
        for round_index in (3, 4, 5):
            paths = round_paths(round_index)
            state["current_step"] = f"aggregate_Global{round_index}"
            write_json(state_path, state)
            global_path, aggregation = aggregate(round_index, paths, args.python)
            complete_step(f"aggregate_Global{round_index}")
            state["current_step"] = f"validate_Global{round_index}"
            write_json(state_path, state)
            ensure_materialized(global_path, aggregation, paths, round_index)
            validate_global(paths, round_index, args.python)
            complete_step(f"validate_Global{round_index}")
            state.setdefault("global_results", {})[str(round_index)] = {"skill_count": aggregation["output_skill_count"], "global_file_sha256": aggregation["global_skillbank"]["file_sha256"], "client_validation": {c: json.loads((paths["global_validation_root"] / f"client_{c}/validation/summary.json").read_text(encoding="utf-8"))["success_count"] for c in "ABC"}}
            write_json(state_path, state)
            if round_index < 5:
                state["current_step"] = f"evolve_local_B{round_index+1}"
                write_json(state_path, state)
                evolve_local(round_index + 1, paths, args.python)
                complete_step(f"evolve_local_B{round_index+1}")
                write_json(state_path, state)
        state.update({"status": "complete", "current_step": None, "completed_at": now(), "stopped_before": ["Global6", "B6"]})
        write_json(state_path, state)
        return 0
    except BaseException as exc:
        state.update({"status": "failed", "failed_at_step": state.get("current_step"), "error_type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc(), "failed_at": now()})
        write_json(state_path, state)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
