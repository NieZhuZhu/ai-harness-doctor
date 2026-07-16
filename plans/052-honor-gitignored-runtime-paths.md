# Plan 052: Stop treating repository-gitignored runtime paths as stale

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md` unless a reviewer maintains the index separately.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 7e03467..HEAD -- \
>   scripts/facts.py scripts/semantic.py scripts/check_drift.py scripts/scan.py \
>   tests/test_semantic.py tests/test_check_drift.py \
>   tests/test_registry_consistency.py tests/test_scan.py EXTERNAL_VALIDATION.md \
>   README.md README.zh-CN.md README.ja.md README.es.md README.ko.md \
>   README.pt-BR.md README.fr.md SKILL.md AGENTS.md
> ```
>
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against live code before proceeding. A semantic
> mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: Plans 014, 018, and 021 (DONE)
- **Category**: correctness / diagnostic precision
- **Planned at**: commit `7e03467`, 2026-07-17
- **Implementation**: IN PROGRESS — PR #233 (plan) / PR #234 (impl);
  implementation branch `fix/052-honor-gitignored-runtime-paths`, full local
  gates and pinned Qwen validation green, awaiting required CI and merge.

## Why this matters

AI harness guidance legitimately documents runtime scratch directories that a
clean checkout should not contain. When the repository itself declares those
paths ignored, reporting them as stale makes `--fail-on-semantic` and
`drift --strict` fail on accurate instructions.

This is live, independently inspectable evidence rather than a hypothetical.
At Qwen Code commit `f8e6e893166d567df94e82e1d53745e4862f6e38`,
root `AGENTS.md` documents `.qwen/issues/`, `.qwen/pr-drafts/`,
`.qwen/pr-reviews/`, `.qwen/investigations/`, and `.qwen/scripts/`, while its
committed `.gitignore` contains `.qwen/*` and selectively re-includes tracked
subtrees. The five runtime paths are absent by design. The current doctor
reports each absent path as both a Phase-0 semantic `MISSING` and Phase-2 `D2`
error.

The repair must use only repository-owned ignore rules. A user's global Git
excludes and `.git/info/exclude` are local machine state and must never change a
committed CI result.

## Mechanical reproduction

Create an isolated repository:

```text
.gitignore:
  .qwen/*

AGENTS.md:
  Runtime scratch lives in `.qwen/issues/` and `.qwen/pr-drafts/`;
  both are git-ignored.
```

Current dev checkout:

```text
scan semantic findings:
  MISSING .qwen/issues/
  MISSING .qwen/pr-drafts/

drift findings:
  D2 .qwen/issues/
  D2 .qwen/pr-drafts/
```

The same paths are positively matched by Git's ignore engine. The implementation
must not run this command against the target repository's real metadata:

```bash
git --git-dir=SYNTHETIC_EMPTY_METADATA --work-tree=REPO \
  check-ignore --no-index -z --stdin
```

## Current state

### Shared path candidacy

`scripts/registry.py:226-370` owns `declared_paths(text)`. It deliberately
filters syntax classes such as commands, Go imports, branch refs, dotenv files,
and generated `dist`/`build` paths before either diagnostic engine sees them.

Do **not** add arbitrary `.gitignore` parsing there: candidacy has only text and
no repository root, while Git ignore semantics depend on nested files,
anchoring, directory rules, and negations.

### Phase 0 existence policy

`scripts/semantic.py:797-830`:

```python
for decl in declared_paths(text):
    token, line = decl["path"], decl["line"]
    if not _within_root(root, token):
        continue
    if not facts.exists_within_root(root, root / token):
        # package-name, ESLint-id, and subtree suffix exceptions
        findings.append(...)
```

### Phase 2 existence policy

`scripts/check_drift.py:144-195`:

```python
for decl in registry.declared_paths(text):
    token, lineno = decl["path"], decl["line"]
    candidate = facts.resolve_within_root(
        Path(root) / token,
        containment_root,
        strict=False,
    )
    if candidate is None:
        continue
    if not facts.exists_within_root(containment_root, candidate):
        # root fallback, package-name, ESLint-id, and subtree suffix exceptions
        findings.append(...)
```

Plans 014/018/021 established an invariant: scan and drift must share the same
candidate and existence policy while nested scopes resolve local-first and
repository-root second.

### Existing tests

- `tests/test_registry_consistency.py:
  test_backtick_path_detection_single_sourced_across_stages` compares Phase 0
  and Phase 2 missing-token sets.
