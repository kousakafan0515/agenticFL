from __future__ import annotations

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from client_code.skillbank_loader import TASK_TYPE_LABELS
from originalFL.banks import file_hash, write_json
from stage2_local_v10.bootstrap_b1 import v10_source
from stage2_local_v10.downlink import expected_bank, materialize
from stage2_local_v10.import_v9_b1 import verify_import, verify_imported_seed
from stage2_local_v10.role_evolver import SCHEMA, combine_adds, evolve, role_patch
from stage2_local_v10.server_aggregate import load_initial_uploads, load_role_uploads
from stage3_2_role_agnostic_semantic_merge.local_round2_evolver import EvolutionError


LABELS = tuple(TASK_TYPE_LABELS.values())


def skill(index: int) -> dict:
    return {
        "skill_id": f"G_{index:03d}", "version": 1,
        "type": "Procedure or Local Strategy", "title": f"Rule {index}",
        "principle": f"Check object state {index} before the next action.",
        "when_to_apply": f"When situation {index} is observed.",
        "source_skill_keys": [f"upstream/{index}"],
    }


def repository() -> dict:
    return {"general": [skill(i) for i in range(1, 5)], "task_specific": {label: [] for label in LABELS}}


def ref_op(operation: str, role: str, target: str) -> dict:
    return {"operation": operation, "target_role": role, "target_skill_id": target, "evidence_refs": ["episode_001"]}


