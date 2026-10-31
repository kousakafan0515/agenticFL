"""Raw-history, single-agent ALFWorld Text baselines.

The paper-aligned ReAct mode retains no skills, no state compression, and no
per-state admissible-action list. It evaluates five valid-unseen games from
each of the six official task families (30 episodes total by default).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import APIError, OpenAI
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

from alfworld.agents.environment.alfred_tw_env import AlfredTWEnv, TASK_TYPES


ACTION_RE = re.compile(r"(?:^|\n)\s*Action\s*:\s*(.+)", re.IGNORECASE)
INFRASTRUCTURE_API_ERROR_MARKER = "STAGE3_INFRASTRUCTURE_API_ERROR"
INVALID_ACTION_PATTERN_RECOVERY_LIMIT = 3
INVALID_ACTION_PATTERN_FAILURE_LIMIT = 6


class InfrastructureAPIError(RuntimeError):
    """Fatal model-service failure that must invalidate the whole paired run."""


def raise_if_api_error(exc: BaseException) -> None:
    """Convert any OpenAI-compatible SDK failure into a fatal, auditable error.

    Client policies may recover from malformed model text, invalid environment
    actions, or their own control-flow failures. They must never convert an API
    failure into an episode failure because paired evaluation has to rerun both
    conditions from a fresh environment.
    """
    current: BaseException | None = exc
    visited: set[int] = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if isinstance(current, InfrastructureAPIError):
            raise current
        if isinstance(current, APIError):
            raise InfrastructureAPIError(
                f"{INFRASTRUCTURE_API_ERROR_MARKER}: {current.__class__.__name__}: {current}"
            ) from current
        current = current.__cause__ or current.__context__
RAW_ACTION_RE = re.compile(
    r"^(?:go to|open|close|take|use|heat|cool|clean|slice|examine)\s+.+$|^put\s+.+?\s+in/on\s+.+$|^(?:inventory|look|help)$",
    re.IGNORECASE,
)
PUT_ACTION_RE = re.compile(
    r"^put\s+(.+?)\s+(?:in/on|in|on)\s+(.+)$",
    re.IGNORECASE,
)


def invalid_action_pattern_key(action: str) -> str | None:
    """Group invalid commands by semantic destination, not raw spelling."""
    normalized = " ".join((action or "").strip().lower().split())
    if not normalized:
        return None
    target_match = re.fullmatch(r"go to\s+(.+)", normalized)
    if target_match:
        return f"target:{target_match.group(1)}"
    target_match = re.fullmatch(r"put\s+.+?\s+(?:in/on|in|on)\s+(.+)", normalized)
    if target_match:
        return f"target:{target_match.group(1)}"
    # Retain legacy recognition for audit/replay data even though new model
    # outputs no longer accept move as a generic placement command.
    target_match = re.fullmatch(r"move\s+.+?\s+to\s+(.+)", normalized)
    if target_match:
        return f"target:{target_match.group(1)}"
    return f"action:{normalized}"


def trailing_invalid_action_pattern(steps: list[dict[str, Any]]) -> tuple[str | None, int]:
    """Return the semantic key/count for the trailing no-effect action run."""
    pattern_key: str | None = None
    count = 0
    for step in reversed(steps):
        if str(step.get("observation") or "").strip().casefold() != "nothing happens.":
            break
        key = invalid_action_pattern_key(str(step.get("action") or step.get("raw_action") or ""))
        if key is None:
            break
        if pattern_key is None:
            pattern_key = key
        elif key != pattern_key:
            break
        count += 1
    return pattern_key, count
ACTION_ONLY_SYSTEM_PROMPT = """You are controlling a text household environment. Complete the task.
Reply with exactly one line in this form: Action: <one environment command>
Do not explain your choice or write reasoning.

