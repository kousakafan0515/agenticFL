from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from stage2_local_v10.scripts.create_english_reference import (
    DEFAULT_OUT, check, load_locked, materialize, replace_text, source_files,
    validate_batch, verify_only_text_changed,
)


class EnglishReferenceTests(unittest.TestCase):
    def test_exact_response_ids_and_english_only(self) -> None:
        raw = json.dumps({"translations": [{"id": "T0001", "english": "Clean the object first."}]})
        self.assertEqual(validate_batch(raw, ["T0001"]), {"T0001": "Clean the object first."})
        with self.assertRaises(ValueError):
            validate_batch(raw, ["T0002"])
        with self.assertRaises(ValueError):
            validate_batch(json.dumps({"translations": [{"id": "T0001", "english": "清洗物品"}]}), ["T0001"])

    def test_only_semantic_text_can_change(self) -> None:
        source = {"skill_id": "G_001", "bucket": "清洗后放置", "source_skill_keys": ["A/Planner/清洗后放置/G_001"], "title": "先清洗", "principle": "Keep the original command: clean soapbar 1 with sinkbasin 1."}
        target = replace_text(source, {"先清洗": "Clean first."})
        self.assertEqual(verify_only_text_changed(source, target), 1)
        self.assertEqual(target["source_skill_keys"], source["source_skill_keys"])
        target["skill_id"] = "G_002"
        with self.assertRaisesRegex(RuntimeError, "non-text field changed"):
            verify_only_text_changed(source, target)

    def test_frozen_v10_scope_is_30_banks(self) -> None:
        self.assertEqual(len(source_files()), 30)
        self.assertTrue(all(path.is_file() for path in source_files()))
        manifest, mapping = load_locked(DEFAULT_OUT)
        self.assertEqual(manifest["unique_chinese_text_count"], 295)
        self.assertEqual(len(mapping["entries"]), 295)

    def test_complete_display_only_materialization_preserves_structure(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            out = Path(name)
            shutil.copy2(DEFAULT_OUT / "source_manifest.json", out)
            shutil.copy2(DEFAULT_OUT / "postedit_audit.json", out)
            mapping = json.loads((DEFAULT_OUT / "translation_map.json").read_text(encoding="utf-8"))
            for row in mapping["entries"]:
                row["english"] = f"English reading reference for {row['id']}."
            (out / "translation_map.json").write_text(json.dumps(mapping, ensure_ascii=False), encoding="utf-8")
            materialize(out)
            verified = check(out)
            self.assertEqual(verified["bank_count"], 30)
            self.assertEqual(verified["unique_translations"], 295)
            self.assertEqual(verified["translated_field_occurrences"], 1700)


if __name__ == "__main__":
    unittest.main()
