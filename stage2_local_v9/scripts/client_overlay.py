"""Fail-closed v9 source overlays for Client B and Client C."""

from __future__ import annotations

from typing import Final

from stage2_local_v9.scripts.overlay import transformed_source


SUPPORTED_CLIENTS: Final = ("B", "C")
ROLE_RULES: Final = {
    "B": {
        "Executor": (
            "The sole environment-acting role. Learn whole-task execution, observation-grounded "
            "action choice, exact ALFWorld action forms, use of advisory Critic feedback, and recovery."
        ),
        "Critic": (
            "A periodic non-acting auditor. Learn diagnosis, progress checks, contradiction detection, "
            "and concise corrective advice for the Executor. Never assign environment actions to Critic."
        ),
    },
    "C": {
        "Supervisor": (
            "A non-acting dispatcher called initially and after HANDOFF or BLOCKED. Learn task "
            "decomposition, worker selection, mission boundaries, handoff repair, and completion checks."
        ),
        "Search Worker": (
            "An environment-acting worker limited to finding, reaching, opening, and taking objects. "
            "Learn search/navigation, inventory acquisition, exact ALFWorld actions, and when to hand off."
        ),
        "Operation Worker": (
            "An environment-acting worker limited to transforming held objects and placing them at the "
            "destination. Learn clean/heat/cool/light/place execution, recovery, and when to hand off."
        ),
    },
}


def _replace(source: str, old: str, new: str, expected: int, label: str) -> str:
    count = source.count(old)
    if count != expected:
        raise RuntimeError(f"B/C overlay expected {expected} {label}, found {count}")
    return source.replace(old, new)


def transformed_phase_source(client: str) -> str:
    if client not in SUPPORTED_CLIENTS:
        raise ValueError(f"unsupported client: {client}")
    lower = client.lower()
    source = transformed_source("run_client_a_phase")
    changes = (
        ("alfworld_client_a.py", f"alfworld_client_{lower}.py", 1, "client runtime"),
        ("client_a_generation_01.json", f"client_{lower}_generation_01.json", 1, "manifest"),
        ('FIXED_ARGS["A"]', f'FIXED_ARGS["{client}"]', 1, "fixed arguments"),
        ('build_adapter(bank_payload, "A"', f'build_adapter(bank_payload, "{client}"', 1, "adapter client"),
        ('"client": "A"', f'"client": "{client}"', 2, "client fields"),
        ('"client_id": "A"', f'"client_id": "{client}"', 1, "evidence client"),
        ("client_A", f"client_{client}", 1, "evidence reference"),
        ("Client A exited", f"Client {client} exited", 1, "exit message"),
    )
    for old, new, expected, label in changes:
        source = _replace(source, old, new, expected, label)
    return source


def transformed_evolver_source(client: str) -> str:
    if client not in SUPPORTED_CLIENTS:
        raise ValueError(f"unsupported client: {client}")
    source = transformed_source("evolve_client_a_bank")
    old_rules = '''ROLE_RULES = {
    "Planner": "Only learn goal decomposition, subtask ordering, and plan repair. Never assign environment actions to Planner.",
    "Executor": "Only learn local execution, observation-based decisions, exact ALFWorld action forms, and recovery inside the assigned subtask.",
}'''
    new_rules = "ROLE_RULES = " + repr(ROLE_RULES[client])
    changes = (
        ('ROLES = EXPECTED_ROLES["A"]', f'ROLES = EXPECTED_ROLES["{client}"]', 1, "role selection"),
        (old_rules, new_rules, 1, "role rules"),
        ('evidence.get("client_id") != "A"', f'evidence.get("client_id") != "{client}"', 1, "evidence client check"),
        ("Client A generation", f"Client {client} generation", 1, "evidence error"),
        ('parse_bank(parent_bank, "A")', f'parse_bank(parent_bank, "{client}")', 1, "parent parser"),
        ('"client": "A"', f'"client": "{client}"', 4, "Teacher client prompts"),
        ('"source_client": "A", "target_client": "A"', f'"source_client": "{client}", "target_client": "{client}"', 1, "bank client identity"),
        ('parse_bank(bank, "A")', f'parse_bank(bank, "{client}")', 1, "output parser"),
        ('"client_id": "A"', f'"client_id": "{client}"', 1, "record client"),
    )
    for old, new, expected, label in changes:
        source = _replace(source, old, new, expected, label)
    return source


def execute_source(source: str, wrapper_file: str) -> None:
    namespace = {
        "__name__": "__main__",
        "__file__": wrapper_file,
        "__package__": None,
        "__builtins__": __builtins__,
    }
    exec(compile(source, wrapper_file, "exec"), namespace, namespace)
