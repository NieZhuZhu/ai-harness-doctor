#!/usr/bin/env python3
"""Semantic consistency engine: compare AGENTS.md *declarations* against repo *facts*.

Phase 0 (Checkup) reports what config files exist and how they overlap/conflict
with each other. This module adds the missing half: it reads the canonical
``AGENTS.md`` and cross-checks the concrete claims it makes — build/test commands,
repository-relative paths, the package manager, and the language/runtime version —
against ground truth in the repository.

It is **multi-ecosystem**: beyond Node/npm it understands Python
(``pyproject.toml`` / ``setup.py`` / ``requirements.txt`` with pip/poetry/uv/pdm/
pipenv), Go (``go.mod``), Rust (``Cargo.toml``), and Java (``pom.xml`` /
``build.gradle``). For each ecosystem it detects the package manager from the
committed lockfile/manifest, the pinned language version, and — where a repo has a
verifiable command namespace (``package.json`` scripts, ``Makefile`` targets,
``[project.scripts]`` / ``[tool.poetry.scripts]`` console scripts, Cargo ``[[bin]]``
targets, Go package paths) — the referenced commands.

Unlike ``check_drift.py`` (the Phase 2 CI *gate* that fails the build), this engine
is read-only reporting surfaced inside the Phase 0 scan so an author sees, at
checkup time, exactly where the instructions no longer match the code. Python 3.9
standard library only; no runtime dependencies.
"""

import json
import re
import sys
from pathlib import Path

# scripts/ holds the shared agent-config registry (single source of truth for the
# lockfile->manager map, etc.). Add it to sys.path so importing this module
# standalone still resolves ``registry``.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import registry  # noqa: E402

# Package-manager subcommands that are always valid regardless of package.json;
# mirrors check_drift.PACKAGE_MANAGER_BUILTINS so the two engines agree on what
# counts as a "real" script name.
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
}

# Common Python tools invoked via ``poetry run`` / ``pdm run`` / ``uv run`` that are
# not project console scripts, so a reference to them must never be flagged as a
# "missing script". Keeps the Python command check conservative (false negatives
# are cheaper than noisy false positives).
PYTHON_RUN_BUILTINS = {
    "python",
    "python3",
    "pip",
    "pip3",
    "pytest",
    "mypy",
    "ruff",
    "black",
    "flake8",
    "isort",
    "tox",
    "nox",
    "coverage",
    "pre-commit",
    "pylint",
    "bandit",
    "twine",
    "build",
    "uvicorn",
    "gunicorn",
    "hypercorn",
    "celery",
    "alembic",
    "django-admin",
    "manage.py",
    "sphinx-build",
    "mkdocs",
    "jupyter",
    "ipython",
    "pyright",
    "poetry",
    "pdm",
    "uv",
}

# Node lockfile -> package manager map, from the shared registry single source of
# truth (includes bun) so semantic.py, check_drift.py and canonicalize.py agree.
LOCKFILE_MANAGERS = registry.LOCKFILE_MANAGERS

# Ecosystems are compared in this fixed order so multi-ecosystem findings are
# deterministic.
ECOSYSTEM_ORDER = ("node", "python", "go", "rust", "java")

# Package-manager token -> ecosystem it belongs to.
PM_TO_ECOSYSTEM = {
    "npm": "node",
    "pnpm": "node",
    "yarn": "node",
    "bun": "node",
    "pip": "python",
    "poetry": "python",
    "uv": "python",
    "pipenv": "python",
    "pdm": "python",
    "cargo": "rust",
    "go": "go",
    "maven": "java",
    "gradle": "java",
}
# Aliases spelled differently in prose than their canonical manager name.
_PM_NORMALIZE = {"mvn": "maven"}

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


