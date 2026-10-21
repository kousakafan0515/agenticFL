from __future__ import annotations

import unittest

from stage3_2_role_agnostic_semantic_merge.round1_aggregate import (
    _manifest_identity_without_display_paths,
    validate_model_output,
)


class Round1AggregationValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.inputs = [
            {"source_skill_key": "A/Planner/general/skill_01"},
            {"source_skill_key": "B/Executor/general/skill_01"},
        ]

    def test_accepts_complete_consolidation(self) -> None:
        value = {"skills": [{
            "type": "Procedure or Local Strategy",
            "title": "Observation-grounded progression",
            "principle": "Use the latest observation to choose a valid next step.",
            "when_to_apply": "When progressing through a household task.",
            "source_skill_keys": [
                "A/Planner/general/skill_01", "B/Executor/general/skill_01",
            ],
        }]}
        cleaned, errors = validate_model_output(value, self.inputs)
        self.assertEqual(errors, [])
        self.assertEqual(len(cleaned), 1)

    def test_rejects_missing_source_and_role_wording(self) -> None:
        value = {"skills": [{
            "type": "Procedure or Local Strategy",
            "title": "Executor rule",
            "principle": "Executor should act.",
            "when_to_apply": "Always.",
            "source_skill_keys": ["A/Planner/general/skill_01"],
        }]}
        _, errors = validate_model_output(value, self.inputs)
        self.assertTrue(any("forbidden role" in error for error in errors))
        self.assertTrue(any("missing source_skill_keys" in error for error in errors))

    def test_manifest_identity_is_portable_between_windows_and_wsl(self) -> None:
        windows = {"inputs": {"A": {"path": "D:\\\\skillMAS\\\\bank.json", "file_sha256": "sha256:x", "skill_count": 1}}}
        wsl = {"inputs": {"A": {"path": "/mnt/d/skillMAS/bank.json", "file_sha256": "sha256:x", "skill_count": 1}}}
        self.assertEqual(
            _manifest_identity_without_display_paths(windows),
            _manifest_identity_without_display_paths(wsl),
        )

    def test_role_check_does_not_reject_critical(self) -> None:
        value = {"skills": [{
            "type": "Procedure or Local Strategy",
            "title": "Verify critical actions",
            "principle": "Check the observation after every critical action.",
            "when_to_apply": "After a critical state transition.",
            "source_skill_keys": [
                "A/Planner/general/skill_01", "B/Executor/general/skill_01",
            ],
        }]}
        _, errors = validate_model_output(value, self.inputs)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
