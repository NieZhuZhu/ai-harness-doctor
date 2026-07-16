#!/usr/bin/env python3
"""Turn drift/scan findings into GitHub PR review comments.

Reads a JSON findings report produced by ``check_drift.py --json`` and/or
``scan.py --json`` and assembles a GitHub pull-request review payload: findings
that carry BOTH a repo-relative ``path`` and a concrete ``line`` become inline
review comments (``{path, line, body}``); every other finding — including one
that has a ``path`` but no ``line`` — is collected into a single summary body.

The ``path``-without-``line`` case matters: GitHub's "create review" endpoint
rejects the ENTIRE review with HTTP 422 if any single inline comment lacks a
valid ``line``/``position``. Routing such findings to the summary body instead
guarantees one unlocatable finding can never nuke the whole review.

Two modes:

* ``--dry-run`` (DEFAULT): print the assembled review payload as pretty JSON to
  stdout. This never touches the network — no sockets are opened and the
  ``urllib`` posting helper is imported lazily only in ``--post`` mode.
* ``--post``: post the review to GitHub via the REST API using the Python
  standard library (``urllib.request``), reading ``GITHUB_TOKEN`` and
  ``GITHUB_REPOSITORY`` from the environment and ``--pr`` / ``--commit`` from
  args.

Python 3.9 standard library only; no third-party dependencies.
"""

import argparse
import json
import posixpath
import sys
from pathlib import PurePosixPath

# Identifying marker embedded in every summary/general comment body so re-runs
# can recognize and update their own prior ai-harness-doctor summary.
MARKER = "<!-- ai-harness-doctor:pr-review -->"

# GitHub pull-request review "event". COMMENT posts the review without
# approving or requesting changes, which is the safe default for an automated
# advisory gate.
REVIEW_EVENT = "COMMENT"

# Bound each GitHub API operation independently so a stalled connect/read
# cannot wedge the PR-feedback step forever. This is deliberately internal:
# workflow callers still decide whether a bounded posting failure is fatal.
GITHUB_API_TIMEOUT_SECONDS = 15

_ERROR_LEVELS = {"ERROR", "HIGH"}
_WARNING_LEVELS = {"NOTICE", "WARN", "WARNING", "MEDIUM", "MISMATCH"}
_INFO_LEVELS = {"INFO", "LOW"}

_RULE_TITLES = {
    "D1": "Command drift",
    "D2": "Path drift",
    "D3": "Tool-stub re-divergence",
    "D4": "Canonical instruction size",
    "D5": "Nested AGENTS.md inventory",
    "D6": "Repository fact drift",
    "D7": "Markdown-link drift",
    "D8": "Competing lockfiles",
    "secret": "Exposed secret",
    "permission": "Broad agent permission",
    "hook": "Risky lifecycle hook",
    "mcp": "Insecure MCP configuration",
    "instruction": "Risky agent instruction",
    "command": "Command consistency",
    "path": "Path consistency",
    "package_manager": "Package-manager consistency",
    "node_version": "Node.js version consistency",
    "conflict": "Conflicting agent declarations",
    "size": "Instruction size warning",
    "gap": "Harness completeness gap",
    "batch_scan": "Batch scan coverage failure",
    "applicability": "Structured rule applicability",
}

_IMPACT_BY_LABEL = {
    "D1": "AI coding agents may run commands that do not exist, wasting CI time or producing incomplete changes.",
    "D2": "AI coding agents may read, edit, or cite a path that no longer exists.",
    "D3": (
        "Tool-specific instructions may diverge from the canonical AGENTS.md "
        "and give different agents conflicting guidance."
    ),
    "D4": "Missing or oversized canonical instructions reduce the context available to AI coding agents.",
    "D6": (
        "Agents may choose the wrong runtime or package manager because "
        "documented facts disagree with repository facts."
    ),
    "D7": "Agents and contributors may follow a documentation link that no longer resolves.",
    "D8": "Competing lockfiles make the intended package manager ambiguous to agents and CI.",
    "secret": "Credentials or sensitive values in agent configuration can be exposed to tools, logs, or pull requests.",
    "permission": "Overly broad agent permissions can allow unintended commands or file access.",
    "hook": "Risky hook commands can execute automatically during an agent lifecycle.",
    "mcp": "An insecure MCP configuration can expose tool traffic or grant unsafe capabilities.",
    "instruction": "Unsafe repository instructions can steer AI agents toward destructive or unreviewed actions.",
    "command": "Agents may execute a command that no longer matches the repository.",
    "path": "Agents may operate on a stale or missing repository path.",
    "package_manager": "Agents may install dependencies or run scripts with the wrong package manager.",
    "node_version": "Agents and CI may use a Node.js version that conflicts with the repository.",
    "conflict": "Conflicting declarations can make different AI coding agents follow incompatible guidance.",
    "size": "Oversized agent instructions may be truncated or crowd useful repository context out of the prompt.",
    "gap": "Missing harness infrastructure can leave agents without canonical, enforceable repository guidance.",
    "batch_scan": "An organization-wide gate passed without checking every listed repository.",
    "applicability": "A structured rule may be ignored or applied in an unintended scope.",
}


