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
import facts  # noqa: E402  # contained reads and repository mutation guard
import registry  # noqa: E402
import scan  # noqa: E402
import semantic  # noqa: E402  # reuse package.json/Makefile/lockfile/node fact readers

# Lockfile -> package-manager map, from the shared registry single source of
# truth (includes bun) so the draft generator and the conflict-default
# recommender agree with semantic.py / check_drift.py on which manager a
# committed lockfile implies (TD-01).
LOCKFILE_MANAGERS = registry.LOCKFILE_MANAGERS


def _build_stubs():
    """Derive the STUBS mapping from the shared agent-config registry.

    Only tools flagged ``canonicalizable`` with declared ``stub_paths`` get a stub
    spec; the ``content`` mirrors the registry byte-for-byte so downgraded stub
    output is unchanged for tools that already worked. See assets/agent-tools.json.
    """
    stubs = {}
    for tool in registry.canonicalizable_tools():
        stubs[tool["id"]] = {
            "paths": list(tool["stub_paths"]),
            "content": tool["stub_content"],
            "marker": "AGENTS.md",
        }
    return stubs


STUBS = _build_stubs()

CURSOR_RULE_STUB = (
    "---\nalwaysApply: true\n---\n\n"
    "Canonical agent instructions live in `AGENTS.md` (single source of truth). "
    "Do not duplicate rules here.\n"
)


def git_clean_or_forced(root, force):
    if force:
        return
    inside = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"], text=True, capture_output=True
    )
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        raise SystemExit("Refusing to write: target is not a git repo. Use --force to override.")
    status = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], text=True, capture_output=True)
    if status.returncode != 0 or status.stdout.strip():
        raise SystemExit("Refusing to write: git working tree is dirty. Commit/stash first or use --force.")


def unified_diff(path, old, new):
    return "".join(
        difflib.unified_diff(
            old.splitlines(True),
            new.splitlines(True),
            fromfile=f"a/{path.as_posix()}",
            tofile=f"b/{path.as_posix()}",
            lineterm="",
        )
    )


def render_plan(report, root=None):
    lines = ["# Phase 1 — Treat Merge Plan Skeleton", ""]
    lines.append("## Inventory")
    lines.append("| File | Tool | Bytes | Lines |")
    lines.append("|---|---|---:|---:|")
    for f in report["files"]:
        lines.append(f"| `{f['path']}` | {f['tool']} | {f['bytes']} | {f['lines']} |")
    lines.extend(["", "## Overlap clusters"])
    if report["overlaps"]:
        for o in report["overlaps"]:
            lines.append(f"- `{o['a']}` ↔ `{o['b']}`: {o['percent']}%")
    else:
        lines.append("- No overlaps above the threshold.")
    lines.extend(["", "## Conflict list"])
    if report["conflicts"]:
        for c in report["conflicts"]:
            scope = f" (scope `{c['scope']}`)" if c.get("scope") else ""
            lines.append(f"- **{c['signal']}**{scope}")
            for value, entries in c["values"].items():
                lines.append(f"  - `{value}`")
                for e in entries:
                    lines.append(f"    - {e['path']}:{e['line']} `{e['evidence']}`")
    else:
        lines.append("- No obvious conflict candidates.")
    lines.extend(["", "## Declared scope overrides (preserve; non-blocking)"])
    if report.get("scope_overrides"):
        lines.append(
            "Nested canonical files are intentional nearest-file scopes. Preserve these "
            "parent → child differences unless the repository owner explicitly removes a scope:"
        )
        for override in report["scope_overrides"]:
            parent_values = ", ".join(f"`{value}`" for value in override["parent_values"])
            values = ", ".join(f"`{value}`" for value in override["values"])
            lines.append(
                f"- **{override['signal']}**: `{override['parent_scope']}` ({parent_values}) "
                f"→ `{override['scope']}` ({values})"
            )
    else:
        lines.append("- No parent → child canonical overrides detected.")
    lines.extend(
        [
            "",
            "## TODO decision checklist",
            "- [ ] Confirm the migration scope (whole repository / subdirectory / selected files).",
            "- [ ] Record the human adjudication for every conflict.",
            "- [ ] Manually write the root `AGENTS.md`, keeping only information "
            "agents cannot infer from code or manifests.",
            "- [ ] Run `canonicalize.py --write-stubs` to preview the downgrade diff.",
            "- [ ] Run `canonicalize.py --validate` to re-check the result.",
        ]
    )
    lines.extend(render_merge_suggestions(report, root))
    return "\n".join(lines) + "\n"


