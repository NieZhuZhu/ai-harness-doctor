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

# Extended harness surfaces beyond plain instruction/rule files. The classic scan
# only looked at the CONFIG_PATTERNS above; these describe the rest of the agent
# runtime surface (MCP servers, subagents, slash commands, hooks, permissions).
MCP_CONFIG_FILES = [
    ".mcp.json",
    ".cursor/mcp.json",
    ".vscode/mcp.json",
    ".gemini/settings.json",
    ".claude/settings.json",
    ".claude/settings.local.json",
]
SUBAGENT_PATTERNS = [".claude/agents/*.md", ".claude/agents/**/*.md"]
COMMAND_PATTERNS = [
    ".claude/commands/*.md",
    ".claude/commands/**/*.md",
    ".codex/prompts/*.md",
    ".cursor/commands/*.md",
    ".cursor/commands/*.toml",
    ".gemini/commands/*.toml",
    ".gemini/commands/**/*.toml",
]
SETTINGS_FILES = [".claude/settings.json", ".claude/settings.local.json"]

# Secret-shaped tokens. Kept intentionally conservative to limit false positives;
# the goal is to flag obvious plaintext credentials committed into agent configs.
SECRET_PATTERNS = [
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    ("Generic hardcoded secret", re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password|passwd)\b\s*[:=]\s*['\"][^'\"\s]{12,}['\"]")),
]

# Permission entries that grant broad/unrestricted execution.
BROAD_PERMISSION_RE = re.compile(r"^(?:Bash|Execute|Shell)?\(\s*\*+\s*\)$|^\*$|:\s*\*\s*\)$")
# Hook / command bodies that fetch-and-run remote code or do destructive things.
RISKY_COMMAND_RES = [
    ("remote code execution", re.compile(r"(?:curl|wget)\b[^\n|]*\|\s*(?:sh|bash|zsh|python[0-9.]*|node)\b", re.I)),
    ("recursive force delete", re.compile(r"\brm\s+-[a-z]*r[a-z]*f|\brm\s+-[a-z]*f[a-z]*r", re.I)),
    ("shell eval of input", re.compile(r"\beval\s+\"?\$", re.I)),
    ("permission bypass flag", re.compile(r"--dangerously-skip-permissions|--yolo\b", re.I)),
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
    rp = rel(path, root)
    warnings = []
    # Stat the file first so an oversize (accidentally matched) file is not
    # fully read into memory before the size check. We still read the body for
    # normally-sized files; oversize files are read only up to max_bytes.
    size = path.stat().st_size
    if size > max_bytes:
        warnings.append({
            "level": "WARN",
            "path": rp,
            "message": f"{rp} is {size} bytes, above {max_bytes}; Codex project_doc_max_bytes defaults to 32KB and may silently truncate context.",
        })
        with path.open("rb") as fh:
            data = fh.read(max_bytes)
    else:
        if size > 12 * 1024:
            warnings.append({
                "level": "NOTICE",
                "path": rp,
                "message": f"{rp} is {size} bytes; this may cause context bloat.",
            })
        data = path.read_bytes()
    text = data.decode("utf-8", errors="replace")
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
    punctuation = set(string.punctuation + "#*-_=|`~>\u3002\uff01\uff1f\u3001\uff0c\uff1b\uff1a\uff08\uff09\u3010\u3011\u300a\u300b")
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
        ("single", re.compile(r"\bsingle quotes?\b|\u5355\u5f15\u53f7", re.I)),
        ("double", re.compile(r"\bdouble quotes?\b|\u53cc\u5f15\u53f7", re.I)),
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


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def glob_files(root, patterns):
    seen = {}
    for pattern in patterns:
        for path in root.glob(pattern):
            if is_skipped(path, root) or not path.is_file():
                continue
            seen.setdefault(rel(path, root), path)
    return [seen[k] for k in sorted(seen)]


def scan_mcp(root):
    servers = []
    for rel_path in MCP_CONFIG_FILES:
        path = root / rel_path
        if not path.is_file():
            continue
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        block = data.get("mcpServers") or data.get("servers") or {}
        if not isinstance(block, dict):
            continue
        for name, cfg in block.items():
            cfg = cfg if isinstance(cfg, dict) else {}
            url = cfg.get("url") or cfg.get("endpoint") or ""
            transport = cfg.get("type") or ("remote" if url else "stdio")
            env = cfg.get("env") if isinstance(cfg.get("env"), dict) else {}
            servers.append({
                "config": rel(path, root),
                "name": name,
                "transport": transport,
                "command": str(cfg.get("command", "")),
                "url": str(url),
                "env_keys": sorted(env.keys()),
            })
    return servers


def scan_subagents(root):
    return [rel(p, root) for p in glob_files(root, SUBAGENT_PATTERNS)]


def scan_commands(root):
    return [rel(p, root) for p in glob_files(root, COMMAND_PATTERNS)]


def iter_hook_commands(entries):
    out = []
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, dict):
                nested = entry.get("hooks")
                if isinstance(nested, list):
                    for h in nested:
                        if isinstance(h, dict) and h.get("command"):
                            out.append(str(h["command"]))
                if entry.get("command"):
                    out.append(str(entry["command"]))
            elif isinstance(entry, str):
                out.append(entry)
    return out