def _read(path):
    """Read text defensively; return ``""`` on any error so callers stay pure."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


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
        # Inside a fenced block a line beginning with `#` is a shell comment, not
        # a command; skip it so prose in comments (e.g. "# make sure the tests
        # pass") is not misread as a command (CORR-02).
        if in_fence and not line.strip().startswith("#"):
            yield lineno, line
        for m in re.finditer(r"`([^`]+)`", line):
            yield lineno, m.group(1)


# English function words whose presence marks a code span as an English prose
# sentence rather than a shell command. Extracting a "command" from such prose
# only produces phantom targets, which are then reported as false mismatches
# (CORR-02).
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


def _looks_like_prose(segment):
    """Return True when a code span reads as an English prose sentence rather than
    a shell command line, so command extraction from it would be spurious."""
    words = re.findall(r"[A-Za-z']+", segment.lower())
    if len(words) < 4:
        return False
    return any(w in _PROSE_WORDS for w in words)


# ---------------------------------------------------------------------------
# Declaration extractors — what AGENTS.md *claims*.
# ---------------------------------------------------------------------------

# Node script invocations: ``npm/pnpm/bun run X`` (``run`` optional) or ``yarn X``.
_NODE_CMD_RE = re.compile(
    r"\b(npm|pnpm|bun)\s+(?:run\s+)?([A-Za-z0-9:_-]+)\b"
    r"|\byarn\s+([A-Za-z0-9:_-]+)\b"
)
# Makefile target invocations: ``make X``.
_MAKE_CMD_RE = re.compile(r"\bmake\s+([A-Za-z0-9_.-]+)\b")
# Rust binary invocations: ``cargo run|build|install ... --bin NAME``.
_CARGO_BIN_RE = re.compile(r"\bcargo\s+(?:run|build|install)\b[^`\n]*?--bin[= ]\s*([A-Za-z0-9._-]+)")
# Go package/file invocations that reference a filesystem path: ``go run|build|test|vet ./pkg`` or ``foo.go``.
_GO_PKG_RE = re.compile(r"\bgo\s+(?:run|build|test|vet)\s+(\.{1,2}/[A-Za-z0-9._/-]+|[A-Za-z0-9._/-]+\.go)\b")
# Python console-script invocations: ``poetry|pdm|uv run NAME``. Capture the
# whole argument so a script-file path (``uv run examples/simple.py``) is not
# truncated at the first ``/`` and mistaken for a console script named
# ``examples``; declared_commands filters those file paths out below.
_PY_RUN_RE = re.compile(r"\b(?:poetry|pdm|uv)\s+run\s+(\S+)")
# Extensions that mark a ``... run <arg>`` target as a script *file* to execute
# rather than a project console script.
_PY_RUN_SCRIPT_SUFFIXES = (".py", ".pyw", ".sh")


def declared_commands(text):
    """Return declared build/test commands as ``{kind, ..., line}`` dicts.

    ``kind`` is one of ``node`` (``{tool, name}``), ``make`` (``{name}``),
    ``cargo_bin`` (``{name}``), ``go_pkg`` (``{path}``), or ``py_run`` (``{name}``).
    """
    out = []
    seen = set()
    for lineno, token in iter_code_tokens(text):
        # Skip English prose sentences so imperatives like "make sure the tests
        # pass" are not parsed into phantom command targets (CORR-02).
        if _looks_like_prose(token):
            continue
        for m in _NODE_CMD_RE.finditer(token):
            tool = m.group(1) or "yarn"
            name = m.group(2) or m.group(3)
            key = ("node", tool, name, lineno)
            if key not in seen:
                seen.add(key)
                out.append({"kind": "node", "tool": tool, "name": name, "line": lineno})
        for m in _MAKE_CMD_RE.finditer(token):
            # A make "target" that is a bare English word ("make sure",
            # "make the ...") is prose, not a Makefile target (CORR-02).
            if m.group(1) in _PROSE_TARGET_WORDS:
                continue
            key = ("make", m.group(1), lineno)
            if key not in seen:
                seen.add(key)
                out.append({"kind": "make", "tool": "make", "name": m.group(1), "line": lineno})
        for m in _CARGO_BIN_RE.finditer(token):
            key = ("cargo_bin", m.group(1), lineno)
            if key not in seen:
                seen.add(key)
                out.append({"kind": "cargo_bin", "tool": "cargo", "name": m.group(1), "line": lineno})
        for m in _GO_PKG_RE.finditer(token):
            key = ("go_pkg", m.group(1), lineno)
            if key not in seen:
                seen.add(key)
                out.append({"kind": "go_pkg", "tool": "go", "path": m.group(1), "line": lineno})
        for m in _PY_RUN_RE.finditer(token):
            name = m.group(1)
            # `uv run path/to/script.py` (or a bare `script.py`) executes a
            # script *file*, not a project console script, so it must never be
            # flagged as a missing console script.
            if "/" in name or "\\" in name or name.endswith(_PY_RUN_SCRIPT_SUFFIXES):
                continue
            key = ("py_run", name, lineno)
            if key not in seen:
                seen.add(key)
                out.append({"kind": "py_run", "tool": "python", "name": name, "line": lineno})
    return out


# Command prefixes that make a backtick token an invocation, not a path.
_CMD_PATH_PREFIXES = (
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


def declared_paths(text):
    """Return repo-relative paths referenced in inline backticks as ``{path, line}``."""
    out = []
    seen = set()
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in re.finditer(r"`([^`]+)`", line):
            token = m.group(1).strip()
            if not token or token in seen:
                continue
            # A backtick span wrapped in matching quotes is a string-literal
            # example value (e.g. `'/usr/bin/google-chrome'`, `"./downloads"`),
            # not a repo path reference. Only the backticks were stripped before,
            # leaving the inner quotes to defeat the absolute-path / value guards
            # below so the quoted value was wrongly flagged as a missing path.
            if len(token) >= 2 and token[0] == token[-1] and token[0] in ("'", '"'):
                continue
            if token.startswith(("http://", "https://")) or "<" in token or "{" in token:
                continue
            if token.startswith(("~", "/", "$")) or ":" in token:
                continue
            if token.startswith(_CMD_PATH_PREFIXES):
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
    """Node-ecosystem package managers named in AGENTS.md (legacy single-ecosystem helper)."""
    pms = set()
    for _lineno, token in iter_code_tokens(text):
        for m in re.finditer(r"\b(npm|pnpm|yarn|bun)\b", token):
            pms.add(m.group(1))
    return pms


_PM_TOKEN_RE = re.compile(r"\b(npm|pnpm|yarn|bun|poetry|pipenv|pdm|uv|pip|cargo|mvn|maven|gradle)\b")
_GO_TOOL_RE = re.compile(r"\bgo\s+(?:build|test|run|mod|vet|install|get|work|generate)\b")


def declared_package_managers_by_ecosystem(text):
    """Return ``{ecosystem: {pm, ...}}`` for package managers named in AGENTS.md code spans."""
    by = {}
    for _lineno, token in iter_code_tokens(text):
        for m in _PM_TOKEN_RE.finditer(token):
            pm = _PM_NORMALIZE.get(m.group(1), m.group(1))
            by.setdefault(PM_TO_ECOSYSTEM[pm], set()).add(pm)
        if _GO_TOOL_RE.search(token):
            by.setdefault("go", set()).add("go")
    return by


def declared_node_version(text):
    """Return ``(major, line)`` for a Node.js version declared in AGENTS.md, else ``(None, None)``."""
    for lineno, line in enumerate(text.splitlines(), 1):
        m = re.search(r"\bnode(?:\.js)?\s*(?:version)?\s*(?:>=?|<=?|==?|\^|~)?\s*v?(\d+)(?:\.\d+|\.x)*", line, re.I)
        if m:
            return int(m.group(1)), lineno
    return None, None


def _declared_two_part(text, keyword):
    """Return ``((major, minor), line)`` for ``<keyword> X.Y`` in AGENTS.md, else ``(None, None)``."""
    pat = re.compile(
        r"\b" + keyword + r"\b\s*(?:version|edition)?\s*(?:>=?|<=?|==?|~=?|\^)?\s*v?(\d+)\.(\d+)",
        re.I,
    )
    for lineno, line in enumerate(text.splitlines(), 1):
        m = pat.search(line)
        if m:
            return (int(m.group(1)), int(m.group(2))), lineno
    return None, None


def declared_python_version(text):
    # Accept ``python`` and ``python3`` spellings; require a dotted X.Y version.
    pat = re.compile(
        r"\bpython(?:3)?\b\s*(?:version)?\s*(?:>=?|<=?|==?|~=?|\^)?\s*v?(\d+)\.(\d+)",
        re.I,
    )
    for lineno, line in enumerate(text.splitlines(), 1):
        m = pat.search(line)
        if m:
            return (int(m.group(1)), int(m.group(2))), lineno
    return None, None


def declared_go_version(text):
    return _declared_two_part(text, "go")


def declared_rust_version(text):
    return _declared_two_part(text, "rust")


def declared_java_version(text):
    pat = re.compile(r"\bjava\b\s*(?:se\s*)?(?:version\s*)?(?:>=?)?\s*v?(1\.\d+|\d+)", re.I)
    for lineno, line in enumerate(text.splitlines(), 1):
        m = pat.search(line)
        if m:
            major = _java_major(m.group(1))
            if major is not None:
                return major, lineno
    return None, None


# ---------------------------------------------------------------------------
# Tiny TOML helpers (stdlib only; ``tomllib`` is 3.11+ so we parse the narrow
# subset we need by hand for 3.9 compatibility).
# ---------------------------------------------------------------------------


def _toml_section_lines(text, header):
    """Return the raw lines inside a ``[header]`` table (excludes array tables)."""
    cur = None
    out = []
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[[") and s.endswith("]]"):
            cur = None
            continue
        if s.startswith("[") and s.endswith("]"):
            cur = s[1:-1].strip()
            continue
        if cur == header:
            out.append(line)
    return out


def _toml_array_tables(text, header):
    """Return a list of line-lists, one per ``[[header]]`` array-of-tables entry."""
    tables = []
    cur = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[[") and s.endswith("]]"):
            cur = [] if s[2:-2].strip() == header else None
            if cur is not None:
                tables.append(cur)
            continue
        if s.startswith("[") and s.endswith("]"):
            cur = None
            continue
        if cur is not None:
            cur.append(line)
    return tables


def _toml_table_keys(text, header):
    """Return the set of ``key = value`` keys declared in a ``[header]`` table."""
    keys = set()
    for line in _toml_section_lines(text, header):
        m = re.match(r'\s*["\']?([A-Za-z0-9._-]+)["\']?\s*=', line)
        if m:
            keys.add(m.group(1))
    return keys


def _two_part(s):
    m = re.search(r"(\d+)\.(\d+)", s or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def _java_major(s):
    """Normalize a Java version token: ``1.8`` -> 8, ``17`` -> 17."""
    if s is None:
        return None
    m = re.match(r"\s*1\.(\d+)", s)
    if m:
        return int(m.group(1))
    m = re.match(r"\s*(\d+)", s)
    return int(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Repository facts — what the code actually says.
# ---------------------------------------------------------------------------


def package_scripts(root):
    """Return the set of package.json script names.

    ``None`` when there is nothing to verify against: either no package.json
    exists, or it is present but could not be read/parsed. Returning ``None``
    (rather than an empty ``set()``) on a parse failure keeps "invalid JSON"
    distinct from "valid JSON with no scripts", so :func:`compare_commands`
    skips the unknown-script check instead of falsely reporting every referenced
    script as a missing script (CORR-01).
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


