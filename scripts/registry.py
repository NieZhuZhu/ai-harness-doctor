#!/usr/bin/env python3
"""Loader for the shared agent-config registry (single source of truth).

All knowledge about known AI-agent config files — detection globs, canonical stub
paths and stub content — lives in ``assets/agent-tools.json``. ``scan.py``,
``canonicalize.py`` and ``check_drift.py`` all derive their lists from this module
instead of hardcoding them separately, so adding a new tool is a one-line change to
the JSON. Python 3.9 standard library only; no runtime dependencies.
"""

import json
from pathlib import Path

# scripts/ is a sibling of assets/ under the package root.
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _PACKAGE_ROOT / "assets" / "agent-tools.json"


def load_registry():
    """Return the full parsed registry as a dict."""
    with _REGISTRY_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_tools():
    """Return the list of tool entries (claude, cursor, ... roo)."""
    return load_registry().get("tools", [])


def load_canonical():
    """Return the list of canonical file names (e.g. AGENTS.md, AGENT.md)."""
    return load_registry().get("canonical", [])


def canonicalizable_tools():
    """Return only the tools that have a canonical stub form to write/guard."""
    return [t for t in load_tools() if t.get("canonicalizable") and t.get("stub_paths")]
