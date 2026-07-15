#!/usr/bin/env python3
"""Explain the canonical instruction chain for one repository-relative target."""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facts  # noqa: E402
import scan  # noqa: E402

SCHEMA_VERSION = 1
DIAGNOSTIC_LIMITATION = (
    "Tool-specific configs are diagnostically associated with lexical scopes; "
    "their own glob, frontmatter, and prose applicability is not inferred."
)


def normalize_target(root, target):
    """Return a contained lexical target path plus public target metadata."""
    root = Path(root).resolve()
    raw = Path(target)
    candidate = raw if raw.is_absolute() else root / raw
    # Preserve the lexical path for nearest-file scope semantics, but separately
    # resolve it to prove existing symlink components cannot escape the repo.
    lexical = Path(os.path.abspath(str(candidate)))
    try:
        rel = lexical.relative_to(root)
    except ValueError:
        raise ValueError("target path must stay inside the repository") from None
    resolved = facts.resolve_within_root(lexical, root, strict=False)
    if resolved is None:
        raise ValueError("target path must stay inside the repository")
    rel_path = rel.as_posix()
    if rel_path in ("", "."):
        rel_path = "."
    exists = lexical.exists()
    if resolved.is_file():
        kind = "file"
    elif resolved.is_dir():
        kind = "directory"
    else:
        kind = "missing"
    excluded = any(part in scan.SKIP_DIRS for part in rel.parts)
    return resolved, {
        "path": rel_path,
        "exists": exists,
        "kind": kind,
        "excluded_by_scan": excluded,
    }


def _scope_for_target(target_path, target_kind, scope_names):
    # A file's instructions are selected from its containing directory; a
    # directory/future path is itself the lexical query location.
    is_directory = target_kind in {"directory", "missing"} or target_path == "."
    return scan.effective_instruction_scope(
        target_path,
        scope_names,
        path_is_directory=is_directory,
    )


def _diagnostic_sources(files, file_scopes, chain):
    chain_set = set(chain)
    return sorted(
        (
            {
                "path": entry["path"],
                "tool": entry["tool"],
                "scope": file_scopes.get(entry["path"], "."),
            }
            for entry in files
            if file_scopes.get(entry["path"], ".") in chain_set
        ),
        key=lambda item: (chain.index(item["scope"]), item["path"], item["tool"]),
    )


def _safe_conflict(conflict):
    """Project conflict evidence down to public path/line/value records."""
    result = {
        "signal": conflict.get("signal", ""),
        "scope": conflict.get("scope") or ".",
        "values": {},
    }
    raw_values = conflict.get("values", {})
    if isinstance(raw_values, dict):
        for value in sorted(raw_values, key=str):
            entries = []
            for evidence in raw_values.get(value, []):
                if not isinstance(evidence, dict):
                    continue
                entry = {"path": evidence.get("path"), "line": evidence.get("line")}
                if evidence.get("value") is not None:
                    entry["value"] = evidence.get("value")
                entries.append(entry)
            result["values"][str(value)] = entries
    return result


def _safe_override(override):
    return {
        "signal": override.get("signal", ""),
        "parent_scope": override.get("parent_scope", "."),
        "scope": override.get("scope", "."),
        "parent_values": list(override.get("parent_values", [])),
        "values": list(override.get("values", [])),
        "evidence": [
            {
                "path": item.get("path"),
                "line": item.get("line"),
                "value": item.get("value"),
            }
            for item in override.get("evidence", [])
            if isinstance(item, dict)
        ],
    }


def build_explanation(repo_root, target, max_bytes=32768):
    """Build the deterministic schema-version-1 explain report."""
    root = Path(repo_root).resolve()
    if not root.is_dir():
        raise ValueError("repository root is not a directory")
    _resolved, target_info = normalize_target(root, target)
    ctx = scan.ScanContext(root)
    files, public_files, _warnings, _ctx = scan.collect_instruction_files(root, max_bytes, ctx)
    scope_rows, file_scopes, parent_by_scope = scan.instruction_scope_map(files)
    _rows, conflicts, overrides = scan.analyze_scoped_conflicts(files)
    scope_names = set(parent_by_scope)
    effective_scope = _scope_for_target(target_info["path"], target_info["kind"], scope_names)
    chain = scan.instruction_scope_chain(effective_scope, parent_by_scope)
    chain_set = set(chain)
    canonical_chain = [row for scope in chain for row in scope_rows if row["scope"] == scope]
    relevant_overrides = [
        _safe_override(item)
        for item in overrides
        if item.get("scope") in chain_set and item.get("parent_scope") in chain_set
    ]
    relevant_conflicts = [
        _safe_conflict(item)
        for item in conflicts
        if (item.get("scope") or ".") in chain_set
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "repo": ".",
        "target": target_info,
        "effective_scope": effective_scope,
        "canonical_chain": canonical_chain,
        "diagnostic_sources": _diagnostic_sources(public_files, file_scopes, chain),
        "scope_overrides": relevant_overrides,
        "conflicts": relevant_conflicts,
        "limitations": [DIAGNOSTIC_LIMITATION],
    }


def render_markdown(report):
    target = report["target"]
    lines = [
        "# Effective instruction explanation",
        "",
        f"- Target: `{target['path']}`",
        f"- Exists: {'yes' if target['exists'] else 'no'} ({target['kind']})",
        f"- Effective lexical scope: `{report['effective_scope']}`",
    ]
    if target["excluded_by_scan"]:
        lines.append(
            "- Scan boundary: target is inside an excluded directory; nested configs "
            "inside that subtree are not inventoried."
        )
    lines.extend(["", "## Canonical instruction chain"])
    if report["canonical_chain"]:
        for item in report["canonical_chain"]:
            parent = item["parent"] if item["parent"] is not None else "none"
            lines.append(f"- `{item['path']}` — scope `{item['scope']}`, parent `{parent}`")
    else:
        lines.append("- None. No canonical instruction file was discovered on this path.")
    lines.extend(["", "## Diagnostic sources"])
    if report["diagnostic_sources"]:
        for item in report["diagnostic_sources"]:
            lines.append(f"- `{item['path']}` — {item['tool']}, lexical scope `{item['scope']}`")
    else:
        lines.append("- None.")
    lines.extend(["", "## Relevant scope overrides"])
    if report["scope_overrides"]:
        for item in report["scope_overrides"]:
            lines.append(
                f"- `{item['signal']}`: `{item['parent_scope']}` "
                f"{item['parent_values']} → `{item['scope']}` {item['values']}"
            )
    else:
        lines.append("- None.")
    lines.extend(["", "## Relevant same-scope conflicts"])
    if report["conflicts"]:
        for item in report["conflicts"]:
            lines.append(
                f"- `{item['signal']}` in `{item['scope']}`: "
                + ", ".join(f"`{value}`" for value in item["values"])
            )
    else:
        lines.append("- None.")
    lines.extend(["", "## Limitations"])
    lines.extend(f"- {item}" for item in report["limitations"])
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Explain effective instructions for a repository path.")
    parser.add_argument("repo_root")
    parser.add_argument("target")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)
    try:
        report = build_explanation(args.repo_root, args.target)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
