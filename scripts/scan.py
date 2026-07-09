#!/usr/bin/env python3
"""Scan AI harness configuration files and report overlap/conflicts."""

import argparse
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

# Markdown rendering lives in scan_render.py (ARCH-07) so this module stays
# focused on producing the report. Re-exported here so `scan.render_*` remains a
# stable import path for any external caller.
from scan_render import (  # noqa: E402,F401  (re-exported for backward compatibility)
    CATEGORY_LABELS,
    render_custom,
    render_gaps,
    render_markdown,
    render_monorepo,
    render_security,
    render_semantic,
    render_snapshot,
    render_surface,
)

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

# Secret-shaped tokens. Kept reasonably conservative to limit false positives;
# the goal is to flag obvious plaintext credentials committed into agent configs
# and MCP env values. Each pattern targets a concrete, high-confidence shape.
SECRET_PATTERNS = [
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{10,}\b")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    # Stripe live/restricted secret keys (sk_live_/rk_live_). Publishable
    # pk_live_ keys are intentionally excluded — they are not secret.
    ("Stripe secret key", re.compile(r"\b[sr]k_live_[0-9A-Za-z]{16,}\b")),
    # JSON Web Token: three base64url segments; the header (and usually the
    # payload) begin with the literal `eyJ` (base64 of `{"`).
    ("JSON Web Token", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----")),
    (
        "Generic hardcoded secret",
        # A credential-shaped key followed by `:`/`=` and a value that is either
        # quoted (>=12 non-space chars) OR unquoted but long/high-signal (>=16
        # credential chars with no spaces). The unquoted arm catches `.env`-style
        # `KEY=value` assignments that the quoted-only rule used to miss, while
        # the length/charset floor keeps prose from matching.
        re.compile(
            r"(?i)\b(?:api[_-]?key|secret(?:[_-]?key)?|access[_-]?key|client[_-]?secret|token|password|passwd|"
            r"auth[_-]?token|bearer)\b\s*[:=]\s*"
            r"(?:['\"][^'\"\s]{12,}['\"]|[A-Za-z0-9+/_\-.]{16,})"
        ),
    ),
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
# to it rather than full duplicated instruction sets. Derived from the shared
# agent-config registry (the same single source gen_adapters.py and check_drift.py
# use) rather than a hardcoded literal, so adding a tool to the registry
# automatically extends gap detection and the two stages cannot drift (TD-04).
GAP_STUB_FILES = [p for tool in registry.canonicalizable_tools() for p in tool["stub_paths"]]
# Maximum pointer-stub size, shared across scan/drift/canonicalize (see
# registry.STUB_POINTER_MAX_BYTES) so the threshold cannot drift between stages.
STUB_POINTER_MAX_BYTES = registry.STUB_POINTER_MAX_BYTES

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
    (
        "Python",
        [
            "pyproject.toml",
            "requirements.txt",
            "setup.py",
            "setup.cfg",
            "Pipfile",
            "poetry.lock",
            "uv.lock",
            "pdm.lock",
            "Pipfile.lock",
        ],
    ),
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
    (
        "ci",
        [
            ".github/workflows/*.yml",
            ".github/workflows/*.yaml",
            ".gitlab-ci.yml",
            ".circleci/config.yml",
            "azure-pipelines.yml",
            "Jenkinsfile",
            ".travis.yml",
            "buildkite.yml",
            ".drone.yml",
        ],
    ),
    (
        "hooks",
        [
            ".pre-commit-config.yaml",
            ".pre-commit-config.yml",
            ".githooks/*",
            ".husky/*",
            "lefthook.yml",
            "lefthook.yaml",
        ],
    ),
    (
        "lint_format",
        [
            ".eslintrc",
            ".eslintrc.*",
            "eslint.config.*",
            ".prettierrc",
            ".prettierrc.*",
            "prettier.config.*",
            "biome.json",
            "biome.jsonc",
            ".flake8",
            "ruff.toml",
            ".ruff.toml",
            ".pylintrc",
            ".golangci.yml",
            ".golangci.yaml",
            ".rubocop.yml",
            ".editorconfig",
            ".rustfmt.toml",
            "rustfmt.toml",
        ],
    ),
    (
        "typecheck",
        [
            "tsconfig.json",
            "mypy.ini",
            ".mypy.ini",
            "pyrightconfig.json",
        ],
    ),
]


def snapshot_tech_stack(root, ctx=None):
    """Detect the languages / ecosystems present via their manifest files."""
    ctx = ctx or ScanContext(root)
    stack = []
    for language, patterns in TECH_STACK_MARKERS:
        markers = []
        for pattern in patterns:
            for path in ctx.glob(pattern):
                if is_skipped(path, root) or not path.is_file():
                    continue
                markers.append(rel(path, root))
        if markers:
            stack.append({"language": language, "markers": sorted(set(markers))})
    return stack


def snapshot_existing_files(root, ctx=None):
    """Inventory CI / hook / lint / typecheck config files present in the repo."""
    ctx = ctx or ScanContext(root)
    groups = {}
    for group, patterns in SNAPSHOT_FILE_GROUPS:
        found = []
        for pattern in patterns:
            for path in ctx.glob(pattern):
                if is_skipped(path, root) or not path.is_file():
                    continue
                found.append(rel(path, root))
        groups[group] = sorted(set(found))
    # Pre-commit drift-guard hook (previously the static G5 check) is now a fact.
    guard_hook = None
    for rel_path in PRECOMMIT_HOOK_PATHS:
        path = root / rel_path
        if path.is_file():
            text = ctx.read_text(path)
            if text is not None and GUARD_MARKER in text:
                guard_hook = rel_path
                break
    groups["drift_guard_hook"] = guard_hook
    return groups


def build_project_snapshot(root, surface, agents_text, ctx=None):
    """Compact, factual description of the repo for agent-based gap inference."""
    ctx = ctx or ScanContext(root)
    sections = markdown_headings(agents_text, levels=(1,)) if agents_text else []
    return {
        "tech_stack": snapshot_tech_stack(root, ctx),
        "existing_files": snapshot_existing_files(root, ctx),
        "agents_sections": sections,
        "maintenance_contract": bool(agents_text) and "maintenance contract" in agents_text.lower(),
        "mcp_tools": [s["name"] for s in surface.get("mcp_servers", [])],
        "has_permissions": bool(surface.get("permissions")),
    }


def write_report_file(report, repo_root):
    """Dump the full JSON report to a temp file so an agent can read it back and
    reason over the machine-readable data (snapshot, gaps, surface, security)
    rather than re-parsing the markdown. Returns the file path, or None if
    writing failed (writing must never break the scan output).

    SEC-02: the report can contain sensitive scan data (secrets, hooks, config).
    It must NOT land at a predictable path in the world-writable temp dir — that
    invites a symlink-overwrite / info-leak attack. Use ``tempfile.mkstemp`` so
    the file is created atomically (O_EXCL, does not follow symlinks) with an
    unpredictable name and 0600 permissions, owned only by the current user.
    """
    del repo_root  # no longer used for naming; kept for call-site compatibility
    try:
        fd, path = tempfile.mkstemp(prefix="harness-scan-", suffix=".json")
    except OSError:
        return None
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(report, ensure_ascii=False, indent=2))
    except OSError:
        try:
            os.unlink(path)
        except OSError:
            pass
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


