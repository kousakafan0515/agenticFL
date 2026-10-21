"""Create display-only Chinese companions for the frozen V10 SkillBanks.

Only six semantic Skill text fields can change. The original experiment inputs
and the pre-existing English reference are read-only inputs to this script.
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

from .create_english_reference import ROOT, TEXT_FIELDS, iter_skills, sha, source_files, write_new


ENGLISH_REFERENCE = ROOT / "stage2_local_v10/artifacts/english_skillbank_reference_20261019_r1"
DEFAULT_OUT = ROOT / "stage2_local_v10/artifacts/chinese_skillbank_reference_20261019_r1"
HAN = re.compile(r"[\u4e00-\u9fff]")
BATCH_SIZE = 20
TASK_ZH = {"general": "通用", "简单取放": "简单取放", "台灯观察": "台灯观察",
           "清洗后放置": "清洗后放置", "加热后放置": "加热后放置",
           "冷却后放置": "冷却后放置", "双物品放置": "双物品放置"}
ROLE_ZH = {"Planner": "规划者", "Executor": "执行者", "Critic": "评估者",
           "Supervisor": "监督者", "Search Worker": "搜索者",
           "Operation Worker": "操作者", "Global": "全局"}
FIELD_ZH = {"principle": "原则", "when_to_apply": "适用条件", "description": "问题描述",
            "why_it_happens": "原因", "how_to_avoid": "避免方法"}
TYPE_ZH = {"Failure Lesson": "失败教训", "Procedure or Local Strategy": "流程或局部策略"}


def save_map(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def walk_text(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in TEXT_FIELDS and isinstance(child, str):
                yield child
            else:
                yield from walk_text(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_text(child)


def plan(out: Path) -> dict[str, Any]:
    if out.exists() and any(out.iterdir()):
        raise RuntimeError(f"refusing to plan into occupied directory: {out}")
    english_manifest = ENGLISH_REFERENCE / "source_manifest.json"
    source_lock = json.loads(english_manifest.read_text(encoding="utf-8"))
    paths = source_files()
    if len(paths) != 30 or [p.relative_to(ROOT).as_posix() for p in paths] != [r["source"] for r in source_lock["source_files"]]:
        raise RuntimeError("30-file V10 source list differs from the English reference")
    unique: dict[str, str] = {}
    rows = []
    for path, locked in zip(paths, source_lock["source_files"]):
        if sha(path) != locked["source_sha256"]:
            raise RuntimeError(f"frozen source changed: {path}")
        texts = list(walk_text(json.loads(path.read_text(encoding="utf-8"))))
        for value in texts:
            if not HAN.search(value):
                unique.setdefault(value, f"Z{len(unique)+1:04d}")
        rows.append({"source": locked["source"], "source_sha256": locked["source_sha256"],
                     "skill_text_occurrences": len(texts),
                     "english_only_occurrences": sum(not HAN.search(t) for t in texts)})
    entries = [{"id": ident, "original": original, "chinese": None} for original, ident in unique.items()]
    manifest = {"schema_version": "v10.chinese_reference.v1", "display_only": True,
                "english_reference_source_manifest_sha256": sha(english_manifest),
                "translation_model": "deepseek-flash", "translation_endpoint": "https://api.deepseek.com",
                "translated_fields": sorted(TEXT_FIELDS),
                "preserved": "IDs, bucket keys, provenance, metadata, JSON structure and all already-Chinese skill text",
                "source_files": rows, "unique_english_text_count": len(entries),
                "translation_batches": [[r["id"] for r in entries[i:i+BATCH_SIZE]]
                                        for i in range(0, len(entries), BATCH_SIZE)]}
    write_new(out / "source_manifest.json", manifest)
    write_new(out / "translation_map.json", {"entries": entries})
    return manifest


def load_locked(out: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = json.loads((out / "source_manifest.json").read_text(encoding="utf-8"))
    mapping = json.loads((out / "translation_map.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "v10.chinese_reference.v1" or manifest.get("display_only") is not True:
        raise RuntimeError("Chinese reference manifest identity mismatch")
    if sha(ENGLISH_REFERENCE / "source_manifest.json") != manifest["english_reference_source_manifest_sha256"]:
        raise RuntimeError("English reference source lock changed")
    if [r["source"] for r in manifest["source_files"]] != [p.relative_to(ROOT).as_posix() for p in source_files()]:
        raise RuntimeError("source list changed")
    for row in manifest["source_files"]:
        if sha(ROOT / row["source"]) != row["source_sha256"]:
            raise RuntimeError(f"frozen source changed: {row['source']}")
    entries = mapping["entries"]
    if len(entries) != manifest["unique_english_text_count"] or len({r["original"] for r in entries}) != len(entries):
        raise RuntimeError("translation map count or uniqueness mismatch")
    expected = [[r["id"] for r in entries[i:i+BATCH_SIZE]] for i in range(0, len(entries), BATCH_SIZE)]
    if expected != manifest["translation_batches"]:
        raise RuntimeError("translation batches changed")
    return manifest, mapping


def validate_batch(raw: str, ids: list[str]) -> dict[str, str]:
    response = json.loads(raw)
    if not isinstance(response, dict) or set(response) != {"translations"} or not isinstance(response["translations"], list):
        raise ValueError("response must have only a translations list")
    rows = response["translations"]
    if len(rows) != len(ids):
        raise ValueError("translation count mismatch")
    found = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"id", "chinese"}:
            raise ValueError("translation row schema mismatch")
        ident, chinese = row["id"], row["chinese"]
        if not isinstance(ident, str) or ident in found or not isinstance(chinese, str) or not chinese.strip() or not HAN.search(chinese) or len(chinese) > 2000:
            raise ValueError(f"invalid Chinese translation or duplicate ID: {ident!r}")
        found[ident] = chinese.strip()
    if set(found) != set(ids):
        raise ValueError("translation ID coverage mismatch")
    return found


def translate(out: Path) -> None:
    manifest, mapping = load_locked(out)
    if os.environ.get("STAGE3_AGGREGATION_BASE_URL", "").rstrip("/") != "https://api.deepseek.com" or not os.environ.get("STAGE3_AGGREGATION_API_KEY"):
        raise RuntimeError("official DeepSeek credentials are required")
    from openai import OpenAI
    client = OpenAI(api_key=os.environ["STAGE3_AGGREGATION_API_KEY"], base_url="https://api.deepseek.com", timeout=180)
    by_id = {r["id"]: r for r in mapping["entries"]}
    for batch_index, ids in enumerate(manifest["translation_batches"], 1):
        if all(by_id[i]["chinese"] is not None for i in ids):
            continue
        if any(by_id[i]["chinese"] is not None for i in ids):
            raise RuntimeError(f"partial batch {batch_index}")
        payload = [{"id": i, "text": by_id[i]["original"]} for i in ids]
        system = (
            "你正在制作仅供人阅读的 ALFWorld SkillBank 中文对照版。将每段英文 Skill 正文准确译成简洁、自然的简体中文。"
            "保留条件、否定、操作顺序、对象编号与占位符；被引号、反引号包住的环境原话、命令模板和动作语法须原样保留。"
            "常见游戏动作如 take、put、open、close、go to、use、look、examine 可在中文解释中保留原命令。"
            "不要增加规则或事实。只输出 JSON：{\"translations\":[{\"id\":\"原ID\",\"chinese\":\"中文译文\"}]}。"
            "每个输入 ID 恰好出现一次，每个译文应含中文。"
        )
        user = json.dumps({"items": payload}, ensure_ascii=False)
        errors = []
        for attempt_index in range(1, 4):
            attempt_path = out / "api_attempts" / f"batch_{batch_index:03d}.attempt_{attempt_index:02d}.json"
            if attempt_path.exists():
                record = json.loads(attempt_path.read_text(encoding="utf-8"))
                if record.get("input_ids") != ids:
                    raise RuntimeError("attempt input IDs changed")
                raw = record["raw_response"]
            else:
                response = client.chat.completions.create(
                    model="deepseek-flash", temperature=0, max_tokens=8500,
                    response_format={"type": "json_object"},
                    extra_body={"thinking": {"type": "disabled"}},
                    messages=[{"role": "system", "content": system},
                              {"role": "user", "content": user + ("\n之前的格式校验错误：" + json.dumps(errors, ensure_ascii=False) if errors else "")}],
                )
                choice = response.choices[0] if response.choices else None
                raw = (choice.message.content or "") if choice else ""
                record = {"batch": batch_index, "attempt": attempt_index, "input_ids": ids,
                          "input_text_sha256": "sha256:" + hashlib.sha256(user.encode("utf-8")).hexdigest(),
                          "raw_response": raw, "finish_reason": choice.finish_reason if choice else "empty_choices",
                          "usage": response.usage.model_dump() if response.usage else None,
                          "model": response.model, "provider": "deepseek_official", "request_max_tokens": 8500}
                write_new(attempt_path, record)
            try:
                if record["finish_reason"] in ("length", "empty_choices"):
                    raise ValueError(f"response {record['finish_reason']}")
                translated = validate_batch(raw, ids)
            except (ValueError, json.JSONDecodeError) as exc:
                errors = [str(exc)]
                continue
            for ident in ids:
                by_id[ident]["chinese"] = translated[ident]
            save_map(out / "translation_map.json", mapping)
            print(f"batch {batch_index}/{len(manifest['translation_batches'])}: {len(ids)} translations", flush=True)
            break
        else:
            raise RuntimeError(f"batch {batch_index} failed after 3 audited attempts: {errors}")


def replace_text(value: Any, translations: dict[str, str], key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {k: replace_text(v, translations, k) for k, v in value.items()}
    if isinstance(value, list):
        return [replace_text(v, translations, key) for v in value]
    if key in TEXT_FIELDS and isinstance(value, str) and not HAN.search(value):
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
    if key in TEXT_FIELDS and isinstance(source, str) and not HAN.search(source):
        if not isinstance(target, str) or not HAN.search(target):
            raise RuntimeError("English-only Skill field has no Chinese translation")
        return 1
    if source != target:
        raise RuntimeError(f"non-translated field changed: {key}")
    return 0


def render_view(document: dict[str, Any], source: str) -> str:
    lines = [f"# 中文阅读版：{Path(source).name}", "", "仅供阅读；原始 Skill ID、任务类别及来源信息保持不变，未参与任何实验。", ""]
    current = None
    for role, bucket, item in iter_skills(document):
        section = (role, bucket)
        if section != current:
            lines.extend([f"## {ROLE_ZH.get(role, role)}（{role}）· {TASK_ZH.get(bucket, bucket)}", ""])
            current = section
        ident = item.get("skill_id", item.get("global_skill_id", "unknown"))
        title = item.get("title") or TYPE_ZH.get(item.get("type"), item.get("type", "技能"))
        lines.extend([f"### {ident}：{title}", ""])
        for field in ("principle", "when_to_apply", "description", "why_it_happens", "how_to_avoid"):
            if field in item:
                lines.extend([f"**{FIELD_ZH[field]}：** {item[field]}", ""])
    return "\n".join(lines)


def materialize(out: Path) -> dict[str, Any]:
    manifest, mapping = load_locked(out)
    if any(not isinstance(r["chinese"], str) or not HAN.search(r["chinese"]) for r in mapping["entries"]):
        raise RuntimeError("translation map incomplete")
    translations = {r["original"]: r["chinese"] for r in mapping["entries"]}
    rows = []
    for locked in manifest["source_files"]:
        source = json.loads((ROOT / locked["source"]).read_text(encoding="utf-8"))
        target = replace_text(source, translations)
        changed = verify_only_text_changed(source, target)
        if changed != locked["english_only_occurrences"]:
            raise RuntimeError("translation occurrence count mismatch")
        relative = Path(locked["source"])
        json_path = out / "banks" / relative.parent / (relative.stem + ".reference.zh.json")
        view_path = out / "views" / relative.parent / (relative.stem + ".reference.zh.md")
        write_new(json_path, target)
        if view_path.exists():
            raise RuntimeError(f"refusing to overwrite {view_path}")
        view_path.parent.mkdir(parents=True, exist_ok=True)
        view_path.write_text(render_view(target, locked["source"]), encoding="utf-8")
        rows.append({"source": locked["source"], "source_sha256": locked["source_sha256"],
                     "reference_json": json_path.relative_to(out).as_posix(), "reference_json_sha256": sha(json_path),
                     "chinese_view": view_path.relative_to(out).as_posix(), "chinese_view_sha256": sha(view_path),
                     "translated_field_occurrences": changed})
    result = {"display_only": True, "source_manifest_sha256": sha(out / "source_manifest.json"),
              "translation_map_sha256": sha(out / "translation_map.json"), "files": rows}
    write_new(out / "output_manifest.json", result)
    lines = ["# V10 全版本 SkillBank 中文阅读版", "", "只供阅读；未用于规划、执行、Teacher、聚合或评价。原始 SkillBank 和英文对照版未改动。",
             "", "B0 为空库，没有可阅读的 Skill。B1 是从 v9 导入的冻结种子；B2–B6、Global1–3 是 V10 正式结果。",
             "", "仅翻译六个 Skill 正文字段中原本不含中文的文本。ID、原任务类别键、来源和元数据保持原样；环境命令及对象名可保留英文以便与原文对照。", "",
             "| 代次 | Client A | Client B | Client C |", "|---|---|---|---|"]
    for generation in range(1, 7):
        cells = []
        for client in "ABC":
            suffix = f"client_{client}/B1_skillbank.json" if generation == 1 else f"locals/B{generation}/client_{client}/B{generation}_skillbank.json"
            row = next(r for r in rows if r["source"].endswith(suffix))
            cells.append(f"[中文阅读]({row['chinese_view']}) · [中文对照JSON]({row['reference_json']})")
        lines.append(f"| B{generation}{'（v9导入）' if generation == 1 else ''} | " + " | ".join(cells) + " |")
    lines.extend(["", "| 聚合轮次 | 服务器库 | 下发 A | 下发 B | 下发 C |", "|---|---|---|---|---|"])
    for generation in range(1, 4):
        suffixes = [f"globals/Global{generation}/aggregation/global_skillbank{generation}.json"] + [f"globals/Global{generation}/validation/client_{client}/replacement_skillbank.json" for client in "ABC"]
        cells = []
        for suffix in suffixes:
            row = next(r for r in rows if r["source"].endswith(suffix))
            cells.append(f"[中文阅读]({row['chinese_view']}) · [中文对照JSON]({row['reference_json']})")
        lines.append(f"| Global{generation} | " + " | ".join(cells) + " |")
    lines.extend(["", "逐文件原文与译本哈希见 [output_manifest.json](output_manifest.json)；逐段译文见 [translation_map.json](translation_map.json)；原始模型响应及用量见 api_attempts/。", ""])
    write_text_new(out / "INDEX.md", "\n".join(lines))
    return result


def write_text_new(path: Path, content: str) -> None:
    if path.exists():
        raise RuntimeError(f"refusing to overwrite {path}")
    path.write_text(content, encoding="utf-8")


def check(out: Path) -> dict[str, int]:
    manifest, mapping = load_locked(out)
    output = json.loads((out / "output_manifest.json").read_text(encoding="utf-8"))
    if not output.get("display_only") or output["source_manifest_sha256"] != sha(out / "source_manifest.json") or output["translation_map_sha256"] != sha(out / "translation_map.json"):
        raise RuntimeError("output manifest provenance mismatch")
    if len(output["files"]) != len(manifest["source_files"]):
        raise RuntimeError("bank count mismatch")
    for row in output["files"]:
        if sha(out / row["reference_json"]) != row["reference_json_sha256"] or sha(out / row["chinese_view"]) != row["chinese_view_sha256"]:
            raise RuntimeError("reference output changed")
        source = json.loads((ROOT / row["source"]).read_text(encoding="utf-8"))
        target = json.loads((out / row["reference_json"]).read_text(encoding="utf-8"))
        if verify_only_text_changed(source, target) != row["translated_field_occurrences"]:
            raise RuntimeError("reference output structural mismatch")
        if any(not HAN.search(text) for text in walk_text(target)):
            raise RuntimeError("English-only Skill text remains in Chinese reference")
    return {"bank_count": len(output["files"]), "unique_translations": len(mapping["entries"]),
            "translated_field_occurrences": sum(r["translated_field_occurrences"] for r in output["files"])}


def localize_view_labels(out: Path) -> dict[str, int]:
    """Update only guarded Markdown headings; JSON banks and sources stay fixed."""
    load_locked(out)
    manifest_path = out / "output_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    changes = []
    for row in manifest["files"]:
        view_path = out / row["chinese_view"]
        bank_path = out / row["reference_json"]
        if sha(view_path) != row["chinese_view_sha256"] or sha(bank_path) != row["reference_json_sha256"]:
            raise RuntimeError("reading output differs from locked manifest")
        old = view_path.read_text(encoding="utf-8")
        new = render_view(json.loads(bank_path.read_text(encoding="utf-8")), row["source"])
        if old != new:
            if old.replace("Failure Lesson", "失败教训").replace("Procedure or Local Strategy", "流程或局部策略") != new:
                raise RuntimeError("unexpected Markdown difference beyond two type labels")
            changes.append((row, view_path, new, sha(view_path)))
    for row, path, new, old_hash in changes:
        path.write_text(new, encoding="utf-8")
        row["chinese_view_sha256"] = sha(path)
    audit = {"display_only": True, "repair": "translate only two type labels in Markdown headings",
             "changed_views": [{"view": row["chinese_view"], "old_sha256": old_hash,
                                "new_sha256": row["chinese_view_sha256"]} for row, _, _, old_hash in changes]}
    write_new(out / "view_label_audit.json", audit)
    save_map(manifest_path, manifest)
    return {"changed_views": len(changes)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("plan", "translate", "materialize", "localize-labels", "check"))
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    result = {"plan": plan, "translate": translate, "materialize": materialize,
              "localize-labels": localize_view_labels, "check": check}[args.phase](args.output_root)
    if result is not None:
        if args.phase == "plan":
            result = {"source_files": len(result["source_files"]), "unique_english_text_count": result["unique_english_text_count"], "batches": len(result["translation_batches"])}
        elif args.phase == "materialize":
            result = {"bank_count": len(result["files"])}
        print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
