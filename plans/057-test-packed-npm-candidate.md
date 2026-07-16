# Plan 057: Execute the packed npm candidate before publication

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md` unless a reviewer maintains the index separately.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 30675ba..HEAD -- \
>   scripts/check_package_candidate.py tests/test_package_candidate.py \
>   package.json .github/workflows/test.yml .github/workflows/release.yml \
>   tests/test_action_metadata.py RELEASING.md \
>   plans/057-test-packed-npm-candidate.md plans/README.md
> ```
>
> If any in-scope file changed, compare the "Current state" excerpts against
> live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: M
- **Risk**: MED
- **Depends on**: Plans 005, 025, 028, and 034 (DONE)
- **Category**: bug / supply chain / tests / release reliability
- **Planned at**: commit `30675ba`, 2026-07-17
- **Implementation**: DONE — PR #251 (plan) / PR #252 (impl),
  squash-merged to `main` as `0b49830`; all nine required contexts green.

## Why this matters

Required PR CI and the tag-driven release preflight run the current checkout,
then call `npm pack --dry-run`. They never install and execute the actual npm
tarball candidate. A broken `package.json#files` allowlist can therefore pass
all required checks and both bundled Action preflights, publish an immutable npm
version, and fail only in the post-publish verification job.

The package is the CLI's public distribution boundary. Add one deterministic,
offline pack-install-self-test that proves the candidate tarball contains and
can dispatch every shipped engine before PR merge and before npm publication.
Keep the existing post-publish exact-registry verification; the two checks
prove different boundaries.

## Mechanical reproduction

At current `main`, an isolated worktree removed only `"scripts/*.py"` from
`package.json#files`, leaving all source files in the checkout.

Observed:

```text
node --test bin/*.test.js                  exit 0
npm pack --dry-run --json                  exit 0
pack record                                hasCli=true, hasScan=false
node bin/cli.js doctor --self-test --json  exit 0, ok=true
npm install <local-tarball>                exit 0
<installed>/bin/cli.js doctor --self-test  exit 1, ok=false
```

The installed package reported `missing scan.py`, `missing explain.py`,
`missing canonicalize.py`, `missing check_drift.py`, `missing pr_review.py`,
and `missing eval_run.py`. This is not hypothetical: every existing required
signal stayed green until the real tarball was executed.

## Current state

### PR CI checks checkout behavior, not installed package behavior

`.github/workflows/test.yml`:

- Python matrix runs source tests.
- Node matrix runs `node --test bin/*.test.js`.
- Each Node job ends with:

  ```yaml
  - name: Check npm package contents
    run: npm pack --dry-run
  ```

`npm pack --dry-run` proves packing succeeds and prints a list. It does not
prove required files are present or that installed CLI dispatch works.

### Release preflight also uses checkout/bundled code

`.github/workflows/release.yml`:

- runs source Python tests and checkout CLI syntax/help;
- calls `npm pack --dry-run`;
- invokes `uses: ./` bundled scan and drift;
- only then publishes;
- installs the exact npm registry version in `verify-published-action`, after
  publication is already immutable.

Bundled `uses: ./` selects `$ACTION_PATH/bin/cli.js` and the checkout's
`scripts/`, so it cannot detect a tarball allowlist omission.

### Existing package assertions are partial

`tests/test_action_metadata.py` asserts `package.json#files` contains `bin` and
that `action-run.js` is not excluded. Historical plans use
`npm pack --dry-run --json` to check individual files. There is no shared
manifest validator, installed-candidate smoke, or required test for all CLI
engine files and runtime imports.

### Public runtime contract is already machine-readable

`node bin/cli.js doctor --self-test --json` reports:

- Node and Python runtime readiness;
- every `SCRIPT_COMMANDS` engine file;
- MCP server presence;
- package version.

This is the right deep smoke after local tarball installation. It should run
with an isolated `HOME`, update checks disabled, no lifecycle scripts, no global
prefix, and no registry access.

## Target contract

1. Add one repository-maintenance verifier that:
   - creates a temporary output/install root;
   - runs `npm pack --json --pack-destination <temp>`;
   - validates the JSON describes exactly one tarball;
   - validates the tarball path stays inside the chosen temp root;
   - installs that local tarball under another temp prefix with
     `npm install --ignore-scripts --no-audit --no-fund`;
   - sets an isolated temporary `HOME` and disables update checks;
   - executes the installed `bin/cli.js doctor --self-test --json`.
2. The installed self-test must exit 0, parse as JSON, report `ok=true`, and
   report the same exact version as source `package.json`.
3. Assert all named doctor checks are healthy, not only top-level `ok`:
   Node, Python, every public script command, and MCP server.
4. Assert the installed CLI and package root resolve inside the isolated install
   prefix. Never use global npm, real HOME, or the checkout source as a fallback.
5. Assert test-only and maintenance-only files stay excluded:
   - `bin/*.test.js`;
   - `scripts/check_readme_sync.py`;
   - `scripts/gen_adapters.py`.
