from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from stage2_local_v10.scripts.create_chinese_reference import (
    DEFAULT_OUT, check, load_locked, materialize, replace_text, source_files,
    validate_batch, verify_only_text_changed,
)


class ChineseReferenceTests(unittest.TestCase):
    def test_exact_response_ids_and_chinese_text(self) -> None:
        raw = json.dumps({"translations": [{"id": "Z0001", "chinese": "先清洗物品。"}]})
        self.assertEqual(validate_batch(raw, ["Z0001"]), {"Z0001": "先清洗物品。"})
        with self.assertRaises(ValueError):
            validate_batch(raw, ["Z0002"])
        with self.assertRaises(ValueError):
            validate_batch(json.dumps({"translations": [{"id": "Z0001", "chinese": "Clean the object first."}]}), ["Z0001"])

    def test_only_english_semantic_text_changes(self) -> None:
        source = {"skill_id": "G_001", "bucket": "清洗后放置", "source_skill_keys": ["A/Planner/G_001"],
                  "title": "先清洗", "principle": "Clean the soapbar with the sinkbasin first."}
        target = replace_text(source, {"Clean the soapbar with the sinkbasin first.": "先在洗手池清洗肥皂。"})
        self.assertEqual(verify_only_text_changed(source, target), 1)
        self.assertEqual(target["title"], source["title"])
        self.assertEqual(target["source_skill_keys"], source["source_skill_keys"])
        target["skill_id"] = "G_002"
        with self.assertRaisesRegex(RuntimeError, "non-translated field changed"):
            verify_only_text_changed(source, target)

    def test_locked_scope_and_offline_materialization(self) -> None:
        self.assertEqual(len(source_files()), 30)
        manifest, mapping = load_locked(DEFAULT_OUT)
        self.assertEqual(manifest["unique_english_text_count"], 774)
        self.assertEqual(len(mapping["entries"]), 774)
        with tempfile.TemporaryDirectory() as name:
            out = Path(name)
            shutil.copy2(DEFAULT_OUT / "source_manifest.json", out)
            for row in mapping["entries"]:
                row["chinese"] = f"仅供离线结构测试的中文译文 {row['id']}。"
            (out / "translation_map.json").write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")
            materialize(out)
            verified = check(out)
            self.assertEqual(verified["bank_count"], 30)
            self.assertEqual(verified["unique_translations"], 774)
            self.assertEqual(verified["translated_field_occurrences"], 5493)


if __name__ == "__main__":
    unittest.main()
