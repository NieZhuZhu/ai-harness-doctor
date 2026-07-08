#!/usr/bin/env python3
"""Read-only drift guard for canonical AGENTS.md files."""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# canonicalize.py lives in the same scripts/ dir; reuse its canonical stub
# content/logic instead of duplicating it here.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import canonicalize  # noqa: E402
import registry  # noqa: E402


DEFAULT_MAX_BYTES = 32768
# Flat list of every canonical stub path, derived (in registry order) from the
# shared agent-config registry so the drift guard tracks exactly the same stubs
# canonicalize.py writes. See assets/agent-tools.json.
STUB_FILES = [p for tool in registry.canonicalizable_tools() for p in tool["stub_paths"]]
PACKAGE_MANAGER_BUILTINS = {
    "install", "ci", "i", "init", "add", "remove", "rm", "uninstall", "update", "up", "upgrade",
    "exec", "dlx", "create", "audit", "link", "unlink", "publish", "outdated", "config", "cache",
    "login", "logout", "whoami", "version", "info", "list", "ls", "why", "dedupe", "prune",
    "rebuild", "help", "test", "start",
}


def line_collected_code(text):
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            yield lineno, line
        for m in re.finditer(r"`([^`]+)`", line):
            yield lineno, m.group(1)


def package_scripts(root):
    path = root / "package.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set((data.get("scripts") or {}).keys())
    except Exception:
        return set()


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


def d1_command_drift(root, text):
    findings = []
    scripts = package_scripts(root)
    targets = make_targets(root)
    cmd_re = re.compile(r"\b(?:(npm|pnpm)\s+(?:run\s+)?([A-Za-z0-9:_-]+)|yarn\s+([A-Za-z0-9:_-]+)|make\s+([A-Za-z0-9_.-]+))\b")
    for lineno, code in line_collected_code(text):
        for m in cmd_re.finditer(code):
            tool = m.group(1) or ("yarn" if m.group(3) else "make")
            name = m.group(2) or m.group(3) or m.group(4)
            if tool == "make" and targets is not None and name not in targets:
                findings.append({"check": "D1", "level": "ERROR", "line": lineno, "message": f"Unknown Makefile target `{name}`", "suggestion": "Update AGENTS.md or add the Makefile target."})
            # Treat package-manager builtins as valid unconditionally; false negatives are cheaper than noisy false positives here.
            if tool != "make" and name in PACKAGE_MANAGER_BUILTINS:
                continue
            if tool != "make" and scripts is not None and name not in scripts:
                findings.append({"check": "D1", "level": "ERROR", "line": lineno, "message": f"Unknown package.json script `{name}`", "suggestion": "Update AGENTS.md or add the package.json script."})
    return findings


def _within_root(root, token):
    """Return True only if `token` resolves to a path contained in `root`.

    The drift gate reads backtick tokens from an untrusted AGENTS.md and probes
    them on disk. `pathlib` happily lets an absolute (`/etc/hostname`) or
    `../`-escaping token point outside the repo, which would let a malicious
    AGENTS.md infer the existence of arbitrary filesystem paths. Reject anything
    that does not stay under the repo root before calling `.exists()`.
    """
    try:
        candidate = (root / token).resolve()
        candidate.relative_to(root.resolve())  # raises ValueError if outside root
        return True
    except (ValueError, OSError):
        return False


def d2_path_drift(root, text):
    findings = []
    known = {"package.json", "Makefile", "AGENTS.md", "README.md"}
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in re.finditer(r"`([^`]+)`", line):
            token = m.group(1).strip()
            if token.startswith(("http://", "https://")) or "<" in token or "{" in token:
                continue
            if token.startswith(("npm ", "pnpm ", "yarn ", "make ", "python", "git ")):
                continue
            if "*" in token or "?" in token:
                continue
            if "/" not in token and token not in known:
                continue
            if any(ch.isspace() for ch in token):
                continue
            # Never probe outside the repo root: an absolute or `../`-escaping
            # token is not repo drift and must not be stat()'d (info-leak guard).
            if not _within_root(root, token):
                continue
            if not (root / token).exists():
                findings.append({"check": "D2", "level": "ERROR", "line": lineno, "message": f"Referenced path `{token}` does not exist", "suggestion": "Fix or remove the backtick-quoted path."})
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
        if len(data) > 600 or "AGENTS.md" not in text:
            findings.append({"check": "D3", "level": "ERROR", "path": rel, "message": f"Tool stub `{rel}` regrew or lost AGENTS.md pointer", "suggestion": "Run canonicalize.py --write-stubs after reviewing changes."})
    cursor_rules = root / ".cursor" / "rules"
    if cursor_rules.is_dir():
        for p in cursor_rules.glob("*"):
            if not p.is_file():
                continue
            data = p.read_bytes()
            text = data.decode("utf-8", errors="replace")
            if len(data) > 600 or "AGENTS.md" not in text:
                findings.append({"check": "D3", "level": "ERROR", "path": p.relative_to(root).as_posix(), "message": "Cursor rule regrew or lost AGENTS.md pointer", "suggestion": "Keep a single minimal pointer rule."})
    return findings


