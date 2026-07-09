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
import tempfile
from itertools import combinations
from pathlib import Path

# The shared agent-config registry is the single source of truth for which config
# files exist and how to detect them; see assets/agent-tools.json and registry.py.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import plugins  # noqa: E402  # user-extensible deterministic rule plugins
import registry  # noqa: E402
import semantic  # noqa: E402  # declaration-vs-fact consistency engine


SKIP_DIRS = {".git", "node_modules", "dist", "build", "__pycache__"}


def _build_config_patterns():
    """Derive (label, glob-patterns) pairs from the shared registry.

    Canonical files (AGENTS.md / AGENT.md) come first and use the conventional
    ``[name, "**/name"]`` pair; tool entries follow in registry order with their
    richer scan_patterns. Order is preserved so scan output is byte-stable.
    """
    reg = registry.load_registry()
    patterns = []
    for name in reg.get("canonical", []):
        patterns.append((name, [name, f"**/{name}"]))
    for tool in reg.get("tools", []):
        patterns.append((tool["label"], list(tool["scan_patterns"])))
    return patterns


CONFIG_PATTERNS = _build_config_patterns()

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

# ---------------------------------------------------------------------------
# Gap analysis: what a healthy harness *should* have but this repo is missing.
# The classic scan only reports what already exists (files, overlaps, conflicts,
# extended surface). Gap analysis diffs the repo against a completeness
# checklist so users can see what infrastructure is absent, not just present.
# ---------------------------------------------------------------------------

# Fallback list used when assets/AGENTS.template.md cannot be read. Kept in sync
# with the H1 headings of that template.
DEFAULT_REQUIRED_SECTIONS = [
    "Project overview",
    "Build & test",
    "Conventions",
    "Testing requirements",
    "Safety",
    "Commit & PR",
]

# Tool stub files that, once an AGENTS.md exists, should be minimal pointers back
# to it rather than full duplicated instruction sets. Mirrors check_drift.py.
GAP_STUB_FILES = [
    "CLAUDE.md",
    ".claude/CLAUDE.md",
    ".cursorrules",
    ".windsurfrules",
    ".github/copilot-instructions.md",
    "GEMINI.md",
    ".clinerules",
]
STUB_POINTER_MAX_BYTES = 600

# Guard / CI templates the `ai-harness-doctor guard` installer writes.
GUARD_CI_WORKFLOWS = [
    (".github/workflows/harness-drift.yml", "WARN", "drift guard CI workflow"),
    (".github/workflows/harness-checkup.yml", "NOTICE", "weekly checkup CI workflow"),
]
GUARD_MARKER = "ai-harness-doctor:guard"
PRECOMMIT_HOOK_PATHS = [".git/hooks/pre-commit", ".githooks/pre-commit"]

# ---------------------------------------------------------------------------
# Project snapshot: a compact, factual description of the repository that an
# external agent/LLM can reason over to infer what harness pieces *should* exist
# for this particular tech stack. Unlike the static G1-G4 gap checks (which are
# mandatory infrastructure and stay rule-based), the snapshot only reports facts
# and defers the "should have but doesn't" judgement to the agent.
# ---------------------------------------------------------------------------

# Manifest files that reveal the primary language / ecosystem. Order matters
# only for readability; every match is reported.
TECH_STACK_MARKERS = [
    ("Go", ["go.mod", "go.sum", "go.work"]),
    ("Node.js", ["package.json"]),
    ("Python", ["pyproject.toml", "requirements.txt", "setup.py", "setup.cfg", "Pipfile",
                "poetry.lock", "uv.lock", "pdm.lock", "Pipfile.lock"]),
    ("Rust", ["Cargo.toml", "Cargo.lock"]),
    ("Ruby", ["Gemfile"]),
    ("PHP", ["composer.json"]),
    ("Java (Maven)", ["pom.xml"]),
    ("Java/Kotlin (Gradle)", ["build.gradle", "build.gradle.kts"]),
    (".NET", ["*.csproj", "*.sln", "*.fsproj"]),
    ("Elixir", ["mix.exs"]),
    ("Dart/Flutter", ["pubspec.yaml"]),
    ("Swift", ["Package.swift"]),
]