Use only these command forms (substitute names exactly as they appear in the observation):
go to <receptacle>; open <receptacle>; close <receptacle>;
take <object> from <receptacle>; put <object> in/on <receptacle>;
use <object>; heat <object> with <microwave>; cool <object> with <fridge>;
clean <object> with <sink or bathtub>; slice <object> with <knife>;
inventory; look; examine <object or receptacle>.
For placement, type the literal token "in/on" exactly as shown. The environment
does not accept synonyms such as 'look around' or 'move'."""

ACTION_FEEDBACK_SYSTEM_PROMPT = """You are controlling a text household environment. Complete the task.
Return exactly one line and nothing else: Action: <one environment command>
Do not write thoughts, explanations, plans, headings, or reasoning.

Use names exactly as they appear in the observation. The only commands are:
1. go to <receptacle>
2. take <object> from <receptacle>
3. put <object> in/on <receptacle> (type the literal token "in/on")
4. open <receptacle>
5. close <receptacle>
6. use <object>
7. clean <object> with <sink or bathtub>
8. heat <object> with <microwave>
9. cool <object> with <fridge>

If the environment says 'Nothing happens.', the previous action was invalid.
Choose a different action; do not repeat the failed action."""

BPO_REACT_SYSTEM_PROMPT = """Interact with a household to solve a task. Imagine you are an intelligent agent
in a household environment and your target is to perform actions to complete the task goal.
At the beginning, you receive a detailed environment description and a goal. At every later turn,
you receive the observation from the previous action. First briefly reason about the current state
and your next subgoal, then choose exactly one action.

Always return exactly two lines and no other text:
Thought: one short sentence about the next subgoal.
Action: one command.
Never omit the Action line, add headings, or write an instruction to yourself.

Use names exactly as they appear in the observation. The only commands are:
1. go to <receptacle>
2. take <object> from <receptacle>
3. put <object> in/on <receptacle> (type the literal token "in/on")
4. open <receptacle>
5. close <receptacle>
6. use <object>
7. clean <object> with <sink or bathtub>
8. heat <object> with <microwave>
9. cool <object> with <fridge>

If the environment says 'Nothing happens.', the last action was invalid. Use the observation and
history to choose a different action; do not repeat that failed action."""

# Ablation: retain the same explicit Thought/Action interface, but rely only on
# ALFWorld's native observation feedback rather than explaining invalid actions
# in the system prompt.
REACT_NATIVE_FEEDBACK_SYSTEM_PROMPT = BPO_REACT_SYSTEM_PROMPT.rsplit("\n\nIf the environment says", 1)[0]

STATE_LEDGER_SYSTEM_PROMPT = REACT_NATIVE_FEEDBACK_SYSTEM_PROMPT + """

