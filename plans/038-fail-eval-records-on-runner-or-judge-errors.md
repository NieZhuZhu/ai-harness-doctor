# Plan 038: Prevent failed runners and judges from producing passing eval records

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm expected results before continuing. Stop on
> any STOP condition; do not improvise. Update `plans/README.md` when done unless
> a reviewer owns the index.
>
> **Drift check (run first)**:
> `git diff --stat a2a7227..HEAD -- scripts/eval_run.py tests/test_eval_run.py README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md benchmark/self-eval/results-after-graded.json`
> If in-scope code changed, compare live code with Current state. A semantic
> mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: M
- **Risk**: MED
- **Depends on**: Plans 030 and 033 (DONE)
- **Category**: bug
- **Planned at**: commit `a2a7227`, 2026-07-16

## Why this matters

Eval health is the project's efficacy authority, but current grading trusts
stdout even when the process that produced it failed. A runner can print a
regex-matching answer and exit 9; the record stores `exit_code: 9` yet
`passed: true` and health 100/A. An external judge can print a passing JSON
verdict and exit 7; its verdict is also trusted and health remains 100/A.

Operational failure must dominate content. Preserve outputs for diagnosis and
continue the remaining matrix/round tasks, but a failed runner or judge can
never create a passing record. This is distinct from CLI exit semantics:
`eval` may still finish exit 0 with failed task records unless `--fail-under`
requires a threshold.

## Current state and reproductions

- `scripts/eval_run.py:1408-1418` parses judge stdout and returns its `passed`
  field regardless of `proc.returncode`; it merely stores `exit_code`.
- `scripts/eval_run.py:1625-1676` grades runner stdout before considering
  `proc.returncode`.
- `scripts/eval_run.py:1892-1927` repeats the same behavior for matrix runners.
- `run_subprocess()` already captures exit/stdout/stderr and kills process
  groups on timeout; reuse it.
- Plans 030/033 validate task definitions and stored result records, but a
  freshly produced record with boolean `passed`, integer `exit_code`, and
  consistent health is schema-valid. Neither plan covers producer exit truth.

Reproduced at `a2a7227`:

```text
RUNNER_NONZERO
runner: prints "right", exits 9
regex: "right"
record: passed=true, exit_code=9
health: 100/A

JUDGE_NONZERO
runner: exits 0 with answer
judge: prints {"passed":true,"score":1}, exits 7
record: passed=true
judge.exit_code=7
health: 100/A
```

## Target contract

1. Runner exit code 0 is required before answer grading can pass.
2. A non-zero runner record:
   - has `passed: false`;
   - preserves `exit_code`, timeout state, bounded stdout/stderr, extracted
     answer, and usage if parseable;
   - does not invoke an external/LLM/builtin judge, because failed runner output
     is not a valid answer to grade.
3. Timeout remains a failed task with `exit_code: null`, and process-group kill
   semantics are unchanged.
4. External judge exit code 0 plus valid verdict JSON is required. Non-zero:
   - returns `passed: false`;
   - preserves judge `exit_code`, bounded raw output, and a concise reason such
     as `judge exited 7`;
   - cannot be overridden by `{"passed": true}` stdout.
5. Exit 0 malformed external judge output remains a failed judge verdict.
6. A missing judge executable or spawn `OSError` becomes a failed judge verdict
   with concise machine-visible reason, not a traceback and not fallback to a
   builtin/LLM judge. The operator explicitly chose `--judge-cmd`.
7. LLM judge API failure keeps the documented deterministic builtin fallback;
   that path does not have a local subprocess exit code.
8. Single runner, every round, and every matrix agent use one shared runner
   execution/grading helper so behavior cannot diverge again.
9. Result compatibility is additive:
   - keep existing task keys;
   - matrix records should preserve runner `exit_code`, stdout/stderr when
     already available in single mode, and judge metadata consistently;
   - old stored files remain readable.
10. `--fail-under`, baseline, stats, compare, evidence, and stored-health
    derivation use the corrected `passed` booleans without special cases.
11. Result/error text must be bounded before persistence. Do not let a failed
    runner/judge write unbounded stdout/stderr into result JSON.
12. Keep explicit shell-template support for operator-supplied `--runner` /
    `--runner-cmd` / `--judge-cmd`. Prompt/answer/rubric/input substitutions
    stay shell-quoted. This plan does not misclassify explicit templates as
    task-data command injection.
13. Task `command` checks remain `shell=False` and unchanged.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Eval tests | `python3 -m unittest discover -s tests -p 'test_eval_run.py' -v` | all pass |
| Python lint | `npm run lint:py` | exit 0 |
| Docs sync | `npm run lint:docs` | aligned |
| Full gate | `npm run check` | all pass |
| Self scan | `python3 scripts/scan.py . --fail-on-security` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | 100/A |
| Eval regrade | `python3 scripts/eval_run.py --regrade benchmark/self-eval/results-after.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md -o benchmark/self-eval/results-after-graded.json` | writes result |
| Eval gate | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | 33/33 A |

## Scope

**In scope**:

- `scripts/eval_run.py`
- `tests/test_eval_run.py`
- `README.md`
- `README.zh-CN.md`
- `README.ja.md`
- `SKILL.md`
- `AGENTS.md`
- `benchmark/self-eval/results-after-graded.json`
- `plans/README.md` and this plan for status/evidence

**Out of scope**:

- MCP server behavior; it exposes only read-only task generation, not agent
  execution.