# Config surfaces grouped by concern so an agent can see what tooling is (and is
# not) wired up. Values are glob patterns evaluated from the repo root.
SNAPSHOT_FILE_GROUPS = [
    ("ci", [
        ".github/workflows/*.yml", ".github/workflows/*.yaml",
        ".gitlab-ci.yml", ".circleci/config.yml", "azure-pipelines.yml",
        "Jenkinsfile", ".travis.yml", "buildkite.yml", ".drone.yml",
    ]),
    ("hooks", [
        ".pre-commit-config.yaml", ".pre-commit-config.yml",
        ".githooks/*", ".husky/*", "lefthook.yml", "lefthook.yaml",
    ]),
    ("lint_format", [
        ".eslintrc", ".eslintrc.*", "eslint.config.*", ".prettierrc",
        ".prettierrc.*", "prettier.config.*", "biome.json", "biome.jsonc",
        ".flake8", "ruff.toml", ".ruff.toml", ".pylintrc",
        ".golangci.yml", ".golangci.yaml", ".rubocop.yml",
        ".editorconfig", ".rustfmt.toml", "rustfmt.toml",
    ]),
    ("typecheck", [
        "tsconfig.json", "mypy.ini", ".mypy.ini", "pyrightconfig.json",
    ]),
]


def snapshot_tech_stack(root):
    """Detect the languages / ecosystems present via their manifest files."""
    stack = []
    for language, patterns in TECH_STACK_MARKERS:
        markers = []
        for pattern in patterns:
            for path in root.glob(pattern):
                if is_skipped(path, root) or not path.is_file():
                    continue
                markers.append(rel(path, root))
        if markers:
            stack.append({"language": language, "markers": sorted(set(markers))})
    return stack


def snapshot_existing_files(root):
    """Inventory CI / hook / lint / typecheck config files present in the repo."""
    groups = {}
    for group, patterns in SNAPSHOT_FILE_GROUPS:
        found = []
        for pattern in patterns:
            for path in root.glob(pattern):
                if is_skipped(path, root) or not path.is_file():
                    continue
                found.append(rel(path, root))
        groups[group] = sorted(set(found))
    # Pre-commit drift-guard hook (previously the static G5 check) is now a fact.
    guard_hook = None
    for rel_path in PRECOMMIT_HOOK_PATHS:
        path = root / rel_path
        if path.is_file() and GUARD_MARKER in path.read_text(encoding="utf-8", errors="replace"):
            guard_hook = rel_path
            break
    groups["drift_guard_hook"] = guard_hook
    return groups


def build_project_snapshot(root, surface, agents_text):
    """Compact, factual description of the repo for agent-based gap inference."""
    sections = markdown_headings(agents_text, levels=(1,)) if agents_text else []
    return {
        "tech_stack": snapshot_tech_stack(root),
        "existing_files": snapshot_existing_files(root),
        "agents_sections": sections,
        "maintenance_contract": bool(agents_text) and "maintenance contract" in agents_text.lower(),
        "mcp_tools": [s["name"] for s in surface.get("mcp_servers", [])],
        "has_permissions": bool(surface.get("permissions")),
    }


def write_report_file(report, repo_root):
    """Dump the full JSON report to a stable temp file so an agent can read it
    back and reason over the machine-readable data (snapshot, gaps, surface,
    security) rather than re-parsing the markdown. Returns the file path, or
    None if writing failed (writing must never break the scan output)."""
    digest = hashlib.sha256(str(Path(repo_root).resolve()).encode("utf-8")).hexdigest()[:12]
    path = Path(tempfile.gettempdir()) / f"harness-scan-{digest}.json"
    try:
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return None
    return str(path)


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
        ("poetry", re.compile(r"\bpoetry\b")),
        ("pipenv", re.compile(r"\bpipenv\b")),
        ("pdm", re.compile(r"\bpdm\b")),
        ("uv", re.compile(r"\buv\s+(?:run|sync|pip|add|lock|venv|tool)\b")),
        # `uv pip install` is uv's pip *interface*, not a competing pip package
        # manager; the negative lookbehind stops it from also matching as "pip"
        # and manufacturing a bogus uv-vs-pip conflict.
        ("pip", re.compile(r"(?<!uv )\bpip3?\s+install\b")),
        ("cargo", re.compile(r"\bcargo\b")),
        ("go modules", re.compile(r"\bgo\s+(?:mod|get|build|test|run)\b")),
        ("maven", re.compile(r"\bmvn\b|\bmaven\b")),
        ("gradle", re.compile(r"\bgradle\b|\bgradlew\b")),
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
        ("cargo test", re.compile(r"\bcargo\s+test\b")),
        ("mvn test", re.compile(r"\bmvn\s+(?:test|verify)\b")),
        ("gradle test", re.compile(r"\bgradle(?:w)?\s+test\b|\./gradlew\s+test\b")),
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


