from __future__ import annotations

import json
import unittest
from pathlib import Path

from stage3_2_role_agnostic_semantic_merge.local_round2_evolver import (
    EvolutionError,
    extract_base_repository,
    validate_and_apply_patch,
    validate_findings,
)


ROOT = Path(__file__).resolve().parents[2]


class LocalRound2PolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        path = ROOT / "stage3_2_role_agnostic_semantic_merge/runs/v9_b1_round1_client_validation_20261014_r1/client_A/replacement_skillbank.json"
        cls.repository = extract_base_repository(json.loads(path.read_text(encoding="utf-8")), "A")

    @staticmethod
    def new_skill() -> dict[str, str]:
        return {
            "type": "Procedure or Local Strategy",
            "title": "Evidence-grounded recovery",
            "principle": "Change the environment state after a failed action.",
            "when_to_apply": "When the previous action produced no state change.",
        }

    def test_three_deletes_fund_one_add_across_buckets(self) -> None:
        value = {"operations": [
            {"operation": "DELETE", "target_skill_id": "G_001", "evidence_refs": ["e1"]},
            {"operation": "DELETE", "target_skill_id": "T2_001", "evidence_refs": ["e2"]},
            {"operation": "DELETE", "target_skill_id": "T5_001", "evidence_refs": ["e3"]},
            {"operation": "ADD", "bucket": "加热后放置", "skill": self.new_skill(), "evidence_refs": ["e4"]},
        ]}
        repository, operations, counts = validate_and_apply_patch(value, self.repository, "A")
        self.assertEqual(counts, {"base": 43, "delete": 3, "add": 1, "update": 0, "candidate": 41})
        self.assertEqual(len(operations), 4)
        self.assertTrue(any(row["skill_id"] == "A_R2_ADD_001" for row in repository["task_specific"]["加热后放置"]))

    def test_two_deletes_cannot_fund_one_add(self) -> None:
        value = {"operations": [
            {"operation": "DELETE", "target_skill_id": "G_001", "evidence_refs": ["e1"]},
            {"operation": "DELETE", "target_skill_id": "T2_001", "evidence_refs": ["e2"]},
            {"operation": "ADD", "bucket": "general", "skill": self.new_skill(), "evidence_refs": ["e3"]},
        ]}
        with self.assertRaisesRegex(EvolutionError, "3-delete/1-add violation"):
            validate_and_apply_patch(value, self.repository, "A")

    def test_update_can_move_between_buckets_without_quota(self) -> None:
        value = {"operations": [{
            "operation": "UPDATE", "target_skill_id": "T2_001", "bucket": "general",
            "skill": self.new_skill(), "evidence_refs": ["e1"],
        }]}
        repository, _, counts = validate_and_apply_patch(value, self.repository, "A")
        self.assertEqual(counts["candidate"], 43)
        self.assertEqual(counts["add"], 0)
        self.assertTrue(any(row["skill_id"] == "T2_001" for row in repository["general"]))

    def test_d096_client_a_uses_an_explicit_control_retry_guard(self) -> None:
        controller = (ROOT / "stage3_2_role_agnostic_semantic_merge/run_client_to_b2.py").read_text(encoding="utf-8")
        overlay = (ROOT / "stage2_local_v9/scripts/overlay.py").read_text(encoding="utf-8")
        self.assertIn('command.extend(["--max-control-retries", "12"])', controller)
        self.assertIn('parser.add_argument(\"--max-control-retries\", type=int)', overlay)
        self.assertIn('\"runtime_guard_amendment\": {\"max_control_retries\": args.max_control_retries}', overlay)

    def test_family_findings_over_eight_require_teacher_repair(self) -> None:
        with self.assertRaisesRegex(EvolutionError, "at most 8"):
            validate_findings({"findings": [{} for _ in range(12)]})
        self.assertEqual(len(validate_findings({"findings": [{} for _ in range(8)]})), 8)


if __name__ == "__main__":
    unittest.main()