- Removing shell-template support for operator-provided commands.
- Task command-check semantics.
- Adding cost-budget, task-count, rounds, or matrix caps.
- Parallelizing runners.
- Changing the overall eval CLI exit code when some tasks fail; use
  `--fail-under`.
- LLM provider endpoint/key/fallback policy.
- Stored result schema redesign or evidence schema changes.

## Git workflow

- Branch: `fix/038-eval-runner-judge-exits`
- Commit: `fix(eval): fail records on runner and judge errors`
- One focused backward-compatible PR.
- Merge only after drift, lint, Node 16/20/22, self-test, and Python
  3.9/3.10/3.12 all green; admin bypass only for sole-maintainer approval.

## Steps

### Step 1: Add failing operational false-success tests

Add end-to-end tests for single, `--rounds 2`, and matrix:

- runner prints matching answer then exits non-zero;
- runner prints passing judge answer then exits non-zero; assert judge command
  marker is absent;
- external judge prints passing JSON then exits non-zero;
- external judge exits 0 with malformed JSON;
- external judge binary missing;
- runner/judge stderr and stdout remain diagnostic but bounded.

Assert record `passed`, health, exit code, judge reason, output files, and
continued execution of later tasks/agents. Tests must fail on `a2a7227` because
non-zero stdout is trusted.

**Verify**: focused new cases fail with false 100/A or passing records.

### Step 2: Centralize runner execution and operational gating

Extract one helper used by `_run_round` and `run_task_with_runner` that:

- invokes the shell template through `run_subprocess`;
- returns a complete record skeleton for success/non-zero/timeout/spawn error;
- bounds stdout/stderr before storing;
- grades only when `returncode == 0`;
- preserves usage and answer extraction.

Matrix must stop dropping stdout/stderr/exit evidence relative to single mode.
Do not change process-group timeout handling.

**Verify**: single/round/matrix non-zero runner cases all fail and later work
continues.

### Step 3: Make external judge operational failure authoritative

Update `run_judge`/`grade_answer`:

- non-zero exit always returns failed verdict irrespective of JSON;
- exit 0 malformed JSON is failed;
- timeout/missing executable/OSError become concise failed judge metadata;
- external judge failures do not fall back to builtin/LLM because explicit
  operator intent must remain visible;
- cap stored raw/stdout/stderr.

Preserve environment variables, temp input cleanup, shell quoting, and process
group kill.

**Verify**: passing JSON + exit 7 produces failed judge/record and health 0/F.

### Step 4: Verify downstream health and historical compatibility

Generate valid single/multi/matrix results with:

- runner success;
- runner non-zero;
- judge success;
- judge non-zero.

Run score/stats/compare/regrade as applicable. Confirm stored-result validators
accept the new producer output, derive health from corrected records, and old
fixtures still pass.

**Verify**: focused producer→consumer round trips pass.

### Step 5: Document and codify operational truth

Update all three READMEs and `SKILL.md`: a task passes only when the runner exits
0 and its check passes; an external judge must exit 0 with valid verdict JSON.
Non-zero/timeout/spawn failures remain records for diagnosis and matrices keep
running. Explain that overall CLI exit remains health-gate controlled.

Add a concise `AGENTS.md` invariant, keep it under the strict size threshold,
and refresh only the evidence hash through honest offline regrade.

**Verify**: docs sync, 33/33 evidence gate, scan, strict drift.

### Step 6: Full gates and PR evidence

Run every command above. Open one implementation PR, wait for all nine required
contexts, resolve discussions, then record PR/CI evidence and mark DONE.

## Test plan

- Single runner: success, non-zero matching output, timeout, missing binary.
- Multi-round: non-zero one/all rounds, correct aggregate health/flakiness.
- Matrix: one good and one operationally failed runner; later agents continue.
- External judge: success, non-zero passing JSON, malformed JSON, timeout,
  missing executable.
- Assert failed runner does not invoke any judge.
- Bound persisted stdout/stderr/raw.
- Stored score/stats/compare compatibility.
- Existing prompt shell-quote and command-check injection tests remain green.

## Done criteria

- [ ] No non-zero runner record can be `passed: true`.
- [ ] Failed runner output is never sent to a judge.
- [ ] No non-zero external judge verdict can pass.
- [ ] Timeout/spawn/malformed judge failures are concise failed metadata.
- [ ] Single, rounds, and matrix share one operational gate.
- [ ] Later tasks/agents continue after a failed record.
- [ ] Diagnostic output is bounded and exit evidence preserved.
- [ ] Existing stored result/evidence/baseline consumers remain compatible.
- [ ] Trilingual docs/SKILL/AGENTS/self-eval are current.
- [ ] Full local gate and all nine PR contexts pass.

## STOP conditions

Stop and report if:

- Existing documented behavior intentionally treats non-zero runner/judge exit
  as a valid success protocol.
- Fixing matrix parity requires a breaking result schema rather than additive
  fields.
- External judge failure must intentionally fall back despite explicit
  `--judge-cmd` selection.
- A shared helper would weaken process-group timeout cleanup or prompt quoting.
- The implementation requires changing command-check semantics or removing
  operator shell templates.
- In-scope code drift invalidates the plan.

## Maintenance notes

- Process exit is operational evidence and dominates stdout content.
- Task failure is a record-level result; overall CLI failure remains controlled
  by `--fail-under` and regression gates.
- Every new runner mode must reuse the shared execution helper.
- Explicit external judge failure should stay visible, not silently change
  grading strategy.
