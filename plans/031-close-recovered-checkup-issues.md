# Plan 031: Close the weekly harness issue when the repository recovers

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 704806e..HEAD -- assets/guard/harness-checkup.yml .github/workflows/harness-checkup.yml tests/test_action_metadata.py tests/test_cli.py README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json benchmark/self-eval/results-after-graded.json benchmark/self-eval/README.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: correctness / GitHub operations / DX / tests / docs
- **Planned at**: commit `704806e`, 2026-07-16

## Why this matters

The GitHub weekly checkup models an active incident with one deduplicated issue
named `🩺 Harness checkup: issues detected`. It creates the issue or appends a
fresh report while scan/drift fail, but a healthy later run skips the entire
issue step. The issue therefore remains open after the repository is repaired,
making the public issue tracker and maintainer signal stale.

The alert lifecycle must be symmetric: unhealthy runs open/update exactly one
owned issue; the first healthy run comments with recovery evidence and closes
that exact open issue; later healthy runs are no-ops. Shipped and self-dogfood
workflows must use the same contract.

## Current state

- `assets/guard/harness-checkup.yml:70-85` runs issue management only on
  failure:

  ```yaml
  - name: Create or update harness issue
    if: steps.drift.outputs.status != '0'
    ...
    if [ -n "$issue_number" ]; then
      gh issue comment "$issue_number" --body "$body"
    else
      gh issue create --title "$TITLE" --body "$body"
    fi
    exit "${{ steps.drift.outputs.status }}"
  ```

  Because the step is skipped on `status == 0`, it cannot see or close a prior
  issue. The final explicit exit also makes issue delivery responsible for job
  failure rather than a dedicated status step.

- The repository adaptation repeats the same one-way state machine at
  `.github/workflows/harness-checkup.yml:74-88`, except scheduled checks stay
  green and use the issue as their signal.

- The fixed title is already a strong ownership boundary. Both workflows query
  only open issues whose title equals `TITLE`; no label or issue body parsing is
  needed.

- `tests/test_action_metadata.py:142-162` and
  `tests/test_cli.py:710-753` assert that the workflow/title exists, but do not
  cover open/update/recover/no-op lifecycle behavior or parity between shipped
  and self workflows.

- Public docs promise a "weekly checkup + deduped issue"
  (`README.md:183`, `README.md:286`) but never state how recovery is represented.

- Live repository read-back found no current issue with this title and the one
  recorded scheduled run is healthy. This plan validates the template state
  machine; it does not manufacture a production incident.

## Target contract

1. One issue-management step runs on `always()` after the report/status exists,
   for both healthy and unhealthy runs.
2. It queries open issues by exact title and narrows with exact equality in
   `jq`; never close similarly named or unrelated issues.
3. Unhealthy run:
   - comment the current report on the existing exact issue, or
   - create one exact issue if none exists;
   - never create duplicates;
   - preserve the original checkup status for the shipped workflow.
4. Healthy recovery:
   - if the exact issue is open, add one concise recovery comment with the
     workflow run URL/commit and close it;
   - if none is open, do nothing;
   - repeated healthy runs remain no-ops.
5. Issue API failure stays visible. Do not add `|| true`; the weekly signal must
   not silently disappear.
6. The shipped workflow continues to fail when scan/drift fails. The repository
   self-checkup retains its documented non-failing scheduled policy.
7. Report artifacts remain uploaded on every run.
8. Permissions stay least-privilege (`issues: write`, `contents: read`).
9. No third-party issue Action or runtime dependency is added.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Metadata tests | `python3 -m unittest discover -s tests -p 'test_action_metadata.py' -v` | all pass |
| Installer tests | `python3 -m unittest discover -s tests -p 'test_cli.py' -v` | all pass |
| Workflow lint | `actionlint assets/guard/harness-checkup.yml .github/workflows/harness-checkup.yml` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | `OK` |
| Full gate | `npm run check` | exit 0 |
| Self eval | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0 |
| Self scan | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0, grade A |

## Scope

**In scope**:

- `assets/guard/harness-checkup.yml`
- `.github/workflows/harness-checkup.yml`
- `tests/test_action_metadata.py`
- `tests/test_cli.py`
- synchronized `README.md`, `README.zh-CN.md`, `README.ja.md`
- `SKILL.md`
- `benchmark/self-eval/` only if the maintenance answer changes
- `plans/README.md`

**Out of scope**:

- Changing scan/drift detection or exit codes.
- Adding labels, assignees, projects, discussions, or notifications.
- Closing arbitrary stale issues.
- Changing the GitLab/Codebase artifact-only checkups.
- Changing PR-review comments or Marketplace reminder lifecycle.
- Switching shipped guards from `@latest` in this plan.
- Changing scheduled-job failure policy beyond preserving current shipped/self
  behavior.
