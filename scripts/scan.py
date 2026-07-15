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
import facts  # noqa: E402  # contained repository fact reads
import plugins  # noqa: E402  # user-extensible deterministic rule plugins
import registry  # noqa: E402
import semantic  # noqa: E402  # declaration-vs-fact consistency engine

# Markdown rendering lives in scan_render.py (ARCH-07) so this module stays
# focused on producing the report. Re-exported here so `scan.render_*` remains a
# stable import path for any external caller.
from scan_render import (  # noqa: E402,F401  (re-exported for backward compatibility)
    CATEGORY_LABELS,
    render_baseline,
    render_custom,
    render_gaps,
    render_markdown,
    render_monorepo,
    render_repos_file,
    render_security,
    render_semantic,
    render_snapshot,
    render_surface,
)

SKIP_DIRS = registry.SKIP_DIRS

# Scan baselines are an auditable register of known non-security debt. Security
# findings are deliberately absent from this allow-list so neither a generated
# nor hand-crafted baseline can suppress a credential or unsafe permission.
SCAN_BASELINE_VERSION = 1
SCAN_BASELINE_FAMILIES = {"gap", "semantic", "conflict"}
_LINE_EVIDENCE_RE = re.compile(
    r"(?P<path>(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+):\d+\b"
)


def _without_line_evidence(text):
    """Normalize file:line evidence so unrelated line shifts keep identity."""
    return _LINE_EVIDENCE_RE.sub(r"\g<path>:<line>", str(text or ""))


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

# Documentation/example placeholders, not real committed secrets — checked
# against the MATCHED SPAN only (not the whole line), so an unrelated comment
# elsewhere on the same line can't hide a genuine secret. Found scanning
# continuedev/continue's `.continue/rules/dev-data-guide.md`, which has
# `apiKey: "your-api-key-here"` in an example config block; that shape passes
# every other check (quoted, 12+ chars, no spaces) and was flagged HIGH.
_SECRET_PLACEHOLDER_RE = re.compile(
    r"\byour[_-]|\bmy[_-]|\bexample\b|\bsample\b|\bdummy\b|\bplaceholder\b|\bchangeme\b|"
    r"\bxxx|\binsert[_-]|\bredacted\b|\bhere\b|<[^<>]*>|\$\{",
    re.I,
)

# Permission entries that grant broad/unrestricted execution. A wildcard rule
# is "broad" only when the COMMAND itself is unconstrained: `Bash(*)`,
# `Execute(*)`, `Shell(*)`, a bare `*`, or a wildcard command such as
# `Bash(*:*)`. An argument wildcard on a *named* command (`Bash(git log:*)`,
# `Bash(rg:*)`, `Bash(uv run:*)`) is Claude Code's recommended per-command
# scoping, NOT unrestricted execution, so it must not be flagged — the old
# `:\s*\*\s*\)$` alternative matched every `cmd:*` rule and buried real repos
# (e.g. pydantic-ai's 19 scoped rules) under spurious HIGH findings that break
# `--fail-on-security` CI.
BROAD_PERMISSION_RE = re.compile(r"^(?:Bash|Execute|Shell)?\(\s*\*+\s*\)$|^\*$|\(\s*\*+\s*:")
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
        if facts.is_file_within_root(root, path):
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


def _resolves_within_root(path, resolved_root):
    """Return True only when an existing path resolves inside a normalized root."""
    return facts.resolves_within_root(path, resolved_root)


def build_file_index(root):
    """Walk ``root`` ONCE (pruning vendored dirs) and return every file under it.

    Returns a sorted list of ``(relposix, Path)`` for each regular file, with
    ``SKIP_DIRS`` (``.git`` / ``node_modules`` / ``dist`` / ``build`` /
    ``__pycache__``) pruned at the directory level so their — often enormous —
    subtrees are never descended. Every glob matcher in the scanner then runs
    against this single inventory (see :func:`index_glob`) instead of calling
    ``Path.glob`` once per pattern, which re-walked (and re-filtered) the whole
    tree ~90 times per scan (PERF-01).

    File symlinks are allowed only when their resolved target remains inside the
    audited root. This preserves intentional in-repo aliases while preventing a
    matched config path from making the read-only scanner ingest content outside
    the repository boundary (SEC-03).
    """
    root = Path(root).resolve()
    index = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        base = Path(dirpath)
        for name in filenames:
            path = base / name
            if not _resolves_within_root(path, root):
                continue
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
        self.root = Path(root).resolve()
        self.index = build_file_index(self.root) if index is None else index
        self._bytes = {}
        self._json = {}

    def glob(self, pattern):
        return index_glob(self.index, pattern)

    def read_bytes(self, path):
        key = str(path)
        if key not in self._bytes:
            self._bytes[key] = facts.read_bytes_within_root(self.root, path)
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
            (relposix[len(prefix) :], path)
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
    safe_path = facts.resolve_within_root(path, root)
    if safe_path is None:
        raise OSError(f"refusing to read path outside repository: {rp}")
    # Stat the file first so an oversize (accidentally matched) file is not
    # fully read into memory before the size check. We still read the body for
    # normally-sized files; oversize files are read only up to max_bytes.
    size = safe_path.stat().st_size
    if size > max_bytes:
        warnings.append(
            {
                "level": "WARN",
                "path": rp,
                "message": f"{rp} is {size} bytes, above {max_bytes}; Codex "
                f"project_doc_max_bytes defaults to 32KB and may silently truncate context.",
            }
        )
        with safe_path.open("rb") as fh:
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
        data = safe_path.read_bytes()
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


