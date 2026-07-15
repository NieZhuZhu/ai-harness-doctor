# Plan 032: Fail multi-repo CI when any listed repository was not scanned

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 704806e..HEAD -- scripts/scan.py tests/test_scan.py tests/test_cli.py scripts/pr_review.py tests/test_pr_review.py README.md README.zh-CN.md README.ja.md SKILL.md EXTERNAL_VALIDATION.md AGENTS.md benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json benchmark/self-eval/results-after-graded.json benchmark/self-eval/README.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: correctness / direction / CI / tests / docs
- **Planned at**: commit `704806e`, 2026-07-16

## Why this matters

`scan --repos-file` is the project's organization-wide gate. It intentionally
continues past one bad repository so healthy repositories still produce
reports, but the final exit code considers only findings from successfully
scanned roots. A typo, missing checkout, inaccessible directory, or list made
entirely of bad paths can therefore yield `error_count > 0` and exit `0`, even
with every `--fail-on-*` gate enabled.

That is a false green: CI proves neither that the listed repositories are
healthy nor even that one was scanned. Batch operational coverage errors must
be visible in JSON/Markdown and produce a dedicated non-zero exit after all
reachable repositories have still been scanned.

## Current state

- `scripts/scan.py:2061-2106` records per-repository operational errors and an
  aggregate count:

  ```python
  if not root.is_dir():
      repos.append({
          "path": raw_path,
          "resolved": str(root),
          "error": f"not a directory: {raw_path}",
      })
      continue
  ...
  summary = {
      "repo_count": len(repos),
      "error_count": len(repos) - len(ok),
      "aggregate": aggregate,
  }
  ```

- `_run_repos_file()` at `scripts/scan.py:2142-2154` filters to successful
  reports and initializes success:

  ```python
  ok_reports = [r["report"] for r in repos if "error" not in r]
  exit_code = 0
  if args.fail_on_security and ...:
      exit_code = 2
  elif args.fail_on_gaps and ...:
      exit_code = 3
  ...
  ```

  It never consults `summary["error_count"]`.

- The audit supplied a `repos.txt` containing one nonexistent path and ran:

  ```bash
  python3 scripts/scan.py --repos-file repos.txt --json \
    --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts
  ```

  It exited `0` while JSON reported:

  ```json
  {
    "summary": {"repo_count": 1, "error_count": 1},
    "repos": [{"error": "not a directory: ..."}]
  }
  ```

- `tests/test_scan.py:1741-1779` explicitly expects exit 0 for mixed
  success/error batches in JSON and Markdown. No test covers all-error input or
  an operational-failure exit contract.

- README says all four gates consider every scanned repo and calls the mode
  "CI-gateable across a whole org" (`README.md:344`), but does not state that
  unscanned entries currently stay green.

- Batch reports intentionally retain the raw list label and a resolved path for
  local JSON. PR-review normalizes batch findings summary-only and must not
  acquire cross-repository inline comments.

## Target contract

1. Scan every reachable repository even when earlier entries fail.
2. Any per-repository operational error makes the final command non-zero in
   both JSON and Markdown modes, independent of `--fail-on-*`.
3. Use one dedicated batch operational exit code that does not collide with
   existing scan gates `2` (security), `3` (gaps), `4` (semantic), or `7`
   (conflicts). Prefer `8` unless repository conventions reveal an existing
   public use.
4. Gate precedence remains deterministic:
   - security `2`;
   - gaps `3`;
   - semantic `4`;
   - conflicts `7`;
   - otherwise batch operational errors `8`.
   This preserves the most actionable finding code while never returning 0.
5. The JSON/report schema stays additive/backward-compatible. Existing
   `summary.error_count` and per-entry `error` are the source of truth; a short
   top-level `ok`/`status` may be added only if justified and documented.
6. Diagnostics and public PR summaries must not expose newly derived absolute
   host paths. Do not broaden the existing `resolved` field or copy it into
   review comments.
7. A missing/unreadable/empty repos-file keeps current exit 1 behavior.
8. One bad path plus valid repos still emits all valid reports before returning
   non-zero.
9. Zero successfully scanned repositories is an explicit operational failure,
   not an empty healthy aggregate.
10. Single-repo and monorepo behavior are unchanged.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused scan tests | `python3 -m unittest discover -s tests -p 'test_scan.py' -v` | all pass |
| PR review tests | `python3 -m unittest discover -s tests -p 'test_pr_review.py' -v` | all pass |
| CLI tests | `python3 -m unittest discover -s tests -p 'test_cli.py' -v` | all pass |
| Python lint | `ruff check scripts/scan.py tests/test_scan.py` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | `OK` |
| Full gate | `npm run check` | exit 0 |
| Self eval | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0 |
| Self scan | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0, grade A |

## Scope

**In scope**:

- `scripts/scan.py`
- `tests/test_scan.py`
- `tests/test_cli.py` for packaged forwarding
- `scripts/pr_review.py` / `tests/test_pr_review.py` only if an additive batch
  status needs review rendering changes
- synchronized `README.md`, `README.zh-CN.md`, `README.ja.md`
- `SKILL.md`
- `EXTERNAL_VALIDATION.md` for one real multi-repo list validation
- `benchmark/self-eval/` only if the maintenance contract changes
- `plans/README.md`

