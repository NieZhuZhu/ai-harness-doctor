# Plan 019: Restore public-registry dependency update automation

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat e4992c8..HEAD -- package-lock.json .github/dependabot.yml tests/test_action_metadata.py CONTRIBUTING.md RELEASING.md AGENTS.md benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json benchmark/self-eval/results-after-graded.json benchmark/self-eval/README.md README.md README.zh-CN.md README.ja.md SKILL.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug / supply chain / dx / docs
- **Planned at**: commit `e4992c8`, 2026-07-15

## Why this matters

Plan 017 enabled weekly npm Dependabot updates as part of the public repository
trust baseline, but the first two real update jobs both failed. Every resolved
tarball in `package-lock.json` points at an internal `bnpm.byted.org` host that
GitHub's public Dependabot runner cannot resolve, so the advertised automation
cannot inspect or update any of the three direct development dependencies.

This is now a reproduced operational bug, not provenance noise. Normalize the
lockfile to the public npm registry without changing selected versions, add a
gate that prevents private registry hosts from returning, and correct the stale
self-bootstrap eval wording discovered in the independent core audit.

## Current state

- `.github/dependabot.yml:13-24` enables a weekly grouped npm update:

  ```yaml
  - package-ecosystem: "npm"
    directory: "/"
    schedule:
      interval: "weekly"
    groups:
      node-dev-tooling:
        dependency-type: "development"
  ```

- `package-lock.json` contains 71 `resolved` URLs, all on the internal host.
  Representative evidence at `package-lock.json:23-26`:

  ```json
  "node_modules/@eslint-community/eslint-utils": {
    "version": "4.9.1",
    "resolved": "https://bnpm.byted.org/@eslint-community/eslint-utils/-/eslint-utils-4.9.1.tgz",
    "integrity": "sha512-..."
  }
  ```