def _line_overlap(text_a, text_b):
    """Return ``(shared_line_count, ratio)`` of normalized-line overlap between
    two texts, or ``None`` if either has no comparable content. ``ratio`` is
    shared lines over the SMALLER file's line count. Factored out of
    :func:`find_overlaps` so :func:`find_wholesale_dumping` reuses the exact
    same similarity metric instead of a second bespoke heuristic."""
    la, lb = set(normalized_lines(text_a)), set(normalized_lines(text_b))
    if not la or not lb:
        return None
    shared = la & lb
    return len(shared), len(shared) / float(min(len(la), len(lb)))


def find_overlaps(files):
    overlaps = []
    texts = {f["path"]: f["text"] for f in files}
    for a, b in combinations(files, 2):
        overlap = _line_overlap(texts[a["path"]], texts[b["path"]])
        if overlap is None:
            continue
        shared, ratio = overlap
        if ratio > 0.30:
            overlaps.append(
                {
                    "a": a["path"],
                    "b": b["path"],
                    "shared_lines": shared,
                    "ratio": round(ratio, 4),
                    "percent": round(ratio * 100, 1),
                }
            )
    return sorted(overlaps, key=lambda x: x["ratio"], reverse=True)


# Thresholds for the Wholesale Dumping check (see find_wholesale_dumping):
# higher than find_overlaps's 30% because AGENTS.md and README.md serve
# different audiences and some natural overlap (project name, one-line
# description) is expected and not itself a problem; a minimum shared-line
# floor avoids noise on very short files where a handful of coincidental
# matches would otherwise cross the ratio threshold.
_WHOLESALE_DUMPING_RATIO = 0.5
_WHOLESALE_DUMPING_MIN_SHARED_LINES = 5


def find_wholesale_dumping(root, agents_text, ctx=None):
    """SKILL.md's "Wholesale Dumping" anti-pattern: AGENTS.md content copied
    verbatim from README.md instead of distilled into agent-specific,
    non-inferable rules. See :func:`find_silent_adjudication` for the sibling
    check covering SKILL.md's other named anti-pattern; together they complete
    code support for all five (Copy-Paste Stubs / D3, Silent Truncation / D4,
    and Big-Bang Migration / the phased workflow itself already had it).
    """
    if not agents_text:
        return []
    ctx = ctx or ScanContext(root)
    readme = root / "README.md"
    if not facts.is_file_within_root(root, readme):
        return []
    readme_text = ctx.read_text(readme) or ""
    overlap = _line_overlap(agents_text, readme_text)
    if overlap is None:
        return []
    shared, ratio = overlap
    if ratio <= _WHOLESALE_DUMPING_RATIO or shared < _WHOLESALE_DUMPING_MIN_SHARED_LINES:
        return []
    return [
        gap(
            "G9",
            "WARN",
            "Wholesale dumping: AGENTS.md ↔ README.md",
            f"AGENTS.md shares {round(ratio * 100, 1)}% of its normalized lines with `README.md` "
            f"({shared} shared lines) — content looks copied wholesale rather than distilled "
            'into agent-specific rules (SKILL.md\'s "Wholesale Dumping" anti-pattern).',
            "Keep only rules an agent cannot infer from code or README alone; replace duplicated "
            "project-description prose with a brief pointer to README.md.",
        )
    ]


# Phrases whose presence in AGENTS.md indicates a signal conflict WAS
# surfaced for human review rather than picked silently. Kept short and
# generic so it works across every conflict signal (package manager, node
# version, formatter, ...), not just package_manager.
_ADJUDICATION_MARKERS = re.compile(
    r"instead of|rather than|migrated from|replaces|chosen over|decision:|decided by|"
    r"adjudicat|see merge-plan|per (?:team|owner|maintainer|stakeholder)|confirmed by",
    re.I,
)


def find_silent_adjudication(agents_text, conflicts):
    """SKILL.md's "Silent Adjudication" anti-pattern: AGENTS.md declares one
    side of a live signal conflict (e.g. `pnpm` over `npm`) with no trace that
    the losing value was ever surfaced for the repo owner to adjudicate, as
    the conflict-resolution escalation path requires. Reuses ``find_conflicts``
    — which already scans AGENTS.md alongside every other tool file — so a
    conflict entry with one AGENTS.md-sourced value and one still-live
    non-AGENTS.md value is exactly this anti-pattern's signature.
    """
    if not agents_text or not conflicts:
        return []
    if _ADJUDICATION_MARKERS.search(agents_text):
        return []
    gaps_found = []
    for conflict in conflicts:
        agents_entry = None
        other_entries = []
        for entries in conflict["values"].values():
            source = next((e for e in entries if e["path"] == "AGENTS.md"), None)
            if source:
                agents_entry = source
            else:
                other_entries.append(entries[0])
        if agents_entry is None or not other_entries:
            continue
        # Word-boundary search, not substring: "npm" is a substring of "pnpm"
        # and a plain `in` check would wrongly treat that as a mention.
        unmentioned = [e for e in other_entries if not re.search(rf"\b{re.escape(e['value'])}\b", agents_text, re.I)]
        if not unmentioned:
            continue
        others = ", ".join(f"`{e['value']}` ({e['path']}:{e['line']})" for e in unmentioned)
        gaps_found.append(
            gap(
                "G10",
                "WARN",
                f"Silent adjudication: {conflict['signal']}",
                f"AGENTS.md declares `{agents_entry['value']}` for `{conflict['signal']}` "
                f"(AGENTS.md:{agents_entry['line']}), but {others} still disagrees, with no "
                "trace of adjudication in AGENTS.md — no mention of the other value, no "
                'rationale like "instead of" / "migrated from" — SKILL.md\'s "Silent '
                'Adjudication" anti-pattern.',
                "Cite both values with file:line evidence and let the repo owner adjudicate, "
                'or add a short rationale (e.g. "pnpm, migrated from npm") if already decided.',
            )
        )
    return gaps_found


