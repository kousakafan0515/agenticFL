from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from stage3_2_role_agnostic_semantic_merge.federated_round_aggregate import load_local_banks
from stage3_2_role_agnostic_semantic_merge.run_global_to_local import logical_repository, materialize_local_runtime


ROOT = Path(__file__).resolve().parents[2]
CURRENT = ROOT / "stage3_2_role_agnostic_semantic_merge/runs/v9_global2_to_local_b3_20261015_r1"


class FederatedToGlobal5Tests(unittest.TestCase):
    def test_three_complete_b3_banks_are_full_uploads(self) -> None:
        banks = {c: CURRENT / f"client_{c}/B3_skillbank.json" for c in "ABC"}
        validations = {c: CURRENT / f"client_{c}/B3_validation/summary.json" for c in "ABC"}
        if not all(path.is_file() for path in (*banks.values(), *validations.values())):
            self.skipTest("live B/C B3 validations are not complete yet")
        rows, manifest = load_local_banks(banks, validations, 3)
        self.assertEqual(len(rows), 126)
        self.assertEqual([manifest[c]["skill_count"] for c in "ABC"], [42, 42, 42])
        self.assertTrue(all(manifest[c]["capacity_policy"]["quota_passed"] for c in "ABC"))

    def test_global_runtime_count_is_dynamic(self) -> None:
        parent = ROOT / "stage3_2_role_agnostic_semantic_merge/runs/v9_global2_client_validation_20261015_r1/client_A/replacement_skillbank.json"
        value = json.loads(parent.read_text(encoding="utf-8"))
        repository = logical_repository(value, "A", 44)
        self.assertEqual(len(repository["general"]) + sum(map(len, repository["task_specific"].values())), 44)
        with self.assertRaisesRegex(RuntimeError, "45"):
            logical_repository(value, "A", 45)

    def test_materialize_local_runtime_preserves_quota_audit(self) -> None:
        source = CURRENT / "client_A/B3_skillbank.json"
        if not source.is_file():
            self.skipTest("frozen Client A B3 is unavailable")
        temp_parent = ROOT / "stage3_2_role_agnostic_semantic_merge/.tmp"
        temp_parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_parent) as directory:
            destination = Path(directory) / "runtime.json"
            runtime = materialize_local_runtime(source, "A", destination, 3, 44, "test")
            self.assertTrue(runtime["capacity_policy"]["quota_passed"])
            self.assertEqual(runtime["generation"], 3)
            self.assertTrue(destination.is_file())


if __name__ == "__main__":
    unittest.main()
