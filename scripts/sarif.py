#!/usr/bin/env python3
"""Render scan/drift reports as SARIF 2.1.0 JSON (GitHub code scanning).

SARIF (Static Analysis Results Interchange Format) 2.1.0 is the format GitHub's
code-scanning ingests to surface findings in the Security tab and as inline PR
annotations. This module is a pure, deterministic translation layer: it takes an
in-memory ``scan.py`` or ``check_drift.py`` report and returns the equivalent
SARIF document. Standard library only (``json``/``pathlib`` via the callers, and
``hashlib`` here), no runtime dependencies, and stable output — ``rules`` are
sorted by id while ``results`` keep the report's own order so diffs stay minimal.

Two GitHub-documented alert-lifecycle mechanisms are handled here so uploaded
alerts are durable and composable:

* every ``result`` carries ``partialFingerprints`` derived from a
  line-insensitive finding identity, so an unrelated edit keeps the same alert
  rather than closing it and opening a new one;
* each command's ``run`` carries an ``automationDetails.id`` category
  (``ai-harness-doctor/scan/`` vs ``ai-harness-doctor/drift/``) so uploading both
  SARIF files for one commit does not make the second close the first's alerts.

The identity model here is a deliberately small, dependency-free re-implementation
of the same line-insensitive canonical identity ``scan.py`` uses for baselines
(``scan.scan_finding_fingerprint``); ``sarif.py`` intentionally does not import
``scan.py``. A parity test keeps the two aligned for baseline families.
"""

import hashlib
import json
import re
from pathlib import Path

TOOL_NAME = "ai-harness-doctor"
INFORMATION_URI = "https://github.com/NieZhuZhu/ai-harness-doctor"
SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

# GitHub keys a code-scanning run to a category via runs[].automationDetails.id
# (parsed as "category/run-id"). Uploading two SARIF files for the SAME tool and
# commit WITHOUT distinct categories makes the second upload close the first
# one's alerts. scan and drift share the tool name, so each command gets its own
# category with an empty run-id (the trailing slash keeps the category
# well-defined). See docs: "runAutomationDetails object".
SCAN_CATEGORY = TOOL_NAME + "/scan/"
DRIFT_CATEGORY = TOOL_NAME + "/drift/"

# The single partialFingerprints key GitHub stores to match a result across
# commits. The value is a line-insensitive digest of the finding's identity, so
# an unrelated edit or one-line shift keeps the same alert instead of closing it
# and opening a new one.
FINGERPRINT_KEY = "aiHarnessDoctorIdentity"

# Human-readable one-liner per rule family (the prefix before the first ``/`` in
# a ruleId). Used as each rule's shortDescription so GitHub's UI has a label even
# for dynamically-generated rule ids.
FAMILY_DESCRIPTIONS = {
    "warning": "Instruction size / truncation warning",
    "applicability": "Structured rule applicability diagnostic",
    "custom": "Custom rule plugin finding",
    "security": "Security checkup finding",
    "gap": "Missing harness infrastructure / gap analysis finding",
    "semantic": "Semantic consistency (AGENTS.md declaration vs code) finding",
    "conflict": "Conflicting declaration across agent config files",
    "drift": "AGENTS.md drift finding",
}

_RULE_COMPONENT_RE = re.compile(r"[^A-Za-z0-9._-]+")

# Normalize ``path:line`` evidence to ``path:<line>`` so an unrelated line shift
# keeps the same fingerprint. This mirrors ``scan._without_line_evidence`` so the
# SARIF identity and the baseline identity stay aligned for baseline families.
_LINE_EVIDENCE_RE = re.compile(r"(?P<path>(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+):\d+\b")


def _without_line_evidence(text):
    """Normalize file:line evidence so unrelated line shifts keep identity."""
    return _LINE_EVIDENCE_RE.sub(r"\g<path>:<line>", str(text or ""))


# Source severity vocabulary → SARIF level. Anything unmapped (INFO and any
# unknown level) falls back to "note".
_LEVEL_MAP = {
    "HIGH": "error",
    "ERROR": "error",
    "MEDIUM": "warning",
    "WARN": "warning",
    "NOTICE": "warning",
}