class V10ProtocolTests(unittest.TestCase):
    def test_frozen_v9_b1_import_is_explicitly_labelled_and_usable(self) -> None:
        root = Path(__file__).resolve().parents[1] / "runs" / "imported_v9_b0_to_b1_20261018_r1"
        banks, validations = {}, {}
        for client in "ABC":
            client_root = root / f"client_{client}"
            imported = verify_import(client_root, client)
            self.assertEqual(imported["classification"], "imported_v9_seed_not_native_v10_B1")
            self.assertEqual(imported["non_add_candidate_count"], 0)
            banks[client] = client_root / "B1_skillbank.json"
            validations[client] = client_root / "B1_validation" / "summary.json"
            verify_imported_seed(banks[client], validations[client], client)
        rows, manifest = load_initial_uploads(banks, validations)
        self.assertEqual(len(rows), 151)
        self.assertTrue(all(entry["origin_kind"] == "imported_v9_seed_not_native_v10_B1" for entry in manifest.values()))

    def test_b0_bootstrap_prompts_add_only_for_all_clients(self) -> None:
        for client in "ABC":
            source = v10_source(client)
            compile(source, f"v10_{client}", "exec")
            self.assertIn("Propose 0-4 evidence-grounded ADD candidates only", source)
            self.assertIn("B0 candidate must be ADD with no parent IDs", source)
            self.assertNotIn('"action": "ADD | UPDATE | MERGE | RETAIN | DELETE"', source)

    def test_role_quota_cannot_be_borrowed(self) -> None:
        base = repository()
        refs = {"episode_001"}
        planner = {"operations": [ref_op("DELETE", "Planner", f"G_{i:03d}") for i in (1, 2, 3)]}
        result, _, counts = role_patch(base, "Planner", planner, refs, "A", 2)
        self.assertEqual(counts["delete"], 3)
        self.assertEqual(counts["candidate"], 1)
        self.assertEqual(len(result["general"]), 1)
        add = {"operation": "ADD", "role": "Executor", "bucket": "general", "skill": {key: value for key, value in skill(99).items() if key in {"type", "title", "principle", "when_to_apply"}}, "evidence_refs": ["episode_001"]}
        with self.assertRaisesRegex(EvolutionError, "exceeds floor"):
            role_patch(base, "Executor", {"operations": [add]}, refs, "A", 2)

    def test_split_stage_and_exact_quota(self) -> None:
        base = repository()
        refs = {"episode_001"}
        deletes = [ref_op("DELETE", "Planner", f"G_{i:03d}") for i in (1, 2, 3)]
        add = {"operation": "ADD", "role": "Planner", "bucket": LABELS[0], "skill": {key: value for key, value in skill(99).items() if key in {"type", "title", "principle", "when_to_apply"}}, "evidence_refs": ["episode_001"]}
        _, frozen, counts = role_patch(base, "Planner", {"operations": deletes}, refs, "A", 2, allowed_operations={"DELETE", "UPDATE"})
        combined = combine_adds(frozen, {"operations": [add]}, counts["delete"] // 3)
        result, _, final = role_patch(base, "Planner", combined, refs, "A", 2)
        self.assertEqual((final["base"], final["delete"], final["add"], final["candidate"]), (4, 3, 1, 2))
        self.assertEqual(len(result["task_specific"][LABELS[0]]), 1)
        with self.assertRaisesRegex(EvolutionError, "ADD stage"):
            combine_adds(frozen, {"operations": [add, add]}, 1)

    def test_role_id_and_evidence_are_hard_checked(self) -> None:
        with self.assertRaisesRegex(EvolutionError, "target role mismatch"):
            role_patch(repository(), "Planner", {"operations": [ref_op("DELETE", "Executor", "G_001")]}, {"episode_001"}, "A", 2)
        bad = ref_op("DELETE", "Planner", "G_001")
        bad["evidence_refs"] = ["made_up"]
        with self.assertRaisesRegex(EvolutionError, "evidence refs"):
            role_patch(repository(), "Planner", {"operations": [bad]}, {"episode_001"}, "A", 2)

    def test_server_accepts_role_uploads_and_preserves_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            banks, validations = {}, {}
            roles_by_client = {"A": ("Planner", "Executor"), "B": ("Executor", "Critic"), "C": ("Supervisor", "Search Worker", "Operation Worker")}
            for client, roles in roles_by_client.items():
                bank_path, validation_path = root / f"{client}.json", root / client / "summary.json"
                write_json(bank_path, {"schema_version": SCHEMA, "client": client, "source_client": client, "target_client": client, "generation": 2, "active_skillbanks": {role: repository() for role in roles}, "capacity_policy": {"scope": "per_role_per_round", "quota_passed": True, "per_role": {role: {"base": 4, "delete": 0, "update": 0, "add": 0, "candidate": 4, "quota_passed": True} for role in roles}}})
                write_json(validation_path, {"status": "complete", "client": client, "generation": 2, "phase": "validation", "task_count": 134, "api_clean": True})
                write_json(validation_path.parent / "source_lock.json", {"bank_file_sha256": file_hash(bank_path)})
                banks[client], validations[client] = bank_path, validation_path
            rows, manifest = load_role_uploads(banks, validations, 2)
            self.assertEqual(len(rows), 4 * 7)
            self.assertEqual(len({row["source_skill_key"] for row in rows}), len(rows))
            self.assertEqual(manifest["C"]["uploaded_role_skill_instances"], 12)

    def test_shared_teacher_pipeline_evolves_each_role_separately(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent_path, evidence_path = root / "B1.json", root / "evidence.json"
            write_json(parent_path, {"bank_schema_version": "v10.test", "source_client": "A", "target_client": "A", "generation": 1, "active_skillbanks": {role: repository() for role in ("Planner", "Executor")}})
            episodes = [{"evidence_ref": f"episode_{index:03d}", "task_type_id": (index - 1) % 6 + 1, "goal": "Test", "success": False, "environment_events": [], "role_evidence": {}} for index in range(1, 135)]
            write_json(evidence_path, {"client_id": "A", "generation": 2, "episodes": episodes, "parent_bank_file_sha256": file_hash(parent_path)})
            args = Namespace(client="A", generation=2, parent_kind="independent", parent_bank=parent_path, evidence=evidence_path, output=root / "B2.json", patch_output=root / "B2_patch.json", record_output=root / "B2_teacher.json", experiment_id="v10-offline-test", seed=1234, max_tokens=16000, timeout=240.0, retries=0, truncation_retries=0, schema_attempts=3)

            class FakeConfig:
                model = "deepseek-flash"
                def descriptor(self):
                    return {"provider": "deepseek_official", "endpoint_origin": "https://api.deepseek.com"}

            def fake_teacher(_config, prompt, _system, _args, _prefix, expected):
                if expected == "findings":
                    return {"findings": []}, {"raw_model_output": '{"findings":[]}'}
                if prompt.get("max_add") is not None:
                    add = {"operation": "ADD", "role": "Planner", "bucket": LABELS[0], "skill": {key: value for key, value in skill(99).items() if key in {"type", "title", "principle", "when_to_apply"}}, "evidence_refs": ["episode_001"]}
                    return {"operations": [add]}, {"raw_model_output": '{"operations":[]}'}
                if prompt["role"] == "Planner":
                    return {"operations": [ref_op("DELETE", "Planner", f"G_{i:03d}") for i in (1, 2, 3)]}, {"raw_model_output": '{"operations":[]}'}
                return {"operations": []}, {"raw_model_output": '{"operations":[]}'}

            with patch("stage2_local_v10.role_evolver._local_evolution_config", return_value=FakeConfig()), patch("stage2_local_v10.role_evolver._call_and_check", side_effect=fake_teacher) as calls:
                result = evolve(args)
            self.assertEqual(result["status"], "complete")
            bank = json.loads(args.output.read_text(encoding="utf-8"))
            self.assertEqual(bank["capacity_policy"]["per_role"]["Planner"]["candidate"], 2)
            self.assertEqual(bank["capacity_policy"]["per_role"]["Executor"]["candidate"], 4)
            self.assertEqual(sum(call.args[5] == "findings" for call in calls.call_args_list), 12)
            self.assertEqual(sum(call.args[4].name.startswith("add_") for call in calls.call_args_list), 1)

    def test_downlink_replaces_every_role_with_identical_global_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            global_path, output = root / "global.json", root / "client_C.json"
            global_row = {"global_skill_id": "G_001", **{key: value for key, value in skill(1).items() if key in {"type", "title", "principle", "when_to_apply", "source_skill_keys"}}}
            write_json(global_path, {"schema_version": "stage3_2.role_agnostic_semantic_global.v1", "v10_protocol": "role_partitioned_local_to_role_agnostic_global.v1", "experiment_id": "v10-offline-test", "round_index": 2, "general": [global_row], "task_specific": {label: [] for label in LABELS}})
            result = materialize(global_path, output, "C", 2, file_hash(global_path), "v10-offline-test")
            bank = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(result["skills_per_role"], 1)
            self.assertEqual(len(bank["active_skillbanks"]), 3)
            self.assertEqual(len({json.dumps(repo, sort_keys=True) for repo in bank["active_skillbanks"].values()}), 1)
            self.assertEqual(bank, expected_bank(global_path, "C", 2, file_hash(global_path), "v10-offline-test"))
            bank["active_skillbanks"]["Supervisor"]["general"][0]["title"] = "Tampered"
            self.assertNotEqual(bank, expected_bank(global_path, "C", 2, file_hash(global_path), "v10-offline-test"))
            with self.assertRaisesRegex(RuntimeError, "v10 Global protocol"):
                expected_bank(global_path, "C", 2, file_hash(global_path), "different-experiment")

    def test_initial_server_has_no_frozen_151_skill_assumption(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            banks, validations = {}, {}
            role_sets = {"A": ("Planner", "Executor"), "B": ("Executor", "Critic"), "C": ("Supervisor", "Search Worker", "Operation Worker")}
            for client, roles in role_sets.items():
                bank_path, summary_path = root / f"{client}_B1.json", root / client / "summary.json"
                write_json(bank_path, {"bank_schema_version": "patchFL.role_repository.v3", "experiment_id": "stage2-local-v10-role-partitioned-patch3", "source_client": client, "target_client": client, "generation": 1, "active_skillbanks": {role: repository() for role in roles}})
                write_json(summary_path, {"status": "complete", "client": client, "generation": 1, "phase": "validation", "task_count": 134, "api_clean": True})
                write_json(summary_path.parent / "source_lock.json", {"bank_file_sha256": file_hash(bank_path)})
                banks[client], validations[client] = bank_path, summary_path
            rows, manifest = load_initial_uploads(banks, validations)
            self.assertEqual(len(rows), 28)
            self.assertEqual(sum(entry["uploaded_role_skill_instances"] for entry in manifest.values()), 28)


if __name__ == "__main__":
    unittest.main()
