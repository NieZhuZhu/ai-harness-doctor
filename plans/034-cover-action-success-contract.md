# Plan 034: Self-test every public GitHub Action success path

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 777f962..HEAD -- action.yml .github/workflows/action-self-test.yml .github/workflows/release.yml tests/test_action_metadata.py README.md README.zh-CN.md README.ja.md SKILL.md RELEASING.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: MED
- **Depends on**: none
- **Category**: tests / GitHub operations / release / supply chain / docs
- **Planned at**: commit `777f962`, 2026-07-16

## Why this matters

The Marketplace Action publicly supports two commands (`scan`, `drift`) and two
implementation sources (`bundled`, npm version/tag). Required self-test and
release workflows exercise only bundled `scan` successfully. A broken drift
dispatch or npm override install can therefore ship while the repository,
floating major tag, npm publish, and Marketplace page all appear green.

The Action contract needs an explicit success matrix. Pull requests must prove
the exact checked-out bundled implementation can run both commands and that the
published npm override path remains installable in an isolated location.
Stable release verification must then bind the newly published exact npm
version to the same release as the floating Action ref. This is deeper than the
existing invalid-command/tail-security checks and does not reopen the deferred
free-form `args` interface.

## Current state

- `action.yml:11-29` exposes:

  ```yaml
  command:
    description: "Subcommand to run (scan or drift)."
    default: "scan"
  version:
    description: "Implementation to run: bundled (selected Action ref) or an npm version/tag."
    default: "bundled"
  ```

  `action.yml:46-69` chooses the selected Action ref for `bundled`; otherwise it
  deletes and recreates `$RUNNER_TEMP/ai-harness-doctor-action`, runs
  `npm install ai-harness-doctor@$INPUT_VERSION`, and executes that package.

- `.github/workflows/action-self-test.yml:25-45` has one successful local
  Action invocation: `command: scan`, default `version: bundled`. Its other
  Action calls deliberately fail a security gate or invalid command. There is
  no successful `drift` invocation and no npm override invocation.

- `.github/workflows/release.yml:43-64` preflights only bundled `scan`.
  `.github/workflows/release.yml:330-360` verifies the published floating Action
  only with bundled `scan`, then checks its SARIF driver version. The exact npm
  package just published is never executed through the Action wrapper.

- `tests/test_action_metadata.py:109-117` requires three local Action calls,
  SARIF validation, tail-security failure, and invalid-command failure. It does
  not assert a successful command/source matrix. The release order test at
  `tests/test_action_metadata.py:671-688` similarly checks only generic
  preflight/public steps.

- Recent successful workflow logs through `v1.8.1` all show successful Action
  inputs `command: scan`, `version: bundled`. No successful log exercises
  `command: drift` or a non-bundled version.

- Pull requests cannot install the unmerged package version from npm. They can,
  however, test the install/dispatch mechanism against the current published
  exact version from `package.json`. The tag-driven stable release can test the
  newly published exact version after `publish` completes.

## Target contract

1. Keep `version: bundled` as the default and preserve current Action inputs,
   outputs, exit propagation, install flags, and zero runtime dependencies.
2. Required `action-self-test` successfully exercises:
   - bundled `scan` against this checkout;
   - bundled `drift` against a deterministic clean fixture;
   - npm override `scan` using the exact current `package.json` version known to
     be published on PR/main.
3. The npm override test proves the installed implementation actually ran by
   asserting SARIF `tool.driver.version` equals the requested exact version. It
   also proves installation stayed under a dedicated `$RUNNER_TEMP` directory;
   it must not inspect or write the real user HOME/global npm prefix.
4. Do not run npm override and another Action invocation concurrently: the
   current composite intentionally owns one fixed temporary install directory.
5. The PR npm test validates the already-published compatibility path, not the
   unmerged source. Bundled tests remain the evidence for current code.
6. Release preflight successfully runs both bundled `scan` and bundled `drift`
   before npm publication. A deterministic fixture avoids making release
   success depend on incidental drift in the repository checkout.
7. Stable post-publish verification executes the separately checked-out
   floating Action at `./published-action` twice:
   - bundled `scan`, proving the floating ref's own code and driver version;
   - npm override `drift` with `version` equal to the exact just-published
     `package.json` version, proving the Action's install path reaches that
     immutable package.
