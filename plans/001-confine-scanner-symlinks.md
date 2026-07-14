# Plan 001: Keep scanner reads inside the audited repository

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving on. Touch
> only the files listed as in scope. If a STOP condition occurs, stop and report
> instead of improvising. When done, update this plan's status in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 7121ce6..HEAD -- scripts/scan.py tests/test_scan.py README.md README.zh-CN.md README.ja.md SKILL.md`
> If any in-scope file changed, compare the excerpts below with live code before
> proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: security / bug
- **Planned at**: commit `7121ce6`, 2026-07-14

## Why this matters

`scan` promises a read-only audit of a target repository, but the single file
index includes file symlinks. Later `Path.is_file()`, `stat()`, and
`read_bytes()` calls follow them. A repository can therefore name a symlink
`AGENTS.md` (or another recognized config path), point it outside the audited
root, and cause external content to enter scan JSON, reports, conflict evidence,
security findings, or SARIF. The scanner must not read outside its declared
root.

## Current state

- `scripts/scan.py:377-397` builds the index with `os.walk(...,
  followlinks=False)` but appends every filename without checking whether it is
  a symlink or whether its resolved target remains under `root`.
- `scripts/scan.py:513-523` calls `path.is_file()`, which follows symlinks.
- `scripts/scan.py:526-553` calls `stat()`, `open()`, and `read_bytes()` on the
  accepted path, all of which follow the link.
- `scripts/facts.py:135-149` is the repository's existing containment exemplar:
  resolve the candidate and require it to be relative to `root.resolve()`.
- `tests/test_scan.py:1027-1170` contains scanner traversal/performance
  regression tests and is the correct location for new index-boundary tests.

Verified reproduction at planned commit:

```text
repo/AGENTS.md -> ../outside.txt
python3 scripts/scan.py repo --json
```

exits 0 and reports `AGENTS.md` metadata derived from `outside.txt`.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Targeted tests | `python3 -m unittest tests.test_scan -v` | all pass |
| Python lint | `ruff check scripts/scan.py tests/test_scan.py` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | OK |
| Full gate | `npm run check` | exit 0 |
| Self scan | `python3 scripts/scan.py .` | exit 0 |
| Self drift | `python3 scripts/check_drift.py .` | grade A |

## Scope

**In scope**:

- `scripts/scan.py`
- `tests/test_scan.py`
- `README.md`
- `README.zh-CN.md`
- `README.ja.md`
- `SKILL.md`

**Out of scope**:

- `scripts/check_drift.py` path-declaration probing; it already uses
  `facts.within_root`.
- Installer symlink behavior in `bin/cli.js`; installed payload links are an
  intentional feature.
- Following symlinks that resolve to regular files *inside* the target root,
  unless tests show the safest consistent rule is to skip all file symlinks.
- Directory traversal performance refactors.

## Git workflow

- Branch: `fix/scan-symlink-containment`
- Commit: `fix(scan): keep file reads inside repo`
- Open an English PR; squash merge after all CI checks pass.

## Steps

### Step 1: Add failing containment tests

In `tests/test_scan.py`, add a symlink-capability helper or a
`skipUnless`-guarded test near `ScannerPerformanceTests`.

Cover:

1. a recognized config file symlink (`AGENTS.md`) whose target is outside root;
2. an external symlink whose target contains a secret-shaped marker;
3. a normal in-root `AGENTS.md` remains indexed and scanned;
4. if the implementation permits in-root file symlinks, explicitly test that
   behavior; otherwise assert all file symlinks are skipped and document it.

The external path must not appear in `report["files"]`, security findings, or
serialized report output.

**Verify**:
`python3 -m unittest tests.test_scan.ScannerPerformanceTests -v` must fail on
the new external-symlink assertion before the fix.

### Step 2: Enforce the root boundary in the shared index

Modify `build_file_index` so every indexed file is safe before any downstream
matcher sees it. Prefer one shared helper with these properties:

- root is normalized once;
- symlink resolution errors fail closed;
- resolved targets outside root are skipped;
- regular files retain their lexical repo-relative path in output;
- no extra full-tree walk is introduced.

Keep the security boundary in the shared index rather than repeating checks in
every consumer (`iter_matches`, `glob_files`, snapshots, tech-stack markers).

**Verify**:

- targeted scanner tests pass;
- existing `test_tree_is_walked_only_once` still reports exactly one walk;
- existing `test_index_glob_matches_pathlib_glob` is adjusted only if its
  expected set must exclude unsafe symlinks.

### Step 3: Document the boundary

Update synchronized README prose and `SKILL.md` to say scanning never follows a
matched config file outside the audited root. Do not add a new heading or code
block unless all three READMEs stay structurally identical.

**Verify**: `python3 scripts/check_readme_sync.py` prints OK.

## Test plan

- Regression: external `AGENTS.md` symlink is absent from report.
- Security: external secret-shaped content is not scanned or serialized.
- Compatibility: ordinary files still scan.
- Performance: one root walk remains.
- Platform: skip symlink-specific tests when the platform cannot create them.

## Done criteria

- [ ] External file symlinks cannot enter any scanner output.
- [ ] The scanner still walks the tree once.
- [ ] `python3 -m unittest tests.test_scan -v` passes.
- [ ] `ruff check scripts/scan.py tests/test_scan.py` passes.
- [ ] `npm run check` passes.
- [ ] `python3 scripts/check_drift.py .` reports grade A.
- [ ] Only in-scope files and `plans/README.md` changed.

## STOP conditions

- The fix requires following external symlinks for a documented supported use
  case.
- Preventing the read requires a second repository walk.
- A platform-specific symlink behavior cannot be isolated with `skipUnless`.
- In-scope code no longer matches the current-state description.

## Maintenance notes

Any future scanner feature that opens a path directly instead of using
`ScanContext` must reapply the same containment rule. Reviewers should treat
new `Path.is_file()/read_*()` calls on repository-derived paths as a security
boundary.
