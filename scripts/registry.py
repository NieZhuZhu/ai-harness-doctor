#!/usr/bin/env python3
"""Loader for the shared agent-config registry (single source of truth).

All knowledge about known AI-agent config files — detection globs, canonical stub
paths and stub content — lives in ``assets/agent-tools.json``. ``scan.py``,
``canonicalize.py`` and ``check_drift.py`` all derive their lists from this module
instead of hardcoding them separately, so adding a new tool is a one-line change to
the JSON. Python 3.9 standard library only; no runtime dependencies.
"""

import json
import re
from pathlib import Path

# scripts/ is a sibling of assets/ under the package root.
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _PACKAGE_ROOT / "assets" / "agent-tools.json"

# Single source of truth for the maximum size (in bytes) of a canonical pointer
# stub. A tool file that references AGENTS.md but exceeds this has "regrown" past
# the minimal-pointer budget. Shared by scan.py (gap analysis), check_drift.py
# (D3 drift gate) and canonicalize.py (Phase 1 stub validation) so the threshold
# cannot drift between stages. Reconciled to the value the canonical/writing
# stage (canonicalize.py) already used; genuine minimal stubs are well under it
# (<200 bytes) (CORR-06).
STUB_POINTER_MAX_BYTES = 800

# Single source of truth mapping a committed lockfile name -> the package manager
# it implies. Shared by semantic.py, check_drift.py and canonicalize.py so the
# drift gate, the semantic engine and the draft generator agree on which managers
# exist — including bun (bun.lockb / bun.lock), which the drift gate previously
# omitted and was therefore blind to (TD-01).
LOCKFILE_MANAGERS = {
    "package-lock.json": "npm",
    "npm-shrinkwrap.json": "npm",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "bun.lockb": "bun",
    "bun.lock": "bun",
}

# Single source of truth for recognizing a Node.js version reference in a line of
# AGENTS.md / config prose and normalizing it to its MAJOR version. Previously
# scan.py (Phase-0 conflict signal), semantic.py (Phase-0 declared-version check)
# and check_drift.py (Phase-2 D6 drift gate) each carried their OWN slightly
# different regex, so the same line could yield a different Node version (or none)
# depending on the stage (TD-06). They now all go through ``node_version_major``
# so every stage extracts the identical value. The pattern accepts: an optional
# ``.js`` suffix, an optional ``:`` separator, an optional ``version``/``v`` word,
# an optional comparator (``>=``/``<=``/``==``/``^``/``~``), an optional ``v``
# prefix and an optional surrounding quote, then the version. The full version
# token (major plus any ``.minor`` / ``.patch`` / ``.x`` suffix) is captured as
# the ``version`` group; the leading MAJOR component alone as the ``major``
# group. ``node_version_major`` normalizes to the major for cross-stage
# comparison, while ``node_version_ref`` preserves the full token for display
# and for semantic-version conflict comparison (CORR-05).
NODE_VERSION_RE = re.compile(
    r"\bnode(?:\.js)?\s*:?\s*(?:v|version)?\s*(?:>=?|<=?|==?|\^|~)?\s*v?[\"']?"
    r"(?P<version>(?P<major>\d+)(?:\.\d+|\.x)*)",
    re.I,
)


def node_version_major(line):
    """Return the MAJOR Node.js version (int) referenced in ``line``, else ``None``.

    Single shared extractor used by scan.py, semantic.py and check_drift.py so all
    three stages normalize a Node version reference to the same value (TD-06)."""
    m = NODE_VERSION_RE.search(line)
    return int(m.group("major")) if m else None


def node_version_ref(line):
    """Return the full declared Node.js version token (str) in ``line``, else ``None``.

    Unlike ``node_version_major``, this preserves the minor/patch/``.x`` suffix
    (e.g. ``"18.17.0"``, ``"18.x"``, ``"20"``) so callers can display the exact
    declared version. Semantic conflict comparison still normalizes to the major
    via ``node_version_major`` so ``18`` and ``18.17.0`` are treated as
    compatible, not a false conflict (CORR-05)."""
    m = NODE_VERSION_RE.search(line)
    return m.group("version") if m else None


# ---------------------------------------------------------------------------
# Backtick-quoted repo path detection (single source of truth).
#
# The Phase-0 semantic engine (semantic.declared_paths) and the Phase-2 drift
# gate (check_drift.d2_path_drift) both need to answer "which backtick-quoted
# tokens in AGENTS.md are repo-relative file paths worth existence-checking?".
# They previously carried two separate, drifted rulesets (different command
# prefixes, a smaller known-root-file set, and a missing quoted-literal guard),
# so the same AGENTS.md line could be a "declared path" in one stage and ignored
# in the other (TD-03). ``declared_paths`` below is the ONE shared classifier both
# call, so the two stages can no longer disagree on what counts as a path.
# ---------------------------------------------------------------------------

