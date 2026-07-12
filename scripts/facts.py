#!/usr/bin/env python3
"""Shared repository fact-readers for the semantic engine and the drift gate.

Phase-0 (``semantic.py``) and the Phase-2 drift gate (``check_drift.py``) both need
to read the SAME ground-truth facts out of a repository — package.json scripts,
Makefile targets, the committed lockfile's package manager, the pinned Node
version (``.nvmrc`` / ``engines.node``), the package managers a doc *declares*, and
the shared code-span / prose heuristics used to parse commands. Those readers used
to be copy-pasted near-verbatim into both modules and could silently drift — the
exact failure mode this whole tool exists to catch (TD-02). They now live here as
the single source of truth; both engines import them so every fact is read one way.

Python 3.9 standard library only; no runtime dependencies.
"""

import json
import os
import re
import sys
from pathlib import Path

# scripts/ holds the shared agent-config registry (lockfile->manager map, the
# Node-version regex, etc.). Add it to sys.path so importing this module
# standalone still resolves ``registry``.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import registry  # noqa: E402

# Package-manager subcommands that are always valid regardless of package.json;
# a reference to one of these is never a "missing script". Shared so the Phase-0
# semantic engine and the Phase-2 drift gate agree on what counts as a "real"
# script name.
PACKAGE_MANAGER_BUILTINS = {
    "install",
    "ci",
    "i",
    "init",
    "add",
    "remove",
    "rm",
    "uninstall",
    "update",
    "up",
    "upgrade",
    "exec",
    "dlx",
    "create",
    "audit",
    "link",
    "unlink",
    "publish",
    "outdated",
    "config",
    "cache",
    "login",
    "logout",
    "whoami",
    "version",
    "info",
    "list",
    "ls",
    "why",
    "dedupe",
    "prune",
    "rebuild",
    "help",
    "test",
    "start",
    "workspace",
    "workspaces",
}


# English function words whose presence marks a code span as an English prose
# sentence (a comment or descriptive line) rather than a shell command. Extracting
# a "command" from such prose only produces phantom targets (CORR-02).
_PROSE_WORDS = frozenset(
    {
        "the", "a", "an", "to", "of", "in", "on", "for", "and", "or", "if",
        "then", "that", "this", "your", "you", "we", "is", "are", "be", "should",
        "must", "will", "can", "please", "before", "after", "when", "which",
        "with", "into", "sure",
    }
)
# Words that appear as the object of a common English imperative ("make sure",
# "make certain", "make the ...") — never real Makefile targets / npm scripts.
# Guards the short (sub-sentence) prose case that _looks_like_prose misses.
_PROSE_TARGET_WORDS = frozenset(
    {"sure", "certain", "it", "them", "the", "a", "an", "use", "do", "note", "your", "this", "that"}
)


def looks_like_prose(segment):
    """Return True when a code span reads as an English prose sentence rather than
    a shell command line, so command extraction from it would be spurious.

    Splits on whitespace only, not on internal punctuation: a hyphen/colon-
    joined identifier (``lint-and-fix``, ``build:on:save``) is a single
    command/target/script token, not standalone English words. Previously
    ``[A-Za-z']+`` extracted sub-words from inside such identifiers too, so
    e.g. the "and" in ``make lint-and-fix`` counted as a prose-word hit and
    the whole line was misread as a sentence, silently disabling the D1
    command-drift check for any command name shaped like that (CORRECTNESS-01).
    """
    words = []
    for token in segment.lower().split():
        if "-" in token or ":" in token:
            continue
        words.extend(re.findall(r"[a-z']+", token))
    if len(words) < 4:
        return False
    return any(w in _PROSE_WORDS for w in words)


def iter_code_tokens(text):
    """Yield ``(lineno, token)`` for fenced-code lines and inline backtick spans.

    Commands frequently live inside ```` ```bash ```` fences as well as inline
    ``code`` spans, so both are scanned. This is the single shared code-span
    tokenizer used by both the semantic engine and the drift gate.
    """
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        # Inside a fenced block a line beginning with `#` is a shell comment, not
        # a command; skip it so prose in comments (e.g. "# make sure the tests
        # pass") is not misread as a command (CORR-02).
        if in_fence and not line.strip().startswith("#"):
            yield lineno, line
        for m in re.finditer(r"`([^`]+)`", line):
            yield lineno, m.group(1)


