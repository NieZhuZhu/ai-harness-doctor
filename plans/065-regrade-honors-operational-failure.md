# Plan 065: Make eval `--regrade` honor a stored record's operational-failure evidence

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md` unless a reviewer maintains the index separately.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 9acdafc..HEAD -- \
>   scripts/eval_run.py tests/test_eval_run.py \
>   plans/065-regrade-honors-operational-failure.md plans/README.md
> ```
>
> If any in-scope file changed, compare the "Current state" excerpt against the
> live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW (adds a fail-closed guard to one regex-regrade branch; records
  with `exit_code == 0`/absent keep their current recompute path, and the
  `command`/other-check branches already set `regraded: False` and are untouched)
- **Depends on**: Plan 038 (DONE — established that operational failure always
  fails a live run; this closes the same contract for the offline `--regrade`
  entry point)
- **Category**: correctness / eval integrity
- **Planned at**: commit `9acdafc`, 2026-07-18
- **Status**: TODO

## Why this matters

Plan 038 made operational failure authoritative for **live** eval runs:
`run_runner_record` (eval_run.py:1730-1799) grades a task only when
`proc.returncode == 0`; a runner that prints a matching answer then exits
non-zero (or times out) is recorded `passed: False`. The **offline `--regrade`**
path reopens exactly that hole. `regrade()` recomputes `passed` for a `regex`
check purely from the stored `stdout`, ignoring the record's own `exit_code`
and `timed_out` fields. A previously-captured record with `exit_code: 9,
stdout: "OK"` for a regex task `"OK"` is written back as `passed: True`, and a
subsequent `--score` on that file reports `Health score: 100/100 (grade A)`,
exit 0 — a false green on a run that never actually succeeded.

`--regrade` exists so an operator can fix an over-strict regex and re-derive
`passed` without paying to re-run the agents. That is legitimate; what is not
legitimate is silently flipping an **operationally failed** task (crash /
non-zero exit / timeout) to passing because its partial stdout happens to match.
This plan makes the regex-regrade branch fail closed on stored operational
failure, matching Plan 038's live-run contract.

## Mechanical reproduction (confirm the defect is live)

```bash
tmp=$(mktemp -d); cd "$tmp"
cat > tasks.json <<'JSON'
[{"id":"t1","prompt":"say OK","check":{"type":"regex","value":"OK"}}]
JSON
cat > results.json <<'JSON'
{"label":"demo","tasks":[{"id":"t1","passed":false,"timed_out":false,"duration_s":0.1,"exit_code":9,"stdout":"OK","answer":"OK","stderr":"boom","usage":{}}]}
JSON
python3 "$OLDPWD/scripts/eval_run.py" --tasks tasks.json --regrade results.json -o regraded.json >/dev/null 2>&1
python3 -c "import json;r=json.load(open('regraded.json'));print('passed after regrade =', r['tasks'][0]['passed'], '| exit_code =', r['tasks'][0]['exit_code'])"
python3 "$OLDPWD/scripts/eval_run.py" --score regraded.json --fail-under 80 >/dev/null 2>&1; echo "score exit = $?"
cd "$OLDPWD"; rm -rf "$tmp"
```

Expected on the unpatched tree: `passed after regrade = True | exit_code = 9`
and `score exit = 0` (false green). After this plan lands: `passed after regrade
= False` and `score exit` is non-zero (fails `--fail-under 80`).

## Current state

- `scripts/eval_run.py` — the `regrade()` loop (**eval_run.py:1931-1947**):

  ```python
      for record in results.get("tasks", []):
          task = task_map.get(record.get("id"))
          answer = extract_answer(record.get("stdout", ""))
          record["answer"] = answer
          if not task:
              record["regraded"] = False
              sanitize_result_record(record)
              continue
          check = task.get("check", {})
          if check.get("type") == "regex":
              record["passed"] = regex_passes(check.get("value", ""), answer)
              record["regraded"] = True
          elif check.get("type") == "command":
              record["regraded"] = False
          else:
              record["regraded"] = False
          sanitize_result_record(record)
  ```

  The `regex` branch never inspects `record.get("exit_code")` or
  `record.get("timed_out")`.
- The live-run contract to mirror is `run_runner_record`
  (**eval_run.py:1730-1799**): `if proc.returncode != 0: return
  sanitize_result_record(record)` (grading is skipped, `passed` stays `False`)
  and the `TimeoutExpired` branch returns `passed: False, timed_out: True`.
- `manual_protocol()` documents `exit_code` as an **optional** field on
  hand-authored records; a record with **no** `exit_code` and no
  `timed_out: true` must keep the current recompute behavior (the guard only
  fires on present, non-passing operational evidence).

**Repo conventions to match**:

- `sanitize_result_record(record)` is already called on every branch; keep it.
- Existing regrade tests live in `tests/test_eval_run.py`:
  - `test_regrade_flips_stored_false_to_true_after_regex_fix`
    (tests/test_eval_run.py:441) — the happy path that must stay green
    (its record has no failing `exit_code`).
  - `test_regrade_rejects_malformed_tasks_before_output_mutation`
    (tests/test_eval_run.py:203) — preflight behavior, unaffected.
- Any change to `scripts/*.py` ships with matching tests in the same commit.
- Python 3.9+ standard library only.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Eval tests | `python3 -m unittest tests.test_eval_run -v` | OK |
| Full Python suite | `python3 -m unittest discover -s tests` | OK |
| Node tests | `npm test` | fail 0 |
| Self drift | `python3 scripts/check_drift.py . --strict` | 100/100 grade A |
| Full local gate | `npm run check` | exit 0 |

