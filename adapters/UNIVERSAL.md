# Universal AI Harness Doctor adapter

Copy/paste for any agent that can read files and run shell commands:

> Read `{{{PLAYBOOK}}}/SKILL.md` and run phase N on `<repo>`. Obey the phase stop condition exactly. Scripts live in `{{{PLAYBOOK}}}/scripts/`.

Bare CLI fallback for humans and CI:

```bash
npx ai-harness-doctor scan .
npx ai-harness-doctor plan . -o merge-plan.md
npx ai-harness-doctor stubs . --apply
npx ai-harness-doctor drift . --strict
npx ai-harness-doctor eval --tasks tasks.json --label after --workdir . -o results-after.json
```