def recommend_conflict_value(values):
    """Deterministically pick one recommended value for a conflict signal.

    Rule: prefer the value with the most supporting evidence entries; break ties
    by the lexicographically smallest value so the recommendation is stable.
    """
    best_value = None
    best_count = -1
    for value in sorted(values.keys()):
        count = len(values[value])
        if count > best_count:
            best_value = value
            best_count = count
    return best_value


def _lockfile_backed_manager(root):
    """Return ``(manager, lockfile)`` when exactly one lockfile-backed package
    manager is committed, else ``(None, None)``.

    A committed lockfile is stronger evidence than instruction-file text, so it
    is the preferred tie-breaker for a ``package_manager`` conflict.
    """
    if root is None:
        return None, None
    root = Path(root)
    managers = facts.lockfile_managers(root)
    if len(managers) == 1:
        manager = next(iter(managers))
        lockfile = next(
            name
            for name, candidate in LOCKFILE_MANAGERS.items()
            if candidate == manager and facts.is_file_within_root(root, root / name)
        )
        return manager, lockfile
    return None, None


def _ground_node_version(root):
    """Return ``(major_version, source)`` for the Node version the repo pins via
    ``.nvmrc`` or ``package.json`` engines.node, else ``(None, None)``."""
    if root is None:
        return None, None
    root = Path(root)
    nvmrc = semantic.nvmrc_node_version(root)
    if nvmrc is not None:
        return nvmrc, ".nvmrc"
    engines = semantic.engines_node_version(root)
    if engines is not None:
        return engines, "package.json engines.node"
    return None, None


def recommend_conflict_default(signal, values, root=None):
    """Return ``(recommended_value, rationale)`` for a conflict signal.

    Prefers a repository *fact* when one settles the conflict (a committed
    lockfile for ``package_manager``, ``.nvmrc`` / engines.node for
    ``node_version``); otherwise falls back to :func:`recommend_conflict_value`
    (most-supported value, ties broken lexicographically) with a generic
    rationale. Deterministic.
    """
    if signal == "package_manager":
        mgr, lockfile = _lockfile_backed_manager(root)
        if mgr is not None and mgr in values:
            return mgr, f"backed by the committed lockfile `{lockfile}`"
    if signal == "node_version":
        version, source = _ground_node_version(root)
        if version is not None:
            # `values` is keyed by the full declared string (e.g. "node 18.2.0"),
            # not the bare major `_ground_node_version` returns, so compare by
            # normalized major (registry.node_version_major) rather than exact
            # string equality — otherwise a repo pinned to Node 20 via .nvmrc
            # with only dotted-version conflicts (e.g. "node 18.2.0") never
            # matches and silently falls through to the vote-count tiebreak,
            # contradicting this function's own "prefers a repository fact"
            # docstring. Mirrors scan.py's `_conflict_key` fix for the same bug.
            for candidate in values:
                if registry.node_version_major(candidate) == version:
                    return candidate, f"matches `{source}`"
    return recommend_conflict_value(values), "most configuration files agree; ties broken alphabetically"


def _evidence_ref(entry):
    return f"{entry['path']}:{entry['line']}"


