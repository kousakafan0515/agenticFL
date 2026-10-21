from __future__ import annotations

import unittest

from stage3_2_role_agnostic_semantic_merge.round2_aggregate import (
    DEFAULT_BANKS,
    DEFAULT_PATCHES,
    EXPECTED_TOTAL_SKILLS,
    add_upstream_lineage,
    load_local_b2,
)


class Round2AggregationTests(unittest.TestCase):
    def test_frozen_local_b2_inputs_are_complete_and_consistent(self) -> None:
        rows, manifest = load_local_b2(DEFAULT_BANKS, DEFAULT_PATCHES)
        self.assertEqual(len(rows), EXPECTED_TOTAL_SKILLS)
        self.assertEqual({row["source_client"] for row in rows}, {"A", "B", "C"})
        self.assertEqual([manifest[c]["skill_count"] for c in "ABC"], [41, 41, 41])
        self.assertTrue(all(manifest[c]["quota_passed"] for c in "ABC"))

    def test_lineage_is_deterministically_unioned(self) -> None:
        rows = [
            {"source_skill_key": "A/general/G_1", "upstream_source_skill_keys": ["x", "y"]},
            {"source_skill_key": "B/general/G_1", "upstream_source_skill_keys": ["y", "z"]},
        ]
        outputs = [{"type": "Procedure or Local Strategy", "title": "t", "principle": "p", "when_to_apply": "w", "source_skill_keys": ["B/general/G_1", "A/general/G_1"]}]
        enriched = add_upstream_lineage(outputs, rows)
        self.assertEqual(enriched[0]["upstream_source_skill_keys"], ["x", "y", "z"])


if __name__ == "__main__":
    unittest.main()