- `tests/test_registry_consistency.py:
  test_subtree_path_existence_policy_agrees_across_stages` pins subtree parity.
- `tests/test_semantic.py:512` covers the narrower runtime-dotenv exception.
- `tests/test_check_drift.py:288` and nearby tests pin D2 subtree behavior.

## Target contract

1. An absent declared path is not a semantic/D2 finding when Git's
   **repository-owned** ignore rules positively ignore that exact path.
2. Repository-owned means committed/worktree `.gitignore` files under the
   audited root. Do not honor:
   - user/global `core.excludesFile`;
   - `.git/info/exclude`;
   - the target repository's real `.git/config` or any other target `.git`
     metadata;
   - an external parent worktree's rules when auditing an arbitrary directory;
   - environment-injected Git config.
3. Use Git's own matcher when available. Do not implement a partial glob parser.
   The query must support:
   - nested `.gitignore`;
   - anchored and directory patterns;
   - negation/re-inclusion;
   - untracked/nonexistent candidates (`--no-index`);
   - spaces and non-ASCII paths without line-splitting ambiguity.
4. Batch candidate tokens in one bounded subprocess per diagnostic root, not
   one Git process per token.
5. Fail closed:
   - if `git` is missing;
   - if the subprocess times out;
   - if temporary metadata cannot be created safely;
   - if output is malformed;
   - if Git returns an unexpected status;
   then treat no path as ignored and retain existing findings.
6. Query only already-contained, repository-relative candidate tokens. Never
   probe an absolute/escaping token or follow an external symlink.
7. A negated/re-included path remains checkable. For example:

   ```text
   .qwen/*
   !.qwen/commands/
   !.qwen/commands/**
   ```

   suppresses missing `.qwen/issues/` but not missing
   `.qwen/commands/example.md`.
8. Existing files remain checked as existing regardless of ignore rules.
9. Phase 0 and Phase 2 produce the same set of missing paths after ignore
   classification, including monorepo package scans, nested AGENTS scopes, and
   root fallback.
10. No new runtime dependency; Python 3.9 standard library only.

## Design

### Repository-owned Git sandbox

Add a contained helper in `scripts/facts.py`, for example:

```python
def repository_ignored_paths(root, tokens, timeout=5):
    """Return the contained relative tokens ignored by repo .gitignore rules."""
```

Recommended mechanics:

- normalize/deduplicate already-contained relative tokens;
- create a temporary synthetic Git directory outside the audited worktree with
  only the minimum valid metadata (`HEAD`, `config`, empty object/ref dirs, and
  an empty `info/exclude`);
- point synthetic `core.worktree` / `--work-tree` at the audited root;
- run one
  `git --git-dir=TEMP --work-tree=ROOT check-ignore --no-index -z --stdin`;
- pass NUL-delimited UTF-8 input and parse NUL-delimited output;
- isolate configuration with an explicit environment/config policy:
  - disable system/global config (`GIT_CONFIG_NOSYSTEM=1` and a null global
    config, or an equivalent tested mechanism);
  - set `core.excludesFile` to the platform null device;
  - prevent optional hooks/fsmonitor features from affecting the query;
- do not use `-v` for the product decision unless source parsing is necessary;
  with ordinary output, only positively ignored paths are emitted after
  negation semantics;
- treat exit `0` as one or more ignored tokens, exit `1` as no ignored tokens,
  and every other outcome as fail-closed empty.

This design was mechanically validated before planning: a synthetic metadata
directory applied root and nested `.gitignore` rules plus negated
re-inclusions, while the target repository's real/local metadata was absent.
The helper must not read or parse ignored file contents. It asks only whether a
candidate name is excluded.

If synthetic metadata cannot retain nested `.gitignore` semantics without
consulting the target's `.git` directory, STOP. Do not silently let local Git
metadata change CI findings. A bounded stdlib parser may be investigated only
in a new plan with an explicit compatibility matrix; it is not an escape hatch
here.

### One existence-classification seam

Prefer a small shared helper in `facts.py` that classifies a batch of declared
paths for one scope, or have both callers consume the exact same
`repository_ignored_paths` result. Do not copy subprocess/output logic into
`semantic.py` and `check_drift.py`.

For nested drift:

- local scope existence still wins;
- repository-root fallback still wins;
- ignore suppression should reflect the repository root's owned ignore rules
  for the final root-relative candidate;
- a package-local `.gitignore` must apply according to Git semantics;
- do not run a nested path as an unrelated Git repository.

