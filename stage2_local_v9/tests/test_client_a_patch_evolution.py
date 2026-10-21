from __future__ import annotations

import json
import signal
import tempfile
import time
import unittest
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

from stage2_local_v9.client_a_patch_evolver import (
    EvolutionError,
    TeacherResponseBudgetError,
    allowed_target_ids_by_role,
    call_json_recorded,
    combine_split_patch,
    normalize_known_json_mode_wrapper,
    record_normalization_audit,
    unknown_target_pairs,
    validate_delete_update_stage,
    validate_and_apply_patch,
    validate_family_findings,
)


ROOT = Path(__file__).resolve().parents[2]
B1_PATH = ROOT / "stage2_local_v9/runs/client_a_generation_01_20261013_r1/B1_skillbank.json"


def procedure(title: str) -> dict[str, str]:
    return {
        "type": "Procedure or Local Strategy",
        "title": title,
        "principle": f"Unique test principle for {title}.",
        "when_to_apply": f"Only in the synthetic test case {title}.",
    }


class FakeCompletions:
    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.requests: list[dict] = []

    def create(self, **kwargs: object) -> object:
        self.requests.append(kwargs)
        return self.responses.pop(0)


class FakeConfig:
    model = "deepseek-flash"

    def __init__(self, responses: list[object]) -> None:
        self.completions = FakeCompletions(responses)

    def client(self, timeout: float) -> object:
        return SimpleNamespace(chat=SimpleNamespace(completions=self.completions))


class SlowConfig(FakeConfig):
    def client(self, timeout: float) -> object:
        def create(**kwargs: object) -> object:
            time.sleep(0.2)
            return response('{"findings":[]}', "stop", 8)

        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def response(content: str | None, finish_reason: str = "stop", completion_tokens: int = 10) -> object:
    message = SimpleNamespace(content=content, reasoning_content=None)
    choice = SimpleNamespace(finish_reason=finish_reason, message=message)
    usage = SimpleNamespace(prompt_tokens=100, completion_tokens=completion_tokens, total_tokens=100 + completion_tokens)
    return SimpleNamespace(choices=[choice], usage=usage, model="deepseek-flash")


class ClientAPatchEvolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.parent = json.loads(B1_PATH.read_text(encoding="utf-8"))
        cls.refs = {"evidence:test:001", "evidence:test:002"}

    def test_three_deletes_allow_one_add_across_roles_and_buckets(self) -> None:
        value = {"operations": [
            {"operation": "DELETE", "target_role": "Planner", "target_skill_id": "skill_001", "evidence_refs": ["evidence:test:001"]},
            {"operation": "DELETE", "target_role": "Executor", "target_skill_id": "skill_001", "evidence_refs": ["evidence:test:001"]},
            {"operation": "DELETE", "target_role": "Executor", "target_skill_id": "skill_002", "evidence_refs": ["evidence:test:002"]},
            {"operation": "ADD", "role": "Planner", "bucket": "冷却后放置", "skill": procedure("quota add"), "evidence_refs": ["evidence:test:002"]},
        ]}
        _, operations, counts, by_role = validate_and_apply_patch(value, self.parent, self.refs, 2)
        self.assertEqual(counts, {"base": 46, "delete": 3, "update": 0, "add": 1, "candidate": 44})
        self.assertEqual(by_role, {"Planner": 23, "Executor": 21})
        self.assertRegex(operations[-1]["assigned_skill_id"], r"^skill_\d{3}$")

    def test_two_deletes_do_not_allow_one_add(self) -> None:
        value = {"operations": [
            {"operation": "DELETE", "target_role": "Planner", "target_skill_id": "skill_001", "evidence_refs": ["evidence:test:001"]},
            {"operation": "DELETE", "target_role": "Executor", "target_skill_id": "skill_001", "evidence_refs": ["evidence:test:002"]},
            {"operation": "ADD", "role": "Executor", "bucket": "general", "skill": procedure("forbidden add"), "evidence_refs": ["evidence:test:002"]},
        ]}
        with self.assertRaisesRegex(EvolutionError, "3-delete/1-add violation"):
            validate_and_apply_patch(value, self.parent, self.refs, 2)

    def test_split_base_rejects_add_and_role_local_id_error(self) -> None:
        add = {"operations": [{
            "operation": "ADD", "role": "Planner", "bucket": "general",
            "skill": procedure("early add"), "evidence_refs": ["evidence:test:001"],
        }]}
        with self.assertRaisesRegex(EvolutionError, "DELETE/UPDATE"):
            validate_delete_update_stage(add, self.parent, self.refs, 3)
        unknown = {"operations": [{
            "operation": "DELETE", "target_role": "Planner", "target_skill_id": "skill_999",
            "evidence_refs": ["evidence:test:001"],
        }]}
        with self.assertRaisesRegex(EvolutionError, "unknown target"):
            validate_delete_update_stage(unknown, self.parent, self.refs, 3)

    def test_split_add_is_program_bounded_before_full_validation(self) -> None:
        base = [
            {"operation": "DELETE", "target_role": "Planner", "target_skill_id": "skill_001", "evidence_refs": ["evidence:test:001"]},
            {"operation": "DELETE", "target_role": "Executor", "target_skill_id": "skill_001", "evidence_refs": ["evidence:test:001"]},
            {"operation": "DELETE", "target_role": "Executor", "target_skill_id": "skill_002", "evidence_refs": ["evidence:test:002"]},
        ]
        one_add = {"operations": [{
            "operation": "ADD", "role": "Planner", "bucket": "general",
            "skill": procedure("bounded add"), "evidence_refs": ["evidence:test:002"],
        }]}
        combined = combine_split_patch(base, one_add, 1)
        _, _, counts, _ = validate_and_apply_patch(combined, self.parent, self.refs, 3)
        self.assertEqual((counts["delete"], counts["add"]), (3, 1))
        with self.assertRaisesRegex(EvolutionError, "permits only ADD"):
            combine_split_patch(base, {"operations": [base[0]]}, 1)
        with self.assertRaisesRegex(EvolutionError, "exceeds computed max_add"):
            combine_split_patch(base, {"operations": one_add["operations"] * 2}, 1)

    def test_update_can_move_bucket_and_does_not_require_delete_quota(self) -> None:
        value = {"operations": [{
            "operation": "UPDATE", "target_role": "Planner", "target_skill_id": "skill_001",
            "bucket": "加热后放置", "skill": procedure("moved update"),
            "evidence_refs": ["evidence:test:001"],
        }]}
        candidate, _, counts, by_role = validate_and_apply_patch(value, self.parent, self.refs, 3)
        self.assertEqual(counts, {"base": 46, "delete": 0, "update": 1, "add": 0, "candidate": 46})
        self.assertEqual(by_role, {"Planner": 23, "Executor": 23})
        moved = [row for row in candidate["Planner"]["task_specific"]["加热后放置"] if row["skill_id"] == "skill_001"]
        self.assertEqual(len(moved), 1)
        self.assertEqual(moved[0]["version"], 2)

    def test_unknown_target_and_repeated_target_are_rejected(self) -> None:
        unknown = {"operations": [{
            "operation": "DELETE", "target_role": "Planner", "target_skill_id": "skill_999",
            "evidence_refs": ["evidence:test:001"],
        }]}
        with self.assertRaisesRegex(EvolutionError, "unknown target"):
            validate_and_apply_patch(unknown, self.parent, self.refs, 2)

        repeated = {"operations": [
            {"operation": "DELETE", "target_role": "Planner", "target_skill_id": "skill_001", "evidence_refs": ["evidence:test:001"]},
            {"operation": "UPDATE", "target_role": "Planner", "target_skill_id": "skill_001", "bucket": "general", "skill": procedure("repeat"), "evidence_refs": ["evidence:test:002"]},
        ]}
        with self.assertRaisesRegex(EvolutionError, "modified more than once"):
            validate_and_apply_patch(repeated, self.parent, self.refs, 2)

    def test_target_allowlist_is_role_scoped_when_ids_overlap(self) -> None:
        parent = json.loads(json.dumps(self.parent))
        for bucket, rows in (
            ("general", parent["active_skillbanks"]["Planner"]["general"]),
            *parent["active_skillbanks"]["Planner"]["task_specific"].items(),
        ):
            if bucket == "general":
                parent["active_skillbanks"]["Planner"]["general"] = [
                    row for row in rows if row["skill_id"] != "skill_017"
                ]
            else:
                parent["active_skillbanks"]["Planner"]["task_specific"][bucket] = [
                    row for row in rows if row["skill_id"] != "skill_017"
                ]
        allowlist = allowed_target_ids_by_role(parent)
        self.assertNotIn("skill_017", allowlist["Planner"])
        self.assertIn("skill_017", allowlist["Executor"])
        value = {"operations": [
            {"operation": "DELETE", "target_role": "Planner", "target_skill_id": "skill_017", "evidence_refs": ["evidence:test:001"]},
            {"operation": "UPDATE", "target_role": "Executor", "target_skill_id": "skill_017", "bucket": "general", "skill": procedure("valid executor target"), "evidence_refs": ["evidence:test:002"]},
        ]}
        self.assertEqual(unknown_target_pairs(value, parent), [{
            "operation_number": 1,
            "operation": "DELETE",
            "target_role": "Planner",
            "target_skill_id": "skill_017",
        }])

    def test_evidence_refs_are_generation_local(self) -> None:
        value = {"operations": [{
            "operation": "DELETE", "target_role": "Planner", "target_skill_id": "skill_001",
            "evidence_refs": ["evidence:other-generation"],
        }]}
        with self.assertRaisesRegex(EvolutionError, "belong to this generation"):
            validate_and_apply_patch(value, self.parent, self.refs, 2)

    def test_length_response_is_recorded_then_retried_in_json_mode(self) -> None:
        config = FakeConfig([
            response('{"findings":[', "length", 16000),
            response('{"findings":[]}', "stop", 8),
        ])
        args = Namespace(timeout=1.0, retries=0, truncation_retries=2, seed=1234, max_tokens=16000)
        with tempfile.TemporaryDirectory() as temporary:
            prefix = Path(temporary) / "family_Planner_task_01_schema_01"
            value, record = call_json_recorded(
                config,
                [{"role": "system", "content": "Return JSON."}, {"role": "user", "content": "JSON only."}],
                args,
                prefix,
            )
            files = sorted(Path(temporary).glob("*.json"))
            first = json.loads(files[0].read_text(encoding="utf-8"))
            second = json.loads(files[1].read_text(encoding="utf-8"))
        self.assertEqual(value, {"findings": []})
        self.assertEqual(first["status"], "length_truncated")
        self.assertEqual(first["finish_reason"], "length")
        self.assertEqual(first["usage"]["completion_tokens"], 16000)
        self.assertEqual(first["raw_model_output"], '{"findings":[')
        self.assertEqual(first["requested_max_tokens"], 16000)
        self.assertEqual(second["status"], "parsed")
        self.assertEqual(record["usage"]["response_attempts"], 2)
        self.assertEqual(config.completions.requests[0]["response_format"], {"type": "json_object"})

    def test_empty_choices_are_recorded_and_bounded(self) -> None:
        empty = SimpleNamespace(choices=[], usage=SimpleNamespace(prompt_tokens=50, completion_tokens=0, total_tokens=50), model="deepseek-flash")
        config = FakeConfig([empty, empty, empty])
        args = Namespace(timeout=1.0, retries=0, truncation_retries=2, seed=1234, max_tokens=16000)
        with tempfile.TemporaryDirectory() as temporary:
            prefix = Path(temporary) / "family_Planner_task_01_schema_01"
            with self.assertRaisesRegex(TeacherResponseBudgetError, "after 3 bounded attempts"):
                call_json_recorded(config, [{"role": "user", "content": "Return JSON."}], args, prefix)
            files = sorted(Path(temporary).glob("*.json"))
            records = [json.loads(path.read_text(encoding="utf-8")) for path in files]
        self.assertEqual(len(records), 3)
        self.assertTrue(all(row["status"] == "empty_choices" for row in records))
        self.assertTrue(all(row["choice_count"] == 0 for row in records))
        self.assertTrue(all("finish_reason" in row and "raw_model_output" in row and "usage" in row for row in records))

    def test_family_findings_enforce_text_and_reference_limits(self) -> None:
        valid = {"findings": [{
            "recommendation": "Keep the plan concise.",
            "affected_skill_ids": ["skill_001"],
            "evidence_refs": ["evidence:test:001"],
        }]}
        self.assertEqual(
            validate_family_findings(valid, {"evidence:test:001"}, {"skill_001"}),
            valid["findings"],
        )
        invalid = json.loads(json.dumps(valid))
        invalid["findings"][0]["recommendation"] = "x" * 601
        with self.assertRaisesRegex(EvolutionError, "1-600 characters"):
            validate_family_findings(invalid, {"evidence:test:001"}, {"skill_001"})

    def test_exact_known_json_mode_wrapper_is_normalized_and_audited(self) -> None:
        wrapped = {"type": "json_object", "findings": [{
            "recommendation": "Keep the plan concise.",
            "affected_skill_ids": ["skill_001"],
            "evidence_refs": ["evidence:test:001"],
        }]}
        normalized, audit = normalize_known_json_mode_wrapper(wrapped, "findings")
        self.assertIsNotNone(audit)
        self.assertEqual(set(normalized), {"findings"})
        self.assertEqual(audit["removed_field"], {"type": "json_object"})
        self.assertEqual(
            validate_family_findings(normalized, {"evidence:test:001"}, {"skill_001"}),
            normalized["findings"],
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "response_01.json"
            source.write_text(json.dumps({"raw_model_output": json.dumps(wrapped)}) + "\n", encoding="utf-8")
            record = {"response_attempt_record": str(source)}
            record_normalization_audit(record, audit)
            audit_path = Path(record["normalization_audit_record"])
            saved = json.loads(audit_path.read_text(encoding="utf-8"))
            source_after = json.loads(source.read_text(encoding="utf-8"))
        self.assertEqual(saved["policy"], "remove_exact_known_json_mode_type_wrapper.v1")
        self.assertEqual(source_after["raw_model_output"], json.dumps(wrapped))

    def test_unknown_or_inexact_wrapper_is_not_normalized(self) -> None:
        for value in (
            {"type": "object", "findings": []},
            {"type": "json_object", "schema": "extra", "findings": []},
            {"type": "json_object"},
        ):
            normalized, audit = normalize_known_json_mode_wrapper(value, "findings")
            self.assertIsNone(audit)
            self.assertEqual(normalized, value)
            with self.assertRaisesRegex(EvolutionError, "exactly one findings field"):
                validate_family_findings(normalized, set(), set())

    @unittest.skipUnless(hasattr(signal, "SIGALRM"), "POSIX wall-clock deadline required")
    def test_wall_clock_timeout_is_recorded_as_transport_error(self) -> None:
        config = SlowConfig([])
        args = Namespace(timeout=0.02, retries=0, truncation_retries=2, seed=1234, max_tokens=16000)
        with tempfile.TemporaryDirectory() as temporary:
            prefix = Path(temporary) / "family_Planner_task_01_schema_01"
            with self.assertRaisesRegex(TimeoutError, "exceeded 0.02 seconds"):
                call_json_recorded(config, [{"role": "user", "content": "Return JSON."}], args, prefix)
            files = list(Path(temporary).glob("*.json"))
            record = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(record["status"], "transport_error")
        self.assertEqual(record["error_type"], "TeacherWallClockTimeout")


if __name__ == "__main__":
    unittest.main()
