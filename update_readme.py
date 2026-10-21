#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Maintain the auto-generated overview block inside README.md.

Usage
-----
  python update_readme.py                 # scan once and rewrite the block
  python update_readme.py --watch         # keep README in sync (default 60s poll)
  python update_readme.py --watch --interval 15
  python update_readme.py --check         # exit 1 if README is stale, write nothing

Only the region between the AUTO:BEGIN / AUTO:END markers is touched, so any
hand-written prose outside that region is preserved.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta, timezone

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.abspath(__file__))
README = os.path.join(ROOT, "README.md")
BEGIN = "<!-- AUTO:BEGIN -->"
END = "<!-- AUTO:END -->"
TZ = timezone(timedelta(hours=8))


def human_int(value: int) -> str:
    return f"{value:,}"


def human_mb(total_bytes: int) -> str:
    return f"{total_bytes / 1048576:.1f} MB"


def _bump(store: dict, key: str, size: int) -> None:
    entry = store.get(key)
    if entry is None:
        store[key] = [1, size]
    else:
        entry[0] += 1
        entry[1] += size


def scan(root: str) -> dict:
    """Walk the tree once and aggregate counts/sizes per top-level entry."""
    dirs: dict[str, list[int]] = {}
    files: dict[str, int] = {}
    draft_kids: dict[str, list[int]] = {}

    for dirpath, _dirnames, filenames in os.walk(root, onerror=lambda _e: None):
        rel = os.path.relpath(dirpath, root)
        parts = [] if rel == "." else rel.split(os.sep)
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                size = os.path.getsize(path)
            except OSError:
                size = 0
            if not parts:
                files[name] = files.get(name, 0) + size
                continue
            top = parts[0]
            _bump(dirs, top, size)
            if top == "draft":
                kid = parts[1] if len(parts) > 1 else name
                _bump(draft_kids, kid, size)

    top_dirs: list[tuple[str, int, int]] = []
    for name in sorted(dirs):
        count, size = dirs[name]
        top_dirs.append((name, count, size))

    draft_rows: list[tuple[str, int, int]] = []
    for name in sorted(draft_kids):
        count, size = draft_kids[name]
        draft_rows.append((name, count, size))

    total_files = sum(c for _n, c, _s in top_dirs) + len(files)
    total_bytes = sum(s for _n, _c, s in top_dirs) + sum(files.values())

    return {
        "top_dirs": top_dirs,
        "top_files": sorted(files.items()),
        "draft_children": draft_rows,
        "total_files": total_files,
        "total_bytes": total_bytes,
    }


def render(scan_result: dict) -> str:
    now = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    lines: list[str] = []
    lines.append(f"- 最后更新：{now}（Asia/Shanghai，自动写入）")
    lines.append(f"- 扫描根目录：`{ROOT}`")
    lines.append(
        f"- 统计总量：{human_int(scan_result['total_files'])} 个文件，"
        f"{human_mb(scan_result['total_bytes'])}"
    )
    lines.append("- 更新方式：`python update_readme.py`；持续监测：`python update_readme.py --watch`")
    lines.append("")

    lines.append("### 根目录条目")
    lines.append("")
    lines.append("| 名称 | 类型 | 文件数 | 体积 |")
    lines.append("|---|---|---:|---:|")
    for name, count, size in scan_result["top_dirs"]:
        lines.append(f"| `{name}/` | 目录 | {human_int(count)} | {human_mb(size)} |")
    for name, size in scan_result["top_files"]:
        lines.append(f"| `{name}` | 文件 | 1 | {human_mb(size)} |")
    lines.append("")

    draft_rows = scan_result["draft_children"]
    if draft_rows:
        lines.append("### draft/ 内容")
        lines.append("")
        lines.append("| 名称 | 文件数 | 体积 |")
        lines.append("|---|---:|---:|")
        for name, count, size in draft_rows:
            lines.append(f"| `{name}` | {human_int(count)} | {human_mb(size)} |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def build_document(block: str) -> str:
    current = read_text(README)
    if BEGIN in current and END in current:
        head, rest = current.split(BEGIN, 1)
        _old, tail = rest.split(END, 1)
        return f"{head}{BEGIN}\n{block}{END}{tail}"
    suffix = "\n" if current.endswith("\n") else "\n\n"
    return f"{current}{suffix}{BEGIN}\n{block}{END}\n"


STAMP_PREFIX = "- 最后更新："

# Names excluded from change detection: rewriting README.md must not retrigger
# the watcher, otherwise the loop would refresh forever.
IGNORED_IN_SIGNATURE = {"README.md"}


def without_stamp(text: str) -> str:
    """Drop the volatile timestamp line so --check is not time sensitive."""
    return "\n".join(
        line for line in text.splitlines() if not line.startswith(STAMP_PREFIX)
    )


def refresh(verbose: bool = True) -> str:
    block = render(scan(ROOT))
    document = build_document(block)
    write_text(README, document)
    if verbose:
        stamp = datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{stamp}] README.md 已更新")
    return document


def signature() -> tuple:
    top: list[tuple] = []
    try:
        with os.scandir(ROOT) as entries:
            for entry in entries:
                if entry.name in IGNORED_IN_SIGNATURE:
                    continue
                try:
                    stat = entry.stat()
                    top.append((entry.name, entry.is_dir(), stat.st_size, stat.st_mtime_ns))
                except OSError:
                    top.append((entry.name, None, None, None))
    except OSError:
        pass
    top.sort()

    draft: list[tuple] = []
    draft_path = os.path.join(ROOT, "draft")
    if os.path.isdir(draft_path):
        try:
            with os.scandir(draft_path) as entries:
                for entry in entries:
                    if entry.name in IGNORED_IN_SIGNATURE:
                        continue
                    try:
                        stat = entry.stat()
                        draft.append((entry.name, entry.is_dir(), stat.st_size, stat.st_mtime_ns))
                    except OSError:
                        draft.append((entry.name, None, None, None))
        except OSError:
            pass
    draft.sort()
    return tuple(top), tuple(draft)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refresh the README overview block.")
    parser.add_argument("--watch", action="store_true", help="keep polling and refresh on change")
    parser.add_argument("--interval", type=float, default=60.0, help="poll interval in seconds")
    parser.add_argument("--check", action="store_true", help="exit 1 if README is stale")
    parser.add_argument("--quiet", action="store_true", help="suppress per-refresh log lines")
    args = parser.parse_args(argv)

    if args.check:
        block = render(scan(ROOT))
        expected = build_document(block)
        current = read_text(README)
        if without_stamp(current) == without_stamp(expected):
            print("README.md 与当前目录状态一致")
            return 0
        print("README.md 已过期，请运行：python update_readme.py")
        return 1

    if not args.watch:
        refresh(verbose=not args.quiet)
        return 0

    print(f"监测中：{ROOT}（每 {args.interval:g} 秒检查一次，Ctrl+C 退出）")
    refresh(verbose=not args.quiet)
    last = signature()
    try:
        while True:
            time.sleep(args.interval)
            current = signature()
            if current != last:
                refresh(verbose=not args.quiet)
                last = signature()
    except KeyboardInterrupt:
        print("已停止监测")
    return 0


if __name__ == "__main__":
    sys.exit(main())
