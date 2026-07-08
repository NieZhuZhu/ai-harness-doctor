#!/usr/bin/env python3
"""Semantic consistency engine: compare AGENTS.md *declarations* against repo *facts*.

Phase 0 (Checkup) reports what config files exist and how they overlap/conflict
with each other. This module adds the missing half: it reads the canonical
``AGENTS.md`` and cross-checks the concrete claims it makes — build/test commands,
repository-relative paths, the package manager, and the Node.js version — against
ground truth in the repository (``package.json`` scripts, ``Makefile`` targets, the
filesystem, lockfiles, ``.nvmrc`` / ``engines.node``).

Unlike ``check_drift.py`` (the Phase 2 CI *gate* that fails the build), this engine
is read-only reporting surfaced inside the Phase 0 scan so an author sees, at
checkup time, exactly where the instructions no longer match the code. Python 3.9
standard library only; no runtime dependencies.
"""

import json
import re
from pathlib import Path

# Package-manager subcommands that are always valid regardless of package.json;
# mirrors check_drift.PACKAGE_MANAGER_BUILTINS so the two engines agree on what
# counts as a "real" script name.
PACKAGE_MANAGER_BUILTINS = {
    "install", "ci", "i", "init", "add", "remove", "rm", "uninstall", "update", "up", "upgrade",
    "exec", "dlx", "create", "audit", "link", "unlink", "publish", "outdated", "config", "cache",
    "login", "logout", "whoami", "version", "info", "list", "ls", "why", "dedupe", "prune",
    "rebuild", "help", "test", "start",
}

LOCKFILE_MANAGERS = {
    "package-lock.json": "npm",
    "npm-shrinkwrap.json": "npm",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "bun.lockb": "bun",
    "bun.lock": "bun",
}

# Repo-root files that are referenced by bare name (no slash) yet are legitimate
# repo-relative paths worth verifying.
KNOWN_ROOT_FILES = {"package.json", "Makefile", "AGENTS.md", "README.md"}


def _finding(category, level, message, suggestion, declared, actual, line=None):
    entry = {
        "category": category,
        "level": level,
        "message": message,
        "suggestion": suggestion,
        "declared": declared,
        "actual": actual,
    }
    if line is not None:
        entry["line"] = line
    return entry


def iter_code_tokens(text):
    """Yield ``(lineno, token)`` for fenced-code lines and inline backtick spans.

    Commands frequently live inside ```` ```bash ```` fences as well as inline
    ``code`` spans, so both are scanned. Mirrors ``check_drift.line_collected_code``.
    """
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            yield lineno, line
        for m in re.finditer(r"`([^`]+)`", line):
            yield lineno, m.group(1)


# ---------------------------------------------------------------------------
# Declaration extractors — what AGENTS.md *claims*.
# ---------------------------------------------------------------------------

_COMMAND_RE = re.compile(
    r"\b(?:(npm|pnpm|bun)\s+(?:run\s+)?([A-Za-z0-9:_-]+)"
    r"|yarn\s+([A-Za-z0-9:_-]+)"
    r"|make\s+([A-Za-z0-9_.-]+))\b"
)


def declared_commands(text):
    """Return declared build/test commands as ``{tool, name, line}`` dicts."""
    out = []
    seen = set()
    for lineno, token in iter_code_tokens(text):
        for m in _COMMAND_RE.finditer(token):
            tool = m.group(1) or ("yarn" if m.group(3) else "make")
            name = m.group(2) or m.group(3) or m.group(4)
            key = (tool, name, lineno)
            if key in seen:
                continue
            seen.add(key)
            out.append({"tool": tool, "name": name, "line": lineno})
    return out


def declared_paths(text):
    """Return repo-relative paths referenced in inline backticks as ``{path, line}``."""
    out = []
    seen = set()
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in re.finditer(r"`([^`]+)`", line):
            token = m.group(1).strip()
            if not token or token in seen:
                continue
            if token.startswith(("http://", "https://")) or "<" in token or "{" in token:
                continue
            if token.startswith(("~", "/", "$")) or ":" in token:
                continue
            if token.startswith(("npm ", "pnpm ", "yarn ", "bun ", "make ", "python", "git ", "node ")):
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


def declared_package_managers(text):
    pms = set()
    for _lineno, token in iter_code_tokens(text):
        for m in re.finditer(r"\b(npm|pnpm|yarn|bun)\b", token):
            pms.add(m.group(1))
    return pms


def declared_node_version(text):
    """Return ``(major, line)`` for a Node.js version declared in AGENTS.md, else ``(None, None)``."""
    for lineno, line in enumerate(text.splitlines(), 1):
        m = re.search(r"\bnode(?:\.js)?\s*(?:version)?\s*(?:>=?|<=?|==?|\^|~)?\s*v?(\d+)(?:\.\d+|\.x)*", line, re.I)
        if m:
            return int(m.group(1)), lineno
    return None, None


# ---------------------------------------------------------------------------
# Repository facts — what the code actually says.
# ---------------------------------------------------------------------------

