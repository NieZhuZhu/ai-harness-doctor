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
import sys

# Identifying marker embedded in every summary/general comment body so re-runs
# can recognize (and, if desired, supersede) a prior ai-harness-doctor review.
MARKER = "<!-- ai-harness-doctor:pr-review -->"

# GitHub pull-request review "event". COMMENT posts the review without
# approving or requesting changes, which is the safe default for an automated
# advisory gate.
REVIEW_EVENT = "COMMENT"

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
}


def collect_findings(report):
    """Flatten the finding lists out of a check_drift and/or scan JSON report.

    Accepts either a single report dict, a list of finding dicts, or a list of
    report dicts, and gathers findings from all the shapes those two tools emit:

      - ``check_drift.py --json`` -> ``{"findings": [...], "custom": [...]}``
      - ``scan.py --json``        -> ``{"security": [...], "gaps": [...],
                                         "semantic": {"findings": [...]}}``

    Returns a flat list of finding dicts, preserving input order.
    """
    findings = []
    if isinstance(report, list):
        for item in report:
            findings.extend(collect_findings(item))
        return findings
    if not isinstance(report, dict):
        return findings
    # A bare finding dict (has a message but none of the container keys).
    container_keys = ("findings", "custom", "security", "gaps", "semantic")
    if "message" in report and not any(k in report for k in container_keys):
        return [report]
    if isinstance(report.get("findings"), list):
        findings.extend(f for f in report["findings"] if isinstance(f, dict))
    if isinstance(report.get("custom"), list):
        findings.extend(f for f in report["custom"] if isinstance(f, dict))
    if isinstance(report.get("security"), list):
        findings.extend(f for f in report["security"] if isinstance(f, dict))
    if isinstance(report.get("gaps"), list):
        findings.extend(f for f in report["gaps"] if isinstance(f, dict))
    semantic = report.get("semantic")
    if isinstance(semantic, dict) and isinstance(semantic.get("findings"), list):
        findings.extend(f for f in semantic["findings"] if isinstance(f, dict))
    return findings


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
    return _IMPACT_BY_LABEL.get(
        label,
        "AI coding agents may act on inconsistent, stale, or unsafe repository guidance.",
    )


def _rule_title(label):
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
        ("declared", "Declared"),
        ("actual", "Repository fact"),
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
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


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
        path = finding.get("path")
        line = _coerce_line(finding.get("line"))
        if not path and line is not None and default_path:
            path = default_path
        # An inline comment is only safe to post when it has BOTH a path and a
        # concrete line; otherwise GitHub 422-rejects the entire review. Route
        # everything else (no location, or path-without-line) to the summary.
        if path and line is not None:
            comments.append(
                {
                    "path": str(path),
                    "line": line,
                    "body": format_body(finding, path=str(path), line=line),
                }
            )
        else:
            summary_findings.append(finding)

    metadata = report if isinstance(report, dict) else {}
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
        if path and line is not None:
            placement = f"Inline comment posted at `{_display_location(path, line)}`."
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


def load_report(path):
    """Read the JSON report from ``path`` (``-`` or ``None`` means stdin)."""
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

    Uses inline comments through the pulls "create review" endpoint when there
    are any. If GitHub rejects their placement with HTTP 422, retries once as a
    single general issue comment carrying the complete summary body. Payloads
    without inline comments use that summary endpoint directly. All network
    imports happen here so ``--dry-run`` stays fully offline. Returns the parsed
    JSON response dict.
    """
    # Import network machinery lazily so importing this module (and running
    # --dry-run) never pulls in urllib/sockets.
    import urllib.error
    import urllib.request

    def _request(url, data, method):
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("Content-Type", "application/json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("User-Agent", "ai-harness-doctor")
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            finally:
                exc.close()
            raise _GitHubAPIError(method, url, exc.code, exc.reason, detail) from None

    comments = payload.get("comments", [])
    if comments:
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
        data = {
            "commit_id": commit_sha,
            "event": payload.get("event", REVIEW_EVENT),
            "body": payload.get("body", ""),
            "comments": comments,
        }
        try:
            return _request(url, data, "POST")
        except _GitHubAPIError as exc:
            if exc.code != 422:
                raise SystemExit(str(exc)) from None
            # A source line can exist but still be outside the PR diff. GitHub
            # then rejects the entire review; preserve all repair guidance by
            # delivering the already self-contained summary instead.
            url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
            try:
                return _request(url, {"body": payload.get("body", "")}, "POST")
            except _GitHubAPIError as fallback_exc:
                raise SystemExit(str(fallback_exc)) from None
    # No inline comments -> a single general issue comment with the summary.
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    try:
        return _request(url, {"body": payload.get("body", "")}, "POST")
    except _GitHubAPIError as exc:
        raise SystemExit(str(exc)) from None


def main(argv=None):
    parser = argparse.ArgumentParser(description="Turn drift/scan findings into GitHub PR review comments.")
    parser.add_argument(
        "--report",
        help="Path to a JSON findings report (default: read from stdin).",
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

    report = load_report(args.report)
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
    print(f"posted PR review to {repo}#{args.pr} {url}".rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
