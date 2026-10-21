from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from client_code.skillbank_loader import SKILL_FIELDS
from stage3_2_role_agnostic_semantic_merge.local_round2_evolver import (
    EvolutionError,
    apply_compression_replacements,
    normalize_known_json_mode_wrapper,
    oversized_skill_fields,
    validate_compression_only,
    validate_and_apply_patch,
)
from stage3_2_role_agnostic_semantic_merge.run_global2_to_local_b3 import logical_repository
from stage3_2_role_agnostic_semantic_merge.manual_field_repair import apply_reviewed_replacements


ROOT = Path(__file__).resolve().parents[2]


class Global2ToLocalB3Tests(unittest.TestCase):
    def setUp(self) -> None:
        path = ROOT / "stage3_2_role_agnostic_semantic_merge/runs/v9_global2_client_validation_20261015_r1/client_A/replacement_skillbank.json"
        self.parent = json.loads(path.read_text(encoding="utf-8"))
        self.repository = logical_repository(self.parent, "A")

    def test_exact_json_mode_wrapper_only(self) -> None:
        normalized, audit = normalize_known_json_mode_wrapper(
            {"type": "json_object", "findings": []}, "findings"
        )
        self.assertEqual(normalized, {"findings": []})
        self.assertEqual(audit["removed_field"], {"type": "json_object"})
        unchanged, rejected_audit = normalize_known_json_mode_wrapper(
            {"type": "object", "findings": []}, "findings"
        )
        self.assertEqual(unchanged["type"], "object")
        self.assertIsNone(rejected_audit)

    def test_round_three_add_id_and_whole_bank_quota(self) -> None:
        rows = self.repository["general"] + sum(self.repository["task_specific"].values(), [])
        deleted = rows[:3]
        template = deleted[0]
        skill = {"type": template["type"]}
        for field in SKILL_FIELDS[template["type"]]:
            skill[field] = f"Unique round three regression content for {field}."
        operations = [
            {"operation": "DELETE", "target_skill_id": row["skill_id"], "evidence_refs": [f"evidence/{index}"]}
            for index, row in enumerate(deleted, 1)
        ]
        operations.append({"operation": "ADD", "bucket": "general", "skill": skill, "evidence_refs": ["evidence/add"]})
        candidate, accepted, counts = validate_and_apply_patch(
            {"operations": operations}, self.repository, "A", round_index=3
        )
        candidate_rows = candidate["general"] + sum(candidate["task_specific"].values(), [])
        self.assertEqual(counts, {"base": 44, "delete": 3, "add": 1, "update": 0, "candidate": 42})
        self.assertEqual(accepted[-1]["operation"], "ADD")
        self.assertIn("A_R3_ADD_001", {row["skill_id"] for row in candidate_rows})

    def test_field_compression_cannot_change_any_other_patch_content(self) -> None:
        previous = {
            "operations": [{
                "operation": "ADD",
                "bucket": "general",
                "skill": {
                    "type": "Procedure or Local Strategy",
                    "title": "Bounded repair",
                    "principle": "x" * 901,
                    "when_to_apply": "Use for the regression test.",
                },
                "evidence_refs": ["evidence/1"],
            }]
        }
        targets = oversized_skill_fields(previous)
        self.assertEqual([(row["operation_number"], row["field"], row["original_length"]) for row in targets], [(1, "principle", 901)])
        candidate = copy.deepcopy(previous)
        candidate["operations"][0]["skill"]["principle"] = "compressed meaning" * 20
        validate_compression_only(previous, candidate, targets, 760)
        changed_evidence = copy.deepcopy(candidate)
        changed_evidence["operations"][0]["evidence_refs"] = ["evidence/2"]
        with self.assertRaisesRegex(EvolutionError, "outside the authorized fields"):
            validate_compression_only(previous, changed_evidence, targets, 760)

        replacement_response = {
            "replacements": [{
                "operation_number": 1,
                "field": "principle",
                "text": "replacement-only compressed meaning",
            }]
        }
        applied = apply_compression_replacements(previous, replacement_response, targets, 760)
        self.assertEqual(applied["operations"][0]["evidence_refs"], ["evidence/1"])
        self.assertEqual(applied["operations"][0]["skill"]["title"], "Bounded repair")
        self.assertEqual(applied["operations"][0]["skill"]["principle"], "replacement-only compressed meaning")
        duplicate = {"replacements": replacement_response["replacements"] * 2}
        with self.assertRaisesRegex(EvolutionError, "unknown or duplicated"):
            apply_compression_replacements(previous, duplicate, targets, 760)

    def test_reviewed_repair_changes_only_invalid_fields_and_drops_named_add(self) -> None:
        previous = {
            "operations": [
                {"operation": "DELETE", "target_skill_id": "T1", "evidence_refs": ["e/1"]},
                {"operation": "DELETE", "target_skill_id": "T2", "evidence_refs": ["e/2"]},
                {"operation": "DELETE", "target_skill_id": "T3", "evidence_refs": ["e/3"]},
                {
                    "operation": "UPDATE", "target_skill_id": "T4", "bucket": "general",
                    "skill": {
                        "type": "Procedure or Local Strategy", "title": "Repair",
                        "principle": "The executor repeats the action.",
                        "when_to_apply": "Use after a failed action.",
                    },
                    "evidence_refs": ["e/4"],
                },
                {
                    "operation": "ADD", "bucket": "general",
                    "skill": {
                        "type": "Procedure or Local Strategy", "title": "Keep",
                        "principle": "Keep this supported addition.", "when_to_apply": "Use in one case.",
                    },
                    "evidence_refs": ["e/5"],
                },
                {
                    "operation": "ADD", "bucket": "general",
                    "skill": {
                        "type": "Procedure or Local Strategy", "title": "Drop",
                        "principle": "Drop this excess addition.", "when_to_apply": "Never retained.",
                    },
                    "evidence_refs": ["e/6"],
                },
            ]
        }
        spec = {
            "replacements": [{
                "operation_number": 4, "field": "principle",
                "text": "Repeat failures require changing the action or state.",
            }],
            "drop_add_operation_numbers": [6],
        }
        candidate, targets, dropped = apply_reviewed_replacements(previous, spec)
        self.assertEqual([(row["operation_number"], row["field"]) for row in targets], [(4, "principle")])
        self.assertEqual(dropped, [6])
        self.assertEqual(len(candidate["operations"]), 5)
        self.assertEqual(candidate["operations"][4], previous["operations"][4])
        bad = copy.deepcopy(spec)
        bad["drop_add_operation_numbers"] = [1]
        with self.assertRaisesRegex(ValueError, "only existing ADD"):
            apply_reviewed_replacements(previous, bad)

    def test_reviewed_repair_accepts_three_bounded_fields_without_other_changes(self) -> None:
        previous = {
            "operations": [
                {
                    "operation": "UPDATE", "target_skill_id": f"T{index}", "bucket": "general",
                    "skill": {
                        "type": "Procedure or Local Strategy", "title": f"Rule {index}",
                        "principle": chr(96 + index) * (900 + index),
                        "when_to_apply": f"Case {index}.",
                    },
                    "evidence_refs": [f"e/{index}"],
                }
                for index in range(1, 4)
            ]
        }
        spec = {
            "replacements": [
                {"operation_number": index, "field": "principle", "text": f"Bounded rule {index}."}
                for index in range(1, 4)
            ],
            "drop_add_operation_numbers": [],
        }
        candidate, targets, dropped = apply_reviewed_replacements(previous, spec)
        self.assertEqual([(row["operation_number"], row["field"]) for row in targets], [(1, "principle"), (2, "principle"), (3, "principle")])
        self.assertEqual(dropped, [])
        for index in range(3):
            self.assertEqual(candidate["operations"][index]["skill"]["principle"], f"Bounded rule {index + 1}.")
            self.assertEqual(candidate["operations"][index]["evidence_refs"], previous["operations"][index]["evidence_refs"])


if __name__ == "__main__":
    unittest.main()
