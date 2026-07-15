# Plan 028: Make lint CI install the committed npm lockfile exactly

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 150d1c9..HEAD -- .github/workflows/test.yml package.json package-lock.json tests/test_action_metadata.py CONTRIBUTING.md RELEASING.md AGENTS.md benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json benchmark/self-eval/results-after-graded.json benchmark/self-eval/README.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: security / dependencies / dx / tests / docs
- **Planned at**: commit `150d1c9`, 2026-07-16

## Why this matters

The public repository commits a complete npm lockfile with 72 package records,
71 public tarball URLs, and integrity hashes, but the required lint job does not
install from it. Instead it invokes Yarn Classic without a `yarn.lock`, resolves
fresh versions from semver ranges on every PR, and creates an untracked lockfile
inside the runner.

That means a required CI context can pass against dependency bytes that are not
the reviewed dependency graph. The historical npm workaround is also stale:
the exact CI Node `20.19.5` environment now runs `npm ci` successfully from the
committed lockfile.

## Current state

- `.github/workflows/test.yml:13-28` pins Node 20.19.5 for ESLint, then says:

  ```yaml
  # `npm install`/`npm ci` deterministically aborts with "Exit handler never
  # called" on this runner while resolving the eslint 10 tree. Yarn classic
  # produces the same flat node_modules layout and is immune to that bug.
  - name: Install Node dev dependencies
    run: yarn install --non-interactive --ignore-engines
  ```

- There is no committed `yarn.lock`. Real `main` lint job
  `87419464002` printed:

  ```text
  yarn install v1.22.22
  info No lockfile found.
  warning package-lock.json found. Your project contains lock files generated
  by tools other than Yarn.
  ...
  success Saved lockfile.
  ```

  Therefore the required job explicitly confirms that it ignores the reviewed
  lock format.

- A local isolated reproduction changed only
  `package-lock.json#packages["node_modules/prettier"].version` to `3.9.4`,
  then ran the exact CI Yarn command. Yarn installed Prettier `3.9.5`, proving
  the committed lock record does not constrain the job.

- The current dependency graph happens to resolve to the same direct versions
  today:

  ```json
  {
    "@eslint/js": "10.0.1",
    "eslint": "10.7.0",
    "prettier": "3.9.5"
  }
  ```

  That coincidence does not make the install reproducible; range resolution
  can change without a repository diff.

- Running this command in an isolated directory containing only the current
  manifests succeeds on the exact CI Node/npm versions (`v20.19.5`, npm
  `10.8.2`):

  ```bash
  npm ci --ignore-scripts --no-audit --no-fund
  ```

  It installs 71 packages and every direct installed version equals the
  committed lock.

- `tests/test_action_metadata.py` enforces public registry hosts and workflow
  trigger/pin policy, but does not assert that the lint job consumes
  `package-lock.json` or reject a generated Yarn lock.

## Target contract

1. The required lint job installs dev dependencies only through the committed
   `package-lock.json`.
2. Use `npm ci`, not `npm install`, Yarn, pnpm, or a lockfile-regenerating
   command.
3. Keep `--ignore-scripts`, `--no-audit`, and `--no-fund` so CI does not execute
   package lifecycle scripts or add unrelated network behavior.
4. Keep the exact Node 20.19.5 lint runtime unless current ESLint support
   requires a documented update.
5. A package/lock mismatch, missing lockfile, integrity mismatch, or
   unavailable artifact must fail the required lint job.
6. Do not commit `yarn.lock`, rewrite dependency versions, or add a second
   package-manager workflow.
7. Structural tests must prevent the stale workaround from returning.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Workflow tests | `python3 -m unittest discover -s tests -p 'test_action_metadata.py' -v` | all pass |
| actionlint | `actionlint .github/workflows/test.yml` | exit 0 |
| Exact install | isolated `npm ci --ignore-scripts --no-audit --no-fund` | exit 0; 71 packages |
| Node lint | `npm run lint` | exit 0 |
| Full gate | `npm run check` | exit 0 |
| Evidence gate | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0 |
| Self scan | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0; grade A |

## Scope

**In scope**:

- `.github/workflows/test.yml`
- `tests/test_action_metadata.py`
- `CONTRIBUTING.md` and `RELEASING.md` only for the public lock/install
  maintenance contract
- compact dependency-install invariant in `AGENTS.md`
- evidence-bound `benchmark/self-eval/` refresh after `AGENTS.md` changes
- `plans/README.md`

