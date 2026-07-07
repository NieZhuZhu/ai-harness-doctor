---
description: Run AI Harness Doctor full pipeline
argument-hint: "[repo-path]"
---

Target repo: `$ARGUMENTS` if provided, otherwise the current working directory.

Locate the installed AI Harness Doctor skill in this order:

1. `<target-repo>/.claude/skills/ai-harness-doctor`
2. `~/.claude/skills/ai-harness-doctor`

Read `<skill>/SKILL.md` first. Then execute phases 0→2 in order (phase 3 only when explicitly requested) on the target repo, obeying the exact stop condition documented in `SKILL.md`. Use the deterministic scripts under `<skill>/scripts/`; do not substitute scripts from the target repo unless they are the installed skill scripts.
