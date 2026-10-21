"""Client A: static Plan-and-Execute for ALFWorld Text.

This is intentionally separate from ``alfworld_p0.py``.  It implements the
Client A protocol agreed for the project:

* one Planner call at episode start, producing a fixed AND/OR plan;
* a fresh Executor conversation for every planned sub-task;
* no executor sees another sub-task's trajectory;
* the Controller passes a small factual handoff (last successful action,
  current location, and held object) across successful sub-tasks, while never
  passing a prior trajectory or failure text across OR branches;
* every executor keeps its own last-ten-turn window and only then adds its own
  deterministic event ledger; and
* there is one 50-action episode budget, with no per-sub-task action cap.

It uses LangGraph for the Planner -> prepare-subtask -> Executor -> Controller
state machine.  Skill injection is disabled by default; Stage3 experiments may
explicitly attach a validated, role-isolated SkillBank.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypedDict

try:
    from langgraph.graph import END, StateGraph
except ImportError as exc:  # Give a useful message instead of a cryptic import failure.
    raise SystemExit(
        "Client A requires langgraph in .alfworld-venv. "
        "Install it in that existing virtual environment, then rerun."
    ) from exc

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


# These examples teach only static decomposition syntax.  They deliberately do
# not state ALFWorld mechanisms such as the prerequisites for heat/cool/clean.
PLANNER_SYSTEM_PROMPT = """You are a static planner for a household text environment.
At the beginning of an episode, decompose the whole task once into a concise,
complete plan. You will never receive execution feedback and must not revise it.

Output exactly this format and nothing else:
Execution Order: <an expression using S1, S2, ... AND, OR, and parentheses>
S1: <an English subtask>
S2: <an English subtask>

Rules:
- You MUST define no more than six subtasks in total: only S1 through S6 are
  allowed. This is a hard output constraint, not a preference.
- Before responding, count the S-numbered lines. If there are more than six,
  merge them into broader high-level subtasks before outputting the plan.
- AND means left-to-right sequential execution. OR means left-to-right
  alternative search branches.
- When an object's location is unknown, normally use one broad subtask such as
  "Find and take a mug". Do not enumerate every possible receptacle as OR
  branches; use OR only when the whole plan, including its final goal-achieving
  step, still has at most six subtasks.
- A subtask must be a meaningful local objective, not one low-level command.
- The plan must include the action that achieves the whole task's final goal;
  a plan that ends with finding or taking an object is incomplete.
- Do not invent concrete numbered objects or locations absent from the initial
  environment description.
- A robot can carry only one object. For a two-object task, plan to place the
  first object before fetching the second.

Example 1
Task: Put a mug on desk 1.
Execution Order: (S1 AND S2)
S1: Find and take a mug.
S2: Put the mug on desk 1.

Example 2
Task: Put a clean mug on desk 1.
Execution Order: (S1 AND S2 AND S3)
S1: Find and take a mug.
S2: Clean the mug.
S3: Put the clean mug on desk 1.

Example 3
Task: Find and take a mug whose location is unknown.
Execution Order: (S1 OR S2 OR S3)
S1: Find and take a mug from a countertop.
S2: Find and take a mug from a cabinet.
S3: Find and take a mug from a drawer.

Example 4
Task: Put two credit cards in drawer 1.
Execution Order: (S1 AND S2 AND S3 AND S4)
S1: Find and take the first credit card.
S2: Put the first credit card in drawer 1.
S3: Find and take the second credit card.
S4: Put the second credit card in drawer 1.
"""


EXECUTOR_SYSTEM_PROMPT = """You are an executor in a household text environment.
The OVERALL TASK is supplied only as context. Solve only the CURRENT SUBTASK
supplied by the controller; do not infer or attempt later planned subtasks.
The CURRENT SUBTASK has completion priority: as soon as its required end state
is satisfied, immediately return Status: COMPLETED. Do not continue acting to
complete the overall task or any later planned subtask after that point.

For every nonterminal turn, return exactly two lines:
Thought: one short sentence about the next action for the current subtask.
Action: one environment command.

When the CURRENT SUBTASK has been completed, return exactly:
Thought: one short completion reason.
Status: COMPLETED

Do not declare FAILED after one invalid action or one unsuccessful search.
Only after sufficiently attempting the CURRENT SUBTASK with valid environment
interactions may you return exactly:
Thought: brief concrete evidence of the valid attempts already made.
Status: FAILED

Never include an Action line and a Status line in the same response. An Action
has not succeeded until the environment returns an observation. Therefore, use
Status: COMPLETED only in a later response after observing that the preceding
single Action completed the CURRENT SUBTASK.

If the environment says 'Nothing happens.', the preceding Action was invalid
and did not change the environment state. Choose a different Action; do not
repeat that failed Action unless the state has changed.

