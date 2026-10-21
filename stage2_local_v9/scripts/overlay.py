"""Fail-closed source overlay that changes only the audited v6 capacity policy."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final


ROOT: Final = Path(__file__).resolve().parents[2]
V6_SCRIPTS: Final = ROOT / "stage2_local_v6" / "scripts"

FROZEN_SHA256: Final = {
    "run_client_a_phase": "7602211daa38b189b72d5eed86e0d520f8bac2a6cc221e22d84e389b536e420a",
    "evolve_client_a_bank": "555fc3979f4f48447855c513229ec9728e7c7f10ad7669d6deb395db41f06f2b",
    "run_client_a_to_b5": "b5285c2f1885d8700af95c288a47b28553d7aff8b5a779d99718ae8bdda60503",
}

CAPACITY_SENTENCE: Final = " Maximum 14 total skills."
CAPACITY_BLOCK_START: Final = (
    '        prior_repairs = sum(1 for row in records if row.get("stage") == '
    '"capacity_repair" and row.get("role") == role)\n'
)
SCHEMA_BLOCK_START: Final = "        prior_schema_repairs = sum(\n"
FINAL_CAP_ASSERTION: Final = (
    "        if next_id - 1 > 14:\n"
    '            raise RuntimeError(f"Teacher exceeded 14-skill cap for {role}")\n'
)


def _load_frozen(name: str) -> str:
    path = V6_SCRIPTS / f"{name}.py"
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    expected = FROZEN_SHA256[name]
    if actual != expected:
        raise RuntimeError(
            f"refusing v9 overlay: frozen v6 source changed for {path}; "
            f"expected {expected}, got {actual}"
        )
    return raw.decode("utf-8").replace("\r\n", "\n")


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"v9 overlay expected one {label}, found {count}")
    return source.replace(old, new, 1)


def transformed_source(name: str) -> str:
    """Return the frozen v6 entry point with only declared v9 edits applied."""
    source = _load_frozen(name)
    if name == "evolve_client_a_bank":
        source = _replace_once(source, CAPACITY_SENTENCE, "", "merge-prompt capacity sentence")
        start = source.find(CAPACITY_BLOCK_START)
        end = source.find(SCHEMA_BLOCK_START, start)
        if start < 0 or end < 0:
            raise RuntimeError("v9 overlay could not locate the audited capacity block")
        source = source[:start] + source[end:]
        source = _replace_once(source, FINAL_CAP_ASSERTION, "", "final capacity assertion")
        source = _replace_once(
            source,
            "from originalFL.round1_evolver import _local_evolution_config\n",
            "from originalFL.round1_evolver import _local_evolution_config\n"
            "from stage2_local_v9.capacity_policy import (\n"
            "    enforce_role_capacity, resolve_b1_capacity_policy, role_capacity_context, role_skill_count,\n"
            ")\n",
            "B1-derived capacity imports",
        )
        source = _replace_once(
            source,
            "    parent_bank_hash = file_hash(args.parent_bank)\n"
            "    checkpoint_path = args.record_output.with_suffix(\".checkpoint.json\")\n",
            "    parent_bank_hash = file_hash(args.parent_bank)\n"
            "    capacity_policy = resolve_b1_capacity_policy(\n"
            "        parent_bank, args.generation, ROLES, parent_bank_hash\n"
            "    )\n"
            "    checkpoint_path = args.record_output.with_suffix(\".checkpoint.json\")\n",
            "B1-derived capacity resolution",
        )
        source = _replace_once(
            source,
            '            or checkpoint.get("teacher_endpoint") != teacher_descriptor\n'
            "        ):\n",
            '            or checkpoint.get("teacher_endpoint") != teacher_descriptor\n'
            '            or checkpoint.get("capacity_policy") != capacity_policy\n'
            "        ):\n",
            "checkpoint capacity identity",
        )
        source = _replace_once(
            source,
            '            "maximum_skill_field_characters": MAX_SKILL_FIELD_CHARACTERS,\n'
            '            "candidates": candidates,\n',
            '            "maximum_skill_field_characters": MAX_SKILL_FIELD_CHARACTERS,\n'
            '            "capacity_policy": capacity_policy,\n'
            '            "candidates": candidates,\n',
            "checkpoint capacity metadata",
        )
        source = _replace_once(
            source,
            '        "active_skillbanks": {},\n'
            "    }\n"
            "    for role in ROLES:\n"
            "        if role not in merged_values:\n",
            '        "active_skillbanks": {},\n'
            "    }\n"
            "    if capacity_policy is not None:\n"
            '        bank["capacity_policy"] = capacity_policy\n'
            "    for role in ROLES:\n"
            "        capacity_context = role_capacity_context(\n"
            '            capacity_policy, role, parent_bank["active_skillbanks"][role]\n'
            "        )\n"
            "        if capacity_context is None:\n"
            "            capacity_instruction = (\n"
            '                "B1 is the open-ended bootstrap generation: it has no fixed total skill "\n'
            '                "capacity. Keep every distinct evidence-grounded skill while deduplicating overlaps."\n'
            "            )\n"
            "            role_capacity = None\n"
            "        else:\n"
            '            role_capacity = capacity_context["maximum_total_skills"]\n'
            "            capacity_instruction = (\n"
            '                f"This role has a fixed B1-derived capacity of {role_capacity} skills. "\n'
            '                f"The parent contains {capacity_context[\'parent_skill_count\']} skills, leaving "\n'
            '                f"{capacity_context[\'available_add_slots\']} direct ADD slots. ADD is allowed "\n'
            '                "without deletion while the complete returned bank stays within the fixed capacity. "\n'
            '                "At capacity, DELETE or MERGE existing content before ADD. Never borrow capacity "\n'
            '                "from another role and never exceed the fixed capacity."\n'
            "            )\n"
            "        if role not in merged_values:\n",
            "role capacity prompt context",
        )
        source = _replace_once(
            source,
            '                "instruction": "Construct the complete next-generation role bank by jointly applying the six-family evidence to the frozen parent role bank. You may retain, update, merge, add, or delete parent content, but every change must be evidence-grounded. Deduplicate overlaps. General must transfer across task families; otherwise place it under exactly one task-specific Chinese label. Return the complete bank, not a patch. Return JSON only; do not assign IDs. The only allowed type strings are \'Procedure or Local Strategy\' and \'Failure Lesson\'.",\n'
            '                "allowed_task_labels": list(TASK_TYPE_LABELS.values()),\n',
            '                "instruction": "Construct the complete next-generation role bank by jointly applying the six-family evidence to the frozen parent role bank. You may retain, update, merge, add, or delete parent content, but every change must be evidence-grounded. Deduplicate overlaps. General must transfer across task families; otherwise place it under exactly one task-specific Chinese label. " + capacity_instruction + " Return the complete bank, not a patch. Return JSON only; do not assign IDs. The only allowed type strings are \'Procedure or Local Strategy\' and \'Failure Lesson\'.",\n'
            '                "capacity_policy": capacity_context,\n'
            '                "allowed_task_labels": list(TASK_TYPE_LABELS.values()),\n',
            "dynamic B1-derived capacity prompt",
        )
        source = _replace_once(
            source,
            SCHEMA_BLOCK_START,
            "        if role_capacity is not None:\n"
            "            prior_b1_capacity_repairs = sum(\n"
            "                1 for row in records\n"
            '                if row.get("stage") == "b1_capacity_repair" and row.get("role") == role\n'
            "            )\n"
            "            for capacity_repair_index in range(prior_b1_capacity_repairs, 2):\n"
            "                skill_count = role_skill_count(value)\n"
            "                if skill_count <= role_capacity:\n"
            "                    break\n"
            "                repair_prompt = {\n"
            '                    "client": "A", "role": role, "role_boundary": ROLE_RULES[role],\n'
            '                    "current_merged_bank": value,\n'
            '                    "maximum_total_skills": role_capacity,\n'
            '                    "current_skill_count": skill_count,\n'
            '                    "instruction": "The complete role bank exceeds its fixed B1-derived capacity. Remove or merge the least useful overlapping content until the total is at most the stated maximum. Do not add new claims. Preserve the exact top-level shape and all six task-specific labels. Return JSON only; do not assign IDs.",\n'
            "                }\n"
            "                value, capacity_repair_record = call_json(\n"
            "                    config,\n"
            '                    [{"role": "system", "content": "You are repairing a B1-derived capacity violation without mechanical trimming."}, {"role": "user", "content": json.dumps(repair_prompt, ensure_ascii=False)}],\n'
            "                    args,\n"
            "                )\n"
            '                if set(value) != {"general", "task_specific"} or set(value.get("task_specific", {})) != set(TASK_TYPE_LABELS.values()):\n'
            '                    raise RuntimeError(f"invalid B1-capacity-repaired bank shape for {role}")\n'
            "                merged_values[role] = value\n"
            "                records.append({\n"
            '                    "stage": "b1_capacity_repair", "role": role,\n'
            '                    "repair_index": capacity_repair_index + 1,\n'
            '                    "maximum_total_skills": role_capacity,\n'
            '                    "previous_skill_count": skill_count,\n'
            "                    **capacity_repair_record,\n"
            "                })\n"
            "                save_checkpoint()\n"
            "            enforce_role_capacity(value, role, capacity_policy)\n"
            + SCHEMA_BLOCK_START,
            "dynamic B1-derived capacity repair",
        )
        source = _replace_once(
            source,
            "        if remaining_errors:\n"
            '            raise RuntimeError(f"Teacher schema repair failed for {role}: {remaining_errors}")\n'
            '        numbered, next_id = {"general": [], "task_specific": {label: [] for label in TASK_TYPE_LABELS.values()}}, 1\n',
            "        if remaining_errors:\n"
            '            raise RuntimeError(f"Teacher schema repair failed for {role}: {remaining_errors}")\n'
            "        enforce_role_capacity(value, role, capacity_policy)\n"
            '        numbered, next_id = {"general": [], "task_specific": {label: [] for label in TASK_TYPE_LABELS.values()}}, 1\n',
            "final B1-derived capacity assertion",
        )
        source = _replace_once(
            source,
            '        "maximum_skill_field_characters": MAX_SKILL_FIELD_CHARACTERS,\n'
            '        "parent_bank_file_sha256": parent_bank_hash,\n',
            '        "maximum_skill_field_characters": MAX_SKILL_FIELD_CHARACTERS,\n'
            '        "capacity_policy": capacity_policy,\n'
            '        "parent_bank_file_sha256": parent_bank_hash,\n',
            "Teacher record capacity metadata",
        )
        source = _replace_once(
            source,
            "        remaining_errors = merged_bank_validation_errors(value)\n",
            "        field_alias_normalizations = []\n"
            "        for alias_scope, alias_label, alias_rows in (\n"
            "            [(\"general\", None, value[\"general\"])]\n"
            "            + [(\"task_specific\", label, value[\"task_specific\"][label]) for label in TASK_TYPE_LABELS.values()]\n"
            "        ):\n"
            "            for alias_index, alias_row in enumerate(alias_rows, 1):\n"
            "                if alias_row.get(\"type\") != \"Failure Lesson\":\n"
            "                    continue\n"
            "                description = alias_row.get(\"description\")\n"
            "                principle = alias_row.get(\"principle\")\n"
            "                other_fields_valid = all(\n"
            "                    isinstance(alias_row.get(field), str)\n"
            "                    and alias_row[field].strip()\n"
            "                    and len(alias_row[field]) <= MAX_SKILL_FIELD_CHARACTERS\n"
            "                    for field in (\"why_it_happens\", \"how_to_avoid\")\n"
            "                )\n"
            "                if (\n"
            "                    (not isinstance(description, str) or not description.strip())\n"
            "                    and isinstance(principle, str)\n"
            "                    and principle.strip()\n"
            "                    and len(principle) <= MAX_SKILL_FIELD_CHARACTERS\n"
            "                    and other_fields_valid\n"
            "                ):\n"
            "                    alias_row[\"description\"] = principle\n"
            "                    field_alias_normalizations.append({\n"
            "                        \"scope\": alias_scope,\n"
            "                        \"task_label\": alias_label,\n"
            "                        \"index\": alias_index,\n"
            "                        \"type\": \"Failure Lesson\",\n"
            "                        \"source_field\": \"principle\",\n"
            "                        \"target_field\": \"description\",\n"
            "                    })\n"
            "        if field_alias_normalizations:\n"
            "            merged_values[role] = value\n"
            "            records.append({\n"
            "                \"stage\": \"deterministic_schema_field_alias_normalization\",\n"
            "                \"role\": role,\n"
            "                \"normalizations\": field_alias_normalizations,\n"
            "                \"policy\": \"copy existing principle verbatim into missing Failure Lesson description only when the other declared fields are valid\",\n"
            "            })\n"
            "            save_checkpoint()\n"
            "        type_normalizations = []\n"
            "        for normalization_scope, normalization_label, normalization_rows in (\n"
            "            [(\"general\", None, value[\"general\"])]\n"
            "            + [(\"task_specific\", label, value[\"task_specific\"][label]) for label in TASK_TYPE_LABELS.values()]\n"
            "        ):\n"
            "            for normalization_index, normalization_row in enumerate(normalization_rows, 1):\n"
            "                declared_fields = SKILL_FIELDS.get(normalization_row.get(\"type\"))\n"
            "                declared_valid = declared_fields is not None and all(\n"
            "                    isinstance(normalization_row.get(field), str)\n"
            "                    and normalization_row[field].strip()\n"
            "                    and len(normalization_row[field]) <= MAX_SKILL_FIELD_CHARACTERS\n"
            "                    for field in declared_fields\n"
            "                )\n"
            "                if declared_valid:\n"
            "                    continue\n"
            "                valid_types = [\n"
            "                    skill_type\n"
            "                    for skill_type, fields in SKILL_FIELDS.items()\n"
            "                    if all(\n"
            "                        isinstance(normalization_row.get(field), str)\n"
            "                        and normalization_row[field].strip()\n"
            "                        and len(normalization_row[field]) <= MAX_SKILL_FIELD_CHARACTERS\n"
            "                        for field in fields\n"
            "                    )\n"
            "                ]\n"
            "                if len(valid_types) == 1:\n"
            "                    previous_type = normalization_row.get(\"type\")\n"
            "                    normalization_row[\"type\"] = valid_types[0]\n"
            "                    type_normalizations.append({\n"
            "                        \"scope\": normalization_scope,\n"
            "                        \"task_label\": normalization_label,\n"
            "                        \"index\": normalization_index,\n"
            "                        \"from_type\": previous_type,\n"
            "                        \"to_type\": valid_types[0],\n"
            "                    })\n"
            "        if type_normalizations:\n"
            "            merged_values[role] = value\n"
            "            records.append({\n"
            "                \"stage\": \"deterministic_schema_type_normalization\",\n"
            "                \"role\": role,\n"
            "                \"normalizations\": type_normalizations,\n"
            "                \"policy\": \"change only an invalid declared type when exactly one complete legal field set exists\",\n"
            "            })\n"
            "            save_checkpoint()\n"
            "        remaining_errors = merged_bank_validation_errors(value)\n",
            "deterministic schema type normalization",
        )
        source = _replace_once(
            source,
            "    if args.generation < 2:\n        raise SystemExit(\"continuation evolver requires generation >= 2\")\n",
            "    if args.generation < 1:\n        raise SystemExit(\"v9 evolver requires generation >= 1\")\n",
            "generation-1 evolver gate",
        )
        source = _replace_once(
            source,
            "    if evidence.get(\"parent_bank_file_sha256\") != file_hash(args.parent_bank):\n",
            "    if args.generation > 1 and evidence.get(\"parent_bank_file_sha256\") != file_hash(args.parent_bank):\n",
            "empty-B0 evidence parent hash gate",
        )
    elif name == "run_client_a_phase":
        source = _replace_once(
            source,
            "stage2_local_v6/artifacts/manifests/client_a_generation_01.json",
            "stage2_local_v9/artifacts/manifests/client_a_generation_01.json",
            "phase default manifest path",
        )
        source = _replace_once(
            source,
            "    if args.generation > 0 and not args.bank:\n",
            "    if args.generation > 0 and not args.bank and not (args.phase == \"training\" and args.generation == 1):\n",
            "empty-B0 generation-1 training gate",
        )
        source = _replace_once(
            source,
            '    for task in tasks:\n'
            '        cmd.extend(["--only-game-file", str(args.data_root / "json_2.1.1" / "train" / task / "game.tw-pddl")])\n',
            '    if args.max_control_retries is not None:\n'
            '        cmd.extend(["--max-control-retries", str(args.max_control_retries)])\n'
            '    for task in tasks:\n'
            '        cmd.extend(["--only-game-file", str(args.data_root / "json_2.1.1" / "train" / task / "game.tw-pddl")])\n',
            "optional Client-A control-retry forwarding",
        )
        source = _replace_once(
            source,
            '    parser.add_argument("--resume-order-reference", type=Path)\n',
            '    parser.add_argument("--resume-order-reference", type=Path)\n'
            '    parser.add_argument("--max-control-retries", type=int)\n',
            "optional Client-A control-retry argument",
        )
        source = _replace_once(
            source,
            '            "order_reference_file_sha256": file_hash(args.resume_order_reference),\n',
            '            "order_reference_file_sha256": file_hash(args.resume_order_reference),\n'
            '            "runtime_guard_amendment": {"max_control_retries": args.max_control_retries},\n',
            "Client-A resume control-retry audit",
        )
        source = _replace_once(
            source,
            '            "parent_bank_file_sha256": file_hash(args.bank),\n'
            '            "parent_live_repository_sha256": bank_payload.get("live_repository_sha256"),\n',
            '            "parent_bank_file_sha256": file_hash(args.bank) if args.bank else None,\n'
            '            "parent_live_repository_sha256": bank_payload.get("live_repository_sha256") if bank_payload else None,\n',
            "empty-B0 evidence parent hashes",
        )
    elif name == "run_client_a_to_b5":
        source = source.replace("stage2_local_v6", "stage2_local_v9")
        if "stage2_local_v6" in source:
            raise RuntimeError("v9 controller overlay left a v6 path behind")
    else:
        raise ValueError(f"unsupported v9 overlay entry point: {name}")
    return source


def execute(name: str, wrapper_file: str) -> None:
    source = transformed_source(name)
    namespace = {
        "__name__": "__main__",
        "__file__": wrapper_file,
        "__package__": None,
        "__builtins__": __builtins__,
    }
    exec(compile(source, wrapper_file, "exec"), namespace, namespace)