def _join_report_path(prefix, value):
    """Prefix a report-local path with its monorepo package path."""
    if value in (None, ""):
        return None
    path = str(value).replace("\\", "/")
    if not prefix:
        return path
    if path.startswith("./"):
        path = path[2:]
    return posixpath.join(str(prefix).strip("/"), path)


def _safe_repo_label(entry):
    """Return a public batch-repo label without exposing ``resolved`` paths."""
    raw = _no_embedded_newlines(entry.get("path") or "repository")
    path = PurePosixPath(raw.replace("\\", "/"))
    raw_label = (path.name or "repository") if path.is_absolute() else raw
    name = _no_embedded_newlines(entry.get("name")) if entry.get("name") else None
    if name and raw_label and name != raw_label:
        return f"{name} ({raw_label})"
    return name or raw_label


def _safe_batch_finding_path(value):
    """Keep only non-escaping relative paths in public batch summaries."""
    if value in (None, ""):
        return None
    raw = str(value).replace("\\", "/")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts:
        return None
    return path.as_posix()


def _normalize_finding(finding, prefix="", package=None, repository=None, summary_only=False):
    normalized = dict(finding)
    if normalized.get("path"):
        if repository:
            safe_path = _safe_batch_finding_path(normalized["path"])
            if safe_path:
                normalized["path"] = safe_path
            else:
                normalized.pop("path", None)
        else:
            normalized["path"] = _join_report_path(prefix, normalized["path"])
    if package:
        normalized["_review_package"] = _no_embedded_newlines(package)
    if repository:
        normalized["_review_repository"] = _no_embedded_newlines(repository)
    if summary_only:
        normalized["_review_summary_only"] = True
    return normalized


def _conflict_evidence(raw_values, prefix="", repository=None):
    """Render deterministic, safe source locations for conflict values."""
    if not isinstance(raw_values, dict):
        return []
    evidence = []
    for value in sorted(raw_values, key=str):
        locations = []
        entries = raw_values.get(value)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict) or not entry.get("path"):
                continue
            path = (
                _safe_batch_finding_path(entry["path"])
                if repository
                else _join_report_path(prefix, entry["path"])
            )
            if not path:
                continue
            line = _coerce_line(entry.get("line"))
            locations.append(f"{path}:{line}" if line is not None else path)
        if locations:
            evidence.append(f"{value}: {', '.join(locations)}")
    return evidence


def _normalize_conflict(
    conflict,
    prefix="",
    package=None,
    repository=None,
    summary_only=False,
):
    signal = str(conflict.get("signal", ""))
    raw_values = conflict.get("values", {})
    if isinstance(raw_values, dict):
        values = sorted(str(value) for value in raw_values)
    elif isinstance(raw_values, (list, tuple, set)):
        values = sorted(str(value) for value in raw_values)
    else:
        values = [str(raw_values)] if raw_values not in (None, "") else []
    scope = str(conflict.get("scope", ""))
    scope_suffix = f" (scope: {scope})" if scope not in ("", ".") else ""
    finding = {
        "category": f"conflict/{signal}",
        "level": "WARN",
        "message": f"Conflicting {signal} declarations: " + ", ".join(values) + scope_suffix,
        "values": values,
        "suggestion": (
            "Choose one canonical declaration inside this diagnostic scope and "
            "keep tool-specific files compatible with its nearest AGENTS.md."
        ),
    }
    if scope not in ("", "."):
        finding["scope"] = scope
    evidence = _conflict_evidence(raw_values, prefix=prefix, repository=repository)
    if evidence:
        finding["evidence"] = evidence
    return _normalize_finding(
        finding,
        package=package,
        repository=repository,
        summary_only=summary_only,
    )