For Phase-0 monorepo package reports, thread the top-level audited repository
root through `scan_monorepo` → `scan_repo` → `semantic.analyze` instead of
treating a package directory as a separate ignore root. Convert a package-local
candidate to its repository-root-relative spelling before the single Git query,
so nested `.gitignore` files apply exactly where they live. Preserve standalone
`scan_repo` callers by defaulting the repository root to the scan root.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Targeted tests | `python3 -m unittest tests.test_semantic tests.test_check_drift tests.test_registry_consistency -v` | all pass |
| Full gate | `npm run check` | lint + all Python/Node tests pass |
| README sync | `python3 scripts/check_readme_sync.py` | seven READMEs aligned |
| Self scan | `python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json --check-baseline --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts --no-report-file` | exit 0 |
| Self drift | `python3 scripts/check_drift.py . --strict` | 100/100, grade A |
| Self eval | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | 34/34, grade A |

## Scope

**In scope**:

- `scripts/facts.py`
- `scripts/semantic.py`
- `scripts/check_drift.py`
- `scripts/scan.py`
- `tests/test_semantic.py`
- `tests/test_check_drift.py`
- `tests/test_registry_consistency.py`
- `tests/test_scan.py`
- `EXTERNAL_VALIDATION.md`
- all seven READMEs and `SKILL.md` for public behavior
- `plans/052-honor-gitignored-runtime-paths.md`
- `plans/README.md`

**Out of scope**:

- A user-authored ignore/config language.
- Suppressing tracked or merely generated paths without repository evidence.
- Parsing prose such as "optional", "generated", or "external repository".
- Reading user-global Git ignore files.
- Treating `.git/info/exclude` as project truth.
- Changing conflict extraction, security scanning, or mutation authority.
- Solving package-root-relative nested paths (a separate deferred class).
- Docker image/RPC/import identifier heuristics.
- Adding Git as a hard runtime requirement for scan/drift; absence must preserve
  current behavior.

## Git workflow

- Branch from current `main`: `fix/052-honor-gitignored-runtime-paths`.
- Use Conventional Commits in English, e.g.
  `fix(paths): honor repository gitignore for runtime paths`.
- Land through one implementation PR; do not push directly to `main`.
- Wait for all nine required checks before squash merge:
  `drift`, `lint`, Node 16/20/22, Python 3.9/3.10/3.12, and `self-test`.

## Steps

### Step 1: Pin the false positive and fail-closed boundaries

Add generated temporary-repository tests before implementation:

1. `.gitignore` ignores a missing runtime directory: Phase 0 and D2 both omit
   it.
2. An adjacent missing unignored path remains a finding.
3. A negated/re-included path remains a finding.
4. Nested `.gitignore` rules apply to a nested AGENTS scope.
5. A tracked/existing path remains healthy.
6. User-global excludes and `.git/info/exclude` do not suppress findings.
7. Missing Git, temporary-metadata failure, timeout, malformed output, and
   unexpected exit all preserve the finding.
8. Spaces/non-ASCII names are transported without splitting.
9. Multiple paths cause one subprocess, not N.

Model parity assertions after
`test_backtick_path_detection_single_sourced_across_stages`.

**Verify**:

```bash
python3 -m unittest \
  tests.test_semantic \
  tests.test_check_drift \
  tests.test_registry_consistency -v
```

Expected before implementation: only the new positive-ignore tests fail. After
implementation: all pass.

### Step 2: Add the contained batch Git-ignore query

Implement the shared helper in `scripts/facts.py`.

- Accept only contained relative tokens from callers.
- Use one bounded subprocess with NUL I/O.
- Sanitize Git configuration and environment as specified above.
- Return an empty set on every unavailable/ambiguous/error path.
- Never print subprocess stderr or repository content.

**Verify**: run the helper tests directly. Expected: exact positive-ignore set,
negations retained, all error paths return empty, and one subprocess call for a
multi-token batch.

### Step 3: Integrate at the shared existence boundary

Update `semantic.compare_paths` and `check_drift.d2_path_drift` to batch
declared candidates and consult the shared ignore result only for would-be
missing paths.

Preserve:

- package-name self-import exemption;
- configured ESLint rule handling;
- subtree suffix index reuse;
- nested scope local/root fallback;
- line attribution and existing output schemas.

Do not reduce `checked` counts merely because an accurate declared path is
ignored; it was still checked against repository truth.

