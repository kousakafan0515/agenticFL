from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from stage2_local_v10.scripts.repair_global3_cooling_principle import (
    BUCKET, REPLACEMENT, compress_one_field, prepare,
)
from stage3_2_role_agnostic_semantic_merge.round1_aggregate import (
    AggregationError, bucket_inputs, parse_json_object, validate_model_output,
)


ROOT = Path(__file__).resolve().parents[1] / "runs/two_local_global3_20261018_r1/globals/Global3/aggregation"


class Global3CoolingRepairTests(unittest.TestCase):
    def test_frozen_attempt_has_one_error_and_only_target_field_changes(self) -> None:
        rows = json.loads((ROOT / "uploaded_local_b3.json").read_text(encoding="utf-8"))["skills"]
        inputs = bucket_inputs(rows, BUCKET)
        attempt = json.loads((ROOT / "buckets/task_05.attempt_03.json").read_text(encoding="utf-8"))
        original = parse_json_object(attempt["raw_model_output"])
        updated, errors = compress_one_field(original, inputs)
        self.assertEqual(errors, ["skills[3].principle exceeds 900 characters"])
        self.assertEqual(len(original["skills"][2]["principle"]), 952)
        self.assertEqual(updated["skills"][2]["principle"], REPLACEMENT)
        restored = copy.deepcopy(updated)
        restored["skills"][2]["principle"] = original["skills"][2]["principle"]
        self.assertEqual(restored, original)
        self.assertEqual(validate_model_output(updated, inputs)[1], [])

    def test_overlong_replacement_is_rejected(self) -> None:
        rows = json.loads((ROOT / "uploaded_local_b3.json").read_text(encoding="utf-8"))["skills"]
        inputs = bucket_inputs(rows, BUCKET)
        attempt = json.loads((ROOT / "buckets/task_05.attempt_03.json").read_text(encoding="utf-8"))
        with self.assertRaisesRegex(AggregationError, "bounded compression"):
            compress_one_field(parse_json_object(attempt["raw_model_output"]), inputs, "x" * 901)

    def test_frozen_inputs_and_attempts_are_locked(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            target = Path(name)
            shutil.copy2(ROOT / "input_manifest.json", target)
            shutil.copy2(ROOT / "uploaded_local_b3.json", target)
            bucket_dir = target / "buckets"
            bucket_dir.mkdir()
            for path in (ROOT / "buckets").glob("*.accepted.json"):
                if path.name != "task_05.accepted.json":
                    shutil.copy2(path, bucket_dir)
            for path in (ROOT / "buckets").glob("task_05.attempt_*.json"):
                shutil.copy2(path, bucket_dir)
            audit, repaired, record = prepare(target)
            self.assertTrue(audit["full_validation_passed"])
            self.assertEqual(len(repaired["skills"]), 4)
            self.assertEqual(record["manual_repair_scope"], "skills[3].principle_only")
            (bucket_dir / "task_05.record.json").write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(AggregationError, "refusing to overwrite"):
                prepare(target)


if __name__ == "__main__":
    unittest.main()