def build_file_index(root):
    """Walk ``root`` ONCE (pruning vendored dirs) and return every file under it.

    Returns a sorted list of ``(relposix, Path)`` for each regular file, with
    ``SKIP_DIRS`` (``.git`` / ``node_modules`` / ``dist`` / ``build`` /
    ``__pycache__``) pruned at the directory level so their — often enormous —
    subtrees are never descended. Every glob matcher in the scanner then runs
    against this single inventory (see :func:`index_glob`) instead of calling
    ``Path.glob`` once per pattern, which re-walked (and re-filtered) the whole
    tree ~90 times per scan (PERF-01).
    """
    root = Path(root)
    index = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        base = Path(dirpath)
        for name in filenames:
            path = base / name
            index.append((path.relative_to(root).as_posix(), path))
    index.sort(key=lambda item: item[0])
    return index


_GLOB_RE_CACHE = {}


def _compile_glob(pattern):
    """Translate a ``Path.glob``-style pattern to an anchored regex (cached).

    Supports the only wildcard features the scanner's patterns use: ``**``
    (zero or more path segments), ``*`` (any run of non-separator chars) and
    ``?`` (a single non-separator char); everything else is matched literally.
    Patterns are static, so compiled regexes are memoized for the process.
    """
    regex = _GLOB_RE_CACHE.get(pattern)
    if regex is not None:
        return regex
    segments = pattern.split("/")
    parts = ["^"]
    for i, seg in enumerate(segments):
        last = i == len(segments) - 1
        if seg == "**":
            # ``**`` matches this directory and any number of nested ones, so
            # ``a/**/b`` matches ``a/b`` as well as ``a/x/y/b``.
            parts.append("(?:[^/]+/)*")
        else:
            for ch in seg:
                if ch == "*":
                    parts.append("[^/]*")
                elif ch == "?":
                    parts.append("[^/]")
                else:
                    parts.append(re.escape(ch))
            if not last:
                parts.append("/")
    parts.append("$")
    regex = re.compile("".join(parts))
    _GLOB_RE_CACHE[pattern] = regex
    return regex


