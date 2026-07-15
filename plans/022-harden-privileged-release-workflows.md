# Plan 022: Reject untrusted inputs and off-main tags in privileged npm workflows

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat ced1530..HEAD -- .github/workflows/deprecate.yml .github/workflows/release.yml tests/test_action_metadata.py RELEASING.md CONTRIBUTING.md AGENTS.md benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json benchmark/self-eval/results-after-graded.json benchmark/self-eval/README.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: security / supply chain / tests / docs
- **Planned at**: commit `ced1530`, 2026-07-15

## Why this matters

Two privileged npm workflows trust GitHub ref/input shape more than their
security boundary permits. The manual deprecation workflow inserts dispatcher
strings directly into a generated shell script while holding `NPM_TOKEN`; shell
syntax inside either input is evaluated before `npm` receives an argument. The
release workflow verifies only that the tag text matches `package.json`, so a
matching version tag on an unreviewed side branch can pass the current
pre-publish check and publish with the repository's npm credential.

Both are high-confidence supply-chain gaps with small, deterministic fixes.
Move dispatch data through environment variables, validate an exact SemVer
version before calling npm, and require the exact release commit to be reachable
from `origin/main` before any publish step. Keep the existing tag-driven
workflow, prerelease channel, provenance, idempotent reruns, and floating-major
behavior unchanged.

## Current state

- `.github/workflows/deprecate.yml:24-27` gives a shell script direct access to
  expression-expanded dispatcher strings:

  ```yaml
  - name: Deprecate npm version
    env:
      NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
    run: npm deprecate "ai-harness-doctor@${{ inputs.version }}" "${{ inputs.message }}"
  ```

  Quoting the expression does not make it data: GitHub substitutes the value
  before the runner invokes Bash. The audit's isolated mechanical reproduction
  confirmed shell command substitution in either `version` or `message` is
  evaluated. The plan does not include or preserve a runnable misuse payload.

- `.github/workflows/release.yml:94-113` checks out full history and compares
  only tag text to package metadata:

  ```yaml
  - uses: actions/checkout@... # actions/checkout@v7
    with:
      fetch-depth: 0
  ...
  - name: Verify tag matches package version
    run: |
      tag_version="${GITHUB_REF_NAME#v}"
      package_version="$(node -p "require('./package.json').version")"
      if [ "$tag_version" != "$package_version" ]; then
        ...
        exit 1
      fi
  ```

- The audit created an isolated Git repository with `main` and an unmerged
  branch carrying a matching `package.json` version/tag. The current string
  comparison passed, while:

  ```bash
  git merge-base --is-ancestor "$tag_commit" origin/main
  ```

  returned 1. This proves version equality is not reviewed-main ancestry.

- The `publish` job has `contents: write` and `id-token: write`, and its npm
  command receives `NPM_TOKEN` (`release.yml:149-154`). The `deprecate` workflow
  also receives `NPM_TOKEN`. Inputs/refs at these boundaries must be treated as
  untrusted data even when only maintainers can normally dispatch or push tags.

- `tests/test_action_metadata.py` already enforces immutable Action pins,
  release order, stable/prerelease routing, public lockfile sources, and
  Marketplace behavior. It is the repository's established structural policy
  test for workflow hardening.

- `RELEASING.md:56-67` currently documents version equality and manual
  deprecation but does not state exact SemVer validation, environment-only
  input transport, or the reviewed-main ancestry requirement.

## Target contract

1. A deprecation dispatch accepts one exact npm package version:
   `MAJOR.MINOR.PATCH` with an optional valid SemVer prerelease component.
   Reject ranges, tags, whitespace, shell syntax, a leading `v`, empty values,
   and build metadata unless npm/package release policy explicitly proves build
   metadata is supported and desired.
2. `inputs.version` and `inputs.message` appear only in YAML `env:` mappings,
   never inside `run:` script text. The shell uses quoted environment variables
   (`"$VERSION"`, `"$MESSAGE"`).
3. The deprecation message must be non-empty after validation and is passed as
   one opaque argv element. Do not evaluate it, interpolate it into another
   command, or log it unnecessarily.
4. Before `npm publish`, the release workflow fetches/has `origin/main`,
   resolves the triggering exact tag to a commit, and requires that commit to
   be an ancestor of `origin/main`.
5. The ancestry check is fail-closed: a missing main ref, shallow/incomplete
   history, non-commit tag target that cannot be peeled, or Git error stops the
   publish job.
6. Stable and prerelease tags that point at reviewed main history continue to
   publish through their existing `latest`/`next` channels. A release from an
   older main commit remains allowed; the existing latest-tag check separately
   prevents moving `vN` backwards.
