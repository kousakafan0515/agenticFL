"""Read-only paired audit of V10 B2→Global1 and B6→Global3 harm cases.

Writes only an analysis artifact. An injected Skill is an exposure, not proof
that an agent followed the Skill or that the Skill caused its outcome.
"""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "stage2_local_v12/runs/two_local_global3"
DEFAULT_OUT = ROOT / "stage2_local_v12/artifacts/global_harm_audit"
PAIRS = ((2, 1), (6, 3))
TASK_BUCKETS = {
    "pick_and_place_simple": "简单取放",
    "look_at_obj_in_light": "台灯观察",
    "pick_clean_then_place_in_recep": "清洗后放置",
    "pick_heat_then_place_in_recep": "加热后放置",
    "pick_cool_then_place_in_recep": "冷却后放置",
    "pick_two_obj_and_place": "双物品放置",
}
REQUIRED_VERB = {
    "pick_clean_then_place_in_recep": "clean",
    "pick_heat_then_place_in_recep": "heat",
    "pick_cool_then_place_in_recep": "cool",
}


def file_hash(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def read_stage(path: Path, client: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result_path = path / "result.json"
    summary = json.loads((path / "summary.json").read_text(encoding="utf-8"))
    if summary.get("status") != "complete" or summary.get("task_count") != 134 or summary.get("client") != client or summary.get("api_clean") is not True:
        raise RuntimeError(f"incomplete or non-clean validation: {path}")
    if file_hash(result_path) != summary["result_file_sha256"]:
        raise RuntimeError(f"result hash mismatch: {result_path}")
    episodes = json.loads(result_path.read_text(encoding="utf-8"))["episodes"]
    if len(episodes) != 134 or len({e["game_file"] for e in episodes}) != 134:
        raise RuntimeError(f"episode identity mismatch: {result_path}")
    if sum(bool(e["success"]) for e in episodes) != summary["success_count"]:
        raise RuntimeError(f"summary success mismatch: {result_path}")
    return summary, episodes


def actions(episode: dict[str, Any]) -> list[str]:
    return [(step.get("action") or "").lower() for step in episode.get("steps", [])]


def role_injections(episode: dict[str, Any], bank: dict[str, Any]) -> dict[str, Any]:
    output = {}
    bucket = TASK_BUCKETS[episode["task_type"]]
    expected_ids = [skill["global_skill_id"] for skill in bank["general"]]
    expected_ids += [skill["global_skill_id"] for skill in bank["task_specific"][bucket]]
    for role, evidence in episode["skill_injections"].items():
        keys = evidence["injected_skill_keys"]
        ids = [key.rsplit("/", 1)[-1] for key in keys]
        if ids != expected_ids or evidence["injected_skill_count"] != len(keys):
            raise RuntimeError(f"actual injected IDs differ from Global bank: {role} {episode['game_file']}")
        display_map = evidence["display_id_map"]
        if set(display_map) != set(ids):
            raise RuntimeError("display ID map does not match injected IDs")
        output[role] = {
            "injected_skill_keys": keys,
            "injected_skill_ids": ids,
            "injected_skill_count": evidence["injected_skill_count"],
            "injected_character_count": evidence["injected_character_count"],
            "source_skill_keys_by_id": {ident: display_map[ident]["source_skill_keys"] for ident in ids},
        }
    if not output:
        raise RuntimeError("no role injection evidence")
    return output


def control_mentions(episode: dict[str, Any], client: str, verb: str | None) -> bool | None:
    if verb is None:
        return None
    if client == "A":
        return verb in episode.get("planner", {}).get("output", "").lower()
    calls = episode.get("critic_calls", []) if client == "B" else episode.get("supervisor_calls", [])
    return any(verb in call.get("model_output", "").lower() for call in calls)


def make_record(local: dict[str, Any], global_episode: dict[str, Any], index: int,
                client: str, local_gen: int, global_gen: int,
                bank: dict[str, Any]) -> dict[str, Any]:
    verb = REQUIRED_VERB.get(global_episode["task_type"])
    before, after = actions(local), actions(global_episode)
    injections = role_injections(global_episode, bank)
    old_chars = {role: local["skill_injections"][role]["injected_character_count"] for role in injections}
    nonempty_steps = [step for step in global_episode.get("steps", []) if step.get("action")]
    return {
        "global_round": global_gen, "local_parent": f"B{local_gen}", "client": client,
        "task_type": global_episode["task_type"], "task_bucket": TASK_BUCKETS[global_episode["task_type"]],
        "game_file": global_episode["game_file"], "episode_index": index,
        "local_success": True, "global_success": False,
        "local_step_count": len(before), "global_step_count": len(after),
        "global_termination_reason": global_episode.get("terminal_reason", global_episode.get("termination_reason")),
        "required_action": verb,
        "local_required_action_count": sum(action.startswith(f"{verb} ") for action in before) if verb else None,
        "global_required_action_count": sum(action.startswith(f"{verb} ") for action in after) if verb else None,
        "global_put_in_microwave_count": sum(action.startswith("put ") and "microwave" in action for action in after),
        "global_put_in_fridge_count": sum(action.startswith("put ") and "fridge" in action for action in after),
        "global_null_action_count": sum(not action for action in after),
        "control_role_mentions_required_action": control_mentions(global_episode, client, verb),
        "local_injected_characters_by_role": old_chars,
        "global_role_injections": injections,
        "global_actions": [step.get("action") for step in global_episode.get("steps", [])],
        "last_nonempty_action": nonempty_steps[-1].get("action") if nonempty_steps else None,
        "last_nonempty_observation": nonempty_steps[-1].get("observation") if nonempty_steps else None,
    }


def analyze() -> dict[str, Any]:
    input_files = []
    records = []
    categories = collections.defaultdict(lambda: collections.Counter())
    by_client = collections.defaultdict(lambda: collections.Counter())
    for local_gen, global_gen in PAIRS:
        bank_path = RUN / f"globals/Global{global_gen}/aggregation/global_skillbank{global_gen}.json"
        bank = json.loads(bank_path.read_text(encoding="utf-8"))
        input_files.append({"path": bank_path.relative_to(ROOT).as_posix(), "sha256": file_hash(bank_path)})
        for client in "ABC":
            local_dir = RUN / f"locals/B{local_gen}/client_{client}/validation"
            global_dir = RUN / f"globals/Global{global_gen}/validation/client_{client}/validation"
            old_summary, old_episodes = read_stage(local_dir, client)
            new_summary, new_episodes = read_stage(global_dir, client)
            old = {episode["game_file"]: episode for episode in old_episodes}
            if set(old) != {episode["game_file"] for episode in new_episodes}:
                raise RuntimeError(f"paired task identities differ for {client} Global{global_gen}")
            for path, summary in ((local_dir / "result.json", old_summary), (global_dir / "result.json", new_summary)):
                input_files.append({"path": path.relative_to(ROOT).as_posix(), "sha256": summary["result_file_sha256"]})
            for index, episode in enumerate(new_episodes, 1):
                prior = old[episode["game_file"]]
                if episode["task_type"] != prior["task_type"]:
                    raise RuntimeError("paired task type changed")
                category = categories[(global_gen, episode["task_type"])]
                category["task_count"] += 1
                category["local_success"] += bool(prior["success"])
                category["global_success"] += bool(episode["success"])
                category["rescue"] += not prior["success"] and episode["success"]
                category["harm"] += prior["success"] and not episode["success"]
                client_counts = by_client[(global_gen, client)]
                client_counts["local_success"] += bool(prior["success"])
                client_counts["global_success"] += bool(episode["success"])
                client_counts["rescue"] += not prior["success"] and episode["success"]
                client_counts["harm"] += prior["success"] and not episode["success"]
                if prior["success"] and not episode["success"]:
                    records.append(make_record(prior, episode, index, client, local_gen, global_gen, bank))
    if len(records) != 107 or sum(r["global_round"] == 1 for r in records) != 61 or sum(r["global_round"] == 3 for r in records) != 46:
        raise RuntimeError("harm count differs from frozen paired audit")
    overlap = []
    keys = {(r["global_round"], r["client"], r["game_file"]) for r in records}
    for row in records:
        if row["global_round"] == 1 and (3, row["client"], row["game_file"]) in keys:
            overlap.append({"client": row["client"], "task_type": row["task_type"], "game_file": row["game_file"]})
    return {"schema_version": "v10.global_harm_audit.v1", "read_only_analysis": True,
            "comparison": "B2->Global1 and B6->Global3 on identical per-client frozen validation tasks",
            "source_files": input_files,
            "by_client": [{"global_round": g, "client": c, **dict(v)} for (g, c), v in sorted(by_client.items())],
            "by_task_category": [{"global_round": g, "task_type": t, "task_bucket": TASK_BUCKETS[t], **dict(v)}
                                 for (g, t), v in sorted(categories.items())],
            "repeated_harm_cases": overlap, "harm_cases": records}


def write_new(path: Path, contents: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    data = analyze()
    out = args.output_root
    write_new(out / "harm_cases.json", json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    columns = ("global_round", "local_parent", "client", "task_type", "task_bucket", "game_file", "episode_index",
               "global_termination_reason", "local_step_count", "global_step_count", "required_action",
               "local_required_action_count", "global_required_action_count", "global_put_in_microwave_count",
               "global_put_in_fridge_count", "global_null_action_count", "control_role_mentions_required_action",
               "local_injected_characters_by_role", "global_role_injections", "last_nonempty_action", "last_nonempty_observation")
    csv_path = out / "harm_cases.csv"
    if csv_path.exists():
        raise RuntimeError(f"refusing to overwrite {csv_path}")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in data["harm_cases"]:
            writer.writerow({key: json.dumps(row[key], ensure_ascii=False) if isinstance(row.get(key), (dict, list)) else row.get(key)
                             for key in columns})
    print(json.dumps({"harm_cases": len(data["harm_cases"]), "repeated": len(data["repeated_harm_cases"]),
                      "inputs": len(data["source_files"]), "json_sha256": file_hash(out / "harm_cases.json"),
                      "csv_sha256": file_hash(csv_path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