**Out of scope**:

- Stopping at the first failed repository.
- Adding remote clone/discovery or GitHub organization API integration.
- Combining independent-repository baselines.
- Enabling package expansion inside each batch repository.
- Cross-repository inline PR comments.
- Removing `resolved` from local JSON (a breaking schema change).
- Changing single-repo or monorepo exit codes.
- Adding retry/network behavior.
- Updating `AGENTS.md`; the batch completion PR owns final durable invariants.

## Git workflow

- Branch: `fix/batch-scan-operational-errors`
- Commit: `fix(scan): fail on unscanned batch repositories`
- One focused correctness PR.
- Do not push directly to `main`.
- Wait for all nine required contexts, then squash-merge/delete the branch.
- Patch-level because the current success exit is a false-green bug. If a
  documented consumer depends on exit 0 with `error_count > 0`, stop and assess
  compatibility rather than adding an opt-out silently.

## Steps

### Step 1: Characterize mixed and all-error batches

Add focused CLI tests for:

- one valid clean repo + one nonexistent repo;
- all nonexistent repos;
- one unreadable/non-directory entry where portable;
- errors plus a valid repo with a security/gap/semantic/conflict finding;
- JSON and Markdown output;
- no report-file behavior.

Assert all valid repo reports are present even when the final exit is non-zero.
Assert the existing higher-priority finding exits win over operational exit 8.

**Verify**: the operational tests fail against `704806e` because exit is 0.

### Step 2: Centralize batch exit selection

Add a small pure helper that takes `summary`/reports/options and returns the
documented exit code. Keep current finding precedence and append operational
failure only when no higher-priority gate fires.

Avoid parallel scattered `if` logic in CLI/JSON/Markdown paths. Define the
batch operational code as a named constant and include it in help/docs.

**Verify**: pure precedence table passes for clean, each finding family,
operational-only, and mixed states.

### Step 3: Apply fail-closed behavior after complete scanning

Call the selector only after `scan_repos_file()` has processed every entry.
Render the same payload/report regardless of exit code, then return the
selected status.

Add a concise stderr or Markdown summary line for operational failure without
duplicating absolute resolved paths. JSON already has structured error entries.

**Verify**: all-error and mixed-error batches emit complete reports and exit 8;
finding precedence cases return 2/3/4/7.

### Step 4: Preserve review and forwarding safety

Run batch JSON through `ai-harness-doctor review` dry-run. Confirm:

- error entries remain summary-only;
- `resolved` absolute paths are not rendered into the review;
- no inline comment is attempted for an unrelated repository;
- the public Node CLI forwards exit 8 unchanged.

Modify `pr_review.py` only if the current summary omits operational error
context or misclassifies the report; otherwise add tests and leave it untouched.

**Verify**: focused PR-review and CLI tests pass.

### Step 5: Document and validate on a real local repo list

Update trilingual docs and `SKILL.md`: batch mode is best-effort in coverage
(scans all reachable repos) but fail-closed in final status; any unscanned entry
returns exit 8 unless a higher-priority finding exit applies.

Create an isolated repos list containing two clean real public checkouts already
used in `EXTERNAL_VALIDATION.md` plus one deliberately missing local path. Run
the dev checkout read-only, verify both real reports complete and final exit is
8, and record repo commits, list shape, results, and clean worktree hashes. Do
not clone or mutate an external repo solely to satisfy the record if suitable
existing checkouts are unavailable; use deterministic local fixtures and state
that boundary instead.

Refresh self-eval only if the maintenance answer changes.

**Verify**: docs sync, focused/full tests, self-eval, scan, and strict drift.

## Test plan

- Pure batch exit precedence.
- Mixed valid/error and all-error lists.
- Every fail-on family combined with operational errors.
- JSON/Markdown output parity.
- Node CLI exit propagation.
- PR-review summary path sanitization.
- Existing repos-file reports, no-report-file, and single/monorepo tests.

## Done criteria

- [ ] Any unscanned listed repository prevents exit 0.
- [ ] All reachable repositories are still scanned and rendered.
- [ ] Operational-only failure exits with documented code 8.
- [ ] Existing finding exits 2/3/4/7 retain precedence.
- [ ] JSON schema remains compatible and `error_count` stays authoritative.
- [ ] PR review does not leak `resolved` paths or create cross-repo inline comments.
- [ ] Single-repo and monorepo behavior is unchanged.
- [ ] Public CLI forwards the new exit correctly.
- [ ] Real/local multi-repo validation is recorded.
- [ ] Trilingual docs and `SKILL.md` are current.
- [ ] Full local and nine required CI gates pass.

## STOP conditions

Stop and report back if:

- Exit code 8 is already used by a public scan/eval/drift contract.
- A documented production consumer intentionally treats unscanned entries as
  success.
- Complete reporting cannot be preserved before returning non-zero.
- Safe output requires removing or renaming existing JSON fields.
- The fix requires remote cloning/authentication or org API credentials.
- Verification fails twice after a reasonable scoped fix.

## Maintenance notes

- Batch success means coverage plus findings, not just no findings among the
  subset that happened to be reachable.
- New per-repo operational error types must contribute to `error_count` and the
  shared exit selector.
- Keep independent repositories summary-only in PR review; one PR diff cannot
  safely host their inline findings.
