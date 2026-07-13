#!/usr/bin/env python3
"""Read-only drift guard for canonical AGENTS.md files."""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote

# canonicalize.py lives in the same scripts/ dir; reuse its canonical stub
# content/logic instead of duplicating it here.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import canonicalize  # noqa: E402
import facts  # noqa: E402  # shared repo fact-readers (single source of truth, TD-02)
import plugins  # noqa: E402  # user-extensible deterministic rule plugins
import registry  # noqa: E402
import scan  # noqa: E402  # reuse scan.SKIP_DIRS so the drift walk prunes the same vendored dirs

DEFAULT_MAX_BYTES = 32768
# Flat list of every canonical stub path, derived (in registry order) from the
# shared agent-config registry so the drift guard tracks exactly the same stubs
# canonicalize.py writes. See assets/agent-tools.json.
STUB_FILES = [p for tool in registry.canonicalizable_tools() for p in tool["stub_paths"]]

# Package-manager subcommands that are always valid; the prose heuristics; and the
# shared code-span tokenizer are single-sourced in facts.py so this drift gate and
# the Phase-0 semantic engine parse commands identically (TD-02).
PACKAGE_MANAGER_BUILTINS = facts.PACKAGE_MANAGER_BUILTINS
_PROSE_WORDS = facts._PROSE_WORDS
_PROSE_TARGET_WORDS = facts._PROSE_TARGET_WORDS
_looks_like_prose = facts.looks_like_prose
line_collected_code = facts.iter_code_tokens

# package.json scripts and Makefile targets are read via the shared facts layer
# so this gate and the Phase-0 engine read them identically (TD-02).
package_scripts = facts.package_scripts
make_targets = facts.make_targets

# Positive evidence that a file IS a managed pointer stub written by
# canonicalize.py: either the Claude `@AGENTS.md` import directive, or the
# canonical "instructions live in AGENTS.md" redirect phrase shared by the
# cursor/windsurf/cline/continue/copilot/gemini stubs. Matching a bare
# "AGENTS.md" mention (the old D3 heuristic) over-fires on full hand-authored
# configs that merely *link* to nested `dir/AGENTS.md` files or name the file in
# prose — e.g. pydantic-ai's CLAUDE.md, a complete duplicate of AGENTS.md that
# indexes ten nested `*/AGENTS.md` docs, was wrongly flagged as a regrown stub.
_STUB_POINTER_SIGNAL_RE = re.compile(
    r"(?m)^\s*@AGENTS\.md\b|instructions live in\s+`?AGENTS\.md`?",
    re.IGNORECASE,
)


def d1_command_drift(root, text):
    findings = []
    scripts = package_scripts(root)
    targets = make_targets(root)
    # Keep the package-manager alternation in lock-step with semantic.py's
    # _NODE_CMD_RE (npm|pnpm|bun); omitting bun left this CI gate blind to
    # `bun run <script>` references that the Phase-0 engine already audits.
    cmd_re = re.compile(
        r"\b(?:(npm|pnpm|bun)\s+(?:run\s+)?([A-Za-z0-9:_-]+)|yarn\s+([A-Za-z0-9:_-]+)|make\s+([A-Za-z0-9_.-]+))\b"
    )
    for lineno, code in line_collected_code(text):
        # Skip English prose sentences so imperatives like "make sure the tests
        # pass" are not parsed into phantom command targets (CORR-02).
        if _looks_like_prose(code):
            continue
        for m in cmd_re.finditer(code):
            tool = m.group(1) or ("yarn" if m.group(3) else "make")
            name = m.group(2) or m.group(3) or m.group(4)
            # A make "target" that is a bare English word ("make sure",
            # "make the ...") is prose, not a Makefile target (CORR-02).
            if tool == "make" and name in _PROSE_TARGET_WORDS:
                continue
            if tool == "make" and targets is not None and name not in targets:
                findings.append(
                    {
                        "check": "D1",
                        "level": "ERROR",
                        "line": lineno,
                        "message": f"Unknown Makefile target `{name}`",
                        "suggestion": "Update AGENTS.md or add the Makefile target.",
                    }
                )
            # Treat package-manager builtins as valid unconditionally; false negatives
            # are cheaper than noisy false positives here.
            if tool != "make" and name in PACKAGE_MANAGER_BUILTINS:
                continue
            # Same for yarn's node_modules/.bin passthrough (`yarn vitest`) — see
            # facts.is_yarn_bin_passthrough (TD-02).
            if tool != "make" and facts.is_yarn_bin_passthrough(root, tool, name):
                continue
            if tool != "make" and scripts is not None and name not in scripts:
                findings.append(
                    {
                        "check": "D1",
                        "level": "ERROR",
                        "line": lineno,
                        "message": f"Unknown package.json script `{name}`",
                        "suggestion": "Update AGENTS.md or add the package.json script.",
                    }
                )
    return findings


