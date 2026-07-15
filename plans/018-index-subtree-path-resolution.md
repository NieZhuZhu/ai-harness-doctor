# Plan 018: Index subtree path resolution once per diagnostic run

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat e4992c8..HEAD -- scripts/facts.py scripts/semantic.py scripts/check_drift.py tests/test_semantic.py tests/test_check_drift.py tests/test_registry_consistency.py plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: performance / correctness / tests
- **Planned at**: commit `e4992c8`, 2026-07-15

## Why this matters

The subtree resolver fixed real false positives in large monorepos, but its
current lazy design walks the entire repository once for every otherwise
missing path token. A document with several stale or externally attributed
paths therefore pays `O(candidate paths × repository tree)` filesystem
traversals in both Phase 0 and Phase 2.

The audit reproduced this with 1,200 non-vendored directories: 20 missing
multi-segment tokens caused 21 `os.walk` calls and took about 25 seconds in
each engine. A doctor should report many stale paths, not become slower because
the patient is sicker. Build one conservative subtree index per diagnostic
call and reuse it without weakening containment or path-resolution semantics.

## Current state

- `scripts/facts.py:343-382` implements a token-at-a-time full walk:

  ```python
  def path_resolves_in_subtree(root, token):
      ...
      for dirpath, dirnames, _filenames in os.walk(root):
          dirnames[:] = [d for d in dirnames if d not in registry.SKIP_DIRS]
          current = Path(dirpath)
          if current == rootp:
              continue
          if exists_within_root(root, current / token):
              return True
      return False
  ```

- `scripts/semantic.py:791-823` invokes that function inside the declaration
  loop. `package_names` is cached, but the subtree walk is not:

  ```python
  for decl in declared_paths(text):
      ...
      if facts.path_resolves_in_subtree(root, token):
          continue
  ```

- `scripts/check_drift.py:114-155` has the same call shape in
  `d2_path_drift()`.

- The measured audit fixture created 1,200 directories and counted
  `facts.os.walk` calls:

  | Engine | Missing tokens | Walk calls | Directories yielded | Time |
  |---|---:|---:|---:|---:|
  | `semantic.compare_paths` | 1 | 2 | 2,462 | 1.37s |
  | `semantic.compare_paths` | 20 | 21 | 25,851 | 25.80s |
  | `check_drift.d2_path_drift` | 20 | 21 | 25,851 | 24.90s |

  One walk comes from the lazy package-name lookup; every additional walk is a
  subtree-token resolution. Exact timings are machine-dependent, but the walk
  count is deterministic evidence of the complexity problem.

- Existing correctness contracts that must survive:
  - multi-segment paths resolve only as an exact trailing path;
  - bare tokens resolve only for `registry.KNOWN_ROOT_FILES`;
  - `registry.SKIP_DIRS` are pruned;
  - external symlinks never satisfy a declaration;
  - safe in-repository file symlinks retain their lexical report path;
  - Phase 0 and D2 return the same missing-token set.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Semantic tests | `python3 -m unittest discover -s tests -p 'test_semantic.py' -v` | all pass |
| Drift tests | `python3 -m unittest discover -s tests -p 'test_check_drift.py' -v` | all pass |
| Cross-engine tests | `python3 -m unittest discover -s tests -p 'test_registry_consistency.py' -v` | all pass |
| Python lint | `ruff check scripts/facts.py scripts/semantic.py scripts/check_drift.py tests/test_semantic.py tests/test_check_drift.py tests/test_registry_consistency.py` | exit 0 |
| Full gate | `npm run check` | exit 0 |
| Self scan | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0; grade A |

## Scope

**In scope**:

- `scripts/facts.py`
- `scripts/semantic.py`
- `scripts/check_drift.py`
- `tests/test_semantic.py`
- `tests/test_check_drift.py`
- `tests/test_registry_consistency.py`
- `plans/README.md`

**Out of scope**:

- Changing which backtick spans are classified as paths.
- Parsing prose to infer which workspace a section describes.
- Changing path-finding messages, severity, exit codes, JSON/SARIF shape, or
  baseline identity.
- Following external symlinks or vendored directories.
- Replacing every fact helper with one global cache.
- Caching across separate CLI invocations or after repository mutation.
- Adding a runtime dependency.
- Editing the trilingual READMEs; this optimization preserves public behavior.

## Git workflow

- Branch: `perf/index-subtree-path-resolution`
- Commit: `perf(paths): index subtree resolution once`
- One focused, backward-compatible performance PR.
- Do not push or open a PR unless the operator instructed it. When instructed,
  squash-merge only after every required check is green.

## Steps

### Step 1: Add a deterministic traversal-count regression

Add temporary-repository tests that create:

- at least 100 non-skipped directories;
- several existing subtree suffixes;
- 20 distinct missing multi-segment tokens;
- one known manifest basename in a subtree;
- one external symlink case when the platform supports it.

Patch or wrap `facts.os.walk` only to count top-level invocations; do not use a
wall-clock assertion in the unit suite. Characterize both
`semantic.compare_paths()` and `check_drift.d2_path_drift()`.

The new tests must first demonstrate that the planned commit performs one
subtree walk per missing eligible token. Keep package-name traversal separate
in assertions: after the fix, each engine may still perform one package-json
walk, but subtree resolution itself must build at most one index.