def render_merge_suggestions(report, root=None):
    """Concrete, actionable semi-automatic merge suggestions derived from scan results.

    Deterministic: overlaps and conflicts are already ordered by scan.py, and the
    recommended conflict value is chosen by a stable, fact-aware rule (see
    recommend_conflict_default). When ``root`` is provided the recommendation
    prefers repository facts (lockfile, .nvmrc/engines.node) over vote counts.
    """
    lines = ["", "## Merge suggestions (semi-automatic)", "Canonical file: `AGENTS.md` (single source of truth)."]
    nested_canonical_paths = {
        row["path"]
        for row in report.get("instruction_scopes", [])
        if row.get("scope") not in (None, "", ".")
    }

    lines.append("")
    lines.append("### Overlap consolidation")
    if report["overlaps"]:
        for o in report["overlaps"]:
            lines.append(
                f"- [ ] `{o['a']}` \u2194 `{o['b']}` ({o['percent']}% shared): "
                f"keep the shared content in `AGENTS.md` and reduce these files to stubs:"
            )
            for path in (o["a"], o["b"]):
                if path == "AGENTS.md":
                    # The canonical single-source-of-truth file is the merge
                    # TARGET named on the line above ("keep the shared content in
                    # `AGENTS.md`"), not a file to reduce to an import stub
                    # pointing at itself. Only its overlap partner is downgraded.
                    continue
                if path in nested_canonical_paths:
                    lines.append(
                        f"  - [ ] preserve nested canonical `{path}` and remove only redundant shared content; "
                        "do not replace this scope with a root import stub"
                    )
                else:
                    lines.append(f"  - [ ] reduce `{path}` to an import stub pointing at `AGENTS.md`")
    else:
        lines.append("- No overlap clusters above the threshold; nothing to consolidate.")

    lines.append("")
    lines.append("### Conflict resolutions")
    if report["conflicts"]:
        for c in report["conflicts"]:
            values = c["values"]
            recommended, rationale = recommend_conflict_default(c["signal"], values, root)
            rec_entries = values[recommended]
            rec_evidence = ", ".join(f"`{_evidence_ref(e)}`" for e in rec_entries)
            others = []
            for value in sorted(values.keys()):
                if value == recommended:
                    continue
                ev = ", ".join(f"`{_evidence_ref(e)}`" for e in values[value])
                others.append(f"`{value}` ({ev})")
            other_text = "; ".join(others) if others else "none"
            scope = f" in scope `{c['scope']}`" if c.get("scope") else ""
            lines.append(
                f"- [ ] **{c['signal']}**{scope} \u2192 recommend `{recommended}` "
                f"(evidence: {rec_evidence}; rationale: {rationale}); record it in `AGENTS.md` and drop conflicting "
                f"lines from the other files. Other candidates: {other_text}."
            )
    else:
        lines.append("- No conflict signals detected; no adjudication needed.")

    lines.append("")
    lines.append("### Nested canonical scopes to preserve")
    if report.get("scope_overrides"):
        for override in report["scope_overrides"]:
            lines.append(
                f"- [ ] Preserve `{override['scope']}` as a nested canonical scope overriding "
                f"`{override['parent_scope']}` for **{override['signal']}**; "
                "do not collapse it into a root stub."
            )
    else:
        lines.append("- No nested override layers need preservation.")

    return lines


def write_plan(args):
    root = Path(args.repo_root).resolve()
    report = scan.scan_repo(root, args.max_bytes)
    content = render_plan(report, root)
    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
    else:
        print(content, end="")


DRAFT_PROVENANCE = "<!-- Auto-drafted by `ai-harness-doctor canonicalize.py --draft`. -->"
INFERRED = "(inferred — confirm)"
SUGGESTED = "(suggested default)"
DRAFT_TODOS = [
    "TODO: Describe what this repository does, its main subsystems, "
    "and boundaries an agent cannot infer from code alone.",
    "TODO: List only the commands agents must run and any required preconditions.",
    "TODO: Document repository-specific conventions not already enforced "
    "by a formatter, linter, type checker, or manifest.",
    "TODO: Explain when tests are required, where fixtures live, and which test scopes are safe to run locally.",
    "TODO: Call out secrets, production resources, data boundaries, and destructive commands.",
    "TODO: Document commit message style and PR validation expectations.",
    "# TODO: no build/test commands could be inferred; add the exact commands agents must run.",
]
DRAFT_BANNER = [
    DRAFT_PROVENANCE,
    '<!-- Lines tagged "(inferred — confirm)" are mechanical guesses derived from repository facts; -->',
    '<!-- lines tagged "(suggested default)" are safe conventions to keep. Replace every TODO, review -->',
    "<!-- each inference, and delete this banner before committing. -->",
]

# package.json scripts worth surfacing in a Build & test draft, in a stable order.
DRAFT_SCRIPT_ORDER = ["test", "build", "lint", "typecheck", "dev", "start"]
DRAFT_MAKE_ORDER = ["test", "build", "lint"]

# Python package-manager -> (install command, run-prefix). ``run_prefix`` is
# prepended to tool invocations (e.g. ``uv run pytest``); pip has no run wrapper.
PYTHON_MANAGER_COMMANDS = {
    "uv": ("uv sync", "uv run "),
    "poetry": ("poetry install", "poetry run "),
    "pdm": ("pdm install", "pdm run "),
    "pipenv": ("pipenv install", "pipenv run "),
    "pip": ("pip install -e .", ""),
}