def scan_hooks(root):
    hooks = []
    for rel_path in SETTINGS_FILES:
        path = root / rel_path
        if not path.is_file():
            continue
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        hook_block = data.get("hooks")
        if isinstance(hook_block, dict):
            for event, entries in hook_block.items():
                for cmd in iter_hook_commands(entries):
                    hooks.append({"config": rel(path, root), "event": event, "command": cmd})
    githooks = root / ".githooks"
    if githooks.is_dir():
        for p in sorted(githooks.iterdir()):
            if p.is_file() and not p.name.endswith(".sample"):
                hooks.append({"config": rel(p, root), "event": "git", "command": p.name})
    return hooks


def scan_permissions(root):
    perms = []
    for rel_path in SETTINGS_FILES:
        path = root / rel_path
        if not path.is_file():
            continue
        data = load_json(path)
        if not isinstance(data, dict):
            continue
        block = data.get("permissions")
        if not isinstance(block, dict):
            continue
        entry = {"config": rel(path, root)}
        for key in ["allow", "deny", "ask"]:
            vals = block.get(key)
            if isinstance(vals, list):
                entry[key] = [str(v) for v in vals]
        if block.get("defaultMode"):
            entry["defaultMode"] = str(block["defaultMode"])
        perms.append(entry)
    return perms


def secret_hits(text):
    return [label for label, pattern in SECRET_PATTERNS if pattern.search(text)]


def security_findings(root, files, mcp, hooks, permissions):
    findings = []
    # 1) Plaintext secrets in instruction/rule files.
    for f in files:
        for label in secret_hits(f["text"]):
            findings.append({"level": "HIGH", "category": "secret", "path": f["path"],
                             "message": f"Possible {label} committed in {f['path']}"})
    # Raw MCP/settings config files are not in `files`; scan them directly.
    for rel_path in sorted(set(MCP_CONFIG_FILES) | set(SETTINGS_FILES)):
        path = root / rel_path
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for label in secret_hits(text):
            findings.append({"level": "HIGH", "category": "secret", "path": rel_path,
                             "message": f"Possible {label} committed in {rel_path}"})
    # 2) MCP transport / credential hygiene.
    for s in mcp:
        if s["url"].startswith("http://"):
            findings.append({"level": "MEDIUM", "category": "mcp", "path": s["config"],
                             "message": f"MCP server `{s['name']}` uses insecure http:// transport"})
        for key in s["env_keys"]:
            if re.search(r"(?i)key|token|secret|password", key):
                findings.append({"level": "MEDIUM", "category": "mcp", "path": s["config"],
                                 "message": f"MCP server `{s['name']}` sets credential-shaped env `{key}`; reference an env var instead of a literal"})
    # 3) Permission breadth.
    for p in permissions:
        for entry in p.get("allow", []):
            if BROAD_PERMISSION_RE.search(entry.strip()):
                findings.append({"level": "HIGH", "category": "permission", "path": p["config"],
                                 "message": f"Overly broad allow rule `{entry}` grants unrestricted execution"})
        mode = p.get("defaultMode", "")
        if mode == "bypassPermissions":
            findings.append({"level": "HIGH", "category": "permission", "path": p["config"],
                             "message": "permissions.defaultMode is `bypassPermissions` (no confirmation prompts)"})
        elif mode == "acceptEdits":
            findings.append({"level": "MEDIUM", "category": "permission", "path": p["config"],
                             "message": "permissions.defaultMode is `acceptEdits` (edits auto-approved)"})
    # 4) Risky hook / command bodies.
    for h in hooks:
        for label, pattern in RISKY_COMMAND_RES:
            if pattern.search(h["command"]):
                findings.append({"level": "HIGH", "category": "hook", "path": h["config"],
                                 "message": f"{h['event']} hook contains {label}: `{h['command'][:80]}`"})
    # 5) Risky flags recommended inside instruction files.
    for f in files:
        for label, pattern in RISKY_COMMAND_RES:
            if label == "permission bypass flag" and pattern.search(f["text"]):
                findings.append({"level": "MEDIUM", "category": "instruction", "path": f["path"],
                                 "message": f"Instruction file recommends a {label}"})
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    return sorted(findings, key=lambda x: (order.get(x["level"], 3), x["category"], x["path"]))


