#!/usr/bin/env python3
"""Render scan/drift reports as SARIF 2.1.0 JSON (GitHub code scanning).

SARIF (Static Analysis Results Interchange Format) 2.1.0 is the format GitHub's
code-scanning ingests to surface findings in the Security tab and as inline PR
annotations. This module is a pure, deterministic translation layer: it takes an
in-memory ``scan.py`` or ``check_drift.py`` report and returns the equivalent
SARIF document. Standard library only (``json``/``pathlib`` via the callers), no
runtime dependencies, and stable output — ``rules`` are sorted by id while
``results`` keep the report's own order so diffs stay minimal.
"""

import re
from pathlib import Path

TOOL_NAME = "ai-harness-doctor"
INFORMATION_URI = "https://github.com/NieZhuZhu/ai-harness-doctor"
SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

# Human-readable one-liner per rule family (the prefix before the first ``/`` in
# a ruleId). Used as each rule's shortDescription so GitHub's UI has a label even
# for dynamically-generated rule ids.
FAMILY_DESCRIPTIONS = {
    "warning": "Instruction size / truncation warning",
    "custom": "Custom rule plugin finding",
    "security": "Security checkup finding",
    "gap": "Missing harness infrastructure / gap analysis finding",
    "semantic": "Semantic consistency (AGENTS.md declaration vs code) finding",
    "conflict": "Conflicting declaration across agent config files",
    "drift": "AGENTS.md drift finding",
}

_RULE_COMPONENT_RE = re.compile(r"[^A-Za-z0-9._-]+")

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
        import json

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


def _result(rule_id, level, message, uri=None, start_line=None):
    """Build a single SARIF result.

    When ``uri`` is None the finding has no file location, so ``locations`` is an
    empty list; otherwise it is a single physicalLocation carrying the artifact
    uri and (when known) the 1-based ``startLine``.
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


def build_document(results, rules, version=None):
    """Assemble the top-level SARIF 2.1.0 document."""
    return {
        "$schema": SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
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
        ],
    }


def _scan_results_for_report(report, prefix):
    """Translate one single-repo scan report into SARIF results.

    ``prefix`` is the package directory for a monorepo package (root == ""); when
    non-empty every uri is prefixed with ``f"{prefix}/{path}"`` so findings point
    at the package's files.
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
            )
        )
    # conflicts are cross-file and unlocated → conflict/<signal>, always warning.
    for conflict in report.get("conflicts", []):
        signal = conflict.get("signal", "")
        values = conflict.get("values", {})
        rule_id = "conflict/" + signal
        message = f"Conflicting {signal} declarations: " + ", ".join(sorted(values.keys()))
        results.append(_result(rule_id, "warning", message))
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
    return build_document(results, rules, version=version)


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
            )
        )
    rules = _rules_from_results(results)
    return build_document(results, rules, version=version)