8. Post-publish validation asserts both SARIF documents are 2.1.0, both contain
   a run/results array, and both driver versions equal the release version.
9. Prereleases retain current policy: no stable floating-tag verification.
   Pre-publish bundled command coverage still runs, but this plan does not add a
   prerelease npm override job.
10. Any npm installation, drift, SARIF, driver-version, or path-isolation
    failure fails the workflow and prevents the Marketplace reminder. Do not add
    `continue-on-error` or `|| true` to success paths.
11. Existing tail-secret and invalid-command failure tests remain. This plan
    does not redesign `args`, upload SARIF, or add an npm package-build test
    that pretends to be a Marketplace Action test.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Action metadata tests | `python3 -m unittest discover -s tests -p 'test_action_metadata.py' -v` | all pass |
| Workflow lint | `actionlint .github/workflows/action-self-test.yml .github/workflows/release.yml` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | `OK` |
| Full gate | `npm run check` | exit 0 |
| Package preview | `npm pack --dry-run` | exit 0; expected files only |
| Self eval | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0, grade A |
| Self scan | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0, grade A |

## Scope

**In scope**:

- `.github/workflows/action-self-test.yml`
- `.github/workflows/release.yml`
- `tests/test_action_metadata.py`
- `action.yml` only if a testable temporary-install-path output/contract is
  strictly necessary; prefer no production Action change
- synchronized `README.md`, `README.zh-CN.md`, `README.ja.md`
- `SKILL.md`
- `RELEASING.md`
- `plans/README.md`

**Out of scope**:

- Replacing the default bundled implementation with npm.
- Structured `args` or whitespace-preserving argument redesign.
- Uploading SARIF to GitHub Code Scanning.
- Adding new Action commands beyond `scan|drift`.
- Changing scan/drift result semantics or exit codes.
- Testing an unpublished PR tarball through a fake npm registry.
- Changing npm credentials, OIDC/trusted-publishing policy, floating-tag
  strategy, or Marketplace categories.
- Adding a second release workflow or mutable external Action refs.
- Updating `AGENTS.md`; the batch completion PR owns final durable invariants.

## Git workflow

- Branch: `test/action-success-matrix`
- Commit: `test(action): cover command and version success paths`
- One focused Action/release reliability PR.
- Do not push directly to `main`.
- Run actionlint and the full local gate, then wait for all nine required
  contexts before squash-merge/delete.
- This is test/operations hardening, not a user-facing feature. It is patch-level
  unless implementation reveals a real Action behavior bug; stop and reclassify
  instead of hiding that bug inside this PR.

## Steps

### Step 1: Make the public Action matrix a static contract

Extend `tests/test_action_metadata.py` so it fails unless the workflows contain:

- a successful bundled `scan`;
- a successful bundled `drift`;
- a successful exact npm-version override;
- distinct SARIF paths/step IDs;
- driver-version assertions;
- post-publish exact version flow from `package.json`;
- ordering before publish and after floating-tag update;
- no tolerated failure on those success steps.

Assert npm override uses an exact value, not `latest`, `next`, a mutable major,
or arbitrary workflow input. Keep existing invalid-command and tail-security
assertions.

**Verify**: new assertions fail against `777f962` because neither drift success
nor npm override exists.

### Step 2: Add bundled drift and exact published npm coverage to PR self-test

Create a small clean repository under `$RUNNER_TEMP` with a canonical
`AGENTS.md` that makes `drift --sarif` return success. Run `uses: ./` with
`command: drift`, a unique SARIF output, and default bundled version.

Resolve the current exact package version in a preceding shell step and expose
it through `$GITHUB_OUTPUT`. Run a separate `uses: ./` scan with that exact
version. Validate:

- both SARIF versions/runs/results;
- bundled driver equals the checkout package version;
- npm override driver equals the requested exact version;
- `$RUNNER_TEMP/ai-harness-doctor-action/node_modules/ai-harness-doctor`
  exists and resolves inside `$RUNNER_TEMP`.

Do not test against `latest`; CDN/dist-tag movement would make the check
nondeterministic.

**Verify**: actionlint and metadata tests pass locally; the PR's required
`self-test` context proves all three successful calls on GitHub.

### Step 3: Cover both bundled commands before publish

