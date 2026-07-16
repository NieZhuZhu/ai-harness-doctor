# Plan 056: Keep the pre-commit example on the current stable release

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md` unless a reviewer maintains the index separately.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 725128d..HEAD -- \
>   README.md README.zh-CN.md README.ja.md README.es.md README.ko.md \
>   README.pt-BR.md README.fr.md tests/test_precommit_hooks.py \
>   scripts/check_readme_sync.py plans/056-keep-precommit-example-current.md \
>   plans/README.md
> ```
>
> If any in-scope file changed, compare the "Current state" excerpts against
> live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: Plans 003, 005, and 019 (DONE)
- **Category**: docs / consumer safety / test coverage
- **Planned at**: commit `725128d`, 2026-07-17
- **Implementation**: DONE — PR #248 (plan) / PR #249 (impl),
  squash-merged to `main` as `fcb400f`; all nine required contexts green.

## Why this matters

Every public README gives pre-commit users a copy-paste configuration pinned to
`rev: v1.3.0`, while the current stable release is `v1.11.0`. In pre-commit,
`rev` is an immutable ref and the framework caches it; consumers who follow the
example therefore install and continue running the old tag rather than the
current `v1` implementation.

The hook metadata itself has not changed, which makes the example look valid,
but the runtime behind it has. Between `v1.3.0` and `v1.11.0`, `scripts/` and
`bin/` changed by 7,013 insertions / 731 deletions and gained security,
containment, nested-scope, baseline, SARIF, eval, and installer fixes. Update the
example to the exact current stable tag and add a deterministic guard so the
next release-version change cannot silently leave all seven READMEs stale.

## Mechanical reproduction

Current evidence:

```text
README.md through README.fr.md: rev: v1.3.0
package.json:                         1.11.0
npm latest / GitHub stable release:   1.11.0 / v1.11.0
```

All seven READMEs contain the same fenced block at line 104:

```yaml
repos:
  - repo: https://github.com/NieZhuZhu/ai-harness-doctor
    rev: v1.3.0
```

The remote refs peel to different commits:

```text
v1.3.0  -> b3e670d
v1.11.0 -> 5d96c95
v1       -> 5d96c95
```

Official pre-commit documentation states that `rev` must be an immutable ref
(tag or SHA) and is cached. Using `v1` is therefore not a supported way to make
this snippet float; the exact tag must be maintained deliberately.

The metadata hash is identical at `v1.3.0` and `v1.11.0`, but runtime hashes
are not. For example, `scripts/check_drift.py` differs, and `v1.3.0` lacks
`scripts/redaction.py`, `scripts/explain.py`, and the modern Action helpers.

## Current state

### Seven READMEs intentionally share fenced code byte-for-byte

`scripts/check_readme_sync.py` requires:

- all seven public language files;
- the same heading skeleton;
- byte-identical fenced code blocks, including inline comments;
- the same table-row and link counts/targets;
- bounded prose paragraph length.

Changing only `README.md` must fail. The tag update belongs in all seven files
in one change.

### Existing pre-commit tests do not validate the selected version

`tests/test_precommit_hooks.py` currently verifies:

- both hook IDs exist;
- hook entries use the public packaged CLI;
- hooks are repo-wide Node hooks;
- every README names both hook IDs and the repository URL.

It never extracts `rev`, never compares it to `package.json`, and would accept
any old or nonexistent tag. This plan should deepen that test module rather
than add a release-network test.

### Exact tag, not a floating branch

Pre-commit requires an immutable `rev`. Keep the public example as:

```yaml
rev: v<package.json version>
```

Do not replace it with `v1`, `main`, or `HEAD`. The GitHub Action examples
correctly use floating `@v1` under a different consumer/update contract and are
out of scope.

## Target contract

1. Every required public README's pre-commit example uses exactly:
   `rev: v${package.json.version}`.