def d4_size(root, max_bytes):
    path = root / "AGENTS.md"
    if not path.is_file():
        return [{"check": "D4", "level": "ERROR", "message": "AGENTS.md is missing", "suggestion": "Create canonical AGENTS.md first."}]
    size = len(path.read_bytes())
    if size > max_bytes:
        return [{"check": "D4", "level": "ERROR", "message": f"AGENTS.md is {size} bytes, above {max_bytes}", "suggestion": "Move details to references/ and keep AGENTS.md concise."}]
    if size > 12 * 1024:
        return [{"check": "D4", "level": "NOTICE", "message": f"AGENTS.md is {size} bytes; context bloat risk", "suggestion": "Consider progressive disclosure."}]
    return []


LOCKFILE_MANAGERS = {
    "package-lock.json": "npm",
    "npm-shrinkwrap.json": "npm",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
}


def declared_node_version(text):
    """Return (major_version, lineno) for a node version declared in AGENTS.md, else (None, None)."""
    for lineno, line in enumerate(text.splitlines(), 1):
        m = re.search(r"\bnode(?:\.js)?\s*(?:version)?\s*(?:>=?|<=?|==?|\^|~)?\s*v?(\d+)(?:\.\d+|\.x)*", line, re.I)
        if m:
            return int(m.group(1)), lineno
    return None, None


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


def declared_package_managers(text):
    pms = set()
    for _lineno, code in line_collected_code(text):
        for m in re.finditer(r"\b(npm|pnpm|yarn)\b", code):
            pms.add(m.group(1))
    return pms


def lockfile_managers(root):
    return {mgr for name, mgr in LOCKFILE_MANAGERS.items() if (root / name).is_file()}


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
            findings.append({
                "check": "D6", "level": "ERROR", "line": node_line,
                "message": f"AGENTS.md claims Node {declared_node} but `.nvmrc` pins Node {nvmrc}",
                "suggestion": "Align AGENTS.md with `.nvmrc` or update `.nvmrc`.",
            })
        engines = engines_node_version(root)
        if engines is not None and engines != declared_node:
            findings.append({
                "check": "D6", "level": "ERROR", "line": node_line,
                "message": f"AGENTS.md claims Node {declared_node} but `package.json` engines.node requires Node {engines}",
                "suggestion": "Align AGENTS.md with `package.json` engines.node or update engines.node.",
            })

    # Package manager: declared claim vs the lockfile that actually exists.
    declared_pms = declared_package_managers(text)
    ground_pms = lockfile_managers(root)
    if len(declared_pms) == 1 and len(ground_pms) == 1:
        declared_pm = next(iter(declared_pms))
        ground_pm = next(iter(ground_pms))
        if declared_pm != ground_pm:
            lockfile = next(name for name, mgr in LOCKFILE_MANAGERS.items() if mgr == ground_pm and (root / name).is_file())
            findings.append({
                "check": "D6", "level": "ERROR",
                "message": f"AGENTS.md uses `{declared_pm}` but the repo has `{lockfile}` implying `{ground_pm}`",
                "suggestion": f"Align AGENTS.md with `{ground_pm}` or replace the lockfile to match `{declared_pm}`.",
            })
    return findings


def nested_agents(root):
    out = []
    for p in root.rglob("AGENTS.md"):
        if ".git" in p.parts or p == root / "AGENTS.md":
            continue
        out.append(p.relative_to(root).as_posix())
    return out


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


def run_checks(root, max_bytes, strict=False):
    agents = root / "AGENTS.md"
    text = agents.read_text(encoding="utf-8", errors="replace") if agents.is_file() else ""
    findings = []
    findings.extend(d1_command_drift(root, text))
    findings.extend(d2_path_drift(root, text))
    findings.extend(d3_stub_regrowth(root))
    findings.extend(d4_size(root, max_bytes))
    findings.extend(d6_fact_drift(root, text))
    if strict:
        for f in findings:
            if f.get("level") == "NOTICE":
                f["level"] = "ERROR"
    info = [{"check": "D5", "level": "INFO", "path": p, "message": "Nested AGENTS.md inventory"} for p in nested_agents(root)]
    failures = [f for f in findings if f.get("level") == "ERROR"]
    score, grade = health_score(findings)
    return {"ok": not failures, "findings": findings, "info": info, "score": score, "grade": grade}


def render(report):
    lines = ["# Phase 2 — Follow-up Drift Guard Report", ""]
    if report["ok"]:
        lines.append("No blocking drift found.")
    for check in ["D1", "D2", "D3", "D4", "D6"]:
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


def run_fix(root, max_bytes, apply, strict=False):
    """Auto-repair ONLY the safe, mechanical subset of drift (D3 stub regrowth).

    Dry run by default (writes nothing); with apply=True actually rewrites the
    regrown tool stubs back to their minimal canonical import-stub form. Any drift
    that is not safely auto-fixable is reported as "needs manual attention" and its
    files are left untouched.
    """
    report = run_checks(root, max_bytes, strict)
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
            lines.append(f"- needs manual attention: **{f['check']}**{loc} {f['message']} — {f.get('suggestion', '')}".rstrip(" —"))
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
    parser.add_argument("--fix", action="store_true", help="Auto-repair the safe subset (D3 stub regrowth); dry run unless --apply.")
    parser.add_argument("--apply", action="store_true", help="With --fix, actually rewrite files instead of a dry run.")
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--min-score", type=int, default=None, help="Exit non-zero if the health score is below N (CI gating).")
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    if args.fix:
        text, code = run_fix(root, args.max_bytes, args.apply, args.strict)
        print(text, end="")
        return code
    report = run_checks(root, args.max_bytes, args.strict)
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
