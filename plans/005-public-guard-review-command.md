# Plan 005: Make installed guard workflows use only the public packaged CLI

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat c8d2f05..HEAD -- bin/cli.js package.json assets/guard/harness-drift.yml assets/guard/gitlab/harness-ci.yml assets/guard/codebase/harness-guard.sh tests/test_cli.py tests/test_pr_review.py tests/test_action_metadata.py bin/cli.test.js README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md`
> If any in-scope file changed, compare the current-state excerpts below with
> live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: `plans/004-contain-repository-mutations.md`
- **Category**: bug / direction / DX
- **Planned at**: commit `c8d2f05`, 2026-07-15

## Why this matters

The shipped GitHub guard promises rich PR review feedback, but its workflow
invokes `python3 scripts/check_drift.py` and `scripts/pr_review.py` inside the
*consumer repository*. `guard --apply` installs only workflows/hooks/contract,
not these scripts, so the post step fails in every normal adopter repo. The
self-bootstrap copy works only because this source repository happens to own
those paths. A premium guard must be executable solely through the published
package/CLI it installs.

## Current state

- `assets/guard/harness-drift.yml:39-60` runs the drift gate via
  `npx -y ai-harness-doctor`, then switches to local `scripts/*.py` for the PR
  report/post path.
- `bin/cli.js:580-609,996-1010` exposes Python-backed commands through one
  `SCRIPT_COMMANDS` map; there is no public `review` / `pr-review` command.
- `package.json:8-23` already ships every `scripts/*.py`, including
  `pr_review.py`, so no package-content expansion is needed.
- `tests/test_cli.py:88-128` verifies guard installation/idempotency but only
  searches for the drift command, not executable PR-review delivery.
- The self-hosted `.github/workflows/harness-drift.yml` deliberately uses local
  scripts to dogfood changes. That adapted copy may keep local execution, while
  the shipped template must use the package CLI.

Verified consumer reproduction at the planned commit:

1. Run `node bin/cli.js guard <empty-git-repo> --apply --provider github`.
2. Confirm `<repo>/scripts/check_drift.py` and `pr_review.py` are absent.
3. The installed workflow's report command errors because it opens those paths.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| CLI unit/integration | `python3 -m unittest tests.test_cli tests.test_pr_review -v` | all pass |
| Node tests | `node --test bin/*.test.js` | all pass |
| Metadata tests | `python3 -m unittest tests.test_action_metadata -v` | all pass |
| Package contents | `npm pack --dry-run` | `scripts/pr_review.py` included |
| Docs sync | `python3 scripts/check_readme_sync.py` | OK |
| Full gate | `npm run check` | exit 0 |
| Self guard | `python3 scripts/check_drift.py .` | grade A |

## Scope

**In scope**:

- `bin/cli.js`
- `package.json` only if command metadata/scripts need an explicit contract
- `assets/guard/harness-drift.yml`
- `assets/guard/gitlab/harness-ci.yml`
- `assets/guard/codebase/harness-guard.sh`
- `tests/test_cli.py`
- `tests/test_pr_review.py`
- `tests/test_action_metadata.py`
- `bin/cli.test.js`
- `README.md`, `README.zh-CN.md`, `README.ja.md`
- `SKILL.md`
- `AGENTS.md`
- `.github/workflows/harness-drift.yml` only for an adapted self-dogfood update
  or contract test; do not replace local drift execution blindly

**Out of scope**:

- GitLab/Codebase inline comment implementations. They remain documented as no
  inline review support; remove their broken direct `eval_run.py` path by using
  the public `eval` CLI, but do not build provider APIs.
- Deduplicating previous bot comments.
- Changing `pr_review.py` finding formatting except where needed for CLI
  usability.
- Bundling Python into the Action; Python 3 remains an explicit runtime.
- Installing the entire source tree into consumer repos.

## Git workflow

- Branch: `fix/public-guard-review-command`
- Commit: `fix(guard): run review feedback through packaged CLI`
- Conventional Commit, English.
- Open one focused PR; squash merge after every CI check is green.

## Steps

### Step 1: Add a public CLI command for review payload/posting

Choose one stable name (`review` is preferred; `pr-review` is acceptable if
documented consistently) and add it to `SCRIPT_COMMANDS`, usage/examples,
dispatch, and runtime self-test automatically through the map. It should forward
arguments to `scripts/pr_review.py` without reimplementing logic in Node.

Add tests proving dry-run JSON and `--post` argument validation are reachable
through `node bin/cli.js <command>`. Existing `pr_review.py` network tests remain
the source of truth for HTTP behavior.

**Verify**: Node/CLI focused tests pass and `doctor --json` lists the new script
check.

### Step 2: Rewrite the shipped GitHub template as a package-only pipeline

Generate drift JSON with the public CLI, then pipe/pass it to the public review
command. A target shape is:

```bash
npx -y ai-harness-doctor drift . --json > drift-report.json || true
npx -y ai-harness-doctor review --report drift-report.json ...
```

Do not refer to consumer-local `scripts/`. Keep the gate's original strict exit
behavior and the best-effort comment-post behavior for fork/limited-token PRs.
Pin the package channel intentionally (`@latest` or a documented floating npm
tag) so the workflow has an explicit update model.

**Verify**: static template tests assert no `python3 scripts/` invocations; an
integration test installs the guard into an empty repo and executes the dry-run
report/review commands with an isolated npm cache or local package path.

### Step 3: Remove the same packaging assumption from portable eval gates

The GitLab and Codebase templates call `python3 scripts/eval_run.py` when a
results file exists. The current `eval` command already forwards arbitrary
arguments, so use `ai-harness-doctor eval --score ...` and update templates to
call only the public CLI. Preserve their provider-specific behavior and exit
codes.

**Verify**: grep across shipped guard assets finds no consumer-local
`scripts/*.py` command; template tests cover all providers.

### Step 4: Keep self-dogfood explicit and test consumer executability

The repository's own `.github/workflows/harness-drift.yml` may continue using
local code so PRs test their changes. Add comments/tests that distinguish this
adapted copy from public templates. Extend `tests/test_cli.py` beyond file
presence: after `guard --apply`, execute the installed workflow's public command
sequence (dry-run post) against the fixture repo and assert valid review JSON.

**Verify**: full CLI/metadata suites pass; consumer fixture has no `scripts/`
directory and still completes the dry-run pipeline.

### Step 5: Document the real public surface and maintenance contract

Update trilingual command references, `SKILL.md`, and `AGENTS.md`:

- list the new public review command and its dry-run/post modes;
- require shipped guard templates to run only package CLI commands available in
  a fresh consumer repository;
- require one end-to-end consumer-repo guard test for template changes.

**Verify**: docs sync, `npm pack --dry-run`, full gate, self scan/drift.

## Test plan

- CLI forwarding: stdin/report file, default dry run, post argument errors,
  propagated exit status.
- Consumer install: empty repo + `guard --apply`; no local scripts; drift JSON
  and review-payload generation succeed.
- Template contracts: GitHub/GitLab/Codebase assets contain no
  `python3 scripts/`; self-hosted copy remains explicitly local where intended.
- Package tarball: `pr_review.py` and any required engine remain included.

## Done criteria

- [ ] Fresh consumer repositories can execute every installed guard command.
- [ ] Shipped guard assets contain no consumer-local `scripts/*.py` invocation.
- [ ] GitHub PR review payload/posting is reachable through the public CLI.
- [ ] GitLab/Codebase eval gates use the package CLI or are honestly omitted.
- [ ] Consumer-repo integration test runs without copying source scripts.
- [ ] `npm run check` exits 0; self drift stays grade A.
- [ ] No files outside Scope and `plans/README.md` are modified.

## STOP conditions

- A public command would expose write behavior not already available in
  `pr_review.py`.
- The installed template cannot post reviews without adding a runtime
  dependency beyond Node + Python stdlib.
- Testing requires publishing an intermediate npm package; use a local packed
  tarball or command override instead and report if that is impossible.
- The adapted self-hosted workflow can no longer test unmerged local changes.

## Maintenance notes

Any future guard template must be tested in a repository containing only what
`guard --apply` installs. Source-repo paths are not a public interface. Keep the
Node `SCRIPT_COMMANDS` map as the single dispatch/self-test source, and do not
create a second wrapper for `pr_review.py`.