def _finding_fingerprint(finding, include_package=True):
    """Stable identity used to avoid duplicate findings in combined reports."""
    identity = {
        key: value
        for key, value in finding.items()
        if key != "_review_summary_only"
        and (include_package or key != "_review_package")
    }
    return json.dumps(identity, ensure_ascii=False, sort_keys=True, default=str)


def collect_findings(report):
    """Flatten the finding lists out of a check_drift and/or scan JSON report.

    Accepts either a single report dict, a list of finding dicts, or a list of
    report dicts, and gathers findings from all the shapes those two tools emit:

      - ``check_drift.py --json`` -> ``{"findings": [...], "custom": [...]}``
      - ``scan.py --json``        -> root findings plus ``packages`` / ``repos``
      - combined guard input      -> ``{"reports": [scan_report, drift_report]}``

    ``baselined`` scan debt is deliberately not traversed. Monorepo findings
    receive repository-relative package paths; independent batch-repo findings
    receive a public repo label and are forced to summary-only delivery.

    Returns a de-duplicated flat list of finding dicts, preserving first-seen
    input order.
    """
    findings = []

    def append(finding, prefix="", package=None, repository=None, summary_only=False):
        if not isinstance(finding, dict):
            return
        findings.append(
            _normalize_finding(
                finding,
                prefix=prefix,
                package=package,
                repository=repository,
                summary_only=summary_only,
            )
        )

    def walk(value, prefix="", package=None, repository=None, summary_only=False):
        if isinstance(value, list):
            for item in value:
                walk(
                    item,
                    prefix=prefix,
                    package=package,
                    repository=repository,
                    summary_only=summary_only,
                )
            return
        if not isinstance(value, dict):
            return

        container_keys = (
            "findings",
            "custom",
            "security",
            "warnings",
            "applicability_warnings",
            "gaps",
            "semantic",
            "conflicts",
            "packages",
            "repos",
            "reports",
        )
        if "message" in value and not any(key in value for key in container_keys):
            append(value, prefix, package, repository, summary_only)
            return

        for key in (
            "findings",
            "custom",
            "security",
            "warnings",
            "applicability_warnings",
        ):
            for finding in value.get(key, []) if isinstance(value.get(key), list) else []:
                normalized = dict(finding) if isinstance(finding, dict) else finding
                if key == "warnings" and isinstance(normalized, dict):
                    normalized.setdefault("category", "size")
                if key == "applicability_warnings" and isinstance(normalized, dict):
                    detail = normalized.get("category") or "metadata"
                    normalized["category"] = f"applicability/{detail}"
                append(normalized, prefix, package, repository, summary_only)

        for finding in value.get("gaps", []) if isinstance(value.get("gaps"), list) else []:
            normalized = dict(finding) if isinstance(finding, dict) else finding
            if isinstance(normalized, dict) and not normalized.get("path"):
                normalized["path"] = "AGENTS.md"
            append(normalized, prefix, package, repository, summary_only)

        semantic = value.get("semantic")
        if isinstance(semantic, dict):
            for finding in semantic.get("findings", []) if isinstance(semantic.get("findings"), list) else []:
                normalized = dict(finding) if isinstance(finding, dict) else finding
                if isinstance(normalized, dict) and not normalized.get("path"):
                    normalized["path"] = "AGENTS.md"
                append(normalized, prefix, package, repository, summary_only)

        for conflict in value.get("conflicts", []) if isinstance(value.get("conflicts"), list) else []:
            if isinstance(conflict, dict):
                findings.append(
                    _normalize_conflict(
                        conflict,
                        prefix=prefix,
                        package=package,
                        repository=repository,
                        summary_only=summary_only,
                    )
                )

        reports = value.get("reports")
        if isinstance(reports, list):
            for nested in reports:
                walk(
                    nested,
                    prefix=prefix,
                    package=package,
                    repository=repository,
                    summary_only=summary_only,
                )

        packages = value.get("packages")
        if isinstance(packages, list):
            for entry in packages:
                if not isinstance(entry, dict) or not isinstance(entry.get("report"), dict):
                    continue
                package_path = _join_report_path(prefix, entry.get("path") or "")
                walk(
                    entry["report"],
                    prefix=package_path or prefix,
                    package=package_path or package,
                    repository=repository,
                    summary_only=summary_only,
                )

        repos = value.get("repos")
        if isinstance(repos, list):
            for entry in repos:
                if not isinstance(entry, dict):
                    continue
                repository = _safe_repo_label(entry)
                if "error" in entry:
                    append(
                        {
                            "category": "batch_scan",
                            "level": "ERROR",
                            "message": "Listed repository was not scanned.",
                            "suggestion": (
                                "Fix the repository path, checkout, or permissions, "
                                "then rerun the complete multi-repo scan."
                            ),
                        },
                        repository=repository,
                        summary_only=True,
                    )
                    continue
                if not isinstance(entry.get("report"), dict):
                    continue
                walk(
                    entry["report"],
                    repository=repository,
                    summary_only=True,
                )

    walk(report)
    unique = []
    seen = set()
    root_fingerprints = {
        _finding_fingerprint(finding, include_package=False)
        for finding in findings
        if not finding.get("_review_package")
        and not finding.get("_review_repository")
    }
    for finding in findings:
        # Root scan reports can already index a nested package file. Keep the
        # root occurrence and suppress the package copy, but preserve identical
        # findings from two packages when no root occurrence exists.
        if (
            finding.get("_review_package")
            and _finding_fingerprint(finding, include_package=False) in root_fingerprints
        ):
            continue
        fingerprint = _finding_fingerprint(finding)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(finding)
    return unique


