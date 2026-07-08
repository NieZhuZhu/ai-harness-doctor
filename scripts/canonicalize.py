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
import scan  # noqa: E402
import registry  # noqa: E402


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

CURSOR_RULE_STUB = "---\nalwaysApply: true\n---\n\nCanonical agent instructions live in `AGENTS.md` (single source of truth). Do not duplicate rules here.\n"


def git_clean_or_forced(root, force):
    if force:
        return
    inside = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"], text=True, capture_output=True)
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        raise SystemExit("Refusing to write: target is not a git repo. Use --force to override.")
    status = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], text=True, capture_output=True)
    if status.returncode != 0 or status.stdout.strip():
        raise SystemExit("Refusing to write: git working tree is dirty. Commit/stash first or use --force.")


def unified_diff(path, old, new):
    return "".join(difflib.unified_diff(
        old.splitlines(True), new.splitlines(True),
        fromfile=f"a/{path.as_posix()}", tofile=f"b/{path.as_posix()}", lineterm=""
    ))


def render_plan(report):
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
            lines.append(f"- **{c['signal']}**")
            for value, entries in c["values"].items():
                lines.append(f"  - `{value}`")
                for e in entries:
                    lines.append(f"    - {e['path']}:{e['line']} `{e['evidence']}`")
    else:
        lines.append("- No obvious conflict candidates.")
    lines.extend([
        "", "## TODO decision checklist",
        "- [ ] Confirm the migration scope (whole repository / subdirectory / selected files).",
        "- [ ] Record the human adjudication for every conflict.",
        "- [ ] Manually write the root `AGENTS.md`, keeping only information agents cannot infer from code or manifests.",
        "- [ ] Run `canonicalize.py --write-stubs` to preview the downgrade diff.",
        "- [ ] Run `canonicalize.py --validate` to re-check the result.",
    ])
    lines.extend(render_merge_suggestions(report))
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


def _evidence_ref(entry):
    return f"{entry['path']}:{entry['line']}"


def render_merge_suggestions(report):
    """Concrete, actionable semi-automatic merge suggestions derived from scan results.

    Deterministic: overlaps and conflicts are already ordered by scan.py, and the
    recommended conflict value is chosen by a stable rule (see recommend_conflict_value).
    """
    lines = ["", "## Merge suggestions (semi-automatic)",
             "Canonical file: `AGENTS.md` (single source of truth)."]

    lines.append("")
    lines.append("### Overlap consolidation")
    if report["overlaps"]:
        for o in report["overlaps"]:
            lines.append(
                f"- [ ] `{o['a']}` \u2194 `{o['b']}` ({o['percent']}% shared): "
                f"keep the shared content in `AGENTS.md` and reduce these files to stubs:"
            )
            for path in (o["a"], o["b"]):
                lines.append(f"  - [ ] reduce `{path}` to an import stub pointing at `AGENTS.md`")
    else:
        lines.append("- No overlap clusters above the threshold; nothing to consolidate.")

    lines.append("")
    lines.append("### Conflict resolutions")
    if report["conflicts"]:
        for c in report["conflicts"]:
            values = c["values"]
            recommended = recommend_conflict_value(values)
            rec_entries = values[recommended]
            rec_evidence = ", ".join(f"`{_evidence_ref(e)}`" for e in rec_entries)
            others = []
            for value in sorted(values.keys()):
                if value == recommended:
                    continue
                ev = ", ".join(f"`{_evidence_ref(e)}`" for e in values[value])
                others.append(f"`{value}` ({ev})")
            other_text = "; ".join(others) if others else "none"
            lines.append(
                f"- [ ] **{c['signal']}** \u2192 recommend `{recommended}` "
                f"(evidence: {rec_evidence}); record it in `AGENTS.md` and drop conflicting "
                f"lines from the other files. Other candidates: {other_text}."
            )
    else:
        lines.append("- No conflict signals detected; no adjudication needed.")

    return lines


def write_plan(args):
    report = scan.scan_repo(args.repo_root, args.max_bytes)
    content = render_plan(report)
    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
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
            for p in sorted(rules_dir.iterdir()):
                if p.is_file() and p.name != "agents-md.mdc" and p.suffix in {".md", ".mdc"}:
                    changes.append({"action": "delete", "path": p})
    return changes


def write_stubs(args):
    root = Path(args.repo_root).resolve()
    if not (root / "AGENTS.md").is_file():
        raise SystemExit("AGENTS.md must exist before writing stubs.")
    tools = [t.strip() for t in args.tools.split(",") if t.strip()]
    changes = collect_stub_targets(root, tools)
    if args.apply:
        git_clean_or_forced(root, args.force)
    if not changes:
        print("No existing tool files matched; nothing to change.")
        return
    for change in changes:
        path = change["path"]
        rp = path.relative_to(root)
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


def validate(args):
    root = Path(args.repo_root).resolve()
    findings = []
    agents = root / "AGENTS.md"
    if not agents.is_file():
        findings.append({"level": "ERROR", "check": "AGENTS_EXISTS", "message": "AGENTS.md is missing"})
    else:
        data = agents.read_bytes()
        text = data.decode("utf-8", errors="replace")
        if len(data) > args.max_bytes:
            findings.append({"level": "ERROR", "check": "SIZE", "message": f"AGENTS.md is {len(data)} bytes, above {args.max_bytes}"})
        for req in args.require_sections.split(","):
            if req.strip() and not heading_present(text, req.strip()):
                findings.append({"level": "ERROR", "check": "SECTION", "message": f"Missing required heading: {req.strip()}"})
    if agents.is_file():
        for change in collect_stub_targets(root, ["claude", "cursor", "windsurf", "copilot", "gemini", "cline"]):
            path = change["path"]
            if not path.is_file():
                continue
            if change["action"] == "write":
                text = path.read_text(encoding="utf-8", errors="replace")
                if "AGENTS.md" in text and len(text.encode("utf-8")) <= 800:
                    continue
            # Existing full files are allowed before stub-writing; check_drift catches post-migration re-divergence.
            findings.append({"level": "NOTICE", "check": "STUB", "path": path.relative_to(root).as_posix(), "message": "tool file not yet downgraded to stub (or regrew)"})
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
    mode.add_argument("--write-stubs", action="store_true")
    mode.add_argument("--validate", action="store_true")
    parser.add_argument("repo_root", nargs="?", default=".")
    parser.add_argument("-o", "--output")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--tools", default="claude,cursor,windsurf,copilot,gemini,cline")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--max-bytes", type=int, default=32768)
    parser.add_argument("--require-sections", default="Project overview,Build & test,Conventions")
    args = parser.parse_args(argv)
    if args.plan:
        write_plan(args)
        return 0
    if args.write_stubs:
        write_stubs(args)
        return 0
    return validate(args)


if __name__ == "__main__":
    sys.exit(main())