# Command prefixes that make a backtick token a shell invocation, not a path.
CMD_PATH_PREFIXES = (
    "npm ",
    "pnpm ",
    "yarn ",
    "bun ",
    "make ",
    "python",
    "git ",
    "node ",
    "go ",
    "cargo ",
    "mvn ",
    "gradle ",
    "./gradlew",
    "./mvnw",
    "poetry ",
    "pdm ",
    "uv ",
    "pip ",
    "pipenv ",
    "pytest",
    "rustc ",
    "javac ",
    "java ",
)

# Repo-root files that are referenced by bare name (no slash) yet are legitimate
# repo-relative paths worth verifying. Covers every ecosystem's manifest/lockfile.
KNOWN_ROOT_FILES = {
    # Generic
    "AGENTS.md",
    "README.md",
    "Makefile",
    # Node
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    # Python
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "Pipfile",
    "poetry.lock",
    "uv.lock",
    "pdm.lock",
    # Go
    "go.mod",
    "go.sum",
    "go.work",
    # Rust
    "Cargo.toml",
    "Cargo.lock",
    # Java
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
}

_BACKTICK_RE = re.compile(r"`([^`]+)`")
# Matches a bare "<word>-name" placeholder path segment; see declared_paths.
_PLACEHOLDER_SEGMENT_RE = re.compile(r"^[a-z][a-z0-9]*-name$")


def declared_paths(text):
    """Return repo-relative paths referenced in inline backticks as ``{path, line}``.

    Single shared classifier used by both ``semantic.declared_paths`` (Phase-0)
    and ``check_drift.d2_path_drift`` (Phase-2) so the two stages agree on exactly
    what counts as a declared path (TD-03). This only decides candidacy from the
    token text; callers still apply their own containment (``_within_root``) and
    existence checks. Tokens are de-duplicated across the whole document.
    """
    out = []
    seen = set()
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in _BACKTICK_RE.finditer(line):
            token = m.group(1).strip()
            if not token or token in seen:
                continue
            # A backtick span wrapped in matching quotes is a string-literal
            # example value (e.g. `'/usr/bin/google-chrome'`, `"./downloads"`),
            # not a repo path reference. Only the backticks were stripped, leaving
            # the inner quotes to defeat the absolute-path / value guards below.
            if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
                continue
            if token.startswith(("http://", "https://")) or "<" in token or "{" in token:
                continue
            # Home-relative (~/.claude), absolute (/etc/...), env-var ($HOME/...),
            # or scheme/drive-like paths reference locations outside the repo tree.
            if token.startswith(("~", "/", "$")) or ":" in token:
                continue
            # Scoped npm package names (`@ai-sdk/provider`) and path-alias imports
            # (`@/components`) contain a slash but are package/module identifiers,
            # not repo-relative filesystem paths; probing `root/@scope/...` always
            # misses and produced false "path does not exist" findings on real
            # AGENTS.md files (e.g. vercel/ai). npm scopes are `@`-prefixed, which
            # no legitimate repo-relative path uses.
            if token.startswith("@"):
                continue
            # A leading `<word>-name` segment (`skill-name/SKILL.md`,
            # `package-name/index.js`) documents a naming *pattern* in prose, not
            # a literal repo path — no real directory is ever named literally
            # "skill-name". Found scanning tldraw/tldraw's AGENTS.md, which uses
            # this idiom to describe its skill-folder convention. Only the exact
            # "<word>-name" shape matches, so a real path segment that merely
            # contains "name" (`username/profile.py`) is still checked.
            if _PLACEHOLDER_SEGMENT_RE.fullmatch(token.split("/", 1)[0]):
                continue
            if token.startswith(CMD_PATH_PREFIXES):
                continue
            if "*" in token or "?" in token:
                continue
            if any(ch.isspace() for ch in token):
                continue
            if "/" not in token and token not in KNOWN_ROOT_FILES:
                continue
            seen.add(token)
            out.append({"path": token, "line": lineno})
    return out


def load_registry():
    """Return the full parsed registry as a dict."""
    with _REGISTRY_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_tools():
    """Return the list of tool entries (claude, cursor, ... roo)."""
    return load_registry().get("tools", [])


def load_canonical():
    """Return the list of canonical file names (e.g. AGENTS.md, AGENT.md)."""
    return load_registry().get("canonical", [])


def canonicalizable_tools():
    """Return only the tools that have a canonical stub form to write/guard."""
    return [t for t in load_tools() if t.get("canonicalizable") and t.get("stub_paths")]
