---
description: Explain AI Harness Doctor instructions for one target path
argument-hint: "[repo-path] [target-path]"
---

Arguments: a target repository path followed by the file/directory path to explain.

Locate the installed AI Harness Doctor skill in this order:

1. `<target-repo>/.claude/skills/ai-harness-doctor`
2. `~/.claude/skills/ai-harness-doctor`

Read `<skill>/SKILL.md` first. Run the deterministic read-only `explain` capability for the target path, present the canonical instruction chain, diagnostic sources, relevant overrides/conflicts, and limitations, then stop. Do not merge, rewrite, or generate instruction files.
