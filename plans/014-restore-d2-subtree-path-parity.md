# Plan 014: Restore subtree-scoped path parity between scan and drift

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 73bd749..HEAD -- scripts/check_drift.py scripts/facts.py scripts/semantic.py tests/test_check_drift.py tests/test_registry_consistency.py tests/test_semantic.py EXTERNAL_VALIDATION.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: correctness / tests
- **Planned at**: commit `73bd749`, 2026-07-15

## Why this matters

The Phase 0 semantic scan and Phase 2 drift gate share the same candidate-path
classifier, but no longer share the same existence policy. A root `AGENTS.md`
may scope instructions to a workspace and then reference paths relative to that
workspace. `scan` correctly accepts those paths through the shared subtree
resolver, while `drift` emits a blocking D2 error for the identical declaration.

This violates the repository's cross-engine consistency promise and can make a
consumer pass checkup but fail the installed PR/pre-commit guard. The fix is a
small parity restoration, not a new heuristic.

## Current state

- `scripts/facts.py:343-382` already owns the repository-contained,
  pruned-walk helper:

  ```python
  def path_resolves_in_subtree(root, token):
      """True when a backtick path that is missing at the repo root still resolves
      ...
  ```

- `scripts/semantic.py:801-811` uses it after the root and package-import checks:

  ```python
  if not facts.exists_within_root(root, root / token):
      ...
      if facts.path_resolves_in_subtree(root, token):
          continue
  ```

- `scripts/check_drift.py:131-149` performs the same root/package checks but
  immediately emits D2; it never calls `path_resolves_in_subtree()`:

  ```python
  if not facts.exists_within_root(root, root / token):
      ...
      if token.split("/", 1)[0] in package_names:
          continue
      findings.append({"check": "D2", ...})
  ```

- Real minimal reproduction at the planned commit:
  - repository contains `packages/app/src/config/`;
  - root `AGENTS.md` says “In the packages/app workspace, edit `src/config`”;
  - `python3 scripts/scan.py REPO --json` exits 0 with no semantic path finding;
  - `python3 scripts/check_drift.py REPO --json` exits 1 with D2 for
    `src/config`.

- `EXTERNAL_VALIDATION.md` rounds 14–15 say the subtree fix covered the full
  chain, but only `tests/test_semantic.py` carries subtree regressions. The
  Phase 2 claim needs an explicit regression test and a correction note.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Drift tests | `python3 -m unittest discover -s tests -p 'test_check_drift.py' -v` | all pass |
| Cross-engine tests | `python3 -m unittest discover -s tests -p 'test_registry_consistency.py' -v` | all pass |
| Semantic compatibility | `python3 -m unittest discover -s tests -p 'test_semantic.py' -v` | all pass |
| Python lint | `ruff check scripts/check_drift.py tests/test_check_drift.py tests/test_registry_consistency.py` | exit 0 |
| Full gate | `npm run check` | exit 0 |
| Self checks | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts && python3 scripts/check_drift.py . --strict` | exit 0; grade A |

## Scope

**In scope**:

- `scripts/check_drift.py`
- `tests/test_check_drift.py`
- `tests/test_registry_consistency.py`
- `tests/test_semantic.py` only if an existing fixture/helper must be shared
- `scripts/facts.py` / `scripts/semantic.py` only if a tiny shared policy helper
  is required to prevent this class from recurring
- `EXTERNAL_VALIDATION.md`
- `plans/README.md`

**Out of scope**:

- Changing which backtick tokens count as path candidates.
- Adding new subtree heuristics or section-language parsing.
- Masking fully qualified missing paths merely because a same-basename file
  exists elsewhere.
- Changing D2 severity, exit codes, baselines, SARIF, or PR-review rendering.
- Updating `AGENTS.md`; the final repository-hardening plan records the compact
  cross-engine maintenance invariant after all selected work lands.

## Git workflow

- Branch: `fix/d2-subtree-path-parity`
- Commit: `fix(drift): restore subtree path parity`
- One focused bugfix PR; squash-merge only after all CI checks pass.

## Steps

### Step 1: Add a failing Phase 2 characterization

Add a real CLI or `run_checks()` regression in `tests/test_check_drift.py` using
a temporary repository:

1. root `AGENTS.md` references `src/config`;
2. only `packages/app/src/config` exists;
3. D2 must not report it.

Add the negative control in the same test/class: a fully-qualified missing path
with no matching subtree suffix must still emit D2 and exit non-zero.

**Verify**: the new positive test fails against `73bd749`; the negative control
passes.

### Step 2: Restore the shared existence policy in D2

In `d2_path_drift()`, after containment, root existence, and package-name
checks, consult `facts.path_resolves_in_subtree(root, token)` before appending
the D2 finding. Preserve the lazy behavior: the subtree walk runs only for a
would-be missing path.

Do not duplicate the resolver or copy its manifest/suffix rules into
`check_drift.py`.

**Verify**: the focused D2 tests pass and the minimal reproduction produces no
Phase 0 or Phase 2 path finding.

### Step 3: Lock scan/drift agreement as a cross-engine invariant

Add a compact parity test to `tests/test_registry_consistency.py` that feeds the
same temporary repo/text to `semantic.compare_paths()` and
`check_drift.d2_path_drift()` for:

- a subtree-resolved multi-segment path;
- a missing multi-segment path;
- a subtree-resolved known manifest basename, if that behavior is already
  covered by `facts.path_resolves_in_subtree()`.

Compare the set of path tokens judged missing rather than comparing
engine-specific message text.

**Verify**: both engines agree for every case.

### Step 4: Correct the external-validation evidence boundary

Append a short note to rounds 14–15 in `EXTERNAL_VALIDATION.md` explaining that
the original fix covered Phase 0, this audit exposed the missing Phase 2
traversal, and this PR adds the cross-engine regression. Do not rewrite the
historical findings or imply a fresh external clone was run if none was.

**Verify**: the log names the reproduction, affected phases, and fixing PR
placeholder without claiming unsupported evidence.

### Step 5: Run full gates

Run all commands in the command table, confirm the working tree contains only
in-scope files, and mark Plan 014 DONE.

## Test plan

- Subtree-relative path exists: no semantic finding, no D2.
- Fully missing path: semantic MISSING and D2 remain.
- Package self-import behavior remains unchanged.
- External symlink/containment tests remain green.
- One parity test compares the engines by missing token.

## Done criteria

- [ ] `scan` and `drift` agree on subtree-scoped path existence.
- [ ] Genuine fully missing paths still fail both engines.
- [ ] The shared resolver remains single-sourced in `scripts/facts.py`.
- [ ] No new repository walk occurs for already-valid root paths.
- [ ] External-validation history accurately records the repaired gap.
- [ ] `npm run check` passes and strict self-drift remains Grade A.
- [ ] Only in-scope files are modified.

## STOP conditions

- The fix requires broadening `registry.declared_paths()` candidacy.
- Phase 0's subtree behavior is found to mask a demonstrated genuine finding;
  stop and reassess the shared policy rather than copying it into D2.
- The resolver follows external symlinks or requires weakening containment.
- Verification fails twice after a reasonable correction.

## Maintenance notes

Path candidacy and path existence are separate shared contracts. Any future
exception added to Phase 0 must have a Phase 2 parity test before release.
Reviewers should reject engine-local path-resolution heuristics.