def python_scripts(root):
    """Return console-script names from ``[project.scripts]`` / ``[tool.poetry.scripts]``.

    ``None`` when no ``pyproject.toml`` exists (nothing to verify against).
    """
    path = root / "pyproject.toml"
    if not path.is_file():
        return None
    text = _read(path)
    return _toml_table_keys(text, "project.scripts") | _toml_table_keys(text, "tool.poetry.scripts")


def cargo_bin_targets(root):
    """Return the set of Cargo binary target names, or ``None`` when no ``Cargo.toml``.

    Combines explicit ``[[bin]]`` names, the default binary (``[package] name`` when
    ``src/main.rs`` exists), and ``src/bin/*.rs`` file stems.
    """
    path = root / "Cargo.toml"
    if not path.is_file():
        return None
    text = _read(path)
    bins = set()
    for table in _toml_array_tables(text, "bin"):
        for line in table:
            m = re.match(r'\s*name\s*=\s*["\']([^"\']+)["\']', line)
            if m:
                bins.add(m.group(1))
    if (root / "src" / "main.rs").is_file():
        for line in _toml_section_lines(text, "package"):
            m = re.match(r'\s*name\s*=\s*["\']([^"\']+)["\']', line)
            if m:
                bins.add(m.group(1))
                break
    bindir = root / "src" / "bin"
    if bindir.is_dir():
        try:
            for entry in bindir.iterdir():
                if entry.suffix == ".rs" and entry.is_file():
                    bins.add(entry.stem)
        except OSError:
            pass
    return bins