2. For this implementation, the expected line is `rev: v1.11.0`.
3. The value remains an exact stable semantic-version tag:
   `vMAJOR.MINOR.PATCH`; no prerelease, branch, floating major, range, or SHA.
4. `tests/test_precommit_hooks.py` extracts the `rev` only from the fenced
   pre-commit snippet associated with
   `repo: https://github.com/NieZhuZhu/ai-harness-doctor`.
   Do not globally reject historical version references elsewhere.
5. The test derives the expected exact tag from `package.json`, then asserts all
   seven READMEs have one matching pre-commit repo/rev pair.
6. The test must fail for:
   - one stale translation;
   - a floating `v1`;
   - a branch such as `main`;
   - an absent/malformed rev.
   These may be unit-level helper cases or repository-file assertions with
   temporary text; do not mutate real READMEs in tests.
7. README synchronization still enforces byte-identical fenced code across all
   languages. Do not weaken or special-case that rule.
8. `.pre-commit-hooks.yaml` and hook commands do not change; only the consumer
   example/version guard changes.
9. Do not query GitHub/npm during required tests. Package version is the local
   release source of truth; the tag-driven release workflow proves publication.
10. No runtime dependencies or product behavior changes.

## Design

Add a small stdlib regex/helper inside `tests/test_precommit_hooks.py`, scoped
to the known repository line followed by `rev` within the same YAML snippet.
For example:

```python
EXPECTED_REV = "v" + json.loads(PACKAGE_JSON.read_text())["version"]
```

Then, per README:

- find exactly one matching repository/rev pair;
- require the captured value to equal `EXPECTED_REV`;
- require `EXPECTED_REV` to match exact stable SemVer.

Keep `scripts/check_readme_sync.py` unchanged unless implementation proves the
existing code-block comparison cannot catch a one-language drift. Its current
tests already prove code-block body mismatches fail.

This is a version-maintenance guard: every future release bump PR will fail
until the seven snippets are updated to the new exact stable tag. That is
intentional because an immutable pre-commit reference cannot auto-follow `v1`.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused hooks | `python3 -m unittest tests.test_precommit_hooks -v` | all pass |
| README sync | `python3 scripts/check_readme_sync.py` | seven READMEs aligned |
| Docs tests | `python3 -m unittest tests.test_check_readme_sync -v` | all pass |
| Python lint | `python3 -m ruff check tests/test_precommit_hooks.py scripts/check_readme_sync.py` | exit 0 |
| Full gate | `npm run check` | all lint/tests pass |
| Self scan | `python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json --check-baseline --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts --no-report-file` | exit 0 |
| Self drift | `python3 scripts/check_drift.py . --strict` | 100/100, Grade A |
| Self eval | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | 38/38, Grade A |

## Scope

**In scope**:

- `README.md`
- `README.zh-CN.md`
- `README.ja.md`
- `README.es.md`
- `README.ko.md`
- `README.pt-BR.md`
- `README.fr.md`
- `tests/test_precommit_hooks.py`
- `scripts/check_readme_sync.py` only if required for an existing sync-gap
  regression; default is no change
- `plans/056-keep-precommit-example-current.md`
- `plans/README.md`

**Out of scope**:

- `.pre-commit-hooks.yaml` behavior or hook IDs.
- GitHub Action `uses: ...@v1` examples.
- Replacing exact pre-commit tags with `v1`, `main`, or another mutable ref.
- Installing/running pre-commit in required CI.
- A network request to prove the tag exists.
- Automatically editing READMEs during release.
- A `CHANGELOG.md` or release workflow redesign.
- The unrelated `npm run format` write-set problem.
- Any runtime code or dependency.

## Git workflow

- Branch: `docs/056-current-precommit-example`.
- Commit: `docs(readme): keep pre-commit example current`.
- One focused documentation/test PR; do not push directly to `main`.
- Wait for all nine required checks before squash merge:
  `drift`, `lint`, Node 16/20/22, Python 3.9/3.10/3.12, and `self-test`.
