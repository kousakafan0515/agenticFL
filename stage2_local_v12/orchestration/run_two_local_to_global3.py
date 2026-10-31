"""V10 synchronous federation: B2 -> G1, then two local rounds per Global.

The three clients execute each local or Global validation stage concurrently.
Every stage has a separate output directory; failure stops the chain without
overwriting or automatically joining partial episode results.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path

from stage2_local_v12.runtime.banks import file_hash, write_json
from stage2_local_v12.orchestration.import_v9_b1 import verify_import
from stage2_local_v12.orchestration.materialize_assets import EXPERIMENT_ID, materialize
from stage2_local_v12.evolution.role_evolver import now
from stage2_local_v12.orchestration.run_local_round import complete_summary


ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "stage2_local_v12/assets/seeds/imported_v9_b0_to_b1_20261018_r1"
PLAN = (
    ("local", 2), ("aggregate", 1), ("validate", 1),
    ("local", 3), ("local", 4), ("aggregate", 2), ("validate", 2),
    ("local", 5), ("local", 6), ("aggregate", 3), ("validate", 3),
)
SOURCE_GENERATION = {1: 2, 2: 4, 3: 6}


def local_root(root: Path, generation: int, client: str) -> Path:
    return root / "locals" / f"B{generation}" / f"client_{client}"


def aggregation_root(root: Path, round_index: int) -> Path:
    return root / "globals" / f"Global{round_index}" / "aggregation"


def validation_root(root: Path, round_index: int) -> Path:
    return root / "globals" / f"Global{round_index}" / "validation"


def parent_paths(root: Path, generation: int, client: str) -> tuple[Path, Path, str]:
    if generation == 2:
        base = SEED / f"client_{client}"
        return base / "B1_skillbank.json", base / "B1_validation/summary.json", "independent"
    if generation in (3, 5):
        round_index = 1 if generation == 3 else 2
        base = validation_root(root, round_index) / f"client_{client}"
        return base / "replacement_skillbank.json", base / "validation/summary.json", "global"
    base = local_root(root, generation - 1, client)
    return base / f"B{generation - 1}_skillbank.json", base / "validation/summary.json", "independent"


def preflight(args: argparse.Namespace) -> None:
    materialize(check=True)
    for client in "ABC":
        verify_import(SEED / f"client_{client}", client)
    if not args.python.is_file() or not args.data_root.is_dir():
        raise RuntimeError("locked Python or ALFWorld data root missing")
    if not os.environ.get("DASHSCOPE_API_KEY"):
        raise RuntimeError("DASHSCOPE_API_KEY missing")
    from stage2_local_v12.evolution.teacher_api import _local_evolution_config
    from stage2_local_v12.federation.aggregation_api import AggregationAPIConfig
    for config in (_local_evolution_config(), AggregationAPIConfig.from_env()):
        descriptor = config.descriptor()
        if config.model != "deepseek-flash" or descriptor.get("provider") != "deepseek_official" or descriptor.get("endpoint_origin") != "https://api.deepseek.com":
            raise RuntimeError("official DeepSeek deepseek-flash model lock failed")


def checked_local(root: Path, generation: int, client: str) -> dict | None:
    target = local_root(root, generation, client)
    state_path = target / "controller_state.json"
    if not state_path.exists():
        return None
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("status") != "complete":
        return None
    parent, _, _ = parent_paths(root, generation, client)
    bank = target / f"B{generation}_skillbank.json"
    summary = complete_summary(target / "validation/summary.json", client, generation, "validation")
    if state.get("parent_bank_file_sha256") != file_hash(parent) or state.get("output_bank_file_sha256") != file_hash(bank):
        raise RuntimeError(f"Client {client} B{generation}: completed bank identity changed")
    if json.loads((target / "validation/source_lock.json").read_text(encoding="utf-8")).get("bank_file_sha256") != file_hash(bank):
        raise RuntimeError(f"Client {client} B{generation}: validation bank lock changed")
    return {"success_count": summary["success_count"], "bank_file_sha256": file_hash(bank), "result_file_sha256": summary["result_file_sha256"]}


def checked_aggregate(root: Path, round_index: int) -> dict | None:
    target = aggregation_root(root, round_index)
    summary_path = target / "summary.json"
    if not summary_path.exists():
        return None
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    bank = target / f"global_skillbank{round_index}.json"
    manifest = json.loads((target / "input_manifest.json").read_text(encoding="utf-8"))
    if summary.get("status") != "complete" or summary.get("round_index") != round_index or manifest.get("source_generation") != SOURCE_GENERATION[round_index] or summary.get("global_skillbank", {}).get("file_sha256") != file_hash(bank):
        raise RuntimeError(f"Global{round_index}: completed aggregation identity changed")
    for client in "ABC":
        checked = checked_local(root, SOURCE_GENERATION[round_index], client)
        if checked is None or manifest["inputs"][client]["bank_file_sha256"] != checked["bank_file_sha256"]:
            raise RuntimeError(f"Global{round_index}: Client {client} upload changed")
    return {"skill_count": summary["output_skill_count"], "bank_file_sha256": file_hash(bank)}


def checked_validation(root: Path, round_index: int) -> dict | None:
    target = validation_root(root, round_index)
    state_path = target / "controller_state.json"
    if not state_path.exists():
        return None
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("status") != "complete":
        return None
    bank = aggregation_root(root, round_index) / f"global_skillbank{round_index}.json"
    if state.get("global_round") != round_index or state.get("generation") != SOURCE_GENERATION[round_index] or state.get("global_bank_file_sha256") != file_hash(bank):
        raise RuntimeError(f"Global{round_index}: validation identity changed")
    for client in "ABC":
        base = target / f"client_{client}"
        complete_summary(base / "validation/summary.json", client, SOURCE_GENERATION[round_index], "validation")
        if json.loads((base / "validation/source_lock.json").read_text(encoding="utf-8"))["bank_file_sha256"] != file_hash(base / "replacement_skillbank.json"):
            raise RuntimeError(f"Global{round_index}: Client {client} downlink lock changed")
    return {"pooled_success_count": state["pooled_success_count"], "clients": state["results"]}


def stage_result(root: Path, kind: str, index: int) -> dict | None:
    if kind == "local":
        results = {client: checked_local(root, index, client) for client in "ABC"}
        return results if all(results.values()) else None
    return checked_aggregate(root, index) if kind == "aggregate" else checked_validation(root, index)


def run_local_parallel(args: argparse.Namespace, generation: int, state: dict) -> None:
    processes: dict[str, subprocess.Popen] = {}
    handles = []
    try:
        for client in "ABC":
            if checked_local(args.run_root, generation, client) is not None:
                continue
            parent, parent_summary, parent_kind = parent_paths(args.run_root, generation, client)
            target = local_root(args.run_root, generation, client)
            command = [str(args.python), "-m", "stage2_local_v12.orchestration.run_local_round", "--client", client, "--generation", str(generation), "--parent-kind", parent_kind, "--parent-bank", str(parent), "--parent-validation-summary", str(parent_summary), "--run-root", str(target), "--manifest", str(ROOT / f"stage2_local_v12/assets/manifests/client_{client.lower()}_generation_01.json"), "--data-root", str(args.data_root), "--experiment-id", EXPERIMENT_ID, "--python", str(args.python)]
            if (target / "controller_state.json").exists():
                command.append("--resume")
            log_dir = args.run_root / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            out = (log_dir / f"B{generation}_client_{client}.stdout.log").open("ab")
            err = (log_dir / f"B{generation}_client_{client}.stderr.log").open("ab")
            handles.extend((out, err))
            processes[client] = subprocess.Popen(command, cwd=ROOT, stdout=out, stderr=err)
            state.setdefault("processes", {})[client] = processes[client].pid
            write_json(args.run_root / "controller_state.json", state)
        while processes:
            for client, process in list(processes.items()):
                code = process.poll()
                if code is None:
                    continue
                del processes[client]
                if code != 0:
                    for other in processes.values():
                        other.terminate()
                    for other in processes.values():
                        other.wait(timeout=30)
                    raise RuntimeError(f"Client {client} B{generation} exited {code}; see logs/B{generation}_client_{client}.stderr.log")
                checked_local(args.run_root, generation, client)
            if processes:
                time.sleep(args.poll_seconds)
    finally:
        for handle in handles:
            handle.close()
        state["processes"] = {}
        write_json(args.run_root / "controller_state.json", state)


def run_single(args: argparse.Namespace, kind: str, index: int) -> None:
    if kind == "aggregate":
        target = aggregation_root(args.run_root, index)
        generation = SOURCE_GENERATION[index]
        command = [str(args.python), "-m", "stage2_local_v12.federation.server_aggregate", "--round-index", str(index), "--source-generation", str(generation), "--experiment-id", EXPERIMENT_ID, "--output-root", str(target)]
        for client in "ABC":
            local = local_root(args.run_root, generation, client)
            command += [f"--bank-{client.lower()}", str(local / f"B{generation}_skillbank.json"), f"--validation-{client.lower()}", str(local / "validation/summary.json")]
    else:
        target = validation_root(args.run_root, index)
        command = [str(args.python), "-m", "stage2_local_v12.federation.run_global_validation", "--global-bank", str(aggregation_root(args.run_root, index) / f"global_skillbank{index}.json"), "--generation", str(SOURCE_GENERATION[index]), "--global-round", str(index), "--parallel-clients", "--experiment-id", EXPERIMENT_ID, "--run-root", str(target), "--data-root", str(args.data_root), "--python", str(args.python)]
        if (target / "controller_state.json").exists():
            command.append("--resume")
    log_dir = args.run_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    with (log_dir / f"{kind}_{index}.stdout.log").open("ab") as out, (log_dir / f"{kind}_{index}.stderr.log").open("ab") as err:
        subprocess.run(command, cwd=ROOT, stdout=out, stderr=err, check=True)


def run(args: argparse.Namespace) -> dict:
    preflight(args)
    state_path = args.run_root / "controller_state.json"
    identity = {"schema_version": "stage2_local_v10.two_local_to_global3.v1", "implementation_id": "stage2-local-v12-self-contained-v1", "experiment_id": EXPERIMENT_ID, "seed_b1_hashes": {client: file_hash(SEED / f"client_{client}" / "B1_skillbank.json") for client in "ABC"}, "manifest_hashes": {client: file_hash(ROOT / f"stage2_local_v12/assets/manifests/client_{client.lower()}_generation_01.json") for client in "ABC"}, "plan": [f"{kind}_{index}" for kind, index in PLAN], "stop_after": "Global3_three_client_validation"}
    if state_path.exists():
        if not args.resume:
            raise RuntimeError("existing controller requires --resume")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if any(state.get(key) != value for key, value in identity.items()) or state.get("status") not in ("running", "failed"):
            raise RuntimeError("resume identity or status mismatch")
        state.setdefault("resume_events", []).append({"time": now(), "step": state.get("current_step")})
    else:
        if args.resume or (args.run_root.exists() and any(args.run_root.iterdir())):
            raise RuntimeError("fresh V10 output root must be empty")
        args.run_root.mkdir(parents=True, exist_ok=True)
        state = {**identity, "status": "running", "started_at": now(), "current_step": None, "completed_steps": [], "results": {}}
    state["status"] = "running"
    write_json(state_path, state)
    try:
        for kind, index in PLAN:
            name = f"{kind}_{index}"
            state["current_step"] = name
            write_json(state_path, state)
            result = stage_result(args.run_root, kind, index)
            if result is None:
                if kind == "local":
                    run_local_parallel(args, index, state)
                else:
                    run_single(args, kind, index)
                result = stage_result(args.run_root, kind, index)
            if result is None:
                raise RuntimeError(f"{name}: incomplete after command")
            state["results"][name] = result
            if name not in state["completed_steps"]:
                state["completed_steps"].append(name)
            write_json(state_path, state)
        state.update(status="complete", current_step=None, completed_at=now())
        write_json(state_path, state)
        return state
    except BaseException as exc:
        state.update(status="failed", error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc(), failed_at=now())
        write_json(state_path, state)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--poll-seconds", type=float, default=10)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    if args.preflight_only:
        preflight(args)
        print(json.dumps({"status": "preflight_ok", "plan": [f"{kind}_{index}" for kind, index in PLAN], "clients": "ABC", "paid_calls": 0}, ensure_ascii=False))
    else:
        print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
