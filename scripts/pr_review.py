#!/usr/bin/env python3
"""Turn drift/scan findings into GitHub PR review comments.

Reads a JSON findings report produced by ``check_drift.py --json`` and/or
``scan.py --json`` and assembles a GitHub pull-request review payload: findings
that carry a repo-relative ``path`` become inline review comments
(``{path, line, body}``); findings without a file location are collected into a
single summary body.

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


def collect_findings(report):
    """Flatten the finding lists out of a check_drift and/or scan JSON report.

    Accepts either a single report dict, a list of finding dicts, or a list of
    report dicts, and gathers findings from all the shapes those two tools emit:

      - ``check_drift.py --json`` -> ``{"findings": [...]}``
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
    container_keys = ("findings", "security", "gaps", "semantic")
    if "message" in report and not any(k in report for k in container_keys):
        return [report]
    if isinstance(report.get("findings"), list):
        findings.extend(f for f in report["findings"] if isinstance(f, dict))
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
    for key in ("check", "category"):
        value = finding.get(key)
        if value:
            return str(value)
    return "finding"


def format_body(finding):
    """Render one finding into a Markdown comment body.

    Deterministic: only reads fields present on the finding, always in the same
    order, so identical findings produce byte-identical bodies across re-runs.
    """
    label = finding_label(finding)
    level = finding.get("level")
    header = f"**{label}"
    if level:
        header += f" — {level}"
    header += "**"
    parts = [header]
    message = finding.get("message")
    if message:
        parts.append(str(message))
    suggestion = finding.get("suggestion")
    if suggestion:
        parts.append(f"Suggestion: {suggestion}")
    return " ".join(parts)


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
    dict that ``--post`` would send. Findings carrying a repo-relative ``path``
    become inline review ``comments`` (``{path, line?, body}``, with ``line``
    included only when the finding has one); findings without a location — or
    that only carry a ``line`` and no ``path`` unless ``default_path`` is given —
    are collected into the review ``body`` summary.

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
        if path:
            comment = {"path": str(path)}
            if line is not None:
                comment["line"] = line
            comment["body"] = format_body(finding)
            comments.append(comment)
        else:
            summary_findings.append(finding)

    body = build_summary(summary_findings, inline_count=len(comments), marker=marker)
    return {
        "event": event,
        "body": body,
        "comments": comments,
        "inline_count": len(comments),
        "summary_count": len(summary_findings),
    }


def build_summary(summary_findings, inline_count, marker=MARKER):
    """Assemble the deterministic Markdown summary body for the review.

    Always starts with the identifying ``marker`` line so re-runs are
    recognizable. Reports the inline-comment count and lists every finding that
    could not be attached to a specific file location.
    """
    lines = [marker, "## AI Harness Doctor — PR review", ""]
    total = inline_count + len(summary_findings)
    if total == 0:
        lines.append("No drift or scan findings. ✅")
        return "\n".join(lines) + "\n"

    if inline_count:
        noun = "comment" if inline_count == 1 else "comments"
        lines.append(f"{inline_count} inline {noun} added for located findings.")
        lines.append("")

    if summary_findings:
        lines.append("### Findings without a file location")
        for finding in summary_findings:
            lines.append(f"- {format_body(finding)}")
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


def post_review(payload, repo, pr_number, commit_sha, token):
    """Post the assembled review to GitHub via the REST API (stdlib only).

    Uses inline comments through the pulls "create review" endpoint when there
    are any; otherwise falls back to a single general issue comment carrying the
    summary body. All network imports happen here so ``--dry-run`` stays fully
    offline. Returns the parsed JSON response dict.
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
            detail = exc.read().decode("utf-8", errors="replace")
            raise SystemExit(f"GitHub API {method} {url} failed: {exc.code} {exc.reason}\n{detail}")

    comments = payload.get("comments", [])
    if comments:
        url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
        data = {
            "commit_id": commit_sha,
            "event": payload.get("event", REVIEW_EVENT),
            "body": payload.get("body", ""),
            "comments": comments,
        }
        return _request(url, data, "POST")
    # No inline comments -> a single general issue comment with the summary.
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    return _request(url, {"body": payload.get("body", "")}, "POST")


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