def within_root(root, token):
    """Return True only if ``token`` resolves to a path contained in ``root``.

    Both engines read backtick tokens from an untrusted AGENTS.md and probe them
    on disk. ``pathlib`` happily lets an absolute (``/etc/hostname``) or
    ``../``-escaping token point outside the repo, which would let a malicious
    AGENTS.md infer the existence of arbitrary filesystem paths. Reject anything
    that does not stay under the repo root before calling ``.exists()``.
    """
    try:
        candidate = (root / token).resolve()
        candidate.relative_to(root.resolve())  # raises ValueError if outside root
        return True
    except (ValueError, OSError):
        return False


# ---------------------------------------------------------------------------
# Repository facts — what the code actually says.
# ---------------------------------------------------------------------------


def package_scripts(root):
    """Return the set of package.json script names.

    ``None`` when there is nothing to verify against: either no package.json
    exists, or it is present but could not be read/parsed. Returning ``None``
    (rather than an empty ``set()``) on a parse failure keeps "invalid JSON"
    distinct from "valid JSON with no scripts", so callers skip the unknown-
    script check instead of falsely reporting every referenced script as unknown
    (CORR-01).
    """
    path = root / "package.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    scripts = data.get("scripts")
    return set(scripts.keys()) if isinstance(scripts, dict) else set()