- Documentation correction only: no release is required by itself.

## Steps

### Step 1: Add a failing version-contract test

In `tests/test_precommit_hooks.py`, derive `EXPECTED_REV` from
`package.json`. Add a helper that extracts the exact repo/rev pair from README
text, then assert all required files use it exactly once.

Before changing READMEs, run the focused suite. It must fail with:

```text
expected v1.11.0, found v1.3.0
```

Also add helper-level cases that reject `v1`, `main`, missing rev, and duplicate
repo/rev entries without writing repository files.

**Verify**:

```bash
python3 -m unittest tests.test_precommit_hooks -v
```

Expected before Step 2: RED only on the new current-version assertion.

### Step 2: Update all seven immutable refs together

Replace `rev: v1.3.0` with `rev: v1.11.0` in the pre-commit fenced code block
of every public README. Do not translate or otherwise edit the fenced block.

**Verify**:

```bash
python3 scripts/check_readme_sync.py
python3 -m unittest tests.test_precommit_hooks -v
```

Expected: all seven READMEs aligned and all hook tests pass.

### Step 3: Prove the guard catches future drift

Use helper-level unit inputs (preferred) or a temporary copy to assert:

- one old exact version is rejected;
- floating/branch refs are rejected;
- a duplicate pair is rejected;
- the current exact tag is accepted.

Do not invoke Git, GitHub, npm, or pre-commit in the unit test.

**Verify**:

```bash
python3 -m unittest tests.test_precommit_hooks -v
```

Expected: all positive and negative contract cases pass.

### Step 4: Run gates and two-axis review

Run every command in the table.

- **Standards review**: seven README code blocks remain byte-identical; no
  runtime/dependency/workflow changes; tests are stdlib-only and deterministic.
- **Spec review**: every public snippet equals local package version; no
  mutable pre-commit ref; Action examples stay unchanged.

Open one implementation PR and wait for all nine contexts before squash merge.

## Test plan

- Repository-level assertion over all seven required READMEs.
- Exact-current ref accepted.
- Stale exact tag rejected.
- `v1` and `main` rejected.
- Missing or duplicate repo/rev pair rejected.
- Existing README sync tests continue to prove one-language code-block drift
  fails.
- Full matrix proves the parser works on Python 3.9/3.10/3.12.

## Done criteria

- [x] All seven public pre-commit snippets use `rev: v1.11.0`.
- [x] The expected ref is derived from `package.json`, not duplicated in test
      code.
- [x] Exact stable SemVer is required; mutable refs are rejected.
- [x] Missing, stale, malformed, and duplicate snippets fail deterministically.
- [x] README fenced blocks remain byte-identical across translations.
- [x] `.pre-commit-hooks.yaml` and Action examples are unchanged.
- [x] No required test performs a network or pre-commit installation.
- [x] Full local gate (802 Python + 47 Node), strict drift 100/A, and self eval
      38/38 pass.
- [x] All nine PR checks pass and the implementation is squash-merged.

## STOP conditions

Stop and report back if:

- the current `package.json` version is a prerelease;
- the exact matching Git tag/release does not exist;
- official pre-commit behavior supports a tested immutable floating-major
  mechanism that makes version maintenance unnecessary;
- updating the snippet requires changing hook metadata or behavior;
- the current README sync checker cannot preserve all seven fenced blocks
  without a larger documentation migration;
- a required test needs network access;
- any required CI context is red or pending at merge time.

## Maintenance notes

- Pre-commit and GitHub Actions have different update semantics. Keep exact
  immutable `rev: vX.Y.Z` for pre-commit and floating `@vN` for the Action.
- The release bump PR must update all seven pre-commit snippets. The new test is
  expected to enforce that coupling.
- `pre-commit autoupdate` is still a valid consumer workflow; this repository's
  copy-paste example should start new consumers at the current stable tag.
- If the project later automates version bumps, include these seven code blocks
  in that single release change rather than weakening the guard.
