#!/usr/bin/env python3
"""Mechanical helpers for AI harness canonicalization."""

import argparse
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import scan  # noqa: E402


STUBS = {
    "claude": {
        "paths": ["CLAUDE.md", ".claude/CLAUDE.md"],
        "content": "@AGENTS.md\n<!-- Canonical instructions live in AGENTS.md. Keep this file as an import stub only. -->\n",
        "marker": "AGENTS.md",
    },
    "cursor": {
        "paths": [".cursorrules"],
        "content": "All agent instructions live in AGENTS.md (single source of truth). Do not add rules here.\n",
        "marker": "AGENTS.md",
    },
    "windsurf": {
        "paths": [".windsurfrules"],
        "content": "All agent instructions live in AGENTS.md (single source of truth). Do not add rules here.\n",
        "marker": "AGENTS.md",
    },
    "copilot": {
        "paths": [".github/copilot-instructions.md"],
        "content": "# GitHub Copilot instructions\n\nCanonical agent instructions live in `AGENTS.md`. Keep this stub minimal; do not duplicate rules here.\n",
        "marker": "AGENTS.md",
    },
    "gemini": {
        "paths": ["GEMINI.md"],
        "content": "# Gemini instructions\n\nCanonical agent instructions live in `AGENTS.md`. Prefer configuring Gemini CLI `contextFileName` to `AGENTS.md`; keep this file as a pointer only.\n",
        "marker": "AGENTS.md",
    },
    "cline": {
        "paths": [".clinerules"],
        "content": "Canonical agent instructions live in AGENTS.md. Keep this Cline pointer minimal and do not duplicate rules here.\n",
        "marker": "AGENTS.md",
    },
}

CURSOR_RULE_STUB = "---\nalwaysApply: true\n---\n\nCanonical agent instructions live in `AGENTS.md` (single source of truth). Do not duplicate rules here.\n"


def git_clean_or_forced(root, force):
    if force:
        return
    inside = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"], text=True, capture_output=True)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        raise SystemExit("Refusing to write: target is not a git repo. Use --force to override.")
    status = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], text=True, capture_output=True)
    if status.returncode != 0 or status.stdout.strip():
        raise SystemExit("Refusing to write: git working tree is dirty. Commit/stash first or use --force.")


def unified_diff(path, old, new):
    return "".join(difflib.unified_diff(
        old.splitlines(True), new.splitlines(True),
        fromfile=f"a/{path.as_posix()}", tofile=f"b/{path.as_posix()}", lineterm=""
    ))


def render_plan(report):
    lines = ["# 阶段 1 治疗合并计划骨架", ""]
    lines.append("## Inventory")
    lines.append("| 文件 | 工具 | 字节 | 行数 |")
    lines.append("|---|---|---:|---:|")
    for f in report["files"]:
        lines.append(f"| `{f['path']}` | {f['tool']} | {f['bytes']} | {f['lines']} |")
    lines.extend(["", "## Overlap clusters"])
    if report["overlaps"]:
        for o in report["overlaps"]:
            lines.append(f"- `{o['a']}` ↔ `{o['b']}`：{o['percent']}%")
    else:
        lines.append("- 无超过阈值的重叠。")
    lines.extend(["", "## Conflict list"])
    if report["conflicts"]:
        for c in report["conflicts"]:
            lines.append(f"- **{c['signal']}**")
            for value, entries in c["values"].items():
                lines.append(f"  - `{value}`")
                for e in entries:
                    lines.append(f"    - {e['path']}:{e['line']} `{e['evidence']}`")
    else:
        lines.append("- 无明显冲突候选。")
    lines.extend([
        "", "## TODO decision checklist",
        "- [ ] 确认迁移范围（全仓 / 子目录 / 指定文件）。",
        "- [ ] 对每个冲突项记录人工裁决结论。",
        "- [ ] 手工编写 root `AGENTS.md`，只纳入 agent 无法从代码/manifest 推断的信息。",
        "- [ ] 运行 `canonicalize.py --write-stubs` 预览降级 diff。",
        "- [ ] 运行 `canonicalize.py --validate` 复核。",
    ])
    return "\n".join(lines) + "\n"


def write_plan(args):
    report = scan.scan_repo(args.repo_root, args.max_bytes)
    content = render_plan(report)
    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
    else:
        print(content, end="")