def lockfile_managers(root):
    return {mgr for name, mgr in LOCKFILE_MANAGERS.items() if (root / name).is_file()}


def _node_ground_pm(root):
    for name in ("pnpm-lock.yaml", "yarn.lock", "bun.lockb", "bun.lock", "package-lock.json", "npm-shrinkwrap.json"):
        if (root / name).is_file():
            return LOCKFILE_MANAGERS[name], name
    return None, None


def _python_ground_pm(root):
    for name, pm in (
        ("poetry.lock", "poetry"),
        ("uv.lock", "uv"),
        ("pdm.lock", "pdm"),
        ("Pipfile.lock", "pipenv"),
        ("Pipfile", "pipenv"),
    ):
        if (root / name).is_file():
            return pm, name
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        text = _read(pyproject)
        if re.search(r"(?m)^\[tool\.poetry\b", text):
            return "poetry", "pyproject.toml"
        if re.search(r"(?m)^\[tool\.uv\b", text):
            return "uv", "pyproject.toml"
        if re.search(r"(?m)^\[tool\.pdm\b", text):
            return "pdm", "pyproject.toml"
    if (root / "requirements.txt").is_file():
        return "pip", "requirements.txt"
    return None, None


def _rust_ground_pm(root):
    for name in ("Cargo.lock", "Cargo.toml"):
        if (root / name).is_file():
            return "cargo", name
    return None, None


