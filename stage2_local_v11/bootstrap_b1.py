"""V11 empty-B0 Teacher: ADD candidates only, then a complete B1 bank.

This reuses the hash-locked v9 overlay while narrowing its generation-1
candidate prompt and adding a fail-closed B0-only action check.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from client_code.skillbank_loader import EXPECTED_ROLES, parse_bank
from stage2_local_v9.scripts.client_overlay import execute_source, transformed_evolver_source
from stage2_local_v9.scripts.overlay import transformed_source


OLD_INSTRUCTION = (
    "Analyze every supplied trajectory relative to the frozen parent role bank. "
    "Propose 0-4 evidence-grounded changes. A change may add a new skill, update or "
    "merge an existing skill, retain a supported skill, or delete a contradicted or "
    "harmful skill. Do not copy object instance IDs. Return JSON only."
)
NEW_INSTRUCTION = (
    "B0 is empty. Propose 0-4 evidence-grounded ADD candidates only. "
    "There are no parent skills to retain, update, delete or merge. "
    "The later full-bank synthesis may deduplicate overlapping ADD ideas. "
    "Do not copy object instance IDs. Return JSON only."
)
OLD_ACTIONS = '"action": "ADD | UPDATE | MERGE | RETAIN | DELETE"'
NEW_ACTIONS = '"action": "ADD"'
OLD_FINAL = "You may retain, update, merge, add, or delete parent content, but every change must be evidence-grounded. Deduplicate overlaps."
NEW_FINAL = "The parent B0 bank is empty. Construct new skills only from evidence-grounded ADD candidates. Deduplicate and synthesize overlapping candidate ideas; do not retain, update, delete, or merge an old skill."
CHECK_ANCHOR = "            candidates[role][label] = rows_out\n"
ADD_CHECK = (
    "            if any(not isinstance(row, dict) or row.get('action') != 'ADD' "
    "or row.get('source_skill_ids') not in (None, []) for row in rows_out):\n"
    "                raise RuntimeError(f'B0 candidate must be ADD with no parent IDs: {role}/{label}')\n"
)


def v11_source(client: str) -> str:
    if client not in EXPECTED_ROLES:
        raise ValueError(f"unsupported client {client}")
    source = transformed_source("evolve_client_a_bank") if client == "A" else transformed_evolver_source(client)
    for old, new in ((OLD_INSTRUCTION, NEW_INSTRUCTION), (OLD_ACTIONS, NEW_ACTIONS), (OLD_FINAL, NEW_FINAL), (CHECK_ANCHOR, ADD_CHECK + CHECK_ANCHOR)):
        if source.count(old) != 1:
            raise RuntimeError(f"v11 B0 overlay expected exactly one source anchor: {old[:60]}")
        source = source.replace(old, new, 1)
    return source


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", choices=tuple("ABC"), required=True)
    parser.add_argument("--parent-bank", type=Path, required=True)
    args, remainder = parser.parse_known_args()
    parent = json.loads(args.parent_bank.read_text(encoding="utf-8"))
    parse_bank(parent, args.client)
    if parent.get("generation") != 0:
        parser.error("v11 bootstrap requires generation-0 parent")
    if any(bank["general"] or any(bank["task_specific"].values()) for bank in parent["active_skillbanks"].values()):
        parser.error("v11 bootstrap requires every B0 role bank to be empty")
    if "--generation" not in remainder or remainder[remainder.index("--generation") + 1] != "1":
        parser.error("v11 bootstrap only produces B1")
    if "--evidence" not in remainder:
        parser.error("v11 bootstrap requires B0 training evidence")
    evidence = json.loads(Path(remainder[remainder.index("--evidence") + 1]).read_text(encoding="utf-8"))
    if evidence.get("client_id") != args.client or evidence.get("generation") != 1 or evidence.get("experiment_id") != "stage2-local-v11-role-partitioned-patch3" or len(evidence.get("episodes") or []) != 134:
        parser.error("v11 bootstrap requires this client's complete v11 B0 training evidence")
    sys.argv = [sys.argv[0], *remainder, "--parent-bank", str(args.parent_bank)]
    wrapper = Path(__file__).resolve().parent / "scripts" / "bootstrap_b1.py"
    execute_source(v11_source(args.client), str(wrapper))


if __name__ == "__main__":
    main()
