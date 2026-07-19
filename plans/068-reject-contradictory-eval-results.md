# Plan 068: Reject stored eval passes that contradict explicit operational failure evidence

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and honor every STOP condition. Update the plan index
> only when actual merge/check evidence exists.
>
> **Drift check**:
>
> ```bash
> git diff --stat 5280ad3..HEAD -- \
>   scripts/eval_run.py tests/test_eval_run.py \
>   README.md README.zh-CN.md README.ja.md README.es.md README.ko.md \
>   README.pt-BR.md README.fr.md SKILL.md AGENTS.md \
>   benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json \
>   benchmark/self-eval/results-after-graded.json
> ```
>
> If `_validate_result_records`, `validate_result`, or the four reproductions
> below changed semantically, rerun the audit before implementing.

## Status

- **Priority**: P0
- **Effort**: S
- **Risk**: LOW–MED (fail-closed validation of contradictions only; valid
  producer and legacy/manual records remain accepted)
- **Depends on**: Plans 033, 038, and 065 (DONE)
- **Category**: correctness / efficacy integrity
- **Planned at**: commit `5280ad3`, 2026-07-20
- **Status**: TODO

## Why this matters

Plan 038 made operational success authoritative during live execution: a task
cannot pass unless its runner exits zero, and an explicit external judge cannot
pass unless it exits zero with a passing verdict. Plan 065 applies the same
rule while regrading stored regex output.

The shared stored-result validator does not enforce that invariant. It accepts
`passed: true` alongside explicit runner failure, timeout, judge failure, or a
judge's own `passed: false`. Every offline consumer then derives health from the
contradictory top-level boolean. A hand-edited, corrupted, or produced-by-old-
bug result can therefore pass `--score --fail-under 80`, `--stats`, evidence
gates, and baseline writes at 100/A despite carrying proof that execution did
not succeed.

Stored result files are untrusted evidence. Reject explicit contradictions with
the existing safe `result error`/exit-2 path before health, thresholds, evidence
hash reads, reports, or baseline writes. Do not silently rewrite `passed`;
validation is read-only and a contradictory artifact needs operator attention.

## Mechanical reproduction on `main@5280ad3`

Four one-record task result files were independently tested through both
`--score --fail-under 80` and `--stats`:

| Case | Stored fields | Observed |
|---|---|---|
| runner non-zero | `passed:true`, `exit_code:9` | exit 0, 100/A |
| timeout | `passed:true`, `timed_out:true`, `exit_code:null` | exit 0, 100/A |
| judge non-zero | `passed:true`, runner exit 0, `judge.exit_code:7`, `judge.passed:true` | exit 0, 100/A |
| judge rejected | `passed:true`, runner exit 0, `judge.exit_code:0`, `judge.passed:false` | exit 0, 100/A |

The timeout case even reports “1/1 tasks passed; 1 timed out,” a logically
impossible health summary.

## Current state

`scripts/eval_run.py:1108-1129` validates only record container, `id`,
`passed`, and `timed_out` types:

```python
def _validate_result_records(records, location, allow_ungraded=False):
    ...
    if "passed" not in record and allow_ungraded:
        all_graded = False
    elif not isinstance(record.get("passed"), bool):
        _result_error(item, "field `passed` must be a boolean")
    if "timed_out" in record and not isinstance(record["timed_out"], bool):
        _result_error(item, "field `timed_out` must be a boolean")
```

`compute_health()` counts only truthy `passed`; it counts timeouts separately
but does not make them fail. `validate_result()` is already the shared read
boundary for:

- `--score`;
- `--stats`;
- both `--compare` inputs;
- `--regrade`;
- single, round, bare-round, and matrix/agents families.

That seam makes this a narrow validator patch.

## Target contract

1. Keep `passed` required and boolean for ordinary stored consumers. Regrade's
   existing `allow_ungraded=True` compatibility remains.
2. If present, runner `exit_code` must be an integer (not bool) or null.
   Missing/null means “no explicit exit evidence” and remains compatible with
   manual/historical records.
3. A record with `passed: true` is invalid when:
   - `timed_out` is true;
   - runner `exit_code` is an explicit non-zero integer.
4. If `judge` is present it must remain producer-compatible:
   - inspect operational fields only when it is an object;
   - if `judge.exit_code` is present, require integer-not-bool or null;
   - if `judge.passed` is present, require boolean.
5. A record with `passed: true` is invalid when an explicit judge object says:
   - `judge.exit_code` is non-zero; or
   - `judge.passed` is false.
6. Do not require a judge object or its fields. Builtin/LLM/manual historical
   shapes that omit operational fields remain valid.
7. Do not reject `passed:false` merely because runner/judge evidence looks
   successful. This plan closes false green, not every possible false negative.
8. During `allow_ungraded=True`, validate present operational field types but
   defer contradiction checks until a boolean `passed` exists. Regrade keeps
   Plan 065 behavior.
9. Errors identify only stable record position and field names. Never echo
   task ID, answer/stdout/stderr, judge reason, secret values, or absolute path.
10. All result families inherit the check through `_validate_result_records`.
    IDs may still repeat across rounds/agents, not within one array.
11. Invalid results exit 2 before:
    - health/threshold output;
    - evidence freshness hashing;
    - baseline append/regression;
    - compare/regrade output mutation.
12. Valid live producer output remains accepted byte-for-byte on read. No
    required `schemaVersion`, normalization, or persisted rewrite.
13. Python 3.9 standard library only.

## Scope

**In scope**:

- `scripts/eval_run.py`: narrow operational-field validation inside or beside
  `_validate_result_records`.
