# Plan 004: Refuse repository mutations through symlinks or escaping paths

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat c8d2f05..HEAD -- scripts/facts.py scripts/canonicalize.py scripts/check_drift.py bin/cli.js tests/test_canonicalize.py tests/test_check_drift.py tests/test_cli.py README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md`
> If any in-scope file changed, compare the current-state excerpts below with
> live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: security / bug
- **Planned at**: commit `c8d2f05`, 2026-07-15

## Why this matters

The scanner now confines repository-derived reads, but the mutation paths still
follow repository-controlled symlinks. A target repo can commit
`CLAUDE.md -> ../outside/CLAUDE.md`; `stubs --apply` then rewrites the external
target while reporting only `rewrote CLAUDE.md`. The same pattern exists in
`drift --fix --apply`, Cursor-rule deletion, and Node guard writes/removals.
Write-capable commands must never change anything outside the explicitly
selected repository (except the deliberate `.git/hooks` target returned by
Git).

## Current state

- `scripts/facts.py:147-207` is the established containment module for reads:
  `resolve_within_root`, `is_file_within_root`, `read_text_within_root`, and
  `read_bytes_within_root`. Reuse and extend this interface rather than adding
  unrelated `resolve()` checks to every caller.
- `scripts/canonicalize.py:553-601` selects targets with `Path.is_file()`, then
  calls `unlink()` / `write_text()` directly. Those operations follow file
  symlinks.
- `scripts/check_drift.py:153-215,498-505,638-652` directly reads `AGENTS.md`
  and stubs and rewrites D3 paths with `write_text()`.
- `bin/cli.js:852-960` reads and writes guard files with Node filesystem calls;
  `applyGuardChanges()` does not reject symlinks or revalidate containment.
- `AGENTS.md:50-56` currently codifies contained *read/probe* behavior only.

Verified reproduction at the planned commit:

```text
repo/CLAUDE.md -> ../outside/CLAUDE.md
python3 scripts/canonicalize.py --write-stubs repo --apply
```

exits 0 and changes the SHA-256 of `outside/CLAUDE.md`. A second reproduction
with a larger pointer body shows `check_drift.py repo --fix --apply` also
rewrites the external target.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Canonicalize tests | `python3 -m unittest tests.test_canonicalize -v` | all pass |
| Drift tests | `python3 -m unittest tests.test_check_drift -v` | all pass |
| Guard/installer tests | `python3 -m unittest tests.test_cli -v` | all pass |
| Node tests | `node --test bin/*.test.js` | all pass |
| Python lint | `ruff check scripts tests` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | OK |
| Full gate | `npm run check` | exit 0 |
| Self check | `python3 scripts/scan.py . && python3 scripts/check_drift.py .` | scan clean; drift grade A |

## Scope

**In scope**:

- `scripts/facts.py`
- `scripts/canonicalize.py`
- `scripts/check_drift.py`
- `bin/cli.js`
- `tests/test_canonicalize.py`
- `tests/test_check_drift.py`
- `tests/test_cli.py`
- `bin/cli.test.js` only if a pure Node helper is exported/tested there
- `README.md`, `README.zh-CN.md`, `README.ja.md`
- `SKILL.md`
- `AGENTS.md`

**Out of scope**:

- Installer writes under the user's explicit home/project installation targets;
  those already have separate ownership checks.
- Explicit output paths such as `draft -o` or `--write-baseline FILE`; the user
  names those destinations directly. Document them as explicit output paths
  rather than treating them as repository-derived.
- Changing the dry-run report shape except to label unsafe targets as skipped /
  refused.
- Following external symlinks for compatibility. There is no documented use
  case that justifies mutating an external target.

## Git workflow

- Branch: `fix/contain-repository-mutations`
- Commit: `fix(safety): refuse writes through repository symlinks`
- Conventional Commit, English.
- Open one focused PR; squash merge after every CI check is green.

## Steps

### Step 1: Add failing mutation-boundary tests

Use platform-guarded file/directory symlink helpers like the existing scan
tests. Add separate tests proving:

1. `canonicalize --write-stubs --apply` refuses/skips an external
   `CLAUDE.md` symlink and does not change its target;
2. Cursor-rule cleanup never deletes a file reached through an external
   `.cursor/rules` symlink;
3. `drift --fix --apply` does not rewrite an external D3 stub target;
4. drift read-only checks do not read an external `AGENTS.md` or stub;
5. `guard --apply` and `guard --remove --apply` do not overwrite/delete through
   repository worktree symlinks, including `AGENTS.md` and managed workflow
   paths;
6. normal regular files and in-repo symlinks retain the documented behavior
   chosen by the implementation.

Use sentinels/hashes, never sensitive content. For Node guard tests keep
`HOME` isolated exactly like `CliInstallerTests`.

**Verify**: each new external-symlink test fails before implementation, while
the existing happy-path tests still pass.

### Step 2: Deepen the shared Python containment interface

Extend `scripts/facts.py` with write-oriented helpers or validators that make
the invariant hard to misuse. Required properties:

- distinguish a lexical repository path from its resolved target;
- reject any repository-derived symlink for mutation (including an in-repo
  symlink unless there is a strong documented need to preserve it);
- reject a parent-directory symlink before creating a new child;
- support safe regular-file write/delete decisions without opening twice;
- fail closed on resolution/stat errors;
- keep Python 3.9 stdlib-only.

Prefer an interface such as `safe_mutation_path(root, path,
allow_git_dir=False) -> Path | None` over scattered boolean checks. Do not use
the read helper unchanged if it would return the resolved target and thereby
lose the lexical-path identity needed for safe replacement.

**Verify**: focused helper tests plus `ruff check scripts/facts.py`.

### Step 3: Route Treat and Follow-up through the mutation guard

In `canonicalize.py`, filter/refuse unsafe changes before diff generation and
again immediately before `unlink` / write (TOCTOU defense). In
`check_drift.py`, use contained reads for D1–D8 and the mutation guard for D3
apply. Unsafe repository paths must never be reported as successfully fixed.
Return a non-zero status with an actionable message, or list them as manual
attention; choose one deterministic policy and test it.

Keep dry-run non-mutating. Preserve the clean-tree gate; containment is an
additional invariant, not a replacement.

**Verify**: targeted canonicalize/drift suites pass; external sentinels remain
byte-identical.

### Step 4: Enforce the same rule in Node guard operations

Add a small Node helper that uses `lstatSync` on the lexical path and its
existing parent chain, plus `realpathSync` containment under the target worktree.
Repository worktree files must not be symlinks when read, written, or removed.
The `.git/hooks/pre-commit` path is a special, deliberate Git-controlled target:
accept the path returned by `git rev-parse --git-path` but still reject a
symlinked hook file before overwrite/removal.

Revalidate immediately inside `applyGuardChanges`; planning-time checks alone
are insufficient.

**Verify**: `python3 -m unittest tests.test_cli -v` and
`node --test bin/*.test.js` pass, including new external-target sentinel tests.

### Step 5: Document and codify the full mutation contract

Update synchronized READMEs and `SKILL.md`: read-only commands ignore external
repository symlinks; write-capable commands refuse repository-derived symlink
targets and explicit external output paths are a separate opt-in. Expand
`AGENTS.md` Safety from reads/probes to reads, writes, deletes, directory
creation, and guard operations.

**Verify**: docs sync and self scan/drift pass.

## Test plan

- Python: external regular-file symlink, parent-directory symlink, Cursor rules
  directory symlink, broken symlink, and regular-file happy path.
- Drift: read path remains contained; D3 dry-run/apply both refuse unsafe target.
- Node: guard install/remove over symlinked workflow/AGENTS.md; `.git/hooks`
  regular file remains supported; isolated `HOME`.
- Race defense: at minimum unit-test the apply-time revalidation by changing a
  planned target to a symlink before apply.

## Done criteria

- [ ] No Treat/Follow-up/guard repository mutation follows a symlink.
- [ ] External sentinel targets remain byte-identical in all regression tests.
- [ ] Unsafe targets are visible and never counted as fixed/applied.
- [ ] All explicit output-path behavior is documented and unchanged.
- [ ] `npm run check` exits 0.
- [ ] Self drift remains 100/100 grade A.
- [ ] No files outside Scope and `plans/README.md` are modified.

## STOP conditions

- A documented supported workflow requires mutating through a repository
  symlink.
- Safely supporting a target requires a platform-specific native dependency.
- Git worktrees/submodules make the proposed containment helper reject normal
  repository files; report the concrete topology before weakening the rule.
- The fix requires silently replacing a symlink with a regular file rather than
  refusing it; that is a product decision, not an executor assumption.

## Maintenance notes

Treat all new repository-derived write/delete/create operations as a security
boundary. Reviewers should reject direct `write_text`, `unlink`, `fs.writeFile*`,
or `fs.rm*` calls on target-repo paths unless they are immediately guarded by
the shared mutation contract. Explicit user-selected output files must remain
clearly separated from inferred repository paths.