Use names exactly as present in the observation. The accepted command forms are:
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

Do not output a plan, an explanation, or commands outside this grammar."""


# Optional static ICL control.  This is deliberately an environment-operation
# card, not a task solution, search policy, skill memory, or admissible-action
# list.  A-Base never receives it; experiments must opt in with --operation-card.
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

STATUS_RE = re.compile(r"^\s*Status\s*:\s*(COMPLETED|FAILED)\s*$", re.IGNORECASE | re.MULTILINE)
STEP_RE = re.compile(r"^\s*S(\d+)\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
ORDER_RE = re.compile(r"^\s*Execution\s+Order\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)
PLAN_TOKEN_RE = re.compile(r"S\d+|AND|OR|\(|\)", re.IGNORECASE)


class ClientAState(TypedDict, total=False):
    env: Any
    client: OpenAI
    args: argparse.Namespace
    task_type: int
    game_file: str
    initial_observation: str
    current_observation: str
    planner_output: str
    planner_usage: dict[str, int | None]
    planner_attempts: list[dict[str, Any]]
    plan_steps: dict[str, str]
    plan_ast: dict[str, Any]
    frames: list[dict[str, Any]]
    active_subtask_id: str
    active_subtask: str
    current_handoff: dict[str, Any] | None
    controller_ledger: StateLedger
    leaf_history: list[dict[str, str]]
    leaf_ledger: StateLedger
    leaf_steps: list[dict[str, Any]]
    leaf_control_calls: list[dict[str, Any]]
    retry_note: str | None
    leaf_index: int
    pending_status: Literal["COMPLETED", "FAILED"] | None
    pending_reason: str | None
    last_executor_output: str
    last_usage: dict[str, int | None]
    terminal_model_call: dict[str, Any]
    won: bool
    terminal: bool
    terminal_reason: str
    success: bool
    total_actions: int
    environment_steps: list[dict[str, Any]]
    subtask_runs: list[dict[str, Any]]


def parse_plan(text: str) -> tuple[dict[str, str], dict[str, Any]]:
    """Parse the deliberately narrow Execution Order grammar without an LLM repair."""
    order_match = ORDER_RE.search(text)
    steps = {f"S{number}": body.strip() for number, body in STEP_RE.findall(text)}
    if not order_match or not steps:
        raise ValueError("missing Execution Order or S-numbered steps")
    expression = order_match.group(1).strip().upper()
    tokens = PLAN_TOKEN_RE.findall(expression)
    if "".join(tokens) != re.sub(r"\s+", "", expression):
        raise ValueError("Execution Order contains unsupported text")
    if not tokens:
        raise ValueError("empty Execution Order")

    position = 0

    def parse_atom() -> dict[str, Any]:
        nonlocal position
        if position >= len(tokens):
            raise ValueError("unexpected end of Execution Order")
        token = tokens[position].upper()
        if token == "(":
            position += 1
            node = parse_expression()
            if position >= len(tokens) or tokens[position] != ")":
                raise ValueError("unmatched parenthesis")
            position += 1
            return node
        if re.fullmatch(r"S\d+", token):
            position += 1
            if token not in steps:
                raise ValueError(f"{token} is referenced but has no step text")
            return {"type": "leaf", "id": token}
        raise ValueError(f"expected step or '(', got {token}")

    def parse_expression() -> dict[str, Any]:
        nonlocal position
        first = parse_atom()
        children = [first]
        operator: str | None = None
        while position < len(tokens) and tokens[position].upper() in {"AND", "OR"}:
            candidate = tokens[position].upper()
            if operator is None:
                operator = candidate
            elif candidate != operator:
                raise ValueError("mix AND and OR only with explicit parentheses")
            position += 1
            children.append(parse_atom())
        return first if operator is None else {"type": operator.lower(), "children": children}

    tree = parse_expression()
    if position != len(tokens):
        raise ValueError("unparsed tokens in Execution Order")
    if len(steps) > 6:
        raise ValueError("planner produced more than six subtasks")
    return steps, tree


def make_frame(node: dict[str, Any], handoff: dict[str, Any] | None) -> dict[str, Any]:
    if node["type"] == "leaf":
        return {"type": "leaf", "id": node["id"], "handoff": handoff}
    return {"type": node["type"], "children": node["children"], "index": 0, "handoff": handoff}


def descend_to_leaf(frames: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Expand the next pending AST branch until a leaf is ready to execute."""
    while frames:
        top = frames[-1]
        if top["type"] == "leaf":
            return top
        if top["index"] >= len(top["children"]):
            raise RuntimeError("controller reached an exhausted non-leaf frame")
        frames.append(make_frame(top["children"][top["index"]], top["handoff"]))
    return None


