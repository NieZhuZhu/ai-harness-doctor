#!/usr/bin/env python3
"""Read-only drift guard for canonical AGENTS.md files."""

import argparse
import json
import os
import re
import sys
from pathlib import Path


DEFAULT_MAX_BYTES = 32768
STUB_FILES = ["CLAUDE.md", ".claude/CLAUDE.md", ".cursorrules", ".windsurfrules", ".github/copilot-instructions.md", "GEMINI.md", ".clinerules"]
PACKAGE_MANAGER_BUILTINS = {
    "install", "ci", "i", "init", "add", "remove", "rm", "uninstall", "update", "up", "upgrade",
    "exec", "dlx", "create", "audit", "link", "unlink", "publish", "outdated", "config", "cache",
    "login", "logout", "whoami", "version", "info", "list", "ls", "why", "dedupe", "prune",
    "rebuild", "help", "test", "start",
}


def line_collected_code(text):
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            yield lineno, line
        for m in re.finditer(r"`([^`]+)`", line):
            yield lineno, m.group(1)


def package_scripts(root):
    path = root / "package.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set((data.get("scripts") or {}).keys())
    except Exception:
        return set()


def make_targets(root):
    path = root / "Makefile"
    if not path.is_file():
        return None
    targets = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(r"^([A-Za-z0-9_.-]+):", line)
        if m and not line.startswith("\t"):
            targets.add(m.group(1))
    return targets


def d1_command_drift(root, text):
    findings = []
    scripts = package_scripts(root)
    targets = make_targets(root)
    cmd_re = re.compile(r"\b(?:(npm|pnpm)\s+(?:run\s+)?([A-Za-z0-9:_-]+)|yarn\s+([A-Za-z0-9:_-]+)|make\s+([A-Za-z0-9_.-]+))\b")
    for lineno, code in line_collected_code(text):
        for m in cmd_re.finditer(code):
            tool = m.group(1) or ("yarn" if m.group(3) else "make")
            name = m.group(2) or m.group(3) or m.group(4)
            if tool == "make" and targets is not None and name not in targets:
                findings.append({"check": "D1", "level": "ERROR", "line": lineno, "message": f"Unknown Makefile target `{name}`", "suggestion": "Update AGENTS.md or add the Makefile target."})
            # Treat package-manager builtins as valid unconditionally; false negatives are cheaper than noisy false positives here.
            if tool != "make" and name in PACKAGE_MANAGER_BUILTINS:
                continue
            if tool != "make" and scripts is not None and name not in scripts:
                findings.append({"check": "D1", "level": "ERROR", "line": lineno, "message": f"Unknown package.json script `{name}`", "suggestion": "Update AGENTS.md or add the package.json script."})
    return findings


def d2_path_drift(root, text):
    findings = []
    known = {"package.json", "Makefile", "AGENTS.md", "README.md"}
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in re.finditer(r"`([^`]+)`", line):
            token = m.group(1).strip()
            if token.startswith(("http://", "https://")) or "<" in token or "{" in token:
                continue
            if token.startswith(("npm ", "pnpm ", "yarn ", "make ", "python", "git ")):
                continue
            if "*" in token or "?" in token:
                continue
            if "/" not in token and token not in known:
                continue
            if any(ch.isspace() for ch in token):
                continue
            if not (root / token).exists():
                findings.append({"check": "D2", "level": "ERROR", "line": lineno, "message": f"Referenced path `{token}` does not exist", "suggestion": "Fix or remove the backtick-quoted path."})
    return findings


def d3_stub_regrowth(root):
    findings = []
    for rel in STUB_FILES:
        path = root / rel
        if not path.is_file():
            continue
        data = path.read_bytes()
        text = data.decode("utf-8", errors="replace")
        if len(data) > 600 or "AGENTS.md" not in text:
            findings.append({"check": "D3", "level": "ERROR", "path": rel, "message": f"Tool stub `{rel}` regrew or lost AGENTS.md pointer", "suggestion": "Run canonicalize.py --write-stubs after reviewing changes."})
    cursor_rules = root / ".cursor" / "rules"
    if cursor_rules.is_dir():
        for p in cursor_rules.glob("*"):
            if not p.is_file():
                continue
            data = p.read_bytes()
            text = data.decode("utf-8", errors="replace")
            if len(data) > 600 or "AGENTS.md" not in text:
                findings.append({"check": "D3", "level": "ERROR", "path": p.relative_to(root).as_posix(), "message": "Cursor rule regrew or lost AGENTS.md pointer", "suggestion": "Keep a single minimal pointer rule."})
    return findings


def d4_size(root, max_bytes):
    path = root / "AGENTS.md"
    if not path.is_file():
        return [{"check": "D4", "level": "ERROR", "message": "AGENTS.md is missing", "suggestion": "Create canonical AGENTS.md first."}]
    size = len(path.read_bytes())
    if size > max_bytes:
        return [{"check": "D4", "level": "ERROR", "message": f"AGENTS.md is {size} bytes, above {max_bytes}", "suggestion": "Move details to references/ and keep AGENTS.md concise."}]
    if size > 12 * 1024:
        return [{"check": "D4", "level": "NOTICE", "message": f"AGENTS.md is {size} bytes; context bloat risk", "suggestion": "Consider progressive disclosure."}]
    return []


def nested_agents(root):
    out = []
    for p in root.rglob("AGENTS.md"):
        if ".git" in p.parts or p == root / "AGENTS.md":
            continue
        out.append(p.relative_to(root).as_posix())
    return out


def run_checks(root, max_bytes, strict=False):
    agents = root / "AGENTS.md"
    text = agents.read_text(encoding="utf-8", errors="replace") if agents.is_file() else ""
    findings = []
    findings.extend(d1_command_drift(root, text))
    findings.extend(d2_path_drift(root, text))
    findings.extend(d3_stub_regrowth(root))
    findings.extend(d4_size(root, max_bytes))
    if strict:
        for f in findings:
            if f.get("level") == "NOTICE":
                f["level"] = "ERROR"
    info = [{"check": "D5", "level": "INFO", "path": p, "message": "Nested AGENTS.md inventory"} for p in nested_agents(root)]
    failures = [f for f in findings if f.get("level") == "ERROR"]
    return {"ok": not failures, "findings": findings, "info": info}


def render(report):
    lines = ["# 阶段 2 复诊 Drift Guard 报告", ""]
    if report["ok"]:
        lines.append("未发现阻断性 drift。")
    for check in ["D1", "D2", "D3", "D4"]:
        items = [f for f in report["findings"] if f["check"] == check]
        if not items:
            continue
        lines.extend(["", f"## {check}"])
        for f in items:
            loc = f":{f['line']}" if "line" in f else f" `{f.get('path')}`" if "path" in f else ""
            lines.append(f"- **{f['level']}**{loc} {f['message']} 修复建议：{f['suggestion']}")
    lines.extend(["", "## D5 嵌套 AGENTS.md（信息项，不阻断）"])
    if report["info"]:
        lines.extend(f"- `{i['path']}`" for i in report["info"])
    else:
        lines.append("无。")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check AGENTS.md drift.")
    parser.add_argument("repo_root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    args = parser.parse_args(argv)
    report = run_checks(Path(args.repo_root).resolve(), args.max_bytes, args.strict)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report), end="")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
