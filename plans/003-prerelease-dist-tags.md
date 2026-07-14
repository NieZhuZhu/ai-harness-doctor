# Plan 003: Prevent prereleases from replacing stable npm and Action refs

> **Executor instructions**: Follow every step and verification gate. Touch
> only the in-scope files. Stop rather than improvising when a STOP condition
> occurs. Update `plans/README.md` when complete.
>
> **Drift check (run first)**:
> `git diff --stat 7121ce6..HEAD -- .github/workflows/release.yml tests/test_action_metadata.py RELEASING.md AGENTS.md`

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: MED
- **Depends on**: none
- **Category**: bug / release
- **Planned at**: commit `7121ce6`, 2026-07-14

## Why this matters

The release trigger `v*.*.*` also matches tags such as `v1.1.0-beta.1`.
`npm publish` currently omits `--tag`, so npm uses `latest`; the workflow also
moves the stable floating `v1` tag. A prerelease can therefore silently become
the default npm install and Action version for stable consumers. Prereleases
must use a non-`latest` dist-tag and must not move the stable major Action ref.

## Current state

- `.github/workflows/release.yml:3-9` matches full and prerelease tags.
- `.github/workflows/release.yml:113-137` derives only the major and runs
  `npm publish --provenance --access public`.
- `.github/workflows/release.yml:149-163` always moves the floating major tag.
- `.github/workflows/release.yml:165-224` always verifies that floating tag.
- `tests/test_action_metadata.py:44-99` locks release ordering and dynamic major
  behavior, but has no prerelease contract.
- `RELEASING.md:5-27, 52-66` documents stable publication only.
- npm's documented default dist-tag for `npm publish` is `latest` unless
  `--tag` is provided.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Targeted tests | `python3 -m unittest tests.test_action_metadata -v` | all pass |
| YAML parse | `ruby -e 'require "yaml"; YAML.load_file(".github/workflows/release.yml")'` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | OK |
| Full gate | `npm run check` | exit 0 |
| Self drift | `python3 scripts/check_drift.py .` | grade A |

## Scope

**In scope**:

- `.github/workflows/release.yml`
- `tests/test_action_metadata.py`
- `RELEASING.md`
- `AGENTS.md`

**Out of scope**:

- Changing the exact-tag trigger; prerelease GitHub Releases remain supported.
- Automatically publishing prerelease Releases to Marketplace.
- Changing stable release semantics.
- Adding a new CLI command for releases.

## Git workflow

- Branch: `fix/prerelease-dist-tags`
- Commit: `fix(release): isolate prerelease channels`
- One focused PR; squash merge after CI.

## Steps

### Step 1: Add failing prerelease metadata tests

Extend `tests/test_action_metadata.py` to assert:

1. release metadata detects whether `package.json` contains a prerelease;
2. stable versions emit npm dist-tag `latest` and a non-empty floating major
   tag;
3. prereleases emit a prerelease dist-tag (use `next` unless repository policy
   chooses a sanitized prerelease identifier) and no stable floating tag update;
4. npm publish includes `--tag "$NPM_TAG"`;
5. floating-tag update, verification, and Marketplace reminder are skipped or
   explicitly adapted for prereleases;
6. stable `v1.0.1` remains unchanged.

Prefer workflow outputs (`is_prerelease`, `npm_tag`, `floating_tag`) that make
job conditions testable and visible.

**Verify**: the new test fails before workflow changes.

### Step 2: Derive release channel metadata

In `Determine release metadata`, parse `package.json.version` without external
dependencies:

- prerelease iff version contains `-`;
- stable: `npm_tag=latest`, `floating_tag=v<major>`;
- prerelease: `npm_tag=next`, and do not move the stable floating major tag.

Expose outputs for downstream steps. Keep the exact GitHub Release creation
idempotent for both channels.

**Verify**: static metadata tests pass.

### Step 3: Publish with the explicit npm dist-tag

Pass `--tag "$NPM_TAG"` to `npm publish`. Ensure the npm existence check still
checks the exact version, not the dist-tag.

For prereleases:

- do not update `vN`;
- do not run stable floating-tag verification;
- do not create the stable Marketplace reminder, or create a clearly labeled
  prerelease reminder only if the current product policy requires it.

The simplest safe policy is to condition all stable floating/Marketplace jobs
on `is_prerelease != 'true'`.

**Verify**: YAML parses and ordering tests pass.

### Step 4: Document stable and prerelease channels

Update `RELEASING.md`:

- stable versions publish to npm `latest`, move `vN`, verify it, and open the
  Marketplace reminder;
- prereleases publish to npm `next`, create an exact GitHub Release, and leave
  `latest`/`vN`/Marketplace stable state untouched.

Update `AGENTS.md` release contract with the same invariant.

**Verify**: docs and drift checks pass.

## Test plan

- Static stable example: `1.0.1` → `latest`, `v1`.
- Static prerelease example: `1.1.0-beta.1` → `next`, no `v1` move.
- Existing version/tag guard remains.
- Workflow YAML is valid.
- Full release tests remain green.

## Done criteria

- [ ] A prerelease cannot replace npm `latest`.
- [ ] A prerelease cannot move a stable floating major Action tag.
- [ ] Stable releases still update and verify `vN`.
- [ ] Exact prerelease GitHub Releases remain supported.
- [ ] Targeted/full tests and drift grade A pass.
- [ ] Only in-scope files and plan status changed.

## STOP conditions

- npm provenance cannot be used with an explicit dist-tag.
- Existing documented policy intentionally wants prereleases on `latest`.
- Job-output conditions would prevent stable Marketplace reminders.

## Maintenance notes

Every future release-channel feature must preserve two independent stable
consumer pointers: npm `latest` and GitHub Action `vN`. Exact semantic-version
tags may be prerelease, but stable floating refs must never be.