def bubble_result(frames: list[dict[str, Any]], succeeded: bool, handoff_out: dict[str, Any] | None) -> tuple[bool | None, dict[str, Any] | None]:
    """Propagate a leaf result through AND/OR frames.

    ``None`` means a sibling remains and should be prepared next.  A Boolean
    means the root plan is now complete/failed.
    """
    if not frames or frames[-1]["type"] != "leaf":
        raise RuntimeError("controller expected a leaf frame")
    frames.pop()
    while frames:
        parent = frames[-1]
        if parent["type"] == "and":
            if not succeeded:
                frames.pop()  # an AND fails immediately
                succeeded = False
                continue
            parent["handoff"] = handoff_out
            parent["index"] += 1
            if parent["index"] < len(parent["children"]):
                return None, None
            # All children of this AND have succeeded.  The composite node is
            # itself a success, so carry its final action to its own parent.
            frames.pop()
            succeeded = True
            handoff_out = parent["handoff"]
            continue
        if parent["type"] == "or":
            if succeeded:
                frames.pop()
                continue  # propagate this successful branch to its parent
            parent["index"] += 1
            if parent["index"] < len(parent["children"]):
                return None, None  # retain the OR's original handoff
            frames.pop()
            succeeded = False
            continue
        raise RuntimeError(f"unknown frame type {parent['type']}")
    return succeeded, handoff_out


def executor_base_message(state: ClientAState) -> str:
    handoff = state.get("current_handoff")
    if handoff:
        held = ", ".join(handoff["holding"]) if handoff["holding"] else "nothing known"
        handoff_text = (
            "Last successful action from the preceding successful subtask:\n"
            f"{handoff['last_action'] or 'None'}\n"
            "Environment observation returned by that action:\n"
            f"{handoff['last_observation'] or 'None'}\n"
            f"Current location: {handoff['location']}\n"
            f"Holding: {held}"
        )
    else:
        handoff_text = "None (there is no preceding successful subtask)."
    task_match = re.search(r"Your task is to:\s*(.+)", state["initial_observation"], re.IGNORECASE)
    overall_task = task_match.group(1).strip() if task_match else "Unknown"
    room_description = re.split(r"\n\s*Your task is to:\s*.+", state["initial_observation"], maxsplit=1, flags=re.IGNORECASE)[0]
    content = (
        f"OVERALL TASK — context only:\n{overall_task}\n\n"
        f"EXECUTE NOW — only this current subtask:\n{state['active_subtask']}\n\n"
        "INITIAL ROOM AND NAVIGABLE LOCATIONS (verbatim):\n"
        f"{room_description}\n\n"
        "CONTROLLER HANDOFF (factual state, not a trajectory):\n"
        f"{handoff_text}"
    )
    if len(state["leaf_history"]) >= 2 * state["args"].history_window_turns:
        content += "\n\n" + state["leaf_ledger"].event_ledger()
    if state.get("retry_note"):
        content += "\n\nCONTROLLER FORMAT REMINDER:\n" + state["retry_note"]
    return content


def planner_node(state: ClientAState) -> dict[str, Any]:
    task_match = re.search(r"Your task is to:\s*(.+)", state["initial_observation"], re.IGNORECASE)
    whole_task = task_match.group(1).strip() if task_match else state["initial_observation"]
    prompt = "INITIAL ENVIRONMENT OBSERVATION:\n" + state["initial_observation"] + "\n\nWHOLE TASK:\n" + whole_task
    planner_prompt, _ = state["args"].skill_loader.augment_system_prompt(
        PLANNER_SYSTEM_PROMPT, "Planner", state["task_type"]
    )
    messages = [{"role": "system", "content": planner_prompt}, {"role": "user", "content": prompt}]
    attempts: list[dict[str, Any]] = []
    last_error: Exception | None = None
    try:
        for repair_index in range(state["args"].planner_format_repairs + 1):
            output, usage = call_model(
                state["client"], state["args"].model, messages,
                state["args"].send_disable_thinking, state["args"].planner_max_completion_tokens,
                state["args"].transport_retries, state["args"].generation_seed,
            )
            record = {"attempt": repair_index + 1, "output": output, "usage": usage}
            try:
                plan_steps, plan_ast = parse_plan(output)
                attempts.append({**record, "valid": True})
                return {
                    "planner_output": output,
                    "planner_usage": usage,
                    "planner_attempts": attempts,
                    "plan_steps": plan_steps,
                    "plan_ast": plan_ast,
                    "frames": [make_frame(plan_ast, None)],
                    "terminal": False,
                }
            except ValueError as exc:
                last_error = exc
                attempts.append({**record, "valid": False, "validation_error": str(exc)})
                if repair_index >= state["args"].planner_format_repairs:
                    break
                messages.extend([
                    {"role": "assistant", "content": output},
                    {"role": "user", "content": (
                        f"Your plan has a structural format error: {exc}. No environment action has been taken. "
                        "Rewrite the complete plan from scratch in the required format. Every S-number in "
                        "Execution Order must have exactly one S#: definition, and there may be at most six steps."
                    )},
                ])
    except Exception as exc:
        raise_if_api_error(exc)
        last_error = exc
    return {
        "planner_output": locals().get("output", ""),
        "planner_usage": locals().get("usage", {}),
        "planner_attempts": attempts,
        "terminal": True,
        "terminal_reason": f"planner_failure: {last_error!r}",
        "success": False,
    }