def finding_label(finding):
    """A short, stable prefix identifying the finding kind (D1/security/...)."""
    for key in ("check", "category", "rule"):
        value = finding.get(key)
        if value:
            return str(value)
    return "finding"


def _no_embedded_newlines(value):
    """Collapse embedded newlines so one finding can never inject extra lines
    into a posted GitHub PR comment (SEC-01).

    Most finding text is already backtick-free by construction (scan.py's
    security findings escape their few free-form JSON-sourced fields; the
    semantic/drift engines only ever extract regex-bounded command/path
    tokens), but a custom rule plugin's ``message``/``suggestion`` (opt-in via
    ``--allow-plugins``) is fully attacker-controlled free text. A literal
    newline there could otherwise splice a fake heading, image, or mention into
    the review body/comment; this is the defense-in-depth backstop for that.
    """
    return " ".join(str(value).split())


def _severity_group(level):
    normalized = str(level or "").upper()
    if normalized in _ERROR_LEVELS:
        return "error"
    if normalized in _WARNING_LEVELS:
        return "warning"
    if normalized in _INFO_LEVELS:
        return "info"
    return "info"


def _severity_icon(level):
    return {"error": "❌", "warning": "⚠️", "info": "ℹ️"}[_severity_group(level)]


def _impact_text(finding):
    """Explain why a finding matters to an AI-harness user."""
    label = finding_label(finding)
    if label.startswith("conflict/"):
        label = "conflict"
    elif label.startswith("applicability/"):
        label = "applicability"
    elif label.startswith("G") and label[1:].isdigit():
        label = "gap"
    return _IMPACT_BY_LABEL.get(
        label,
        "AI coding agents may act on inconsistent, stale, or unsafe repository guidance.",
    )


def _rule_title(label):
    if str(label).startswith("conflict/"):
        signal = str(label).split("/", 1)[1]
        return f"Conflicting {signal.replace('_', ' ')} declarations"
    if str(label).startswith("applicability/"):
        detail = str(label).split("/", 1)[1].replace("_", " ").replace("-", " ")
        return f"Structured rule applicability: {detail}"
    if str(label).startswith("G") and str(label)[1:].isdigit():
        return f"Harness completeness gap {label}"
    return _RULE_TITLES.get(label, str(label).replace("_", " ").replace("-", " ").title())


def _display_location(path, line):
    if not path:
        return None
    safe_path = _no_embedded_newlines(path)
    return f"{safe_path}:{line}" if line is not None else safe_path


def _evidence_lines(finding, path=None, line=None):
    """Return deterministic Markdown bullets for the evidence fields available."""
    evidence = []
    location = _display_location(path or finding.get("path"), line)
    if location:
        evidence.append(f"- **Location:** `{location}`")
    field_labels = (
        ("_review_package", "Package"),
        ("_review_repository", "Repository"),
        ("declared", "Declared"),
        ("actual", "Repository fact"),
        ("values", "Conflicting values"),
        ("evidence", "Source evidence"),
        ("item", "Affected item"),
        ("source", "Source"),
    )
    for key, label in field_labels:
        value = finding.get(key)
        if value not in (None, "", [], {}):
            if isinstance(value, (list, tuple, set)):
                value = ", ".join(str(item) for item in value)
            elif isinstance(value, dict):
                value = json.dumps(value, ensure_ascii=False, sort_keys=True)
            evidence.append(f"- **{label}:** {_no_embedded_newlines(value)}")
    return evidence


