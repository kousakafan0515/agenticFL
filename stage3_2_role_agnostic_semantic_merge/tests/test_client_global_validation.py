from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from client_code.skillbank_loader import BLIND_GLOBAL_RENDERER_VERSION, EXPECTED_ROLES, parse_bank
from originalFL.runtime_adapter import build_adapter
from stage3_2_role_agnostic_semantic_merge.client_global_validation import (
    EXPECTED_GLOBAL_SKILLS,
    ReplacementError,
    load_global,
    materialize,
    materialize_client,
    normalize_sha256,
)


class ClientGlobalReplacementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.global_bank = {
            "live_global_hash": "sha256:test",
            "general": [{
                "global_skill_id": "G_001",
                "type": "Procedure or Local Strategy",
                "title": "General",
                "principle": "Use observations.",
                "when_to_apply": "Always.",
                "source_skill_keys": ["A/Planner/general/skill_001"],
            }] * 11,
            "task_specific": {},
        }
        # Give every repeated fixture row a unique ID while preserving the 43-skill layout.
        self.global_bank["general"] = [
            {**row, "global_skill_id": f"G_{index:03d}"}
            for index, row in enumerate(self.global_bank["general"], 1)
        ]
        counts = (1, 5, 6, 7, 5, 8)
        labels = ("简单取放", "台灯观察", "清洗后放置", "加热后放置", "冷却后放置", "双物品放置")
        for family, (label, count) in enumerate(zip(labels, counts), 1):
            self.global_bank["task_specific"][label] = [{
                "global_skill_id": f"T{family}_{index:03d}",
                "type": "Failure Lesson",
                "title": "Display title",
                "description": "Avoid an unsupported action.",
                "why_it_happens": "The state is incompatible.",
                "how_to_avoid": "Inspect and adjust first.",
                "source_skill_keys": [f"B/Executor/{label}/skill_{index:03d}"],
            } for index in range(1, count + 1)]
        self.assertEqual(
            len(self.global_bank["general"]) + sum(map(len, self.global_bank["task_specific"].values())),
            EXPECTED_GLOBAL_SKILLS,
        )

    def test_every_role_receives_the_same_complete_repository(self) -> None:
        temp_parent = Path(__file__).resolve().parents[1] / ".tmp"
        temp_parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_parent) as directory:
            for client in ("A", "B", "C"):
                path = Path(directory) / client / "replacement.json"
                record = materialize_client(self.global_bank, client, path)
                bank = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(len(parse_bank(bank, client)), EXPECTED_GLOBAL_SKILLS * len(EXPECTED_ROLES[client]))
                repositories = list(bank["active_skillbanks"].values())
                self.assertTrue(all(repository == repositories[0] for repository in repositories[1:]))
                self.assertEqual(record["logical_global_skill_count"], EXPECTED_GLOBAL_SKILLS)
                for repository in repositories:
                    failure = repository["task_specific"]["简单取放"][0]
                    self.assertNotIn("title", failure)
                adapter = build_adapter(bank, client, Path(directory) / client / "adapter")
                profile = json.loads(Path(adapter["capacity_profile"]).read_text(encoding="utf-8"))
                self.assertEqual(profile["renderer_version"], BLIND_GLOBAL_RENDERER_VERSION)

    def test_frozen_global2_can_be_materialized_as_complete_replacement(self) -> None:
        global2 = Path(__file__).resolve().parents[1] / "runs" / "v9_local_b2_round2_20261014_r1" / "global_skillbank2.json"
        temp_parent = Path(__file__).resolve().parents[1] / ".tmp"
        temp_parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_parent) as directory:
            output = Path(directory) / "global2"
            manifest = materialize(
                global2,
                output,
                expected_sha256="7ea48b556110d7ac1524a091b45396f81f590eb0367be11ba0e16e9cb7e1954d",
                expected_skills=44,
                expected_round_index=2,
                experiment_id="v9-global2-client-validation-test",
                generation=2,
            )
            self.assertEqual(manifest["logical_global_skill_count"], 44)
            for client in "ABC":
                bank = json.loads((output / f"client_{client}" / "replacement_skillbank.json").read_text(encoding="utf-8"))
                self.assertEqual(bank["generation"], 2)
                self.assertEqual(len(parse_bank(bank, client)), 44 * len(EXPECTED_ROLES[client]))

    def test_sha256_normalization_accepts_bare_or_single_prefix_only(self) -> None:
        digest = "a" * 64
        self.assertEqual(normalize_sha256(digest), digest)
        self.assertEqual(normalize_sha256("sha256:" + digest), digest)
        with self.assertRaisesRegex(ReplacementError, "invalid SHA-256"):
            normalize_sha256("sha256:sha256:" + digest)
        with self.assertRaisesRegex(ReplacementError, "invalid SHA-256"):
            normalize_sha256("not-a-digest")

    def test_load_global_accepts_prefixed_expected_hash(self) -> None:
        global2 = Path(__file__).resolve().parents[1] / "runs" / "v9_local_b2_round2_20261014_r1" / "global_skillbank2.json"
        digest = "7ea48b556110d7ac1524a091b45396f81f590eb0367be11ba0e16e9cb7e1954d"
        value = load_global(global2, expected_sha256="sha256:" + digest, expected_skills=44, expected_round_index=2)
        self.assertEqual(value["round_index"], 2)


if __name__ == "__main__":
    unittest.main()