def index_glob(index, pattern):
    """Return the Paths in a file ``index`` matching a ``Path.glob`` pattern."""
    regex = _compile_glob(pattern)
    return [path for relposix, path in index if regex.match(relposix)]


class ScanContext:
    """Per-scan shared state so the repo tree is walked once and each config
    file is read/parsed at most once.

    - ``index`` is the single pruned file inventory (:func:`build_file_index`),
      reused by every glob matcher instead of re-walking the tree per pattern
      (PERF-01).
    - ``read_bytes`` / ``read_text`` / ``load_json`` memoize file reads and JSON
      parses, so a settings/MCP file consumed by ``scan_mcp``, ``scan_hooks``,
      ``scan_permissions`` and ``security_findings`` is only touched once, and
      ``AGENTS.md`` is not re-read by both ``scan_repo`` and ``find_gaps``
      (PERF-02).
    - :meth:`subcontext` slices the parent inventory (and shares the read/parse
      caches) for a package subdirectory so monorepo mode never re-walks a
      subtree the root scan already inventoried (PERF-03).
    """

    def __init__(self, root, index=None):
        self.root = Path(root)
        self.index = build_file_index(self.root) if index is None else index
        self._bytes = {}
        self._json = {}

    def glob(self, pattern):
        return index_glob(self.index, pattern)

    def read_bytes(self, path):
        key = str(path)
        if key not in self._bytes:
            try:
                self._bytes[key] = Path(path).read_bytes()
            except OSError:
                self._bytes[key] = None
        return self._bytes[key]

    def read_text(self, path, errors="replace"):
        data = self.read_bytes(path)
        if data is None:
            return None
        return data.decode("utf-8", errors=errors)

    def load_json(self, path):
        key = str(path)
        if key not in self._json:
            self._json[key] = load_json(path, ctx=self)
        return self._json[key]

    def subcontext(self, subroot):
        """Return a context scoped to ``subroot`` reusing this walk and caches."""
        subroot = Path(subroot).resolve()
        try:
            prefix = subroot.relative_to(self.root).as_posix()
        except ValueError:
            # Not under this root (should not happen): fall back to a fresh walk.
            return ScanContext(subroot)
        prefix = "" if prefix == "." else prefix + "/"
        sub_index = [
            (relposix[len(prefix):], path)
            for relposix, path in self.index
            if not prefix or relposix.startswith(prefix)
        ]
        sub = ScanContext.__new__(ScanContext)
        sub.root = subroot
        sub.index = sub_index
        sub._bytes = self._bytes  # share read cache across the whole scan
        sub._json = self._json
        return sub