def format_body(finding, path=None, line=None, heading_level=3):
    """Render one finding into a Markdown comment body.

    Deterministic: only reads fields present on the finding, always in the same
    order, so identical findings produce byte-identical bodies across re-runs.
    """
    label = _no_embedded_newlines(finding_label(finding))
    level = _no_embedded_newlines(finding.get("level") or "FINDING").upper()
    message = _no_embedded_newlines(finding.get("message") or "Harness inconsistency detected.")
    suggestion = _no_embedded_newlines(
        finding.get("suggestion")
        or "Review the finding and align the repository guidance with the current codebase."
    )
    lines = [
        f"{'#' * heading_level} {_severity_icon(level)} {label} · {_rule_title(label)} · {level}",
        "",
        f"**Finding:** {message}",
        "",
        f"**Why it matters:** {_impact_text(finding)}",
    ]
    evidence = _evidence_lines(finding, path=path, line=line)
    if evidence:
        lines.extend(["", "**Evidence:**", *evidence])
    lines.extend(["", f"**Suggested fix:** {suggestion}"])
    return "\n".join(lines)


def _coerce_line(value):
    """Return an int line number if ``value`` looks like one, else ``None``."""
    if isinstance(value, bool):  # bool is an int subclass; never a line number
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return None


def _inline_path(value):
    """Return a safe GitHub repo-relative POSIX path, else ``None``."""
    if value in (None, ""):
        return None
    raw = str(value)
    if "\n" in raw or "\r" in raw or "\\" in raw:
        return None
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        return None
    normalized = path.as_posix()
    return normalized if normalized not in ("", ".") else None


def build_review(report, default_path=None, marker=MARKER, event=REVIEW_EVENT):
    """Build a GitHub PR review payload from a findings report.

    Pure function (no I/O, no network): given a parsed report it returns the
    dict that ``--post`` would send. A finding becomes an inline review
    ``comment`` (``{path, line, body}``) ONLY when it carries both a
    repo-relative ``path`` and a concrete ``line``. Every other finding — one
    with no location at all, one that carries a ``line`` but no ``path`` (unless
    ``default_path`` supplies one), or one that carries a ``path`` but no
    ``line`` — is collected into the review ``body`` summary.

    Requiring a ``line`` on every inline comment is deliberate: GitHub's
    "create review" endpoint 422-rejects the WHOLE review if a single comment
    lacks a valid ``line``/``position``, so a ``path``-only finding that slipped
    through as an inline comment would silently discard the entire review.

    Args:
      report: parsed JSON report (dict) or list of findings / reports.
      default_path: optional repo-relative path used for findings that carry a
        ``line`` but no ``path`` (e.g. check_drift D1/D2/D6 which are implicitly
        about ``AGENTS.md``). When ``None`` such findings go to the summary.
      marker: identifying HTML comment placed at the top of the summary body.
      event: the GitHub review event (COMMENT / APPROVE / REQUEST_CHANGES).

    Returns:
      ``{"event", "body", "comments", "summary_count", "inline_count"}``.
    """
    findings = collect_findings(report)
    comments = []
    summary_findings = []
    for finding in findings:
        raw_path = finding.get("path")
        path = _inline_path(raw_path)
        line = _coerce_line(finding.get("line"))
        if not raw_path and line is not None and default_path:
            path = _inline_path(default_path)
        # An inline comment is only safe to post when it has BOTH a path and a
        # concrete line; otherwise GitHub 422-rejects the entire review. Route
        # everything else (no location, or path-without-line) to the summary.
        if path and line is not None and not finding.get("_review_summary_only"):
            comments.append(
                {
                    "path": path,
                    "line": line,
                    "body": format_body(finding, path=path, line=line),
                }
            )
        else:
            summary_findings.append(finding)

    metadata = _report_metadata(report)
    body = build_summary(
        findings,
        summary_findings,
        inline_count=len(comments),
        marker=marker,
        score=metadata.get("score"),
        grade=metadata.get("grade"),
        default_path=default_path,
    )
    return {
        "event": event,
        "body": body,
        "comments": comments,
        "inline_count": len(comments),
        "summary_count": len(summary_findings),
    }


def _plural(count, singular, plural=None):
    return f"{count} {singular if count == 1 else (plural or singular + 's')}"


