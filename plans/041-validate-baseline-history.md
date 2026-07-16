# Plan 041: Validate the eval baseline-history store before trend/regression reads

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md`.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat a5c6195..HEAD -- \
>   scripts/eval_run.py tests/test_eval_run.py \
>   README.md README.zh-CN.md README.ja.md SKILL.md \
>   AGENTS.md benchmark/self-eval/results-after-graded.json
> ```
>
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against live code before proceeding. Refresh the
> plan against current `main`; if the baseline-history schema, the offline
> `result error` contract, or the regression/trend logic changed materially,
> treat that as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: Plan 033 (DONE)
- **Category**: correctness
- **Planned at**: commit `a5c6195`, 2026-07-16
- **Implementation**: DONE — PR #201 (plan) / PR #202 (impl), squash-merged to
  `main` as `e25d421`; all nine required contexts green.

## Implementation progress

- Added `validate_baseline_store(data, location)` raising `ResultFileError` on
  structural corruption (non-list/non-`baselines` top level, non-dict entry, or
  non-numeric non-null `score`); `load_baseline_store` routes decodable content
  through it while missing/undecodable files still yield an empty history.
- `--trend`, `--check-regression`, and `--save-baseline` now fail closed with
  `result error` / exit 2 and never append onto a corrupt store; existing
  `main()` `ResultFileError` handling suppresses the traceback.
- Hardened `detect_regression`/`render_trend` via a shared `_snapshot_score`
  helper so absent/`null`/wrong-typed scores are non-comparable rather than
  crashes, and bool is excluded from numeric scores.
- New `BaselineHistoryValidationTests`; existing `BaselineTests` unchanged.
  Local gate: full Python + 26 Node tests, self scan rc 0, strict drift 100/A,
  evidence-bound self-eval 34/34. Final PR/CI/merge evidence pending.

## Why this matters

Plan 033 made every offline eval result consumer fail closed: `--score`,
`--stats`, `--compare`, and `--regrade` validate their stored records, derive
health from validated data, and exit `2` with a concise `result error` before
reading or writing anything, never leaking a Python traceback. Plan 033
explicitly left one consumer family out of scope: the eval **baseline-history
store** used by `--baseline` + `--save-baseline` (append), `--check-regression`
(gate), and `--trend` (render).

That deferred store is still trusted blindly. `load_baseline_store()` returns
whatever JSON list it finds, and the regression/trend code then calls
`entry.get(...)` on each item and does numeric comparisons on `entry["score"]`
without checking types. A history file that is a list of non-dict entries (or
whose top level is a scalar) therefore crashes `--trend` and
`--check-regression` with an uncaught `AttributeError` and a raw traceback
(exit 1) instead of the project's clean `result error` contract. A history
whose `score` is a non-numeric value is silently ignored, which is acceptable
for a merely incomplete snapshot but is indistinguishable from a corrupted one.

A premium diagnostic tool should treat its own persisted efficacy history with
the same fail-closed rigor as every other stored artifact: structural
corruption is a deterministic `result error`, and regression/trend math runs
only over validated numeric snapshots.

## Mechanical reproduction

Against `main@a5c6195`:

```bash
# A history whose entries are not objects.
printf '[1, 2, "x"]' > /tmp/bad-history.json
python3 scripts/eval_run.py --trend /tmp/bad-history.json ; echo "trend rc=$?"

# A history used as a regression baseline for an otherwise valid result.
printf '{"label":"cur","tasks":[{"id":"x","passed":true,"timed_out":false}]}' > /tmp/res.json
python3 scripts/eval_run.py --score /tmp/res.json \
  --baseline /tmp/bad-history.json --check-regression ; echo "regress rc=$?"
```

Observed on `a5c6195` (both commands):

```
AttributeError: 'int' object has no attribute 'get'
... rc=1
```

`[{"label":"a","score":"oops"}]` and a top-level scalar (`42`) instead
silently render/return success (rc 0), so a corrupted score is treated exactly
like an absent one.

Expected after this plan:

- structurally malformed history (non-list top level, or any non-dict entry)
  exits `2` with a concise `result error` and no traceback, for `--trend`,
  `--check-regression`, and `--save-baseline`;
- regression/trend math consumes only validated numeric snapshots;
- valid histories (including legitimately partial snapshots with an absent
  score) render and gate exactly as before.

## Current state

### The history loader trusts any list

`scripts/eval_run.py:2152-2167`:

```python
def load_baseline_store(path):
    """Load a baseline history file into a list; empty list if absent/invalid."""
    p = Path(path)
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("baselines"), list):
        return data["baselines"]
    return []
```

A JSON-decode failure or an unrecognized top-level shape already fails safe
(empty history). The gap is a *decodable* list whose **entries** are not the
snapshot objects the readers assume.

### Readers assume every entry is a dict with a numeric score

`scripts/eval_run.py:2189-2210` (`detect_regression`) filters with
`e.get("score")` and then computes `current_score - prev_score`; `render_trend`
(`scripts/eval_run.py:2222-2252`) iterates `for i, e in enumerate(store, 1)`
and calls `e.get(...)` on every entry. A non-dict entry raises
`AttributeError`; there is no `result error` path and no traceback suppression.

### The offline contract this should match

Plan 033 established `ResultFileError` → `main()` prints `result error: ...`
and returns `2`. `scripts/eval_run.py` already routes that exception class in
`main()`:

```python
except ResultFileError as exc:
    print(f"result error: {exc}", file=sys.stderr)
    return 2
```

The `--trend` branch and `apply_baseline()` currently never raise it.

### Append path

`apply_baseline()` (`scripts/eval_run.py:2254-2283`) loads the store, optionally
runs `detect_regression`, then optionally appends and re-saves. If the store is
malformed, `--check-regression` crashes before the append, and `--save-baseline`
would otherwise append a valid entry onto a corrupt list — silently persisting a
half-valid history. Both must fail closed on structural corruption.

## Target contract

1. Add a single validator (e.g. `validate_baseline_store(data, location)`)
   that accepts already-decoded JSON and returns the list of snapshot dicts, or
   raises `ResultFileError` with a concise, location-tagged message.
2. Structural corruption raises `ResultFileError`:
   - top level is neither a list nor `{"baselines": [...]}`;
   - any entry is not a JSON object;
   - a present `score` is neither a number nor `null`;
   - a present `timestamp`/`label`/`grade` is a non-string when present
     (only if cheap and non-breaking — otherwise leave string-shape lenient and
     document it).
3. A **missing** score (absent key or explicit `null`) stays a valid,
   non-comparable snapshot — this is how partial/among-first snapshots already
   behave in `render_trend`. Do not turn absence into an error.
4. `--trend`, `--check-regression`, and `--save-baseline` all route through the
   validator before any read, comparison, append, or write.
5. On `ResultFileError`, every one of those commands exits `2` via the existing
   `main()` handler with `result error: ...` on stderr and no traceback; no file
   is written and no snapshot is appended.
6. `detect_regression`/`render_trend` operate only on validated snapshots and
   never call `.get(...)` on a non-dict or do arithmetic on a non-number.
7. Diagnostics never echo full file contents; include only the location and a
   short structural reason (index/kind), consistent with Plan 033/030 wording.
8. The append-only history schema is unchanged. Every currently valid history
   file — including empty, single-entry, partial-score, and
   `{"baselines": [...]}` shapes — behaves byte-for-byte as before.
9. `save_baseline_store` output shape and `make_baseline_entry` fields are
   unchanged.
