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

# Single source of truth for the maximum size (in bytes) of a canonical pointer
# stub. A tool file that references AGENTS.md but exceeds this has "regrown" past
# the minimal-pointer budget. Shared by scan.py (gap analysis), check_drift.py
# (D3 drift gate) and canonicalize.py (Phase 1 stub validation) so the threshold
# cannot drift between stages. Reconciled to the value the canonical/writing
# stage (canonicalize.py) already used; genuine minimal stubs are well under it
# (<200 bytes) (CORR-06).
STUB_POINTER_MAX_BYTES = 800

# Single source of truth mapping a committed lockfile name -> the package manager
# it implies. Shared by semantic.py, check_drift.py and canonicalize.py so the
# drift gate, the semantic engine and the draft generator agree on which managers
# exist — including bun (bun.lockb / bun.lock), which the drift gate previously
# omitted and was therefore blind to (TD-01).
LOCKFILE_MANAGERS = {
    "package-lock.json": "npm",
    "npm-shrinkwrap.json": "npm",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "bun.lockb": "bun",
    "bun.lock": "bun",
}


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