- Dependabot runs
  [#29408386768](https://github.com/NieZhuZhu/ai-harness-doctor/actions/runs/29408386768)
  and
  [#29409694079](https://github.com/NieZhuZhu/ai-harness-doctor/actions/runs/29409694079)
  failed. The latest log reports `private_source_timed_out` for
  `@eslint/js`, `eslint`, and `prettier`, with source `bnpm.byted.org`.

- A clean temporary directory containing only `package.json`, followed by:

  ```bash
  npm install --package-lock-only --ignore-scripts --no-audit --no-fund \
    --registry=https://registry.npmjs.org
  ```

  produces the same lockfile schema and package count with 71 public
  `registry.npmjs.org` URLs and zero private URLs. Because current semver ranges
  may have advanced since the committed lockfile, blindly regenerating from
  only `package.json` may also update selected versions; the implementation
  must preserve the committed graph unless that update is intentionally
  reviewed.

- The lockfile can be normalized without changing dependency metadata by
  rewriting only each `resolved` host from the known npm-compatible mirror to
  `registry.npmjs.org`, then verifying package keys, versions, integrity hashes,
  dependency edges, and root metadata remain byte-equivalent after removing
  only `resolved` fields.

- The public npm package has zero runtime dependencies; all 71 nodes are
  development tooling. `npm audit --registry=https://registry.npmjs.org`
  currently reports zero vulnerabilities.

- Independent docs audit found stale self-bootstrap claims:
  - `README.md:287` says “The eval gate remains soft”;
  - `README.zh-CN.md:287` and `README.ja.md:287` translate the same claim;
  - `SKILL.md:216` says “The eval gate stays soft.”

  In contrast, `.github/workflows/harness-drift.yml:77-90` unconditionally
  requires current tasks/`AGENTS.md` evidence and `--fail-under 80`. Generic
  shipped guard templates remain optional; this repository's self-guard is
  hard.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Registry policy test | `python3 -m unittest discover -s tests -p 'test_action_metadata.py' -v` | all pass |
| Docs sync | `python3 scripts/check_readme_sync.py` | OK |
| Public lock install | isolated temp-dir `npm ci --ignore-scripts --registry=https://registry.npmjs.org --no-audit --no-fund` | exit 0 |
| Public audit | `npm audit --registry=https://registry.npmjs.org --json` | zero high/critical; currently zero total |
| Package dry run | `npm pack --dry-run --json` | exit 0; expected package contents only |
| Full gate | `npm run check` | exit 0 |
| Evidence gate | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0 |
| Self scan | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0; grade A |

## Scope

**In scope**:

- `package-lock.json`
- `.github/dependabot.yml` only if a comment/policy clarification is needed
- `tests/test_action_metadata.py`
- `CONTRIBUTING.md`
- `RELEASING.md`
- synchronized `README.md`, `README.zh-CN.md`, `README.ja.md`
- `SKILL.md`
- `AGENTS.md`
- evidence-bound `benchmark/self-eval/` files if `AGENTS.md` changes
- `plans/README.md`
- retriggering and verifying the real npm Dependabot update job after merge

**Out of scope**:

- Changing direct dependency ranges in `package.json`.
- Intentionally upgrading eslint, Prettier, or transitive packages in this PR.
- Adding npm runtime dependencies.
- Adding credentials or a private-registry block to Dependabot.
- Normalizing historical npm package metadata or already-published tarballs.
- Changing release credentials, provenance, Action tags, or the npm publish
  workflow.
- Fixing the separately vetted manual `deprecate` workflow input interpolation;
  it is a trusted-maintainer-only surface and should be a separate security PR
  if selected later.
- Claiming GitHub's Dependabot job is fixed without a successful post-merge
  run/read-back.

## Git workflow

- Branch: `fix/public-dependency-update-source`
- Commit: `fix(deps): restore public registry updates`
- One focused bugfix/operations PR.
- Do not push or open a PR unless the operator instructed it. When instructed,
  squash-merge only after every required check is green.

## Steps

### Step 1: Add a failing public-registry policy test

Extend `tests/test_action_metadata.py` with a lockfile test that:

- parses `package-lock.json` as JSON;
- inspects every non-empty `resolved` URL;
- permits only HTTPS URLs on `registry.npmjs.org` for npm package tarballs;
- reports the package key and hostname, never URL credentials/query data;
- asserts at least one resolved dependency was examined so an accidentally
  empty lockfile cannot pass.

Keep the rule deliberately repository-specific. Do not put a general “private
registries are bad” rule into the product scanner; private registries are valid
for many consumers.

**Verify**: the new test fails at `e4992c8` and identifies the internal hostname
without printing any credential material.

### Step 2: Normalize only the lockfile source host

Transform each npm tarball `resolved` URL from the known mirror host to the
equivalent path on `https://registry.npmjs.org`. Do not run an unconstrained
fresh resolution that picks newer versions.

Before writing, save or programmatically derive a normalized copy of the
original lockfile with all `resolved` fields removed. After writing, assert:

- lockfile version unchanged;
- identical package-key set;
- identical package versions;
- identical integrity hashes;
- identical dependency/peer/optional edges and engine metadata;
- identical root `devDependencies`;
- only `resolved` strings differ.

If any non-URL field changes, revert and STOP rather than mixing a dependency
upgrade into this repair.

**Verify**: the policy test passes, private-host count is zero, public-host
count is 71 at the planned graph, and the normalized before/after JSON objects
are equal.

### Step 3: Prove public install and update discovery locally

Copy only `package.json` and the normalized `package-lock.json` to an isolated
temporary directory. With no user `.npmrc` inherited where feasible, run:

```bash
npm ci --ignore-scripts --registry=https://registry.npmjs.org --no-audit --no-fund
npm outdated --registry=https://registry.npmjs.org
```

`npm ci` must succeed. `npm outdated` may exit 1 when updates exist; treat that
as successful discovery if it produces normal package/update output and no
network/private-source error.

Then run the public audit and package dry run from the repository.

**Verify**: no command attempts to reach `bnpm.byted.org`; install succeeds and
dependency metadata is readable from the public registry.

### Step 4: Correct docs and make the operational invariant durable

Update `CONTRIBUTING.md` / `RELEASING.md` with a concise invariant:

- the committed public-project lockfile must not bind public dependencies to a
  private registry;
- weekly npm Dependabot is considered healthy only after a real successful
  update check;
- dependency PRs still require the full Node/Python/Action matrix.

Correct the self-bootstrap paragraph in all three READMEs and `SKILL.md`:

- generic shipped eval gating remains optional;
- this repository's committed evidence is an unconditional freshness + health
  gate;
- only PR-review posting tolerates a missing/limited token.

Add one compact `AGENTS.md` sentence tying lockfile source portability to the
Dependabot operational baseline. Keep the file below the strict D4 threshold.

Because `AGENTS.md` is evidence-bound, honestly refresh/regrade the existing
manual-protocol result and update its evidence digest. Do not claim a model run.

**Verify**: docs sync, evidence freshness, 20/20 score, and strict drift pass.

### Step 5: Run full PR gates and merge

Run every local command in the table. Open an English PR describing both the
real Dependabot run evidence and the normalized-graph proof. Wait for all nine
required contexts to succeed before squash-merging and deleting the branch.

Do not use admin bypass while any required check is red or pending.

### Step 6: Re-run and verify real Dependabot after merge

From the merged main branch, trigger “Check for updates” for the npm ecosystem
through GitHub's Dependency graph UI (or wait for the next scheduled run if no
stable API exists). Read the resulting Actions log/status:

- no `private_source_timed_out`;
- no request to `bnpm.byted.org`;
- job conclusion `success`, whether or not it opens a PR.

Record the successful run URL in Plan 019 completion evidence. If GitHub still
fails for another reason, leave the plan BLOCKED with the exact non-sensitive
error and do not claim completion.

## Test plan

- Lockfile contains resolved dependencies and every host is public npm HTTPS.
- No non-`resolved` lockfile field changes during normalization.
- Isolated public-registry `npm ci` succeeds.
- Public audit remains clean.
- Dependabot configuration still has both `github-actions` and `npm`.
- Self-bootstrap docs accurately distinguish generic optional eval from the
  repository's hard evidence+health gate.
- Evidence-bound self-eval is refreshed after `AGENTS.md` changes.

## Done criteria

- [x] `package-lock.json` contains zero `bnpm.byted.org` URLs and no unexpected
  registry host.
- [x] Package keys, versions, integrity hashes, and dependency graph are
  unchanged except for `resolved` URLs.
- [x] Isolated public-registry `npm ci` succeeds.
- [x] `npm audit` has no high/critical vulnerability.
- [x] All self-bootstrap docs describe the hard evidence + health gate
  accurately.
- [x] A post-merge npm Dependabot update job succeeds without private-source
  errors, and its run URL is recorded.
- [x] `npm run check`, evidence freshness, and strict drift pass.
- [x] Only in-scope files are modified.

## Completion evidence (2026-07-15)

- Fix PR [#148](https://github.com/NieZhuZhu/ai-harness-doctor/pull/148)
  passed all nine required contexts and was squash-merged as `fc585b8`.
- The lockfile repair changed exactly 71 `resolved` URLs. A normalized JSON
  comparison with every `resolved` field removed proved all package keys,
  versions, integrity hashes, dependency edges, engines, and root metadata
  remained identical.
- An isolated `HOME` plus isolated copies of `package.json` /
  `package-lock.json` completed public-registry `npm ci` with 71 packages and
  no private-source access. Public npm audit reported zero vulnerabilities.
- The evidence-bound self-eval was honestly regraded from the manual protocol:
  21/21, Grade A, with current task and `AGENTS.md` SHA-256 evidence.
- GitHub's Dependency graph “Check for updates” produced Dependabot update job
  `1461813115` and Actions run
  [29413064827](https://github.com/NieZhuZhu/ai-harness-doctor/actions/runs/29413064827)
  at main SHA `fc585b8`. It completed successfully in 46 seconds. Its log
  contains successful `registry.npmjs.org` responses and no
  `bnpm.byted.org`, `private_source`, or timeout error.
- The successful update job created
  [PR #149](https://github.com/NieZhuZhu/ai-harness-doctor/pull/149) for
  eslint `10.6.0` → `10.7.0` and Prettier `3.9.4` → `3.9.5`. It changed only
  their lockfile records, passed all nine required contexts, and was
  squash-merged as `5bd7ff8`.

## STOP conditions

- Normalization requires changing a selected dependency version or integrity
  hash.
- Any URL contains credentials or a query string; do not copy it into tests,
  plans, commits, or PR text.
- The project intentionally requires an internal fork whose tarball is not
  available on public npm.
- Public `npm ci` fails because an artifact is genuinely unavailable.
- GitHub provides no way to run/observe a post-merge update check; mark the
  remote verification pending instead of claiming success.
- Verification fails twice after a reasonable correction.

## Maintenance notes

Private registries are valid in private projects; this invariant exists because
this is a public zero-runtime-dependency package whose Dependabot runs on
GitHub-hosted infrastructure. Future dependency updates must preserve public
lockfile sources, immutable workflow Action pins, and the full compatibility
matrix.
