# Plan 025: Bind idempotent release reruns to the published npm artifact

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 935eeb6..HEAD -- .github/workflows/release.yml tests/test_action_metadata.py RELEASING.md CONTRIBUTING.md AGENTS.md benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json benchmark/self-eval/results-after-graded.json benchmark/self-eval/README.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: security / supply chain / tests / docs
- **Planned at**: commit `935eeb6`, 2026-07-15

## Why this matters

The tag-driven release workflow is intentionally rerunnable, but its
"already published" branch proves only that npm has the same version string.
If an exact tag is deleted/recreated or moved to another reviewed-main commit
whose `package.json` still carries that version, the current version and
main-ancestry guards pass and the workflow silently treats the different npm
artifact as the release for the new tag commit. It can then create or reuse a
GitHub Release and move the floating Action tag even though npm consumers and
Action consumers no longer share one source identity.

The audit reproduced that state in an isolated Git repository: a moved
`v1.6.0` still matched `package.json`, remained reachable from main, and took
the current skip branch while published npm metadata identified a different
commit. The live, legitimate `ai-harness-doctor@1.6.0` currently reports
`gitHead=935eeb664a0e215d46c88abd0a68b872f01225e6`, and its registry
`dist.shasum` matches `npm pack --dry-run`. Make that identity check part of
the fail-closed rerun contract without pretending GitHub's unavailable
immutable-release switch can be automated.

## Current state

- `.github/workflows/release.yml:106-131` verifies that the tag text matches
  `package.json` and that the peeled tag commit is an ancestor of
  `origin/main`. This blocks an unreviewed side-branch release, but ancestry
  does not prove that a previously published version came from the current tag
  commit.

- `.github/workflows/release.yml:156-165` currently treats existence as
  identity:

  ```yaml
  - name: Check whether this version is already on npm
    id: npm_version
    run: |
      version="$(node -p "require('./package.json').version")"
      if npm view "ai-harness-doctor@$version" version >/dev/null 2>&1; then
        echo "ai-harness-doctor@$version is already published; skipping npm publish."
        echo "already_published=true" >> "$GITHUB_OUTPUT"
      else
        echo "already_published=false" >> "$GITHUB_OUTPUT"
      fi
  ```

  The subsequent publish step is skipped solely from this output.

- `tests/test_action_metadata.py:307-506` is the established policy suite for
  release order, main ancestry, prerelease routing, floating tags, Marketplace
  reminders, and pinned dependencies. Its `_run_script()` helper executes
  workflow shell blocks in isolated repositories without making real release
  writes.

- `RELEASING.md:57-59` documents version equality and main ancestry.
  `RELEASING.md:90-92` already says a retroactive tag is allowed only after
  its packed tarball shasum matches npm, but the automated already-published
  path does not enforce even the stronger available `gitHead` identity.

- The audit checked the remote posture on 2026-07-15: there is no tag ruleset,
  the exact release is not immutable, and exact tags can therefore be moved by
  an administrator. A GitHub Release update request did not enable immutable
  releases. This plan must add a workflow guard and document server-side tag
  protection as a separate operational control, not claim unavailable remote
  immutability.

## Target contract

1. The npm existence/identity step runs only after version and main-ancestry
   verification, before publish, GitHub Release creation, floating-tag update,
   or any other release-side write.
2. When `ai-harness-doctor@<version>` does not exist, the workflow emits
   `already_published=false` and preserves the current publish path.
3. When that exact version exists, the workflow fetches registry metadata as
   structured JSON, including at minimum `version`, `gitHead`, and
   `dist.shasum`, and fails closed unless:
   - registry `version` exactly equals `package.json#version`;
   - `gitHead` is a 40-hex commit;
   - `gitHead` exactly equals the peeled triggering tag commit.
4. Only a matching identity emits `already_published=true`. Missing,
   malformed, ambiguous, or mismatching metadata must stop the workflow; a
   registry/network error must not be reinterpreted as "not published" and
   must not fall through to a blind publish attempt.
5. Compare an independently packed tarball SHA-1 (`npm pack --dry-run --json`
   or an equivalently isolated, deterministic command) with `dist.shasum`
   during the already-published path if the packed bytes are reproducible in
   the GitHub runner. If a mechanical characterization proves the npm pack
   shasum is not reproducible across a clean tagged checkout, STOP and keep
   `gitHead` as the mandatory gate rather than adding a flaky checksum claim.