def _severity_counts(findings):
    counts = {"error": 0, "warning": 0, "info": 0}
    for finding in findings:
        counts[_severity_group(finding.get("level"))] += 1
    return counts


def _finding_index_line(finding, default_path=None):
    label = _no_embedded_newlines(finding_label(finding))
    level = _no_embedded_newlines(finding.get("level") or "FINDING").upper()
    message = _no_embedded_newlines(finding.get("message") or "Harness inconsistency detected.")
    path = finding.get("path") or (default_path if _coerce_line(finding.get("line")) is not None else None)
    line = _coerce_line(finding.get("line"))
    location = _display_location(path, line)
    where = f" · `{location}`" if location else ""
    return f"- {_severity_icon(level)} **{label} · {_rule_title(label)} · {level}**{where} — {message}"


def _resolved_location(finding, default_path=None):
    line = _coerce_line(finding.get("line"))
    path = finding.get("path")
    if not path and line is not None and default_path:
        path = default_path
    return (str(path), line) if path and line is not None else (path, line)


def _report_metadata(report):
    """Find the first score/grade metadata in a combined report structure."""
    if isinstance(report, list):
        candidates = report
    elif isinstance(report, dict) and isinstance(report.get("reports"), list):
        candidates = [report, *report["reports"]]
    else:
        candidates = [report]
    for candidate in candidates:
        if isinstance(candidate, dict) and (
            candidate.get("score") is not None or candidate.get("grade") is not None
        ):
            return candidate
    return {}


def build_summary(
    all_findings,
    summary_findings,
    inline_count,
    marker=MARKER,
    score=None,
    grade=None,
    default_path=None,
):
    """Assemble the deterministic Markdown summary body for the review.

    Always starts with the identifying ``marker`` line so re-runs are
    recognizable. Reports the inline-comment count and lists every finding that
    could not be attached to a specific file location.
    """
    lines = [marker, "## 🩺 AI Harness Doctor — PR review", ""]
    total = len(all_findings)
    if total == 0:
        lines.extend(
            [
                "### ✅ Harness checks passed",
                "",
                "No drift, semantic, gap, or security findings were reported.",
                "",
            ]
        )
        if score is not None:
            health = f"**Health:** {score}/100"
            if grade:
                health += f" (grade {grade})"
            lines.extend([health, ""])
        lines.extend(
            [
                "**Coverage:** canonical instructions, commands, paths, tool stubs, "
                "repository facts, and configured custom rules.",
                "",
                "**Next step:** No action is required for this review.",
            ]
        )
        return "\n".join(lines) + "\n"

    counts = _severity_counts(all_findings)
    severity_parts = []
    if counts["error"]:
        severity_parts.append(_plural(counts["error"], "error"))
    if counts["warning"]:
        severity_parts.append(_plural(counts["warning"], "warning"))
    if counts["info"]:
        severity_parts.append(_plural(counts["info"], "informational finding"))

    lines.extend(
        [
            "### Review overview",
            "",
            f"**Delivery:** {total} total · {_plural(inline_count, 'inline thread')} · "
            f"{len(summary_findings)} summary-only",
            f"**Severity:** {', '.join(severity_parts) if severity_parts else 'none'}",
        ]
    )
    if score is not None:
        health = f"**Health:** {score}/100"
        if grade:
            health += f" (grade {grade})"
        lines.append(health)

    lines.extend(["", "### Findings index"])
    for finding in all_findings:
        lines.append(_finding_index_line(finding, default_path=default_path))

    lines.extend(["", "<details>", f"<summary><strong>Detailed findings ({total})</strong></summary>", ""])
    for finding in all_findings:
        path, line = _resolved_location(finding, default_path=default_path)
        if path and line is not None and not finding.get("_review_summary_only"):
            placement = f"Inline comment posted at `{_display_location(path, line)}`."
        elif path and line is not None:
            placement = (
                f"Summary only: `{_display_location(path, line)}` belongs to an "
                "independent batch repository."
            )
        elif path:
            placement = f"Summary only: `{_no_embedded_newlines(path)}` has no attachable line."
        else:
            placement = "Summary only: this finding has no attachable file and line."
        lines.extend(
            [
                format_body(finding, path=path, line=line, heading_level=4),
                "",
                f"**Review placement:** {placement}",
                "",
                "---",
                "",
            ]
        )
    lines.extend(["</details>"])

    lines.extend(
        [
            "",
            "### Recommended next steps",
            "1. Fix error-level findings first; they can make agent instructions or CI behavior incorrect.",
            "2. Review warnings for stale or ambiguous guidance before merging.",
            "3. Re-run the harness check and resolve or explicitly accept every remaining finding.",
        ]
    )
    return "\n".join(lines) + "\n"


