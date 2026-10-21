"""Client B: single Executor with periodic Critic audit for ALFWorld Text.

This runner deliberately has no Planner and no Controller.  One Executor sees
the whole task throughout the episode and is the only component allowed to
interact with ALFWorld.  After every fixed number of *environment* actions, a
non-acting Critic reviews the last ten action/observation turns plus the same
deterministic event ledger used by the Executor.  Its short advice is injected
as advisory context for the Executor's next turn.
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


EXECUTOR_SYSTEM_PROMPT = """You are the only Executor controlling a text household environment.
Complete the entire task from the initial state to the environment success
condition. You alone can act in the environment.

For a normal turn, return exactly two lines and nothing else:
Thought: one short sentence about the next action.
Action: one environment command.

After sufficiently attempting the whole task with valid environment
interactions, if you believe it cannot be completed, you may instead return
exactly:
Thought: brief concrete evidence from your valid attempts.
Status: FAILED

You may also return Status: FAILED when your current strategy has repeatedly
been ineffective and there is no new direction grounded in the observations.

Do not return FAILED after one invalid action, one unsuccessful search, or one
location without the target. Never include an Action line and a Status line in
the same response. Do not output Status: COMPLETED; only the environment's
success signal completes the task.

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

""" + OPERATION_CARD + """
A Critic Note, if supplied, is advisory rather than a command or environmental
fact. Check it against the latest observation. Do not blindly follow it when
it conflicts with that observation.
"""


CRITIC_SYSTEM_PROMPT = """You are a non-acting Critic auditing an Executor in a text household environment.
You cannot operate the environment. You cannot output an Action or Status,
rewrite a plan, split the task into subtasks, or declare task success/failure.

""" + OPERATION_CARD + """

Review the most recent already-executed action against its corresponding
environment observation. The earlier turns provide context only: do not call
the most recent action invalid merely because an older action failed. Then give
one short directional suggestion. Use only supplied evidence; never assume
unobserved object locations or contents. 'Nothing happens.' means the
preceding action was invalid and did not change the environment. Do not advise
abandoning the task after a single invalid action. Do not include a concrete
environment command or a multi-step plan.

Return exactly two short natural-language sentences, one per line, with no
labels, headings, categories, Action, or Status:
1. State whether the latest action was effective or ineffective, and why, using
   its observation as evidence.