def collect_stub_targets(root, tools):
    changes = []
    for tool in tools:
        spec = STUBS.get(tool)
        if not spec:
            continue
        for rel_path in spec["paths"]:
            path = root / rel_path
            if path.is_file():
                changes.append({"action": "write", "path": path, "content": spec["content"]})
    if "cursor" in tools:
        rules_dir = root / ".cursor" / "rules"
        if rules_dir.is_dir() and any(p.is_file() for p in rules_dir.iterdir()):
            changes.append({"action": "write", "path": rules_dir / "agents-md.mdc", "content": CURSOR_RULE_STUB})
            for p in sorted(rules_dir.iterdir()):
                if p.is_file() and p.name != "agents-md.mdc" and p.suffix in {".md", ".mdc"}:
                    changes.append({"action": "delete", "path": p})
    return changes


def write_stubs(args):
    root = Path(args.repo_root).resolve()
    if not (root / "AGENTS.md").is_file():
        raise SystemExit("AGENTS.md must exist before writing stubs.")
    tools = [t.strip() for t in args.tools.split(",") if t.strip()]
    changes = collect_stub_targets(root, tools)
    if args.apply:
        git_clean_or_forced(root, args.force)
    if not changes:
        print("No existing tool files matched; nothing to change.")
        return
    for change in changes:
        path = change["path"]
        rp = path.relative_to(root)
        if change["action"] == "delete":
            if args.apply:
                path.unlink()
            print(f"delete {rp.as_posix()}")
            continue
        new = change["content"]
        old = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        if old == new:
            continue
        if args.apply:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(new, encoding="utf-8")
            print(f"rewrote {rp.as_posix()}")
        else:
            print(unified_diff(rp, old, new))


def heading_present(text, requirement):
    variants = [v.strip().lower() for v in requirement.split("/") if v.strip()]
    headings = []
    for line in text.splitlines():
        m = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$", line)
        if m:
            headings.append(m.group(1).strip().lower())
    return any(any(v in h for v in variants) for h in headings)


def validate(args):
    root = Path(args.repo_root).resolve()
    findings = []
    agents = root / "AGENTS.md"
    if not agents.is_file():
        findings.append({"level": "ERROR", "check": "AGENTS_EXISTS", "message": "AGENTS.md is missing"})
    else:
        data = agents.read_bytes()
        text = data.decode("utf-8", errors="replace")
        if len(data) > args.max_bytes:
            findings.append({"level": "ERROR", "check": "SIZE", "message": f"AGENTS.md is {len(data)} bytes, above {args.max_bytes}"})
        for req in args.require_sections.split(","):
            if req.strip() and not heading_present(text, req.strip()):
                findings.append({"level": "ERROR", "check": "SECTION", "message": f"Missing required heading: {req.strip()}"})
    if agents.is_file():
        for change in collect_stub_targets(root, ["claude", "cursor", "windsurf", "copilot", "gemini", "cline"]):
            path = change["path"]
            if not path.is_file():
                continue
            if change["action"] == "write":
                text = path.read_text(encoding="utf-8", errors="replace")
                if "AGENTS.md" in text and len(text.encode("utf-8")) <= 800:
                    continue
            # Existing full files are allowed before stub-writing; check_drift catches post-migration re-divergence.
            findings.append({"level": "NOTICE", "check": "STUB", "path": path.relative_to(root).as_posix(), "message": "tool file not yet downgraded to stub (or regrew)"})
    errors = [f for f in findings if f.get("level") == "ERROR"]
    result = {"ok": not errors, "findings": findings}
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if findings:
            print("阶段 1 治疗校验失败：" if errors else "阶段 1 治疗校验通过（含提示）：")
            for f in findings:
                loc = f" {f['path']}" if "path" in f else ""
                print(f"- [{f['level']}/{f['check']}]{loc} {f['message']}")
        else:
            print("阶段 1 治疗校验通过。")
    return 0 if not errors else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Canonicalization mechanics for AGENTS.md.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument("--write-stubs", action="store_true")
    mode.add_argument("--validate", action="store_true")
    parser.add_argument("repo_root", nargs="?", default=".")
    parser.add_argument("-o", "--output")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--tools", default="claude,cursor,windsurf,copilot,gemini,cline")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--max-bytes", type=int, default=32768)
    parser.add_argument("--require-sections", default="项目概览/Project overview,构建与测试/Build & test,代码规范/Conventions")
    args = parser.parse_args(argv)
    if args.plan:
        write_plan(args)
        return 0
    if args.write_stubs:
        write_stubs(args)
        return 0
    return validate(args)


if __name__ == "__main__":
    sys.exit(main())
