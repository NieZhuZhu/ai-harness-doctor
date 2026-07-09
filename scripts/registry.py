#!/usr/bin/env python3
"""Loader for the shared agent-config registry (single source of truth).

All knowledge about known AI-agent config files — detection globs, canonical stub
paths and stub content — lives in ``assets/agent-tools.json``. ``scan.py``,
``canonicalize.py`` and ``check_drift.py`` all derive their lists from this module
instead of hardcoding them separately, so adding a new tool is a one-line change to
the JSON. Python 3.9 standard library only; no runtime dependencies.
"""

import json
import re
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

# Single source of truth for recognizing a Node.js version reference in a line of
# AGENTS.md / config prose and normalizing it to its MAJOR version. Previously
# scan.py (Phase-0 conflict signal), semantic.py (Phase-0 declared-version check)
# and check_drift.py (Phase-2 D6 drift gate) each carried their OWN slightly
# different regex, so the same line could yield a different Node version (or none)
# depending on the stage (TD-06). They now all go through ``node_version_major``
# so every stage extracts the identical value. The pattern accepts: an optional
# ``.js`` suffix, an optional ``:`` separator, an optional ``version``/``v`` word,
# an optional comparator (``>=``/``<=``/``==``/``^``/``~``), an optional ``v``
# prefix and an optional surrounding quote, then the version; only the MAJOR
# component is captured and any ``.minor`` / ``.x`` suffix is consumed.
NODE_VERSION_RE = re.compile(
    r"\bnode(?:\.js)?\s*:?\s*(?:v|version)?\s*(?:>=?|<=?|==?|\^|~)?\s*v?[\"']?(\d+)(?:\.\d+|\.x)*",
    re.I,
)


def node_version_major(line):
    """Return the MAJOR Node.js version (int) referenced in ``line``, else ``None``.

    Single shared extractor used by scan.py, semantic.py and check_drift.py so all
    three stages normalize a Node version reference to the same value (TD-06)."""
    m = NODE_VERSION_RE.search(line)
    return int(m.group(1)) if m else None


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
