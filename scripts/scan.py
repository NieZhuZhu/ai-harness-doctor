#!/usr/bin/env python3
"""Scan AI harness configuration files and report overlap/conflicts."""

import argparse
import fnmatch
import hashlib
import json
import os
import re
import string
import sys
from itertools import combinations
from pathlib import Path


SKIP_DIRS = {".git", "node_modules", "dist", "build", "__pycache__"}

CONFIG_PATTERNS = [
    ("AGENTS.md", ["AGENTS.md", "**/AGENTS.md"]),
    ("AGENT.md", ["AGENT.md", "**/AGENT.md"]),
    ("Claude Code", ["CLAUDE.md", "CLAUDE.local.md", ".claude/CLAUDE.md", "**/CLAUDE.md"]),
    ("Cursor", [".cursorrules", ".cursor/rules/*.mdc", ".cursor/rules/*.md"]),
    ("Windsurf", [".windsurfrules", ".windsurf/rules/*"]),
    ("GitHub Copilot", [".github/copilot-instructions.md", ".github/instructions/*.instructions.md"]),
    ("Gemini CLI", ["GEMINI.md", "**/GEMINI.md"]),
    ("Cline", [".clinerules", ".clinerules/*.md", ".clinerules/**/*.md"]),
    ("Roo", [".roo/rules/*.md", ".roo/rules/*.mdc"]),
]


def rel(path, root):
    return path.relative_to(root).as_posix()


def is_skipped(path, root):
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        parts = path.parts
    return any(part in SKIP_DIRS for part in parts)


def iter_matches(root):
    seen = {}
    for tool, patterns in CONFIG_PATTERNS:
        for pattern in patterns:
            for path in root.glob(pattern):
                if is_skipped(path, root) or not path.is_file():
                    continue
                rp = rel(path, root)
                seen.setdefault(rp, (tool, path))
    return [(tool, path) for _, (tool, path) in sorted(seen.items())]


def file_info(root, tool, path, max_bytes):
    data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
    size = len(data)
    warnings = []
    rp = rel(path, root)
    if size > max_bytes:
        warnings.append({
            "level": "WARN",
            "path": rp,
            "message": f"{rp} is {size} bytes, above {max_bytes}; Codex project_doc_max_bytes defaults to 32KB and may silently truncate context.",
        })
    elif size > 12 * 1024:
        warnings.append({
            "level": "NOTICE",
            "path": rp,
            "message": f"{rp} is {size} bytes; this may cause context bloat.",
        })
    return {
        "path": rp,
        "tool": tool,
        "bytes": size,
        "lines": 0 if not text else text.count("\n") + (0 if text.endswith("\n") else 1),
        "sha256": hashlib.sha256(data).hexdigest()[:12],
        "text": text,
        "warnings": warnings,
    }


def normalized_lines(text):
    out = []
    punctuation = set(string.punctuation + "#*-_=|`~>。！？、，；：（）【】《》")
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        s = re.sub(r"^#+\s*", "", s)
        if not s or all(ch in punctuation or ch.isspace() for ch in s):
            continue
        out.append(re.sub(r"\s+", " ", s).lower())
    return out


def find_overlaps(files):
    overlaps = []
    indexed = {f["path"]: set(normalized_lines(f["text"])) for f in files}
    for a, b in combinations(files, 2):
        la, lb = indexed[a["path"]], indexed[b["path"]]
        if not la or not lb:
            continue
        shared = la & lb
        ratio = len(shared) / float(min(len(la), len(lb)))
        if ratio > 0.30:
            overlaps.append({
                "a": a["path"],
                "b": b["path"],
                "shared_lines": len(shared),
                "ratio": round(ratio, 4),
                "percent": round(ratio * 100, 1),
            })
    return sorted(overlaps, key=lambda x: x["ratio"], reverse=True)