def iter_matches(root, ctx=None):
    ctx = ctx or ScanContext(root)
    seen = {}
    for tool, patterns in CONFIG_PATTERNS:
        for pattern in patterns:
            for path in ctx.glob(pattern):
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
        warnings.append(
            {
                "level": "WARN",
                "path": rp,
                "message": f"{rp} is {size} bytes, above {max_bytes}; Codex "
                f"project_doc_max_bytes defaults to 32KB and may silently truncate context.",
            }
        )
        with path.open("rb") as fh:
            data = fh.read(max_bytes)
    else:
        if size > 12 * 1024:
            warnings.append(
                {
                    "level": "NOTICE",
                    "path": rp,
                    "message": f"{rp} is {size} bytes; this may cause context bloat.",
                }
            )
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
    punctuation = set(
        string.punctuation + "#*-_=|`~>\u3002\uff01\uff1f\u3001\uff0c\uff1b\uff1a\uff08\uff09\u3010\u3011\u300a\u300b"
    )
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
            overlaps.append(
                {
                    "a": a["path"],
                    "b": b["path"],
                    "shared_lines": len(shared),
                    "ratio": round(ratio, 4),
                    "percent": round(ratio * 100, 1),
                }
            )
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
    # Node version uses the shared registry regex so the scan conflict signal, the
    # Phase-0 semantic check and the Phase-2 D6 drift gate all extract the same
    # MAJOR-normalized value from a given line (TD-06). group(1) is the major.
    "node_version": [("node", registry.NODE_VERSION_RE)],
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
                # Preserve the full declared Node version (e.g. "node 18.17.0")
                # for user-facing evidence; conflict grouping normalizes it to
                # the major so 18 and 18.17.0 are not a false conflict (CORR-05).
                if signal == "node_version" and match.groupdict().get("version"):
                    actual = f"node {match.group('version')}"
                else:
                    actual = value
                signals.append(
                    {
                        "signal": signal,
                        "value": actual,
                        "path": file_entry["path"],
                        "line": lineno,
                        "evidence": line.strip(),
                    }
                )
    return signals


def _conflict_key(signal, value):
    """Return the normalization key used to decide if two signal values conflict.

    Version signals are compared by normalized semantic version so a bare major
    (``node 18``) is recognized as compatible with a fuller version
    (``node 18.17.0``) — only a differing MAJOR is a genuine conflict (CORR-05).
    All other signals compare by their exact value. Reuses the shared
    ``registry.node_version_major`` helper so scan agrees with the other stages.
    """
    if signal == "node_version":
        major = registry.node_version_major(value)
        if major is not None:
            return f"node {major}"
    return value


def find_conflicts(files):
    by_signal = {}
    for f in files:
        # De-duplicate within a file by CONFLICT KEY (not raw value) so two
        # compatible references in one file — e.g. "node 18" and "node 18.17.0"
        # — collapse to one entry instead of manufacturing a conflict.
        seen = {}
        for sig in extract_signals(f):
            seen[(sig["signal"], _conflict_key(sig["signal"], sig["value"]))] = sig
        for (signal, key), sig in seen.items():
            by_signal.setdefault(signal, {}).setdefault(key, []).append(sig)
    conflicts = []
    for signal, groups in by_signal.items():
        # A conflict needs at least two DISTINCT normalized values (keys).
        if len(groups) <= 1:
            continue
        conflicts.append(
            {
                "signal": signal,
                # Key the reported values by a representative actual value string
                # (the first occurrence) so users still see the real version(s).
                "values": {entries[0]["value"]: entries[:3] for entries in groups.values()},
            }
        )
    return conflicts


def nested_agents(files):
    return [f["path"] for f in files if f["path"].endswith("AGENTS.md") and "/" in f["path"]]


def load_json(path, ctx=None):
    try:
        if ctx is not None:
            data = ctx.read_bytes(path)
            if data is None:
                return None
            text = data.decode("utf-8")
        else:
            text = Path(path).read_text(encoding="utf-8")
        return json.loads(text)
    except Exception:
        return None


def glob_files(root, patterns, ctx=None):
    ctx = ctx or ScanContext(root)
    seen = {}
    for pattern in patterns:
        for path in ctx.glob(pattern):
            if is_skipped(path, root) or not path.is_file():
                continue
            seen.setdefault(rel(path, root), path)
    return [seen[k] for k in sorted(seen)]


def scan_mcp(root, ctx=None):
    ctx = ctx or ScanContext(root)
    servers = []
    for rel_path in MCP_CONFIG_FILES:
        path = root / rel_path
        if not path.is_file():
            continue
        data = ctx.load_json(path)
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
            servers.append(
                {
                    "config": rel(path, root),
                    "name": name,
                    "transport": transport,
                    "command": str(cfg.get("command", "")),
                    "url": str(url),
                    "env_keys": sorted(env.keys()),
                }
            )
    return servers