def prepare_subtask_node(state: ClientAState) -> dict[str, Any]:
    leaf = descend_to_leaf(state["frames"])
    if leaf is None:
        return {"terminal": True, "terminal_reason": "controller_empty_plan", "success": False}
    subtask_number = len(state["subtask_runs"])
    # A ledger is intentionally recreated here: no factual state from an older
    # subtask crosses this boundary.  The first task's initial observation is
    # kept only to initialize its local ledger, never displayed by event_ledger.
    ledger_seed = state["initial_observation"] if subtask_number == 0 else ""
    return {
        "active_subtask_id": leaf["id"],
        "active_subtask": state["plan_steps"][leaf["id"]],
        "current_handoff": leaf["handoff"],
        "leaf_history": [],
        "leaf_ledger": StateLedger(ledger_seed),
        "leaf_steps": [],
        "leaf_control_calls": [],
        "leaf_index": subtask_number,
        "pending_status": None,
        "pending_reason": None,
        "retry_note": None,
        "terminal_model_call": {},
    }


def executor_node(state: ClientAState) -> dict[str, Any]:
    if state["total_actions"] >= state["args"].max_steps:
        # This is the Controller's hard environment-action budget terminal.
        return {"pending_status": "FAILED", "pending_reason": "episode_action_budget_exhausted"}
    if (state["args"].max_control_retries is not None
            and len(state["leaf_control_calls"]) >= state["args"].max_control_retries):
        return {"pending_status": "FAILED", "pending_reason": "controller_protocol_retry_exhausted"}
    executor_system_prompt = EXECUTOR_SYSTEM_PROMPT
    if state["args"].operation_card:
        cards = {"full": OPERATION_CARD, "weak": OPERATION_CARD_WEAK,
                 "invalid-only": OPERATION_CARD_INVALID_ONLY}
        card = cards[state["args"].operation_card_mode]
        executor_system_prompt += "\n\n" + card
    executor_system_prompt, _ = state["args"].skill_loader.augment_system_prompt(
        executor_system_prompt, "Executor", state["task_type"]
    )
    messages = [{"role": "system", "content": executor_system_prompt}, {"role": "user", "content": executor_base_message(state)}]
    messages.extend(state["leaf_history"])
    started = time.monotonic()
    try:
        model_text, usage = call_model(
            state["client"], state["args"].model, messages,
            state["args"].send_disable_thinking, state["args"].executor_max_completion_tokens,
            state["args"].transport_retries, state["args"].generation_seed,
        )
        status_match = STATUS_RE.search(model_text)
        raw_action = extract_action(model_text)
        action_lines = re.findall(r"(?im)^\s*Action\s*:\s*(.+?)\s*$", model_text)
        if len(action_lines) > 1 or (status_match and raw_action):
            violation = "multiple Action lines" if len(action_lines) > 1 else "both an Action line and a Status line"
            rejected_call = {
                "kind": "executor_response_format_rejected",
                "subtask": state["active_subtask_id"],
                "subtask_step": len(state["leaf_steps"]) + 1,
                "global_step_before_call": state["total_actions"],
                "model_output": model_text,
                "usage": usage,
                "latency_s": round(time.monotonic() - started, 3),
                "agent_context": messages[-1]["content"],
            }
            append_trace(state["args"].trace_file, {
                "event": "executor_response_format_rejected", "task_type": TASK_TYPES[state["task_type"]],
                "game_file": state["game_file"], "request_messages": messages, **rejected_call,
            })
            return {
                "leaf_control_calls": state["leaf_control_calls"] + [rejected_call],
                "retry_note": (
                    f"Your previous reply contained {violation}. No proposed action was sent to the "
                    "environment, no state change occurred, and any Status claim is unverified. "
                    "Regenerate either exactly one Thought line and exactly one Action line, or only "
                    "Thought plus Status: COMPLETED if the current subtask was already completed by "
                    "a previously observed environment action."
                ),
            }
        if status_match and not raw_action and status_match.group(1).upper() == "COMPLETED":
            terminal_call = {
                "kind": "executor_status",
                "subtask": state["active_subtask_id"],
                "subtask_step": len(state["leaf_steps"]) + 1,
                "global_step_before_call": state["total_actions"],
                "model_output": model_text,
                "usage": usage,
                "latency_s": round(time.monotonic() - started, 3),
                "agent_context": messages[-1]["content"],
            }
            append_trace(state["args"].trace_file, {
                "event": "executor_status", "task_type": TASK_TYPES[state["task_type"]],
                "game_file": state["game_file"], "request_messages": messages, **terminal_call,
            })
            return {
                "pending_status": "COMPLETED",
                "pending_reason": "executor_self_report",
                "last_executor_output": model_text,
                "last_usage": usage,
                "terminal_model_call": terminal_call,
            }
        if status_match and not raw_action and status_match.group(1).upper() == "FAILED":
            terminal_call = {
                "kind": "executor_failed_status",
                "subtask": state["active_subtask_id"],
                "subtask_step": len(state["leaf_steps"]) + 1,
                "global_step_before_call": state["total_actions"],
                "model_output": model_text,
                "usage": usage,
                "latency_s": round(time.monotonic() - started, 3),
                "agent_context": messages[-1]["content"],
            }
            append_trace(state["args"].trace_file, {
                "event": "executor_failed_status", "task_type": TASK_TYPES[state["task_type"]],
                "game_file": state["game_file"], "request_messages": messages, **terminal_call,
            })
            return {
                "pending_status": "FAILED",
                "pending_reason": "executor_self_report",
                "last_executor_output": model_text,
                "last_usage": usage,
                "terminal_model_call": terminal_call,
            }
        if not raw_action:
            rejected_call = {
                "kind": "executor_format_rejected",
                "subtask": state["active_subtask_id"],
                "subtask_step": len(state["leaf_steps"]) + 1,
                "global_step_before_call": state["total_actions"],
                "model_output": model_text,
                "usage": usage,
                "latency_s": round(time.monotonic() - started, 3),
                "agent_context": messages[-1]["content"],
            }
            append_trace(state["args"].trace_file, {
                "event": "executor_format_rejected", "task_type": TASK_TYPES[state["task_type"]],
                "game_file": state["game_file"], "request_messages": messages, **rejected_call,
            })
            return {
                "leaf_control_calls": state["leaf_control_calls"] + [rejected_call],
                "retry_note": "Your previous reply had no valid Action. Continue the current subtask with exactly Thought and one Action, or Status: COMPLETED only after the subtask is actually complete.",
            }
        action = " ".join(raw_action.split())
        next_obs, scores, dones, infos = state["env"].step([action])
        observation = next_obs[0]
        won = bool(dones[0] and infos["won"][0])
        leaf_history = state["leaf_history"] + [
            {"role": "assistant", "content": model_text},
            {"role": "user", "content": observation},
        ]
        leaf_history = leaf_history[-2 * state["args"].history_window_turns:]
        state["leaf_ledger"].update(action, observation)
        state["controller_ledger"].update(action, observation)
        entry = {
            "global_step": state["total_actions"] + 1,
            "subtask": state["active_subtask_id"],
            "subtask_step": len(state["leaf_steps"]) + 1,
            "raw_action": raw_action,
            "action": action,
            "observation": observation,
            "reward": float(scores[0]),
            "model_output": model_text,
            "usage": usage,
            "latency_s": round(time.monotonic() - started, 3),
            "agent_context": messages[-1]["content"],
        }
        append_trace(state["args"].trace_file, {
            "event": "executor_step", "task_type": TASK_TYPES[state["task_type"]],
            "game_file": state["game_file"], "request_messages": messages, **entry,
        })
        new_environment_steps = state["environment_steps"] + [entry]
        pattern_key, pattern_count = trailing_invalid_action_pattern(new_environment_steps)
        pending_status = "COMPLETED" if won else None
        pending_reason = "environment_won" if won else None
        retry_note = None
        if not won and pattern_count >= INVALID_ACTION_PATTERN_FAILURE_LIMIT:
            pending_status = "FAILED"
            pending_reason = "repeated_invalid_action_pattern_failure"
        elif not won and pattern_count >= INVALID_ACTION_PATTERN_RECOVERY_LIMIT:
            retry_note = (
                f"RECOVERY REQUIRED: {pattern_count} consecutive no-effect actions targeted "
                f"{pattern_key}. Do not issue another go-to/put variant for that same target. "
                "Choose a genuinely different target or prerequisite action grounded in the observation."
            )
        if pattern_count in {INVALID_ACTION_PATTERN_RECOVERY_LIMIT, INVALID_ACTION_PATTERN_FAILURE_LIMIT}:
            append_trace(state["args"].trace_file, {
                "event": "invalid_action_pattern_guard", "task_type": TASK_TYPES[state["task_type"]],
                "game_file": state["game_file"], "pattern_key": pattern_key,
                "count": pattern_count, "outcome": "fail" if pending_status == "FAILED" else "recover",
            })
        return {
            "current_observation": observation,
            "leaf_history": leaf_history,
            "leaf_steps": state["leaf_steps"] + [entry],
            "environment_steps": new_environment_steps,
            "total_actions": state["total_actions"] + 1,
            "won": won,
            "pending_status": pending_status,
            "pending_reason": pending_reason,
            "retry_note": retry_note,
            "leaf_control_calls": state["leaf_control_calls"],
        }
    except Exception as exc:
        raise_if_api_error(exc)
        terminal_call = {
            "kind": "executor_error",
            "subtask": state["active_subtask_id"],
            "subtask_step": len(state["leaf_steps"]) + 1,
            "global_step_before_call": state["total_actions"],
            "error": repr(exc),
            "latency_s": round(time.monotonic() - started, 3),
        }
        append_trace(state["args"].trace_file, {
            "event": "executor_error", "task_type": TASK_TYPES[state["task_type"]],
            "game_file": state["game_file"], **terminal_call,
        })
        return {"pending_status": "FAILED", "pending_reason": f"executor_error: {exc!r}", "terminal_model_call": terminal_call}