7. No npm credential value is printed or copied into tests/docs.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Workflow policy tests | `python3 -m unittest discover -s tests -p 'test_action_metadata.py' -v` | all pass |
| actionlint | `actionlint .github/workflows/deprecate.yml .github/workflows/release.yml` | exit 0 |
| Full gate | `npm run check` | exit 0 |
| Evidence gate | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0 |
| Self scan | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0; grade A |

## Scope

**In scope**:

- `.github/workflows/deprecate.yml`
- `.github/workflows/release.yml`
- `tests/test_action_metadata.py`
- `RELEASING.md`
- `CONTRIBUTING.md` only if its release checklist needs the ancestry invariant
- a compact privileged-workflow invariant in `AGENTS.md`
- evidence-bound `benchmark/self-eval/` refresh after `AGENTS.md` changes
- `plans/README.md`

**Out of scope**:

- Replacing `NPM_TOKEN` with npm trusted publishing/OIDC. That requires npmjs
  account-side trusted-publisher configuration and independent live
  verification; do not claim it in a code-only PR.
- Rotating or exposing the current npm token.
- Changing npm package ownership, 2FA policy, access level, provenance, or
  dist-tag semantics.
- Adding tag protection/rulesets through repository administration.
- Requiring the release commit to equal the tip of `main`; ancestry is the
  intended contract so releasing an older reviewed commit remains recoverable.
- Reordering npm publish, GitHub Release creation, floating-tag update, Action
  verification, or Marketplace reminder steps.
- Changing supported stable/prerelease syntax in `package.json`.
- Adding a runtime dependency or a third-party validation Action.
- Publishing or deprecating a real version while testing this PR.

## Git workflow

- Branch: `fix/privileged-workflow-inputs`
- Commit: `fix(release): harden privileged npm workflows`
- One focused security/supply-chain PR.
- Do not push directly to `main`. Open an English PR, wait for all nine
  required contexts, then squash-merge and delete the branch.
- This is a backward-compatible bug/security fix. By itself it is patch-level;
  the combined three-plan batch is minor because Plan 023 adds a public
  feature.

## Steps

### Step 1: Add structural tests that fail on the current workflows

Extend `tests/test_action_metadata.py` with repository-specific tests. Avoid a
general YAML parser dependency; use the file's established text/regex policy
style.

For `deprecate.yml`, assert:

- `inputs.version` and `inputs.message` do not occur in any `run:` block;
- they occur in an `env:` mapping with stable names such as `VERSION` and
  `MESSAGE`;
- the run script validates `VERSION` against one anchored exact-SemVer regex
  before the `npm deprecate` line;
- the npm invocation uses exactly quoted environment arguments;
- `NODE_AUTH_TOKEN` remains environment-only.

For `release.yml`, assert:

- checkout still uses `fetch-depth: 0`;
- an ancestry guard occurs after checkout/version validation and before both
  npm version lookup and npm publish;
- it resolves/peels `GITHUB_REF_NAME` to a commit;
- it verifies that commit with `git merge-base --is-ancestor ... origin/main`;
- no `|| true`, `continue-on-error`, or warning-only fallback can bypass it.

When extracting run blocks, make the helper indentation-aware so an unrelated
expression elsewhere in YAML cannot satisfy the test.

**Verify**: the new tests fail against `ced1530` for both missing contracts and
all existing workflow tests remain green.

### Step 2: Treat deprecation inputs as data

Update `.github/workflows/deprecate.yml`:

```yaml
env:
  NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
  VERSION: ${{ inputs.version }}
  MESSAGE: ${{ inputs.message }}
run: |
  # validate VERSION and MESSAGE
  npm deprecate "ai-harness-doctor@$VERSION" "$MESSAGE"
```

Use a Bash `[[ ... =~ ... ]]` expression or an equivalent Node stdlib validator
with an anchored exact-SemVer grammar. The accepted prerelease grammar must not
allow empty dot-separated identifiers, whitespace, ranges, or a `v` prefix.
Keep validation readable and cover accepted/rejected values mechanically in
the test (extract the regex/validator or run a harmless local equivalent; never
invoke npm).

Reject an empty message. Do not impose an arbitrary prose character allow-list:
opaque deprecation text is safe once it is transported through `env` and
quoted. Never echo the message during validation.

**Verify**: policy tests pass; `actionlint` passes; a local harmless harness
proves representative stable/prerelease versions are accepted and ranges,
leading `v`, whitespace, and malformed prereleases are rejected without
executing any input as shell syntax.

### Step 3: Bind releases to reviewed main history

In the `publish` job of `.github/workflows/release.yml`, add a named step before
`Check whether this version is already on npm`:

1. ensure `refs/remotes/origin/main` exists (explicitly fetch it if checkout
   does not guarantee that ref);