In the release test job, retain bundled scan and add bundled drift against the
same style of deterministic clean fixture. Give every call/output a unique path
and validate driver version against `package.json`.

Keep all success calls before `Publish to npm`; retain invalid-command failure
propagation. Do not use an npm override in pre-publish because the new version
does not yet exist.

**Verify**: tests prove both command success steps precede npm access and cannot
be skipped/tolerated.

### Step 4: Bind the floating Action to the newly published npm version

After the stable publish job moves `vN`, the existing verify job checks out that
ref at `published-action`. Preserve bundled scan, then add a second sequential
call:

```yaml
uses: ./published-action
with:
  command: drift
  version: <exact package version output>
  path: <clean fixture>
```

Expose `package_version` as a publish-job output from the already validated
release metadata step; do not recompute from an untrusted dispatch input. Check
both driver versions equal that exact value and ensure the npm install directory
is isolated.

The Marketplace reminder must continue to require the whole verify job.

**Verify**: static order/identity tests and actionlint pass.

### Step 5: Document the verification evidence

Update the three READMEs, `SKILL.md`, and `RELEASING.md` with a concise matrix:

- PR/main: current bundled scan+drift plus exact currently published npm
  compatibility;
- pre-publish: exact tagged bundled scan+drift;
- stable post-publish: floating bundled scan plus exact newly published npm
  drift.

State clearly that PR npm coverage does not validate unmerged package bytes and
that prereleases do not move/verify stable refs.

**Verify**: docs sync, focused/full tests, package preview, self-eval, self scan,
strict drift, and actionlint.

### Step 6: Capture live GitHub evidence after merge/release

After the implementation PR is merged, inspect the required `self-test` run and
record in the PR completion note (not source files):

- bundled scan success;
- bundled drift success;
- exact npm override success and driver version.

After the batch release, inspect `verify-published-action` and confirm both the
floating bundled and exact npm override steps succeeded with the release
version before closing the Marketplace reminder. Do not mark this plan DONE
solely from static tests.

**Verify**: the relevant GitHub job logs show all named success steps; no npm or
Action runtime deprecation warning is present.

## Test plan

- Static PR success-matrix assertions.
- Static release ordering and exact-version flow.
- Unique outputs/step IDs and SARIF driver-version checks.
- Temporary install containment assertions.
- actionlint on both workflows.
- Real required self-test run after PR merge.
- Real stable release post-publish run.
- Existing failure propagation, immutable pins, tag identity, prerelease, and
  Marketplace ordering tests remain green.

## Done criteria

- [ ] Required Action self-test succeeds for bundled scan and bundled drift.
- [ ] Required Action self-test succeeds for an exact published npm override.
- [ ] PR npm override reports the exact requested driver version and stays in
      `$RUNNER_TEMP`.
- [ ] Release preflight succeeds for both bundled commands before publish.
- [ ] Stable post-publish verification succeeds for floating bundled code and
      the newly published exact npm version.
- [ ] Marketplace reminder depends on the complete published verification.
- [ ] Prerelease stable-pointer policy is unchanged.
- [ ] Existing failure-path tests remain intact.
- [ ] Trilingual docs, `SKILL.md`, and `RELEASING.md` describe the matrix.
- [ ] Full local and nine required CI gates pass, followed by live release proof.

## STOP conditions

Stop and report back if:

- The current `package.json` version is not actually available from public npm
  during PR self-test.
- A clean drift fixture cannot be made deterministic without bypassing real
  Action behavior.
- Exact npm verification can only run before publish.
- The composite Action's fixed install directory makes required invocations
  race; keep them sequential rather than changing global semantics.
- The implementation requires exposing host paths or writing outside
  `$RUNNER_TEMP`.
- A real Action behavior bug is discovered; split/reclassify it instead of
  landing an expectation-only test.
- Verification fails twice after a reasonable scoped fix.

## Maintenance notes

- Treat the Action contract as the cross-product of command and implementation
  source, not a single happy-path invocation.
- Current-source correctness comes from bundled PR tests; published-artifact
  compatibility comes from exact npm tests. Do not claim one proves the other.
- New Action commands or implementation sources must add a successful
  self-test and release verification path.
- Keep npm override invocations sequential unless `action.yml` gains an
  invocation-unique install directory with its own separately reviewed plan.