You receive a compact factual state ledger instead of the full transcript. It is
updated mechanically from environment observations. Treat it as the record of
what is known; when information is absent, use a listed `go to <receptacle>`
command to visit it. Do not invent commands such as `inspect`. Do not output a
summary or a plan: still return exactly Thought and Action."""


class StateLedger:
    """A deterministic, bounded substitute for an ever-growing chat history.

    It intentionally does not infer unobserved facts or invoke another model.
    The raw observation after every executed action is stored in the result JSON
    for auditability; only this factual view is sent back to the acting model.
    """

    def __init__(self, initial_observation: str) -> None:
        self.initial_observation = initial_observation
        self.last_observation = initial_observation
        goal_match = re.search(r"Your task is to:\s*(.+)", initial_observation, re.IGNORECASE)
        self.goal = goal_match.group(1).strip() if goal_match else "Complete the task."
        world_match = re.search(r"Looking quickly around you, you see (.+?)\.\s*\n\nYour task", initial_observation, re.DOTALL)
        self.receptacles = world_match.group(1).strip() if world_match else "unknown"
        self.location = "middle of the room"
        self.holding: set[str] = set()
        self.contents: dict[str, str] = {}
        self.states: dict[str, str] = {}
        self.transforms: dict[str, str] = {}
        self.failed_actions: list[str] = []
        self.recent: list[tuple[str, str]] = []

    @staticmethod
    def _items(text: str) -> str:
        return text.strip().rstrip(".")

    def update(self, action: str, observation: str) -> None:
        self.last_observation = observation
        compact_observation = " ".join(observation.split())
        if "Nothing happens." in observation:
            if action not in self.failed_actions:
                self.failed_actions.append(action)
            self.failed_actions = self.failed_actions[-3:]
            self.recent.append((action, compact_observation))
            self.recent = self.recent[-4:]
            return

        arrival = re.search(r"You arrive at (.+?)\.", observation)
        if arrival:
            self.location = arrival.group(1)
        opened = re.search(r"You open (.+?)\.\s+The .*? is open\.", observation)
        if opened:
            self.states[opened.group(1)] = "open"
            self.location = opened.group(1)
        closed = re.search(r"You close (.+?)\.", observation)
        if closed:
            self.states[closed.group(1)] = "closed"
            self.location = closed.group(1)
        taken = re.search(r"You pick up (.+?) from (.+?)\.", observation)
        if taken:
            self.holding.add(taken.group(1))
        placed = re.search(r"You (?:move|put) (.+?) (?:to|in/on) (?:the )?(.+?)\.", observation)
        if placed:
            self.holding.discard(placed.group(1))
            self.contents[placed.group(2)] = self._items(placed.group(1))
        transformed = re.match(r"(clean|heat|cool) (.+?) with ", action)
        if transformed:
            self.transforms[transformed.group(2)] = transformed.group(1) + "ed"

        visible = re.search(r"(?:On the|In) (.+?), you see (.+?)\.", observation)
        if visible:
            container, items = visible.groups()
            self.contents[container] = self._items(items)
        self.recent.append((action, compact_observation[:240]))
        self.recent = self.recent[-4:]

    def prompt(self) -> str:
        content_lines = [f"{where}: {items}" for where, items in sorted(self.contents.items())]
        state_lines = [f"{where}={state}" for where, state in sorted(self.states.items())]
        recent_lines = [f"{action} -> {obs}" for action, obs in self.recent]
        return "\n".join([
            "INITIAL ENVIRONMENT AND GOAL (verbatim; fixed throughout this episode):",
            self.initial_observation,
            "COMPACT FACTUAL STATE LEDGER (not a complete world model):",
            f"Goal: {self.goal}",
            f"Navigable receptacles listed initially: {self.receptacles}",
            f"Current location: {self.location}",
            f"Holding: {', '.join(sorted(self.holding)) if self.holding else 'nothing known'}",
            f"Known container states: {'; '.join(state_lines) if state_lines else 'none'}",
            "Known visible contents: " + ("; ".join(content_lines[-12:]) if content_lines else "none"),
            f"Known transformations: {'; '.join(f'{item}={state}' for item, state in sorted(self.transforms.items())) if self.transforms else 'none'}",
            f"Recent invalid actions (do not repeat unless the state has changed): {'; '.join(self.failed_actions) if self.failed_actions else 'none'}",
            "Recent environment evidence: " + (" | ".join(recent_lines) if recent_lines else "initial observation only"),
            "LATEST ENVIRONMENT OBSERVATION (verbatim; act on this now):",
            self.last_observation,
        ])

    def messages(self) -> list[dict[str, str]]:
        return [{"role": "system", "content": STATE_LEDGER_SYSTEM_PROMPT}, {"role": "user", "content": self.prompt()}]

    def event_ledger(self) -> str:
        """Compact persistent facts for history that has fallen out of a raw window."""
        content_lines = [f"{where}: {items}" for where, items in sorted(self.contents.items())]
        state_lines = [f"{where}={state}" for where, state in sorted(self.states.items())]
        transform_lines = [f"{item}={state}" for item, state in sorted(self.transforms.items())]
        return "\n".join([
            "EVENT LEDGER FOR EARLIER HISTORY (mechanically extracted; not a command):",
            f"Current location: {self.location}",
            f"Holding: {', '.join(sorted(self.holding)) if self.holding else 'nothing known'}",
            f"Known container states: {'; '.join(state_lines) if state_lines else 'none'}",
            "Known discovered contents: " + ("; ".join(content_lines[-12:]) if content_lines else "none"),
            f"Known transformations: {'; '.join(transform_lines) if transform_lines else 'none'}",
            f"Recent invalid actions: {'; '.join(self.failed_actions) if self.failed_actions else 'none'}",
        ])


def make_config(data_dir: str, task_type: int, games_per_type: int, max_steps: int) -> dict[str, Any]:
    root = "$ALFWORLD_DATA"
    return {
        "env": {
            "task_types": [task_type],
            "goal_desc_human_anns_prob": 0,
            "domain_randomization": False,
            "expert_type": "handcoded",
        },
        "dataset": {
            "data_path": f"{root}/json_2.1.1/train",
            "eval_id_data_path": f"{root}/json_2.1.1/valid_seen",
            "eval_ood_data_path": f"{root}/json_2.1.1/valid_unseen",
            "num_train_games": 0,
            "num_eval_games": games_per_type,
        },
        "logic": {"domain": f"{root}/logic/alfred.pddl", "grammar": f"{root}/logic/alfred.twl2"},
        "general": {"training_method": "dagger"},
        "dagger": {"training": {"max_nb_steps_per_episode": max_steps}},
    }


def select_train_game_files(data_dir: str, task_type: int, count: int) -> list[str]:
    """Return a fixed, diverse train cohort without enumerating all train games.

    AlfredTWEnv's stock train loader validates every game in the full split
    before slicing it. For trajectory collection we inspect only the requested
    task-family directories and validate at most one usable game per
    object/receptacle setting. We then select one game from as many distinct
    target-object settings as possible, while deterministically varying the
    final receptacle too. This changes sampling only; it does not alter
    prompts, policy, or environment dynamics.
    """
    root = Path(data_dir) / "json_2.1.1" / "train"
    task_name = TASK_TYPES[task_type]
    # object -> final-receptacle -> one solvable representative game
    representatives: dict[str, dict[str, str]] = {}
    for task_dir in sorted(root.glob(f"{task_name}-*"), key=lambda item: str(item).casefold()):
        # Match AlfredTWEnv's unsupported-task filter.
        if "movable" in str(task_dir) or "Sliced" in str(task_dir):
            continue
        suffix = task_dir.name[len(task_name) + 1 :].split("-")
        # ALFWorld family directories have the form
        # <task>-<object>-None-<final-receptacle>-<scene-id>.
        # Use the object and final receptacle only as sampling strata; neither
        # is injected into an agent prompt.
        object_key = suffix[0] if suffix else task_dir.name
        receptacle_key = suffix[2] if len(suffix) >= 3 else task_dir.name
        if object_key in representatives and receptacle_key in representatives[object_key]:
            continue
        for game_path in sorted(task_dir.glob("*/game.tw-pddl"), key=lambda item: str(item).casefold()):
            try:
                game_data = json.loads(game_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not game_data.get("solvable", False):
                continue
            representatives.setdefault(object_key, {})[receptacle_key] = str(game_path)
            break

    # A stable shuffle avoids the previous lexical-prefix bias (e.g. every
    # selected item being Apple) while keeping the cohort reproducible.
    object_keys = sorted(representatives, key=str.casefold)
    seed_material = f"ALFWorld-diverse-train-v1:{task_name}:1234".encode("utf-8")
    rng = random.Random(int.from_bytes(hashlib.sha256(seed_material).digest()[:8], "big"))
    rng.shuffle(object_keys)

    # First take one representative per object. If a task family has fewer
    # than ``count`` usable objects (notably heat/cool), fill the remaining
    # slots round-robin from additional receptacle settings of those objects.
    # This retains maximum object diversity without reducing the requested
    # cohort size.
    by_object_remaining: dict[str, list[str]] = {}
    selected: list[str] = []
    for position, object_key in enumerate(object_keys):
        by_receptacle = representatives[object_key]
        receptacle_keys = sorted(by_receptacle, key=str.casefold)
        start = int.from_bytes(
            hashlib.sha256(f"{task_name}:{object_key}:1234".encode("utf-8")).digest()[:8], "big"
        ) % len(receptacle_keys)
        receptacle_key = receptacle_keys[(start + position) % len(receptacle_keys)]
        selected.append(by_receptacle[receptacle_key])
        by_object_remaining[object_key] = [
            by_receptacle[key] for key in receptacle_keys if key != receptacle_key
        ]
        if len(selected) == count:
            break

    while len(selected) < count:
        made_progress = False
        for object_key in object_keys:
            remaining = by_object_remaining[object_key]
            if not remaining:
                continue
            selected.append(remaining.pop(0))
            made_progress = True
            if len(selected) == count:
                break
        if not made_progress:
            raise SystemExit(
                f"Only {len(selected)} diverse usable train games were found for {task_name}; {count} were requested."
            )

    print(
        f"Selected {count} diverse fixed train games for {task_name}: "
        f"{min(len(representatives), count)} distinct target objects, without scanning the full train split."
    )
    return selected


def preselected_alfred_tw_env(config: dict[str, Any], split: str, game_files: list[str]) -> AlfredTWEnv:
    """Create an AlfredTWEnv around an already selected cohort.

    This intentionally bypasses AlfredTWEnv.__init__, whose only extra work is
    full-split discovery.  ``init_env`` needs exactly config, train_eval,
    game_files and num_games, all set here.
    """
    wrapper = AlfredTWEnv.__new__(AlfredTWEnv)
    wrapper.config = config
    wrapper.train_eval = split
    wrapper.game_files = game_files
    wrapper.num_games = len(game_files)
    return wrapper


def canonical_game_path(path: str) -> str:
    """Normalize a TextWorld game path for exact de-duplication."""
    return os.path.normcase(os.path.realpath(path))


def game_paths_from_results(result_paths: list[str]) -> set[str]:
    """Read previously evaluated game paths from this runner's result JSON."""
    excluded: set[str] = set()
    for result_path in result_paths:
        path = Path(result_path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            episodes = payload["episodes"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise SystemExit(f"Could not read prior result file {path}: {exc}") from exc
        for episode in episodes:
            game_file = episode.get("game_file")
            if isinstance(game_file, str):
                excluded.add(canonical_game_path(game_file))
    return excluded


def extract_action(text: str) -> str | None:
    match = ACTION_RE.search(text)
    candidate = match.group(1).strip() if match else text.strip()
    put_match = PUT_ACTION_RE.fullmatch(candidate)
    if put_match:
        candidate = f"put {put_match.group(1)} in/on {put_match.group(2)}"
    # Some instruction models return the requested command but omit the
    # presentation prefix.  Accept only a single command matching the public
    # ALFWorld grammar; this is parsing, not an extra repair-model call.
    return candidate if RAW_ACTION_RE.fullmatch(candidate) else None


def call_model(client: OpenAI, model: str, messages: list[dict[str, str]], no_thinking: bool, max_tokens: int, transport_retries: int, generation_seed: int | None = 1234, enable_thinking: bool | None = None, reasoning_sink: list[str] | None = None) -> tuple[str, dict[str, int | None]]:
    kwargs: dict[str, Any] = {"model": model, "messages": messages, "temperature": 0, "max_tokens": max_tokens}
    if generation_seed is not None:
        kwargs["seed"] = generation_seed
    if enable_thinking is not None:
        kwargs["extra_body"] = {"enable_thinking": enable_thinking}
    elif no_thinking:
        kwargs["extra_body"] = {"enable_thinking": False}
    if enable_thinking:
        # DashScope accepts enable_thinking only with SSE streaming.  The
        # updater still receives only final answer text; reasoning_content is
        # intentionally not appended to its structured-update parser input.
        kwargs["stream"] = True
        kwargs["stream_options"] = {"include_usage": True}
    recoverable = (APITimeoutError, APIConnectionError, InternalServerError, RateLimitError)
    for attempt in range(transport_retries + 1):
        try:
            response = client.chat.completions.create(**kwargs)
            if enable_thinking:
                content_parts: list[str] = []
                # Keep this attempt local: a transport retry must not leave
                # partial reasoning from a failed stream in the audit record.
                reasoning_parts: list[str] = []
                usage: Any | None = None
                for chunk in response:
                    chunk_usage = getattr(chunk, "usage", None)
                    if chunk_usage is not None:
                        usage = chunk_usage
                    choices = getattr(chunk, "choices", None) or []
                    if not choices:
                        continue
                    delta = getattr(choices[0], "delta", None)
                    content = getattr(delta, "content", None) if delta is not None else None
                    if content:
                        content_parts.append(content)
                    reasoning = getattr(delta, "reasoning_content", None) if delta is not None else None
                    if reasoning:
                        reasoning_parts.append(reasoning)
                if reasoning_sink is not None:
                    reasoning_sink.extend(reasoning_parts)
                return "".join(content_parts), {
                    "prompt_tokens": getattr(usage, "prompt_tokens", None),
                    "completion_tokens": getattr(usage, "completion_tokens", None),
                    "total_tokens": getattr(usage, "total_tokens", None),
                    "transport_attempts": attempt + 1,
                }
            usage = response.usage
            return response.choices[0].message.content or "", {
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
                "transport_attempts": attempt + 1,
            }
        except recoverable as exc:
            if attempt == transport_retries:
                raise
            delay = min(2 ** (attempt + 1), 15)
            print(f"Transport failure ({exc.__class__.__name__}); retrying the same action in {delay}s ({attempt + 1}/{transport_retries})", flush=True)
            time.sleep(delay)
    raise AssertionError("unreachable")


def append_trace(path: str | None, record: dict[str, Any]) -> None:
    """Persist debugging evidence after each environment step, if requested."""
    if not path:
        return
    trace_path = Path(path)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        handle.flush()


def run_episode(env: Any, client: OpenAI, args: argparse.Namespace, task_type: int) -> dict[str, Any]:
    observation, info = env.reset()
    observation = observation[0]
    initial_observation = observation
    game_file = info["extra.gamefile"][0]
    messages: list[dict[str, str]] = [{"role": "system", "content": args.system_prompt}, {"role": "user", "content": observation}]
    ledger = StateLedger(observation) if args.policy in ("react-state-ledger", "react-window-ledger") else None
    window_history: list[dict[str, str]] = []
    steps: list[dict[str, Any]] = []
    won = False
    append_trace(args.trace_file, {"event": "reset", "task_type": TASK_TYPES[task_type], "game_file": game_file, "initial_observation": initial_observation})
    for step_index in range(1, args.max_steps + 1):
        started = time.monotonic()
        try:
            print(f"Calling {args.model}: {TASK_TYPES[task_type]} step {step_index}/{args.max_steps}", flush=True)
            if args.policy == "react-state-ledger":
                request_messages = ledger.messages()
            elif args.policy in ("react-window", "react-window-ledger"):
                # Preserve exact ReAct chronology. The final item is always the
                # latest environment observation, directly adjacent to output.
                initial_message = messages[1]["content"]
                if args.policy == "react-window-ledger" and len(window_history) >= 2 * args.history_window_turns:
                    initial_message += "\n\n" + ledger.event_ledger()
                request_messages = [messages[0], {"role": "user", "content": initial_message}] + window_history
            else:
                request_messages = messages
            model_text, usage = call_model(client, args.model, request_messages, args.send_disable_thinking, args.max_completion_tokens, args.transport_retries)
            raw_action = extract_action(model_text)
            if not raw_action:
                entry = {"step": step_index, "model_output": model_text, "parse_error": True, "usage": usage, "agent_context": request_messages[-1]["content"]}
                steps.append(entry)
                append_trace(args.trace_file, {"event": "step", "task_type": TASK_TYPES[task_type], "game_file": game_file, "request_messages": request_messages, **entry})
                print(f"P0 parse failure in {TASK_TYPES[task_type]}: model replied {model_text!r}", flush=True)
                break
            action = " ".join(raw_action.split())
            next_obs, scores, dones, infos = env.step([action])
            observation = next_obs[0]
            won = bool(dones[0] and infos["won"][0])
            entry = {"step": step_index, "raw_action": raw_action, "action": action, "observation": observation, "model_output": model_text, "usage": usage, "latency_s": round(time.monotonic() - started, 3), "agent_context": request_messages[-1]["content"]}
            steps.append(entry)
            append_trace(args.trace_file, {"event": "step", "task_type": TASK_TYPES[task_type], "game_file": game_file, "request_messages": request_messages, **entry})
            if ledger:
                ledger.update(action, observation)
            if args.policy in ("react-window", "react-window-ledger"):
                window_history.extend([
                    {"role": "assistant", "content": model_text},
                    {"role": "user", "content": observation},
                ])
                window_history = window_history[-2 * args.history_window_turns:]
            elif not ledger:
                messages.append({"role": "assistant", "content": model_text})
                messages.append({"role": "user", "content": observation})
            if dones[0]:
                break
        except Exception as exc:
            raise_if_api_error(exc)
            entry = {"step": step_index, "error": repr(exc), "latency_s": round(time.monotonic() - started, 3)}
            steps.append(entry)
            append_trace(args.trace_file, {"event": "step", "task_type": TASK_TYPES[task_type], "game_file": game_file, **entry})
            print(f"P0 API/environment error in {TASK_TYPES[task_type]}: {exc!r}", flush=True)
            break
    return {"task_type_id": task_type, "task_type": TASK_TYPES[task_type], "game_file": game_file, "initial_observation": initial_observation, "success": won, "steps": steps}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-key-env", default="DASHSCOPE_API_KEY")
    parser.add_argument("--base-url", default="https://dashscope.aliyuncs.com/compatible-mode/v1")
    parser.add_argument("--model", required=True, help="OpenAI-compatible Qwen model ID")
    parser.add_argument("--data-dir", default="/mnt/c/Users/26624/Documents/Codex/2026-09-07/xia/alfworld-data")
    parser.add_argument("--games-per-type", type=int, default=5)
    parser.add_argument("--task-types", type=int, nargs="+", choices=range(1, 7), default=list(range(1, 7)))
    parser.add_argument("--max-steps", type=int, default=25)
    parser.add_argument("--policy", choices=("action-only", "action-feedback", "react-native-feedback", "react-window", "react-window-ledger", "react-state-ledger", "bpo-react"), default="action-only")
    parser.add_argument("--history-window-turns", type=int, default=10, help="For react-window: number of complete recent Thought/Action/observation turns to retain.")
    parser.add_argument("--max-completion-tokens", type=int, default=None)
    parser.add_argument("--request-timeout", type=float, default=60, help="Fail one API request after this many seconds.")
    parser.add_argument("--transport-retries", type=int, default=3, help="Retries for timeouts, connection failures, 5xx and rate limits.")
    parser.add_argument("--send-disable-thinking", action="store_true", help="Only for APIs that explicitly require enable_thinking=False.")
    parser.add_argument("--output", default="results/alfworld_p0.json")
    parser.add_argument("--trace-file", default=None, help="Optional JSONL path; flush one debugging record after every action.")
    parser.add_argument("--exclude-result", action="append", default=[], help="Prior result JSON whose game files must not be sampled again. May be repeated.")
    parser.add_argument("--only-game-file", action="append", default=[], help="Evaluate this exact .tw-pddl game file. May be repeated.")
    args = parser.parse_args()
    api_key = os.environ.get(args.api_key_env)
    if not api_key:
        raise SystemExit(f"Set {args.api_key_env} before running; do not put the key in this command.")
    if not (Path(args.data_dir) / "json_2.1.1" / "valid_unseen").is_dir():
        raise SystemExit(f"ALFWorld Text data was not found at {args.data_dir}")
    os.environ["ALFWORLD_DATA"] = args.data_dir
    if args.max_completion_tokens is None:
        args.max_completion_tokens = 256 if args.policy in ("bpo-react", "react-native-feedback", "react-window", "react-window-ledger", "react-state-ledger") else 64
    system_prompt = {
        "action-only": ACTION_ONLY_SYSTEM_PROMPT,
        "action-feedback": ACTION_FEEDBACK_SYSTEM_PROMPT,
        "react-native-feedback": REACT_NATIVE_FEEDBACK_SYSTEM_PROMPT,
        "react-window": REACT_NATIVE_FEEDBACK_SYSTEM_PROMPT,
        "react-window-ledger": REACT_NATIVE_FEEDBACK_SYSTEM_PROMPT,
        "react-state-ledger": STATE_LEDGER_SYSTEM_PROMPT,
        "bpo-react": BPO_REACT_SYSTEM_PROMPT,
    }[args.policy]
    args.system_prompt = system_prompt
    client = OpenAI(api_key=api_key, base_url=args.base_url, timeout=args.request_timeout, max_retries=0)
    output = {
        "protocol": (
            f"P1 {args.policy}; deterministic bounded state ledger; no skills/admissible-action list"
            if args.policy == "react-state-ledger"
            else (f"P1 react-window; initial observation + {args.history_window_turns} recent raw ReAct turns; no skills/admissible-action list"
                  if args.policy == "react-window"
                  else (f"P1 react-window-ledger; initial observation + {args.history_window_turns} recent raw ReAct turns + event ledger after the window fills; no skills/admissible-action list"
                        if args.policy == "react-window-ledger"
                        else f"P0 {args.policy}; raw full history; no skills/admissible-action list/state compression"))
        ),
        "reproduction_assumptions": {
            "horizon": args.max_steps,
            "temperature": 0,
            "environment": "official ALFWorld Text valid-unseen",
            "action_interface": "native TextWorld commands; placement uses literal 'put … in/on …'",
            "paper_status": (
                "paper-aligned policy; original BPO code and action wrapper are not public"
                if args.policy == "bpo-react"
                else ("ablation policy; deterministic bounded factual ledger replaces raw history"
                      if args.policy == "react-state-ledger"
                      else ("ablation policy; a fixed raw ReAct-history window replaces older history"
                            if args.policy == "react-window"
                            else ("ablation policy; raw ReAct window plus deterministic event ledger replaces older history"
                                  if args.policy == "react-window-ledger"
                                  else "ablation policy; the model receives only ALFWorld's native invalid-action observation")))
            ),
        },
        "started_at": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "episodes": [],
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    excluded_game_files = game_paths_from_results(args.exclude_result)
    requested_game_files = {canonical_game_path(path) for path in args.only_game_file}
    if requested_game_files & excluded_game_files:
        raise SystemExit("A requested --only-game-file is also present in --exclude-result.")
    for task_type in args.task_types:
        # Collect the whole task-family pool before filtering. This is sampling
        # control only: it does not alter the environment, prompt, or policy.
        pool_size = 0 if (excluded_game_files or requested_game_files) else args.games_per_type
        environment_wrapper = AlfredTWEnv(
            make_config(args.data_dir, task_type, pool_size, args.max_steps),
            train_eval="eval_out_of_distribution",
        )
        if requested_game_files:
            candidates = [game for game in environment_wrapper.game_files if canonical_game_path(game) in requested_game_files]
        else:
            candidates = [game for game in environment_wrapper.game_files if canonical_game_path(game) not in excluded_game_files]
        if len(candidates) < args.games_per_type:
            raise SystemExit(
                f"Only {len(candidates)} eligible {TASK_TYPES[task_type]} games remain, "
                f"but --games-per-type={args.games_per_type} was requested."
            )
        environment_wrapper.game_files = candidates[:args.games_per_type]
        environment_wrapper.num_games = len(environment_wrapper.game_files)
        environment = environment_wrapper.init_env(batch_size=1)
        try:
            for _ in range(args.games_per_type):
                episode = run_episode(environment, client, args, task_type)
                output["episodes"].append(episode)
                output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"{episode['task_type']}: {'SUCCESS' if episode['success'] else 'FAIL'} ({len(episode['steps'])} calls)", flush=True)
        finally:
            environment.close()
    output["finished_at"] = datetime.now(timezone.utc).isoformat()
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    successes = sum(item["success"] for item in output["episodes"])
    print(f"Completed {len(output['episodes'])} episodes: {successes} successes. Results: {args.output}")


if __name__ == "__main__":
    main()