- Updating `AGENTS.md`; the batch completion PR owns final durable invariants.

## Git workflow

- Branch: `fix/checkup-issue-recovery`
- Commit: `fix(guard): close recovered checkup issues`
- One focused GitHub-operations bugfix PR.
- Do not push directly to `main`.
- Run actionlint and all repository gates, wait for nine required contexts,
  then squash-merge/delete the branch.
- Patch-level unless the current shipped failure policy cannot be preserved (a
  STOP condition).

## Steps

### Step 1: Add lifecycle contract tests before changing YAML

Extract or add a stdlib-only test helper that models issue decisions from:

- numeric/string check status;
- zero/one exact open issue;
- unrelated open issues.

Cover:

- fail + none → create;
- fail + exact → comment;
- pass + exact → recovery comment then close;
- pass + none → no-op;
- unrelated titles untouched;
- repeated pass after close → no-op.

Add static workflow assertions that both workflow copies run issue management
on `always()`, use exact-title filtering, contain `gh issue close`, preserve
report upload, and contain no `|| true`.

**Verify**: new workflow assertions fail on `704806e` because no close path
exists.

### Step 2: Implement one symmetric issue-management step

In the shipped template, replace the failure-only step with an `if: always()`
step. Pass the status, report path, run URL, and commit through `env`; do not
interpolate untrusted expressions into shell script text.

Use one exact-title lookup. For failure, update/create. For success, comment and
close only when the exact open issue exists.

Keep the final non-zero checkup status in a separate explicit step (or an
equally clear mechanism) so a successful issue API call cannot mask scan/drift
failure and a recovery close cannot fail the checkup.

**Verify**: actionlint and lifecycle/static tests pass.

### Step 3: Mirror the state machine in self-dogfood

Adapt `.github/workflows/harness-checkup.yml` to the same issue lifecycle while
retaining local `node bin/cli.js`, Python setup, committed scan baseline, and
non-failing scheduled-job policy.

Do not copy the shipped `npx` execution path into self-dogfood. The issue
management shell should otherwise stay structurally aligned so tests can detect
future divergence.

**Verify**: metadata tests prove both workflows contain the same exact title,
lookup, recovery comment, and close operation; self workflow still has no final
status failure step.

### Step 4: Verify an installed consumer receives the recovery lifecycle

Extend the isolated-HOME guard installer test. After `guard --apply`, inspect
the installed checkup workflow and assert the recovery contract. Preserve
idempotency and no real GitHub calls.

No test may write to real user config or issue APIs.

**Verify**: focused CLI installer tests pass.

### Step 5: Document operational semantics

Update the three READMEs and `SKILL.md`: one exact issue tracks active weekly
failure; repeated failures append evidence; the first healthy run closes it;
unrelated issues are never touched. Clarify shipped checkup remains a failing
scheduled signal while this repository's adapted copy remains non-failing and
uses issue state as signal.

Refresh self-eval only if its maintenance answer needs the new lifecycle.

**Verify**: docs sync, full gate, self-eval, scan, strict drift, and actionlint.

## Test plan

- Pure fail/update/recover/no-op decision table.
- Exact-title ownership boundary.
- Static shipped/self workflow parity.
- Installed consumer template assertions under isolated HOME.
- actionlint on both YAML files.
- Existing provider, permissions, artifact, baseline, and public-CLI tests.

## Done criteria

- [ ] An active exact checkup issue is closed on the first healthy run.
- [ ] Recovery adds a concise evidence comment before close.
- [ ] Repeated healthy runs do nothing.
- [ ] Repeated failures update rather than duplicate.
- [ ] Unrelated issues are never touched.
- [ ] Shipped workflow failure semantics are preserved.
- [ ] Self-dogfood remains non-failing while issue state is truthful.
- [ ] Shipped and self workflows stay structurally synchronized.
- [ ] Installer emits the updated workflow safely.
- [ ] Trilingual docs/SKILL describe the lifecycle.
- [ ] Full local and nine required CI gates pass.

## STOP conditions

Stop and report back if:

- Exact-title ownership is insufficient because another workflow owns the same
  title.
- Recovery requires broad issue search/close permissions beyond the current
  repository.
- GitHub CLI cannot close an issue with the current `issues: write` permission.
- Preserving shipped failure and self non-failure policies requires divergent
  lifecycle scripts that cannot be tested for parity.
- A real issue must be created to test the implementation.
- Verification fails twice after a reasonable scoped fix.

## Maintenance notes

- Treat the issue as current incident state, not an append-only history store;
  reports remain available as workflow artifacts.
- Keep the exact title and lifecycle logic in both template and self-dogfood
  copies.
- If labels are added later, title equality must remain the final ownership
  check before closing.
