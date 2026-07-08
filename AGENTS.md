# Project overview

This repository contains the `ai-harness-doctor` Claude Code skill. It audits, consolidates, guards, and evaluates AI harness configuration files around a canonical `AGENTS.md`.

# Build & test

Run the full test suite from the repository root:

```bash
python3 -m unittest discover -s tests -v
npm test
node --check bin/cli.js
node bin/cli.js help
```

# Conventions

- Python scripts must use Python 3.9+ standard library only.
- The set of known AI-agent config files lives in `assets/agent-tools.json` (the single source of truth). `scripts/scan.py`, `scripts/canonicalize.py`, and `scripts/check_drift.py` derive their lists from it via `scripts/registry.py`; add a new tool as one entry there rather than re-hardcoding lists. The `bin/cli.js` `AGENTS` constant is a separate concept (installer deployment targets, not scanned config files) and is intentionally not derived from the registry.
- `bin/cli.js` must use Node >=16 standard library only; do not add npm runtime dependencies.
- Keep scripts deterministic: scanning, stub writing, validation, drift checks, and eval harness mechanics only.
- Do not implement semantic merging in scripts; semantic decisions belong in `SKILL.md` workflow and human review.
- Public documentation is kept in synchronized English, Simplified Chinese, and Japanese READMEs; code comments are English; `assets/AGENTS.template.md` is English.
- Guard suite templates live under `assets/guard/`; keep the pre-commit, PR gate, weekly checkup, and maintenance contract templates synchronized with `bin/cli.js` behavior.
- Installer smoke tests must use an isolated `HOME` temp directory and must never write into the real `~/.claude`, `~/.codex`, or other user config directories.