def load_report(paths):
    """Read one or more JSON reports; repeated ``--report`` forms one review."""
    paths = paths if isinstance(paths, list) else [paths]
    reports = []
    for path in paths:
        reports.append(_load_one_report(path))
    return reports[0] if len(reports) == 1 else {"reports": reports}


def _load_one_report(path):
    """Read one JSON report from ``path`` (``-`` or ``None`` means stdin)."""
    if path in (None, "-"):
        raw = sys.stdin.read()
    else:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
    if not raw.strip():
        return {}
    return json.loads(raw)


class _GitHubAPIError(Exception):
    """Internal HTTP error retaining the status needed for narrow recovery."""

    def __init__(self, method, url, code, reason, detail):
        super().__init__(method, url, code, reason, detail)
        self.method = method
        self.url = url
        self.code = code
        self.reason = reason
        self.detail = detail

    def __str__(self):
        return (
            f"GitHub API {self.method} {self.url} failed: "
            f"{self.code} {self.reason}\n{self.detail}"
        )


def post_review(payload, repo, pr_number, commit_sha, token):
    """Post the assembled review to GitHub via the REST API (stdlib only).

    Upserts one complete marker summary owned by the authenticated poster, then
    uses the pulls "create review" endpoint for any inline annotations. If
    GitHub rejects inline placement with HTTP 422, the already-upserted summary
    remains the successful complete delivery. All network imports happen here
    so ``--dry-run`` stays fully offline. Returns the durable summary response.
    """
    # Import network machinery lazily so importing this module (and running
    # --dry-run) never pulls in urllib/sockets.
    import urllib.error
    import urllib.request
    from urllib.parse import urlsplit

    def _request(url, data=None, method="GET"):
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "api.github.com"
            or parsed.port is not None
            or parsed.username is not None
            or parsed.password is not None
        ):
            raise SystemExit(f"Refusing GitHub API request outside https://api.github.com: {url}")
        body = None if data is None else json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/vnd.github+json")
        if body is not None:
            req.add_header("Content-Type", "application/json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("User-Agent", "ai-harness-doctor")
        try:
            with urllib.request.urlopen(
                req,
                timeout=GITHUB_API_TIMEOUT_SECONDS,
            ) as resp:
                return json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            finally:
                exc.close()
            raise _GitHubAPIError(method, url, exc.code, exc.reason, detail) from None
        except TimeoutError:
            raise SystemExit(
                f"GitHub API {method} {parsed.path} timed out after "
                f"{GITHUB_API_TIMEOUT_SECONDS}s"
            ) from None
        except urllib.error.URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                message = (
                    f"GitHub API {method} {parsed.path} timed out after "
                    f"{GITHUB_API_TIMEOUT_SECONDS}s"
                )
            else:
                message = f"GitHub API {method} {parsed.path} transport failed"
            raise SystemExit(message) from None
        except OSError:
            # Response-body reads can raise a raw socket/SSL OSError after the
            # connection was opened instead of urllib wrapping it in URLError.
            raise SystemExit(
                f"GitHub API {method} {parsed.path} transport failed"
            ) from None

    def _authenticated_identity():
        """Return the token's GraphQL actor identity for safe comment PATCH."""
        query = "query ViewerIdentity { viewer { login id } }"
        try:
            response = _request(
                "https://api.github.com/graphql",
                {"query": query},
                "POST",
            )
        except _GitHubAPIError as exc:
            if exc.code in {403, 404}:
                # Creating is safe; editing an unproven owner is not.
                return None
            raise SystemExit(str(exc)) from None
        data = response.get("data") if isinstance(response, dict) else None
        viewer = data.get("viewer") if isinstance(data, dict) else None
        node_id = viewer.get("id") if isinstance(viewer, dict) else None
        login = viewer.get("login") if isinstance(viewer, dict) else None
        if isinstance(node_id, str) and node_id and isinstance(login, str) and login:
            return {"node_id": node_id, "login": login}
        return None

    def _is_owned_marker(comment, identity):
        if not isinstance(comment, dict) or not identity:
            return False
        body = comment.get("body")
        if not isinstance(body, str) or not body.startswith(MARKER):
            return False
        user = comment.get("user")
        return (
            isinstance(user, dict)
            and user.get("node_id") == identity["node_id"]
            and user.get("login") == identity["login"]
        )

    def _owned_marker_comments(identity):
        if not identity:
            return []
        comments = []
        per_page = 100
        max_pages = 10
        for page in range(1, max_pages + 1):
            url = (
                f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
                f"?per_page={per_page}&page={page}"
            )
            try:
                batch = _request(url)
            except _GitHubAPIError as exc:
                raise SystemExit(str(exc)) from None
            if not isinstance(batch, list):
                raise SystemExit(f"GitHub API GET {url} returned a non-list comment payload")
            comments.extend(
                comment for comment in batch if _is_owned_marker(comment, identity)
            )
            if len(batch) < per_page:
                return comments
        raise SystemExit(
            f"Refusing to upsert PR summary: comment scan exceeded {max_pages * per_page} entries"
        )

    def _upsert_summary():
        identity = _authenticated_identity()
        owned = _owned_marker_comments(identity)
        existing = max(
            owned,
            key=lambda comment: (
                str(comment.get("created_at") or ""),
                comment.get("id") if isinstance(comment.get("id"), int) else -1,
            ),
            default=None,
        )
        data = {"body": payload.get("body", "")}
        if existing is not None:
            url = (
                f"https://api.github.com/repos/{repo}/issues/comments/"
                f"{existing['id']}"
            )
            method = "PATCH"
        else:
            url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
            method = "POST"
        try:
            return _request(url, data, method)
        except _GitHubAPIError as exc:
            raise SystemExit(str(exc)) from None

    summary_response = _upsert_summary()
    comments = payload.get("comments", [])
    if comments:
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
        data = {
            "commit_id": commit_sha,
            "event": payload.get("event", REVIEW_EVENT),
            "body": (
                "AI Harness Doctor inline annotations for this head; "
                "see the marker summary for the complete report."
            ),
            "comments": comments,
        }
        try:
            _request(url, data, "POST")
        except _GitHubAPIError as exc:
            if exc.code != 422:
                raise SystemExit(str(exc)) from None
            # A source line can exist but be outside the PR diff. The complete
            # summary was already delivered, so 422 needs no duplicate fallback.
    return summary_response


def main(argv=None):
    parser = argparse.ArgumentParser(description="Turn drift/scan findings into GitHub PR review comments.")
    parser.add_argument(
        "--report",
        action="append",
        help="Path to a JSON findings report; repeat to combine scan + drift "
        "into one review (default: read one report from stdin).",
    )
    parser.add_argument(
        "--default-path",
        dest="default_path",
        default=None,
        help="Repo-relative path for findings that carry a line but no path "
        "(e.g. AGENTS.md for check_drift D1/D2/D6 findings).",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=True,
        help="Print the assembled review payload as JSON; never posts (DEFAULT).",
    )
    mode.add_argument(
        "--post",
        dest="dry_run",
        action="store_false",
        help="Post the review to GitHub via the REST API.",
    )
    parser.add_argument("--pr", type=int, help="Pull request number (with --post).")
    parser.add_argument("--commit", help="Head commit SHA (with --post).")
    parser.add_argument(
        "--repo",
        help="owner/name (defaults to $GITHUB_REPOSITORY; used with --post).",
    )
    parser.add_argument(
        "--event",
        default=REVIEW_EVENT,
        choices=["COMMENT", "APPROVE", "REQUEST_CHANGES"],
        help="GitHub review event (default: COMMENT).",
    )
    args = parser.parse_args(argv)

    report = load_report(args.report or [None])
    payload = build_review(report, default_path=args.default_path, event=args.event)

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    # --post: gather the environment/args needed to talk to GitHub. Import os
    # here so --dry-run does not even read the environment.
    import os

    token = os.environ.get("GITHUB_TOKEN")
    repo = args.repo or os.environ.get("GITHUB_REPOSITORY")
    if not token:
        parser.error("--post requires GITHUB_TOKEN in the environment")
    if not repo:
        parser.error("--post requires --repo or $GITHUB_REPOSITORY")
    if not args.pr:
        parser.error("--post requires --pr N")
    if not args.commit:
        parser.error("--post requires --commit SHA")

    response = post_review(payload, repo, args.pr, args.commit, token)
    url = response.get("html_url", "")
    print(f"posted PR summary to {repo}#{args.pr} {url}".rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
