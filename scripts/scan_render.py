#!/usr/bin/env python3
"""Markdown rendering for the scan report.

Split out of ``scan.py`` (ARCH-07) so the scanner module stays focused on
*producing* the report data while this module owns *presenting* it. These
functions are pure: they take the already-built report dict (plus a running
``lines`` list) and append markdown, with no filesystem or scan-internal
dependencies. ``scan.py`` re-exports these names, so ``scan.render_*`` remains a
stable import path.
"""


def render_markdown(report, report_path=None):
    lines = ["# Phase 0 — Checkup Report", ""]
    if "monorepo" in report:
        render_monorepo(lines, report["monorepo"], report.get("packages", []))
    if "baseline" in report:
        render_baseline(lines, report["baseline"], report.get("baselined", []))
    lines.append("## Configuration file inventory")
    if not report["files"]:
        lines.append("No known AI harness configuration files were found.")
    else:
        lines.append("| File | Tool | Bytes | Lines | SHA256 |")
        lines.append("|---|---:|---:|---:|---|")
        for f in report["files"]:
            lines.append(f"| `{f['path']}` | {f['tool']} | {f['bytes']} | {f['lines']} | `{f['sha256']}` |")
    lines.extend(["", "## Size warnings"])
    if report["warnings"]:
        for w in report["warnings"]:
            lines.append(f"- **{w['level']}** `{w['path']}`: {w['message']}")
    else:
        lines.append("No size warnings found.")
    lines.extend(["", "## Overlap candidates"])
    if report["overlaps"]:
        for o in report["overlaps"]:
            lines.append(f"- `{o['a']}` ↔ `{o['b']}`: shared lines are {o['percent']}% of the smaller file")
    else:
        lines.append("No overlap candidates above 30% were found.")
    lines.extend(["", "## Conflict candidates"])
    if report["conflicts"]:
        for c in report["conflicts"]:
            lines.append(f"- **{c['signal']}**")
            for value, entries in c["values"].items():
                evidence = "; ".join(f"{e['path']}:{e['line']} `{e['evidence']}`" for e in entries)
                lines.append(f"  - `{value}`: {evidence}")
    else:
        lines.append("No obvious conflict candidates were found.")
    lines.extend(["", "## Nested AGENTS.md", *(f"- `{p}`" for p in report["nested"])])
    if not report["nested"]:
        lines.append("None.")
    render_surface(lines, report.get("surface", {}))
    if "security" in report:
        render_security(lines, report["security"])
    if "project_snapshot" in report:
        render_snapshot(lines, report["project_snapshot"])
    if "semantic" in report:
        render_semantic(lines, report["semantic"])
    if "gaps" in report:
        render_gaps(lines, report["gaps"])
    if "custom" in report:
        render_custom(lines, report["custom"])
    if report_path:
        lines.extend(
            [
                "",
                "## Full JSON report",
                f"The complete machine-readable report was written to `{report_path}`. "
                "An agent can read this file to reason over the project snapshot, gaps, "
                "surface, and security findings, and to plan fixes.",
            ]
        )
    lines.extend(
        [
            "",
            "> Stop condition: confirm the migration scope (whole repository / "
            "subdirectory / selected files) before entering Phase 1 — Treat.",
        ]
    )
    return "\n".join(lines) + "\n"


def render_baseline(lines, baseline, findings):
    """Render transparent baseline debt without duplicating full finding prose."""
    lines.extend(["", "## Scan baseline"])
    count = baseline.get("suppressed", len(findings))
    path = baseline.get("path", "")
    lines.append(
        f"{count} pre-existing non-security finding(s) suppressed by baseline `{path}` "
        "(still available in the JSON `baselined` array; not counted by fail-on gates or SARIF)."
    )
    if findings:
        counts = {}
        for finding in findings:
            family = finding.get("family", "unknown")
            counts[family] = counts.get(family, 0) + 1
        summary = ", ".join(f"{family}={counts[family]}" for family in sorted(counts))
        lines.append(f"Suppressed debt by family: {summary}.")
    lines.append("HIGH security findings are never baseline-eligible.")
    lines.append("")