def _go_ground_pm(root):
    for name in ("go.mod", "go.sum"):
        if (root / name).is_file():
            return "go", name
    return None, None


def _java_ground_pm(root):
    has_pom = (root / "pom.xml").is_file()
    gradle = next((n for n in ("build.gradle", "build.gradle.kts") if (root / n).is_file()), None)
    if has_pom and not gradle:
        return "maven", "pom.xml"
    if gradle and not has_pom:
        return "gradle", gradle
    return None, None  # ambiguous (both) or neither


ECOSYSTEM_GROUND_PM = {
    "node": _node_ground_pm,
    "python": _python_ground_pm,
    "go": _go_ground_pm,
    "rust": _rust_ground_pm,
    "java": _java_ground_pm,
}


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


def python_ground_versions(root):
    """Return ``[(source_label, (major, minor)), ...]`` pinned Python versions."""
    out = []
    pyver = root / ".python-version"
    if pyver.is_file():
        v = _two_part(_read(pyver))
        if v:
            out.append((".python-version", v))
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        text = _read(pyproject)
        m = re.search(r'requires-python\s*=\s*["\']([^"\']+)["\']', text)
        if m:
            v = _two_part(m.group(1))
            if v:
                out.append(("pyproject.toml requires-python", v))
        for line in _toml_section_lines(text, "tool.poetry.dependencies"):
            mm = re.match(r'\s*python\s*=\s*["\']([^"\']+)["\']', line)
            if mm:
                v = _two_part(mm.group(1))
                if v:
                    out.append(("pyproject.toml tool.poetry.dependencies.python", v))
                break
    setup = root / "setup.py"
    if setup.is_file():
        m = re.search(r'python_requires\s*=\s*["\']([^"\']+)["\']', _read(setup))
        if m:
            v = _two_part(m.group(1))
            if v:
                out.append(("setup.py python_requires", v))
    return out


def go_ground_versions(root):
    path = root / "go.mod"
    if not path.is_file():
        return []
    for line in _read(path).splitlines():
        m = re.match(r"\s*go\s+(\d+)\.(\d+)", line)
        if m:
            return [("go.mod", (int(m.group(1)), int(m.group(2))))]
    return []


def rust_ground_versions(root):
    out = []
    cargo = root / "Cargo.toml"
    if cargo.is_file():
        m = re.search(r'rust-version\s*=\s*["\'](\d+)\.(\d+)', _read(cargo))
        if m:
            out.append(("Cargo.toml rust-version", (int(m.group(1)), int(m.group(2)))))
    for name in ("rust-toolchain.toml", "rust-toolchain"):
        rt = root / name
        if rt.is_file():
            v = _two_part(_read(rt))
            if v:
                out.append((name, v))
            break
    return out


