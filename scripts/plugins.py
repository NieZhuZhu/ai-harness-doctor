#!/usr/bin/env python3
"""User-extensible rule plugins for scan.py / check_drift.py.

This module is a tiny, standard-library-only loader that lets users extend the
scan (Phase 0) and drift (Phase 2) engines with their own **deterministic**
rules, without forking the tool.

Plugin contract
---------------
A rule plugin is a plain Python module that exposes a single function::

    def check(root, context) -> list[dict]:
        ...

* ``root`` is a :class:`pathlib.Path` pointing at the target repository root.
* ``context`` is a read-only ``dict`` of facts about the current run. It always
  contains at least ``phase`` (``"scan"`` or ``"drift"``) and ``agents_text``
  (the canonical ``AGENTS.md`` text, or ``""`` when absent). Treat unknown keys
  as optional — future phases may add more.
* The function returns a list of finding dicts. Each finding must carry a
  ``level`` (e.g. ``"ERROR"``/``"WARN"``/``"NOTICE"``) and a ``message``, and may
  optionally include ``path``, ``line``, ``suggestion``, and a ``rule`` id that
  names the specific check. Anything missing is filled with safe defaults.

Plugins must stay deterministic and dependency-free (Python 3.9 standard library
only) and must treat the audited repository as read-only.

Security & opt-in
-----------------
Plugins execute arbitrary Python found *inside the scanned repository*, so they
are DISABLED BY DEFAULT. No plugin directory is searched and no plugin code is
imported unless the caller explicitly opts in (``run_plugins(...,
allow_plugins=True)``, wired to the ``--allow-plugins`` CLI flag). Without that
opt-in :func:`run_plugins` is a no-op returning an empty list, so auditing an
untrusted repository never runs its code.

When opt-in IS granted, modules are discovered from:

1. the conventional ``<root>/.ai-harness-doctor/rules/*.py`` directory in the
   scanned repository, and
2. any explicit directories passed via the ``--rules DIR`` flag (repeatable).

Files whose names start with ``_`` (e.g. ``__init__.py``, ``_helpers.py``) are
skipped so plugins can keep private helpers alongside their rules.

Robustness
----------
A plugin that fails to import, does not define ``check``, or raises at runtime
MUST NOT crash the core scan/drift. Each plugin is isolated in ``try``/``except``
and any failure is surfaced as a ``level: "ERROR"`` finding describing the
problem, so a broken plugin degrades gracefully instead of taking down the audit.
"""

import hashlib
import importlib.util
from pathlib import Path

# Conventional per-repo plugin directory, relative to the scanned repo root.
DEFAULT_RULES_DIRNAME = ".ai-harness-doctor/rules"


def discover_rule_files(root, extra_dirs=None):
    """Return an ordered, de-duplicated list of plugin ``.py`` files.

    Sources are searched in a stable order — the conventional
    ``<root>/.ai-harness-doctor/rules/`` directory first, then each explicit
    directory in ``extra_dirs`` (typically ``--rules DIR`` values) — and within a
    directory files are sorted by name so the resulting order (and thus the
    report output) is byte-stable. Files whose names start with ``_`` are
    skipped. A directory that does not exist or cannot be read is ignored.
    """
    root = Path(root)
    search_dirs = [root / DEFAULT_RULES_DIRNAME]
    for extra in extra_dirs or []:
        search_dirs.append(Path(extra))
    seen = {}
    for directory in search_dirs:
        try:
            if not directory.is_dir():
                continue
            candidates = sorted(directory.glob("*.py"))
        except OSError:
            continue
        for path in candidates:
            if path.name.startswith("_") or not path.is_file():
                continue
            try:
                key = path.resolve()
            except OSError:
                key = path
            seen.setdefault(key, path)
    return list(seen.values())


def _plugin_label(path, root):
    """A stable, human-readable identifier for a plugin (repo-relative if possible)."""
    try:
        return path.resolve().relative_to(Path(root).resolve()).as_posix()
    except (ValueError, OSError):
        return path.name


def _module_name(path):
    """A collision-free import name derived from the plugin path."""
    try:
        digest = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:12]
    except OSError:
        digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:12]
    stem = "".join(ch if ch.isalnum() else "_" for ch in path.stem)
    return f"ai_harness_doctor_plugin_{stem}_{digest}"