**Out of scope**:

- Changing selected dependency versions or package semver ranges.
- Creating/committing `yarn.lock`.
- Replacing npm in published runtime or consumer documentation.
- Adding install steps to Python/Node syntax-test matrix jobs that do not need
  dev dependencies.
- Running package lifecycle scripts.
- Reworking Dependabot grouping, registry host normalization, or Action pins.
- Adding a runtime dependency.

## Git workflow

- Branch: `fix/locked-lint-install`
- Commit: `fix(ci): install lint dependencies from npm lock`
- One focused CI reproducibility/supply-chain PR.
- Do not push directly to `main`. Open an English PR, wait for all nine required
  contexts, then squash-merge and delete the branch.
- This is an internal CI correctness/security repair. By itself it is
  patch-level.

## Steps

### Step 1: Add a policy test that fails on unlocked installs

Extend `tests/test_action_metadata.py` to extract the lint job's dependency
install step and assert:

- it contains exactly one `npm ci`;
- it passes `--ignore-scripts --no-audit --no-fund`;
- it contains no `yarn`, `pnpm`, `npm install`, or lock generation;
- `package-lock.json` exists and its root devDependencies equal
  `package.json#devDependencies`;
- every installed package record used by direct dev dependencies has a version,
  public `resolved`, and `integrity`.

Avoid a broad YAML parser dependency; follow the file's existing structural
workflow-test style.

**Verify**: the new test fails against `150d1c9` because the job invokes Yarn
without a lock.

### Step 2: Replace the stale workaround with exact npm CI

Update the named lint step to:

```yaml
- name: Install Node dev dependencies
  run: npm ci --ignore-scripts --no-audit --no-fund
```

Remove the obsolete “Exit handler never called” comment. Optionally add one
short comment that the committed public npm lock is the reviewed dependency
graph; do not narrate old failures.

**Verify**: actionlint and focused workflow tests pass.

### Step 3: Prove exact installation on the CI runtime

In an isolated temp directory, copy only `package.json` and
`package-lock.json`, select Node 20.19.5/npm 10.8.2, run the exact command, and
compare installed direct package versions with lock records.

Then push the PR and inspect the real lint log:

- no “No lockfile found”;
- no Yarn mixed-lock warning;
- npm reports the locked install;
- `npm run lint` passes.

**Verify**: all direct versions match and the required lint context is green.

### Step 4: Document the reproducibility invariant

Update `CONTRIBUTING.md`/`RELEASING.md` only where they describe dependency
maintenance. Add a compact `AGENTS.md` invariant: CI installs from the
committed public npm lock; changing manifests requires refreshing and reviewing
that lock.

Refresh self-eval evidence and mark Plan 028 DONE only after merge.

**Verify**: evidence gate, self scan, strict drift, and full gate pass;
`AGENTS.md` remains compact.

## Test plan

- Structural workflow test for exact installer argv and banned alternatives.
- Lock root-vs-package manifest equality.
- Direct dependency record completeness without logging complete URLs.
- Isolated real `npm ci` on Node 20.19.5.
- Full action metadata and repository test suite.

## Done criteria

- [ ] Required lint CI consumes the committed `package-lock.json`.
- [ ] No Yarn/no-lock dynamic resolution remains in active workflows.
- [ ] Exact isolated install succeeds on the CI Node/npm runtime.
- [ ] Direct installed versions equal committed lock records.
- [ ] Structural tests prevent reintroduction of unlocked installs.
- [ ] Maintenance docs, `AGENTS.md`, and self-eval evidence are current.
- [ ] All nine required PR contexts are green.
- [ ] Plan 028 and its index row are marked DONE after squash merge.

## STOP conditions

Stop and report back (do not improvise) if:

- `npm ci` still reproduces the historical exit-handler failure on the exact
  CI image/runtime.
- Fixing npm requires lifecycle scripts, a private registry, or a lock rewrite.
- The committed lock is internally inconsistent with `package.json`.
- An artifact in the reviewed lock is genuinely unavailable.
- A verification command fails twice after a reasonable scoped fix.

## Maintenance notes

- A lockfile helps only when required jobs actually consume it.
- Keep the install command fail-closed; do not add fallback-to-Yarn behavior.
- Dependabot PRs must continue updating both manifest and npm lock.
- Review any future package-manager workaround against a current real runner
  reproduction before bypassing the lock.