def scan_subagents(root, ctx=None):
    ctx = ctx or ScanContext(root)
    return [rel(p, root) for p in glob_files(root, SUBAGENT_PATTERNS, ctx)]


def scan_commands(root, ctx=None):
    ctx = ctx or ScanContext(root)
    return [rel(p, root) for p in glob_files(root, COMMAND_PATTERNS, ctx)]


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


def scan_hooks(root, ctx=None):
    ctx = ctx or ScanContext(root)
    hooks = []
    for rel_path in SETTINGS_FILES:
        path = root / rel_path
        if not path.is_file():
            continue
        data = ctx.load_json(path)
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


def scan_permissions(root, ctx=None):
    ctx = ctx or ScanContext(root)
    perms = []
    for rel_path in SETTINGS_FILES:
        path = root / rel_path
        if not path.is_file():
            continue
        data = ctx.load_json(path)
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


def security_findings(root, files, mcp, hooks, permissions, ctx=None):
    ctx = ctx or ScanContext(root)
    findings = []
    # 1) Plaintext secrets in instruction/rule files.
    for f in files:
        for label in secret_hits(f["text"]):
            findings.append(
                {
                    "level": "HIGH",
                    "category": "secret",
                    "path": f["path"],
                    "message": f"Possible {label} committed in {f['path']}",
                }
            )
    # Raw MCP/settings config files are not in `files`; scan them directly.
    for rel_path in sorted(set(MCP_CONFIG_FILES) | set(SETTINGS_FILES)):
        path = root / rel_path
        if not path.is_file():
            continue
        text = ctx.read_text(path)
        if text is None:
            continue
        for label in secret_hits(text):
            findings.append(
                {
                    "level": "HIGH",
                    "category": "secret",
                    "path": rel_path,
                    "message": f"Possible {label} committed in {rel_path}",
                }
            )
    # 1b) Secret-shaped values inside MCP server `env` maps. JSON-quoted
    # `"KEY": "value"` assignments slip past the generic key=value rule (the
    # quote before the colon breaks it), so inspect each env value directly and
    # attribute the finding to the exact server/key.
    seen_env_secrets = set()
    for rel_path in MCP_CONFIG_FILES:
        path = root / rel_path
        if not path.is_file():
            continue
        data = ctx.load_json(path)
        if not isinstance(data, dict):
            continue
        block = data.get("mcpServers") or data.get("servers") or {}
        if not isinstance(block, dict):
            continue
        for name, cfg in block.items():
            env = cfg.get("env") if isinstance(cfg, dict) else None
            if not isinstance(env, dict):
                continue
            for key, value in env.items():
                if not isinstance(value, str):
                    continue
                for label in secret_hits(value):
                    dedupe_key = (rel_path, name, key, label)
                    if dedupe_key in seen_env_secrets:
                        continue
                    seen_env_secrets.add(dedupe_key)
                    findings.append(
                        {
                            "level": "HIGH",
                            "category": "secret",
                            "path": rel_path,
                            "message": f"Possible {label} in MCP server `{name}` env `{key}`",
                        }
                    )
    # 2) MCP transport / credential hygiene.
    for s in mcp:
        if s["url"].startswith("http://"):
            findings.append(
                {
                    "level": "MEDIUM",
                    "category": "mcp",
                    "path": s["config"],
                    "message": f"MCP server `{s['name']}` uses insecure http:// transport",
                }
            )
        for key in s["env_keys"]:
            if re.search(r"(?i)key|token|secret|password", key):
                findings.append(
                    {
                        "level": "MEDIUM",
                        "category": "mcp",
                        "path": s["config"],
                        "message": f"MCP server `{s['name']}` sets credential-shaped "
                        f"env `{key}`; reference an env var instead of a literal",
                    }
                )
    # 3) Permission breadth.
    for p in permissions:
        for entry in p.get("allow", []):
            if BROAD_PERMISSION_RE.search(entry.strip()):
                findings.append(
                    {
                        "level": "HIGH",
                        "category": "permission",
                        "path": p["config"],
                        "message": f"Overly broad allow rule `{entry}` grants unrestricted execution",
                    }
                )
        mode = p.get("defaultMode", "")
        if mode == "bypassPermissions":
            findings.append(
                {
                    "level": "HIGH",
                    "category": "permission",
                    "path": p["config"],
                    "message": "permissions.defaultMode is `bypassPermissions` (no confirmation prompts)",
                }
            )
        elif mode == "acceptEdits":
            findings.append(
                {
                    "level": "MEDIUM",
                    "category": "permission",
                    "path": p["config"],
                    "message": "permissions.defaultMode is `acceptEdits` (edits auto-approved)",
                }
            )
    # 4) Risky hook / command bodies.
    for h in hooks:
        for label, pattern in RISKY_COMMAND_RES:
            if pattern.search(h["command"]):
                findings.append(
                    {
                        "level": "HIGH",
                        "category": "hook",
                        "path": h["config"],
                        "message": f"{h['event']} hook contains {label}: `{h['command'][:80]}`",
                    }
                )
    # 5) Risky flags recommended inside instruction files.
    for f in files:
        for label, pattern in RISKY_COMMAND_RES:
            if label == "permission bypass flag" and pattern.search(f["text"]):
                findings.append(
                    {
                        "level": "MEDIUM",
                        "category": "instruction",
                        "path": f["path"],
                        "message": f"Instruction file recommends a {label}",
                    }
                )
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