def controller_node(state: ClientAState) -> dict[str, Any]:
    status = state.get("pending_status")
    if status not in {"COMPLETED", "FAILED"}:
        raise RuntimeError("controller called before an executor terminal signal")
    incoming_handoff = state.get("current_handoff")
    leaf_last_action = (
        state["leaf_steps"][-1]["action"] if state["leaf_steps"]
        else (incoming_handoff["last_action"] if incoming_handoff else None)
    )
    controller_ledger = state["controller_ledger"]
    last_observation = (
        state["leaf_steps"][-1]["observation"] if state["leaf_steps"]
        else (incoming_handoff["last_observation"] if incoming_handoff else None)
    )
    handoff_out = {
        "last_action": leaf_last_action,
        "last_observation": last_observation,
        "location": controller_ledger.location,
        "holding": sorted(controller_ledger.holding),
    } if status == "COMPLETED" else None
    subtask_record = {
        "id": state["active_subtask_id"],
        "task": state["active_subtask"],
        "handoff_in": state.get("current_handoff"),
        "status": status,
        "reason": state.get("pending_reason"),
        "last_successful_action_out": leaf_last_action if status == "COMPLETED" else None,
        "controller_state_out": handoff_out,
        "steps": state["leaf_steps"],
        "control_calls": state["leaf_control_calls"],
        "terminal_model_call": state.get("terminal_model_call"),
    }
    append_trace(state["args"].trace_file, {
        "event": "subtask_terminal", "task_type": TASK_TYPES[state["task_type"]],
        "game_file": state["game_file"], "subtask": subtask_record,
    })
    root_result, _ = bubble_result(state["frames"], status == "COMPLETED", handoff_out)
    updates: dict[str, Any] = {
        "subtask_runs": state["subtask_runs"] + [subtask_record],
        "pending_status": None,
        "pending_reason": None,
        "terminal_model_call": {},
    }
    if state.get("won"):
        updates.update({"terminal": True, "terminal_reason": "environment_won", "success": True})
    elif root_result is not None:
        updates.update({
            "terminal": True,
            "terminal_reason": "plan_completed_without_environment_win" if root_result else "plan_failed",
            "success": False,
        })
    return updates