# A backtick/fenced token from a CLAUDE.md is treated as a real Python
# build/test/lint command only when its first token is one of these runners.
_PY_CLAUDE_CMD_RE = re.compile(
    r"^(?:(?:uv|poetry|pdm|pipenv)\s+run\s+\S+"
    r"|pytest\b|ruff\b|pyright\b|mypy\b|tox\b|nox\b|pre-commit\b"
    r"|python3?\s+-m\s+\S+)"
)

def _detected_package_manager(root):
    """Return ``(manager, rationale)`` for the repo's primary Node package manager.

    A committed lockfile wins; otherwise a bare ``package.json`` implies npm.
    Returns ``(None, None)`` for non-Node repositories.
    """
    mgr, lockfile = _lockfile_backed_manager(root)
    if mgr is not None:
        return mgr, f"from the committed `{lockfile}` lockfile"
    if facts.lockfile_managers(root):
        return None, None
    field_manager = facts.package_manager_field(root)
    if field_manager is not None:
        return field_manager, "from the contained `package.json#packageManager` field"
    if facts.is_file_within_root(root, root / "package.json"):
        return "npm", "`package.json` present (no lockfile; npm assumed)"
    return None, None


def _detected_python_manager(root):
    """Return ``(manager, rationale)`` for the repo's Python package manager, or
    ``(None, None)`` for non-Python repositories.

    Reuses ``semantic._python_ground_pm`` (lockfile / ``[tool.*]`` table /
    requirements.txt precedence) so the draft and the semantic checks agree.
    """
    mgr, source = semantic._python_ground_pm(root)
    if mgr is not None:
        return mgr, f"from `{source}`"
    return None, None


def _has_pytest(root):
    """True when the repo shows evidence of a pytest-based test setup."""
    if facts.is_dir_within_root(root, root / "tests") or facts.is_dir_within_root(root, root / "test"):
        return True
    for name in ("pytest.ini", "conftest.py", "tox.ini"):
        if facts.is_file_within_root(root, root / name):
            return True
    pyproject = root / "pyproject.toml"
    text = facts.read_text_within_root(root, pyproject, errors="replace")
    if text is not None and "pytest" in text:
        return True
    return False


def _has_ruff(root):
    """True when the repo shows evidence of ruff being configured."""
    if facts.is_file_within_root(root, root / "ruff.toml") or facts.is_file_within_root(
        root, root / ".ruff.toml"
    ):
        return True
    pyproject = root / "pyproject.toml"
    text = facts.read_text_within_root(root, pyproject, errors="replace")
    if text is not None and "ruff" in text:
        return True
    return False


def _claude_documented_commands(root):
    """Return build/test/lint commands documented in an existing ``CLAUDE.md``.

    Scans the same fenced-code and inline-backtick tokens as the semantic engine
    (``semantic.iter_code_tokens``) and keeps only tokens whose first word is a
    recognized Python runner (``uv run``/``poetry run``/``pytest``/``ruff``/...).
    Returns a de-duplicated, appearance-ordered list of command strings. These
    are the most reliable signal because the project already documents them for
    humans. Read-only; empty list when there is no ``CLAUDE.md``.
    """
    path = root / "CLAUDE.md"
    text = facts.read_text_within_root(root, path, errors="replace")
    if text is None:
        return []
    commands = []
    seen = set()
    for _lineno, token in semantic.iter_code_tokens(text):
        candidate = token.strip()
        # Drop trailing inline comments (e.g. "uv run pytest  # CI tests").
        candidate = re.split(r"\s{2,}#|\s+#\s", candidate, maxsplit=1)[0].strip()
        if not candidate or not _PY_CLAUDE_CMD_RE.match(candidate):
            continue
        if candidate not in seen:
            seen.add(candidate)
            commands.append(candidate)
    return commands


