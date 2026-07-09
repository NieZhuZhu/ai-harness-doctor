#!/usr/bin/env python3
"""Example ai-harness-doctor rule plugin.

Copy this file into your target repository's `.ai-harness-doctor/rules/`
directory (or point `--rules DIR` at a directory containing it) to add your own
DETERMINISTIC scan/drift rules without forking the tool.

The plugin contract is a single function::

    def check(root, context) -> list[dict]:
        ...

* ``root``    — a ``pathlib.Path`` to the target repository root.
* ``context`` — a read-only ``dict`` of facts about the run. It always contains
                ``phase`` (``"scan"`` or ``"drift"``) and ``agents_text`` (the
                canonical ``AGENTS.md`` text, or ``""`` when it is absent).
* returns     — a list of finding dicts. Each finding needs at least ``level``
                and ``message``; ``path``, ``line``, ``suggestion`` and ``rule``
                (a short id for the specific check) are optional but recommended.

Keep plugins deterministic and standard-library-only, and treat the repository
as read-only (never write into the repo being audited).
"""

from pathlib import Path


def check(root, context):
    """Two tiny illustrative rules; replace with your own project policy."""
    root = Path(root)
    findings = []

    # Rule 1: require a top-level LICENSE file.
    if not (root / "LICENSE").is_file() and not (root / "LICENSE.md").is_file():
        findings.append({
            "rule": "example/require-license",
            "level": "WARN",
            "message": "No top-level LICENSE file found.",
            "suggestion": "Add a LICENSE (or LICENSE.md) at the repository root.",
        })

    # Rule 2: discourage a banned phrase in AGENTS.md (uses context.agents_text).
    agents_text = context.get("agents_text", "")
    for lineno, line in enumerate(agents_text.splitlines(), 1):
        if "TODO(agents)" in line:
            findings.append({
                "rule": "example/no-agent-todo",
                "level": "NOTICE",
                "path": "AGENTS.md",
                "line": lineno,
                "message": "AGENTS.md still contains a `TODO(agents)` marker.",
                "suggestion": "Resolve the TODO before shipping the canonical AGENTS.md.",
            })

    return findings