def route_after_planner(state: ClientAState) -> str:
    return "end" if state.get("terminal") else "prepare"


def route_after_executor(state: ClientAState) -> str:
    return "controller" if state.get("pending_status") else "executor"


def route_after_controller(state: ClientAState) -> str:
    return "end" if state.get("terminal") else "prepare"


def build_client_a_graph() -> Any:
    graph = StateGraph(ClientAState)
    graph.add_node("planner", planner_node)
    graph.add_node("prepare", prepare_subtask_node)
    graph.add_node("executor", executor_node)
    graph.add_node("controller", controller_node)
    graph.set_entry_point("planner")
    graph.add_conditional_edges("planner", route_after_planner, {"prepare": "prepare", "end": END})
    graph.add_edge("prepare", "executor")
    graph.add_conditional_edges("executor", route_after_executor, {"executor": "executor", "controller": "controller"})
    graph.add_conditional_edges("controller", route_after_controller, {"prepare": "prepare", "end": END})
    return graph.compile()


def run_episode(env: Any, client: OpenAI, graph: Any, args: argparse.Namespace, task_type: int) -> dict[str, Any]:
    observation, info = env.reset()
    initial_observation = observation[0]
    game_file = info["extra.gamefile"][0]
    skill_injections = {
        role: args.skill_loader.render(role, task_type).audit
        for role in ("Planner", "Executor")
    }
    append_trace(args.trace_file, {
        "event": "reset", "task_type": TASK_TYPES[task_type], "game_file": game_file,
        "initial_observation": initial_observation, "skill_injections": skill_injections,
    })
    initial_state: ClientAState = {
        "env": env,
        "client": client,
        "args": args,
        "task_type": task_type,
        "game_file": game_file,
        "initial_observation": initial_observation,
        "current_observation": initial_observation,
        "frames": [],
        "leaf_history": [],
        "controller_ledger": StateLedger(initial_observation),
        "leaf_steps": [],
        "environment_steps": [],
        "subtask_runs": [],
        "total_actions": 0,
        "won": False,
        "terminal": False,
        "success": False,
        "terminal_reason": "not_started",
    }
    final_state = graph.invoke(initial_state, {"recursion_limit": args.max_steps * 4 + 32})
    return {
        "task_type_id": task_type,
        "task_type": TASK_TYPES[task_type],
        "game_file": game_file,
        "initial_observation": initial_observation,
        "success": final_state.get("success", False),
        "final_reward": float(final_state.get("environment_steps", [{}])[-1].get("reward", 0.0)) if final_state.get("environment_steps") else 0.0,
        "terminal_reason": final_state.get("terminal_reason"),
        "planner": {"output": final_state.get("planner_output"), "usage": final_state.get("planner_usage"), "attempts": final_state.get("planner_attempts", [])},
        "plan_steps": final_state.get("plan_steps"),
        "plan_ast": final_state.get("plan_ast"),
        "subtasks": final_state.get("subtask_runs", []),
        "steps": final_state.get("environment_steps", []),
        "skill_injections": skill_injections,
    }


