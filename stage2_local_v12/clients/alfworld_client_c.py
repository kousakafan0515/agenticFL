"""Client C: dynamic Supervisor -> Search/Operation Worker for ALFWorld Text.

The Supervisor never acts in the environment.  It is called once at episode
start and again only after the active Worker returns HANDOFF or BLOCKED.  The
two Workers both execute real ALFWorld actions: Search handles finding and
acquiring objects; Operation handles transformations and goal delivery.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI

from alfworld.agents.environment.alfred_tw_env import AlfredTWEnv, TASK_TYPES
from alfworld_p0 import (
    INVALID_ACTION_PATTERN_FAILURE_LIMIT,
    INVALID_ACTION_PATTERN_RECOVERY_LIMIT,
    StateLedger,
    append_trace,
    call_model,
    canonical_game_path,
    extract_action,
    game_paths_from_results,
    make_config,
    preselected_alfred_tw_env,
    raise_if_api_error,
    select_train_game_files,
    trailing_invalid_action_pattern,
)
from skillbank_loader import add_skill_loader_arguments, loader_from_args


OPERATION_CARD = """ALFWORLD OPERATION CARD:
- Carry only one object. Before take or put, go to the object's or destination
  receptacle; open it first if it is closed.
- To clean/heat/cool a held object, directly perform the corresponding
  environment operation. You do not need to put the object inside an appliance first.
- A desklamp is fixed and cannot be taken.
- 'Nothing happens.' means the preceding Action was invalid and changed no
  state. Choose a different Action unless state has changed.
"""

OPERATION_CARD_INVALID_ONLY = """ALFWORLD OPERATION CARD:
- 'Nothing happens.' means the preceding Action was invalid and changed no
  state. Choose a different Action unless state has changed.
"""

OPERATION_CARD_WEAK = """ALFWORLD OPERATION CARD:
- Carry only one object. Before take or put, go to the object's or destination
  receptacle; open it first if it is closed.
- Cleaning, heating, and cooling depend on the held object and current
  environment state. Do not assume an object must first be placed inside an appliance.
- A desklamp is fixed and cannot be taken.
- 'Nothing happens.' means the preceding Action was invalid and changed no
  state. Choose a different Action unless state has changed.
"""


SUPERVISOR_SYSTEM_PROMPT = """You are the non-acting Supervisor of a text household task.
You never operate the environment. Based only on supplied task facts and real
environment evidence, assign exactly one current local mission to SEARCH or
OPERATION.

SEARCH is responsible for finding, reaching, opening, and taking required
objects. OPERATION is responsible for transforming a held object when required
and delivering it to its required destination. Do not make a full fixed plan;
decide only the current phase. Do not ask a Worker to perform an unnecessary
later phase.

For a normal assignment, return exactly these three lines and nothing else:
ASSIGN: SEARCH or OPERATION
MISSION: one concrete current local mission
RETURN WHEN: observable condition for HANDOFF, or sufficient blocking evidence

When the supplied control state contains sufficient evidence that the whole
task cannot be completed or there is no new grounded direction to assign, you
may instead return exactly:
Status: FAILED
Do not return Status: FAILED after one unsuccessful Worker report. You never
operate the environment.
"""


SEARCH_SYSTEM_PROMPT = """You are Search Worker in a text household environment. Complete only the
Supervisor's current MISSION: finding, reaching, opening, and taking objects.
Do not perform transformations or final placement unless they are strictly
necessary to satisfy this MISSION.

For a normal turn, return exactly two lines and nothing else:
Thought: one short sentence about the next action.
Action: one environment command.

When RETURN WHEN has been satisfied, return exactly:
Thought: brief evidence from the latest environment state.
Status: HANDOFF

If you judge that the current MISSION cannot be completed, or the current
search has repeatedly been ineffective with no new direction grounded in the
observations, you may instead return Status: BLOCKED in the same two-line form.
Never include Action and Status in the same response. You never declare the
whole task completed or failed.

