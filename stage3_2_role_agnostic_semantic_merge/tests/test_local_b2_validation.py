from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from client_code.skillbank_loader import EXPECTED_ROLES, parse_bank
from stage3_2_role_agnostic_semantic_merge.local_b2_validation import materialize_client


ROOT = Path(__file__).resolve().parents[2]


class LocalB2ValidationTests(unittest.TestCase):
    def test_materialized_runtime_roles_receive_identical_complete_b2(self) -> None:
        source_root = ROOT / "stage3_2_role_agnostic_semantic_merge/runs/v9_global1_to_local_b2_20261014_r1"
        with tempfile.TemporaryDirectory(dir=ROOT / "stage3_2_role_agnostic_semantic_merge/tests") as directory:
            for client in ("A", "B", "C"):
                destination = Path(directory) / f"client_{client}.json"
                record = materialize_client(source_root / f"client_{client}/B2_skillbank.json", client, destination)
                bank = json.loads(destination.read_text(encoding="utf-8"))
                self.assertEqual(record["logical_skill_count"], 41)
                self.assertEqual(len(parse_bank(bank, client)), 41 * len(EXPECTED_ROLES[client]))
                repositories = [bank["active_skillbanks"][role] for role in EXPECTED_ROLES[client]]
                self.assertTrue(all(repository == repositories[0] for repository in repositories[1:]))
                self.assertTrue(bank["capacity_policy"]["quota_passed"])


if __name__ == "__main__":
    unittest.main()
