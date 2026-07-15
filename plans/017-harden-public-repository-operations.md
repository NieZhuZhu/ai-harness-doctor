# Plan 017: Establish a verifiable public-repository trust baseline

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 73bd749..HEAD -- SECURITY.md CODE_OF_CONDUCT.md SUPPORT.md .github/ISSUE_TEMPLATE .github/pull_request_template.md .github/dependabot.yml .github/workflows/test.yml .github/workflows/release.yml tests/test_action_metadata.py tests/test_cli.py CONTRIBUTING.md README.md README.zh-CN.md README.ja.md RELEASING.md AGENTS.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: Plans 014–016 should land first so the final AGENTS.md
  operational contract describes the completed batch
- **Category**: security / GitHub engineering / docs / operations
- **Planned at**: commit `73bd749`, 2026-07-15

## Why this matters

The product and release automation are unusually mature, but the public
repository still lacks the trust surfaces and enforced remote settings expected
of a premium GitHub project. GitHub reports 57% community profile health, no
security policy or issue/PR templates, secret scanning and push protection
disabled, and no required CI contexts on `main`.

This is not cosmetic: vulnerability reporters have no private disclosure route,
contributions have no structured reproduction/checklist, npm dependencies are
not monitored by Dependabot, and branch protection does not require the CI
matrix that the repository's own `AGENTS.md` says must pass. Land reviewable
repository files first, then apply the remote settings with before/after
evidence and rollback instructions.

## Current state

- GitHub community profile API at the planned commit:

  ```json
  {
    "health_percentage": 57,
    "files": {
      "readme": {...},
      "contributing": {...},
      "license": {...},
      "code_of_conduct": null,
      "issue_template": null,
      "pull_request_template": null
    }
  }
  ```

- Missing repository files:
  - `SECURITY.md`
  - `CODE_OF_CONDUCT.md`
  - `SUPPORT.md`
  - `.github/ISSUE_TEMPLATE/*`
  - `.github/pull_request_template.md`

- `.github/dependabot.yml` updates `github-actions` weekly but has no npm entry,
  despite 71 dev dependency nodes and a committed lockfile. A public-registry
  `npm audit` currently reports zero vulnerabilities; this is a clean baseline,
  not a substitute for ongoing updates.

- A fresh isolated `npm ci` from only `package.json` and `package-lock.json`
  succeeds against `https://registry.npmjs.org` despite committed resolved URLs
  using `bnpm.byted.org`. Therefore lockfile normalization is not required to
  unblock public contributors and remains out of this plan.

- Repository API reports:

  ```json
  {
    "secret_scanning": {"status": "disabled"},
    "secret_scanning_push_protection": {"status": "disabled"},
    "secret_scanning_validity_checks": {"status": "disabled"},
    "dependabot_security_updates": {"status": "disabled"}
  }
  ```

- `main` branch protection has one required approving review, but:
  - `required_status_checks` is null;
  - admin enforcement is disabled;
  - conversation resolution is disabled.

  The owner uses admin squash merges after all checks pass because GitHub does
  not permit self-approval to satisfy the review requirement. Do not enable
  admin enforcement without first proving it will not deadlock this
  single-maintainer workflow.

- Recent PRs expose stable check names:
  `drift`, `lint`, `node (16|20|22)`, `self-test`,
  `unittest (3.9|3.10|3.12)`.