SIGNAL_PATTERNS = {
    "package_manager": [
        ("pnpm", re.compile(r"\bpnpm\b")),
        ("npm", re.compile(r"\bnpm\b")),
        ("yarn", re.compile(r"\byarn\b")),
        ("bun", re.compile(r"\bbun\b")),
    ],
    "indent_style": [
        ("tabs", re.compile(r"\btab(?:s)?\b", re.I)),
        ("2 spaces", re.compile(r"\b2\s+spaces\b|\btwo\s+spaces\b", re.I)),
        ("4 spaces", re.compile(r"\b4\s+spaces\b|\bfour\s+spaces\b", re.I)),
    ],
    "quote_style": [
        ("single", re.compile(r"\bsingle quotes?\b|单引号", re.I)),
        ("double", re.compile(r"\bdouble quotes?\b|双引号", re.I)),
    ],
    "test_command": [
        ("jest", re.compile(r"\bjest\b")),
        ("vitest", re.compile(r"\bvitest\b")),
        ("pytest", re.compile(r"\bpytest\b")),
        ("go test", re.compile(r"\bgo\s+test\b")),
        ("npm test", re.compile(r"\bnpm\s+(?:run\s+)?test\b")),
        ("pnpm test", re.compile(r"\bpnpm\s+(?:run\s+)?test\b")),
    ],
    "node_version": [("node", re.compile(r"\bnode(?:\.js)?\s*(?:v|version)?\s*(\d+(?:\.\d+)*)", re.I))],
    "formatter": [
        ("prettier", re.compile(r"\bprettier\b", re.I)),
        ("biome", re.compile(r"\bbiome\b", re.I)),
        ("eslint", re.compile(r"\beslint\b", re.I)),
    ],
}


def extract_signals(file_entry):
    signals = []
    for lineno, line in enumerate(file_entry["text"].splitlines(), 1):
        for signal, patterns in SIGNAL_PATTERNS.items():
            for value, pattern in patterns:
                match = pattern.search(line)
                if not match:
                    continue
                actual = f"node {match.group(1)}" if signal == "node_version" and match.groups() else value
                signals.append({"signal": signal, "value": actual, "path": file_entry["path"], "line": lineno, "evidence": line.strip()})
    return signals


def find_conflicts(files):
    by_signal = {}
    for f in files:
        values = {}
        for sig in extract_signals(f):
            values.setdefault(sig["signal"], {})[sig["value"]] = sig
        for signal, vals in values.items():
            for value, sig in vals.items():
                by_signal.setdefault(signal, {}).setdefault(value, []).append(sig)
    conflicts = []
    for signal, values in by_signal.items():
        if len(values) <= 1:
            continue
        conflicts.append({
            "signal": signal,
            "values": {value: entries[:3] for value, entries in values.items()},
        })
    return conflicts


def nested_agents(files):
    return [f["path"] for f in files if f["path"].endswith("AGENTS.md") and "/" in f["path"]]


def scan_repo(repo_root, max_bytes):
    root = Path(repo_root).resolve()
    files = []
    warnings = []
    for tool, path in iter_matches(root):
        info = file_info(root, tool, path, max_bytes)
        warnings.extend(info.pop("warnings"))
        files.append(info)
    result_files = [{k: v for k, v in f.items() if k != "text"} for f in files]
    return {
        "files": result_files,
        "warnings": warnings,
        "overlaps": find_overlaps(files),
        "conflicts": find_conflicts(files),
        "nested": nested_agents(result_files),
    }


def render_markdown(report):
    lines = ["# 阶段 0 体检报告", ""]
    lines.append("## 配置文件清单")
    if not report["files"]:
        lines.append("未发现已知 AI harness 配置文件。")
    else:
        lines.append("| 文件 | 工具 | 字节 | 行数 | SHA256 |")
        lines.append("|---|---:|---:|---:|---|")
        for f in report["files"]:
            lines.append(f"| `{f['path']}` | {f['tool']} | {f['bytes']} | {f['lines']} | `{f['sha256']}` |")
    lines.extend(["", "## 体积告警"])
    if report["warnings"]:
        for w in report["warnings"]:
            lines.append(f"- **{w['level']}** `{w['path']}`：{w['message']}")
    else:
        lines.append("未发现体积告警。")
    lines.extend(["", "## 重叠候选"])
    if report["overlaps"]:
        for o in report["overlaps"]:
            lines.append(f"- `{o['a']}` ↔ `{o['b']}`：共享行占较小文件 {o['percent']}%")
    else:
        lines.append("未发现超过 30% 的重叠候选。")
    lines.extend(["", "## 冲突候选"])
    if report["conflicts"]:
        for c in report["conflicts"]:
            lines.append(f"- **{c['signal']}**")
            for value, entries in c["values"].items():
                evidence = "; ".join(f"{e['path']}:{e['line']} `{e['evidence']}`" for e in entries)
                lines.append(f"  - `{value}`：{evidence}")
    else:
        lines.append("未发现明显冲突候选。")
    lines.extend(["", "## 嵌套 AGENTS.md", *(f"- `{p}`" for p in report["nested"])])
    if not report["nested"]:
        lines.append("无。")
    lines.extend(["", "> 停止条件：请确认迁移范围（全仓 / 子目录 / 指定文件）后再进入阶段 1 治疗。"])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Scan AI harness config files.")
    parser.add_argument("repo_root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--max-bytes", type=int, default=32768)
    args = parser.parse_args(argv)
    report = scan_repo(args.repo_root, args.max_bytes)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