def required_sections():
    """H1 headings the canonical AGENTS.md is expected to contain.

    Prefers the bundled assets/AGENTS.template.md so the checklist stays in sync
    with the template shipped by this skill; falls back to a built-in list."""
    template = Path(__file__).resolve().parent.parent / "assets" / "AGENTS.template.md"
    try:
        heads = [h for h in markdown_headings(template.read_text(encoding="utf-8"), levels=(1,))]
        if heads:
            return heads
    except Exception:
        pass
    return list(DEFAULT_REQUIRED_SECTIONS)


def markdown_headings(text, levels=None):
    """Return heading titles, ignoring lines inside fenced code blocks.

    `levels` optionally restricts to specific heading depths (e.g. (1,) for H1).
    """
    heads = []
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^(#+)\s+(\S.*)$", line)
        if not m:
            continue
        if levels and len(m.group(1)) not in levels:
            continue
        heads.append(m.group(2).strip())
    return heads


def gap(check, level, item, message, suggestion):
    return {"check": check, "level": level, "item": item, "message": message, "suggestion": suggestion}


def find_gaps(root, surface):
    """Diff the repo against a harness completeness checklist and report what is
    missing. Read-only: never writes or mutates the target repository."""
    gaps = []
    agents = root / "AGENTS.md"

    # 1) Canonical root AGENTS.md must exist — the single source of truth.
    if not agents.is_file():
        gaps.append(gap(
            "G1", "ERROR", "Root AGENTS.md",
            "No canonical `AGENTS.md` at the repository root.",
            "Create a root AGENTS.md (see assets/AGENTS.template.md), then run canonicalize.py --write-stubs.",
        ))
        agents_text = ""
    else:
        agents_text = agents.read_text(encoding="utf-8", errors="replace")

    # 2) Required sections present in AGENTS.md.
    if agents.is_file():
        present = [h.lower() for h in markdown_headings(agents_text)]
        for section in required_sections():
            needle = section.lower()
            if not any(needle == h or needle in h for h in present):
                gaps.append(gap(
                    "G2", "WARN", f"Section: {section}",
                    f"AGENTS.md is missing the `{section}` section.",
                    f"Add a `# {section}` section describing what agents cannot infer from code alone.",
                ))

    # 3) Tool stubs should be minimal pointers to AGENTS.md, not full duplicates.
    if agents.is_file():
        for rel_path in GAP_STUB_FILES:
            path = root / rel_path
            if not path.is_file():
                continue
            data = path.read_bytes()
            text = data.decode("utf-8", errors="replace")
            if len(data) > STUB_POINTER_MAX_BYTES or "AGENTS.md" not in text:
                gaps.append(gap(
                    "G3", "WARN", f"Stub pointer: {rel_path}",
                    f"`{rel_path}` exists but is not a minimal pointer to AGENTS.md "
                    f"({len(data)} bytes; pointer must be <= {STUB_POINTER_MAX_BYTES} bytes and reference AGENTS.md).",
                    "Run canonicalize.py --write-stubs to downgrade it to a pointer.",
                ))

    # 4) Drift guard / checkup CI workflows.
    for rel_path, level, item in GUARD_CI_WORKFLOWS:
        if not (root / rel_path).is_file():
            gaps.append(gap(
                "G4", level, item,
                f"`{rel_path}` is not installed.",
                "Run `ai-harness-doctor guard . --apply` to install the guard suite.",
            ))

    # G5-G8 (pre-commit drift guard, maintenance contract, MCP configuration,
    # permission configuration) used to be reported here as static gaps. They
    # are stack-dependent judgement calls rather than mandatory infrastructure,
    # so they are now surfaced as facts in `project_snapshot`, which an agent can
    # read from the full JSON report (see write_report_file) to reason about.
    order = {"ERROR": 0, "WARN": 1, "NOTICE": 2}
    return sorted(gaps, key=lambda g: (order.get(g["level"], 3), g["check"]))


def scan_repo(repo_root, max_bytes, rules_dirs=None):
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
    surface = {
        "mcp_servers": mcp,
        "subagents": scan_subagents(root),
        "commands": scan_commands(root),
        "hooks": hooks,
        "permissions": permissions,
    }
    agents_path = root / "AGENTS.md"
    agents_text = agents_path.read_text(encoding="utf-8", errors="replace") if agents_path.is_file() else ""
    report = {
        "files": result_files,
        "warnings": warnings,
        "overlaps": find_overlaps(files),
        "conflicts": find_conflicts(files),
        "nested": nested_agents(result_files),
        "surface": surface,
        "security": security_findings(root, files, mcp, hooks, permissions),
        "project_snapshot": build_project_snapshot(root, surface, agents_text),
        "semantic": semantic.analyze(root, agents_text),
        "gaps": find_gaps(root, surface),
    }
    # User-extensible deterministic rule plugins (opt-in). Discovered from
    # <root>/.ai-harness-doctor/rules/*.py plus any --rules DIR; each plugin is
    # isolated so a broken one is reported as an ERROR finding, never a crash.
    # The key is always present (empty list when no plugins) and rendered under
    # its own "Custom rule plugins" section.
    context = {"phase": "scan", "agents_text": agents_text}
    report["custom"] = plugins.run_plugins(root, context, rules_dirs)
    return report


# ---------------------------------------------------------------------------
# Monorepo / multi-package awareness. A single repository frequently hosts many
# packages (npm/yarn/pnpm workspaces, or simply several nested package.json /
# AGENTS.md subtrees). The classic scan only ever looks at one root; monorepo
# mode additionally scans each detected package subdirectory and reports
# per-package results plus a top-level aggregate. Single-repo behavior is
# unchanged whenever no workspace is detected.
# ---------------------------------------------------------------------------


def _read_root_workspaces(root):
    """npm/yarn workspace globs declared in the root package.json, if any."""
    path = root / "package.json"
    data = load_json(path) if path.is_file() else None
    if not isinstance(data, dict):
        return []
    ws = data.get("workspaces")
    if isinstance(ws, list):
        return [str(x) for x in ws]
    if isinstance(ws, dict) and isinstance(ws.get("packages"), list):
        return [str(x) for x in ws["packages"]]
    return []


def _read_pnpm_workspaces(root):
    """pnpm workspace globs from pnpm-workspace.yaml (minimal stdlib parser)."""
    path = root / "pnpm-workspace.yaml"
    if not path.is_file():
        path = root / "pnpm-workspace.yml"
    if not path.is_file():
        return []
    globs = []
    in_packages = False
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not in_packages:
            if re.match(r"^packages\s*:", stripped):
                after = stripped.split(":", 1)[1].strip()
                if after.startswith("["):
                    globs.extend(re.findall(r"['\"]([^'\"]+)['\"]", after))
                else:
                    in_packages = True
            continue
        m = re.match(r"^-\s*(.+)$", stripped)
        if m:
            val = m.group(1).strip().strip("'\"")
            if val:
                globs.append(val)
        elif not raw.startswith((" ", "\t")):
            # Dedented back to a new top-level key; the packages block ended.
            in_packages = False
    return globs


def _expand_workspace_globs(root, globs):
    """Expand workspace globs to concrete package directories under ``root``.

    A directory qualifies as a package when it holds its own ``package.json`` or
    ``AGENTS.md``. Negation entries (``!pkg``) and vendored dirs are ignored.
    Returns an ordered ``{relative_path: Path}`` mapping.
    """
    dirs = {}
    for glob in globs:
        glob = str(glob).strip().strip("/")
        if not glob or glob.startswith("!"):
            continue
        for path in sorted(root.glob(glob)):
            if not path.is_dir() or is_skipped(path, root):
                continue
            if (path / "package.json").is_file() or (path / "AGENTS.md").is_file():
                dirs[rel(path, root)] = path
    return dict(sorted(dirs.items()))


def _discover_nested_packages(root):
    """Heuristic package discovery when no workspace config exists.

    Finds the shallowest subdirectories that contain a ``package.json`` or a
    ``AGENTS.md`` (never descending into an already-detected package), pruning
    the same vendored dirs the rest of the scan skips.
    """
    dirs = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        p = Path(dirpath)
        if p == root:
            continue
        if "package.json" in filenames or "AGENTS.md" in filenames:
            dirs[rel(p, root)] = p
            dirnames[:] = []  # do not descend into a detected package subtree
    return dict(sorted(dirs.items()))


def detect_packages(root, mode="auto"):
    """Detect workspace/monorepo packages under ``root``.

    ``mode`` is one of ``"auto"`` (explicit workspace config only — the default,
    so single repos are never treated as monorepos), ``"force"`` (also fall back
    to nested-package discovery), or ``"off"`` (never a monorepo). Returns
    ``(ordered {rel: Path}, source_label|None)``.
    """
    if mode == "off":
        return {}, None
    dirs = _expand_workspace_globs(root, _read_root_workspaces(root))
    if dirs:
        return dirs, "package.json workspaces"
    dirs = _expand_workspace_globs(root, _read_pnpm_workspaces(root))
    if dirs:
        return dirs, "pnpm-workspace.yaml"
    if mode == "force":
        dirs = _discover_nested_packages(root)
        if dirs:
            return dirs, "nested packages"
    return {}, None


def _package_name(path):
    data = load_json(path / "package.json") if (path / "package.json").is_file() else None
    if isinstance(data, dict) and isinstance(data.get("name"), str):
        return data["name"]
    return None


def _package_summary(report):
    return {
        "files": len(report.get("files", [])),
        "gaps": len(report.get("gaps", [])),
        "security_high": sum(1 for s in report.get("security", []) if s.get("level") == "HIGH"),
        "overlaps": len(report.get("overlaps", [])),
        "conflicts": len(report.get("conflicts", [])),
        "semantic_mismatches": (report.get("semantic") or {}).get("mismatches", 0),
    }


def _aggregate_packages(packages):
    """Sum the per-package summaries into a single top-level aggregate."""
    keys = ["files", "gaps", "security_high", "overlaps", "conflicts", "semantic_mismatches"]
    aggregate = {k: 0 for k in keys}
    aggregate["packages_with_agents_md"] = 0
    for pkg in packages:
        for k in keys:
            aggregate[k] += pkg["summary"].get(k, 0)
        if pkg.get("has_agents_md"):
            aggregate["packages_with_agents_md"] += 1
    return aggregate


def scan_monorepo(root, max_bytes, package_dirs, source, rules_dirs=None):
    """Scan every detected package subdirectory and build the aggregate.

    Returns ``(monorepo_summary, packages)`` where ``packages`` is a list of
    ``{path, name, has_agents_md, summary, report}`` (each ``report`` is a plain
    single-repo :func:`scan_repo` result so there is never nested recursion).
    """
    packages = []
    for relpath, pdir in package_dirs.items():
        sub = scan_repo(pdir, max_bytes, rules_dirs)
        packages.append({
            "path": relpath,
            "name": _package_name(pdir),
            "has_agents_md": (pdir / "AGENTS.md").is_file(),
            "summary": _package_summary(sub),
            "report": sub,
        })
    monorepo = {
        "source": source,
        "package_count": len(packages),
        "aggregate": _aggregate_packages(packages),
    }
    return monorepo, packages


def render_markdown(report, report_path=None):
    lines = ["# Phase 0 — Checkup Report", ""]
    if "monorepo" in report:
        render_monorepo(lines, report["monorepo"], report.get("packages", []))
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
    if "project_snapshot" in report:
        render_snapshot(lines, report["project_snapshot"])
    if "semantic" in report:
        render_semantic(lines, report["semantic"])
    if "gaps" in report:
        render_gaps(lines, report["gaps"])
    if "custom" in report:
        render_custom(lines, report["custom"])
    if report_path:
        lines.extend([
            "",
            "## Full JSON report",
            f"The complete machine-readable report was written to `{report_path}`. "
            "An agent can read this file to reason over the project snapshot, gaps, "
            "surface, and security findings, and to plan fixes.",
        ])
    lines.extend(["", "> Stop condition: confirm the migration scope (whole repository / subdirectory / selected files) before entering Phase 1 — Treat."])
    return "\n".join(lines) + "\n"


def render_monorepo(lines, monorepo, packages):
    lines.extend(["", "## Monorepo"])
    source = monorepo.get("source") or "unknown"
    lines.append(f"Detected {monorepo.get('package_count', 0)} package(s) via {source}.")
    agg = monorepo.get("aggregate", {})
    lines.append(
        "Aggregate across packages: "
        f"{agg.get('files', 0)} config file(s), "
        f"{agg.get('gaps', 0)} gap(s), "
        f"{agg.get('security_high', 0)} HIGH security finding(s), "
        f"{agg.get('overlaps', 0)} overlap(s), "
        f"{agg.get('conflicts', 0)} conflict(s), "
        f"{agg.get('packages_with_agents_md', 0)} package(s) with AGENTS.md."
    )
    if packages:
        lines.append("")
        lines.append("| Package | Name | AGENTS.md | Config files | Gaps | HIGH sec |")
        lines.append("|---|---|:---:|---:|---:|---:|")
        for pkg in packages:
            summary = pkg.get("summary", {})
            lines.append(
                f"| `{pkg['path']}` | {pkg.get('name') or '—'} | "
                f"{'yes' if pkg.get('has_agents_md') else 'no'} | "
                f"{summary.get('files', 0)} | {summary.get('gaps', 0)} | "
                f"{summary.get('security_high', 0)} |"
            )
    lines.append("")
    lines.append("> Per-package details are in the `packages` array of the JSON report (`--json`).")
    lines.append("")


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


def render_gaps(lines, gaps):
    lines.extend(["", "## Missing / Gap Analysis"])
    if not gaps:
        lines.append("No harness infrastructure gaps detected.")
        return
    lines.append("Checklist items this repository is missing (compared with a complete harness):")
    lines.append("")
    for g in gaps:
        lines.append(f"- **{g['level']}** {g['item']}: {g['message']}")
        lines.append(f"  - Suggestion: {g['suggestion']}")


def render_custom(lines, findings):
    lines.extend(["", "## Custom rule plugins"])
    if not findings:
        lines.append("No custom rule plugins loaded (see `.ai-harness-doctor/rules/` or `--rules DIR`).")
        return
    for f in findings:
        loc = f":{f['line']}" if "line" in f else (f" `{f['path']}`" if "path" in f else "")
        lines.append(f"- **{f['level']}** [{f.get('plugin', '?')}:{f.get('rule', 'custom')}]{loc} {f['message']}")
        if f.get("suggestion"):
            lines.append(f"  - Suggestion: {f['suggestion']}")


CATEGORY_LABELS = {
    "command": "Command",
    "path": "Path",
    "package_manager": "Package manager",
    "node_version": "Node version",
    "python_version": "Python version",
    "go_version": "Go version",
    "rust_version": "Rust version",
    "java_version": "Java version",
}


def render_semantic(lines, semantic_report):
    lines.extend(["", "## Semantic consistency (declaration vs code)"])
    findings = semantic_report.get("findings", [])
    checked = semantic_report.get("checked", 0)
    if not findings:
        if checked:
            lines.append(f"All {checked} AGENTS.md declaration(s) match repository facts.")
        else:
            lines.append("No verifiable AGENTS.md declarations were found to cross-check.")
        return
    lines.append(
        f"{len(findings)} of {checked} checked AGENTS.md declaration(s) do not match the code:"
    )
    for f in findings:
        label = CATEGORY_LABELS.get(f["category"], f["category"])
        loc = f":{f['line']}" if "line" in f else ""
        lines.append(f"- **{f['level']}** [{label}]{loc} {f['message']}")
        lines.append(f"  - Suggestion: {f['suggestion']}")


def render_snapshot(lines, snapshot):
    lines.extend(["", "## Project snapshot"])
    stack = snapshot.get("tech_stack", [])
    if stack:
        lines.append("- Tech stack:")
        for s in stack:
            lines.append(f"  - {s['language']}: {', '.join(f'`{m}`' for m in s['markers'])}")
    else:
        lines.append("- Tech stack: none detected")
    existing = snapshot.get("existing_files", {})
    for group in ("ci", "hooks", "lint_format", "typecheck"):
        items = existing.get(group, [])
        if items:
            lines.append(f"- {group}: {', '.join(f'`{i}`' for i in items)}")
        else:
            lines.append(f"- {group}: none")
    lines.append(f"- Drift-guard pre-commit hook: {existing.get('drift_guard_hook') or 'none'}")
    sections = snapshot.get("agents_sections", [])
    lines.append(f"- AGENTS.md sections: {', '.join(sections) if sections else 'none'}")
    lines.append(f"- Maintenance contract: {'present' if snapshot.get('maintenance_contract') else 'absent'}")
    mcp_tools = snapshot.get("mcp_tools", [])
    lines.append(f"- MCP tools: {', '.join(f'`{t}`' for t in mcp_tools) if mcp_tools else 'none'}")
    lines.append(f"- Permission configuration: {'present' if snapshot.get('has_permissions') else 'absent'}")


def _apply_section_flags(report, args):
    """Drop optional report sections per the --no-* flags (in place)."""
    if args.no_snapshot:
        report.pop("project_snapshot", None)
    if args.no_security:
        report.pop("security", None)
    if args.no_gaps:
        report.pop("gaps", None)
    if args.no_semantic:
        report.pop("semantic", None)
    if args.no_custom:
        report.pop("custom", None)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Scan AI harness config files.")
    parser.add_argument("repo_root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--max-bytes", type=int, default=32768)
    parser.add_argument("--no-security", action="store_true",
                        help="Skip the security checkup section.")
    parser.add_argument("--fail-on-security", action="store_true",
                        help="Exit non-zero when any HIGH-severity security finding is present.")
    parser.add_argument("--no-gaps", action="store_true",
                        help="Skip the missing / gap analysis section.")
    parser.add_argument("--fail-on-gaps", action="store_true",
                        help="Exit non-zero when any ERROR-level harness gap is present.")
    parser.add_argument("--no-semantic", action="store_true",
                        help="Skip the semantic consistency section (drops the `semantic` key).")
    parser.add_argument("--fail-on-semantic", action="store_true",
                        help="Exit non-zero when any AGENTS.md declaration contradicts the code.")
    parser.add_argument("--no-snapshot", action="store_true",
                        help="Skip the project snapshot section (drops the `project_snapshot` key).")
    parser.add_argument("--no-custom", action="store_true",
                        help="Skip custom rule plugins (drops the `custom` key).")
    parser.add_argument("--rules", action="append", default=None, metavar="DIR", dest="rules",
                        help="Directory of custom rule plugins (`*.py` exposing `check(root, context)`). "
                             "Repeatable; searched in addition to `<repo>/.ai-harness-doctor/rules/`.")
    parser.add_argument("--no-report-file", action="store_true",
                        help="Do not write the full JSON report to a temp file (markdown mode only).")
    parser.add_argument("--monorepo", action="store_true",
                        help="Force monorepo mode: scan each package subdir even without a "
                             "workspace config (falls back to nested package.json / AGENTS.md subtrees).")
    parser.add_argument("--no-monorepo", action="store_true",
                        help="Disable monorepo detection; scan only the repo root.")
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    report = scan_repo(root, args.max_bytes, args.rules)

    mode = "force" if args.monorepo else ("off" if args.no_monorepo else "auto")
    package_dirs, source = detect_packages(root, mode)
    if package_dirs:
        monorepo, packages = scan_monorepo(root, args.max_bytes, package_dirs, source, args.rules)
        report["monorepo"] = monorepo
        report["packages"] = packages
        for pkg in packages:
            _apply_section_flags(pkg["report"], args)

    _apply_section_flags(report, args)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        report_path = None if args.no_report_file else write_report_file(report, args.repo_root)
        print(render_markdown(report, report_path), end="")
    # Fail-on gates consider the root report and every package report so a
    # monorepo run cannot hide a failing package. In single-repo mode this is
    # exactly the previous behavior (only the root report is present).
    reports = [report] + [pkg["report"] for pkg in report.get("packages", [])]
    if args.fail_on_security and any(
            any(s["level"] == "HIGH" for s in r.get("security", [])) for r in reports):
        return 2
    if args.fail_on_gaps and any(
            any(g["level"] == "ERROR" for g in r.get("gaps", [])) for r in reports):
        return 3
    if args.fail_on_semantic and any(r.get("semantic", {}).get("findings") for r in reports):
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