def _walk_package_jsons(root):
    """Yield the parsed dict of every readable ``package.json`` under root
    (root plus nested/workspace packages), skipping vendored dirs. Shared by
    ``all_package_scripts`` and ``all_package_names`` so a repo-wide walk
    happens at most once per fact, not once per fact PER CALLER. Uses
    ``os.walk`` with directory pruning (not ``Path.rglob``) so a huge
    unrelated ``node_modules`` never gets traversed.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in registry.SKIP_DIRS]
        if "package.json" not in filenames:
            continue
        try:
            yield json.loads((Path(dirpath) / "package.json").read_text(encoding="utf-8"))
        except Exception:
            continue


def all_package_scripts(root):
    """Union of package.json script names across every package.json in the
    repo (root plus nested/workspace packages), skipping vendored dirs.

    Monorepo AGENTS.md commonly documents per-package commands ("run these
    from within packages/foo") that a root-only lookup can't see — checking
    a monorepo's AGENTS.md against just ``package_scripts(root)`` produced a
    false MISMATCH (found scanning vercel/ai, whose root AGENTS.md documents
    `pnpm test:node` / `pnpm build:watch`, which live in packages/ai's
    package.json, not the pnpm-workspace root's).

    ``None`` only when there is no package.json anywhere under root, mirroring
    ``package_scripts``'s None-vs-empty-set contract (CORR-01).
    """
    found_any = False
    names = set()
    for data in _walk_package_jsons(root):
        found_any = True
        scripts = data.get("scripts")
        if isinstance(scripts, dict):
            names.update(scripts.keys())
    return names if found_any else None


def all_package_names(root):
    """Union of every package.json ``name`` field under root (root plus
    nested/workspace packages), skipping vendored dirs.

    A backtick-quoted token whose first path segment matches one of these is
    a package self-import specifier — `better-auth/test` imports
    packages/better-auth's own `test` export subpath — not a repo-relative
    filesystem path. Found scanning better-auth/better-auth's AGENTS.md,
    where this was flagged MISSING even though the package resolves fine.
    """
    names = set()
    for data in _walk_package_jsons(root):
        name = data.get("name")
        if isinstance(name, str) and name:
            names.add(name)
    return names


def package_dependency_names(root):
    """Return dependency names declared in package.json, or ``None`` if unreadable.

    Covers ``dependencies``, ``devDependencies``, ``peerDependencies``, and
    ``optionalDependencies``. Used as a fallback ground truth for yarn's binary
    passthrough (see ``is_yarn_bin_passthrough``) when ``node_modules/.bin`` has
    not been installed. Mirrors ``package_scripts``'s None-vs-empty-set contract
    (CORR-01).
    """
    path = root / "package.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    names = set()
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        section = data.get(key)
        if isinstance(section, dict):
            names.update(section.keys())
    return names


def node_modules_bin_names(root):
    """Return binary names present in ``node_modules/.bin``, or ``None`` if absent."""
    bin_dir = root / "node_modules" / ".bin"
    if not bin_dir.is_dir():
        return None
    try:
        return {p.name for p in bin_dir.iterdir()}
    except OSError:
        return None


# Yarn Classic and Berry fall back to executing a binary straight out of
# ``node_modules/.bin`` when the token after ``yarn`` does not match a
# package.json script name — e.g. `yarn vitest` runs the vitest binary directly
# even though no "vitest" script is declared. npm has no such fallback (`npm
# vitest` errors with "Unknown command"), and pnpm does not resolve
# node_modules/.bin entries this way either (pnpm/pnpm#3297), so this passthrough
# is scoped to yarn only.
_BIN_PASSTHROUGH_TOOLS = {"yarn"}


def is_yarn_bin_passthrough(root, tool, name):
    """True if ``tool name`` is a legitimate yarn binary passthrough, not a missing script.

    Prefers the installed ``node_modules/.bin`` ground truth when available (it
    reflects the binary's real name, e.g. ``tsc`` from the ``typescript``
    package); falls back to the declared dependency names for repositories
    scanned without ``node_modules`` installed.
    """
    if tool not in _BIN_PASSTHROUGH_TOOLS:
        return False
    bin_names = node_modules_bin_names(root)
    if bin_names is not None:
        return name in bin_names
    deps = package_dependency_names(root)
    return deps is not None and name in deps


# Matches a rule/assignment header: one or more whitespace-separated names,
# then `:` or `::`, then an optional immediately-following `=`. Group 3 only
# captures when `=` has NO whitespace before it, which is what distinguishes an
# immediate-expansion assignment (`CFLAGS := -O2`) from a genuine rule with a
# target-specific variable value (`debug: CFLAGS = -g`, space-separated).
_MAKE_TARGET_LINE_RE = re.compile(r"^([A-Za-z0-9_.-]+(?:[ \t]+[A-Za-z0-9_.-]+)*)[ \t]*(::?)(=?)")


def make_targets(root):
    path = root / "Makefile"
    if not path.is_file():
        return None
    targets = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("\t"):
            continue
        m = _MAKE_TARGET_LINE_RE.match(line)
        if not m:
            continue
        # `VAR := value` / `VAR ::= value` is a variable assignment, not a rule.
        if m.group(3) == "=":
            continue
        for name in m.group(1).split():
            # A standard multi-target rule (`build test: deps`) declares every
            # space-separated name before the colon as its own target. Dot-
            # prefixed names are GNU Make's own special targets (.PHONY,
            # .SUFFIXES, ...), never real invokable targets.
            if not name.startswith("."):
                targets.add(name)
    return targets


def nvmrc_node_version(root):
    path = root / ".nvmrc"
    if not path.is_file():
        return None
    m = re.search(r"v?(\d+)", path.read_text(encoding="utf-8", errors="replace").strip())
    return int(m.group(1)) if m else None


def engines_node_version(root):
    path = root / "package.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    engines = data.get("engines")
    node = engines.get("node") if isinstance(engines, dict) else None
    if not node:
        return None
    m = re.search(r"(\d+)", str(node))
    return int(m.group(1)) if m else None


def lockfile_managers(root):
    """Return the set of package managers implied by committed lockfiles.

    Uses the shared ``registry.LOCKFILE_MANAGERS`` map (single source of truth,
    incl. bun) so the semantic engine and the drift gate see the same managers.
    """
    return {mgr for name, mgr in registry.LOCKFILE_MANAGERS.items() if (root / name).is_file()}


# ---------------------------------------------------------------------------
# Declaration extractors — what AGENTS.md *claims*.
# ---------------------------------------------------------------------------


def declared_node_version(text):
    """Return ``(major, line)`` for a Node.js version declared in AGENTS.md, else ``(None, None)``.

    Uses the shared ``registry.node_version_major`` extractor so the Phase-0 check,
    the Phase-2 D6 drift gate and the scan conflict signal all read the same value
    from a given line (TD-06)."""
    for lineno, line in enumerate(text.splitlines(), 1):
        major = registry.node_version_major(line)
        if major is not None:
            return major, lineno
    return None, None


def declared_package_managers(text):
    """Return the set of Node package managers named in AGENTS.md code spans.

    Includes bun so this matches ``registry.LOCKFILE_MANAGERS`` (TD-01) and so the
    Phase-0 engine and the Phase-2 D6 drift gate agree on what a doc declares."""
    pms = set()
    for _lineno, token in iter_code_tokens(text):
        for m in re.finditer(r"\b(npm|pnpm|yarn|bun)\b", token):
            pms.add(m.group(1))
    return pms