def _load_module(path):
    """Import a plugin module in isolation (never registered in sys.modules)."""
    spec = importlib.util.spec_from_file_location(_module_name(path), str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot create an import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _error_finding(rule, plugin, message, suggestion):
    return {
        "level": "ERROR",
        "rule": rule,
        "plugin": plugin,
        "message": message,
        "suggestion": suggestion,
    }


def _normalize_finding(raw, plugin):
    """Coerce a plugin-returned value into a well-formed finding dict."""
    if not isinstance(raw, dict):
        return _error_finding(
            "plugin-output",
            plugin,
            f"Rule plugin `{plugin}` returned a non-dict finding: {raw!r}",
            "Return finding dicts with at least `level` and `message` from check().",
        )
    finding = dict(raw)
    level = finding.get("level", "NOTICE")
    finding["level"] = level.upper() if isinstance(level, str) else "NOTICE"
    finding.setdefault("message", "")
    finding.setdefault("rule", "custom")
    # Stamp the source plugin so a finding is always traceable back to its module.
    finding["plugin"] = plugin
    return finding


def run_plugins(root, context=None, extra_dirs=None, allow_plugins=False):
    """Load and run every discovered rule plugin, returning merged findings.

    Plugin execution is opt-in: unless ``allow_plugins`` is true this is a
    no-op that returns an empty list *without* discovering or importing any
    module. This is a security gate — plugin files live inside the scanned
    (potentially untrusted) repository, so importing them runs arbitrary code
    on the host/CI. Callers must explicitly opt in (via ``--allow-plugins``).

    When opted in, each plugin is isolated: an import failure, a missing/invalid
    ``check`` function, a runtime exception, or a bad return value is converted
    into an ``ERROR`` finding instead of propagating. The core scan/drift
    therefore never crashes because of a user plugin. Returns a list of
    normalized finding dicts (empty when no plugins are present).
    """
    # Security gate: never touch the scanned repo's plugin directory or import
    # any code from it unless the caller explicitly opted in.
    if not allow_plugins:
        return []
    root = Path(root)
    context = dict(context or {})
    findings = []
    for path in discover_rule_files(root, extra_dirs):
        plugin = _plugin_label(path, root)
        try:
            module = _load_module(path)
        # SystemExit is a BaseException, not an Exception, so a plugin that calls
        # sys.exit() at import time previously escaped isolation and killed the
        # whole scan/drift process — contradicting this function's own "never
        # crashes because of a user plugin" guarantee. KeyboardInterrupt is left
        # to propagate deliberately (an operator's own Ctrl-C during a scan).
        except (Exception, SystemExit) as exc:  # noqa: BLE001 - isolate any import-time failure
            findings.append(
                _error_finding(
                    "plugin-load",
                    plugin,
                    f"Failed to import rule plugin `{plugin}`: {exc.__class__.__name__}: {exc}",
                    "Fix the plugin so it imports cleanly, or remove it from the rules directory.",
                )
            )
            continue
        check = getattr(module, "check", None)
        if not callable(check):
            findings.append(
                _error_finding(
                    "plugin-contract",
                    plugin,
                    f"Rule plugin `{plugin}` does not define a callable `check(root, context)`.",
                    "Add `def check(root, context): ...` returning a list of finding dicts.",
                )
            )
            continue
        try:
            results = check(root, context)
        # See the import-time except above: SystemExit must be caught here too,
        # or a plugin's check() calling sys.exit() kills the whole run instead of
        # degrading to an ERROR finding.
        except (Exception, SystemExit) as exc:  # noqa: BLE001 - isolate any runtime failure
            findings.append(
                _error_finding(
                    "plugin-error",
                    plugin,
                    f"Rule plugin `{plugin}` raised at runtime: {exc.__class__.__name__}: {exc}",
                    "Fix the plugin's check() so it handles the repository without raising.",
                )
            )
            continue
        if results is None:
            continue
        if not isinstance(results, (list, tuple)):
            findings.append(
                _error_finding(
                    "plugin-output",
                    plugin,
                    f"Rule plugin `{plugin}` returned {type(results).__name__}, expected a list of finding dicts.",
                    "Return a list of finding dicts (or an empty list) from check().",
                )
            )
            continue
        for raw in results:
            findings.append(_normalize_finding(raw, plugin))
    return findings