def java_ground_versions(root):
    out = []
    pom = root / "pom.xml"
    if pom.is_file():
        text = _read(pom)
        for tag in ("maven.compiler.release", "maven.compiler.source", "maven.compiler.target", "java.version"):
            m = re.search(r"<" + re.escape(tag) + r">\s*(1\.\d+|\d+)", text)
            if m:
                major = _java_major(m.group(1))
                if major is not None:
                    out.append(("pom.xml " + tag, major))
                    break
    for name in ("build.gradle", "build.gradle.kts"):
        gradle = root / name
        if gradle.is_file():
            text = _read(gradle)
            m = re.search(r"(?:source|target)Compatibility\s*=?\s*(?:JavaVersion\.VERSION_)?[\"']?(1\.\d+|\d+)", text)
            if not m:
                m = re.search(r"languageVersion\s*=\s*JavaLanguageVersion\.of\((\d+)\)", text)
            if m:
                major = _java_major(m.group(1))
                if major is not None:
                    out.append((name, major))
                    break
    return out


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
    py_scripts = python_scripts(root)
    cargo_bins = cargo_bin_targets(root)
    for decl in declared_commands(text):
        kind = decl["kind"]
        line = decl["line"]
        if kind == "node":
            name = decl["name"]
            if name in PACKAGE_MANAGER_BUILTINS:
                continue
            if scripts is not None and name not in scripts:
                findings.append(
                    _finding(
                        "command",
                        "MISMATCH",
                        f"AGENTS.md references `{decl['tool']} run {name}` but package.json has no `{name}` script.",
                        "Add the package.json script or update AGENTS.md to a real script.",
                        f"{decl['tool']} run {name}",
                        "no such package.json script",
                        line,
                    )
                )
        elif kind == "make":
            name = decl["name"]
            if targets is not None and name not in targets:
                findings.append(
                    _finding(
                        "command",
                        "MISMATCH",
                        f"AGENTS.md references `make {name}` but the Makefile has no `{name}` target.",
                        "Add the Makefile target or update AGENTS.md to a real target.",
                        f"make {name}",
                        "no such Makefile target",
                        line,
                    )
                )
        elif kind == "cargo_bin":
            name = decl["name"]
            # Conservative: only flag when we positively parsed a non-empty bin set.
            if cargo_bins and name not in cargo_bins:
                findings.append(
                    _finding(
                        "command",
                        "MISMATCH",
                        f"AGENTS.md references `cargo run --bin {name}` but Cargo.toml declares no such binary target.",
                        "Add the `[[bin]]` target (or `src/bin/{name}.rs`) or update AGENTS.md to a real binary.",
                        f"cargo run --bin {name}",
                        "no such Cargo binary target",
                        line,
                    )
                )
        elif kind == "go_pkg":
            path = decl["path"]
            if "..." in path or not _within_root(root, path):
                continue
            if not (root / path).exists():
                findings.append(
                    _finding(
                        "command",
                        "MISMATCH",
                        f"AGENTS.md references Go package path `{path}` which does not exist in the repository.",
                        "Fix the package path in AGENTS.md or add the missing Go package.",
                        path,
                        "no such Go package path",
                        line,
                    )
                )
        elif kind == "py_run":
            name = decl["name"]
            if name in PYTHON_RUN_BUILTINS:
                continue
            # Conservative: only flag when pyproject declares a non-empty script set.
            if py_scripts and name not in py_scripts:
                findings.append(
                    _finding(
                        "command",
                        "MISMATCH",
                        f"AGENTS.md references `{decl['tool']} run {name}` but pyproject.toml declares "
                        f"no `{name}` console script.",
                        "Add the console script under `[project.scripts]` / "
                        "`[tool.poetry.scripts]` or update AGENTS.md.",
                        f"{decl['tool']} run {name}",
                        "no such pyproject console script",
                        line,
                    )
                )
    return findings


def compare_paths(root, text):
    findings = []
    for decl in declared_paths(text):
        token, line = decl["path"], decl["line"]
        if not _within_root(root, token):
            continue
        if not (root / token).exists():
            findings.append(
                _finding(
                    "path",
                    "MISSING",
                    f"AGENTS.md references path `{token}` which does not exist in the repository.",
                    "Fix or remove the backtick-quoted path in AGENTS.md.",
                    token,
                    "path not found",
                    line,
                )
            )
    return findings


def compare_package_manager(root, text):
    findings = []
    by_eco = declared_package_managers_by_ecosystem(text)
    for eco in ECOSYSTEM_ORDER:
        declared = by_eco.get(eco)
        if not declared or len(declared) != 1:
            continue
        ground_pm, evidence = ECOSYSTEM_GROUND_PM[eco](root)
        if ground_pm is None:
            continue
        declared_pm = next(iter(declared))
        if declared_pm != ground_pm:
            findings.append(
                _finding(
                    "package_manager",
                    "MISMATCH",
                    f"AGENTS.md uses `{declared_pm}` but the repo has `{evidence}`, implying `{ground_pm}`.",
                    f"Align AGENTS.md with `{ground_pm}` or change the {eco} "
                    f"manifest/lockfile to match `{declared_pm}`.",
                    declared_pm,
                    ground_pm,
                )
            )
    return findings