6. Assert the required public distribution surface is present:
   - package metadata/license and all seven READMEs;
   - `SKILL.md`;
   - `bin/cli.js`, `bin/runtime.js`, `bin/mcp-server.js`,
     `bin/action-run.js`, `bin/action-report.js`;
   - every production `scripts/*.py` selected by the allowlist;
   - commands, adapters, assets, and references needed by install/guard/runtime.
7. Derive production script expectations from the checkout plus the explicit
   two-file maintenance exclusion, or from one clear package-manifest helper.
   Do not duplicate a long hand-maintained engine list across workflow YAML.
8. The verifier must fail mechanically for the reproduced omission of
   `"scripts/*.py"` and for an excluded CLI/runtime helper.
9. Run the verifier in:
   - required PR CI (one job is sufficient; do not multiply identical pack
     installs across Node matrix entries);
   - release `test` before the `publish` job can start.
10. Keep post-publish registry/floating-Action verification unchanged. A local
    candidate proves package construction; registry verification proves the
    immutable artifact actually published and became installable.
11. The verifier may use Node/Python/npm already required by the project but no
    third-party runtime dependency, network registry, or npm credentials.
12. Temporary artifacts must be deleted even on failure where practical and
    remain outside the repository/real HOME.

## Design

Prefer a Python 3.9 stdlib maintenance script,
`scripts/check_package_candidate.py`, excluded from the npm package like the
other maintenance scripts. It can safely orchestrate subprocesses with argv
arrays and parse JSON without shell interpolation.

Suggested structure:

```python
def pack_candidate(root, temp_root): ...
def validate_pack_record(record, expected_files): ...
def install_candidate(tarball, install_root, home): ...
def run_installed_self_test(package_root, home): ...
def main(): ...
```

Use `subprocess.run([...], check=False, capture_output=True, text=True,
timeout=<finite>)`; no `shell=True`. On failure, print a concise stage-specific
message and sanitized stderr tail. Do not print environment values or user
paths beyond the temporary root.

Package inventory may come from `npm pack --dry-run --json` or the real pack
record. Use the real pack once so the bytes installed are the same candidate
whose inventory is checked.

Add `test:package` (or `check:package`) in `package.json` and call it from:

- the lint or a dedicated step in one existing required job;
- release `test` in place of the weak `npm pack --dry-run` step.

Do not add a tenth required branch-protection context; keep this inside an
existing required job so repository operations remain stable.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Verifier tests | `python3 -m unittest tests.test_package_candidate -v` | all pass |
| Candidate smoke | `python3 scripts/check_package_candidate.py` | packed/installed candidate passes every check |
| Python lint | `python3 -m ruff check scripts/check_package_candidate.py tests/test_package_candidate.py` | exit 0 |
| Workflow tests | `python3 -m unittest tests.test_action_metadata -v` | all pass |
| Full gate | `npm run check` | all lint/tests plus required candidate verification pass |
| Workflow lint | `actionlint .github/workflows/test.yml .github/workflows/release.yml` | exit 0 |
| Self scan | `python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json --check-baseline --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts --no-report-file` | exit 0 |
| Self drift | `python3 scripts/check_drift.py . --strict` | 100/100, Grade A |
| Self eval | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | 38/38, Grade A |

## Scope

**In scope**:

- new `scripts/check_package_candidate.py`
- new `tests/test_package_candidate.py`
- `package.json`
- `.github/workflows/test.yml`
- `.github/workflows/release.yml`
- `tests/test_action_metadata.py`
- `RELEASING.md`
- `plans/057-test-packed-npm-candidate.md`
- `plans/README.md`

**Out of scope**:

- Changing the current package allowlist unless the verifier exposes a real
  existing omission.
- Publishing a test version or using a fake npm registry.
- Removing post-publish npm/Action verification.
- Adding a new required check context or changing branch protection.
- npm trusted publishing, credentials, provenance, tags, or Marketplace policy.
- Lifecycle scripts (`prepack`, `prepare`, `postinstall`) or automatic code
  generation during pack/install.
- Running install scripts for the local candidate.
- Global npm installation or the real user HOME/cache/prefix.
- Testing every CLI subcommand end-to-end; `doctor --self-test` plus inventory
  validates dispatch prerequisites, existing source tests validate behavior.
- `npm run format` policy.
- Runtime dependencies.

## Git workflow

- Branch: `test/057-packed-npm-candidate`.
- Commit: `test(package): execute the packed npm candidate`.
- One focused supply-chain/test PR; do not push directly to `main`.
- Wait for all nine required checks before squash merge:
  `drift`, `lint`, Node 16/20/22, Python 3.9/3.10/3.12, and `self-test`.
- Test/release hardening only: patch-release material if released alone.

## Steps

### Step 1: Characterize the current blind spot as a red test

Add tests around a small verifier seam. Build a temporary minimal copy or
temporarily modify a copied `package.json` so `"scripts/*.py"` is excluded while
source files remain.

Assert:

- checkout Node tests/package packing can still succeed;
- candidate inventory has no `scripts/scan.py`;
- local tarball installation succeeds;
- installed `doctor --self-test --json` exits non-zero with missing engines;
- the new verifier rejects this state.

Do not mutate the real worktree package manifest.

**Verify**:

```bash
python3 -m unittest \
  tests.test_package_candidate.PackageCandidateTests.test_missing_script_allowlist_fails \
  -v
```

Expected before verifier implementation: RED. Expected after Steps 2–3: PASS.

### Step 2: Validate the real packed inventory

Implement one real `npm pack --json --pack-destination` in a temporary root.
Parse the single record and validate:

- contained tarball path;
- exact package version;
- required surface present;
- test/maintenance exclusions absent;
- no duplicate/unsafe member paths if the metadata exposes them.

Avoid shell parsing of the generated filename. Resolve it from validated JSON
and confirm containment before use.

**Verify**: current package inventory passes; the copied broken allowlist fails
with a precise missing-file list.

### Step 3: Install and execute only the candidate bytes

Install the local tarball into an isolated prefix with lifecycle scripts
disabled. Use the installed package path, not the checkout:

```text
<temp>/install/node_modules/ai-harness-doctor/bin/cli.js
```

Run `doctor --self-test --json` with:

- isolated `HOME`;
- `AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1`;
- finite subprocess timeouts;
- inherited PATH only for Node/Python/npm discovery.

Require exact version, `ok=true`, and every check `ok=true`.

**Verify**: current package succeeds; missing scripts or helpers fail before any
publication.

### Step 4: Wire one required PR job and release preflight

Add a package script and call it in one existing required CI job. Recommended:
lint, after dependencies/ruff install and normal lint, or one Node matrix member
under an explicit condition. Do not run it three times.

Replace release's bare `npm pack --dry-run` step with the candidate verifier.
Keep it before bundled Action fixtures and therefore before `publish` can
start.

Update structural tests to assert:

- required PR workflow executes the verifier exactly once;
- release executes it before all publish-side writes;
- bare preview is not the sole package gate;
- post-publish verification still exists.

Run actionlint.

### Step 5: Document the two-stage package proof

Update `RELEASING.md`:

- pre-publish packs, installs, and self-tests the exact local candidate;
- post-publish still installs the exact registry version through the floating
  Action;
- candidate verification is offline and does not claim registry provenance;
- both are required because npm publication is immutable.

No README/SKILL update is needed unless the user-facing release process is
described there beyond the current generic wording.

### Step 6: Run all gates and review

Run every command in the table.

- **Standards**: Python 3.9 stdlib-only, no shell interpolation, finite process
  bounds, isolated HOME/prefix, tests in the same PR.
- **Spec**: installed bytes come from the real tarball, all engines/version
  healthy, exactly one required PR execution, pre-publish ordering, post-publish
  verification retained.

Open one implementation PR and wait for all nine contexts before squash merge.

## Test plan

- Current real package inventory/install/self-test passes.
- Missing `scripts/*.py` allowlist fails.
- Missing a required bin helper fails.
- Test and maintenance files remain excluded.
- Malformed/multiple pack records fail.
- Escaping tarball path fails containment.
- Install failure and installed self-test failure are concise/non-zero.
- Version mismatch and one unhealthy doctor check fail.
- Workflow structure executes candidate verification once in required PR CI and
  before release publish.
- Existing release identity, bundled Action, post-publish npm, Marketplace, and
  Node/Python matrix tests remain green.

## Done criteria

- [x] Required PR CI installs and executes the exact local npm candidate once;
      verified in required lint job `87762189365`.
- [x] Release preflight does the same before npm publish is reachable.
- [x] Missing scripts/helpers in `package.json#files` fail before merge/publish.
- [x] Candidate version and every doctor self-test check are healthy.
- [x] Candidate install uses isolated HOME/prefix, local tarball, disabled
      lifecycle scripts, finite timeouts, and no registry/credential.
- [x] Required/excluded inventory is mechanically checked.
- [x] Post-publish exact npm/floating Action verification remains unchanged.
- [x] No new required status context or runtime dependency is added.
- [x] Full local gates (812 Python + 47 Node), actionlint v1.7.12, strict drift
      100/A, and self eval 38/38 pass.
- [x] All nine PR checks pass and the implementation is squash-merged.

## STOP conditions

Stop and report back if:

- `npm pack --json` cannot identify a contained local tarball deterministically;
- local tarball install requires lifecycle scripts or registry access;
- installed self-test resolves scripts from the checkout rather than package;
- current valid package is already missing a required production file;
- the verifier requires changing public package contents unrelated to a proven
  omission;
- running once cannot be expressed inside an existing required job;
- release preflight ordering cannot block publish;
- post-publish registry verification would need removal or weakening;
- any required CI context is red or pending at merge time.

## Maintenance notes

- `npm pack --dry-run` is inventory preview, not executable package evidence.
  Keep the candidate verifier as the authoritative pre-publication package gate.
- Run the verifier once per PR, not once per Node/Python matrix leg.
- Doctor self-test is intentionally the deep package-dispatch seam. When a new
  public engine/helper is added, update doctor and candidate inventory together.
- Keep post-publish verification: local pack construction and public registry
  identity/availability are separate claims.
- Never add lifecycle scripts merely to make the candidate test pass; shipped
  bytes must already be complete in a clean checkout.