Use names exactly as present in the observation. The accepted commands are:
go to <receptacle>
open <receptacle>
close <receptacle>
take <object> from <receptacle>
put <object> in/on <receptacle> (type the literal token "in/on")
use <object>
clean <object> with <sink or bathtub>
heat <object> with <microwave>
cool <object> with <fridge>
inventory
look
examine <object or receptacle>
"""


OPERATION_SYSTEM_PROMPT = """You are Operation Worker in a text household environment. Complete only the
Supervisor's current MISSION: transforming a held object when required and
delivering it to its required destination. Do not independently begin later
unassigned phases.

For a normal turn, return exactly two lines and nothing else:
Thought: one short sentence about the next action.
Action: one environment command.

When RETURN WHEN has been satisfied, return exactly:
Thought: brief evidence from the latest environment state.
Status: HANDOFF

If you judge that the current MISSION cannot be completed, or the current
strategy has repeatedly been ineffective with no new direction grounded in the
observations, you may instead return Status: BLOCKED in the same two-line form.
Never include Action and Status in the same response. You never declare the
whole task completed or failed.

Use names exactly as present in the observation. The accepted commands are:
go to <receptacle>
open <receptacle>
close <receptacle>
take <object> from <receptacle>
put <object> in/on <receptacle> (type the literal token "in/on")
use <object>
clean <object> with <sink or bathtub>
heat <object> with <microwave>
cool <object> with <fridge>
inventory
look
examine <object or receptacle>
"""


STATUS_RE = re.compile(
    r"^\s*Thought\s*:\s*.+?\s*\n\s*Status\s*:\s*(HANDOFF|BLOCKED)\s*$",
    re.IGNORECASE | re.DOTALL,
)
DISPATCH_RE = re.compile(
    r"^\s*ASSIGN\s*:\s*(SEARCH|OPERATION)\s*\n"
    r"\s*MISSION\s*:\s*(.+?)\s*\n"
    r"\s*RETURN\s+WHEN\s*:\s*(.+?)\s*$",
    re.IGNORECASE | re.DOTALL,
)
SUPERVISOR_FAILED_RE = re.compile(r"^\s*Status\s*:\s*FAILED\s*$", re.IGNORECASE)


def recent_trace_block(steps: list[dict[str, Any]], limit: int) -> str:
    """Only completed environment turns are supplied as raw trajectory."""
    rows: list[str] = []
    completed = [item for item in steps if "action" in item and "observation" in item]
    for item in completed[-limit:]:
        # C stores each Worker response under worker_calls, unlike the older
        # single-agent runners which keep model_output on the step itself.
        # Read the final call because it is the response that produced the
        # executed action after any format-repair attempt.
        calls = item.get("worker_calls") or []
        model_output = item.get("model_output") or (
            calls[-1].get("model_output", "") if calls else ""
        )
        rows.extend([
            f"Turn {item['action_step']} {item['worker']} Thought/Action:",
            model_output,
            f"Turn {item['action_step']} environment observation:",
            item["observation"],
        ])
    return "\n".join(rows) if rows else "No completed environment actions yet."


def supervisor_messages(
    initial_observation: str,
    ledger: StateLedger,
    steps: list[dict[str, Any]],
    control: dict[str, Any],
    history_turns: int,
    operation_card: str,
    skill_suffix: str = "",
) -> list[dict[str, str]]:
    sections = [
        "INITIAL ENVIRONMENT AND ENTIRE TASK (verbatim; fixed throughout this episode):\n" + initial_observation,
        operation_card,
    ]
    if sum("action" in item for item in steps) >= history_turns:
        sections.append(ledger.event_ledger())
    sections.extend([
        f"RECENT {history_turns} COMPLETE GLOBAL INTERACTION TURNS:\n" + recent_trace_block(steps, history_turns),
        "CURRENT CONTROL STATE:\n"
        + f"Trigger: {control['trigger']}\n"
        + f"Previous Worker: {control.get('worker') or 'none'}\n"
        + f"Previous Mission: {control.get('mission') or 'none'}\n"
        + f"Worker feedback: {control.get('feedback') or 'initial dispatch'}",
        "CURRENT LATEST ENVIRONMENT OBSERVATION (verbatim; latest factual state):\n" + ledger.last_observation,
    ])
    system_prompt = SUPERVISOR_SYSTEM_PROMPT.rstrip()
    if skill_suffix:
        system_prompt += "\n\n" + skill_suffix
    return [{"role": "system", "content": system_prompt}, {"role": "user", "content": "\n\n".join(sections)}]


def worker_messages(
    worker: str,
    initial_observation: str,
    ledger: StateLedger,
    steps: list[dict[str, Any]],
    dispatch: dict[str, str],
    history_turns: int,
    operation_card: str,
    skill_suffix: str = "",
) -> list[dict[str, str]]:
    base = SEARCH_SYSTEM_PROMPT if worker == "SEARCH" else OPERATION_SYSTEM_PROMPT
    sections = [
        "INITIAL ENVIRONMENT AND ENTIRE TASK (verbatim; fixed throughout this episode):\n" + initial_observation,
        "CURRENT SUPERVISOR ASSIGNMENT:\n"
        + f"MISSION: {dispatch['mission']}\nRETURN WHEN: {dispatch['return_when']}",
    ]
    if sum("action" in item for item in steps) >= history_turns:
        sections.append(ledger.event_ledger())
    sections.extend([
        f"RECENT {history_turns} COMPLETE GLOBAL INTERACTION TURNS:\n" + recent_trace_block(steps, history_turns),
        "CURRENT LATEST ENVIRONMENT OBSERVATION (verbatim; act on this now):\n" + ledger.last_observation,
    ])
    system_prompt = (base + "\n" + operation_card).rstrip()
    if skill_suffix:
        system_prompt += "\n\n" + skill_suffix
    return [{"role": "system", "content": system_prompt}, {"role": "user", "content": "\n\n".join(sections)}]


def parse_dispatch(text: str) -> tuple[str, dict[str, str] | None]:
    if SUPERVISOR_FAILED_RE.fullmatch(text.strip()):
        return "failed", None
    match = DISPATCH_RE.fullmatch(text.strip())
    if not match:
        return "invalid", None
    return "dispatch", {
        "worker": match.group(1).upper(),
        "mission": " ".join(match.group(2).split()),
        "return_when": " ".join(match.group(3).split()),
    }


def parse_worker(text: str) -> tuple[str, str | None]:
    """Return (kind, action-or-status); kind is action/status/invalid."""
    status_match = STATUS_RE.fullmatch(text.strip())
    if status_match:
        return "status", status_match.group(1).upper()
    action = extract_action(text)
    # A Status marker anywhere else is a mixed response, not an action.
    if action and not re.search(r"(?:^|\n)\s*Status\s*:", text, re.IGNORECASE):
        return "action", " ".join(action.split())
    return "invalid", None


def append_repair_message(messages: list[dict[str, str]], previous: str, instruction: str) -> list[dict[str, str]]:
    return messages + [
        {"role": "assistant", "content": previous},
        {"role": "user", "content": instruction},
    ]


def call_supervisor(
    client: OpenAI,
    args: argparse.Namespace,
    messages: list[dict[str, str]],
) -> tuple[str, dict[str, str] | None, list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    request = messages
    for attempt in range(1, 3):
        started = time.monotonic()
        text, usage = call_model(client, args.model, request, args.send_disable_thinking,
                                 args.supervisor_max_completion_tokens, args.transport_retries, args.generation_seed)
        kind, dispatch = parse_dispatch(text)
        records.append({
            "attempt": attempt, "model_output": text, "usage": usage,
            "latency_s": round(time.monotonic() - started, 3),
            "context": request[-1]["content"], "parse_error": kind == "invalid",
        })
        if kind != "invalid":
            return kind, dispatch, records
        request = append_repair_message(
            messages, text,
            "Your format was invalid. Reissue either exactly three lines: ASSIGN: SEARCH or OPERATION; MISSION: ...; RETURN WHEN: ...; or exactly Status: FAILED when permitted.",
        )
    return "invalid", None, records


def call_worker(
    client: OpenAI,
    args: argparse.Namespace,
    messages: list[dict[str, str]],
) -> tuple[str, str | None, list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    request = messages
    for attempt in range(1, 3):
        started = time.monotonic()
        text, usage = call_model(client, args.model, request, args.send_disable_thinking,
                                 args.max_completion_tokens, args.transport_retries, args.generation_seed)
        kind, payload = parse_worker(text)
        records.append({
            "attempt": attempt, "model_output": text, "usage": usage,
            "latency_s": round(time.monotonic() - started, 3),
            "context": request[-1]["content"], "parse_error": kind == "invalid",
        })
        if kind != "invalid":
            return kind, payload, records
        request = append_repair_message(
            messages, text,
            "Your response was invalid. Return either exactly Thought + one Action, or exactly Thought + Status: HANDOFF/BLOCKED. Never combine Action and Status or give multiple actions.",
        )
    return "invalid", None, records


def reference_games_by_type(result_paths: list[str], task_types: list[int], per_type: int, start_index: int) -> dict[int, list[str]]:
    selected: dict[int, list[str]] = {task_type: [] for task_type in task_types}
    seen: dict[int, set[str]] = {task_type: set() for task_type in task_types}
    for result_path in result_paths:
        try:
            episodes = json.loads(Path(result_path).read_text(encoding="utf-8"))["episodes"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise SystemExit(f"Could not read reference result file {result_path}: {exc}") from exc
        for episode in episodes:
            task_type, game_file = episode.get("task_type_id"), episode.get("game_file")
            if task_type not in selected or not isinstance(game_file, str):
                continue
            canonical = canonical_game_path(game_file)
            if canonical not in seen[task_type]:
                selected[task_type].append(game_file)
                seen[task_type].add(canonical)
    cohort: dict[int, list[str]] = {}
    for task_type, paths in selected.items():
        chosen = paths[start_index:start_index + per_type]
        if len(chosen) != per_type:
            raise SystemExit(f"Reference results contain only {len(paths)} distinct {TASK_TYPES[task_type]} games; cannot select {per_type} starting at index {start_index}.")
        cohort[task_type] = chosen
    return cohort


def run_episode(env: Any, client: OpenAI, args: argparse.Namespace, task_type: int, operation_card: str) -> dict[str, Any]:
    observation, info = env.reset()
    initial_observation = observation[0]
    game_file = info["extra.gamefile"][0]
    ledger = StateLedger(initial_observation)
    steps: list[dict[str, Any]] = []
    supervisor_calls: list[dict[str, Any]] = []
    action_count = 0
    handoffs_without_action = 0
    won = False
    supervisor_injection = args.skill_loader.render("Supervisor", task_type)
    search_injection = args.skill_loader.render("Search Worker", task_type)
    operation_injection = args.skill_loader.render("Operation Worker", task_type)
    skill_injections = {
        "Supervisor": supervisor_injection.audit,
        "Search Worker": search_injection.audit,
        "Operation Worker": operation_injection.audit,
    }

    def finish(termination_reason: str, error: str | None = None) -> dict[str, Any]:
        return episode_result(
            task_type, game_file, initial_observation, won, steps, supervisor_calls,
            action_count, termination_reason, error, skill_injections,
        )

    control: dict[str, Any] = {"trigger": "initial dispatch", "worker": None, "mission": None, "feedback": None}
    append_trace(args.trace_file, {"event": "reset", "client": "C", "task_type": TASK_TYPES[task_type], "game_file": game_file, "initial_observation": initial_observation, "skill_injections": skill_injections})

    while action_count < args.max_steps:
        supervisor_request = supervisor_messages(
            initial_observation, ledger, steps, control, args.history_window_turns,
            operation_card, supervisor_injection.text,
        )
        print(f"Calling Supervisor {args.model}: {TASK_TYPES[task_type]} ({control['trigger']})", flush=True)
        try:
            supervisor_kind, dispatch, records = call_supervisor(client, args, supervisor_request)
        except Exception as exc:
            raise_if_api_error(exc)
            return finish("supervisor_error", repr(exc))
        for record in records:
            supervisor_calls.append({"control": dict(control), **record})
            append_trace(args.trace_file, {"event": "supervisor_call", "task_type": TASK_TYPES[task_type], "game_file": game_file, "control": dict(control), **record})
        if supervisor_kind == "failed":
            append_trace(args.trace_file, {"event": "supervisor_failed", "task_type": TASK_TYPES[task_type], "game_file": game_file, "control": dict(control)})
            return finish("supervisor_declared_failed")
        if supervisor_kind != "dispatch" or not dispatch:
            return finish("supervisor_parse_error")

        active_worker = dispatch["worker"]
        while action_count < args.max_steps:
            worker_injection = search_injection if active_worker == "SEARCH" else operation_injection
            request = worker_messages(
                active_worker, initial_observation, ledger, steps, dispatch,
                args.history_window_turns, operation_card, worker_injection.text,
            )
            print(f"Calling {active_worker} Worker {args.model}: {TASK_TYPES[task_type]} step {action_count + 1}/{args.max_steps}", flush=True)
            try:
                kind, payload, records = call_worker(client, args, request)
            except Exception as exc:
                raise_if_api_error(exc)
                return finish("worker_error", repr(exc))
            if kind == "invalid":
                entry = {"action_step": action_count + 1, "worker": active_worker, "kind": "worker_parse_error", "worker_calls": records}
                steps.append(entry)
                append_trace(args.trace_file, {"event": "worker_parse_error", "task_type": TASK_TYPES[task_type], "game_file": game_file, **entry})
                return finish("worker_parse_error")
            if kind == "status":
                handoffs_without_action += 1
                entry = {"action_step": action_count, "worker": active_worker, "kind": "worker_status", "status": payload, "worker_calls": records}
                steps.append(entry)
                append_trace(args.trace_file, {"event": "worker_status", "task_type": TASK_TYPES[task_type], "game_file": game_file, **entry})
                if payload == "BLOCKED":
                    return finish("worker_declared_failed")
                if handoffs_without_action > args.max_handoffs_without_action:
                    return finish("handoff_loop_guard")
                control = {"trigger": f"worker returned {payload}", "worker": active_worker, "mission": dispatch["mission"], "feedback": records[-1]["model_output"]}
                break

            handoffs_without_action = 0
            started = time.monotonic()
            try:
                next_obs, scores, dones, infos = env.step([payload])
                observation = next_obs[0]
                action_count += 1
                won = bool(dones[0] and infos["won"][0])
                entry = {
                    "action_step": action_count, "worker": active_worker, "raw_action": payload,
                    "action": payload, "observation": observation, "reward": float(scores[0]), "worker_calls": records,
                    "latency_s": round(time.monotonic() - started, 3), "mission": dispatch["mission"],
                }
                steps.append(entry)
                ledger.update(payload, observation)
                append_trace(args.trace_file, {"event": "environment_step", "task_type": TASK_TYPES[task_type], "game_file": game_file, **entry})
                if dones[0]:
                    return finish("environment_success" if won else "environment_done_without_success")
                pattern_key, pattern_count = trailing_invalid_action_pattern(steps)
                if pattern_count >= INVALID_ACTION_PATTERN_FAILURE_LIMIT:
                    append_trace(args.trace_file, {
                        "event": "invalid_action_pattern_guard", "task_type": TASK_TYPES[task_type],
                        "game_file": game_file, "worker": active_worker, "mission": dispatch["mission"],
                        "pattern_key": pattern_key, "count": pattern_count, "outcome": "fail",
                    })
                    return finish("repeated_invalid_action_pattern_failure")
                if pattern_count >= INVALID_ACTION_PATTERN_RECOVERY_LIMIT:
                    recovery = (
                        f"{pattern_count} consecutive no-effect actions targeted {pattern_key}. "
                        "Do not dispatch another go-to/put variant for that target; choose a different "
                        "target or prerequisite action grounded in the observation."
                    )
                    append_trace(args.trace_file, {
                        "event": "invalid_action_pattern_guard", "task_type": TASK_TYPES[task_type],
                        "game_file": game_file, "worker": active_worker, "mission": dispatch["mission"],
                        "pattern_key": pattern_key, "count": pattern_count, "outcome": "recover",
                    })
                    control = {
                        "trigger": "invalid action pattern requires strategy change",
                        "worker": active_worker, "mission": dispatch["mission"], "feedback": recovery,
                    }
                    break
            except Exception as exc:
                raise_if_api_error(exc)
                return finish("environment_error", repr(exc))

    return finish("action_budget_exhausted")


def episode_result(task_type: int, game_file: str, initial_observation: str, success: bool, steps: list[dict[str, Any]], supervisor_calls: list[dict[str, Any]], action_count: int, termination_reason: str, error: str | None = None, skill_injections: dict[str, Any] | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "task_type_id": task_type, "task_type": TASK_TYPES[task_type], "game_file": game_file,
        "initial_observation": initial_observation, "success": success, "steps": steps,
        "final_reward": float(steps[-1].get("reward", 0.0)) if steps else 0.0,
        "supervisor_calls": supervisor_calls, "environment_action_count": action_count,
        "termination_reason": termination_reason,
        "skill_injections": skill_injections or {},
    }
    if error is not None:
        result["error"] = error
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Client C: dynamic Supervisor with Search and Operation Workers")
    parser.add_argument("--api-key-env", default="DASHSCOPE_API_KEY")
    parser.add_argument("--base-url", default="https://dashscope.aliyuncs.com/compatible-mode/v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--data-dir", default="/mnt/c/Users/26624/Documents/Codex/2026-09-07/xia/alfworld-data")
    parser.add_argument("--split", choices=("train", "eval_in_distribution", "eval_out_of_distribution"), default="eval_out_of_distribution", help="ALFWorld dataset split; does not change the client policy.")
    parser.add_argument("--games-per-type", type=int, default=5)
    parser.add_argument("--task-types", type=int, nargs="+", choices=range(1, 7), default=list(range(1, 7)))
    parser.add_argument("--max-steps", type=int, default=50, help="Whole-episode environment-action budget")
    parser.add_argument("--history-window-turns", type=int, default=10)
    parser.add_argument("--max-completion-tokens", type=int, default=256)
    parser.add_argument("--supervisor-max-completion-tokens", type=int, default=192)
    parser.add_argument("--max-handoffs-without-action", type=int, default=3, help="Protocol safety guard; only applies to repeated status-only loops.")
    parser.add_argument("--request-timeout", type=float, default=60)
    parser.add_argument("--transport-retries", type=int, default=3)
    parser.add_argument("--send-disable-thinking", action="store_true")
    parser.add_argument("--generation-seed", type=int, default=1234, help="Fixed sampling seed sent to every model call; use the same value for repeatable runs.")
    parser.add_argument("--operation-card-mode", choices=("full", "weak", "invalid-only"), default="full")
    add_skill_loader_arguments(parser)
    parser.add_argument("--output", default="results/client_c.json")
    parser.add_argument("--trace-file", default=None)
    parser.add_argument("--exclude-result", action="append", default=[])
    parser.add_argument("--only-game-file", action="append", default=[])
    parser.add_argument("--reference-result", action="append", default=[])
    parser.add_argument("--reference-start-index", type=int, default=0)
    args = parser.parse_args()
    args.skill_loader = loader_from_args(args, "C")
    if args.history_window_turns < 1 or args.max_handoffs_without_action < 1 or args.reference_start_index < 0:
        raise SystemExit("History window, handoff guard, and reference start index must be positive/non-negative as appropriate.")
    if args.reference_result and args.only_game_file:
        raise SystemExit("Use either --reference-result or --only-game-file, not both.")
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f"Set {args.api_key_env} before running; do not put the key in this command.")
    split_directory = {"train": "train", "eval_in_distribution": "valid_seen", "eval_out_of_distribution": "valid_unseen"}[args.split]
    if not (Path(args.data_dir) / "json_2.1.1" / split_directory).is_dir():
        raise SystemExit(f"ALFWorld Text data was not found at {args.data_dir}")
    operation_cards = {"full": OPERATION_CARD, "weak": OPERATION_CARD_WEAK,
                       "invalid-only": OPERATION_CARD_INVALID_ONLY}
    operation_card = operation_cards[args.operation_card_mode]
    os.environ["ALFWORLD_DATA"] = args.data_dir
    client = OpenAI(api_key=api_key, base_url=args.base_url, timeout=args.request_timeout, max_retries=0)
    output: dict[str, Any] = {
        "protocol": "Client C: non-acting dynamic Supervisor -> Search/Operation Workers. Supervisor is called only initially and after Worker HANDOFF/BLOCKED; Workers execute all environment actions.",
        "reproduction_assumptions": {
            "horizon": args.max_steps, "history_window_turns": args.history_window_turns,
            "temperature": 0, "generation_seed": args.generation_seed, "environment": f"official ALFWorld Text {args.split}",
            "supervisor_can_act": False, "workers_can_act": True,
            "operation_card_mode": args.operation_card_mode, "invalid_action_reminder": True,
            "supervisor_trigger": "initial dispatch or Worker HANDOFF/BLOCKED only",
            "invalid_action_pattern_guard": {
                "grouping": "same semantic destination across go-to/put/legacy-move",
                "recovery_after": INVALID_ACTION_PATTERN_RECOVERY_LIMIT,
                "failure_after": INVALID_ACTION_PATTERN_FAILURE_LIMIT,
            },
            "skill_loader": args.skill_loader.descriptor(),
        },
        "started_at": datetime.now(timezone.utc).isoformat(), "model": args.model, "episodes": [],
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    excluded = game_paths_from_results(args.exclude_result)
    requested = {canonical_game_path(path) for path in args.only_game_file}
    reference = reference_games_by_type(args.reference_result, args.task_types, args.games_per_type, args.reference_start_index) if args.reference_result else {}
    if reference:
        output["sampling_reference"] = {"result_files": args.reference_result, "per_task_start_index": args.reference_start_index, "selected_game_files_by_task_type": {TASK_TYPES[key]: value for key, value in reference.items()}}
    if requested & excluded:
        raise SystemExit("A requested --only-game-file is also present in --exclude-result.")
    for task_type in args.task_types:
        pool_size = 0 if (excluded or requested or reference) else args.games_per_type
        direct_train_selection = args.split == "train" and not (excluded or requested or reference)
        if direct_train_selection:
            candidates = select_train_game_files(args.data_dir, task_type, args.games_per_type)
            wrapper = preselected_alfred_tw_env(make_config(args.data_dir, task_type, args.games_per_type, args.max_steps), args.split, candidates)
        else:
            wrapper = AlfredTWEnv(make_config(args.data_dir, task_type, pool_size, args.max_steps), train_eval=args.split)
        if reference:
            available = {canonical_game_path(game): game for game in wrapper.game_files}
            missing = [path for path in reference[task_type] if canonical_game_path(path) not in available]
            if missing:
                raise SystemExit(f"Reference game is not available in {TASK_TYPES[task_type]} valid-unseen pool: {missing[0]}")
            candidates = [available[canonical_game_path(path)] for path in reference[task_type]]
        elif requested:
            candidates = [game for game in wrapper.game_files if canonical_game_path(game) in requested]
        elif not direct_train_selection:
            candidates = [game for game in wrapper.game_files if canonical_game_path(game) not in excluded]
        if args.split == "train" and not reference:
            candidates = sorted(candidates, key=canonical_game_path)
        games_to_run = len(candidates) if requested else args.games_per_type
        if len(candidates) < games_to_run:
            raise SystemExit(f"Only {len(candidates)} eligible {TASK_TYPES[task_type]} games remain, but {games_to_run} were requested.")
        wrapper.game_files = candidates[:games_to_run]
        wrapper.num_games = len(wrapper.game_files)
        environment = wrapper.init_env(batch_size=1)
        try:
            for _ in range(games_to_run):
                episode = run_episode(environment, client, args, task_type, operation_card)
                output["episodes"].append(episode)
                output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"{episode['task_type']}: {'SUCCESS' if episode['success'] else 'FAIL'} ({episode['environment_action_count']} environment actions, {len(episode['supervisor_calls'])} Supervisor calls)", flush=True)
        finally:
            environment.close()
    output["finished_at"] = datetime.now(timezone.utc).isoformat()
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    successes = sum(item["success"] for item in output["episodes"])
    print(f"Completed {len(output['episodes'])} episodes: {successes} successes. Results: {args.output}")


if __name__ == "__main__":
    main()