def render_monorepo(lines, monorepo, packages):
    lines.extend(["", "## Monorepo"])
    source = monorepo.get("source") or "unknown"
    lines.append(f"Detected {monorepo.get('package_count', 0)} package(s) via {source}.")
    agg = monorepo.get("aggregate", {})
    lines.append(
        "Aggregate across packages: "
        f"{agg.get('files', 0)} config file(s), "
        f"{agg.get('gaps', 0)} gap(s), "
        f"{agg.get('security_high', 0)} HIGH security finding(s), "
        f"{agg.get('overlaps', 0)} overlap(s), "
        f"{agg.get('conflicts', 0)} conflict(s), "
        f"{agg.get('packages_with_agents_md', 0)} package(s) with AGENTS.md."
    )
    if packages:
        lines.append("")
        lines.append("| Package | Name | AGENTS.md | Config files | Gaps | HIGH sec |")
        lines.append("|---|---|:---:|---:|---:|---:|")
        for pkg in packages:
            summary = pkg.get("summary", {})
            lines.append(
                f"| `{pkg['path']}` | {pkg.get('name') or '—'} | "
                f"{'yes' if pkg.get('has_agents_md') else 'no'} | "
                f"{summary.get('files', 0)} | {summary.get('gaps', 0)} | "
                f"{summary.get('security_high', 0)} |"
            )
    lines.append("")
    lines.append("> Per-package details are in the `packages` array of the JSON report (`--json`).")
    lines.append("")


def render_repos_file(summary, repos, report_path=None):
    """Render the ``--repos-file`` (multi-repo) cross-repo summary report.

    Separate top-level entry point from :func:`render_markdown`: a batch
    result has no ``files``/``warnings``/single-repo shape to render, only a
    per-repo summary table plus each repo's own report nested underneath.
    """
    lines = ["# Multi-repo Checkup Report", ""]
    agg = summary.get("aggregate", {})
    lines.append(
        f"Scanned {summary.get('repo_count', 0)} repo(s) "
        f"({summary.get('error_count', 0)} could not be scanned). "
        f"Aggregate: {agg.get('files', 0)} config file(s), "
        f"{agg.get('gaps', 0)} gap(s), "
        f"{agg.get('security_high', 0)} HIGH security finding(s), "
        f"{agg.get('overlaps', 0)} overlap(s), "
        f"{agg.get('conflicts', 0)} conflict(s), "
        f"{agg.get('repos_with_agents_md', 0)} repo(s) with AGENTS.md."
    )
    ok_repos = [r for r in repos if "error" not in r]
    if ok_repos:
        lines.append("")
        lines.append("| Repo | Name | AGENTS.md | Config files | Gaps | HIGH sec | Semantic mismatches |")
        lines.append("|---|---|:---:|---:|---:|---:|---:|")
        for r in ok_repos:
            s = r.get("summary", {})
            lines.append(
                f"| `{r['path']}` | {r.get('name') or '—'} | "
                f"{'yes' if r.get('has_agents_md') else 'no'} | "
                f"{s.get('files', 0)} | {s.get('gaps', 0)} | "
                f"{s.get('security_high', 0)} | {s.get('semantic_mismatches', 0)} |"
            )
    error_repos = [r for r in repos if "error" in r]
    if error_repos:
        lines.append("")
        lines.append("## Repos that could not be scanned")
        for r in error_repos:
            lines.append(f"- `{r['path']}`: {r['error']}")
    if report_path:
        lines.extend(
            [
                "",
                "## Full JSON report",
                f"The complete machine-readable report (every scanned repo's full findings) "
                f"was written to `{report_path}`. An agent can read this file to reason over "
                "every repo's snapshot, gaps, and security findings without re-scanning.",
            ]
        )
    lines.extend(
        [
            "",
            "> Per-repo details are in the `repos` array of the JSON report (`--json`).",
        ]
    )
    return "\n".join(lines) + "\n"


def render_surface(lines, surface):
    lines.extend(["", "## Extended surface"])
    mcp = surface.get("mcp_servers", [])
    lines.append(f"- MCP servers: {len(mcp)}")
    for s in mcp:
        where = s["url"] or s["command"] or "(unspecified)"
        lines.append(f"  - `{s['name']}` ({s['transport']}) → `{where}` — {s['config']}")
    for label, key in [("Subagents", "subagents"), ("Slash commands", "commands")]:
        items = surface.get(key, [])
        lines.append(f"- {label}: {len(items)}")
        for it in items:
            lines.append(f"  - `{it}`")
    hooks = surface.get("hooks", [])
    lines.append(f"- Hooks: {len(hooks)}")
    for h in hooks:
        lines.append(f"  - {h['event']}: `{h['command'][:80]}` — {h['config']}")
    perms = surface.get("permissions", [])
    lines.append(f"- Permission configs: {len(perms)}")
    for p in perms:
        summary = ", ".join(f"{k}={len(p[k])}" for k in ["allow", "deny", "ask"] if k in p)
        mode = f", defaultMode={p['defaultMode']}" if "defaultMode" in p else ""
        lines.append(f"  - {p['config']}: {summary or 'no allow/deny/ask lists'}{mode}")