def _draft_python_commands(root):
    """Return ``[(command, note), ...]`` inferred build/test/lint commands for a
    Python repo, or ``[]`` for a non-Python repo.

    Sources, in order: the detected Python package manager install command,
    commands already documented in an existing ``CLAUDE.md``, and common
    test/lint runners (pytest, ruff) when the repo shows evidence of them. Every
    command is tagged ``(inferred — confirm)`` to match the Node/Make style.
    """
    pm, pm_why = _detected_python_manager(root)
    if pm is None:
        return []
    install_cmd, run_prefix = PYTHON_MANAGER_COMMANDS[pm]
    if (
        pm == "pip"
        and not facts.is_file_within_root(root, root / "pyproject.toml")
        and facts.is_file_within_root(root, root / "requirements.txt")
    ):
        install_cmd = "pip install -r requirements.txt"
    commands = [(install_cmd, f"{INFERRED} Python package manager {pm_why}")]
    seen = {install_cmd}

    # Commands the project already documents for humans are the strongest signal.
    for cmd in _claude_documented_commands(root):
        if cmd not in seen:
            seen.add(cmd)
            commands.append((cmd, f"{INFERRED} documented in CLAUDE.md"))

    # Fall back to common runners only when there is evidence of them AND the
    # project did not already document a command for that tool, so a bare library
    # without a test/lint setup gets no spurious commands and we avoid emitting a
    # near-duplicate of a CLAUDE.md command.
    already = " ".join(cmd for cmd, _ in commands)
    for tool, cmd_suffix, present, label in (
        ("pytest", "pytest", _has_pytest(root), "common Python test runner"),
        ("ruff", "ruff check", _has_ruff(root), "common Python lint runner"),
    ):
        if not present or re.search(rf"\b{re.escape(tool)}\b", already):
            continue
        cmd = f"{run_prefix}{cmd_suffix}".strip()
        if cmd not in seen:
            seen.add(cmd)
            commands.append((cmd, f"{INFERRED} {label}"))
    return commands


def _draft_build_lines(root):
    """Build a fact-derived Build & test command block (list of markdown lines)."""
    lines = []
    pm, pm_why = _detected_package_manager(root)
    scripts = semantic.package_scripts(root)
    targets = semantic.make_targets(root)
    commands = []
    if pm is not None:
        commands.append((f"{pm} install", f"{INFERRED} package manager {pm_why}"))
        for name in DRAFT_SCRIPT_ORDER:
            if scripts and name in scripts:
                commands.append((f"{pm} run {name}", f'{INFERRED} from package.json "scripts"'))
    if targets:
        for name in DRAFT_MAKE_ORDER:
            if name in targets:
                commands.append((f"make {name}", f"{INFERRED} from a Makefile target"))
    # Python repos (pyproject + uv/poetry/pdm/pip) infer their own command set.
    commands.extend(_draft_python_commands(root))
    lines.append("```bash")
    if commands:
        width = max(len(cmd) for cmd, _ in commands)
        for cmd, note in commands:
            lines.append(f"{cmd.ljust(width)}  # {note}")
    else:
        lines.append(DRAFT_TODOS[6])
    lines.append("```")
    # Surface pyproject console scripts as a note so agents know the entry points
    # without cluttering the command block (a package can declare many aliases).
    py_scripts = semantic.python_scripts(root)
    if py_scripts:
        names = ", ".join(f"`{n}`" for n in sorted(py_scripts))
        lines += ["", f"- Console scripts declared in `pyproject.toml`: {names}. {INFERRED}"]
    return lines


def _draft_conflict_lines(report, root):
    """Suggested default resolutions for every scan conflict (list of markdown lines)."""
    conflicts = report.get("conflicts", [])
    if not conflicts:
        return []
    lines = ["", f"Conflicting signals were detected across config files; suggested defaults {INFERRED}:"]
    for c in conflicts:
        recommended, rationale = recommend_conflict_default(c["signal"], c["values"], root)
        lines.append(f"- `{c['signal']}` \u2192 `{recommended}` ({rationale})")
    return lines