2. Give one short directional suggestion for the Executor.
"""


FAILED_STATUS_RE = re.compile(
    r"^\s*Thought\s*:\s*.+?\s*\n\s*Status\s*:\s*FAILED\s*$",
    re.IGNORECASE | re.DOTALL,
)
STATUS_RE = re.compile(r"(?:^|\n)\s*Status\s*:\s*FAILED\s*$", re.IGNORECASE | re.MULTILINE)


def recent_trace_block(steps: list[dict[str, Any]], limit: int) -> str:
    """Format completed environment turns only; the final item is current obs."""
    rows: list[str] = []
    for item in steps[-limit:]:
        if "action" not in item or "observation" not in item:
            continue
        rows.extend([
            f"Turn {item['step']} Thought/Action:",
            item.get("model_output", ""),
            f"Turn {item['step']} environment observation:",
            item["observation"],
        ])
    return "\n".join(rows) if rows else "No completed environment actions yet."


def executor_messages(
    initial_observation: str,
    ledger: StateLedger,
    steps: list[dict[str, Any]],
    latest_critic_note: str | None,
    history_turns: int,
    skill_suffix: str = "",
) -> list[dict[str, str]]:
    sections = [
        "INITIAL ENVIRONMENT AND ENTIRE TASK (verbatim; fixed throughout this episode):\n" + initial_observation,
    ]
    # Match Client A's context policy: the deterministic ledger supplements
    # rather than accompanies the raw window, starting only when the window is
    # full. Before that the original interaction trace is sufficient.
    if len(steps) >= history_turns:
        sections.append(ledger.event_ledger())
    sections.extend([
        f"RECENT {history_turns} COMPLETE INTERACTION TURNS (older history is represented only by the ledger once this window is full):\n" + recent_trace_block(steps, history_turns),
        "LATEST CRITIC NOTE (advisory only):\n" + (latest_critic_note or "None yet."),
        # Must be last: the acting model should always attend to the actual
        # current environment state over the ledger or Critic's inference.
        "CURRENT LATEST ENVIRONMENT OBSERVATION (verbatim; act on this now):\n" + ledger.last_observation,
    ])
    content = "\n\n".join(sections)
    system_prompt = EXECUTOR_SYSTEM_PROMPT.rstrip()
    if skill_suffix:
        system_prompt += "\n\n" + skill_suffix
    return [{"role": "system", "content": system_prompt}, {"role": "user", "content": content}]


def critic_messages(initial_observation: str, ledger: StateLedger, steps: list[dict[str, Any]], history_turns: int, skill_suffix: str = "") -> list[dict[str, str]]:
    # Unlike an earlier draft, this does not separately send a five-turn block:
    # it is contained in the last-ten-turn trace and would duplicate tokens.
    sections = [
        "INITIAL ENVIRONMENT AND ENTIRE TASK (verbatim):\n" + initial_observation,
    ]
    if len(steps) >= history_turns:
        sections.append(ledger.event_ledger())
    sections.append(
        f"RECENT {history_turns} COMPLETE INTERACTION TURNS (the final observation is current):\n" + recent_trace_block(steps, history_turns),
    )
    content = "\n\n".join(sections)
    system_prompt = CRITIC_SYSTEM_PROMPT.rstrip()
    if skill_suffix:
        system_prompt += "\n\n" + skill_suffix
    return [{"role": "system", "content": system_prompt}, {"role": "user", "content": content}]


def parse_critic(text: str) -> tuple[str | None, dict[str, str] | None]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) != 2:
        return None, None
    if any(re.match(r"(?:audit|evidence|guidance|review|advice|action|status)\s*:", line, re.IGNORECASE) for line in lines):
        return None, None
    # The two free-form sentences remain separately auditable, while avoiding
    # a categorical label that conflates the latest action with old failures.
    canonical = "\n".join(lines)
    return canonical, {"review": lines[0], "guidance": lines[1]}


def reference_games_by_type(result_paths: list[str], task_types: list[int], per_type: int, start_index: int) -> dict[int, list[str]]:
    """Select exact games in the recorded episode order of a prior result."""
    selected: dict[int, list[str]] = {task_type: [] for task_type in task_types}
    seen: dict[int, set[str]] = {task_type: set() for task_type in task_types}
    for result_path in result_paths:
        path = Path(result_path)
        try:
            episodes = json.loads(path.read_text(encoding="utf-8"))["episodes"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise SystemExit(f"Could not read reference result file {path}: {exc}") from exc
        for episode in episodes:
            task_type = episode.get("task_type_id")
            game_file = episode.get("game_file")
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
            raise SystemExit(
                f"Reference results contain only {len(paths)} distinct {TASK_TYPES[task_type]} games; "
                f"cannot select {per_type} starting at index {start_index}."
            )
        cohort[task_type] = chosen
    return cohort


def run_episode(env: Any, client: OpenAI, args: argparse.Namespace, task_type: int) -> dict[str, Any]:
    observation, info = env.reset()
    initial_observation = observation[0]
    game_file = info["extra.gamefile"][0]
    ledger = StateLedger(initial_observation)
    steps: list[dict[str, Any]] = []
    critic_calls: list[dict[str, Any]] = []
    latest_critic_note: str | None = None
    forced_termination_reason: str | None = None
    won = False
    executor_injection = args.skill_loader.render("Executor", task_type)
    critic_injection = args.skill_loader.render("Critic", task_type)
    skill_injections = {
        "Executor": executor_injection.audit,
        "Critic": critic_injection.audit,
    }
    append_trace(args.trace_file, {
        "event": "reset", "client": "B", "task_type": TASK_TYPES[task_type],
        "game_file": game_file, "initial_observation": initial_observation,
        "skill_injections": skill_injections,
    })

    for step_index in range(1, args.max_steps + 1):
        started = time.monotonic()
        request_messages = executor_messages(
            initial_observation, ledger, steps, latest_critic_note,
            args.history_window_turns, executor_injection.text,
        )
        try:
            print(f"Calling Executor {args.model}: {TASK_TYPES[task_type]} step {step_index}/{args.max_steps}", flush=True)
            model_text, usage = call_model(
                client, args.model, request_messages, args.send_disable_thinking,
                args.max_completion_tokens, args.transport_retries, args.generation_seed,
            )
            if FAILED_STATUS_RE.fullmatch(model_text.strip()):
                entry = {
                    "step": step_index, "kind": "executor_self_report_failure",
                    "model_output": model_text, "usage": usage,
                    "latency_s": round(time.monotonic() - started, 3),
                    "executor_context": request_messages[-1]["content"],
                }
                steps.append(entry)
                append_trace(args.trace_file, {"event": "executor_self_report_failure", "task_type": TASK_TYPES[task_type], "game_file": game_file, **entry})
                return {
                    "task_type_id": task_type, "task_type": TASK_TYPES[task_type], "game_file": game_file,
                    "initial_observation": initial_observation, "success": False, "steps": steps,
                    "critic_calls": critic_calls, "termination_reason": "executor_self_report_failure",
                    "skill_injections": skill_injections,
                }
            raw_action = extract_action(model_text)
            if STATUS_RE.search(model_text):
                # A mixed Action + Status answer is not allowed to change the
                # environment; preserve it as an auditable format failure.
                raw_action = None
            if not raw_action:
                entry = {
                    "step": step_index, "model_output": model_text, "parse_error": True,
                    "usage": usage, "executor_context": request_messages[-1]["content"],
                }
                steps.append(entry)
                append_trace(args.trace_file, {"event": "executor_parse_error", "task_type": TASK_TYPES[task_type], "game_file": game_file, **entry})
                print(f"Client B Executor parse failure in {TASK_TYPES[task_type]}: {model_text!r}", flush=True)
                break

            action = " ".join(raw_action.split())
            next_obs, scores, dones, infos = env.step([action])
            observation = next_obs[0]
            won = bool(dones[0] and infos["won"][0])
            entry = {
                "step": step_index, "raw_action": raw_action, "action": action,
                "observation": observation, "reward": float(scores[0]), "model_output": model_text, "usage": usage,
                "latency_s": round(time.monotonic() - started, 3),
                "executor_context": request_messages[-1]["content"],
            }
            steps.append(entry)
            ledger.update(action, observation)
            append_trace(args.trace_file, {"event": "environment_step", "task_type": TASK_TYPES[task_type], "game_file": game_file, **entry})
            if dones[0]:
                break
            pattern_key, pattern_count = trailing_invalid_action_pattern(steps)
            if pattern_count >= INVALID_ACTION_PATTERN_FAILURE_LIMIT:
                forced_termination_reason = "repeated_invalid_action_pattern_failure"
                append_trace(args.trace_file, {
                    "event": "invalid_action_pattern_guard", "task_type": TASK_TYPES[task_type],
                    "game_file": game_file, "pattern_key": pattern_key,
                    "count": pattern_count, "outcome": "fail",
                })
                break
            if pattern_count >= INVALID_ACTION_PATTERN_RECOVERY_LIMIT:
                latest_critic_note = (
                    f"Recovery required: {pattern_count} consecutive no-effect actions targeted "
                    f"{pattern_key}. Do not issue another go-to/put variant for that same target; "
                    "choose a genuinely different target or prerequisite action grounded in the observation."
                )
                append_trace(args.trace_file, {
                    "event": "invalid_action_pattern_guard", "task_type": TASK_TYPES[task_type],
                    "game_file": game_file, "pattern_key": pattern_key,
                    "count": pattern_count, "outcome": "recover",
                })
                continue

            # A Critic audit is useful only if the Executor still has an action
            # available afterwards. Environment actions (including invalid ones)
            # count; parser failures do not reach this point and do not count.
            if step_index % args.critic_interval == 0 and step_index < args.max_steps:
                critic_started = time.monotonic()
                critic_request = critic_messages(
                    initial_observation, ledger, steps, args.history_window_turns,
                    critic_injection.text,
                )
                print(f"Calling Critic {args.model}: after environment step {step_index}", flush=True)
                try:
                    critic_text, critic_usage = call_model(
                        client, args.model, critic_request, args.send_disable_thinking,
                        args.critic_max_completion_tokens, args.transport_retries, args.generation_seed,
                    )
                    note, parsed = parse_critic(critic_text)
                    critic_record: dict[str, Any] = {
                        "after_step": step_index, "model_output": critic_text,
                        "usage": critic_usage, "latency_s": round(time.monotonic() - critic_started, 3),
                        "critic_context": critic_request[-1]["content"], "parse_error": note is None,
                    }
                    if parsed:
                        critic_record.update(parsed)
                        critic_record["note"] = note
                        latest_critic_note = note
                    critic_calls.append(critic_record)
                    append_trace(args.trace_file, {"event": "critic_audit", "task_type": TASK_TYPES[task_type], "game_file": game_file, **critic_record})
                    if note is None:
                        print(f"Client B Critic format failure after step {step_index}; note not injected.", flush=True)
                except Exception as exc:
                    raise_if_api_error(exc)
                    critic_record = {"after_step": step_index, "error": repr(exc), "latency_s": round(time.monotonic() - critic_started, 3)}
                    critic_calls.append(critic_record)
                    append_trace(args.trace_file, {"event": "critic_error", "task_type": TASK_TYPES[task_type], "game_file": game_file, **critic_record})
                    print(f"Client B Critic error after step {step_index}: {exc!r}; Executor continues.", flush=True)
        except Exception as exc:
            raise_if_api_error(exc)
            entry = {"step": step_index, "error": repr(exc), "latency_s": round(time.monotonic() - started, 3)}
            steps.append(entry)
            append_trace(args.trace_file, {"event": "executor_error", "task_type": TASK_TYPES[task_type], "game_file": game_file, **entry})
            print(f"Client B Executor/environment error in {TASK_TYPES[task_type]}: {exc!r}", flush=True)
            break

    return {
        "task_type_id": task_type, "task_type": TASK_TYPES[task_type], "game_file": game_file,
        "initial_observation": initial_observation, "success": won, "steps": steps,
        "final_reward": float(steps[-1].get("reward", 0.0)) if steps else 0.0,
        "critic_calls": critic_calls,
        "skill_injections": skill_injections,
        "termination_reason": "environment_success" if won else forced_termination_reason or ("action_budget_exhausted" if len(steps) >= args.max_steps else "executor_or_environment_error"),
    }


def main() -> None:
    global EXECUTOR_SYSTEM_PROMPT, CRITIC_SYSTEM_PROMPT
    parser = argparse.ArgumentParser(description="Client B: one Executor with periodic non-acting Critic audits")
    parser.add_argument("--api-key-env", default="DASHSCOPE_API_KEY")
    parser.add_argument("--base-url", default="https://dashscope.aliyuncs.com/compatible-mode/v1")
    parser.add_argument("--model", required=True, help="OpenAI-compatible model ID used by both Executor and Critic")
    parser.add_argument("--data-dir", default="/mnt/c/Users/26624/Documents/Codex/2026-09-07/xia/alfworld-data")
    parser.add_argument("--split", choices=("train", "eval_in_distribution", "eval_out_of_distribution"), default="eval_out_of_distribution", help="ALFWorld dataset split; does not change the client policy.")
    parser.add_argument("--games-per-type", type=int, default=5)
    parser.add_argument("--task-types", type=int, nargs="+", choices=range(1, 7), default=list(range(1, 7)))
    parser.add_argument("--max-steps", type=int, default=50, help="Whole-episode environment-action budget")
    parser.add_argument("--critic-interval", type=int, default=5, help="Audit after this many environment actions")
    parser.add_argument("--history-window-turns", type=int, default=10, help="Completed Action/observation turns sent to both agents")
    parser.add_argument("--max-completion-tokens", type=int, default=256, help="Executor completion limit")
    parser.add_argument("--critic-max-completion-tokens", type=int, default=128, help="Critic completion limit")
    parser.add_argument("--request-timeout", type=float, default=60)
    parser.add_argument("--transport-retries", type=int, default=3)
    parser.add_argument("--send-disable-thinking", action="store_true")
    parser.add_argument("--generation-seed", type=int, default=1234, help="Fixed sampling seed sent to every model call; use the same value for repeatable runs.")
    parser.add_argument("--operation-card-mode", choices=("full", "weak", "invalid-only"), default="full", help="Use the full, weaker, or invalid-action-only operation card.")
    add_skill_loader_arguments(parser)
    parser.add_argument("--output", default="results/client_b.json")
    parser.add_argument("--trace-file", default=None)
    parser.add_argument("--exclude-result", action="append", default=[])
    parser.add_argument("--only-game-file", action="append", default=[])
    parser.add_argument("--reference-result", action="append", default=[], help="Result JSON whose recorded game_file order defines this evaluation cohort. May be repeated.")
    parser.add_argument("--reference-start-index", type=int, default=0, help="Zero-based per-task offset in the reference cohort.")
    args = parser.parse_args()
    args.skill_loader = loader_from_args(args, "B")
    if args.operation_card_mode != "full":
        replacement_card = (OPERATION_CARD_WEAK if args.operation_card_mode == "weak"
                            else OPERATION_CARD_INVALID_ONLY)
        EXECUTOR_SYSTEM_PROMPT = EXECUTOR_SYSTEM_PROMPT.replace(OPERATION_CARD, replacement_card)
        CRITIC_SYSTEM_PROMPT = CRITIC_SYSTEM_PROMPT.replace(OPERATION_CARD, replacement_card)
    if args.critic_interval < 1:
        raise SystemExit("--critic-interval must be at least 1.")
    if args.history_window_turns < 1:
        raise SystemExit("--history-window-turns must be at least 1.")
    if args.reference_start_index < 0:
        raise SystemExit("--reference-start-index must not be negative.")
    if args.reference_result and args.only_game_file:
        raise SystemExit("Use either --reference-result or --only-game-file, not both.")
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f"Set {args.api_key_env} before running; do not put the key in this command.")
    split_directory = {"train": "train", "eval_in_distribution": "valid_seen", "eval_out_of_distribution": "valid_unseen"}[args.split]
    if not (Path(args.data_dir) / "json_2.1.1" / split_directory).is_dir():
        raise SystemExit(f"ALFWorld Text data was not found at {args.data_dir}")
    os.environ["ALFWORLD_DATA"] = args.data_dir
    client = OpenAI(api_key=api_key, base_url=args.base_url, timeout=args.request_timeout, max_retries=0)
    output: dict[str, Any] = {
        "protocol": "Client B: one whole-task Executor + non-acting periodic Critic; operation card; native invalid-action feedback; recent ten-turn raw window plus deterministic ledger; no Planner, Controller, or action list.",
        "reproduction_assumptions": {
            "horizon": args.max_steps, "critic_interval_environment_actions": args.critic_interval,
            "history_window_turns": args.history_window_turns, "temperature": 0, "generation_seed": args.generation_seed,
            "environment": f"official ALFWorld Text {args.split}", "critic_can_act": False,
            "operation_card": True, "operation_card_mode": args.operation_card_mode, "invalid_action_reminder": True,
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
    excluded_game_files = game_paths_from_results(args.exclude_result)
    requested_game_files = {canonical_game_path(path) for path in args.only_game_file}
    reference_cohort = (
        reference_games_by_type(args.reference_result, args.task_types, args.games_per_type, args.reference_start_index)
        if args.reference_result else {}
    )
    if reference_cohort:
        output["sampling_reference"] = {
            "result_files": args.reference_result,
            "per_task_start_index": args.reference_start_index,
            "selected_game_files_by_task_type": {
                TASK_TYPES[task_type]: paths for task_type, paths in reference_cohort.items()
            },
        }
    if requested_game_files & excluded_game_files:
        raise SystemExit("A requested --only-game-file is also present in --exclude-result.")
    for task_type in args.task_types:
        pool_size = 0 if (excluded_game_files or requested_game_files or reference_cohort) else args.games_per_type
        direct_train_selection = args.split == "train" and not (excluded_game_files or requested_game_files or reference_cohort)
        if direct_train_selection:
            candidates = select_train_game_files(args.data_dir, task_type, args.games_per_type)
            environment_wrapper = preselected_alfred_tw_env(make_config(args.data_dir, task_type, args.games_per_type, args.max_steps), args.split, candidates)
        else:
            environment_wrapper = AlfredTWEnv(make_config(args.data_dir, task_type, pool_size, args.max_steps), train_eval=args.split)
        if reference_cohort:
            available = {canonical_game_path(game): game for game in environment_wrapper.game_files}
            missing = [path for path in reference_cohort[task_type] if canonical_game_path(path) not in available]
            if missing:
                raise SystemExit(f"Reference game is not available in {TASK_TYPES[task_type]} valid-unseen pool: {missing[0]}")
            # Preserve the exact ordering recorded by Client A.
            candidates = [available[canonical_game_path(path)] for path in reference_cohort[task_type]]
        elif requested_game_files:
            candidates = [game for game in environment_wrapper.game_files if canonical_game_path(game) in requested_game_files]
        elif not direct_train_selection:
            candidates = [game for game in environment_wrapper.game_files if canonical_game_path(game) not in excluded_game_files]
        if args.split == "train" and not reference_cohort:
            candidates = sorted(candidates, key=canonical_game_path)
        games_to_run = len(candidates) if requested_game_files else args.games_per_type
        if len(candidates) < games_to_run:
            raise SystemExit(f"Only {len(candidates)} eligible {TASK_TYPES[task_type]} games remain, but {games_to_run} were requested.")
        environment_wrapper.game_files = candidates[:games_to_run]
        environment_wrapper.num_games = len(environment_wrapper.game_files)
        environment = environment_wrapper.init_env(batch_size=1)
        try:
            for _ in range(games_to_run):
                episode = run_episode(environment, client, args, task_type)
                output["episodes"].append(episode)
                output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"{episode['task_type']}: {'SUCCESS' if episode['success'] else 'FAIL'} ({len(episode['steps'])} Executor calls, {len(episode['critic_calls'])} Critic calls)", flush=True)
        finally:
            environment.close()
    output["finished_at"] = datetime.now(timezone.utc).isoformat()
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    successes = sum(item["success"] for item in output["episodes"])
    print(f"Completed {len(output['episodes'])} episodes: {successes} successes. Results: {args.output}")


if __name__ == "__main__":
    main()