def render_security(lines, findings):
    lines.extend(["", "## Security checkup"])
    if not findings:
        lines.append("No security issues detected.")
        return
    for s in findings:
        lines.append(f"- **{s['level']}** [{s['category']}] `{s['path']}`: {s['message']}")


def render_gaps(lines, gaps):
    lines.extend(["", "## Missing / Gap Analysis"])
    if not gaps:
        lines.append("No harness infrastructure gaps detected.")
        return
    lines.append("Checklist items this repository is missing (compared with a complete harness):")
    lines.append("")
    for g in gaps:
        lines.append(f"- **{g['level']}** {g['item']}: {g['message']}")
        lines.append(f"  - Suggestion: {g['suggestion']}")


def render_custom(lines, findings):
    lines.extend(["", "## Custom rule plugins"])
    if not findings:
        lines.append("No custom rule plugins loaded (see `.ai-harness-doctor/rules/` or `--rules DIR`).")
        return
    for f in findings:
        loc = f":{f['line']}" if "line" in f else (f" `{f['path']}`" if "path" in f else "")
        lines.append(f"- **{f['level']}** [{f.get('plugin', '?')}:{f.get('rule', 'custom')}]{loc} {f['message']}")
        if f.get("suggestion"):
            lines.append(f"  - Suggestion: {f['suggestion']}")


CATEGORY_LABELS = {
    "command": "Command",
    "path": "Path",
    "package_manager": "Package manager",
    "node_version": "Node version",
    "python_version": "Python version",
    "go_version": "Go version",
    "rust_version": "Rust version",
    "java_version": "Java version",
}


def render_semantic(lines, semantic_report):
    lines.extend(["", "## Semantic consistency (declaration vs code)"])
    findings = semantic_report.get("findings", [])
    checked = semantic_report.get("checked", 0)
    if not findings:
        if checked:
            lines.append(f"All {checked} AGENTS.md declaration(s) match repository facts.")
        else:
            lines.append("No verifiable AGENTS.md declarations were found to cross-check.")
        return
    lines.append(f"{len(findings)} of {checked} checked AGENTS.md declaration(s) do not match the code:")
    for f in findings:
        label = CATEGORY_LABELS.get(f["category"], f["category"])
        loc = f":{f['line']}" if "line" in f else ""
        lines.append(f"- **{f['level']}** [{label}]{loc} {f['message']}")
        lines.append(f"  - Suggestion: {f['suggestion']}")


def render_snapshot(lines, snapshot):
    lines.extend(["", "## Project snapshot"])
    stack = snapshot.get("tech_stack", [])
    if stack:
        lines.append("- Tech stack:")
        for s in stack:
            lines.append(f"  - {s['language']}: {', '.join(f'`{m}`' for m in s['markers'])}")
    else:
        lines.append("- Tech stack: none detected")
    existing = snapshot.get("existing_files", {})
    for group in ("ci", "hooks", "lint_format", "typecheck"):
        items = existing.get(group, [])
        if items:
            lines.append(f"- {group}: {', '.join(f'`{i}`' for i in items)}")
        else:
            lines.append(f"- {group}: none")
    lines.append(f"- Drift-guard pre-commit hook: {existing.get('drift_guard_hook') or 'none'}")
    sections = snapshot.get("agents_sections", [])
    lines.append(f"- AGENTS.md sections: {', '.join(sections) if sections else 'none'}")
    lines.append(f"- Maintenance contract: {'present' if snapshot.get('maintenance_contract') else 'absent'}")
    mcp_tools = snapshot.get("mcp_tools", [])
    lines.append(f"- MCP tools: {', '.join(f'`{t}`' for t in mcp_tools) if mcp_tools else 'none'}")
    lines.append(f"- Permission configuration: {'present' if snapshot.get('has_permissions') else 'absent'}")