def reference_games_by_type(result_paths: list[str], task_types: list[int], per_type: int, start_index: int) -> dict[int, list[str]]:
    """Select exact games in recorded per-type order from earlier result files."""
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Client A: static Plan-and-Execute ALFWorld runner")
    parser.add_argument("--api-key-env", default="DASHSCOPE_API_KEY")
    parser.add_argument("--base-url", default="https://dashscope.aliyuncs.com/compatible-mode/v1")
    parser.add_argument("--model", required=True, help="OpenAI-compatible Qwen model ID")
    parser.add_argument("--data-dir", default="/mnt/c/Users/26624/Documents/Codex/2026-09-07/xia/alfworld-data")
    parser.add_argument("--split", choices=("train", "eval_in_distribution", "eval_out_of_distribution"), default="eval_out_of_distribution", help="ALFWorld dataset split; does not change the client policy.")
    parser.add_argument("--games-per-type", type=int, default=5)
    parser.add_argument("--task-types", type=int, nargs="+", choices=range(1, 7), default=list(range(1, 7)))
    parser.add_argument("--max-steps", type=int, default=50, help="One shared environment-action cap for the whole episode.")
    parser.add_argument("--history-window-turns", type=int, default=10, help="Complete raw turns retained within one subtask.")
    parser.add_argument("--max-control-retries", type=int, default=None, help="Optional maximum format corrections within one subtask. Omit for no format-based early stop.")
    parser.add_argument("--planner-max-completion-tokens", type=int, default=384)
    parser.add_argument("--planner-format-repairs", type=int, default=1, help="Planner rewrite attempts after a parser-detected structural format error.")
    parser.add_argument("--executor-max-completion-tokens", type=int, default=128)
    parser.add_argument("--request-timeout", type=float, default=60)
    parser.add_argument("--transport-retries", type=int, default=3)
    parser.add_argument("--send-disable-thinking", action="store_true")
    parser.add_argument("--generation-seed", type=int, default=1234, help="Fixed sampling seed sent to every model call; use the same value for repeatable runs.")
    parser.add_argument("--operation-card", action="store_true", help="A-OpCard ablation: add static ALFWorld operation prerequisites to each Executor prompt.")
    parser.add_argument("--operation-card-mode", choices=("full", "weak", "invalid-only"), default="full", help="Use the full, weaker, or invalid-action-only operation card. Requires --operation-card.")
    add_skill_loader_arguments(parser)
    parser.add_argument("--output", default="results/alfworld_client_a.json")
    parser.add_argument("--trace-file", default=None)
    parser.add_argument("--exclude-result", action="append", default=[])
    parser.add_argument("--only-game-file", action="append", default=[])
    parser.add_argument("--reference-result", action="append", default=[], help="Result JSON whose recorded game-file order defines this evaluation cohort. May be repeated.")
    parser.add_argument("--reference-start-index", type=int, default=0, help="Zero-based per-task offset in the reference cohort.")
    args = parser.parse_args()
    args.skill_loader = loader_from_args(args, "A")

    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f"Set {args.api_key_env} before running; do not put the key in this command.")
    split_directory = {"train": "train", "eval_in_distribution": "valid_seen", "eval_out_of_distribution": "valid_unseen"}[args.split]
    if not (Path(args.data_dir) / "json_2.1.1" / split_directory).is_dir():
        raise SystemExit(f"ALFWorld Text data was not found at {args.data_dir}")
    os.environ["ALFWORLD_DATA"] = args.data_dir
    client = OpenAI(api_key=api_key, base_url=args.base_url, timeout=args.request_timeout, max_retries=0)
    graph = build_client_a_graph()
    output = {
        "protocol": ("Client A A-OpCard: one static Planner call; fresh subtask-isolated Executors; Controller passes only last successful action, current location, and held object; static operation card added."
                     if args.operation_card else
                     "Client A A-Base: one static Planner call; fresh subtask-isolated Executors; Controller passes only last successful action, current location, and held object; subtask-local 10-turn window plus ledger; no operation-mechanism card."),
        "reproduction_assumptions": {
            "architecture": "ADaPT Plan-and-Execute-inspired, budget-matched adaptation",
            "environment": f"official ALFWorld Text {args.split}", "generation_seed": args.generation_seed,
            "temperature": 0,
            "episode_action_budget": args.max_steps,
            "per_subtask_action_cap": None,
            "executor_history_scope": "current subtask only",
            "controller_handoff": "last successful environment action, current location, and held object only",
            "operation_card": args.operation_card,
            "operation_card_mode": args.operation_card_mode if args.operation_card else "none",
            "invalid_action_pattern_guard": {
                "grouping": "same semantic destination across go-to/put/legacy-move",
                "recovery_after": INVALID_ACTION_PATTERN_RECOVERY_LIMIT,
                "failure_after": INVALID_ACTION_PATTERN_FAILURE_LIMIT,
            },
            "skill_loader": args.skill_loader.descriptor(),
            "paper_status": "adapted to Qwen3, native literal put-in/on syntax, LangGraph, and a 50-step global budget; not an exact paper reproduction",
        },
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "episodes": [],
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    excluded = game_paths_from_results(args.exclude_result)
    requested = {canonical_game_path(path) for path in args.only_game_file}
    if args.reference_result and args.only_game_file:
        raise SystemExit("Use either --reference-result or --only-game-file, not both.")
    if args.reference_start_index < 0:
        raise SystemExit("--reference-start-index must not be negative.")
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
    if requested & excluded:
        raise SystemExit("A requested --only-game-file is also present in --exclude-result.")

    for task_type in args.task_types:
        pool_size = 0 if (excluded or requested or reference_cohort) else args.games_per_type
        direct_train_selection = args.split == "train" and not (excluded or requested or reference_cohort)
        if direct_train_selection:
            candidates = select_train_game_files(args.data_dir, task_type, args.games_per_type)
            wrapper = preselected_alfred_tw_env(make_config(args.data_dir, task_type, args.games_per_type, args.max_steps), args.split, candidates)
        else:
            wrapper = AlfredTWEnv(make_config(args.data_dir, task_type, pool_size, args.max_steps), train_eval=args.split)
        if reference_cohort:
            available = {canonical_game_path(game): game for game in wrapper.game_files}
            missing = [path for path in reference_cohort[task_type] if canonical_game_path(path) not in available]
            if missing:
                raise SystemExit(f"Reference game is not available in {TASK_TYPES[task_type]} valid-unseen pool: {missing[0]}")
            candidates = [available[canonical_game_path(path)] for path in reference_cohort[task_type]]
        elif requested:
            candidates = [game for game in wrapper.game_files if canonical_game_path(game) in requested]
        elif not direct_train_selection:
            candidates = [game for game in wrapper.game_files if canonical_game_path(game) not in excluded]
        if args.split == "train" and not reference_cohort:
            candidates = sorted(candidates, key=canonical_game_path)
        games_to_run = len(candidates) if requested else args.games_per_type
        if len(candidates) < games_to_run:
            raise SystemExit(f"Only {len(candidates)} eligible {TASK_TYPES[task_type]} games remain, but {games_to_run} were requested.")
        wrapper.game_files = candidates[:games_to_run]
        wrapper.num_games = len(wrapper.game_files)
        environment = wrapper.init_env(batch_size=1)
        try:
            for _ in range(games_to_run):
                episode = run_episode(environment, client, graph, args, task_type)
                output["episodes"].append(episode)
                output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"{episode['task_type']}: {'SUCCESS' if episode['success'] else 'FAIL'} ({len(episode['steps'])} environment actions; {episode['terminal_reason']})", flush=True)
        finally:
            environment.close()
    output["finished_at"] = datetime.now(timezone.utc).isoformat()
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    successes = sum(item["success"] for item in output["episodes"])
    print(f"Completed {len(output['episodes'])} episodes: {successes} successes. Results: {args.output}")


if __name__ == "__main__":
    main()
