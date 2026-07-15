#!/usr/bin/env python3
"""Generate the per-command agent adapters from a single source of truth.

The adapters under ``adapters/{codex,cursor,gemini}/`` are near-identical pointer
prompts that vary only by command (phase / action / stop condition) and by target
format (Markdown for Codex & Cursor, TOML for Gemini). Hand-maintaining 18 files
(6 commands x 3 flavors) invites exactly the kind of drift this project guards
against, so this script renders every one of them from ``ADAPTER_COMMANDS`` below.

Usage:
    python3 scripts/gen_adapters.py            # (re)write adapters under ./adapters
    python3 scripts/gen_adapters.py /repo       # target another repo root
    python3 scripts/gen_adapters.py --check      # verify committed adapters, write nothing

``--check`` exits non-zero when a committed adapter is missing or diverges from
what the single source would emit, so CI can gate re-divergence. Stdlib only.
"""

import argparse
import sys
from pathlib import Path

# Single source of truth: one entry per harness command.
# - ``action``      the imperative clause shared by every flavor.
# - ``stop_md``     the parenthetical stop condition used by the Markdown flavors
#                   (Codex & Cursor).
# - ``stop_toml``   the stop condition phrasing used by the Gemini TOML flavor.
# - ``description`` the Gemini command ``description`` field.
# Order follows the CLI's COMMAND_NAMES (doctor, scan, treat, drift, eval, explain).
ADAPTER_COMMANDS = [
    {
        "name": "doctor",
        "action": "Execute full pipeline phases 0\u21922",
        "description": "Run AI Harness Doctor full pipeline",
        "stop_md": "phase 3 only if explicitly requested",
        "stop_toml": "phase 3 only if explicitly requested",
    },
    {
        "name": "scan",
        "action": "Execute Phase 0 \u2014 Checkup (Scan)",
        "description": "Run AI Harness Doctor scan",
        "stop_md": "stop at migration-scope confirmation",
        "stop_toml": "migration-scope confirmation",
    },
    {
        "name": "treat",
        "action": "Execute Phase 1 \u2014 Treat (Canonicalize)",
        "description": "Run AI Harness Doctor treatment",
        "stop_md": "stop at human-adjudicated conflicts",
        "stop_toml": "human-adjudicated conflicts",
    },
    {
        "name": "drift",
        "action": "Execute Phase 2 \u2014 Follow-up (Drift Guard)",
        "description": "Run AI Harness Doctor drift guard",
        "stop_md": "stop when checks pass or repair advice is given",
        "stop_toml": "checks pass or repair advice is given",
    },
    {
        "name": "eval",
        "action": "Execute Phase 3 \u2014 Efficacy (Eval)",
        "description": "Run AI Harness Doctor efficacy eval",
        "stop_md": "stop when metrics are produced",
        "stop_toml": "metrics are produced",
    },
    {
        "name": "explain",
        "action": "Explain the effective canonical instruction chain for one target path",
        "description": "Explain AI Harness Doctor instructions for a path",
        "stop_md": "stop after presenting the read-only scope evidence",
        "stop_toml": "scope evidence is presented without modifying files",
    },
]

# Markdown flavors share byte-identical content; only the directory differs.
MD_FLAVORS = ("codex", "cursor")

# Templates use __TOKEN__ placeholders (not str.format) so the literal
# {{PLAYBOOK}} / {{args}} mustache placeholders survive untouched.
MD_TEMPLATE = (
    "Read {{PLAYBOOK}}/SKILL.md. __ACTION__ on the target repo (argument or cwd), "
    "and obey the phase stop condition (__STOP__). Scripts live in {{PLAYBOOK}}/scripts/.\n"
)

TOML_TEMPLATE = (
    'description = "__DESC__"\n'
    'prompt = """\n'
    "Read {{PLAYBOOK}}/SKILL.md. __ACTION__ on the target repo ({{args}} or cwd), "
    "and obey the phase stop condition (__STOP__). Scripts live in {{PLAYBOOK}}/scripts/.\n"
    '"""\n'
)


def render_md(cmd):
    return MD_TEMPLATE.replace("__ACTION__", cmd["action"]).replace("__STOP__", cmd["stop_md"])


def render_toml(cmd):
    return (
        TOML_TEMPLATE.replace("__DESC__", cmd["description"])
        .replace("__ACTION__", cmd["action"])
        .replace("__STOP__", cmd["stop_toml"])
    )


def generate(root):
    """Return an ordered {absolute_path: content} map of every generated adapter."""
    root = Path(root)
    files = {}
    for cmd in ADAPTER_COMMANDS:
        md = render_md(cmd)
        for flavor in MD_FLAVORS:
            files[root / "adapters" / flavor / f"harness-{cmd['name']}.md"] = md
        files[root / "adapters" / "gemini" / "harness" / f"{cmd['name']}.toml"] = render_toml(cmd)
    return files


def _rel(path, root):
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def check(root):
    """Compare committed adapters against the single source. Returns (missing, drifted)."""
    files = generate(root)
    missing, drifted = [], []
    for path, content in files.items():
        if not path.is_file():
            missing.append(path)
        elif path.read_text(encoding="utf-8") != content:
            drifted.append(path)
    return files, missing, drifted


def write(root):
    """Write adapters that are missing or out of date. Returns the count written."""
    files = generate(root)
    written = 0
    for path, content in files.items():
        if path.is_file() and path.read_text(encoding="utf-8") == content:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written += 1
    return files, written


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate agent adapters from a single source of truth.")
    parser.add_argument("repo_root", nargs="?", default=".")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify committed adapters match the single source; exit 1 on drift (writes nothing).",
    )
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()

    if args.check:
        files, missing, drifted = check(root)
        for path in sorted(missing):
            print(f"MISSING: {_rel(path, root)}")
        for path in sorted(drifted):
            print(f"DRIFT:   {_rel(path, root)}")
        if missing or drifted:
            print(
                f"\n{len(files)} adapters checked from {len(ADAPTER_COMMANDS)} command definitions; "
                f"{len(missing)} missing, {len(drifted)} drifted."
            )
            print("Run: python3 scripts/gen_adapters.py   to regenerate.")
            return 1
        print(
            f"OK: {len(files)} generated adapters match the single source "
            f"({len(ADAPTER_COMMANDS)} command definitions)."
        )
        return 0

    files, written = write(root)
    print(f"Wrote {written} adapter(s) of {len(files)} total from {len(ADAPTER_COMMANDS)} command definitions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