- Release workflow creates a Marketplace reminder per stable tag. Four old
  reminders (#98, #99, #104, #111) remain open even though a later Marketplace
  release supersedes them. This creates issue noise and weakens the operational
  signal.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Metadata tests | `python3 -m unittest discover -s tests -p 'test_action_metadata.py' -v` | all pass |
| CLI/workflow tests | `python3 -m unittest discover -s tests -p 'test_cli.py' -v` | all pass |
| Docs sync | `python3 scripts/check_readme_sync.py` | OK |
| npm audit | `npm audit --registry=https://registry.npmjs.org --json` | zero high/critical vulnerabilities |
| Public install | isolated temp-dir `npm ci --ignore-scripts --registry=https://registry.npmjs.org --no-audit --no-fund` | exit 0 |
| Full gate | `npm run check` | exit 0 |
| Self checks | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts && python3 scripts/check_drift.py . --strict` | exit 0; grade A |

## Scope

**In scope**:

- community health files listed above
- `.github/dependabot.yml`
- structural tests for the files/workflows
- release reminder lifecycle cleanup
- synchronized public docs only where contribution/security behavior changes
- `CONTRIBUTING.md`, `RELEASING.md`
- final compact maintenance/operations contract in `AGENTS.md`
- `benchmark/self-eval/` evidence refresh required by Plan 015 whenever the
  final `AGENTS.md` contract changes
- remote GitHub repository security settings and branch-protection status checks
- `plans/README.md`

**Out of scope**:

- Publishing vulnerability details in public issues.
- CodeQL for a stdlib Python/Node wrapper with no runtime dependencies unless a
  separate evidence-based plan justifies it.
- Normalizing every lockfile registry URL; fresh public `npm ci` already passes.
- Requiring admin enforcement or signed commits/tags.
- Enabling Discussions or adding governance bureaucracy unsupported by current
  two-star/one-maintainer scale.
- Changing product behavior or release channels.
- Adding broad automatic labels, stale bots, or contributor license agreements.

## Git workflow

- Branch: `chore/public-repository-trust-baseline`
- Commit: `chore(repo): establish public trust baseline`
- Keep file changes and the script/workflow changes in one reviewed PR.
- Do not apply remote settings until this PR is fully green and merged. Record
  pre-change JSON in the PR body or a temporary local file, never commit auth
  tokens.

## Steps

### Step 1: Add focused community health files

Create:

- `SECURITY.md`: supported version policy, private vulnerability reporting via
  GitHub Security Advisories, response expectations, and an explicit “do not
  file public exploit details” instruction.
- `CODE_OF_CONDUCT.md`: Contributor Covenant (current stable text) with a real
  enforcement contact route that does not publish a private email unless the
  maintainer chooses to.
- `SUPPORT.md`: discussions/issues boundary using existing GitHub Issues only;
  do not claim Discussions are enabled.
- issue forms:
  - bug report with version, invocation surface, minimal repo shape, expected/
    actual behavior, sanitized output, and safety confirmation;
  - false-positive report tailored to scan/drift evidence, explicitly forbidding
    pasted secrets;
  - feature request emphasizing user/doctor outcome and alternatives.
- issue-template config with private security link and no blank issues if every
  legitimate route is covered.
- PR template with linked issue/plan, change type, tests, trilingual docs,
  safety/read-only boundary, and release classification.

Keep templates concise enough to encourage completion. Do not ask users to
upload private repositories or credentials.

**Verify**: a structural test parses frontmatter/required headings and community
profile API recognizes the files after merge.

### Step 2: Extend Dependabot to npm

Add a weekly npm ecosystem entry at `/`, grouping dev tooling updates where
appropriate. Preserve the existing grouped immutable GitHub Action update flow.

Because runtime dependencies are intentionally zero, document that npm updates
are development-tooling only and must still pass Node 16 product tests even when
the lint tool itself requires newer Node.

Add a test asserting both `github-actions` and `npm` ecosystems exist and no
mutable workflow `uses:` refs are introduced.

**Verify**: metadata tests pass and `npm audit` remains clean.

### Step 3: Make Marketplace reminders represent only actionable work

Update `.github/workflows/release.yml` so a successful new stable release:

1. creates/deduplicates its own confirmation issue;
2. closes older open issues whose exact title matches
   `Marketplace release confirmation: v*`, with a comment that they were
   superseded by the new tag;
3. never closes unrelated issues or the current tag's issue.

Use strict title matching and the existing `gh` CLI; keep idempotency on reruns.
Add workflow structure tests for search scope, current-tag exclusion, and close
behavior.

After the PR merges, manually close the currently stale #98/#99/#104/#111 with
the same superseded rationale if the workflow cannot retroactively run.

**Verify**: a script-level fixture or shell extraction test proves only exact
older reminder titles are selected.

### Step 4: Document contributor and security operations

Link the new files from `CONTRIBUTING.md` and the synchronized READMEs where
appropriate. Update `RELEASING.md` to state the reminder lifecycle and remote
security/branch-protection verification expected after repository-admin changes.

Do not add a new large README section solely to raise a GitHub percentage.

**Verify**: docs sync and link-target tests pass.

### Step 5: Run the full PR gate and merge

Run all local gates. Open a PR in English, wait for:

- drift
- lint
- Python 3.9/3.10/3.12
- Node 16/20/22
- Action self-test

to pass, then squash-merge and delete the branch. Do not change remote settings
from an unmerged branch.

### Step 6: Apply remote security settings with verification

From the merged, up-to-date main:

1. capture current `security_and_analysis` JSON;
2. enable, when the public-repository API/account supports them:
   - private vulnerability reporting;
   - secret scanning;
   - push protection;
   - validity checks;
   - Dependabot security updates;
3. re-fetch and assert statuses.

Use `gh api --input FILE` with a JSON object, not form-string coercion. If GitHub
returns 4xx for an unavailable feature, stop and record the exact unsupported
setting; do not silently claim success.

Check open alerts without printing secret values.

### Step 7: Require the proven CI contexts without deadlocking maintenance

Update main branch protection to require strict status checks for the nine PR
contexts listed in Current state and require conversation resolution. Preserve:

- no force pushes/deletions;
- one approving review;
- admin bypass (`enforce_admins: false`) for the current single-maintainer
  merge workflow.

Before applying, confirm current successful check names from a recent PR.
Afterward, create or use the next implementation PR to prove all required
contexts report and merge remains possible after green CI.

If GitHub's API requires sending the full branch-protection object, preserve
every existing field explicitly; never send a partial object that drops review
requirements.

### Step 8: Record the operational contract in AGENTS.md

Condense a root invariant covering:

- community/security files stay truthful;
- npm and Action Dependabot updates stay review-gated;
- remote security statuses and required checks are part of release/maintenance
  verification;
- admin bypass exists only to avoid self-approval deadlock, never to skip red
  CI.

Keep `AGENTS.md` below the strict D4 threshold and Grade A; shorten older prose
without dropping its semantics if needed.

Because Plan 015 makes the self-eval evidence byte-bound, refresh and offline
regrade `benchmark/self-eval/results-after.json` in the same PR, then stamp the
new `AGENTS.md` digest and pass `--require-current-evidence`. Do not claim a
fresh model run.

### Step 9: Final verification

Verify:

- GitHub community profile recognizes issue/PR/CoC files;
- remote security statuses match supported target values;
- branch protection lists all required CI contexts;
- stale Marketplace reminders are closed, current reminder behavior remains;
- a real follow-up PR passes required checks;
- local full gate and strict drift are green.

Mark Plan 017 DONE.

## Test plan

- Community template frontmatter/required fields and safe wording.
- Dependabot contains npm + GitHub Actions.
- PR template includes tests/docs/safety/release classification.
- Release reminder exact-title selection, current exclusion, idempotent close.
- Workflow pins remain immutable.
- Public-registry fresh install.
- Remote settings verified through read-back, not assumed from PATCH success.

## Done criteria

- [x] Community profile recognizes security/contribution templates (GitHub
  read-back: 100% community health).
- [x] Vulnerability reports have a private supported route (Private
  Vulnerability Reporting read-back: enabled).
- [x] npm and GitHub Actions receive weekly Dependabot updates.
- [x] New stable releases supersede old Marketplace reminders safely; existing
  #98, #99, #104, and #111 were closed as superseded.
- [x] Supported secret scanning/push protection/Dependabot settings are enabled
  and read back as enabled.
- [x] Main requires every proven PR CI context plus conversation resolution.
- [x] Admin bypass remains documented solely for self-approval deadlock.
- [x] Fresh public-registry `npm ci` passes.
- [x] `npm run check` passes and strict self-drift remains Grade A.

## Completion evidence (2026-07-15)

- File PR #143 passed all nine CI contexts and merged before any remote setting
  changed.
- Remote read-back after the merged PR:
  - community profile: 100%;
  - Private Vulnerability Reporting: enabled;
  - secret scanning: enabled;
  - push protection: enabled;
  - Dependabot security updates: enabled;
  - secret-scanning validity checks: unavailable/disabled for this
    repository/account even after an accepted repository PATCH, so they are
    explicitly not claimed as enabled;
  - required status checks: strict `drift`, `lint`, Node 16/20/22,
    `self-test`, Python 3.9/3.10/3.12;
  - conversation resolution: enabled;
  - one approving review retained; force pushes/deletions disabled; admin
    enforcement remains disabled for sole-maintainer self-approval deadlock.
- Branch-protection API diagnostics:
  - the first complete request failed because an organization-only
    `dismissal_restrictions` object was included;
  - the second failed because GitHub still requires top-level
    `restrictions` for a personal repository;
  - the successful payload omitted dismissal restrictions but preserved
    `"restrictions": null`, then read back every protected setting.
- This documentation-only completion PR is the live required-context proof. It
  must pass all nine checks before the admin squash merge; admin bypass is not
  used to skip any failing/pending context.

## STOP conditions

- A required security feature is unavailable for this public repository/account.
- Required contexts differ from recent real PR check-run names.
- Branch-protection mutation would remove existing review requirements or
  deadlock the only maintainer.
- A community file would require publishing private contact information the
  maintainer has not approved.
- Marketplace cleanup cannot select exact reminder titles safely.
- Verification fails twice after a reasonable correction.

## Maintenance notes

Repository settings are production configuration. Review them after workflow
job renames, ownership changes, or GitHub plan changes. A green admin merge is
acceptable only after every required check passes; admin bypass is not a release
shortcut.