## Scope

**In scope**:

- `scripts/eval_run.py` — guard the `regex` branch of `regrade()`.
- `tests/test_eval_run.py` — regression tests.

**Out of scope**:

- The `command` / other-check branches of `regrade()` — they already set
  `regraded: False` and do not recompute `passed`.
- The live-run path (`run_runner_record`, `_run_round`, `run_matrix`) — already
  correct per Plan 038.
- `compute_health` / `--score` internals — the fix corrects the stored `passed`
  upstream; health derives from it unchanged.
- Hand-authored records with no `exit_code`/`timed_out` (manual protocol) — must
  keep recomputing.
- `AGENTS.md` — byte-budgeted at 10,228/10,240; do not add prose there.

## Git workflow

- Branch: `git checkout -b fix/065-regrade-operational-failure`
- Conventional Commits, English (e.g. `fix(eval): fail regrade on stored operational failure`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Guard the regex-regrade branch

In `scripts/eval_run.py`, in `regrade()`, replace the `regex` branch so a stored
operational failure forces `passed=False` instead of recomputing from stdout:

```python
          if check.get("type") == "regex":
              if record.get("timed_out") or record.get("exit_code") not in (0, None):
                  # A crashed / timed-out / non-zero-exit runner never
                  # succeeded; regrading a stricter/looser regex must not flip
                  # its partial stdout to a pass (mirrors run_runner_record's
                  # Plan 038 contract for live runs).
                  record["passed"] = False
                  record["regraded"] = False
              else:
                  record["passed"] = regex_passes(check.get("value", ""), answer)
                  record["regraded"] = True
```

Rationale for the guard shape: `exit_code not in (0, None)` treats a present,
non-zero exit as failure while leaving `exit_code == 0` (success) and
`exit_code is None` (absent — e.g. a manual-protocol record, or the
FileNotFound/timeout records where `None` is paired with an already-`False`
`passed`) on the recompute path. `timed_out` truthy is always a failure.

**Verify**: run the reproduction snippet → `passed after regrade = False`,
`score exit` non-zero.

### Step 2: Regression tests

In `tests/test_eval_run.py`, add tests modeled on
`test_regrade_flips_stored_false_to_true_after_regex_fix`:

1. **Non-zero exit is not flipped**: a stored record `exit_code: 9,
   stdout: "OK", passed: false` with a regex task `"OK"` regrades to
   `passed: false, regraded: false`, and a subsequent `--score --fail-under 80`
   exits non-zero.
2. **Timeout is not flipped**: a stored record `timed_out: true, stdout: "OK"`
   regrades to `passed: false`.
3. **Happy path preserved (explicit)**: a stored record `exit_code: 0,
   stdout: "WRONG", passed: false` with a corrected regex that now matches
   `"WRONG"` regrades to `passed: true, regraded: true` (proves the guard does
   not over-block successful runs). The existing
   `test_regrade_flips_stored_false_to_true_after_regex_fix` may already cover a
   variant of this; keep it green and add the explicit `exit_code: 0` case if it
   is not already present.
4. **Absent exit_code preserved**: a record with **no** `exit_code` field and no
   `timed_out` still recomputes `passed` from stdout (manual-protocol
   compatibility).

**Verify**: `python3 -m unittest tests.test_eval_run -v 2>&1 | tail -3` → OK.

### Step 3: Full local verification

**Verify**:
- `python3 -m unittest discover -s tests` → OK
- `npm test` → fail 0
- `python3 scripts/check_drift.py . --strict` → 100/100 grade A
- `npm run check` → exit 0

## Test plan

Covered in Step 2: non-zero-exit not flipped, timeout not flipped, exit_code==0
happy path preserved, absent-exit_code manual record preserved. Structural
pattern: `test_regrade_flips_stored_false_to_true_after_regex_fix`
(tests/test_eval_run.py:441).

## Done criteria

- [ ] Reproduction snippet: `passed after regrade = False` and `score exit` non-zero.
- [ ] The four Step-2 cases exist and pass; `test_regrade_flips_stored_false_to_true_after_regex_fix` stays green.
- [ ] `python3 -m unittest discover -s tests` exits 0.
- [ ] `npm test` fail 0; `node --check bin/cli.js` exits 0.
- [ ] `python3 scripts/check_drift.py . --strict` → 100/100 grade A.
- [ ] `npm run check` exits 0.
- [ ] `git status` shows only in-scope files modified.
- [ ] `plans/README.md` status row updated.

## STOP conditions

- The `regrade()` excerpt at eval_run.py:1931-1947 does not match live code.
- An existing test asserts that a record with a non-zero `exit_code` or
  `timed_out: true` regrades to `passed: true` (would mean the current behavior
  is intended — investigate before changing).
- Guarding the branch breaks `test_regrade_flips_stored_false_to_true_after_regex_fix`
  (means that test's fixture carries a failing exit_code — inspect its record;
  if so, the test encodes the bug and the fix is to correct the fixture's
  `exit_code` to 0, reported as part of the change).
- Any AGENTS.md edit would be required.

## Maintenance notes

- This closes the last known offline entry point in the Plan 030/033/038/041
  eval-integrity family (validate-before-run, health-from-validated-records,
  fail-on-operational-failure, fail-closed history). If a new offline consumer
  recomputes `passed` from stored output, it must apply the same
  operational-failure guard.
- A reviewer should confirm the guard fires only on **present, non-passing**
  operational evidence, so hand-authored manual-protocol records (no
  `exit_code`) are unaffected.
- Independent of Plans 063/064 (report-surface hardening); land as its own PR.