def find_gaps(root, surface, ctx=None):
    """Diff the repo against a harness completeness checklist and report what is
    missing. Read-only: never writes or mutates the target repository."""
    ctx = ctx or ScanContext(root)
    gaps = []
    agents = root / "AGENTS.md"

    # 1) Canonical root AGENTS.md must exist — the single source of truth.
    if not agents.is_file():
        gaps.append(
            gap(
                "G1",
                "ERROR",
                "Root AGENTS.md",
                "No canonical `AGENTS.md` at the repository root.",
                "Create a root AGENTS.md (see assets/AGENTS.template.md), then run canonicalize.py --write-stubs.",
            )
        )
        agents_text = ""
    else:
        agents_text = ctx.read_text(agents) or ""

    # 2) Required sections present in AGENTS.md.
    if agents.is_file():
        present = [h.lower() for h in markdown_headings(agents_text)]
        for section in required_sections():
            needle = section.lower()
            if not any(needle == h or needle in h for h in present):
                gaps.append(
                    gap(
                        "G2",
                        "WARN",
                        f"Section: {section}",
                        f"AGENTS.md is missing the `{section}` section.",
                        f"Add a `# {section}` section describing what agents cannot infer from code alone.",
                    )
                )

    # 3) Tool stubs should be minimal pointers to AGENTS.md, not full duplicates.
    if agents.is_file():
        for rel_path in GAP_STUB_FILES:
            path = root / rel_path
            if not path.is_file():
                continue
            data = ctx.read_bytes(path)
            if data is None:
                continue
            text = data.decode("utf-8", errors="replace")
            if len(data) > STUB_POINTER_MAX_BYTES or "AGENTS.md" not in text:
                gaps.append(
                    gap(
                        "G3",
                        "WARN",
                        f"Stub pointer: {rel_path}",
                        f"`{rel_path}` exists but is not a minimal pointer to AGENTS.md "
                        f"({len(data)} bytes; pointer must be <= "
                        f"{STUB_POINTER_MAX_BYTES} bytes and reference AGENTS.md).",
                        "Run canonicalize.py --write-stubs to downgrade it to a pointer.",
                    )
                )

    # 4) Drift guard / checkup CI workflows.
    for rel_path, level, item in GUARD_CI_WORKFLOWS:
        if not (root / rel_path).is_file():
            gaps.append(
                gap(
                    "G4",
                    level,
                    item,
                    f"`{rel_path}` is not installed.",
                    "Run `ai-harness-doctor guard . --apply` to install the guard suite.",
                )
            )

    # G5-G8 (pre-commit drift guard, maintenance contract, MCP configuration,
    # permission configuration) used to be reported here as static gaps. They
    # are stack-dependent judgement calls rather than mandatory infrastructure,
    # so they are now surfaced as facts in `project_snapshot`, which an agent can
    # read from the full JSON report (see write_report_file) to reason about.
    order = {"ERROR": 0, "WARN": 1, "NOTICE": 2}
    return sorted(gaps, key=lambda g: (order.get(g["level"], 3), g["check"]))