# Path-containment info-leak guard (rejects absolute / `../`-escaping tokens
# before probing them on disk). Single-sourced in facts.py so this gate and the
# Phase-0 engine apply the same containment rule (TD-02).
_within_root = facts.within_root


def d2_path_drift(root, text):
    findings = []
    # Use the shared registry.declared_paths classifier so this Phase-2 gate and
    # the Phase-0 semantic check agree on exactly what counts as a declared path
    # (TD-03). Candidacy is decided by the shared token rules; this gate then
    # applies its own containment (_within_root) and existence checks.
    #
    # Lazily computed only on a potential finding, mirroring
    # semantic.compare_paths so the common case (path exists) never pays for a
    # repo walk.
    package_names = "not computed"
    for decl in registry.declared_paths(text):
        token, lineno = decl["path"], decl["line"]
        # Never probe outside the repo root: an absolute or `../`-escaping token
        # is not repo drift and must not be stat()'d (info-leak guard).
        if not _within_root(root, token):
            continue
        if not (root / token).exists():
            # Monorepo package self-import guard — mirrors semantic.compare_paths
            # so both gates agree (TD-03). A token whose first segment matches a
            # package.json `name` (e.g. `better-auth/test`) is a package export
            # subpath, not a repo-relative filesystem path. Without this, `scan`
            # stays silent while `drift` ERRORs on the identical token.
            if package_names == "not computed":
                package_names = facts.all_package_names(root)
            if token.split("/", 1)[0] in package_names:
                continue
            findings.append(
                {
                    "check": "D2",
                    "level": "ERROR",
                    "line": lineno,
                    "message": f"Referenced path `{token}` does not exist",
                    "suggestion": "Fix or remove the backtick-quoted path.",
                }
            )
    return findings


def d3_stub_regrowth(root):
    findings = []
    if not (root / "AGENTS.md").is_file():
        return findings
    for rel in STUB_FILES:
        path = root / rel
        if not path.is_file():
            continue
        data = path.read_bytes()
        text = data.decode("utf-8", errors="replace")
        # Only flag a file as a regrown/broken canonical stub when there is
        # positive evidence it IS a managed pointer stub: it carries a canonical
        # pointer signal (`@AGENTS.md` import or the "instructions live in
        # AGENTS.md" redirect phrase) but has grown past the minimal-stub size
        # budget. A file that merely mentions or links to AGENTS.md (a full
        # hand-authored doc indexing nested `dir/AGENTS.md` files) is not a
        # broken stub, so D3 must not claim it "lost" a pointer it never had.
        if _STUB_POINTER_SIGNAL_RE.search(text) and len(data) > registry.STUB_POINTER_MAX_BYTES:
            findings.append(
                {
                    "check": "D3",
                    "level": "ERROR",
                    "path": rel,
                    "message": f"Tool stub `{rel}` regrew past the pointer-stub size budget",
                    "suggestion": "Run canonicalize.py --write-stubs after reviewing changes.",
                }
            )
    cursor_rules = root / ".cursor" / "rules"
    if cursor_rules.is_dir():
        for p in cursor_rules.glob("*"):
            if not p.is_file():
                continue
            data = p.read_bytes()
            text = data.decode("utf-8", errors="replace")
            # Same rule as above: only a genuine pointer rule (carries a
            # canonical `@AGENTS.md`/"instructions live in AGENTS.md" signal)
            # that regrew past the size budget is drift; a rule that merely
            # mentions or links to AGENTS.md is not a broken stub.
            if _STUB_POINTER_SIGNAL_RE.search(text) and len(data) > registry.STUB_POINTER_MAX_BYTES:
                findings.append(
                    {
                        "check": "D3",
                        "level": "ERROR",
                        "path": p.relative_to(root).as_posix(),
                        "message": "Cursor rule regrew past the pointer-stub size budget",
                        "suggestion": "Keep a single minimal pointer rule.",
                    }
                )
    return findings


