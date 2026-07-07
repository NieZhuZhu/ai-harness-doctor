---
description: Run AI Harness Doctor phase 3 efficacy eval
argument-hint: "[repo-path]"
---

Target repo: `$ARGUMENTS` if provided, otherwise the current working directory.

Locate the installed AI Harness Doctor skill in this order:

1. `<target-repo>/.claude/skills/ai-harness-doctor`
2. `~/.claude/skills/ai-harness-doctor`

Read `<skill>/SKILL.md` first. Then execute phase 3 疗效验证 only on the target repo, obeying the exact stop condition documented in `SKILL.md`. Use the deterministic scripts under `<skill>/scripts/`; do not substitute scripts from the target repo unless they are the installed skill scripts.

For `harness-eval`, the intended scope is：3 疗效验证。
