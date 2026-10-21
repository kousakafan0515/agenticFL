"""Display-only English companions for the frozen V10 B1-B6/Global1-3 banks.

Never writes to a run directory. Only six semantic skill-text fields are
translated; IDs, bucket keys, lineage, metadata and structure stay intact.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "stage2_local_v10/runs/two_local_global3_20261018_r1"
SEED = ROOT / "stage2_local_v10/runs/imported_v9_b0_to_b1_20261018_r1"
DEFAULT_OUT = ROOT / "stage2_local_v10/artifacts/english_skillbank_reference_20261019_r1"
PRE_POSTEDIT_MAP_SHA = "sha256:469c07c8528c4456a156d4cca714256c96455bf8661920ed9aa90e8635bfa132"
TEXT_FIELDS = {"title", "principle", "when_to_apply", "description", "why_it_happens", "how_to_avoid"}
HAN = re.compile(r"[\u4e00-\u9fff]")
TASK_EN = {
    "简单取放": "Simple pick-and-place", "台灯观察": "Examine with desk lamp",
    "清洗后放置": "Clean then place", "加热后放置": "Heat then place",
    "冷却后放置": "Cool then place", "双物品放置": "Place two objects",
}
BATCH_SIZE = 15


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def write_new(path: Path, value: Any) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_map(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def source_files() -> list[Path]:
    return (
        [SEED / f"client_{c}/B1_skillbank.json" for c in "ABC"]
        + [RUN / f"locals/B{g}/client_{c}/B{g}_skillbank.json" for g in range(2, 7) for c in "ABC"]
        + [RUN / f"globals/Global{g}/aggregation/global_skillbank{g}.json" for g in range(1, 4)]
        + [RUN / f"globals/Global{g}/validation/client_{c}/replacement_skillbank.json" for g in range(1, 4) for c in "ABC"]
    )


def walk_text(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in TEXT_FIELDS and isinstance(child, str) and HAN.search(child):
                yield child
            else:
                yield from walk_text(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_text(child)


def plan(out: Path) -> dict[str, Any]:
    if out.exists() and any(out.iterdir()):
        raise RuntimeError("English reference output already exists; use translate/check/materialize")
    files = source_files()
    if len(files) != 30 or any(not path.is_file() for path in files):
        raise RuntimeError("expected 30 frozen V10 SkillBanks")
    unique: dict[str, str] = {}
    file_rows = []
    for path in files:
        document = json.loads(path.read_text(encoding="utf-8"))
        texts = list(walk_text(document))
        for value in texts:
            unique.setdefault(value, f"T{len(unique)+1:04d}")
        file_rows.append({"source": path.relative_to(ROOT).as_posix(), "source_sha256": sha(path), "chinese_text_occurrences": len(texts)})
    entries = [{"id": ident, "original": original, "english": None} for original, ident in unique.items()]
    manifest = {
        "schema_version": "v10.english_reference.v1", "display_only": True,
        "source_run": RUN.relative_to(ROOT).as_posix(),
        "scope": "B1-B6 A/B/C, Global1-3 server and A/B/C replacement copies",
        "translation_model": "deepseek-flash", "translation_endpoint": "https://api.deepseek.com",
        "translated_fields": sorted(TEXT_FIELDS), "preserved": "all IDs, bucket keys, source refs, metadata and JSON structure",
        "source_files": file_rows, "unique_chinese_text_count": len(entries),
        "translation_batches": [[entry["id"] for entry in entries[i:i+BATCH_SIZE]] for i in range(0, len(entries), BATCH_SIZE)],
    }
    write_new(out / "source_manifest.json", manifest)
    write_new(out / "translation_map.json", {"entries": entries})
    return manifest


def load_locked(out: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = json.loads((out / "source_manifest.json").read_text(encoding="utf-8"))
    mapping = json.loads((out / "translation_map.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "v10.english_reference.v1" or manifest.get("display_only") is not True:
        raise RuntimeError("reference manifest identity mismatch")
    if [row["source"] for row in manifest["source_files"]] != [path.relative_to(ROOT).as_posix() for path in source_files()]:
        raise RuntimeError("reference source list changed")
    for row in manifest["source_files"]:
        if sha(ROOT / row["source"]) != row["source_sha256"]:
            raise RuntimeError(f"frozen source changed: {row['source']}")
    entries = mapping["entries"]
    if len(entries) != manifest["unique_chinese_text_count"] or len({x["original"] for x in entries}) != len(entries):
        raise RuntimeError("translation map count or uniqueness mismatch")
    expected = [[entry["id"] for entry in entries[i:i+BATCH_SIZE]] for i in range(0, len(entries), BATCH_SIZE)]
    if manifest["translation_batches"] != expected:
        raise RuntimeError("translation batch plan changed")
    return manifest, mapping


def validate_batch(raw: str, ids: list[str]) -> dict[str, str]:
    value = json.loads(raw)
    if set(value) != {"translations"} or not isinstance(value["translations"], list):
        raise ValueError("response must contain only translations list")
    rows = value["translations"]
    if len(rows) != len(ids):
        raise ValueError("translation count mismatch")
    found = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "english"}:
            raise ValueError("translation row schema mismatch")
        ident, english = row["id"], row["english"]
        if not isinstance(ident, str) or ident in found or not isinstance(english, str) or not english.strip() or HAN.search(english) or len(english) > 1800:
            raise ValueError(f"invalid English text or duplicate ID: {ident!r}")
        found[ident] = english.strip()
    if set(found) != set(ids):
        raise ValueError("translation ID coverage mismatch")
    return found


def translate(out: Path) -> None:
    manifest, mapping = load_locked(out)
    if os.environ.get("STAGE3_AGGREGATION_BASE_URL", "").rstrip("/") != "https://api.deepseek.com" or not os.environ.get("STAGE3_AGGREGATION_API_KEY"):
        raise RuntimeError("official DeepSeek credentials are required")
    from openai import OpenAI

    client = OpenAI(api_key=os.environ["STAGE3_AGGREGATION_API_KEY"], base_url="https://api.deepseek.com", timeout=120)
    by_id = {row["id"]: row for row in mapping["entries"]}
    for batch_index, ids in enumerate(manifest["translation_batches"], 1):
        if all(by_id[ident]["english"] is not None for ident in ids):
            continue
        if any(by_id[ident]["english"] is not None for ident in ids):
            raise RuntimeError(f"partial translation batch {batch_index}")
        payload = [{"id": ident, "text": by_id[ident]["original"]} for ident in ids]
        system = (
            "Translate Chinese or mixed Chinese-English ALFWorld skill text into faithful, concise English for a display-only comparison. "
            "Keep all operational meaning, conditionals, negations, object IDs, placeholders, command syntax and quoted error messages. "
            "Do not add facts or advice. Preserve existing English terms where useful. Output a JSON object only: "
            "{\"translations\":[{\"id\":\"same input ID\",\"english\":\"English translation\"}]}. "
            "Return every ID exactly once. No Chinese characters in english values."
        )
        user = json.dumps({"items": payload}, ensure_ascii=False)
        attempt_dir = out / "api_attempts"
        attempt_dir.mkdir(exist_ok=True)
        errors = []
        # Batch 14 exhausted its original three 5,000-token attempts in
        # thinking mode; keep them and allow one explicitly audited recovery.
        max_attempts = 4 if batch_index == 14 else 3
        for attempt_index in range(1, max_attempts + 1):
            attempt_path = attempt_dir / f"batch_{batch_index:03d}.attempt_{attempt_index:02d}.json"
            if attempt_path.exists():
                record = json.loads(attempt_path.read_text(encoding="utf-8"))
                if record.get("input_ids") != ids:
                    raise RuntimeError("existing batch attempt has different input IDs")
                raw = record["raw_response"]
            else:
                response = client.chat.completions.create(
                    model="deepseek-flash", temperature=0, max_tokens=5000,
                    response_format={"type": "json_object"},
                    extra_body={"thinking": {"type": "disabled"}},
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user + ("\nPrior validation errors: " + json.dumps(errors) if errors else "")}],
                )
                if not response.choices:
                    raise RuntimeError("DeepSeek returned empty choices")
                choice = response.choices[0]
                raw = choice.message.content or ""
                record = {
                    "batch": batch_index, "attempt": attempt_index, "input_ids": ids,
                    "input_text_sha256": "sha256:" + hashlib.sha256(user.encode("utf-8")).hexdigest(),
                    "raw_response": raw, "finish_reason": choice.finish_reason,
                    "thinking_mode": "disabled",
                    "usage": response.usage.model_dump() if response.usage else None,
                    "model": response.model, "provider": "deepseek_official",
                }
                write_new(attempt_path, record)
            try:
                if record.get("finish_reason") == "length":
                    raise ValueError("response truncated")
                translated = validate_batch(raw, ids)
            except (ValueError, json.JSONDecodeError) as exc:
                errors = [str(exc)]
                continue
            for ident in ids:
                by_id[ident]["english"] = translated[ident]
            save_map(out / "translation_map.json", mapping)
            print(f"batch {batch_index}/{len(manifest['translation_batches'])}: {len(ids)} translations", flush=True)
            break
        else:
            raise RuntimeError(f"batch {batch_index} failed after {max_attempts} audited attempts: {errors}")


def postedit(out: Path) -> dict[str, Any]:
    """Fix only the audited 'use use desklamp' translation artifact."""
    _, mapping = load_locked(out)
    map_path = out / "translation_map.json"
    if sha(map_path) != PRE_POSTEDIT_MAP_SHA:
        raise RuntimeError("completed model translation map hash mismatch")
    audit_path = out / "postedit_audit.json"
    if audit_path.exists():
        raise RuntimeError("postedit audit already exists")
    changes = []
    for row in mapping["entries"]:
        old = row["english"]
        if "use use desklamp" not in old:
            continue
        new = old.replace("use use desklamp", "execute the command use desklamp")
        row["english"] = new
        changes.append({"id": row["id"], "original_model_translation": old, "edited_translation": new,
                        "reason": "remove duplicated English use while preserving the literal use desklamp command"})
    if len(changes) != 15:
        raise RuntimeError(f"unexpected command duplication count: {len(changes)}")
    audit = {"display_only": True, "pre_edit_translation_map_sha256": PRE_POSTEDIT_MAP_SHA,
             "exact_replacement": {"from": "use use desklamp", "to": "execute the command use desklamp"},
             "changed_count": len(changes), "changes": changes}
    write_new(audit_path, audit)
    save_map(map_path, mapping)
    return {"changed_count": len(changes), "postedit_audit_sha256": sha(audit_path),
            "translation_map_sha256": sha(map_path)}


def replace_text(value: Any, translations: dict[str, str], key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {k: replace_text(v, translations, k) for k, v in value.items()}
    if isinstance(value, list):
        return [replace_text(v, translations, key) for v in value]
    if key in TEXT_FIELDS and isinstance(value, str) and HAN.search(value):
        return translations[value]
    return copy.deepcopy(value)


def verify_only_text_changed(source: Any, target: Any, key: str | None = None) -> int:
    if isinstance(source, dict):
        if not isinstance(target, dict) or list(source) != list(target):
            raise RuntimeError("reference JSON structure or keys changed")
        return sum(verify_only_text_changed(source[k], target[k], k) for k in source)
    if isinstance(source, list):
        if not isinstance(target, list) or len(source) != len(target):
            raise RuntimeError("reference JSON list changed")
        return sum(verify_only_text_changed(a, b, key) for a, b in zip(source, target))
    if key in TEXT_FIELDS and isinstance(source, str) and HAN.search(source):
        if not isinstance(target, str) or not target.strip() or HAN.search(target):
            raise RuntimeError("untranslated or invalid English skill text")
        return 1
    if source != target:
        raise RuntimeError(f"non-text field changed: {key}")
    return 0


def iter_skills(document: dict[str, Any]):
    banks = document.get("active_skillbanks")
    if isinstance(banks, dict):
        for role, bank in banks.items():
            for item in bank["general"]:
                yield role, "general", item
            for bucket, rows in bank["task_specific"].items():
                for item in rows:
                    yield role, bucket, item
    else:
        for item in document["general"]:
            yield "Global", "general", item
        for bucket, rows in document["task_specific"].items():
            for item in rows:
                yield "Global", bucket, item


def render_view(document: dict[str, Any], source: str) -> str:
    lines = [f"# English reference: {Path(source).name}", "", "Display only. Original IDs, buckets, and source references are preserved. This file was not used in any run.", ""]
    current = None
    for role, bucket, item in iter_skills(document):
        section = (role, bucket)
        if section != current:
            lines.extend([f"## {role} — {TASK_EN.get(bucket, 'General' if bucket == 'general' else bucket)}", ""])
            current = section
        ident = item.get("skill_id", item.get("global_skill_id", "unknown"))
        lines.extend([f"### {ident}: {item.get('title', item.get('type', 'Skill'))}", ""])
        for field in ("principle", "when_to_apply", "description", "why_it_happens", "how_to_avoid"):
            if field in item:
                lines.extend([f"**{field.replace('_', ' ').title()}:** {item[field]}", ""])
    return "\n".join(lines)


def materialize(out: Path) -> dict[str, Any]:
    manifest, mapping = load_locked(out)
    if any(not isinstance(row["english"], str) or not row["english"].strip() or HAN.search(row["english"]) for row in mapping["entries"]):
        raise RuntimeError("translation map incomplete")
    translations = {row["original"]: row["english"] for row in mapping["entries"]}
    output_rows = []
    for row in manifest["source_files"]:
        source_path = ROOT / row["source"]
        source = json.loads(source_path.read_text(encoding="utf-8"))
        target = replace_text(source, translations)
        changed = verify_only_text_changed(source, target)
        if changed != row["chinese_text_occurrences"]:
            raise RuntimeError("translated field count mismatch")
        relative = Path(row["source"])
        json_path = out / "banks" / relative.parent / (relative.stem + ".reference.en.json")
        view_path = out / "views" / relative.parent / (relative.stem + ".reference.en.md")
        write_new(json_path, target)
        if view_path.exists():
            raise RuntimeError(f"refusing to overwrite {view_path}")
        view_path.parent.mkdir(parents=True, exist_ok=True)
        view_path.write_text(render_view(target, row["source"]), encoding="utf-8")
        output_rows.append({"source": row["source"], "source_sha256": row["source_sha256"],
                            "reference_json": json_path.relative_to(out).as_posix(), "reference_json_sha256": sha(json_path),
                            "english_view": view_path.relative_to(out).as_posix(), "english_view_sha256": sha(view_path),
                            "translated_field_occurrences": changed})
    final = {"display_only": True, "source_manifest_sha256": sha(out / "source_manifest.json"),
             "translation_map_sha256": sha(out / "translation_map.json"),
             "postedit_audit_sha256": sha(out / "postedit_audit.json"), "files": output_rows}
    write_new(out / "output_manifest.json", final)
    lines = ["# V10 SkillBank English reference", "", "Display only. These translations were never fed to Planner, Executor, Teacher, aggregation, or evaluation. All frozen source files remain unchanged.", "", "Only the six semantic Skill text fields were translated. Role names, IDs, bucket keys and source references stay byte-equivalent for comparison; the Markdown views show English task-family headings.", "", "| Stage | Client A | Client B | Client C |", "|---|---|---|---|"]
    for g in range(1, 7):
        cells = []
        for c in "ABC":
            suffix = f"client_{c}/B1_skillbank.json" if g == 1 else f"locals/B{g}/client_{c}/B{g}_skillbank.json"
            match = next(row for row in output_rows if row["source"].endswith(suffix))
            cells.append(f"[English view]({match['english_view']}) · [JSON]({match['reference_json']})")
        lines.append(f"| B{g}{' (imported v9 seed)' if g == 1 else ''} | " + " | ".join(cells) + " |")
    lines.extend(["", "| Global | Server bank | Downlink A | Downlink B | Downlink C |", "|---|---|---|---|---|"])
    for g in range(1, 4):
        suffixes = [f"globals/Global{g}/aggregation/global_skillbank{g}.json"] + [f"globals/Global{g}/validation/client_{c}/replacement_skillbank.json" for c in "ABC"]
        cells = []
        for suffix in suffixes:
            match = next(row for row in output_rows if row["source"].endswith(suffix))
            cells.append(f"[English view]({match['english_view']}) · [JSON]({match['reference_json']})")
        lines.append(f"| Global{g} | " + " | ".join(cells) + " |")
    lines.extend(["", "The exact original/reference hashes are in [output_manifest.json](output_manifest.json); unique translations and API attempts are retained in translation_map.json and api_attempts/.", ""])
    (out / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")
    return final


def check(out: Path) -> dict[str, Any]:
    manifest, mapping = load_locked(out)
    output = json.loads((out / "output_manifest.json").read_text(encoding="utf-8"))
    if not output.get("display_only") or output["source_manifest_sha256"] != sha(out / "source_manifest.json") or output["translation_map_sha256"] != sha(out / "translation_map.json") or output["postedit_audit_sha256"] != sha(out / "postedit_audit.json"):
        raise RuntimeError("output manifest provenance mismatch")
    if len(output["files"]) != len(manifest["source_files"]):
        raise RuntimeError("translated bank count mismatch")
    for row in output["files"]:
        if sha(out / row["reference_json"]) != row["reference_json_sha256"] or sha(out / row["english_view"]) != row["english_view_sha256"]:
            raise RuntimeError("translated output changed")
        source = json.loads((ROOT / row["source"]).read_text(encoding="utf-8"))
        target = json.loads((out / row["reference_json"]).read_text(encoding="utf-8"))
        if verify_only_text_changed(source, target) != row["translated_field_occurrences"]:
            raise RuntimeError("translated output structural mismatch")
    return {"bank_count": len(output["files"]), "unique_translations": len(mapping["entries"]), "translated_field_occurrences": sum(row["translated_field_occurrences"] for row in output["files"])}


def comparison_index(out: Path) -> dict[str, int]:
    output = json.loads((out / "output_manifest.json").read_text(encoding="utf-8"))
    rows = output["files"]
    lines = ["# Original and English SkillBanks", "", "All English files are display-only. Original source files and IDs are unchanged.", "", "| Stage / source | Original JSON | English reading view | English JSON |", "|---|---|---|---|"]
    for row in rows:
        path = Path(row["source"])
        parts = path.parts
        if "imported_v9_b0_to_b1_20261018_r1" in parts:
            label = f"B1 imported seed / {path.parent.name}"
        elif "locals" in parts:
            label = f"{parts[parts.index('locals')+1]} / {path.parent.name}"
        else:
            generation = parts[parts.index("globals")+1]
            label = f"{generation} / " + ("server" if "aggregation" in parts else path.parent.name)
        original = (ROOT / row["source"]).as_posix()
        lines.append(f"| {label} | [Original]({original}) | [English view]({row['english_view']}) | [English JSON]({row['reference_json']}) |")
    target = out / "ORIGINAL_AND_ENGLISH.md"
    if target.exists():
        raise RuntimeError("refusing to overwrite comparison index")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"paired_banks": len(rows)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("plan", "translate", "postedit", "materialize", "check", "comparison"))
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    result = {"plan": plan, "translate": translate, "postedit": postedit, "materialize": materialize, "check": check, "comparison": comparison_index}[args.phase](args.output_root)
    if result is not None:
        print(json.dumps(result if args.phase != "plan" else {"source_files": len(result["source_files"]), "unique_chinese_text_count": result["unique_chinese_text_count"], "batches": len(result["translation_batches"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