SIGNAL_PATTERNS = {
    "package_manager": [
        ("pnpm", re.compile(r"\bpnpm\b")),
        # Two npm phrasings that are not a "use npm" signal, both found
        # scanning vercel/ai's AGENTS.md:
        # 1. `npm install -g pnpm`/`yarn`/`bun` bootstraps ANOTHER package
        #    manager via npm (npm ships with Node, so it's the standard way to
        #    install the others globally): "`npm install -g pnpm@10`".
        # 2. "`ai` on npm" names the npm REGISTRY a package is published to,
        #    regardless of which tool the project itself uses to install.
        # Both manufactured a bogus npm-vs-pnpm conflict.
        (
            "npm",
            re.compile(r"(?<!on )\bnpm\b(?!\s+(?:install|i|add)\s+(?:-g|--global)\s+(?:pnpm|yarn|bun)\b)"),
        ),
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
        negated = registry.negated_spans(line)
        pm_enumeration = registry.pm_enumeration_spans(line)
        for signal, patterns in SIGNAL_PATTERNS.items():
            for value, pattern in patterns:
                match = pattern.search(line)
                if not match:
                    continue
                # A package manager named inside a slash-joined enumeration —
                # "auto-detects npm/yarn/pnpm workspaces" — lists a supported
                # tool, not the one this repo uses; skip it so the enumeration
                # does not manufacture a false package_manager conflict.
                if signal == "package_manager" and any(
                    start <= match.start() < end for start, end in pm_enumeration
                ):
                    continue
                # A value named only as a rejected alternative — "ALWAYS use
                # `pnpm` (never npm, yarn, or bun)" — is not a declaration
                # that this repo uses npm/yarn/bun (found scanning
                # better-auth/better-auth's AGENTS.md, where this
                # manufactured a bogus 4-way package_manager conflict).
                if any(start <= match.start() < end for start, end in negated):
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


def _path_parts(path):
    """Repository-relative POSIX path components (component-safe ancestry)."""
    return tuple(part for part in str(path).replace("\\", "/").split("/") if part not in ("", "."))


def _scope_path(path):
    parts = _path_parts(path)
    return "." if len(parts) <= 1 else "/".join(parts[:-1])


def _is_scope_ancestor(ancestor, descendant):
    if ancestor == ".":
        return descendant != "."
    ancestor_parts = _path_parts(ancestor)
    descendant_parts = _path_parts(descendant)
    return len(ancestor_parts) < len(descendant_parts) and descendant_parts[: len(ancestor_parts)] == ancestor_parts


def instruction_scope_map(files):
    """Return canonical scope rows plus each config file's effective scope.

    A canonical scope is the parent directory of AGENTS.md/AGENT.md. Every
    config file belongs to its deepest canonical ancestor; files outside a
    nested scope use the virtual repository-root scope ``"."``.
    """
    canonical_order = {name: index for index, name in enumerate(registry.load_canonical())}
    canonical_files = []
    for file_entry in files:
        parts = _path_parts(file_entry.get("path", ""))
        if parts and parts[-1] in canonical_order:
            canonical_files.append((file_entry["path"], _scope_path(file_entry["path"]), canonical_order[parts[-1]]))

    scope_names = {"."}
    scope_names.update(scope for _path, scope, _order in canonical_files)

    def nearest_parent(scope):
        if scope == ".":
            return None
        ancestors = [candidate for candidate in scope_names if _is_scope_ancestor(candidate, scope)]
        return max(ancestors, key=lambda candidate: len(_path_parts(candidate)), default=".")

    rows = [
        {"path": path, "scope": scope, "parent": nearest_parent(scope)}
        for path, scope, _order in sorted(
            canonical_files,
            key=lambda item: (len(_path_parts(item[1])), item[1], item[2], item[0]),
        )
    ]

    file_scopes = {
        file_entry["path"]: effective_instruction_scope(file_entry["path"], scope_names)
        for file_entry in files
    }
    parent_by_scope = {scope: nearest_parent(scope) for scope in scope_names}
    return rows, file_scopes, parent_by_scope


def effective_instruction_scope(path, scope_names, path_is_directory=False):
    """Return the deepest lexical canonical scope applying to ``path``."""
    target = str(path) if path_is_directory else _scope_path(path)
    target_parts = _path_parts(target)
    candidates = ["."]
    for scope in scope_names:
        if scope == ".":
            continue
        scope_parts = _path_parts(scope)
        if target_parts[: len(scope_parts)] == scope_parts:
            candidates.append(scope)
    return max(candidates, key=lambda candidate: len(_path_parts(candidate)))


def instruction_scope_chain(scope, parent_by_scope):
    """Return lexical scope names from repository root to ``scope``."""
    chain = []
    current = scope
    while current is not None:
        chain.append(current)
        current = parent_by_scope.get(current)
    if "." not in chain:
        chain.append(".")
    return list(reversed(chain))


def analyze_scoped_conflicts(files):
    """Return ``(instruction_scopes, conflicts, non-blocking overrides)``."""
    scope_rows, file_scopes, parent_by_scope = instruction_scope_map(files)
    by_scope = {}
    for f in files:
        # De-duplicate within a file by CONFLICT KEY (not raw value) so two
        # compatible references in one file — e.g. "node 18" and "node 18.17.0"
        # — collapse to one entry instead of manufacturing a conflict.
        seen = {}
        for sig in extract_signals(f):
            seen[(sig["signal"], _conflict_key(sig["signal"], sig["value"]))] = sig
        scope = file_scopes.get(f["path"], ".")
        for (signal, key), sig in seen.items():
            by_scope.setdefault(scope, {}).setdefault(signal, {}).setdefault(key, []).append(sig)

    conflicts = []
    for scope in sorted(by_scope, key=lambda value: (len(_path_parts(value)), value)):
        for signal, groups in by_scope[scope].items():
            # A conflict needs at least two DISTINCT normalized values (keys).
            if len(groups) <= 1:
                continue
            # ESLint + Prettier are complementary, not competing formatters.
            if signal == "formatter":
                distinct = {entries[0]["value"].lower() for entries in groups.values()}
                if distinct <= {"prettier", "eslint"}:
                    continue
            conflict = {
                "signal": signal,
                "values": {entries[0]["value"]: entries[:3] for entries in groups.values()},
            }
            # Preserve the historical root conflict shape byte-for-byte.
            if scope != ".":
                conflict["scope"] = scope
            conflicts.append(conflict)

    overrides = []
    for scope in sorted(by_scope, key=lambda value: (len(_path_parts(value)), value)):
        if scope == ".":
            continue
        for signal, groups in by_scope[scope].items():
            ancestor = parent_by_scope.get(scope)
            while ancestor is not None and signal not in by_scope.get(ancestor, {}):
                ancestor = parent_by_scope.get(ancestor)
            if ancestor is None:
                continue
            parent_groups = by_scope[ancestor][signal]
            # Repeating only a subset of inherited values is not an override:
            # absence does not revoke ancestor guidance. Record a child scope
            # only when it introduces at least one normalized value its nearest
            # signal-bearing ancestor did not declare.
            if set(groups).issubset(parent_groups):
                continue
            evidence = []
            for entries in groups.values():
                evidence.extend(entries[:3])
            overrides.append(
                {
                    "signal": signal,
                    "parent_scope": ancestor,
                    "scope": scope,
                    "parent_values": sorted(entries[0]["value"] for entries in parent_groups.values()),
                    "values": sorted(entries[0]["value"] for entries in groups.values()),
                    "evidence": sorted(evidence, key=lambda entry: (entry["path"], entry["line"], entry["value"])),
                }
            )
    return scope_rows, conflicts, overrides


def find_conflicts(files):
    """Backward-compatible true-conflict view (scope overrides are separate)."""
    return analyze_scoped_conflicts(files)[1]


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
        if not facts.is_file_within_root(root, path):
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
        if not facts.is_file_within_root(root, path):
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
    safe_githooks = facts.resolve_within_root(githooks, root)
    if safe_githooks is not None and safe_githooks.is_dir():
        for p in sorted(githooks.iterdir()):
            if facts.is_file_within_root(root, p) and not p.name.endswith(".sample"):
                hooks.append({"config": rel(p, root), "event": "git", "command": p.name})
    return hooks


def scan_permissions(root, ctx=None):
    ctx = ctx or ScanContext(root)
    perms = []
    for rel_path in SETTINGS_FILES:
        path = root / rel_path
        if not facts.is_file_within_root(root, path):
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
    hits = []
    for label, pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match and not _SECRET_PLACEHOLDER_RE.search(match.group(0)):
            hits.append(label)
    return hits


def _md_safe(value):
    """Neutralize Markdown-breakout characters in a value read from attacker-
    controlled JSON (MCP server/env names, permission rules, hook event/command
    strings) before it is embedded in a finding ``message``.

    Unlike the command/path values extracted elsewhere in this module via
    bounded regexes, these come straight from JSON keys/values with no
    constraint on content: a literal backtick closes an inline code span early,
    and a literal newline injects extra lines into a rendered report or a
    posted GitHub PR review comment (SEC-01). Findings are read both by humans
    and by agents/CI tooling (``pr_review.py`` posts them verbatim as PR
    comments), so this is a real injection surface, not just cosmetic.
    """
    return " ".join(str(value).replace("`", "'").split())


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
        if not facts.is_file_within_root(root, path):
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
        if not facts.is_file_within_root(root, path):
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
                            "message": f"Possible {label} in MCP server `{_md_safe(name)}` env `{_md_safe(key)}`",
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
                    "message": f"MCP server `{_md_safe(s['name'])}` uses insecure http:// transport",
                }
            )
        for key in s["env_keys"]:
            if re.search(r"(?i)key|token|secret|password", key):
                findings.append(
                    {
                        "level": "MEDIUM",
                        "category": "mcp",
                        "path": s["config"],
                        "message": f"MCP server `{_md_safe(s['name'])}` sets credential-shaped "
                        f"env `{_md_safe(key)}`; reference an env var instead of a literal",
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
                        "message": f"Overly broad allow rule `{_md_safe(entry)}` grants unrestricted execution",
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
                        "message": f"{_md_safe(h['event'])} hook contains {label}: `{_md_safe(h['command'][:80])}`",
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


def find_gaps(root, surface, conflicts=None, ctx=None):
    """Diff the repo against a harness completeness checklist and report what is
    missing. Read-only: never writes or mutates the target repository."""
    ctx = ctx or ScanContext(root)
    gaps = []
    agents = root / "AGENTS.md"

    # 1) Canonical root AGENTS.md must exist — the single source of truth.
    has_agents = facts.is_file_within_root(root, agents)
    if not has_agents:
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
    if has_agents:
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
    if has_agents:
        for rel_path in GAP_STUB_FILES:
            path = root / rel_path
            if not facts.is_file_within_root(root, path):
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
        if not facts.is_file_within_root(root, root / rel_path):
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

    # 5) Wholesale Dumping (SKILL.md's "Named anti-patterns").
    gaps.extend(find_wholesale_dumping(root, agents_text, ctx))

    # 6) Silent Adjudication (SKILL.md's "Named anti-patterns").
    gaps.extend(find_silent_adjudication(agents_text, conflicts or []))

    order = {"ERROR": 0, "WARN": 1, "NOTICE": 2}
    # Sort check ids numerically (G10 after G9, not before it lexicographically).
    return sorted(
        gaps, key=lambda g: (order.get(g["level"], 3), int(g["check"][1:]) if g["check"][1:].isdigit() else 99)
    )


def collect_instruction_files(repo_root, max_bytes=32768, ctx=None):
    """Collect recognized instruction configs once for scan/explain consumers."""
    root = Path(repo_root).resolve()
    ctx = ctx or ScanContext(root)
    files = []
    warnings = []
    for tool, path in iter_matches(root, ctx):
        info = file_info(root, tool, path, max_bytes)
        warnings.extend(info.pop("warnings"))
        files.append(info)
    result_files = [{k: v for k, v in f.items() if k != "text"} for f in files]
    return files, result_files, warnings, ctx


def scan_repo(repo_root, max_bytes, rules_dirs=None, allow_plugins=False, ctx=None):
    root = Path(repo_root).resolve()
    # Walk the tree once and share the read/parse cache across every stage below
    # (PERF-01/PERF-02). In monorepo mode the caller passes a subcontext sliced
    # from the parent inventory so package subtrees are not re-walked (PERF-03).
    files, result_files, warnings, ctx = collect_instruction_files(root, max_bytes, ctx)
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
    agents_text = (
        (ctx.read_text(agents_path) or "")
        if facts.is_file_within_root(root, agents_path)
        else ""
    )
    instruction_scopes, conflicts, scope_overrides = analyze_scoped_conflicts(files)
    report = {
        "files": result_files,
        "warnings": warnings,
        "overlaps": find_overlaps(files),
        "conflicts": conflicts,
        "instruction_scopes": instruction_scopes,
        "scope_overrides": scope_overrides,
        "nested": nested_agents(result_files),
        "surface": surface,
        "security": security_findings(root, files, mcp, hooks, permissions, ctx),
        "project_snapshot": build_project_snapshot(root, surface, agents_text, ctx),
        "semantic": semantic.analyze(root, agents_text),
        "gaps": find_gaps(root, surface, conflicts, ctx),
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
    text = facts.read_text_within_root(root, path)
    try:
        data = json.loads(text) if text is not None else None
    except Exception:
        data = None
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
    if not facts.is_file_within_root(root, path):
        path = root / "pnpm-workspace.yml"
    text = facts.read_text_within_root(root, path, errors="replace")
    if text is None:
        return []
    globs = []
    in_packages = False
    for raw in text.splitlines():
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
            if not facts.is_dir_within_root(root, path) or is_skipped(path, root):
                continue
            if facts.is_file_within_root(
                root, path / "package.json"
            ) or facts.is_file_within_root(root, path / "AGENTS.md"):
                dirs[rel(path, root)] = path
    return dict(sorted(dirs.items()))


def _discover_nested_packages(root, ctx=None):
    """Heuristic package discovery when no workspace config exists.

    Finds the shallowest subdirectories that contain a ``package.json`` or a
    ``AGENTS.md`` (never descending into an already-detected package). Reuses
    the shared file index (:class:`ScanContext`) instead of a fresh
    ``os.walk``, which previously re-walked the whole tree a second time on
    every ``--monorepo`` (force) run — the exact scenario the shared index was
    built to avoid (PERF-01).
    """
    root = Path(root)
    ctx = ctx or ScanContext(root)
    candidates = set()
    for relposix, _path in ctx.index:
        name = relposix.rsplit("/", 1)[-1]
        if name not in ("package.json", "AGENTS.md"):
            continue
        parent = relposix.rsplit("/", 1)[0] if "/" in relposix else ""
        if parent:  # a root-level manifest is not a "nested" package
            candidates.add(parent)
    dirs = {}
    for relpath in sorted(candidates):
        # Shallowest wins: skip any candidate nested under an already-accepted
        # directory, matching the walk-and-prune semantics this replaces.
        if any(relpath == accepted or relpath.startswith(accepted + "/") for accepted in dirs):
            continue
        dirs[relpath] = root / relpath
    return dict(sorted(dirs.items()))


def detect_packages(root, mode="auto", ctx=None):
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
        dirs = _discover_nested_packages(root, ctx)
        if dirs:
            return dirs, "nested packages"
    return {}, None


def _package_name(path):
    text = facts.read_text_within_root(path, path / "package.json")
    try:
        data = json.loads(text) if text is not None else None
    except Exception:
        data = None
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


def _scan_finding_records(report, package=""):
    """Flatten suppressible scan debt into stable, structured records.

    Identity uses structured rule/category/evidence fields plus the package
    prefix. Line numbers and suggestions are presentation details, not identity.
    Security findings never enter this function and therefore cannot be
    baselined.
    """
    records = []
    for finding in report.get("gaps", []):
        records.append(
            {
                "family": "gap",
                "rule": finding.get("check", ""),
                "package": package,
                "path": "",
                "message": _without_line_evidence(finding.get("message", "")),
                "item": finding.get("item", ""),
            }
        )
    for finding in report.get("semantic", {}).get("findings", []):
        records.append(
            {
                "family": "semantic",
                "rule": finding.get("category", ""),
                "package": package,
                "path": "AGENTS.md",
                "message": _without_line_evidence(finding.get("message", "")),
                "declared": finding.get("declared", ""),
                "actual": finding.get("actual", ""),
            }
        )
    for finding in report.get("conflicts", []):
        values = sorted(str(value) for value in finding.get("values", {}))
        record = {
            "family": "conflict",
            "rule": finding.get("signal", ""),
            "package": package,
            "path": "",
            "message": f"Conflicting {finding.get('signal', '')} declarations: " + ", ".join(values),
            "values": values,
        }
        if finding.get("scope") not in (None, "", "."):
            record["scope"] = finding["scope"]
        records.append(record)
    return records


def _scan_reports(report):
    """Yield ``(package-prefix, report)`` for root followed by packages."""
    yield "", report
    for package in report.get("packages", []):
        yield package.get("path", ""), package.get("report", {})


def _baseline_entry(record):
    """Canonical persisted shape for a scan debt record."""
    entry = {
        "family": record.get("family", ""),
        "rule": record.get("rule", ""),
        "package": record.get("package", ""),
        "path": record.get("path", ""),
        "message": record.get("message", ""),
    }
    family = entry["family"]
    if family == "gap":
        entry["item"] = record.get("item", "")
    elif family == "semantic":
        entry["declared"] = record.get("declared", "")
        entry["actual"] = record.get("actual", "")
    elif family == "conflict":
        entry["values"] = sorted(str(value) for value in record.get("values", []))
        if record.get("scope") not in (None, "", "."):
            entry["scope"] = record["scope"]
    return entry


def scan_finding_fingerprint(record):
    """Return a hashable public identity for one baseline-eligible finding."""
    entry = _baseline_entry(record)
    return json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def baseline_fingerprints(payload):
    """Load valid non-security fingerprints from a decoded baseline payload."""
    if not isinstance(payload, dict) or payload.get("version") != SCAN_BASELINE_VERSION:
        return set()
    fingerprints = set()
    for entry in payload.get("findings", []):
        if not isinstance(entry, dict) or entry.get("family") not in SCAN_BASELINE_FAMILIES:
            continue
        fingerprints.add(scan_finding_fingerprint(entry))
    return fingerprints


def load_scan_baseline(path):
    """Load a scan baseline; missing/malformed files suppress nothing."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return baseline_fingerprints(payload)


def scan_baseline_payload(report):
    """Build a deterministic, timestamp-free baseline for root + packages."""
    unique = {}
    for package, subreport in _scan_reports(report):
        for record in _scan_finding_records(subreport, package):
            entry = _baseline_entry(record)
            unique[scan_finding_fingerprint(entry)] = entry
    findings = sorted(
        unique.values(),
        key=lambda entry: (
            entry["package"],
            entry["family"],
            entry["rule"],
            entry["path"],
            entry["message"],
            json.dumps(entry, ensure_ascii=False, sort_keys=True),
        ),
    )
    return {"version": SCAN_BASELINE_VERSION, "findings": findings}


def _refresh_package_summaries(report):
    """Recompute monorepo summaries after baseline suppression."""
    packages = report.get("packages", [])
    for package in packages:
        package["summary"] = _package_summary(package.get("report", {}))
    if "monorepo" in report:
        report["monorepo"]["aggregate"] = _aggregate_packages(packages)


def apply_scan_baseline(report, baseline, baseline_path):
    """Suppress matching gap/semantic/conflict debt while retaining attribution."""
    baselined = []

    def visible_entry(record, finding):
        entry = _baseline_entry(record)
        if finding.get("message"):
            entry["message"] = finding["message"]
        for key in ("level", "line", "suggestion"):
            if key in finding:
                entry[key] = finding[key]
        return entry

    for package, subreport in _scan_reports(report):
        kept_gaps = []
        for finding in subreport.get("gaps", []):
            record = _scan_finding_records({"gaps": [finding]}, package)[0]
            if scan_finding_fingerprint(record) in baseline:
                baselined.append(visible_entry(record, finding))
            else:
                kept_gaps.append(finding)
        subreport["gaps"] = kept_gaps

        kept_semantic = []
        semantic = subreport.get("semantic", {})
        for finding in semantic.get("findings", []):
            record = _scan_finding_records(
                {"semantic": {"findings": [finding]}},
                package,
            )[0]
            if scan_finding_fingerprint(record) in baseline:
                baselined.append(visible_entry(record, finding))
            else:
                kept_semantic.append(finding)
        if semantic:
            semantic["findings"] = kept_semantic
            semantic["mismatches"] = len(kept_semantic)

        kept_conflicts = []
        for finding in subreport.get("conflicts", []):
            record = _scan_finding_records({"conflicts": [finding]}, package)[0]
            if scan_finding_fingerprint(record) in baseline:
                baselined.append(visible_entry(record, finding))
            else:
                kept_conflicts.append(finding)
        subreport["conflicts"] = kept_conflicts

    # Keep one attributed, deterministic visibility surface at the top level.
    baselined.sort(
        key=lambda entry: (
            entry["package"],
            entry["family"],
            entry["rule"],
            entry["path"],
            entry["message"],
        )
    )
    report["baselined"] = baselined
    report["baseline"] = {"path": str(baseline_path), "suppressed": len(baselined)}
    _refresh_package_summaries(report)
    return report


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
                "has_agents_md": facts.is_file_within_root(pdir, pdir / "AGENTS.md"),
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


def read_repos_file(path):
    """Parse a ``--repos-file``: one repository path per line, blank lines and
    ``#``-prefixed comments ignored. Returns the raw path strings in order,
    exactly as written (not yet resolved)."""
    text = Path(path).read_text(encoding="utf-8")
    out = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        out.append(stripped)
    return out


def scan_repos_file(paths, max_bytes, rules_dirs=None, allow_plugins=False):
    """Scan a list of independent repository roots and build a cross-repo
    summary (an org-wide health snapshot; README's "Mixed-tool team" and "OSS
    maintainer" personas otherwise have no story beyond running the tool once
    per repo by hand).

    Each entry is scanned with its OWN :class:`ScanContext` — unlike
    ``scan_monorepo``'s package subdirectories, these are unrelated
    filesystem trees with nothing to share a walk/read cache over. A path
    that does not resolve to a directory produces an ``{"error": ...}`` entry
    instead of aborting the batch, so one bad line in the file never hides
    the findings for every other repo.

    Returns ``(summary, repos)`` where ``repos`` is a list of
    ``{path, resolved, name, has_agents_md, summary, report}`` for a scanned
    repo, or ``{path, resolved, error}`` for one that could not be scanned.
    """
    repos = []
    for raw_path in paths:
        root = Path(raw_path).expanduser().resolve()
        if not root.is_dir():
            repos.append({"path": raw_path, "resolved": str(root), "error": f"not a directory: {raw_path}"})
            continue
        report = scan_repo(root, max_bytes, rules_dirs, allow_plugins=allow_plugins)
        repos.append(
            {
                "path": raw_path,
                "resolved": str(root),
                "name": _package_name(root),
                "has_agents_md": facts.is_file_within_root(root, root / "AGENTS.md"),
                "summary": _package_summary(report),
                "report": report,
            }
        )
    ok = [r for r in repos if "error" not in r]
    aggregate = _aggregate_packages(ok)
    # _aggregate_packages was written for scan_monorepo's package-subdirectory
    # unit; rename its "packages_with_agents_md" key so the batch JSON output
    # reads correctly for its own unit (independent repos, not sub-packages).
    aggregate["repos_with_agents_md"] = aggregate.pop("packages_with_agents_md")
    summary = {
        "repo_count": len(repos),
        "error_count": len(repos) - len(ok),
        "aggregate": aggregate,
    }
    return summary, repos


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


def _run_repos_file(args):
    """``main()``'s ``--repos-file`` branch: scan every listed repo and print
    a cross-repo summary instead of a single repo's report."""
    try:
        paths = read_repos_file(args.repos_file)
    except OSError as exc:
        print(f"error: could not read --repos-file {args.repos_file}: {exc}", file=sys.stderr)
        return 1
    if not paths:
        print(f"error: --repos-file {args.repos_file} has no repository paths", file=sys.stderr)
        return 1
    if args.allow_plugins:
        print(
            "WARNING: --allow-plugins enabled: executing untrusted rule plugin code from every "
            "scanned repository (<repo>/.ai-harness-doctor/rules/ and any --rules DIR).",
            file=sys.stderr,
        )
    summary, repos = scan_repos_file(paths, args.max_bytes, args.rules, allow_plugins=args.allow_plugins)

    # Same fail-on-gate precedence and pre-suppression evaluation as the
    # single-repo path (CORR-03): decide on the actual findings before the
    # --no-* flags drop any report sections.
    ok_reports = [r["report"] for r in repos if "error" not in r]
    exit_code = 0
    if args.fail_on_security and any(any(s["level"] == "HIGH" for s in r.get("security", [])) for r in ok_reports):
        exit_code = 2
    elif args.fail_on_gaps and any(any(g["level"] == "ERROR" for g in r.get("gaps", [])) for r in ok_reports):
        exit_code = 3
    elif args.fail_on_semantic and any(r.get("semantic", {}).get("findings") for r in ok_reports):
        exit_code = 4
    elif args.fail_on_conflicts and any(r.get("conflicts") for r in ok_reports):
        exit_code = 7

    for report in ok_reports:
        _apply_section_flags(report, args)

    payload = {"summary": summary, "repos": repos}
    if args.as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        report_path = None if args.no_report_file else write_report_file(payload, args.repos_file)
        print(render_repos_file(summary, repos, report_path), end="")
    return exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(description="Scan AI harness config files.")
    parser.add_argument("repo_root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--sarif", action="store_true", help="Emit SARIF 2.1.0 JSON for GitHub code scanning.")
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
        "--fail-on-conflicts",
        action="store_true",
        help="Exit 7 when any conflicting harness declaration is present.",
    )
    parser.add_argument(
        "--baseline",
        metavar="FILE",
        default=None,
        help="Suppress gap/semantic/conflict debt recorded in FILE so gates fail only on new findings. "
        "HIGH security findings are never suppressible.",
    )
    parser.add_argument(
        "--write-baseline",
        metavar="FILE",
        default=None,
        dest="write_baseline",
        help="Record current gap/semantic/conflict debt to FILE and exit 0. "
        "The deterministic payload excludes all security findings.",
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
    parser.add_argument(
        "--repos-file",
        metavar="PATH",
        help="Scan every repository listed in PATH (one path per line, blank lines and "
        "# comments ignored) instead of a single repo_root, and print a cross-repo health "
        "summary (an org-wide checkup for the 'Mixed-tool team' / 'OSS maintainer' personas). "
        "Mutually exclusive with the repo_root positional argument. Each repo is scanned at "
        "its own root only — this mode does not expand monorepo packages within a repo, so "
        "--monorepo/--no-monorepo are ignored alongside it.",
    )
    args = parser.parse_args(argv)
    if args.repos_file:
        if args.repo_root != ".":
            print("error: repo_root and --repos-file are mutually exclusive", file=sys.stderr)
            return 1
        if args.baseline or args.write_baseline:
            print(
                "error: --repos-file cannot be combined with --baseline or --write-baseline; "
                "each repository must own and run its own scan baseline",
                file=sys.stderr,
            )
            return 1
        return _run_repos_file(args)
    root = Path(args.repo_root).resolve()
    if not root.is_dir():
        message = f"error: not a directory: {args.repo_root}"
        if args.as_json:
            print(json.dumps({"error": message}, ensure_ascii=False, indent=2))
        else:
            print(message, file=sys.stderr)
        return 1
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
    package_dirs, source = detect_packages(root, mode, ctx=ctx)
    if package_dirs:
        monorepo, packages = scan_monorepo(
            root, args.max_bytes, package_dirs, source, args.rules, allow_plugins=args.allow_plugins, ctx=ctx
        )
        report["monorepo"] = monorepo
        report["packages"] = packages

    # Recording is a dedicated explicit-output mode over the natural report.
    # Security findings are structurally excluded by scan_baseline_payload().
    if args.write_baseline:
        payload = scan_baseline_payload(report)
        baseline_path = Path(args.write_baseline)
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote scan baseline with {len(payload['findings'])} finding(s) to {args.write_baseline}")
        return 0

    # Apply suppression before gate and SARIF decisions. Only the explicitly
    # suppressible report families are mutated; security remains untouched.
    if args.baseline:
        apply_scan_baseline(report, load_scan_baseline(args.baseline), args.baseline)

    # Evaluate the fail-on gates on the ACTUAL findings BEFORE the --no-* flags
    # suppress any report sections. Otherwise --no-security would pop the security
    # section and silently neuter --fail-on-security, letting HIGH findings pass
    # with exit 0 (CORR-03). --no-security must only hide the section from the
    # printed report, never disable the gate. Precedence: security > gaps >
    # semantic > conflicts, preserving every existing code meaning and adding 7
    # for conflicts. Fail-on gates consider the root report and every package
    # report so a monorepo run cannot hide a failing package.
    reports = [report] + [pkg["report"] for pkg in report.get("packages", [])]
    exit_code = 0
    if args.fail_on_security and any(any(s["level"] == "HIGH" for s in r.get("security", [])) for r in reports):
        exit_code = 2
    elif args.fail_on_gaps and any(any(g["level"] == "ERROR" for g in r.get("gaps", [])) for r in reports):
        exit_code = 3
    elif args.fail_on_semantic and any(r.get("semantic", {}).get("findings") for r in reports):
        exit_code = 4
    elif args.fail_on_conflicts and any(r.get("conflicts") for r in reports):
        exit_code = 7

    # SARIF emission happens on the COMPLETE report (root + every package) before
    # any --no-* suppression below, so GitHub code scanning always receives the
    # full set of findings regardless of which sections are hidden from the
    # human-readable output. --sarif takes precedence over --json/markdown.
    if args.sarif:
        import sarif  # noqa: E402  # sibling module (scripts/ is on sys.path)

        print(json.dumps(sarif.scan_report_to_sarif(report), ensure_ascii=False, indent=2))
        return exit_code

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
