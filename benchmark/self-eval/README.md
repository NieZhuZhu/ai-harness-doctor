# Phase 3 self-bootstrap — AGENTS.md efficacy eval

This directory dogfoods **Phase 3 (Efficacy)** on the `ai-harness-doctor` repo itself:
does *this repo's own* `AGENTS.md` actually steer an AI agent to correct answers?

## Methodology

Because no `claude`/`codex` runner CLI is available in the eval environment, the harness
falls back to its documented **manual protocol** (`eval_run.py` prints it when the runner
binary is missing). An agent answers each task in `tasks.json` using **only** the contents
of `AGENTS.md` — no repo browsing — and the answers are graded offline by the tool's
regex regrader (`eval_run.py --regrade`) against repository ground truth.

- `tasks.json` — 12 objective questions an agent would ask about this repo (build/test
  commands, language/runtime constraints, safety rules, and where the core scripts live).
- `results-before.json` — answers from an agent given the **pre-fix** `AGENTS.md`.
- `results-after.json` — answers from an agent given the **post-fix** `AGENTS.md`.
- `*-graded.json` — the same files after `--regrade` (adds `passed`/`answer`).
- `report.md` — `eval_run.py --compare` before vs after.

## Reproduce

```bash
python3 scripts/eval_run.py --tasks benchmark/self-eval/tasks.json --regrade benchmark/self-eval/results-before.json -o benchmark/self-eval/results-before-graded.json
python3 scripts/eval_run.py --tasks benchmark/self-eval/tasks.json --regrade benchmark/self-eval/results-after.json  -o benchmark/self-eval/results-after-graded.json
python3 scripts/eval_run.py --compare benchmark/self-eval/results-before-graded.json benchmark/self-eval/results-after-graded.json -o benchmark/self-eval/report.md
```

## Result

| | Pass rate |
|---|---|
| before (pre-fix `AGENTS.md`) | 9/12 |
| after (post-fix `AGENTS.md`)  | 12/12 |

**Finding:** the three failures (`drift-script`, `scan-script`, `eval-script`) all shared one
root cause — `AGENTS.md` never named the four phase scripts (`scan.py`, `canonicalize.py`,
`check_drift.py`, `eval_run.py`) and had no directory-layout section, so an agent could not
locate the repo's core deliverables. This violated the skill's own decision rule ("stable
conventions: **project structure**, required commands …").

**Fix:** added a concise `# Project structure` section to `AGENTS.md` mapping each phase to its
script and listing the key directories. Closing that gap raised the pass rate to 12/12 while
keeping `AGENTS.md` small (progressive disclosure preserved). The drift guard stays green
(100/100, grade A) after the change.