2. resolve `"$GITHUB_REF_NAME^{commit}"`;
3. run `git merge-base --is-ancestor "$release_commit" refs/remotes/origin/main`;
4. print only safe ref/SHA diagnostics on failure and exit non-zero.

Keep arguments quoted and distinguish a policy failure (tag is off main) from
an operational Git failure if that can be done without weakening fail-closed
behavior. Do not use GitHub API branch membership: local full-history Git is
deterministic and already available.

Add one positive and one negative isolated-Git test in
`tests/test_action_metadata.py` or a helper it owns:

- tag on main history passes;
- same-version tag on an unmerged branch fails.

The test must run only local Git commands and must never push a tag.

**Verify**: isolated Git characterization passes; existing stable/prerelease,
rerun, and floating-major tests remain unchanged.

### Step 4: Document the privileged workflow invariant

Update `RELEASING.md`:

- exact version tags must point to commits reachable from `origin/main`;
- version text must still match `package.json`;
- manual deprecation accepts an exact version and passes version/message as
  opaque environment data;
- failed validation occurs before npm sees a credentialed command;
- trusted publishing remains a separately configured future option, not a
  completed control.

If `CONTRIBUTING.md` has a release checklist, add only a concise ancestry item;
do not duplicate the full runbook.

In `AGENTS.md`, add or compress one invariant: privileged workflow expressions
must enter scripts through `env`, exact version input must be validated, and
release tags must be main ancestors before npm operations. Keep the file below
the strict D4 threshold.

Because `AGENTS.md` is evidence-bound, refresh/regrade the self-eval honestly;
do not claim a model run.

**Verify**: evidence gate, self scan, and strict drift pass.

### Step 5: Run the full gate and merge

Run every command in the table. Open an English PR describing:

- the defensive input-boundary change without runnable misuse instructions;
- the isolated off-main tag reproduction;
- preserved stable/prerelease/rerun/floating-tag behavior;
- why npm trusted publishing is explicitly not claimed.

Wait for `drift`, `lint`, Node 16/20/22, `self-test`, and Python
3.9/3.10/3.12 to all succeed. Admin bypass may resolve only the sole-maintainer
self-review deadlock; it must not bypass a red or pending check.

**Verify**: all nine required contexts are green before squash merge; branch is
deleted; `main` contains the squash commit.

## Test plan

- Deprecation workflow expression values occur only under `env`, not `run`.
- Stable and prerelease exact versions are accepted.
- ranges/tags/leading `v`/whitespace/malformed prereleases are rejected.
- Empty message is rejected; punctuation remains opaque data.
- Npm command receives two quoted arguments and never evaluates input text.
- Tag on main history passes ancestry.
- Matching-version tag on an unmerged branch fails ancestry.
- Ancestry check precedes every npm network/publish operation and fails closed.
- Existing release order, dist-tags, provenance, rerun, floating tags, and
  Marketplace reminder tests stay green.

## Done criteria

- [ ] No workflow-dispatch input expression appears inside executable shell
  script text in `deprecate.yml`.
- [ ] Deprecation accepts only the documented exact version grammar and a
  non-empty opaque message.
- [ ] A release tag not reachable from `origin/main` cannot reach npm lookup or
  publish.
- [ ] Stable/prerelease tags on reviewed main history retain existing behavior.
- [ ] No credential value is logged, copied, or committed.
- [ ] `RELEASING.md` and `AGENTS.md` record the new invariant truthfully.
- [ ] Every command in the command table passes.
- [ ] All nine required PR checks are green before squash merge.

## STOP conditions

Stop and report back (do not improvise) if:

- Any in-scope workflow changed semantically since `ced1530`.
- The repository's intended release policy actually permits publishing from
  commits that were never reachable from `main`.
- Correct SemVer acceptance would require adding an npm/runtime dependency.
- The ancestry guard cannot obtain `origin/main` with the existing checkout
  permissions and full history.
- The fix requires changing release ordering or suppressing a failed guard.
- Implementing npm trusted publishing would require npmjs account changes; keep
  that as a separately verified follow-up.
- A real npm publish/deprecate operation would be needed to test the PR.
- A step's verification fails twice after a reasonable focused fix.

## Maintenance notes

- Treat GitHub expression values like request input: map to `env`, validate
  constrained fields, and quote every shell use. YAML quoting alone is not the
  boundary.
- Keep the ancestry guard before idempotency checks. “Already published” must
  not turn an off-main release into a successful workflow.
- If npm trusted publishing is configured later, retain these input and
  ancestry controls; OIDC removes a long-lived token but does not make an
  unreviewed tag safe.
- Any future default-branch rename must update both workflow and structural
  tests atomically.