def d4_size(root, max_bytes):
    path = root / "AGENTS.md"
    if not path.is_file():
        return [
            {
                "check": "D4",
                "level": "ERROR",
                "message": "AGENTS.md is missing",
                "suggestion": "Create canonical AGENTS.md first.",
            }
        ]
    size = len(path.read_bytes())
    if size > max_bytes:
        return [
            {
                "check": "D4",
                "level": "ERROR",
                "message": f"AGENTS.md is {size} bytes, above {max_bytes}",
                "suggestion": "Move details to references/ and keep AGENTS.md concise.",
            }
        ]
    if size > 12 * 1024:
        return [
            {
                "check": "D4",
                "level": "NOTICE",
                "message": f"AGENTS.md is {size} bytes; context bloat risk",
                "suggestion": "Consider progressive disclosure.",
            }
        ]
    return []


# Lockfile -> package-manager map, from the shared registry single source of
# truth so the drift gate (D6/D8) tracks the SAME managers as semantic.py and
# canonicalize.py — including bun (bun.lockb / bun.lock), which this map
# previously omitted, leaving the gate blind to bun repos (TD-01).
LOCKFILE_MANAGERS = registry.LOCKFILE_MANAGERS


# ``(major, line)`` for a Node.js version declared in AGENTS.md; the .nvmrc /
# engines.node ground-truth readers; the package managers a doc declares; and the
# committed-lockfile manager set are all single-sourced in facts.py so this D6
# drift gate and the Phase-0 semantic check read every fact one way (TD-02/TD-06).
declared_node_version = facts.declared_node_version
nvmrc_node_version = facts.nvmrc_node_version
engines_node_version = facts.engines_node_version
declared_package_managers = facts.declared_package_managers
lockfile_managers = facts.lockfile_managers


def d6_fact_drift(root, text):
    """Cross-validate factual claims in AGENTS.md against repo ground-truth files."""
    findings = []
    if not text:
        return findings

    # Node version: declared claim vs .nvmrc and package.json engines.node.
    declared_node, node_line = declared_node_version(text)
    if declared_node is not None:
        nvmrc = nvmrc_node_version(root)
        if nvmrc is not None and nvmrc != declared_node:
            findings.append(
                {
                    "check": "D6",
                    "level": "ERROR",
                    "line": node_line,
                    "message": f"AGENTS.md claims Node {declared_node} but `.nvmrc` pins Node {nvmrc}",
                    "suggestion": "Align AGENTS.md with `.nvmrc` or update `.nvmrc`.",
                }
            )
        engines = engines_node_version(root)
        if engines is not None and engines != declared_node:
            findings.append(
                {
                    "check": "D6",
                    "level": "ERROR",
                    "line": node_line,
                    "message": f"AGENTS.md claims Node {declared_node} but "
                    f"`package.json` engines.node requires Node {engines}",
                    "suggestion": "Align AGENTS.md with `package.json` engines.node or update engines.node.",
                }
            )

    # Package manager: declared claim vs the lockfile that actually exists.
    declared_pms = declared_package_managers(text)
    ground_pms = lockfile_managers(root)
    if len(declared_pms) == 1 and len(ground_pms) == 1:
        declared_pm = next(iter(declared_pms))
        ground_pm = next(iter(ground_pms))
        if declared_pm != ground_pm:
            lockfile = next(
                name for name, mgr in LOCKFILE_MANAGERS.items() if mgr == ground_pm and (root / name).is_file()
            )
            findings.append(
                {
                    "check": "D6",
                    "level": "ERROR",
                    "message": f"AGENTS.md uses `{declared_pm}` but the repo has `{lockfile}` implying `{ground_pm}`",
                    "suggestion": f"Align AGENTS.md with `{ground_pm}` or "
                    f"replace the lockfile to match `{declared_pm}`.",
                }
            )
    return findings


