# Plan 030: Validate every eval task before any runner or judge executes

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 704806e..HEAD -- scripts/eval_run.py tests/test_eval_run.py README.md README.zh-CN.md README.ja.md SKILL.md EXTERNAL_VALIDATION.md benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json benchmark/self-eval/results-after-graded.json benchmark/self-eval/README.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: correctness / security / efficacy / tests / docs
- **Planned at**: commit `704806e`, 2026-07-16

## Why this matters

Eval tasks can invoke paid external coding agents and LLM judges. The current
preflight validates only that the task file is a JSON array of objects and that
optional `evidence` has the right shape. Missing `prompt`/`id`, invalid
`check`, duplicate IDs, or an invalid timeout are discovered lazily while
iterating the pack. A valid first task can therefore spend model time before a
malformed later task throws a raw traceback and prevents any result artifact
from being written.

The complete task pack must be validated once, before evidence hashing, runner
binary probing, subprocesses, network judges, or output writes. Single-run,
multi-round, matrix, regrade, and strict freshness must consume one shared
validated task contract rather than each failing differently.

## Current state

- `scripts/eval_run.py:130-147` is named like task validation but checks only
  object/evidence shape:

  ```python
  def _task_evidence_paths(tasks):
      if not isinstance(tasks, list):
          raise ValueError("tasks file must contain a JSON array")
      for index, task in enumerate(tasks):
          if not isinstance(task, dict):
              raise ValueError(f"task {index} must be an object")
          declared = task.get("evidence")
          ...
  ```

- `scripts/eval_run.py:1323-1375` accesses `task["prompt"]` and `task["id"]`
  only when the task is about to run:

  ```python
  for task in tasks:
      prompt = task["prompt"]
      command = args.runner.replace("{prompt}", shlex.quote(prompt))
      proc = run_subprocess(...)
      ...
      record = {"id": task["id"], ...}
  ```

- Matrix mode repeats the same lazy access in
  `run_task_with_runner()` (`scripts/eval_run.py:1577-1612`) and later indexes
  by `task["id"]` while rendering. Regrade constructs
  `{task["id"]: task for task in tasks}` at `scripts/eval_run.py:1484`.

- `grade_answer()` accepts unknown check types as a silent failure, and assumes
  `check` supports `.get()`. A string/list check therefore crashes only after
  the runner already returned.

- The audit used a two-task pack: the first task was valid and appended its
  prompt to a marker file; the second lacked `prompt`. The CLI exited 1 with:

  ```text
  KeyError: 'prompt'
  ```

  The marker contained `first`, proving the runner executed once, while the
  requested result file did not exist.

- `tests/test_eval_run.py` covers evidence preflight, runner timeouts, command
  injection, and mode parity, but has no complete task-schema suite or
  assertion that a malformed later task causes zero runner calls.

- Public docs show the expected task shape (`README.md:562-575`) and supported
  check types, but do not say malformed packs fail before paid execution.

## Target contract

1. Parse and validate the complete task array exactly once per command path.
2. Validation happens before any runner/judge subprocess, HTTP model call,
   evidence digest, baseline mutation, or result/report write.
3. Every task must be an object with:
   - a unique, non-empty string `id`;
   - a non-empty string `prompt`;
   - optional finite positive numeric `timeout_s` (booleans are not numbers);
   - a `check` object whose `type` is exactly `regex`, `command`, or `judge`;
   - existing task evidence rules from Plan 029.
4. `regex` and `command` checks require a string `value`; preserve valid
   historical strings, including regex syntax, without compiling at load time.
5. `judge` checks may use the existing `rubric`/`criteria`, `expect`, `reject`,
   `min_score`, and `model` fields. Validate only their public types/ranges:
   string rubric/criteria/model, string-or-list-of-strings expect/reject, finite
   numeric `min_score` in `[0, 1]`. Do not change grading semantics.
6. Unknown top-level keys remain allowed for generated metadata such as
   `scope`, `target`, and future additive provenance.
7. Invalid task files produce one concise `task error: ...` diagnostic naming
   only the task index/id and field; no traceback, task content, prompt,
   absolute host path, or secret value.
8. Duplicate IDs fail closed; they must not be silently overwritten by matrix
   maps or regrade lookup maps.
9. Strict score verifies the current task pack with the same schema before
   accepting freshness. Non-strict `--score`, `--stats`, `--compare`, and
   `--trend` do not acquire unrelated task requirements.
10. Generated task JSON remains byte-compatible except where a separate
    generator bug is discovered (a STOP condition).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused eval tests | `python3 -m unittest discover -s tests -p 'test_eval_run.py' -v` | all pass |
| CLI forwarding tests | `python3 -m unittest discover -s tests -p 'test_cli.py' -v` | all pass |
| Python lint | `ruff check scripts/eval_run.py tests/test_eval_run.py` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | `OK` |
| Full gate | `npm run check` | exit 0 |
| Self eval | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0, grade A |
| Self scan | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0, grade A |

## Scope

**In scope**:

- `scripts/eval_run.py`
- `tests/test_eval_run.py`
- `tests/test_cli.py` only if public CLI forwarding needs a regression
- synchronized `README.md`, `README.zh-CN.md`, `README.ja.md`
- `SKILL.md`
- `EXTERNAL_VALIDATION.md` only for a real generated-task validation
- `benchmark/self-eval/` only if the public maintenance contract changes
- `plans/README.md`

**Out of scope**:

- Changing runner command templating or Action `args`.
- Running every scope automatically.
- Changing regex/command/judge grading outcomes for valid tasks.
- Defining a JSON Schema package or adding runtime dependencies.
- Validating result JSON, matrix files, or baseline history beyond what this
  task-pack bug requires.