def scan_repo(repo_root, max_bytes, rules_dirs=None, allow_plugins=False, ctx=None):
    root = Path(repo_root).resolve()
    # Walk the tree once and share the read/parse cache across every stage below
    # (PERF-01/PERF-02). In monorepo mode the caller passes a subcontext sliced
    # from the parent inventory so package subtrees are not re-walked (PERF-03).
    ctx = ctx or ScanContext(root)
    files = []
    warnings = []
    for tool, path in iter_matches(root, ctx):
        info = file_info(root, tool, path, max_bytes)
        warnings.extend(info.pop("warnings"))
        files.append(info)
    result_files = [{k: v for k, v in f.items() if k != "text"} for f in files]
    mcp = scan_mcp(root, ctx)
    hooks = scan_hooks(root, ctx)
    permissions = scan_permissions(root, ctx)
    surface = {
        "mcp_servers": mcp,
        "subagents": scan_subagents(root, ctx),
        "commands": scan_commands(root, ctx),
        "hooks": hooks,
        "permissions": permissions,
    }
    agents_path = root / "AGENTS.md"
    agents_text = (ctx.read_text(agents_path) or "") if agents_path.is_file() else ""
    report = {
        "files": result_files,
        "warnings": warnings,
        "overlaps": find_overlaps(files),
        "conflicts": find_conflicts(files),
        "nested": nested_agents(result_files),
        "surface": surface,
        "security": security_findings(root, files, mcp, hooks, permissions, ctx),
        "project_snapshot": build_project_snapshot(root, surface, agents_text, ctx),
        "semantic": semantic.analyze(root, agents_text),
        "gaps": find_gaps(root, surface, ctx),
    }
    # User-extensible deterministic rule plugins (opt-in, default OFF). Plugin
    # files live inside the scanned repo, so importing them runs arbitrary code
    # on the host/CI; discovery + execution therefore happens ONLY when the
    # caller opts in via --allow-plugins. Otherwise this is a no-op returning an
    # empty list. Discovered from <root>/.ai-harness-doctor/rules/*.py plus any
    # --rules DIR; each plugin is isolated so a broken one is reported as an
    # ERROR finding, never a crash. The key is always present (empty list when
    # no plugins ran) and rendered under its own "Custom rule plugins" section.
    context = {"phase": "scan", "agents_text": agents_text}
    report["custom"] = plugins.run_plugins(root, context, rules_dirs, allow_plugins=allow_plugins)
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