- `tests/test_eval_run.py`: unit and all-consumer/family regressions.
- Seven READMEs, `SKILL.md`, and a compact replacement of the existing root
  eval invariant in `AGENTS.md`.
- Self-eval files only if `AGENTS.md` changes; refresh via honest offline
  regrade.
- Plan/index closeout evidence.

**Out of scope**:

- Live runner/judge execution logic (already correct).
- Regrade regex behavior (Plan 065).
- Redaction, usage metadata, generated root evidence, baseline-history schema,
  drift-fix transactionality, or Action/MCP surfaces.
- Recomputing or silently changing stored `passed`.
- Requiring operational fields on legacy/manual records.
- Rejecting explicit `passed:false` with apparently successful evidence.

## Commands

| Purpose | Command | Expected |
|---|---|---|
| Focused integrity tests | `PYTHONPATH=tests python3 -m unittest test_eval_run.StoredResultIntegrityTests -v` | pass |
| Full eval tests | `python3 -m unittest discover -s tests -p 'test_eval_run.py' -v` | pass |
| Full gate | `npm run check` with CI-supported npm | pass |
| Scan | gated baseline scan command from `AGENTS.md` | exit 0 |
| Drift | `python3 scripts/check_drift.py . --strict` | 100/A |
| Eval | current-evidence 40-task score command | 100/A |
| Docs | `python3 scripts/check_readme_sync.py` | seven aligned |
| Audit | npm 10.8.2, public registry, high level | zero high/critical |

## Git workflow

- Plan-only PR first.
- Implementation branch: `fix/068-reject-contradictory-eval-results`.
- Commit: `fix(eval): reject contradictory stored results`.
- Backward-compatible correctness/security patch.
- Merge only after all nine required contexts and zero unresolved threads;
  squash and delete branch.
- Separate green closeout PR afterward.

## Steps

### Step 1: Add one red score-gate tracer test

In `StoredResultIntegrityTests`, write a result with `passed:true` and runner
`exit_code:9`. Run `--score --fail-under 80 --baseline ... --save-baseline`.
Assert exit 2, safe `result error`, no health stdout/traceback, and no baseline.

**Pre-fix expected**: exit 0, 100/A, baseline written.

### Step 2: Implement narrow runner contradiction validation

Validate `exit_code` type when present. If a graded record says `passed:true`,
reject `timed_out:true` or explicit non-zero runner exit. Keep missing/null exit
and ungraded regrade inputs compatible.

Add cases for:

- non-zero runner;
- timeout;
- exit 0 pass;
- missing/null exit pass;
- bad exit types including bool;
- `passed:false` with non-zero/timeout remains valid.

### Step 3: Add judge contradiction validation

For a judge object, validate present `exit_code` and `passed` types. Reject a
top-level pass with explicit non-zero judge exit or judge rejection.

Keep absent judge, builtin judge without exit, judge exit 0/pass, and
top-level failure compatible.

### Step 4: Prove every family and consumer fails before side effects

Cover contradictory records under:

- top-level `tasks`;
- each `round_results` entry and legacy bare-round list;
- `agents.<name>.tasks`.

Exercise:

- score with threshold/evidence/baseline flags;
- stats;
- compare (no report output);
- regrade (no output mutation).

Errors must use stable position diagnostics; agent names/task IDs are not
echoed.

### Step 5: Document and refresh evidence

Update all public languages and `SKILL.md`: stored result validation rejects an
explicit pass that contradicts timeout or runner/judge failure before health or
side effects; omitted operational fields remain legacy-compatible.

Compact the current root eval bullet, keep `AGENTS.md <= 10240`, update an
objective self-eval task/answer, and offline regrade honestly if bytes change.

### Step 6: Review, gate, PR, closeout

Run all commands. Perform Standards/Spec and integrity-focused review. Open the
implementation PR, wait for nine green checks, merge and delete, then record
evidence in a separately green closeout PR.

## Test plan

- Runner non-zero, timeout, exit zero, missing/null, bad types.
- Judge non-zero, judge false, exit zero/pass, omitted fields, bad types.
- Ungraded regrade compatibility.
- `passed:false` compatibility.
- Tasks/rounds/bare-round/matrix families.
- Score/stats/compare/regrade and no-side-effect assertions.
- Error redaction/stable position.
- Existing valid producer, forged health, Plan 065, and evidence tests.

## Done criteria

- [ ] All four reproductions exit 2 instead of reporting 100/A.
- [ ] Manual/historical missing operational fields still pass validation.
- [ ] Valid live producer files remain accepted.
- [ ] Every result family and offline consumer inherits validation.
- [ ] No health, baseline, compare, or regrade side effect on invalid input.
- [ ] Safe diagnostics expose no record-controlled strings.
- [ ] Eval/full gates, scan, drift, self-eval, docs, audit pass.
- [ ] Implementation and closeout PRs each pass nine checks, merge, and delete
      branches.

## STOP conditions

Stop if:

- Correct behavior requires silently rewriting stored `passed`.
- Existing valid producer output contains `passed:true` with explicit failure.
- Manual compatibility would require making exit/judge fields mandatory.
- The fix needs a result schema version or changes health formulas.
- Errors would echo record-controlled values.
- Any required check is red/pending or a review thread remains unresolved.

## Maintenance notes

- Any future operational evidence field must be added to the same shared
  validator before health consumers can trust it.
- Live execution, regrade, and stored validation must keep one invariant:
  explicit operational failure can never become a pass.
- Root-generated evidence and drift-fix atomicity remain separate candidates,
  not follow-ups hidden inside this patch.