6. Parse registry/pack JSON with Node, not shell substring matching or `eval`.
   Do not print credentials, provenance attestations, package contents, or
   arbitrary registry response bodies.
7. Stable/prerelease channel selection, first-time publish with provenance,
   exact GitHub Release creation, floating-major ordering, public Action
   verification, and Marketplace reminders remain unchanged after identity
   succeeds.
8. Exact-tag server-side immutability/rulesets remain an operational
   recommendation. Do not create or mutate remote rulesets in this PR, and do
   not claim the GitHub Release API can enable immutability.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Workflow policy tests | `python3 -m unittest discover -s tests -p 'test_action_metadata.py' -v` | all pass |
| actionlint | `actionlint .github/workflows/release.yml` | exit 0 |
| Pack identity | `npm pack --dry-run --json` | exit 0; one package record with `shasum` |
| Full gate | `npm run check` | exit 0 |
| Evidence gate | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0 |
| Self scan | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0; grade A |

## Scope

**In scope**:

- `.github/workflows/release.yml`
- `tests/test_action_metadata.py`
- `RELEASING.md`
- `CONTRIBUTING.md` only if its release checklist needs the new identity guard
- a compact release-rerun invariant in `AGENTS.md`
- evidence-bound `benchmark/self-eval/` refresh after `AGENTS.md` changes
- `plans/README.md`

**Out of scope**:

- Moving, deleting, signing, or recreating any real Git tag.
- Publishing, unpublishing, deprecating, or changing dist-tags for a real npm
  version while testing.
- Enabling npm trusted publishing/OIDC; it still requires npmjs account-side
  configuration and a real publication proof.
- Rotating, exposing, or changing `NPM_TOKEN`.
- Creating GitHub tag rulesets, changing allowed Actions, or requiring signed
  tags through repository administration.
- Claiming or attempting to toggle immutable GitHub Releases when the current
  remote/API does not expose that capability.
- Requiring the release commit to equal current `main` tip; reviewed-main
  ancestry remains sufficient for a first publication.
- Changing Marketplace categories or confirmation behavior.
- Adding a runtime dependency or third-party release Action.

## Git workflow

- Branch: `fix/npm-release-rerun-identity`
- Commit: `fix(release): verify published npm identity on rerun`
- One focused release-supply-chain PR with structural/mechanical tests.
- Do not push directly to `main`. Open an English PR, wait for all nine
  required contexts, then squash-merge and delete the branch.
- This closes a release replay integrity gap without changing the normal
  public interface. By itself it is patch-level.

## Steps

### Step 1: Characterize the legitimate and moved-tag rerun cases

Extend `tests/test_action_metadata.py` with an extractable test for the npm
existence/identity run block. Use a temporary isolated Git repository and a
stub `npm` executable or other deterministic command seam so no real package
is published.

Cover:

1. package absent → output contains `already_published=false`;
2. package present with matching version, `gitHead`, and `dist.shasum` →
   `already_published=true`;
3. package present with a different 40-hex `gitHead` → non-zero exit and no
   `already_published=true`;
4. missing/malformed `gitHead` → non-zero exit;
5. registry version mismatch → non-zero exit;
6. lookup/network failure distinguishable from a true not-found response →
   non-zero exit, not a blind publish branch;
7. if checksum verification is retained, matching and mismatching
   `dist.shasum`, plus malformed pack JSON;
8. annotated and lightweight exact tags both compare using their peeled commit.

Add ordering assertions proving identity verification occurs before npm
publish, GitHub Release creation, and floating-tag mutation. Avoid asserting
only the presence of strings; execute the extracted logic for both allowed and
rejected states.

**Verify**: the moved-tag and malformed-metadata cases fail against `935eeb6`,
while current ancestry/channel tests remain green.

### Step 2: Make npm not-found distinguishable from lookup failure

Refactor the named release step so registry access has three outcomes:

- exact version absent;
- exact version present with parsed metadata;
- operational failure.

Use npm's structured JSON output and explicit error/status handling. Do not
retain the current `if npm view ... >/dev/null 2>&1; else unpublished` shape,
because it conflates DNS/auth/registry failures with a true 404.

Pass the peeled `release_commit` to the identity step through a step output or
recompute it fail-closed from `GITHUB_REF_NAME^{commit}`. Keep all GitHub
expressions in environment mappings where practical, and compare opaque
environment values in Node/Bash without constructing executable text.