def scan_monorepo(root, max_bytes, package_dirs, source, rules_dirs=None, allow_plugins=False, ctx=None):
    """Scan every detected package subdirectory and build the aggregate.

    Returns ``(monorepo_summary, packages)`` where ``packages`` is a list of
    ``{path, name, has_agents_md, summary, report}`` (each ``report`` is a plain
    single-repo :func:`scan_repo` result so there is never nested recursion).
    """
    ctx = ctx or ScanContext(root)
    packages = []
    for relpath, pdir in package_dirs.items():
        # Reuse the root walk + read cache by slicing a subcontext for the
        # package instead of re-walking (and re-reading) its subtree (PERF-03).
        sub = scan_repo(pdir, max_bytes, rules_dirs, allow_plugins=allow_plugins, ctx=ctx.subcontext(pdir))
        packages.append(
            {
                "path": relpath,
                "name": _package_name(pdir),
                "has_agents_md": (pdir / "AGENTS.md").is_file(),
                "summary": _package_summary(sub),
                "report": sub,
            }
        )
    monorepo = {
        "source": source,
        "package_count": len(packages),
        "aggregate": _aggregate_packages(packages),
    }
    return monorepo, packages


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
    parser.add_argument("--no-security", action="store_true", help="Skip the security checkup section.")
    parser.add_argument(
        "--fail-on-security",
        action="store_true",
        help="Exit non-zero when any HIGH-severity security finding is present.",
    )
    parser.add_argument("--no-gaps", action="store_true", help="Skip the missing / gap analysis section.")
    parser.add_argument(
        "--fail-on-gaps", action="store_true", help="Exit non-zero when any ERROR-level harness gap is present."
    )
    parser.add_argument(
        "--no-semantic", action="store_true", help="Skip the semantic consistency section (drops the `semantic` key)."
    )
    parser.add_argument(
        "--fail-on-semantic",
        action="store_true",
        help="Exit non-zero when any AGENTS.md declaration contradicts the code.",
    )
    parser.add_argument(
        "--no-snapshot",
        action="store_true",
        help="Skip the project snapshot section (drops the `project_snapshot` key).",
    )
    parser.add_argument("--no-custom", action="store_true", help="Skip custom rule plugins (drops the `custom` key).")
    parser.add_argument(
        "--allow-plugins",
        action="store_true",
        help="Opt in to executing custom rule plugins (`*.py`) found inside the scanned repo "
        "or in --rules DIRs. SECURITY: this runs arbitrary code from the target repository; "
        "it is OFF by default and no plugin code is discovered or imported without this flag.",
    )
    parser.add_argument(
        "--rules",
        action="append",
        default=None,
        metavar="DIR",
        dest="rules",
        help="Directory of custom rule plugins (`*.py` exposing `check(root, context)`). "
        "Repeatable; searched in addition to `<repo>/.ai-harness-doctor/rules/`.",
    )
    parser.add_argument(
        "--no-report-file",
        action="store_true",
        help="Do not write the full JSON report to a temp file (markdown mode only).",
    )
    parser.add_argument(
        "--monorepo",
        action="store_true",
        help="Force monorepo mode: scan each package subdir even without a "
        "workspace config (falls back to nested package.json / AGENTS.md subtrees).",
    )
    parser.add_argument(
        "--no-monorepo", action="store_true", help="Disable monorepo detection; scan only the repo root."
    )
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    # Single shared scan context: the repo tree is walked once here and the same
    # read/parse cache is reused by the root scan and every package scan below.
    ctx = ScanContext(root)
    # Executing plugins runs untrusted code from the scanned repo; warn loudly.
    if args.allow_plugins:
        print(
            "WARNING: --allow-plugins enabled: executing untrusted rule plugin code from the "
            "scanned repository (<repo>/.ai-harness-doctor/rules/ and any --rules DIR).",
            file=sys.stderr,
        )
    report = scan_repo(root, args.max_bytes, args.rules, allow_plugins=args.allow_plugins, ctx=ctx)

    mode = "force" if args.monorepo else ("off" if args.no_monorepo else "auto")
    package_dirs, source = detect_packages(root, mode)
    if package_dirs:
        monorepo, packages = scan_monorepo(
            root, args.max_bytes, package_dirs, source, args.rules, allow_plugins=args.allow_plugins, ctx=ctx
        )
        report["monorepo"] = monorepo
        report["packages"] = packages

    # Evaluate the fail-on gates on the ACTUAL findings BEFORE the --no-* flags
    # suppress any report sections. Otherwise --no-security would pop the security
    # section and silently neuter --fail-on-security, letting HIGH findings pass
    # with exit 0 (CORR-03). --no-security must only hide the section from the
    # printed report, never disable the gate. Precedence: security > gaps >
    # semantic, matching the previous return order. Fail-on gates consider the
    # root report and every package report so a monorepo run cannot hide a
    # failing package.
    reports = [report] + [pkg["report"] for pkg in report.get("packages", [])]
    exit_code = 0
    if args.fail_on_security and any(any(s["level"] == "HIGH" for s in r.get("security", [])) for r in reports):
        exit_code = 2
    elif args.fail_on_gaps and any(any(g["level"] == "ERROR" for g in r.get("gaps", [])) for r in reports):
        exit_code = 3
    elif args.fail_on_semantic and any(r.get("semantic", {}).get("findings") for r in reports):
        exit_code = 4

    # Output suppression only: drop optional sections per the --no-* flags. This
    # runs AFTER the gate decision above so suppression cannot change the exit.
    for pkg in report.get("packages", []):
        _apply_section_flags(pkg["report"], args)
    _apply_section_flags(report, args)

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        report_path = None if args.no_report_file else write_report_file(report, args.repo_root)
        print(render_markdown(report, report_path), end="")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