Update `scan_repo`/`scan_monorepo` only as needed to pass the top-level audited
root into package semantic analysis. Add a monorepo regression proving a
package-local missing path ignored by a package `.gitignore` is omitted while a
sibling unignored path remains attributed to that package.

**Verify**:

```bash
python3 -m unittest \
  tests.test_semantic \
  tests.test_check_drift \
  tests.test_registry_consistency -v
```

Expected: Phase 0 and D2 missing sets are byte-for-byte equivalent for the new
fixtures.

### Step 4: Validate against current Qwen Code

Use a clean, pinned checkout at
`f8e6e893166d567df94e82e1d53745e4862f6e38`. Run the dev checkout read-only:

```bash
python3 scripts/scan.py /path/to/qwen-code --json --no-monorepo
python3 scripts/check_drift.py /path/to/qwen-code --json
```

Expected:

- the five `.qwen/*` runtime scratch paths are absent from semantic and D2
  findings;
- `.qwen/commands/`, `.qwen/skills/`, `.qwen/agents/`, and
  `.qwen/team-memory/` re-inclusions are not broadly suppressed;
- unrelated genuine findings are unchanged;
- target commit and `git status --porcelain` are unchanged.

Record the exact commit, commands, evidence boundary, and result in
`EXTERNAL_VALIDATION.md`. Do not claim Treat/Eval coverage if those phases were
not run.

### Step 5: Document the public contract

Update all seven READMEs in parallel and `SKILL.md`:

- missing paths positively ignored by repository `.gitignore` rules are treated
  as deliberate runtime/generated locations;
- global/local Git metadata cannot suppress findings;
- Git failure preserves the old fail-closed finding behavior.

Keep all fenced code blocks byte-identical across translations.

**Verify**:

```bash
python3 scripts/check_readme_sync.py
```

Expected: all seven READMEs aligned and no prose paragraph over the configured
readability budget.

### Step 6: Run all gates and merge

Run every command in "Commands you will need", inspect the final diff for
scope, then open the implementation PR. After all nine contexts are green,
squash-merge and delete the branch.

This is a backward-compatible correctness fix and therefore patch-level unless
implementation requires a public schema/exit change (STOP).

## Test plan

- `facts` helper:
  - positive root ignore;
  - nested ignore;
  - negated re-inclusion;
  - spaces/non-ASCII with NUL transport;
  - global and `.git/info/exclude` isolation;
  - no Git/temp-metadata failure/timeout/malformed/unexpected-exit fail closed;
  - one subprocess per batch.
- Phase 0:
  - ignored runtime path omitted;
  - adjacent missing path retained;
  - monorepo package-local nested `.gitignore` mapped through the top-level
    audited root;
  - checked count stable.
- Phase 2:
  - same ignored/missing sets as Phase 0;
  - nested local/root fallback retained;
  - strict health no longer drops for accurate ignored paths.
- Real Qwen validation as described above.

## Done criteria

- [x] Current Qwen `.qwen/*` scratch paths no longer produce semantic/D2 false
      positives.
- [x] Missing unignored and negated/re-included paths still fail.
- [x] Global excludes and `.git/info/exclude` cannot suppress findings.
- [x] Git absence/temporary-metadata failure preserves current fail-closed
      behavior.
- [x] Phase 0 and Phase 2 share one batch ignore decision and remain in parity.
- [x] No candidate causes per-token subprocess amplification.
- [x] Seven README translations, `SKILL.md`, and external validation are current.
- [x] Full local gates pass.
- [ ] All nine PR checks pass; implementation is
      squash-merged.

## STOP conditions

Stop and report back if:

- synthetic metadata cannot exclude all target `.git` state while retaining
  nested `.gitignore`/negation semantics;
- Git configuration isolation requires trusting user/global state;
- a safe implementation requires a third-party Gitignore parser;
- missing Git would turn scan/drift into an operational failure;
- ignored-path suppression masks a negated/re-included or unrelated missing
  path;
- Phase 0 and Phase 2 need divergent ignore semantics;
- any required CI context is red or pending at merge time.

## Maintenance notes

- `.gitignore` is evidence about expected checkout absence, not permission to
  read ignored files or mutate their paths.
- Keep ignore matching in one contained helper; new diagnostics that classify
  path existence should reuse it rather than invoking Git independently.
- Reviewers should scrutinize config isolation, `.git/info/exclude`, NUL parsing,
  nested scope mapping, and fail-closed error handling.
- Package-root-relative nested paths and image/RPC identifiers remain separate
  follow-ups; do not broaden this repair with prose heuristics.