10. No new runtime dependency; Python 3.9 standard library only.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Eval tests | `python3 -m unittest discover -s tests -p 'test_eval_run.py' -v` | exit 0 |
| Full quality gate | `npm run check` | all lint + Python + Node tests pass |
| CLI syntax/help | `node --check bin/cli.js && node bin/cli.js help` | exit 0 |
| Self scan | `python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0, grade A |
| Evidence-bound eval | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0 |
| Package contents | `npm pack --dry-run --json` | changed shipped script/docs included |
| README synchronization | `python3 scripts/check_readme_sync.py` | exit 0 |
| Adapter synchronization | `python3 scripts/gen_adapters.py --check` | exit 0 |

## Scope

**In scope**:

- `scripts/eval_run.py`
- `tests/test_eval_run.py`
- `README.md`
- `README.zh-CN.md`
- `README.ja.md`
- `SKILL.md`
- `AGENTS.md` only if a durable invariant line is warranted
- `benchmark/self-eval/tasks.json` / `results-after.json` /
  `results-after-graded.json` / `README.md` only if a new objective self-eval
  task is added for the invariant
- `plans/041-validate-baseline-history.md`
- `plans/README.md`

**Out of scope**:

- changing the baseline-history JSON schema or `make_baseline_entry` fields;
- centralizing a broad result-JSON validator across all consumers (Plan 033
  scoped record validation deliberately);
- changing `--score`/`--stats`/`--compare`/`--regrade` record validation;
- changing regression threshold semantics, exit code `6`, or trend rendering
  columns for valid input;
- treating an absent/`null` score as an error;
- discarding a whole history because one entry is malformed beyond raising the
  error (fail closed, do not silently drop-and-continue).

## Git workflow

- Start from latest `main` after the plan PR merges:
  `fix/041-validate-baseline-history`.
- Keep the fix in one implementation PR.
- Use Conventional Commits in English, for example:
  `fix(eval): validate baseline history before reads`.
- Do not push directly to `main`.
- Do not merge until all nine required contexts are green: `drift`, `lint`,
  `node (16)`, `node (20)`, `node (22)`, `self-test`, `unittest (3.9)`,
  `unittest (3.10)`, and `unittest (3.12)`.
- Admin bypass is allowed only for the sole-maintainer approval deadlock after
  required checks are green and every discussion is resolved.

## Steps

### Step 1: Characterize the crash and the silent-skip

Add regression tests that, against the current code, prove:

1. a non-dict-entry history makes `--trend` exit 1 with a traceback (assert the
   post-fix behavior: exit 2, `result error`, no `Traceback`);
2. the same history under `--score ... --check-regression` exits 1 (post-fix:
   exit 2, `result error`, no append, no traceback);
3. a top-level scalar history is rejected (post-fix: exit 2);
4. a valid history with one legitimately partial (absent-score) snapshot still
   renders/gates exactly as today.

**Verify**:

```bash
python3 -m unittest discover -s tests -p 'test_eval_run.py' -v
```

Expected before implementation: the new fail-closed assertions fail. Expected
after: they pass.

### Step 2: Add the validator and route all three consumers through it

Introduce `validate_baseline_store(data, location)` raising `ResultFileError`
on structural corruption and returning the validated snapshot list. Have
`load_baseline_store` (or its callers `trend_report` and `apply_baseline`) call
it so that `--trend`, `--check-regression`, and `--save-baseline` all fail
closed before any read/compare/append/write.

Keep `load_baseline_store`'s missing-file and JSON-decode-failure behavior
(empty history) intact for absent/unreadable files; only *decodable but
structurally invalid* content becomes a `result error`.

**Verify**:

```bash
python3 -m unittest discover -s tests -p 'test_eval_run.py' -v
```

Expected: crash/silent-skip tests pass; existing baseline/trend tests
(`test_detect_regression_unit`, `test_save_baseline_appends_and_trend_renders`,
`test_check_regression_gate_exits_6`) still pass unchanged.

### Step 3: Harden the derivation helpers

Make `detect_regression` and `render_trend` consume only validated snapshots.
They must never call `.get(...)` on a non-dict or do arithmetic on a non-number
even if reached directly in a unit test; the validator is the primary gate but
the helpers stay defensive for numeric filtering.

**Verify**:

```bash
python3 -m unittest discover -s tests -p 'test_eval_run.py' -v
```

Expected: helper unit tests pass, including a mixed store of numeric and
absent-score snapshots.

### Step 4: Synchronize public docs

Update the "Baseline, trend & regression" passage in all three READMEs and
`SKILL.md`: the history store is validated before trend/regression/append,
structural corruption exits `2` with a `result error` (no traceback), and a
partial snapshot with no score remains a valid non-comparable entry. Keep
fenced blocks, tables, and links synchronized.

**Verify**:

```bash
python3 scripts/check_readme_sync.py
python3 scripts/gen_adapters.py --check
```

Expected: both exit 0.

### Step 5: Optional invariant + evidence refresh

If it stays under budget, add one concise `AGENTS.md` invariant (baseline
history is validated like every other stored result; malformed history exits
`result error`, valid partial snapshots are non-comparable). Only then refresh
the evidence-bound self-eval through the documented regrade workflow and keep
Grade A. If no AGENTS/task change is needed, leave the eval evidence untouched.

**Verify**:

```bash
wc -c AGENTS.md
python3 scripts/eval_run.py \
  --score benchmark/self-eval/results-after-graded.json \
  --tasks benchmark/self-eval/tasks.json \
  --workdir . \
  --evidence AGENTS.md \
  --require-current-evidence \
  --fail-under 80