def package_scripts(root):
    path = root / "package.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return set()
    scripts = data.get("scripts")
    return set(scripts.keys()) if isinstance(scripts, dict) else set()


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


def lockfile_managers(root):
    return {mgr for name, mgr in LOCKFILE_MANAGERS.items() if (root / name).is_file()}


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


def _within_root(root, token):
    """True only if ``token`` resolves to a path contained in ``root`` (info-leak guard)."""
    try:
        candidate = (root / token).resolve()
        candidate.relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


# ---------------------------------------------------------------------------
# Comparison — declarations vs facts.
# ---------------------------------------------------------------------------

def compare_commands(root, text):
    findings = []
    scripts = package_scripts(root)
    targets = make_targets(root)
    for decl in declared_commands(text):
        tool, name, line = decl["tool"], decl["name"], decl["line"]
        if tool == "make":
            if targets is not None and name not in targets:
                findings.append(_finding(
                    "command", "MISMATCH",
                    f"AGENTS.md references `make {name}` but the Makefile has no `{name}` target.",
                    "Add the Makefile target or update AGENTS.md to a real target.",
                    f"make {name}", "no such Makefile target", line,
                ))
            continue
        if name in PACKAGE_MANAGER_BUILTINS:
            continue
        if scripts is not None and name not in scripts:
            findings.append(_finding(
                "command", "MISMATCH",
                f"AGENTS.md references `{tool} run {name}` but package.json has no `{name}` script.",
                "Add the package.json script or update AGENTS.md to a real script.",
                f"{tool} run {name}", "no such package.json script", line,
            ))
    return findings


def compare_paths(root, text):
    findings = []
    for decl in declared_paths(text):
        token, line = decl["path"], decl["line"]
        if not _within_root(root, token):
            continue
        if not (root / token).exists():
            findings.append(_finding(
                "path", "MISSING",
                f"AGENTS.md references path `{token}` which does not exist in the repository.",
                "Fix or remove the backtick-quoted path in AGENTS.md.",
                token, "path not found", line,
            ))
    return findings


def compare_package_manager(root, text):
    findings = []
    declared = declared_package_managers(text)
    ground = lockfile_managers(root)
    if len(declared) == 1 and len(ground) == 1:
        declared_pm = next(iter(declared))
        ground_pm = next(iter(ground))
        if declared_pm != ground_pm:
            lockfile = next(
                name for name, mgr in LOCKFILE_MANAGERS.items()
                if mgr == ground_pm and (root / name).is_file()
            )
            findings.append(_finding(
                "package_manager", "MISMATCH",
                f"AGENTS.md uses `{declared_pm}` but the repo has `{lockfile}`, implying `{ground_pm}`.",
                f"Align AGENTS.md with `{ground_pm}` or replace the lockfile to match `{declared_pm}`.",
                declared_pm, ground_pm,
            ))
    return findings


def compare_node_version(root, text):
    findings = []
    declared, line = declared_node_version(text)
    if declared is None:
        return findings
    nvmrc = nvmrc_node_version(root)
    if nvmrc is not None and nvmrc != declared:
        findings.append(_finding(
            "node_version", "MISMATCH",
            f"AGENTS.md claims Node {declared} but `.nvmrc` pins Node {nvmrc}.",
            "Align AGENTS.md with `.nvmrc` or update `.nvmrc`.",
            f"node {declared}", f"node {nvmrc}", line,
        ))
    engines = engines_node_version(root)
    if engines is not None and engines != declared:
        findings.append(_finding(
            "node_version", "MISMATCH",
            f"AGENTS.md claims Node {declared} but `package.json` engines.node requires Node {engines}.",
            "Align AGENTS.md with `package.json` engines.node or update engines.node.",
            f"node {declared}", f"node {engines}", line,
        ))
    return findings


def _count_declarations(root, text):
    """How many concrete claims were checked (used for the consistency summary)."""
    count = 0
    count += len(declared_commands(text))
    count += len(declared_paths(text))
    if len(declared_package_managers(text)) == 1 and len(lockfile_managers(root)) == 1:
        count += 1
    declared_node, _ = declared_node_version(text)
    if declared_node is not None:
        if nvmrc_node_version(root) is not None:
            count += 1
        if engines_node_version(root) is not None:
            count += 1
    return count


def analyze(root, text):
    """Compare AGENTS.md declarations against repository facts.

    Returns ``{"findings": [...], "checked": int, "mismatches": int}``. ``findings``
    is deterministically ordered (category, then line). Read-only: never writes to
    the repository.
    """
    root = Path(root)
    findings = []
    if text:
        findings.extend(compare_commands(root, text))
        findings.extend(compare_paths(root, text))
        findings.extend(compare_package_manager(root, text))
        findings.extend(compare_node_version(root, text))
    order = {"command": 0, "path": 1, "package_manager": 2, "node_version": 3}
    findings.sort(key=lambda f: (order.get(f["category"], 9), f.get("line", 0)))
    checked = _count_declarations(root, text) if text else 0
    return {"findings": findings, "checked": checked, "mismatches": len(findings)}