def scan_repo(repo_root, max_bytes):
    root = Path(repo_root).resolve()
    files = []
    warnings = []
    for tool, path in iter_matches(root):
        info = file_info(root, tool, path, max_bytes)
        warnings.extend(info.pop("warnings"))
        files.append(info)
    result_files = [{k: v for k, v in f.items() if k != "text"} for f in files]
    mcp = scan_mcp(root)
    hooks = scan_hooks(root)
    permissions = scan_permissions(root)
    return {
        "files": result_files,
        "warnings": warnings,
        "overlaps": find_overlaps(files),
        "conflicts": find_conflicts(files),
        "nested": nested_agents(result_files),
        "surface": {
            "mcp_servers": mcp,
            "subagents": scan_subagents(root),
            "commands": scan_commands(root),
            "hooks": hooks,
            "permissions": permissions,
        },
        "security": security_findings(root, files, mcp, hooks, permissions),
    }


def render_markdown(report):
    lines = ["# Phase 0 — Checkup Report", ""]
    lines.append("## Configuration file inventory")
    if not report["files"]:
        lines.append("No known AI harness configuration files were found.")
    else:
        lines.append("| File | Tool | Bytes | Lines | SHA256 |")
        lines.append("|---|---:|---:|---:|---|")
        for f in report["files"]:
            lines.append(f"| `{f['path']}` | {f['tool']} | {f['bytes']} | {f['lines']} | `{f['sha256']}` |")
    lines.extend(["", "## Size warnings"])
    if report["warnings"]:
        for w in report["warnings"]:
            lines.append(f"- **{w['level']}** `{w['path']}`: {w['message']}")
    else:
        lines.append("No size warnings found.")
    lines.extend(["", "## Overlap candidates"])
    if report["overlaps"]:
        for o in report["overlaps"]:
            lines.append(f"- `{o['a']}` ↔ `{o['b']}`: shared lines are {o['percent']}% of the smaller file")
    else:
        lines.append("No overlap candidates above 30% were found.")
    lines.extend(["", "## Conflict candidates"])
    if report["conflicts"]:
        for c in report["conflicts"]:
            lines.append(f"- **{c['signal']}**")
            for value, entries in c["values"].items():
                evidence = "; ".join(f"{e['path']}:{e['line']} `{e['evidence']}`" for e in entries)
                lines.append(f"  - `{value}`: {evidence}")
    else:
        lines.append("No obvious conflict candidates were found.")
    lines.extend(["", "## Nested AGENTS.md", *(f"- `{p}`" for p in report["nested"])])
    if not report["nested"]:
        lines.append("None.")
    render_surface(lines, report.get("surface", {}))
    if "security" in report:
        render_security(lines, report["security"])
    lines.extend(["", "> Stop condition: confirm the migration scope (whole repository / subdirectory / selected files) before entering Phase 1 — Treat."])
    return "\n".join(lines) + "\n"


def render_surface(lines, surface):
    lines.extend(["", "## Extended surface"])
    mcp = surface.get("mcp_servers", [])
    lines.append(f"- MCP servers: {len(mcp)}")
    for s in mcp:
        where = s["url"] or s["command"] or "(unspecified)"
        lines.append(f"  - `{s['name']}` ({s['transport']}) → `{where}` — {s['config']}")
    for label, key in [("Subagents", "subagents"), ("Slash commands", "commands")]:
        items = surface.get(key, [])
        lines.append(f"- {label}: {len(items)}")
        for it in items:
            lines.append(f"  - `{it}`")
    hooks = surface.get("hooks", [])
    lines.append(f"- Hooks: {len(hooks)}")
    for h in hooks:
        lines.append(f"  - {h['event']}: `{h['command'][:80]}` — {h['config']}")
    perms = surface.get("permissions", [])
    lines.append(f"- Permission configs: {len(perms)}")
    for p in perms:
        summary = ", ".join(f"{k}={len(p[k])}" for k in ["allow", "deny", "ask"] if k in p)
        mode = f", defaultMode={p['defaultMode']}" if "defaultMode" in p else ""
        lines.append(f"  - {p['config']}: {summary or 'no allow/deny/ask lists'}{mode}")


def render_security(lines, findings):
    lines.extend(["", "## Security checkup"])
    if not findings:
        lines.append("No security issues detected.")
        return
    for s in findings:
        lines.append(f"- **{s['level']}** [{s['category']}] `{s['path']}`: {s['message']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Scan AI harness config files.")
    parser.add_argument("repo_root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--max-bytes", type=int, default=32768)
    parser.add_argument("--no-security", action="store_true",
                        help="Skip the security checkup section.")
    parser.add_argument("--fail-on-security", action="store_true",
                        help="Exit non-zero when any HIGH-severity security finding is present.")
    args = parser.parse_args(argv)
    report = scan_repo(args.repo_root, args.max_bytes)
    if args.no_security:
        report.pop("security", None)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    if args.fail_on_security and any(s["level"] == "HIGH" for s in report.get("security", [])):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
