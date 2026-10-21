from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from client_code.skillbank_loader import EXPECTED_ROLES, TASK_TYPE_LABELS, parse_bank
from stage2_local_v9.capacity_policy import (
    CAPACITY_POLICY_NAME,
    enforce_role_capacity,
    resolve_b1_capacity_policy,
    role_capacity_context,
)
from stage2_local_v9.scripts.client_overlay import (
    ROLE_RULES,
    transformed_evolver_source,
    transformed_phase_source,
)
from stage2_local_v9.scripts.materialize_client_bc_assets import (
    build_empty_bank,
    build_manifest,
    experiment_id,
)
from stage2_local_v9.scripts.materialize_manifest import EXPERIMENT_ID, SOURCE_SHA256, build
from stage2_local_v9.scripts.overlay import FROZEN_SHA256, ROOT, transformed_source


class Stage2LocalV9ProtocolTests(unittest.TestCase):
    def test_frozen_v6_sources_have_expected_hashes(self) -> None:
        for name, expected in FROZEN_SHA256.items():
            path = ROOT / "stage2_local_v6" / "scripts" / f"{name}.py"
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected)

    def test_manifest_reuses_exact_v6_cohorts_with_new_identity(self) -> None:
        v6_path = ROOT / "stage2_local_v6/artifacts/manifests/client_a_generation_01.json"
        self.assertEqual(hashlib.sha256(v6_path.read_bytes()).hexdigest(), SOURCE_SHA256)
        v6 = json.loads(v6_path.read_text(encoding="utf-8"))
        v9 = build()
        self.assertEqual(v9["experiment_id"], EXPERIMENT_ID)
        self.assertEqual(v9["training"], v6["training"])
        self.assertEqual(v9["validation"], v6["validation"])
        self.assertEqual(v9["task_types"], v6["task_types"])

    def test_evolver_replaces_fixed_14_with_b1_derived_capacity(self) -> None:
        source = transformed_source("evolve_client_a_bank")
        self.assertNotIn("Maximum 14 total skills", source)
        self.assertNotIn('"stage": "capacity_repair"', source)
        self.assertNotIn("deterministic_capacity_trim", source)
        self.assertNotIn("exceeded 14-skill cap", source)
        self.assertIn("resolve_b1_capacity_policy", source)
        self.assertIn('"stage": "b1_capacity_repair"', source)
        self.assertIn("fixed B1-derived capacity", source)
        self.assertIn("available_add_slots", source)
        self.assertIn("enforce_role_capacity(value, role, capacity_policy)", source)
        self.assertIn("schema_repair", source)
        self.assertIn('"stage": "deterministic_schema_type_normalization"', source)
        self.assertIn('"stage": "deterministic_schema_field_alias_normalization"', source)
        self.assertIn('alias_row["description"] = principle', source)
        self.assertIn("if len(valid_types) == 1:", source)
        self.assertIn("maximum_skill_field_characters", source)
        self.assertIn('choices=("deepseek_official",)', source)
        compile(source, "v9_evolver", "exec")

    def test_phase_and_controller_only_redirect_to_v9_paths(self) -> None:
        phase = transformed_source("run_client_a_phase")
        controller = transformed_source("run_client_a_to_b5")
        self.assertIn("stage2_local_v9/artifacts/manifests", phase)
        self.assertNotIn("stage2_local_v6/artifacts/manifests", phase)
        self.assertIn('args.phase == "training" and args.generation == 1', phase)
        self.assertIn("stage2_local_v9/runs", controller)
        self.assertNotIn("stage2_local_v6", controller)
        compile(phase, "v9_phase", "exec")
        compile(controller, "v9_controller", "exec")

    def test_generation_one_evolver_accepts_only_the_empty_b0_special_case(self) -> None:
        source = transformed_source("evolve_client_a_bank")
        self.assertIn("if args.generation < 1:", source)
        self.assertIn('if args.generation > 1 and evidence.get("parent_bank_file_sha256")', source)
        self.assertIn("generation {args.generation} requires parent B{args.generation - 1}", source)
        b0 = json.loads((ROOT / "stage2_local_v9/templates/B0_empty_skillbank.json").read_text(encoding="utf-8"))
        self.assertEqual(b0["generation"], 0)
        self.assertEqual(b0["experiment_id"], EXPERIMENT_ID)
        self.assertFalse(b0["active_skillbanks"]["Planner"]["general"])
        self.assertFalse(b0["active_skillbanks"]["Executor"]["general"])

    def test_generation_one_training_writes_null_empty_b0_hashes(self) -> None:
        source = transformed_source("run_client_a_phase")
        self.assertIn('"parent_bank_file_sha256": file_hash(args.bank) if args.bank else None', source)
        self.assertIn(
            '"parent_live_repository_sha256": bank_payload.get("live_repository_sha256") if bank_payload else None',
            source,
        )

    def test_teacher_pause_marker_is_enforced_before_overlay_execution(self) -> None:
        wrapper = (ROOT / "stage2_local_v9/scripts/evolve_client_a_bank.py").read_text(encoding="utf-8")
        pause_index = wrapper.index("pause_marker.exists()")
        execute_index = wrapper.index('execute("evolve_client_a_bank"')
        self.assertLess(pause_index, execute_index)

    def test_spec_declares_the_single_variable(self) -> None:
        spec = json.loads((ROOT / "stage2_local_v9/experiment_spec.json").read_text(encoding="utf-8"))
        self.assertEqual(spec["experiment_id"], EXPERIMENT_ID)
        self.assertIsNone(spec["generation"]["maximum_total_skills_per_role"])
        self.assertFalse(spec["generation"]["capacity_repair"])
        self.assertFalse(spec["generation"]["deterministic_capacity_trim"])
        self.assertEqual(spec["generation"]["maximum_skill_field_characters"], 900)
        self.assertTrue(spec["generation"]["b1_open_ended_capacity"])
        self.assertEqual(spec["generation"]["b2_plus_capacity_policy"], "fixed_per_role_from_b1")
        self.assertTrue(spec["generation"]["b2_plus_capacity_anchor_does_not_shrink_after_delete"])
        self.assertEqual(spec["generation"]["b2_plus_capacity_repair"], "teacher_only_without_mechanical_trim")
        self.assertTrue(spec["validation"]["task_cohorts_identical_to_v6"])
        self.assertFalse(spec["isolation"]["old_skillbanks_used_as_parent"])
        self.assertTrue(spec["launch_guard"]["formal_run_authorized"])
        self.assertFalse(spec["launch_guard"]["b2_plus_run_authorized"])
        self.assertIn("D-093", spec["launch_guard"]["reason"])
        self.assertIn("B2-B5 transitions remain paused", spec["launch_guard"]["reason"])
        self.assertTrue(spec["launch_guard"]["teacher_provider_schedule_frozen"])
        self.assertEqual(spec["models"]["teacher"]["applies_to_generations"], [1, 2, 3, 4, 5])
        self.assertEqual(spec["launch_guard"]["teacher_provider_schedule"], "B1-B5: deepseek_official/deepseek-flash")

    def test_client_bc_manifests_reuse_the_exact_frozen_cohorts(self) -> None:
        base = build()
        for client in ("B", "C"):
            manifest = build_manifest(client)
            self.assertEqual(manifest["experiment_id"], experiment_id(client))
            self.assertEqual(manifest["target_client"], client)
            self.assertEqual(manifest["training"], base["training"])
            self.assertEqual(manifest["validation"], base["validation"])
            self.assertEqual(manifest["task_types"], base["task_types"])

    def test_client_bc_empty_b0_has_exact_role_schema(self) -> None:
        for client in ("B", "C"):
            bank = build_empty_bank(client)
            parse_bank(bank, client)
            self.assertEqual(tuple(bank["active_skillbanks"]), EXPECTED_ROLES[client])
            for repository in bank["active_skillbanks"].values():
                self.assertFalse(repository["general"])
                self.assertTrue(all(not rows for rows in repository["task_specific"].values()))

    def test_client_bc_phase_overlays_bind_the_correct_runtime_and_identity(self) -> None:
        for client in ("B", "C"):
            lower = client.lower()
            source = transformed_phase_source(client)
            self.assertIn(f"alfworld_client_{lower}.py", source)
            self.assertIn(f"client_{lower}_generation_01.json", source)
            self.assertIn(f'FIXED_ARGS["{client}"]', source)
            self.assertIn(f'build_adapter(bank_payload, "{client}"', source)
            self.assertIn(f'"client_id": "{client}"', source)
            self.assertNotIn("alfworld_client_a.py", source)
            compile(source, f"v9_client_{lower}_phase", "exec")

    def test_client_bc_teacher_overlays_use_role_specific_boundaries(self) -> None:
        for client in ("B", "C"):
            source = transformed_evolver_source(client)
            self.assertIn(f'ROLES = EXPECTED_ROLES["{client}"]', source)
            self.assertIn(f'evidence.get("client_id") != "{client}"', source)
            self.assertIn(f'parse_bank(bank, "{client}")', source)
            self.assertNotIn("Maximum 14 total skills", source)
            self.assertNotIn('"stage": "capacity_repair"', source)
            self.assertIn('"stage": "b1_capacity_repair"', source)
            for rule in ROLE_RULES[client].values():
                self.assertIn(rule, source)
            compile(source, f"v9_client_{client.lower()}_evolver", "exec")

    @staticmethod
    def _repository(count: int) -> dict:
        return {
            "general": [{} for _ in range(count)],
            "task_specific": {label: [] for label in TASK_TYPE_LABELS.values()},
        }

    def test_b1_is_open_and_b2_derives_per_role_capacity(self) -> None:
        parent = {
            "active_skillbanks": {
                "Planner": self._repository(3),
                "Executor": self._repository(5),
            }
        }
        self.assertIsNone(resolve_b1_capacity_policy(parent, 1, ("Planner", "Executor"), "sha256:b0"))
        policy = resolve_b1_capacity_policy(parent, 2, ("Planner", "Executor"), "sha256:b1")
        self.assertEqual(policy["policy"], CAPACITY_POLICY_NAME)
        self.assertEqual(policy["anchor_bank_file_sha256"], "sha256:b1")
        self.assertEqual(policy["role_capacities"], {"Planner": 3, "Executor": 5})
        self.assertEqual(
            role_capacity_context(policy, "Planner", self._repository(2)),
            {"maximum_total_skills": 3, "parent_skill_count": 2, "available_add_slots": 1},
        )

    def test_b3_inherits_b1_capacity_even_after_delete(self) -> None:
        b1 = {
            "active_skillbanks": {
                "Planner": self._repository(3),
                "Executor": self._repository(5),
            }
        }
        policy = resolve_b1_capacity_policy(b1, 2, ("Planner", "Executor"), "sha256:b1")
        b2 = {
            "capacity_policy": policy,
            "active_skillbanks": {
                "Planner": self._repository(1),
                "Executor": self._repository(4),
            },
        }
        inherited = resolve_b1_capacity_policy(b2, 3, ("Planner", "Executor"), "sha256:b2")
        self.assertEqual(inherited, policy)
        self.assertEqual(role_capacity_context(inherited, "Planner", b2["active_skillbanks"]["Planner"])["available_add_slots"], 2)
        self.assertEqual(enforce_role_capacity(self._repository(3), "Planner", inherited), 3)
        with self.assertRaisesRegex(RuntimeError, "exceeded frozen B1 capacity"):
            enforce_role_capacity(self._repository(4), "Planner", inherited)

    def test_bc_controller_excludes_validation_from_teacher_and_stops_at_b1(self) -> None:
        source = (ROOT / "stage2_local_v9/scripts/run_client_to_b1.py").read_text(encoding="utf-8")
        self.assertIn('"stage_order": ["B0_validation", "B0_training", "B1_teacher", "B1_validation"]', source)
        self.assertIn('"--evidence", str(b0_training / "evidence.json")', source)
        self.assertIn('"teacher_evidence_policy": "B0_training/evidence.json only; validation excluded"', source)
        self.assertIn('"stopped_after": "B1_validation"', source)
        self.assertNotIn("B2", source)

    def test_client_bc_explicit_cohort_runs_every_requested_game(self) -> None:
        expectations = {
            "b": "games_to_run = len(candidates) if requested_game_files else args.games_per_type",
            "c": "games_to_run = len(candidates) if requested else args.games_per_type",
        }
        for client, marker in expectations.items():
            source = (ROOT / f"client_code/alfworld_client_{client}.py").read_text(encoding="utf-8")
            self.assertIn(marker, source)
            self.assertIn("for _ in range(games_to_run):", source)

    def test_bc_controller_resume_requires_frozen_prefix_and_reuses_complete_outputs(self) -> None:
        source = (ROOT / "stage2_local_v9/scripts/run_client_to_b1.py").read_text(encoding="utf-8")
        self.assertIn('parser.add_argument("--resume", action="store_true")', source)
        self.assertIn('"--resume-partial", "--resume-order-reference"', source)
        self.assertIn('if summary_path.is_file():', source)
        self.assertIn('if bank.exists() != record.exists():', source)
        self.assertIn('"order_reference_file_sha256": file_hash(args.resume_order_reference)', source)


if __name__ == "__main__":
    unittest.main()