python3 scripts/check_drift.py . --strict
```

Expected: AGENTS below 12 KiB, eval current at Grade A, strict drift Grade A.

### Step 6: Full gate, review, and PR

Run every command in "Commands you will need". Review the diff on two axes:

- standards: stdlib-only, matching tests, trilingual doc parity, no traceback
  leakage;
- spec: structural corruption → exit 2 `result error`; valid/partial histories
  unchanged; schema untouched; no broad validator scope creep.

Open one implementation PR, wait for all nine contexts, resolve discussions,
squash merge, and record PR/head/check/merge evidence in this plan and the
index. This is a backward-compatible **patch** unless a STOP condition forces a
schema change.

## Test plan

- New tests:
  - non-dict-entry history: `--trend` exit 2, `result error`, no traceback;
  - non-dict-entry history: `--check-regression` exit 2, no append, no
    traceback;
  - top-level scalar history rejected;
  - `{"baselines": [...]}` valid shape still accepted;
  - valid history with an absent-score snapshot renders/gates unchanged;
  - `detect_regression`/`render_trend` over a mixed numeric/absent store.
- Preserved tests: existing baseline unit + integration tests unchanged.

## Done criteria

- [ ] Malformed baseline history exits `2` with `result error` (no traceback)
      for `--trend`, `--check-regression`, and `--save-baseline`.
- [ ] Regression/trend math runs only over validated numeric snapshots.
- [ ] Absent/`null` scores remain valid non-comparable snapshots.
- [ ] `{"baselines": [...]}` and list histories both still load.
- [ ] The append-only schema and `make_baseline_entry` fields are unchanged.
- [ ] Diagnostics never echo full history contents.
- [ ] Behavior changes have tests in the same PR.
- [ ] Trilingual READMEs and `SKILL.md` synchronized.
- [ ] `npm run check` passes.
- [ ] Self scan exits 0; strict drift is 100/100 Grade A.
- [ ] Evidence-bound self-eval is current and Grade A.
- [ ] `AGENTS.md` stays below 12 KiB (if edited).
- [ ] No runtime dependency added; Python 3.9 / Node 16 remain supported.
- [ ] Implementation PR has all nine required contexts green and is merged.
- [ ] Plan/index contain final PR, CI, and merge evidence.

## STOP conditions

Stop and report instead of improvising if:

- fixing the crash cannot be done without changing the persisted history
  schema;
- a valid existing history file would change behavior under the new validator;
- correct handling requires rejecting absent/`null` scores;
- the fix would require a broad cross-consumer validator rather than the one
  deferred history path;
- `AGENTS.md` cannot stay under 12 KiB after any consolidation;
- any required CI context is red/pending or a discussion is unresolved.

## Maintenance notes

- Baseline history is the last offline result consumer; keep its validation and
  the Plan 033 record validation consistent in tone and exit contract.
- Absent score vs corrupt entry are different: the former is a legitimate
  partial snapshot, the latter is structural corruption. Preserve that split.
- If the history schema ever gains fields, extend the validator and
  `make_baseline_entry` together, and keep old snapshots loadable.