def render_draft(report, root):
    """Render a starter AGENTS.md filled with deterministic, fact-derived content.

    Every canonical section from assets/AGENTS.template.md is present. Inferred
    lines are tagged ``(inferred — confirm)`` and safe conventions ``(suggested
    default)`` so a human can quickly separate mechanical guesses from prose they
    must still write. Read-only with respect to the scanned repository.
    """
    root = Path(root)
    snapshot = report.get("project_snapshot", {})
    stack = snapshot.get("tech_stack", [])
    existing = snapshot.get("existing_files", {})
    ci = existing.get("ci", [])
    lint_format = existing.get("lint_format", [])
    typecheck = existing.get("typecheck", [])
    scripts = semantic.package_scripts(root)

    lines = list(DRAFT_BANNER)

    lines += ["", "# Project overview", ""]
    lines.append(DRAFT_TODOS[0])
    if stack:
        stack_text = "; ".join(f"{s['language']} ({', '.join(f'`{m}`' for m in s['markers'])})" for s in stack)
        lines += ["", f"- Detected tech stack: {stack_text}. {INFERRED}"]

    lines += ["", "# Build & test", ""]
    lines.append(DRAFT_TODOS[1])
    lines += [""]
    lines += _draft_build_lines(root)
    if ci:
        ci_text = ", ".join(f"`{c}`" for c in ci)
        lines += ["", f"- Continuous integration: {ci_text}. {INFERRED}"]
    lines += _draft_conflict_lines(report, root)

    lines += ["", "# Conventions", ""]
    lines.append(DRAFT_TODOS[2])
    if lint_format:
        lf_text = ", ".join(f"`{c}`" for c in lint_format)
        lines += [
            "",
            f"- Lint/format tooling is configured via {lf_text}; follow it rather than hand-formatting. {INFERRED}",
        ]
    if typecheck:
        tc_text = ", ".join(f"`{c}`" for c in typecheck)
        lines += [f"- Type checking is configured via {tc_text}. {INFERRED}"]

    lines += ["", "# Testing requirements", ""]
    lines.append(DRAFT_TODOS[3])
    if scripts and "test" in scripts:
        pm, _ = _detected_package_manager(root)
        if pm is not None:
            lines += ["", f"- A `test` script is defined; run `{pm} run test` before pushing. {INFERRED}"]

    lines += ["", "# Safety", ""]
    lines.append(DRAFT_TODOS[4])
    lines += [
        "",
        f"- Never commit secrets, tokens, or credentials. {SUGGESTED}",
        f"- Treat the repository as read-only unless a change is explicitly requested. {SUGGESTED}",
    ]

    lines += ["", "# Commit & PR", ""]
    lines.append(DRAFT_TODOS[5])
    lines += ["", f"- Land changes through pull requests; do not push directly to the default branch. {SUGGESTED}"]
    if ci:
        ci_text = ", ".join(f"`{c}`" for c in ci)
        lines.append(f"- Ensure CI is green before merging (workflows: {ci_text}). {INFERRED}")

    return "\n".join(lines) + "\n"


def write_draft(args):
    root = Path(args.repo_root).resolve()
    report = scan.scan_repo(root, args.max_bytes)
    content = render_draft(report, root)
    if args.output:
        out = Path(args.output)
        if out.exists() and not args.force:
            raise SystemExit(f"Refusing to overwrite existing {out}. Use --force to overwrite.")
        out.write_text(content, encoding="utf-8")
        print(f"Wrote draft AGENTS.md to {out}")
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
            # This historical migration surface is deliberately top-level only.
            # Scanner recursive discovery is read authority, not permission to
            # recursively delete nested, team-owned Cursor rule directories.
            for p in sorted(rules_dir.iterdir()):
                if p.is_file() and p.name != "agents-md.mdc" and p.suffix in {".md", ".mdc"}:
                    changes.append({"action": "delete", "path": p})
    return changes


def write_stubs(args):
    root = Path(args.repo_root).resolve()
    readiness = canonical_readiness_findings(
        root,
        args.max_bytes,
        args.require_sections,
    )
    if any(finding["check"] == "AGENTS_EXISTS" for finding in readiness):
        raise SystemExit("AGENTS.md must exist before writing stubs.")
    tools = [t.strip() for t in args.tools.split(",") if t.strip()]
    changes = collect_stub_targets(root, tools)
    if args.apply:
        blockers = [
            finding
            for finding in readiness
            if finding.get("level") == "ERROR"
        ]
        if blockers:
            checks = ", ".join(
                dict.fromkeys(finding["check"] for finding in blockers)
            )
            raise SystemExit(
                "Refusing stub apply: canonical readiness failed "
                f"({checks}). Run `ai-harness-doctor validate {root}` and "
                "resolve every error before replacing instruction sources."
            )
        git_clean_or_forced(root, args.force)
    if not changes:
        print("No existing tool files matched; nothing to change.")
        return
    unsafe = [
        change["path"].relative_to(root).as_posix()
        for change in changes
        if facts.safe_mutation_path(root, change["path"]) is None
    ]
    if unsafe:
        joined = ", ".join(f"`{path}`" for path in unsafe)
        raise SystemExit(
            "Refusing unsafe repository mutation through a symlink or escaping path: "
            + joined
        )
    for change in changes:
        path = change["path"]
        rp = path.relative_to(root)
        if facts.safe_mutation_path(root, path) is None:
            raise SystemExit(f"Refusing unsafe repository mutation: `{rp.as_posix()}`")
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