- Changing evidence schema version or freshness exit code.
- Adding a write-capable MCP eval runner.
- Refactoring `eval_run.py` by file size.
- Updating `AGENTS.md`; the batch completion PR owns final durable invariants.

## Git workflow

- Branch: `fix/eval-task-preflight`
- Commit: `fix(eval): validate tasks before execution`
- One focused backward-compatible bug/cost-safety PR.
- Do not push directly to `main`.
- Wait for all nine required contexts, then squash-merge and delete the branch.
- This is patch-level unless valid documented task packs stop working; that is
  a STOP condition.

## Steps

### Step 1: Add failing no-side-effect characterization tests

Create table-driven tests for invalid JSON, non-array roots, non-object tasks,
missing/empty/wrong-type IDs and prompts, duplicate IDs, malformed checks,
unsupported check types, wrong check payload types, invalid timeouts, malformed
judge fields, and the existing malformed evidence cases.

The load-bearing integration test must place a valid first task before a
malformed second task and use a deterministic local runner that writes a marker.
Assert:

- non-zero exit;
- no marker file (zero runner calls);
- no result/matrix/report file;
- no traceback;
- concise field/index diagnostic.

Run the same pack through single, `--rounds 2`, and matrix modes. Regrade must
reject the same pack before altering its input/output file.

**Verify**: the new tests fail against `704806e` because the first runner
executes or a traceback appears.

### Step 2: Build one pure task-schema validator

Add one helper that accepts already-decoded JSON and returns the validated list
unchanged (or a new list preserving every valid field). Keep evidence
collection inside or immediately after this helper so object traversal occurs
once.

Implement deterministic field diagnostics and duplicate-ID detection. Use
`math.isfinite()` for numeric fields and explicitly reject `bool`.

Do not compile user regex at load time and do not normalize prompts/IDs beyond
checking `.strip()`; output/task identity must retain the authored strings.

**Verify**: pure validation tests pass, including additive generated metadata.

### Step 3: Route every task consumer through the validator

Introduce a single task-file loader that wraps file/UTF-8/JSON failures and
schema failures as `ValueError` with safe diagnostics. Call it from:

- single/multi run;
- matrix;
- regrade;
- strict score/evidence verification.

Catch once at the CLI boundary and emit `task error: ...` without a traceback.
Ensure task validation precedes `prepare_evidence_manifest()`, binary probing,
runner/judge calls, baseline writes, and outputs.

Non-strict score/stats/compare/trend must retain current behavior because they
do not execute or re-bind task definitions.

**Verify**: all invalid packs make zero runner/judge calls in every applicable
mode; valid mode parity tests remain green.

### Step 4: Preserve valid-task compatibility

Characterize existing generated root/scoped tasks and representative
hand-written regex/command/judge tasks. Verify:

- generated task JSON is unchanged;
- valid task result shapes are unchanged apart from already-documented
  evidence metadata;
- optional top-level metadata survives;
- existing schema-v1 evidence verification still passes;
- command checks remain shell-free.

**Verify**: existing eval suite plus new compatibility assertions pass.

### Step 5: Document and externally validate the preflight boundary

Update all three READMEs and `SKILL.md`: task packs are validated completely
before any runner/LLM/judge/evidence/output side effect, and list the concise
required fields.

Use an isolated copy of a real generated Mastra task pack (do not change the
source repo): append one malformed final task, run a marker-only local runner,
and verify zero invocations. Record commit, target, task count, malformed field,
and no-agent/no-source-write boundary in `EXTERNAL_VALIDATION.md`.

If the public wording changes the self-maintenance answer, update the
evidence-bound self-eval artifacts honestly; otherwise leave them untouched.

**Verify**: docs sync, focused/full tests, self-eval, scan, and strict drift.

## Test plan

- Pure table-driven schema validation.
- Valid-first/malformed-later zero-side-effect regression.
- Single/multi/matrix/regrade parity.
- Strict-score current-task validation.
- Duplicate ID rejection.
- Valid generated and hand-written compatibility.
- Sanitized errors without traceback/prompt/path leakage.
- Existing evidence and command-injection tests remain green.

## Done criteria

- [ ] Every applicable mode validates the whole task pack before side effects.
- [ ] A malformed later task causes zero runner/judge calls.
- [ ] Invalid task input emits a concise `task error` and no traceback.
- [ ] IDs are non-empty and unique.
- [ ] Check type/payload, timeout, judge fields, and evidence are validated.
- [ ] Valid task packs and generated task JSON remain compatible.
- [ ] Strict freshness validates current task schema; unrelated offline modes do not.
- [ ] Real generated-task preflight validation is recorded.
- [ ] Trilingual docs and `SKILL.md` describe the boundary.
- [ ] Full local and nine required CI gates pass.

## STOP conditions

Stop and report back if:

- Existing generated tasks violate the proposed contract.
- A documented valid task needs a field shape excluded above.
- Compatibility requires changing valid grading results or result schema.
- Safe validation requires running a regex, command, judge, or plugin.
- Any mode must write an output before validation can complete.
- Verification fails twice after a reasonable scoped fix.

## Maintenance notes

- Any future task field must be added to the shared validator and all mode
  parity tests before a runner consumes it.
- Preflight is a cost/safety boundary, not merely nicer error handling.
- Keep diagnostics metadata-only; never echo prompts, command bodies, evidence
  contents, or host paths.
- Stored result validation is implemented separately by Plan 033; keep the two
  schemas distinct because task definitions authorize execution while result
  records authorize offline health and baseline decisions.