# Markdown inline links: [label](target) and [label](target "title"). We only
# probe the target, and only when it is a repo-relative filesystem path (never a
# URL, anchor, template placeholder, or path outside the repo — see _within_root).
_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(\s*([^)]+?)\s*\)")


def _link_target_is_probeable(target):
    """Return the repo-relative path to probe, or None if the target must be skipped."""
    if not target:
        return None
    # Strip a bracketed <...> target and any optional "title" suffix.
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    else:
        target = target.split(" ", 1)[0].strip()
    if not target or target.startswith("#"):
        return None
    if target.startswith(("http://", "https://", "mailto:", "tel:")) or "://" in target:
        return None
    if "<" in target or "{" in target or "*" in target or "?" in target:
        return None
    if target.startswith(("~", "/", "$")) or ":" in target:
        # Home-relative, absolute, env-var or scheme/drive-like targets are not
        # repo-relative paths; skip them exactly like d2_path_drift does.
        return None
    # Drop any in-page fragment so `references/foo.md#section` probes the file.
    target = target.split("#", 1)[0].strip()
    return target or None


def d7_markdown_link_drift(root, text):
    """Broken relative Markdown-link targets in AGENTS.md.

    D2 only probes backtick-quoted tokens; a canonical section that links to a
    config file or reference doc via Markdown link syntax (`[text](path)`) is not
    covered by D2. This flags link targets that resolve inside the repo but point
    at a file/dir that no longer exists — a documented path that drifted away.
    """
    findings = []
    if not text:
        return findings
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in _MD_LINK_RE.finditer(line):
            target = _link_target_is_probeable(m.group(1))
            if target is None:
                continue
            # Markdown may percent-encode spaces/specials in link targets
            # (`docs/my%20file.md`); decode before probing so a valid file is
            # not falsely reported as a broken link and failing CI.
            target = unquote(target)
            if not _within_root(root, target):
                continue
            if not (root / target).exists():
                findings.append(
                    {
                        "check": "D7",
                        "level": "ERROR",
                        "line": lineno,
                        "message": f"Markdown link target `{target}` does not exist",
                        "suggestion": "Fix or remove the Markdown link to the missing path.",
                    }
                )
    return findings


def d8_competing_lockfiles(root):
    """Competing package-manager lockfiles committed to the same repo.

    If lockfiles for more than one package manager are present (e.g. both
    `package-lock.json` and `pnpm-lock.yaml`), the intended package manager is
    ambiguous and downstream tooling (and AGENTS.md fact checks) cannot pick a
    ground truth. This is not mechanically auto-fixable — a human must decide
    which manager wins — so it is reported for manual attention.
    """
    present = [(name, mgr) for name, mgr in LOCKFILE_MANAGERS.items() if (root / name).is_file()]
    managers = sorted({mgr for _, mgr in present})
    if len(managers) <= 1:
        return []
    names = ", ".join(f"`{name}`" for name, _ in sorted(present))
    return [
        {
            "check": "D8",
            "level": "ERROR",
            "message": f"Competing package-manager lockfiles committed ({names}); intended manager is ambiguous",
            "suggestion": "Keep exactly one lockfile for the chosen package manager and delete the rest.",
        }
    ]


def nested_agents(root):
    out = []
    # Walk with os.walk so we can prune vendored dirs in place and avoid
    # following directory symlinks (which can loop). Reuse scan.SKIP_DIRS so
    # scan.py and check_drift.py never maintain divergent skip sets.
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in scan.SKIP_DIRS]
        if "AGENTS.md" not in filenames:
            continue
        p = Path(dirpath) / "AGENTS.md"
        if p == root / "AGENTS.md":
            continue
        out.append(p.relative_to(root).as_posix())
    return sorted(out)


SCORE_WEIGHTS = {"ERROR": 15, "NOTICE": 5}


def health_score(findings):
    """Aggregate findings into a 0-100 score and a letter grade."""
    score = 100
    for f in findings:
        score -= SCORE_WEIGHTS.get(f.get("level"), 0)
    score = max(0, score)
    if score >= 90:
        grade = "A"
    elif score >= 80:
        grade = "B"
    elif score >= 70:
        grade = "C"
    elif score >= 60:
        grade = "D"
    else:
        grade = "F"
    return score, grade