# Heuristic signal families that a large AGENTS.md is actually end-user
# *library / reference documentation* (installation + usage/API reference aimed
# at consumers of the package) rather than a *contributor guide* (build/test
# workflow + repo conventions aimed at people changing this repo). Each family
# is matched independently; the classifier below only trusts the "library doc"
# verdict when several families agree, so a normal contributor guide — even a
# long one — is never misclassified and keeps the strict section/size checks.
_LIBRARY_DOC_SIGNALS = (
    # 1. Installation / quickstart aimed at consumers of the package.
    re.compile(
        r"(?im)^\s{0,3}#{1,6}\s+.*\b(quick\s?start|getting\s+started|installation|install)\b"
        r"|\b(?:pip|pipx|uv|poetry|pdm)\s+(?:install|add|sync)\b",
    ),
    # 2. API / parameter / usage reference sections (documentation for callers).
    re.compile(
        r"(?im)^\s{0,3}#{1,6}\s+.*\b(parameters?|api|usage|examples?|reference|available\s+\w+|configuration)\b",
    ),
    # 3. End-user support / operational sections, not contributor workflow.
    re.compile(
        r"(?im)^\s{0,3}#{1,6}\s+.*\b(get\s+help|telemetry|faq|troubleshooting|support"
        r"|supported\s+models|going\s+to\s+production)\b",
    ),
    # 4. Library import/usage code examples (consumer-facing snippets).
    re.compile(r"(?im)^\s*(?:from\s+[\w.]+\s+import\b|import\s+[\w.]+)"),
)


def _looks_like_library_doc(text):
    """Return True when this AGENTS.md reads as end-user library/reference
    documentation rather than a contributor guide.

    Conservative on purpose: it requires at least three of the four independent
    signal families in ``_LIBRARY_DOC_SIGNALS`` to match, so we only relax the
    strict contributor-guide checks when we are confident the file is a library
    doc. A conventional contributor guide (Build & test / Conventions / Testing)
    matches at most one or two families and stays under strict validation.
    """
    matched = sum(1 for pattern in _LIBRARY_DOC_SIGNALS if pattern.search(text))
    return matched >= 3


def unresolved_draft_markers(text):
    """Return product-owned provisional markers without echoing user content."""
    records = []
    seen_kinds = set()
    exact_todos = set(DRAFT_TODOS)
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        kind = None
        if stripped == DRAFT_PROVENANCE:
            kind = "provenance"
        elif stripped in exact_todos:
            kind = "todo"
        elif INFERRED in line:
            kind = "inferred"
        elif SUGGESTED in line:
            kind = "suggested"
        if kind is not None and kind not in seen_kinds:
            seen_kinds.add(kind)
            records.append({"kind": kind, "line": lineno})
    return records


def canonical_readiness_findings(root, max_bytes, require_sections):
    """Return canonical AGENTS.md blockers shared by validate and stub apply."""
    root = Path(root).resolve()
    findings = []
    agents = root / "AGENTS.md"
    agents_unsafe = agents.is_symlink() or (
        agents.exists() and facts.safe_mutation_path(root, agents) is None
    )
    if agents_unsafe:
        findings.append(
            {
                "level": "ERROR",
                "check": "UNSAFE_PATH",
                "path": "AGENTS.md",
                "message": "AGENTS.md is a symlink or escapes the repository root",
            }
        )
    elif not facts.is_file_within_root(root, agents):
        findings.append({"level": "ERROR", "check": "AGENTS_EXISTS", "message": "AGENTS.md is missing"})
    else:
        data = facts.read_bytes_within_root(root, agents) or b""
        text = data.decode("utf-8", errors="replace")
        # A large end-user library/reference AGENTS.md is not a contributor guide,
        # so it must not be hard-failed for lacking contributor-guide sections or
        # for exceeding the contributor-guide size budget. When we are confident it
        # is a library doc, downgrade those two checks from blocking ERROR to a
        # non-blocking WARN so validate reports them without failing (exit 0).
        library_doc = _looks_like_library_doc(text)
        soft_level = "WARN" if library_doc else "ERROR"
        note = " (library/reference doc: relaxed to non-blocking)" if library_doc else ""
        if len(data) > max_bytes:
            findings.append(
                {
                    "level": soft_level,
                    "check": "SIZE",
                    "message": f"AGENTS.md is {len(data)} bytes, above {max_bytes}{note}",
                }
            )
        for req in require_sections.split(","):
            if req.strip() and not heading_present(text, req.strip()):
                findings.append(
                    {
                        "level": soft_level,
                        "check": "SECTION",
                        "message": f"Missing required heading: {req.strip()}{note}",
                    }
                )
        marker_labels = {
            "provenance": "auto-draft provenance banner",
            "todo": "generated TODO prompt",
            "inferred": "unconfirmed inferred value",
            "suggested": "unreviewed suggested default",
        }
        for marker in unresolved_draft_markers(text):
            findings.append(
                {
                    "level": "ERROR",
                    "check": "DRAFT_REVIEW",
                    "path": "AGENTS.md",
                    "line": marker["line"],
                    "message": (
                        f"AGENTS.md still contains a {marker_labels[marker['kind']]}; "
                        "review the draft and remove product-owned provisional markers."
                    ),
                }
            )
    return findings


