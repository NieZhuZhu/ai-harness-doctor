# Project overview

This repository contains the `ai-harness-doctor` Claude Code skill. It audits, consolidates, guards, and evaluates AI harness configuration files around a canonical `AGENTS.md`.

# Build & test

Run the full test suite from the repository root:

```bash
python3 -m unittest discover -s tests -v
```

# Conventions

- Python scripts must use Python 3.9+ standard library only.
- Keep scripts deterministic: scanning, stub writing, validation, drift checks, and eval harness mechanics only.
- Do not implement semantic merging in scripts; semantic decisions belong in `SKILL.md` workflow and human review.
- Documentation is primarily Chinese; code comments are English; `assets/AGENTS.template.md` is English.