**Verify**: the new count assertion fails against `e4992c8`; all pre-existing
semantic/path assertions still pass.

### Step 2: Add a conservative reusable subtree index

In `scripts/facts.py`, add a small immutable or read-only index abstraction
owned by this module. It must be built by one pruned `os.walk` and answer:

- whether a multi-segment token equals a safe existing path suffix below root;
- whether a known single-segment manifest basename exists below root.

Normalize separators deterministically to POSIX form for comparison, but keep
all filesystem containment checks on real `Path` objects. Include both
directories and files. Do not index an entry whose resolved target escapes the
audited root.

Preserve the current `path_resolves_in_subtree(root, token)` call form for
external/internal callers. Add an optional index parameter or a separate
indexed helper rather than making global mutable cache state. If safe
in-repository directory symlinks cannot be represented in the fast suffix set,
retain a narrowly bounded fallback for unresolved tokens when such aliases are
present; never follow symlink cycles.

**Verify**: focused pure tests prove known manifest, multi-segment suffix,
missing token, skipped directory, in-repo symlink, and external-symlink
behavior matches the pre-change resolver.

### Step 3: Reuse one lazy index in both engines

In `semantic.compare_paths()` and `check_drift.d2_path_drift()`:

1. keep root existence and package self-import checks first;
2. construct the subtree index only when the first eligible would-be-missing
   token reaches the resolver;
3. reuse the same index for every later token in that function call.

Do not pay for a subtree walk when every declared path already resolves at the
root, is outside the root, is a package self-import, or is not eligible for
subtree resolution.

**Verify**:

- zero eligible missing tokens → zero subtree-index walks;
- 20 eligible missing tokens → one subtree-index walk;
- Phase 0 and D2 report the same missing-token set.

### Step 4: Add a non-gating benchmark reproduction

Add either a test helper or a documented one-off command in the PR body that
recreates the audit's 1,200-directory / 20-token fixture. The acceptance signal
is the deterministic traversal count; record elapsed before/after only as
supporting evidence, not as a flaky unit-test threshold.

Expected post-fix shape: one package-name walk plus at most one subtree-index
walk per engine, rather than 21 walks.

**Verify**: the reproduction reports at most two total `facts.os.walk`
invocations for each engine and the same 20 findings as before.

### Step 5: Run full gates and close the plan

Run every command in the table. Confirm no report shape or exit-code fixture
changed, inspect `git diff --stat`, and mark Plan 018 DONE.

## Test plan

- Existing root path: no index is constructed.
- Twenty missing suffix candidates: one index, twenty findings.
- Existing subtree file and directory suffixes: no finding.
- Known bare manifest in a subtree: no finding.
- Unknown bare token: remains ineligible and missing.
- Skipped/vendored path: never resolves.
- External symlink: never resolves or leaks target existence.
- Safe in-root symlink: retains the current behavior.
- Semantic and D2 missing-token sets remain identical.

## Done criteria

- [x] Subtree resolution walks the repository at most once per
  `compare_paths()` / `d2_path_drift()` call.
- [x] The 1,200-directory / 20-token reproduction drops from 21 total walks to
  at most two while returning the same findings.
- [x] Calls with no eligible missing path pay no subtree-index walk.
- [x] Containment, skip-directory, manifest, suffix, and symlink semantics are
  unchanged.
- [x] Phase 0 and Phase 2 path parity tests pass.
- [x] `npm run check` passes and strict self-drift remains Grade A.
- [x] Only in-scope files are modified.

## Completion evidence (2026-07-15)

- Added a per-call `SubtreePathIndex` in `scripts/facts.py`. It records safe
  lexical suffixes and known subtree manifest basenames from one pruned
  `os.walk`, uses immutable sets/tuples, and has no process-global cache.
- `semantic.compare_paths()` and `check_drift.d2_path_drift()` lazily build the
  index only after a root existence and package-self-import miss, then reuse it
  for all later eligible tokens.
- Deterministic tests prove 20 missing tokens trigger exactly two total
  `facts.os.walk` calls per engine: one package-name scan and one subtree index.
  Root-valid/ineligible paths trigger no subtree-index build.
- The 1,200-directory reproduction returned the same 20 findings:
  - Phase 0: 21 → 2 walks; approximately 25.80s → 0.80s;
  - Phase 2: 21 → 2 walks; approximately 24.90s → 0.94s.
  Timings are supporting local evidence; traversal counts are the regression
  contract.
- Tests preserve skipped-directory behavior, known manifest/suffix resolution,
  safe in-repository file/directory aliases, external-symlink rejection, and
  Phase 0/Phase 2 missing-token parity.
- Full gate at implementation time: 540 Python tests + 26 Node tests, all
  lint/docs/adapter checks, self scan, and strict Grade A drift.

## STOP conditions

- Correctness requires a process-global cache that can become stale.
- The proposed index would follow external directory symlinks or cannot avoid
  symlink cycles.
- A demonstrated path that resolved at `e4992c8` becomes missing, or a genuine
  missing path becomes accepted.
- The only way to reduce traversal count is to weaken containment checks.
- Verification fails twice after a reasonable correction.

## Maintenance notes

The index lifetime is one diagnostic function call over a read-only target.
Future path-policy exceptions belong in `scripts/facts.py` and require matching
Phase 0/Phase 2 tests. Reviewers should scrutinize symlink handling and reject
implicit global memoization even if it benchmarks faster.