def validate(args):
    root = Path(args.repo_root).resolve()
    findings = canonical_readiness_findings(
        root,
        args.max_bytes,
        args.require_sections,
    )
    agents = root / "AGENTS.md"
    if agents.exists() or agents.is_symlink():
        all_canonicalizable = [t["id"] for t in registry.canonicalizable_tools()]
        for change in collect_stub_targets(root, all_canonicalizable):
            path = change["path"]
            if path.is_symlink() or facts.safe_mutation_path(root, path) is None:
                findings.append(
                    {
                        "level": "ERROR",
                        "check": "UNSAFE_PATH",
                        "path": path.relative_to(root).as_posix(),
                        "message": "tool file is a symlink or escapes the repository root",
                    }
                )
                continue
            if not facts.is_file_within_root(root, path):
                continue
            if change["action"] == "write":
                text = facts.read_text_within_root(root, path, errors="replace") or ""
                if "AGENTS.md" in text and len(text.encode("utf-8")) <= registry.STUB_POINTER_MAX_BYTES:
                    continue
            # Existing full files are allowed before stub-writing; check_drift catches post-migration re-divergence.
            findings.append(
                {
                    "level": "NOTICE",
                    "check": "STUB",
                    "path": path.relative_to(root).as_posix(),
                    "message": "tool file not yet downgraded to stub (or regrew)",
                }
            )
    errors = [f for f in findings if f.get("level") == "ERROR"]
    result = {"ok": not errors, "findings": findings}
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if findings:
            print("Phase 1 treat validation failed:" if errors else "Phase 1 treat validation passed (with notices):")
            for f in findings:
                loc = f" {f['path']}" if "path" in f else ""
                print(f"- [{f['level']}/{f['check']}]{loc} {f['message']}")
        else:
            print("Phase 1 treat validation passed.")
    return 0 if not errors else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Canonicalization mechanics for AGENTS.md.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", action="store_true")
    mode.add_argument(
        "--draft",
        action="store_true",
        help="Auto-draft a starter AGENTS.md filled with fact-derived content (write with -o).",
    )
    mode.add_argument("--write-stubs", action="store_true")
    mode.add_argument("--validate", action="store_true")
    parser.add_argument("repo_root", nargs="?", default=".")
    parser.add_argument("-o", "--output")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--tools",
        default=",".join(t["id"] for t in registry.canonicalizable_tools()),
        help="Comma-separated tool ids to write/validate stubs for (default: every "
        "canonicalizable tool in the registry — see assets/agent-tools.json).",
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--max-bytes", type=int, default=32768)
    parser.add_argument(
        "--require-sections",
        default="Project overview,Build & test,Conventions",
        help="Comma-separated list of H1 headings that --validate requires the "
        "canonical AGENTS.md to contain (default: 'Project overview,Build & test,"
        "Conventions'). A missing heading is reported as a SECTION finding "
        "(ERROR, or WARN for a library/reference doc). Only affects --validate.",
    )
    args = parser.parse_args(argv)
    if args.plan:
        write_plan(args)
        return 0
    if args.draft:
        write_draft(args)
        return 0
    if args.write_stubs:
        write_stubs(args)
        return 0
    return validate(args)


if __name__ == "__main__":
    sys.exit(main())