def tool_version():
    """Return the package version from package.json, or "0" on any error."""
    try:
        package = Path(__file__).resolve().parents[1] / "package.json"
        data = json.loads(package.read_text(encoding="utf-8"))
        return str(data["version"])
    except Exception:
        return "0"


def sarif_level(level):
    """Map a source severity level to a SARIF level (default "note")."""
    return _LEVEL_MAP.get(level, "note")


def _message_text(finding):
    """Compose the SARIF message: the finding message plus any suggestion."""
    message = finding.get("message", "")
    suggestion = finding.get("suggestion")
    if suggestion:
        message = message + " — " + suggestion
    return message


def _rule_component(value, fallback):
    """Return a stable SARIF-safe dynamic rule-id component."""
    if not isinstance(value, str):
        return fallback
    component = _RULE_COMPONENT_RE.sub("-", value.strip()).strip("-._")
    return component or fallback


def _fingerprint(rule_id, uri, identity):
    """Return a stable, line-insensitive hex fingerprint for one result.

    The digest combines the SARIF ``rule_id``, the artifact ``uri`` (so the same
    logical finding in two files/packages stays distinct), and the finding's
    line-insensitive ``identity`` fields. No line number, column, suggestion
    text, or run timestamp participates, so unrelated edits keep the same alert.
    A missing uri contributes a fixed empty string rather than crashing.
    """
    payload = json.dumps(
        {"ruleId": rule_id, "uri": uri or "", "identity": identity or {}},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _result(rule_id, level, message, uri=None, start_line=None, identity=None):
    """Build a single SARIF result.

    When ``uri`` is None the finding has no file location, so ``locations`` is an
    empty list; otherwise it is a single physicalLocation carrying the artifact
    uri and (when known) the 1-based ``startLine``. Every result also carries a
    deterministic, line-insensitive ``partialFingerprints`` entry derived from
    ``identity`` so GitHub matches the alert across commits.
    """
    result = {
        "ruleId": rule_id,
        "level": level,
        "message": {"text": message},
    }
    if uri is None:
        result["locations"] = []
    else:
        physical = {"artifactLocation": {"uri": uri}}
        if start_line is not None:
            physical["region"] = {"startLine": start_line}
        result["locations"] = [{"physicalLocation": physical}]
    result["partialFingerprints"] = {
        FINGERPRINT_KEY: _fingerprint(rule_id, uri, identity)
    }
    return result


def _rules_from_results(results):
    """Derive the unique, id-sorted ``rules`` array from the results.

    Each distinct ruleId contributes one rule whose defaultConfiguration.level is
    the level of its FIRST occurrence in ``results``. Sorting by id keeps the
    output deterministic regardless of finding order.
    """
    first_level = {}
    for result in results:
        rule_id = result["ruleId"]
        if rule_id not in first_level:
            first_level[rule_id] = result["level"]
    rules = []
    for rule_id in sorted(first_level):
        family = rule_id.split("/", 1)[0]
        rules.append(
            {
                "id": rule_id,
                "name": rule_id,
                "shortDescription": {"text": FAMILY_DESCRIPTIONS.get(family, family)},
                "defaultConfiguration": {"level": first_level[rule_id]},
            }
        )
    return rules


def _run_properties(command, results, ok=None, score=None, grade=None, resolved_count=0):
    """Return deterministic producer metadata for Action/report consumers.

    Counts are derived from the FINAL SARIF results so baselined debt stays
    excluded and every emitted family (including monorepo/custom findings) is
    represented exactly once. Drift health fields are additive only when the
    source report provides them, preserving compatibility with minimal callers.
    """
    levels = {"error": 0, "warning": 0, "note": 0}
    for result in results:
        level = result.get("level", "note")
        levels[level if level in levels else "note"] += 1
    metadata = {
        "command": command,
        "findingCount": len(results),
        "errorCount": levels["error"],
        "warningCount": levels["warning"],
        "noteCount": levels["note"],
        "resolvedBaselineCount": resolved_count,
    }
    if isinstance(ok, bool):
        metadata["ok"] = ok
    if isinstance(score, (int, float)) and not isinstance(score, bool):
        metadata["score"] = score
    if isinstance(grade, str):
        metadata["grade"] = grade
    return {"aiHarnessDoctor": metadata}


def build_document(results, rules, version=None, category=None, properties=None):
    """Assemble the top-level SARIF 2.1.0 document.

    When ``category`` is set, the run carries ``automationDetails.id`` so GitHub
    keys this run to its own code-scanning category and a second command's
    upload for the same commit does not close this one's alerts.
    """
    run = {
        "tool": {
            "driver": {
                "name": TOOL_NAME,
                "informationUri": INFORMATION_URI,
                "version": version or tool_version(),
                "rules": rules,
            }
        },
        "results": results,
    }
    if category:
        run["automationDetails"] = {"id": category}
    if properties:
        run["properties"] = properties
    return {
        "$schema": SCHEMA,
        "version": "2.1.0",
        "runs": [run],
    }


def _gap_identity(finding, package):
    """Line-insensitive identity for a gap finding (mirrors scan baseline)."""
    return {
        "family": "gap",
        "rule": finding.get("check", ""),
        "package": package,
        "path": "",
        "message": _without_line_evidence(finding.get("message", "")),
        "item": finding.get("item", ""),
    }


def _semantic_identity(finding, package):
    """Line-insensitive identity for a semantic finding (mirrors baseline)."""
    return {
        "family": "semantic",
        "rule": finding.get("category", ""),
        "package": package,
        "path": "AGENTS.md",
        "message": _without_line_evidence(finding.get("message", "")),
        "declared": finding.get("declared", ""),
        "actual": finding.get("actual", ""),
    }


def _conflict_identity(finding, package):
    """Line-insensitive identity for a conflict finding (mirrors baseline).

    The identity ``message`` matches ``scan._scan_finding_records`` (no scope
    suffix); the human-readable SARIF message keeps the scope suffix separately.
    """
    signal = finding.get("signal", "")
    values = sorted(str(value) for value in finding.get("values", {}))
    identity = {
        "family": "conflict",
        "rule": signal,
        "package": package,
        "path": "",
        "message": f"Conflicting {signal} declarations: " + ", ".join(values),
        "values": values,
    }
    if finding.get("scope") not in (None, "", "."):
        identity["scope"] = finding["scope"]
    return identity


def _plain_identity(family, rule, package, path, message):
    """Line-insensitive identity for non-baseline families (never suppressed)."""
    return {
        "family": family,
        "rule": rule or "",
        "package": package,
        "path": path or "",
        "message": _without_line_evidence(message),
    }


def _scan_results_for_report(report, prefix):
    """Translate one single-repo scan report into SARIF results.

    ``prefix`` is the package directory for a monorepo package (root == ""); when
    non-empty every uri is prefixed with ``f"{prefix}/{path}"`` so findings point
    at the package's files. ``prefix`` also flows into each finding's identity as
    the ``package`` field, matching ``scan._scan_finding_records``.
    """

    def make_uri(path):
        if path is None:
            return None
        return f"{prefix}/{path}" if prefix else path

    results = []
    # size/truncation warnings → warning/size.
    for finding in report.get("warnings", []):
        results.append(
            _result(
                "warning/size",
                sarif_level(finding.get("level")),
                _message_text(finding),
                uri=make_uri(finding.get("path")),
                start_line=finding.get("line"),
                identity=_plain_identity(
                    "warning", "size", prefix,
                    finding.get("path", ""), finding.get("message", ""),
                ),
            )
        )
    for finding in report.get("applicability_warnings", []):
        category = _rule_component(finding.get("category"), "metadata")
        results.append(
            _result(
                "applicability/" + category,
                sarif_level(finding.get("level")),
                _message_text(finding),
                uri=make_uri(finding.get("path")),
                start_line=finding.get("line"),
                identity=_plain_identity(
                    "applicability", finding.get("category", ""), prefix,
                    finding.get("path", ""), finding.get("message", ""),
                ),
            )
        )
    # security → security/<category>; path/line come straight from the finding.
    for finding in report.get("security", []):
        rule_id = "security/" + finding.get("category", "")
        results.append(
            _result(
                rule_id,
                sarif_level(finding.get("level")),
                _message_text(finding),
                uri=make_uri(finding.get("path")),
                start_line=finding.get("line"),
                identity=_plain_identity(
                    "security", finding.get("category", ""), prefix,
                    finding.get("path", ""), finding.get("message", ""),
                ),
            )
        )
    # gaps are about the canonical AGENTS.md → gap/<check>, no line.
    for finding in report.get("gaps", []):
        rule_id = "gap/" + finding.get("check", "")
        results.append(
            _result(
                rule_id,
                sarif_level(finding.get("level")),
                _message_text(finding),
                uri=make_uri("AGENTS.md"),
                identity=_gap_identity(finding, prefix),
            )
        )
    # semantic findings also anchor to AGENTS.md → semantic/<category>, with line.
    for finding in report.get("semantic", {}).get("findings", []):
        rule_id = "semantic/" + finding.get("category", "")
        results.append(
            _result(
                rule_id,
                sarif_level(finding.get("level")),
                _message_text(finding),
                uri=make_uri("AGENTS.md"),
                start_line=finding.get("line"),
                identity=_semantic_identity(finding, prefix),
            )
        )
    # conflicts are cross-file and unlocated → conflict/<signal>, always warning.
    for conflict in report.get("conflicts", []):
        signal = conflict.get("signal", "")
        values = conflict.get("values", {})
        rule_id = "conflict/" + signal
        message = f"Conflicting {signal} declarations: " + ", ".join(sorted(values.keys()))
        if conflict.get("scope") not in (None, "", "."):
            message += f" (scope: {conflict['scope']})"
        results.append(
            _result(
                rule_id,
                "warning",
                message,
                identity=_conflict_identity(conflict, prefix),
            )
        )
    # opt-in plugin findings → custom/<rule>; plugins remain disabled unless the
    # scan caller explicitly supplied --allow-plugins.
    for finding in report.get("custom", []):
        rule_id = "custom/" + _rule_component(finding.get("rule"), "custom")
        results.append(
            _result(
                rule_id,
                sarif_level(finding.get("level")),
                _message_text(finding),
                uri=make_uri(finding.get("path")),
                start_line=finding.get("line"),
                identity=_plain_identity(
                    "custom", finding.get("rule", ""), prefix,
                    finding.get("path", ""), finding.get("message", ""),
                ),
            )
        )
    return results


def scan_report_to_sarif(report, version=None):
    """Render a full ``scan.py`` report (incl. monorepo packages) as SARIF."""
    results = _scan_results_for_report(report, "")
    for package in report.get("packages", []):
        prefix = package.get("path", "")
        results.extend(_scan_results_for_report(package.get("report", {}), prefix))
    rules = _rules_from_results(results)
    properties = _run_properties(
        "scan",
        results,
        resolved_count=len(report.get("resolved_baseline", [])),
    )
    return build_document(
        results,
        rules,
        version=version,
        category=SCAN_CATEGORY,
        properties=properties,
    )


def drift_report_to_sarif(report, version=None):
    """Render a ``check_drift.py`` report as SARIF (findings + custom, no info)."""
    results = []
    for finding in report.get("findings", []) + report.get("custom", []):
        rule_id = "drift/" + finding.get("check", "custom")
        uri = finding.get("path") or "AGENTS.md"
        results.append(
            _result(
                rule_id,
                sarif_level(finding.get("level")),
                _message_text(finding),
                uri=uri,
                start_line=finding.get("line"),
                identity=_plain_identity(
                    "drift", finding.get("check", "custom"), "",
                    uri, finding.get("message", ""),
                ),
            )
        )
    rules = _rules_from_results(results)
    properties = _run_properties(
        "drift",
        results,
        ok=report.get("ok"),
        score=report.get("score"),
        grade=report.get("grade"),
        resolved_count=len(report.get("resolved_baseline", [])),
    )
    return build_document(
        results,
        rules,
        version=version,
        category=DRIFT_CATEGORY,
        properties=properties,
    )
