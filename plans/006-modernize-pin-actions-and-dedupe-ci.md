# Plan 006: Pin and modernize GitHub Actions while removing duplicate PR CI

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat c8d2f05..HEAD -- .github/workflows assets/guard README.md README.zh-CN.md README.ja.md RELEASING.md tests/test_action_metadata.py tests/test_cli.py AGENTS.md`
> If any in-scope file changed, compare the current-state excerpts below with
> live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: security / migration / DX / perf
- **Planned at**: commit `c8d2f05`, 2026-07-15

## Why this matters

The `v1.0.1` release completed successfully but every job emitted GitHub's
Node-20 deprecation warning because the workflows still use old Action majors.
All third-party Actions are also referenced by mutable major tags, including in
the npm publish job with `id-token: write`. In addition, `.github/workflows/test.yml`
runs on every branch push and every pull request, so PR branches execute the
same seven matrix jobs twice. A premium public repository should use current
runtimes, immutable dependency pins with an update policy, and one intentional
CI execution per event.

## Current state

- `.github/workflows/test.yml:3-5` declares unrestricted `push` plus
  `pull_request`; PRs #106–#110 each showed duplicate push/PR test checks.
- `.github/workflows/*.yml` and `assets/guard/*.yml` use
  `actions/checkout@v4`, `actions/setup-node@v4`,
  `actions/setup-python@v5`, and `actions/upload-artifact@v4`.
- The `v1.0.1` release run `29381316997` annotated `test`, `publish`, and
  `verify-published-action` with: Node.js 20 is deprecated and these Actions
  are being forced to Node 24.
- GitHub's current floating majors at the planned date resolve to:
  - `actions/checkout@v7` →
    `9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0`
  - `actions/setup-node@v7` →
    `820762786026740c76f36085b0efc47a31fe5020`
  - `actions/setup-python@v6` →
    `ece7cb06caefa5fff74198d8649806c4678c61a1`
  - `actions/upload-artifact@v7` →
    `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a`
  - `github/codeql-action@v4` →
    `99df26d4f13ea111d4ec1a7dddef6063f76b97e9`
- The repo has no `.github/dependabot.yml`, so immutable pins would otherwise
  become manual drift.
- `tests/test_action_metadata.py` covers Action/release semantics but not
  immutable pins, current runtime majors, or trigger deduplication.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Workflow lint | `go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7` | exit 0 |
| YAML parse | `ruby -e 'require "yaml"; Dir[".github/workflows/*.yml"].each { |f| YAML.load_file(f) }'` | exit 0 |
| Metadata tests | `python3 -m unittest tests.test_action_metadata tests.test_cli -v` | all pass |
| Docs sync | `python3 scripts/check_readme_sync.py` | OK |
| Full gate | `npm run check` | exit 0 |
| Self drift | `python3 scripts/check_drift.py .` | grade A |

## Scope

**In scope**:

- `.github/workflows/*.yml`
- `.github/dependabot.yml` (create)
- `assets/guard/harness-drift.yml`
- `assets/guard/harness-checkup.yml`
- any GitHub Action examples in `README.md`, `README.zh-CN.md`, `README.ja.md`
- `RELEASING.md`
- `tests/test_action_metadata.py`
- `tests/test_cli.py` if guard-template assertions belong there
- `AGENTS.md`

**Out of scope**:

- Changing runtime support (`Node >=16`, Python 3.9+) or removing matrix
  versions. The Actions' own runtime and the tested product runtime are separate.
- GitLab/Codebase container versions unless required by a tested compatibility
  issue.
- Enabling remote GitHub security settings via API. Record the recommendation,
  but this plan changes version-controlled configuration only.
- Renovate or any new runtime dependency.
- Combining push and pull-request matrices into reduced coverage; keep the
  existing matrix, just stop duplicate execution.

## Git workflow

- Branch: `chore/harden-github-actions`
- Commit: `chore(ci): pin and modernize GitHub Actions`
- Conventional Commit, English.
- Open one focused PR; squash merge after every CI check is green.

## Steps

### Step 1: Lock the desired workflow contracts in tests

Add static tests that enumerate every external `uses:` line under
`.github/workflows/` and `assets/guard/` and require:

- a 40-character commit SHA, with an adjacent `# owner/action@vN` update hint;
- only an explicit allow-list of local Actions (`./`, `./published-action`);
- current Action major comments listed in Current state;
- no bare/mutable third-party tag;
- `.github/workflows/test.yml` pushes only on `main` (or uses a condition that
  provably excludes PR branch pushes) while retaining `pull_request`;
- Dependabot's `github-actions` ecosystem exists on a weekly cadence.

Keep expected SHA constants in one test mapping. Do not scatter them through
multiple tests.

**Verify**: tests fail on the current mutable/old `uses:` lines.

### Step 2: Upgrade and pin every repository workflow

Replace every external Action reference with the vetted immutable SHA and a
human-readable major comment:

```yaml
- uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # actions/checkout@v7
```

Cover test, Action self-test, drift/checkup, release, deprecate, and every
duplicate checkout in verification. Keep job permissions unchanged unless
modern action docs require a narrower permission. Update README SARIF upload
example to the current CodeQL major; because examples favor readability, the
README may show `@v4`, but document that production workflows should pin a SHA.

**Verify**: actionlint/YAML parse and metadata tests pass.

### Step 3: Keep shipped guard templates synchronized

Apply the same immutable pins/current majors to
`assets/guard/harness-drift.yml` and `harness-checkup.yml`. Update
`tests/test_cli.py` so `guard --apply` output is checked for the pinned refs and
remains idempotent/removable. The self-hosted copies differ only where they run
local product code; external dependencies must match the templates.

**Verify**: install/remove tests pass and no mutable external `uses:` remains.

### Step 4: Remove duplicate PR branch runs without losing main validation

Change `test.yml` to:

```yaml
on:
  push:
    branches: [main]
  pull_request:
```

or an equivalent unambiguous trigger. `action-self-test.yml` already follows
this model. Do not remove push-on-main because merged commits still need a
post-merge signal.

Add a regression test for this exact event contract. If YAML 1.1 parsers turn
`on` into boolean, tests may inspect text or use a parser that preserves GitHub
syntax.

**Verify**: actionlint passes; on the PR, only one `test` workflow family should
appear for the head SHA (manual observation recorded in the PR).

### Step 5: Add an automated update policy and maintenance rules

Create `.github/dependabot.yml` for `github-actions` weekly updates (group minor
Action dependency bumps if supported), and optionally npm dev dependencies if
the scope stays small. Update `AGENTS.md`:

- external Actions must be full-SHA pinned with a readable major comment;
- Dependabot is the update path;
- workflow/template copies must move together;
- `test.yml` must not duplicate full PR matrices via branch pushes.

Update `RELEASING.md` to require a warning-free current Action runtime during
release verification.

**Verify**: docs, metadata tests, full gate, self drift.

## Test plan

- Static traversal of all workflow/template `uses:` values.
- Trigger contract (`push` main only + all PRs).
- Dependabot `github-actions` entry.
- Guard installer contains identical pinned external dependencies.
- actionlint over all repository workflows and shipped GitHub templates (copy
  templates to a temporary `.github/workflows` location if actionlint requires).

## Done criteria

- [ ] Every third-party Action is pinned to a vetted full commit SHA.
- [ ] Pins carry readable `owner/action@vN` comments and Dependabot updates them.
- [ ] No Node-20 Action-runtime deprecation warning is expected from current
      Action dependencies.
- [ ] PR branches run one full test matrix, while `main` pushes still run it.
- [ ] Shipped guard templates and self-hosted dependencies stay synchronized.
- [ ] `actionlint`, YAML parse, metadata tests, and `npm run check` pass.
- [ ] No files outside Scope and `plans/README.md` are modified.

## STOP conditions

- A current Action major drops support for one of this repo's tested product
  runtimes (Node 16/Python 3.9) in a way that affects the matrix.
- The pinned SHA cannot be verified as the target Action's official major ref.
- Branch protection requires a check name that disappears under trigger
  deduplication; capture the required-check settings before proceeding.
- Dependabot cannot update SHA-pinned Actions with the chosen comment format.

## Maintenance notes

Never refresh SHA pins from an unauthenticated search snippet. Resolve the
official Action ref through GitHub's API and record both SHA and readable major.
Review Dependabot Action bumps like code changes, especially in OIDC/write jobs.
Keep product runtime matrices independent from the JavaScript runtime embedded
inside GitHub Actions.