**Verify**: stubbed not-found continues to the publish branch; stubbed
operational failure stops before the publish command.

### Step 3: Verify the existing npm artifact before declaring idempotence

For a present version:

- parse `version`, `gitHead`, and `dist.shasum`;
- normalize only safe representational details (for example JSON scalar vs
  one-element result), never case-fold versions or commits;
- require exact version and peeled-commit equality;
- if Step 1 proves reproducible, generate the current package tarball in
  `RUNNER_TEMP`, compare its SHA-1 with `dist.shasum`, then remove it;
- emit `already_published=true` only after every retained check passes.

Do not use `npm pack` output filename text as trusted shell syntax. Parse JSON,
validate the returned path stays under the chosen temporary directory, and
hash the file with a standard runner tool/Node standard library. The workflow
must not modify tracked files.

**Verify**: the live read-only command for `1.6.0` demonstrates matching
registry `gitHead` and pack shasum; unit tests use only synthetic metadata and
stub packages.

### Step 4: Document recovery and operational tag protection honestly

Update `RELEASING.md` (and `CONTRIBUTING.md` only if needed) to explain:

- an already-published rerun is idempotent only when npm identity matches the
  current exact tag;
- a mismatched/malformed identity stops before GitHub Release/floating-tag
  writes;
- a moved/deleted exact tag requires investigation and must never be
  "repaired" by publishing the immutable npm version again;
- maintainers should enable exact release-tag protection/immutability when the
  hosting plan exposes it, but the current workflow guard is the portable
  enforcement available here;
- GitHub Release immutability is not currently automated.

Add one compact invariant to `AGENTS.md`, refresh self-eval evidence, and mark
Plan 025 DONE after squash merge.

**Verify**: full gate, evidence gate, self scan, and strict drift pass;
`AGENTS.md` remains below the context-bloat threshold.

## Test plan

- Model workflow extraction after
  `test_release_tag_must_be_reachable_from_main_before_npm_access`.
- Stub registry states; never require npm credentials or a real write.
- Assert negative paths do not emit `already_published=true` and do not reach a
  sentinel publish command.
- Test exact, prerelease, annotated-tag, and lightweight-tag identities.
- Characterize `npm pack --dry-run --json` in a clean tracked checkout before
  making `dist.shasum` mandatory.
- Run actionlint and the full repository gate.

## Done criteria

- [ ] A matching published npm `gitHead` is mandatory before the workflow
      skips publish.
- [ ] Registry/network failure is not treated as an unpublished version.
- [ ] A moved exact tag with the same version fails before all release writes.
- [ ] `dist.shasum` is verified when and only when clean-checkout
      reproducibility is mechanically proven.
- [ ] First publication, stable/prerelease channels, provenance, floating
      tags, Action verification, and Marketplace reminders remain intact.
- [ ] Recovery and server-side tag-protection limits are documented without
      claiming unavailable immutability.
- [ ] `npm run check`, actionlint, evidence gate, self scan, and strict drift
      all pass.
- [ ] No real registry/tag/release state changed during tests.
- [ ] Plan 025 and its index row are marked DONE after squash merge.

## STOP conditions

Stop and report back (do not improvise) if:

- The release step or npm metadata shape has drifted from the current-state
  excerpts.
- npm no longer returns a valid 40-hex `gitHead` for packages published by this
  workflow.
- A clean tagged checkout cannot reproduce `dist.shasum`; keep the mandatory
  `gitHead` check and report the checksum limitation instead of adding a flaky
  gate.
- Distinguishing true not-found from operational lookup failure requires
  credentials or a third-party runtime dependency.
- Correct implementation requires moving a real tag, republishing an immutable
  npm version, or exposing registry credentials.
- GitHub's remote immutability controls are unavailable; do not simulate
  success in workflow/docs.
- A verification command fails twice after a reasonable scoped fix.

## Maintenance notes

- `gitHead` is the primary source-commit binding for an already-published npm
  artifact. Reviewers should reject future rerun logic that checks version
  existence alone.
- `dist.shasum` verifies packed bytes only while npm's pack process is
  reproducible from the tagged checkout. Keep the characterization test if the
  check is enabled.
- Main ancestry and npm identity solve different threats: ancestry proves
  review lineage; identity proves the immutable registry artifact is the same
  release. Preserve both.
- Trusted publishing and server-side exact-tag protection remain worthwhile
  operational follow-ups, but neither substitutes for identity validation.