def run_checks(root, max_bytes, strict=False, rules_dirs=None, allow_plugins=False):
    agents = root / "AGENTS.md"
    text = agents.read_text(encoding="utf-8", errors="replace") if agents.is_file() else ""
    findings = []
    findings.extend(d1_command_drift(root, text))
    findings.extend(d2_path_drift(root, text))
    findings.extend(d3_stub_regrowth(root))
    findings.extend(d4_size(root, max_bytes))
    findings.extend(d6_fact_drift(root, text))
    findings.extend(d7_markdown_link_drift(root, text))
    findings.extend(d8_competing_lockfiles(root))
    if strict:
        for f in findings:
            if f.get("level") == "NOTICE":
                f["level"] = "ERROR"
    info = [
        {"check": "D5", "level": "INFO", "path": p, "message": "Nested AGENTS.md inventory"}
        for p in nested_agents(root)
    ]
    # User-extensible deterministic rule plugins (opt-in, default OFF). Plugin
    # files live inside the scanned repo, so importing them runs arbitrary code
    # on the host/CI; discovery + execution therefore happens ONLY when the
    # caller opts in via --allow-plugins. Otherwise this is a no-op returning an
    # empty list. Discovered from <root>/.ai-harness-doctor/rules/*.py plus any
    # --rules DIR; each plugin is isolated so a broken one is reported as an
    # ERROR finding, never a crash. Custom findings are reported additively
    # under `custom`; they do not alter the built-in D1-D8 health score.
    custom = plugins.run_plugins(
        root, {"phase": "drift", "agents_text": text}, rules_dirs, allow_plugins=allow_plugins
    )
    if strict:
        for f in custom:
            if f.get("level") == "NOTICE":
                f["level"] = "ERROR"
    failures = [f for f in findings if f.get("level") == "ERROR"]
    score, grade = health_score(findings)
    return {"ok": not failures, "findings": findings, "info": info, "custom": custom, "score": score, "grade": grade}


def render(report):
    lines = ["# Phase 2 — Follow-up Drift Guard Report", ""]
    if report["ok"]:
        lines.append("No blocking drift found.")
    for check in ["D1", "D2", "D3", "D4", "D6", "D7", "D8"]:
        items = [f for f in report["findings"] if f["check"] == check]
        if not items:
            continue
        lines.extend(["", f"## {check}"])
        for f in items:
            loc = f":{f['line']}" if "line" in f else f" `{f.get('path')}`" if "path" in f else ""
            lines.append(f"- **{f['level']}**{loc} {f['message']} Repair advice: {f['suggestion']}")
    lines.extend(["", "## D5 Nested AGENTS.md (informational, non-blocking)"])
    if report["info"]:
        lines.extend(f"- `{i['path']}`" for i in report["info"])
    else:
        lines.append("None.")
    custom = report.get("custom", [])
    lines.extend(["", "## Custom rule plugins"])
    if custom:
        for f in custom:
            loc = f":{f['line']}" if "line" in f else (f" `{f['path']}`" if "path" in f else "")
            suggestion = f" Repair advice: {f['suggestion']}" if f.get("suggestion") else ""
            lines.append(
                f"- **{f['level']}** [{f.get('plugin', '?')}:{f.get('rule', 'custom')}]{loc} {f['message']}{suggestion}"
            )
    else:
        lines.append("None.")
    lines.extend(["", "## Health score", f"Score: {report['score']}/100 (grade {report['grade']})"])
    return "\n".join(lines) + "\n"


def canonical_stub_content(root, rel_path):
    """Return the minimal canonical stub content for a regrown stub path.

    Reuses canonicalize.STUBS (path -> content) and the Cursor rule template so
    the auto-fix rewrites drift back to exactly what canonicalize.py would write.
    Returns None if the path is not a known auto-fixable tool stub.
    """
    for spec in canonicalize.STUBS.values():
        if rel_path in spec["paths"]:
            return spec["content"]
    posix = Path(rel_path).as_posix()
    if posix.startswith(".cursor/rules/"):
        return canonicalize.CURSOR_RULE_STUB
    return None