def compare_node_version(root, text):
    findings = []
    declared, line = declared_node_version(text)
    if declared is None:
        return findings
    nvmrc = nvmrc_node_version(root)
    if nvmrc is not None and nvmrc != declared:
        findings.append(
            _finding(
                "node_version",
                "MISMATCH",
                f"AGENTS.md claims Node {declared} but `.nvmrc` pins Node {nvmrc}.",
                "Align AGENTS.md with `.nvmrc` or update `.nvmrc`.",
                f"node {declared}",
                f"node {nvmrc}",
                line,
            )
        )
    engines = engines_node_version(root)
    if engines is not None and engines != declared:
        findings.append(
            _finding(
                "node_version",
                "MISMATCH",
                f"AGENTS.md claims Node {declared} but `package.json` engines.node requires Node {engines}.",
                "Align AGENTS.md with `package.json` engines.node or update engines.node.",
                f"node {declared}",
                f"node {engines}",
                line,
            )
        )
    return findings


def _fmt_version(value):
    return f"{value[0]}.{value[1]}" if isinstance(value, tuple) else str(value)


def _compare_language_version(category, label, declared, line, ground):
    """Generic declared-vs-ground version comparison for a single language."""
    findings = []
    if declared is None:
        return findings
    for source, value in ground:
        if value != declared:
            findings.append(
                _finding(
                    category,
                    "MISMATCH",
                    f"AGENTS.md claims {label} {_fmt_version(declared)} but `{source}` requires "
                    f"{label} {_fmt_version(value)}.",
                    f"Align AGENTS.md with `{source}` or update `{source}`.",
                    f"{label.lower()} {_fmt_version(declared)}",
                    f"{label.lower()} {_fmt_version(value)}",
                    line,
                )
            )
    return findings


def compare_python_version(root, text):
    declared, line = declared_python_version(text)
    return _compare_language_version("python_version", "Python", declared, line, python_ground_versions(root))


def compare_go_version(root, text):
    declared, line = declared_go_version(text)
    return _compare_language_version("go_version", "Go", declared, line, go_ground_versions(root))


def compare_rust_version(root, text):
    declared, line = declared_rust_version(text)
    return _compare_language_version("rust_version", "Rust", declared, line, rust_ground_versions(root))


def compare_java_version(root, text):
    declared, line = declared_java_version(text)
    return _compare_language_version("java_version", "Java", declared, line, java_ground_versions(root))


def _count_declarations(root, text):
    """How many concrete claims were checked (used for the consistency summary)."""
    count = 0
    count += len(declared_commands(text))
    count += len(declared_paths(text))
    by_eco = declared_package_managers_by_ecosystem(text)
    for eco in ECOSYSTEM_ORDER:
        declared = by_eco.get(eco)
        if declared and len(declared) == 1 and ECOSYSTEM_GROUND_PM[eco](root)[0] is not None:
            count += 1
    declared_node, _ = declared_node_version(text)
    if declared_node is not None:
        if nvmrc_node_version(root) is not None:
            count += 1
        if engines_node_version(root) is not None:
            count += 1
    for declared_fn, ground_fn in (
        (declared_python_version, python_ground_versions),
        (declared_go_version, go_ground_versions),
        (declared_rust_version, rust_ground_versions),
        (declared_java_version, java_ground_versions),
    ):
        declared_v, _ = declared_fn(text)
        if declared_v is not None:
            count += len(ground_fn(root))
    return count


ORDER = {
    "command": 0,
    "path": 1,
    "package_manager": 2,
    "node_version": 3,
    "python_version": 4,
    "go_version": 5,
    "rust_version": 6,
    "java_version": 7,
}


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
        findings.extend(compare_python_version(root, text))
        findings.extend(compare_go_version(root, text))
        findings.extend(compare_rust_version(root, text))
        findings.extend(compare_java_version(root, text))
    findings.sort(key=lambda f: (ORDER.get(f["category"], 9), f.get("line", 0)))
    checked = _count_declarations(root, text) if text else 0
    return {"findings": findings, "checked": checked, "mismatches": len(findings)}