def _finding_loc(f):
    if "line" in f:
        return f":{f['line']}"
    if "path" in f:
        return f" `{f.get('path')}`"
    return ""


def run_fix(root, max_bytes, apply, strict=False, rules_dirs=None, allow_plugins=False):
    """Auto-repair ONLY the safe, mechanical subset of drift (D3 stub regrowth).

    Dry run by default (writes nothing); with apply=True actually rewrites the
    regrown tool stubs back to their minimal canonical import-stub form. Any drift
    that is not safely auto-fixable is reported as "needs manual attention" and its
    files are left untouched.
    """
    report = run_checks(root, max_bytes, strict, rules_dirs, allow_plugins=allow_plugins)
    d3 = [f for f in report["findings"] if f["check"] == "D3"]
    manual = [f for f in report["findings"] if f["check"] != "D3" and f.get("level") in ("ERROR", "NOTICE")]

    lines = ["# check_drift --fix (%s)" % ("apply" if apply else "dry run"), ""]
    fixed = 0
    skipped = []

    lines.append("## Auto-fixable: D3 stub regrowth")
    if not d3:
        lines.append("- None.")
    for f in d3:
        rel_path = f["path"]
        path = root / rel_path
        new = canonical_stub_content(root, rel_path)
        if new is None:
            skipped.append(f)
            continue
        old = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        if old == new:
            continue
        fixed += 1
        if apply:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(new, encoding="utf-8")
            lines.append(f"- rewrote `{rel_path}` back to minimal canonical stub")
        else:
            lines.append(f"- would rewrite `{rel_path}` back to minimal canonical stub:")
            lines.append("")
            lines.append("```diff")
            lines.append(canonicalize.unified_diff(Path(rel_path), old, new).rstrip("\n"))
            lines.append("```")

    # Stubs flagged as D3 but with no known canonical form fall back to manual.
    manual = manual + skipped

    lines.extend(["", "## Needs manual attention (not safely auto-fixable)"])
    if manual:
        for f in manual:
            loc = _finding_loc(f)
            lines.append(
                f"- needs manual attention: **{f['check']}**{loc} {f['message']} — {f.get('suggestion', '')}".rstrip(
                    " —"
                )
            )
    else:
        lines.append("- None.")

    action = "fixed" if apply else "fixable"
    lines.extend(["", f"Summary: {fixed} {action}, {len(manual)} need manual attention."])
    text = "\n".join(lines) + "\n"

    # Exit non-zero while drift remains. After --apply the D3 items are resolved,
    # so only manual items keep it failing; in dry run the pending fixes also count.
    remaining = len(manual) + (0 if apply else fixed)
    return text, 0 if remaining == 0 else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check AGENTS.md drift.")
    parser.add_argument("repo_root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--fix", action="store_true", help="Auto-repair the safe subset (D3 stub regrowth); dry run unless --apply."
    )
    parser.add_argument("--apply", action="store_true", help="With --fix, actually rewrite files instead of a dry run.")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
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
        "--min-score", type=int, default=None, help="Exit non-zero if the health score is below N (CI gating)."
    )
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    if not root.is_dir():
        message = f"error: not a directory: {args.repo_root}"
        if args.as_json:
            print(json.dumps({"error": message}, ensure_ascii=False, indent=2))
        else:
            print(message, file=sys.stderr)
        return 1
    # Executing plugins runs untrusted code from the scanned repo; warn loudly.
    if args.allow_plugins:
        print(
            "WARNING: --allow-plugins enabled: executing untrusted rule plugin code from the "
            "scanned repository (<repo>/.ai-harness-doctor/rules/ and any --rules DIR).",
            file=sys.stderr,
        )
    if args.fix:
        text, code = run_fix(
            root, args.max_bytes, args.apply, args.strict, args.rules, allow_plugins=args.allow_plugins
        )
        print(text, end="")
        return code
    report = run_checks(root, args.max_bytes, args.strict, args.rules, allow_plugins=args.allow_plugins)
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render(report), end="")
    exit_code = 0 if report["ok"] else 1
    if args.min_score is not None and report["score"] < args.min_score:
        exit_code = exit_code or 2
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
