# Plan 045: Make scoped eval use the shared lockfile registry

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and honor the STOP conditions. Update the status row in
> `plans/README.md` when the implementation is complete.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 731d9e7..HEAD -- \
>   scripts/eval_run.py scripts/registry.py \
>   tests/test_eval_run.py tests/test_registry_consistency.py \
>   README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md
> ```
>
> If `_scoped_package_manager`, `detect_package_manager`,
> `registry.LOCKFILE_MANAGERS`, or their consistency tests changed materially,
> stop and refresh this plan before implementing.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: Plans 027 and 029 (DONE)
- **Category**: bug / tech debt (fact parity)
- **Planned at**: commit `731d9e7`, 2026-07-16
- **Implementation**: TODO

## Why this matters

Root eval, scan, drift, and Treat all derive Node package-manager facts from the
single source `registry.LOCKFILE_MANAGERS` through `facts.lockfile_managers`.
Target-aware eval is the exception: `_scoped_package_manager` iterates a private
`PKG_MANAGER_LOCKFILES` list in `eval_run.py`.

The private list has already drifted: it additionally recognizes
`pnpm-lock.yml`, while pnpm's documented lockfile is `pnpm-lock.yaml` and the
registry intentionally recognizes only the latter. The same package therefore
has no package-manager fact in root eval but becomes `pnpm` in target-aware
eval. That scoped run generates a confident `package-manager` task and binds the
non-standard `.yml` file as evidence.

Phase 3 must not manufacture different facts solely because `--target` was
supplied. Remove the private map, reuse the registry, and add a consistency
test so eval cannot diverge again.

## Mechanical reproduction

Against `main@731d9e7`:

```bash
python3 - <<'PY'
import sys, tempfile
from pathlib import Path
sys.path.insert(0, "scripts")
import eval_run, facts, registry

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    pkg = root / "packages" / "app"
    pkg.mkdir(parents=True)
    (root / "AGENTS.md").write_text("# Project overview\nDemo.\n")
    (root / "package.json").write_text('{"workspaces":["packages/*"]}\n')
    (pkg / "AGENTS.md").write_text("# Project overview\nApp.\n")
    (pkg / "package.json").write_text('{"scripts":{"test":"vitest"}}\n')
    (pkg / "pnpm-lock.yml").write_text("lockfileVersion: 9\n")

    print("registry:", registry.LOCKFILE_MANAGERS.get("pnpm-lock.yml"))
    print("root:", eval_run.detect_package_manager(pkg))
    print("target:", eval_run._scoped_package_manager(pkg, root))
PY
```

Observed:

```text
registry: None
root: None
target: ('pnpm', ['packages/app/pnpm-lock.yml'])
```

Expected after this plan: both root and scoped detection return no package
manager for `pnpm-lock.yml`; a standard `pnpm-lock.yaml` is still recognized as
pnpm in both paths.

## Current state

`scripts/eval_run.py:531-540` has a private list:

```python
PKG_MANAGER_LOCKFILES = [
    ("pnpm-lock.yaml", "pnpm"),
    ("pnpm-lock.yml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("bun.lockb", "bun"),
    ("bun.lock", "bun"),
    ("package-lock.json", "npm"),
    ("npm-shrinkwrap.json", "npm"),
]
```

`scripts/eval_run.py:608-616` uses it only for scoped facts:

```python
def _scoped_package_manager(fact_root, repo_root):
    for directory in _ancestor_dirs(fact_root, repo_root):
        lock_candidates = {}
        for filename, manager in PKG_MANAGER_LOCKFILES:
            ...
```

Root eval uses `facts.lockfile_managers(root)`, which reads
`registry.LOCKFILE_MANAGERS`. The registry currently contains:

```python
{
    "package-lock.json": "npm",
    "npm-shrinkwrap.json": "npm",
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "bun.lockb": "bun",
    "bun.lock": "bun",
}
```

`tests/test_registry_consistency.py` already asserts semantic, drift, and Treat
reuse the registry, but it does not assert eval's private list or scoped helper.

## Target contract

1. Delete `eval_run.PKG_MANAGER_LOCKFILES`.
2. `_scoped_package_manager` iterates
   `registry.LOCKFILE_MANAGERS.items()` directly (or an equivalent registry
   helper), preserving nearest-scope and ambiguity behavior.
3. `pnpm-lock.yml` is not recognized unless the shared registry is deliberately
   changed in a separate standards-backed decision; this plan does not add it.
4. `pnpm-lock.yaml`, npm, yarn, and bun facts behave exactly as before.
5. Root and scoped eval share the same lockfile vocabulary permanently through
   a consistency test.
6. Python 3.9 standard library only; generated task schema and IDs unchanged.

## Scope

**In scope**:

- `scripts/eval_run.py`
- `tests/test_eval_run.py`
- `tests/test_registry_consistency.py`
- `plans/045-single-source-eval-lockfiles.md`
- `plans/README.md`
- Trilingual READMEs / `SKILL.md` only if a user-facing statement is affected
  (likely no change).

**Out of scope**:

- Adding support for branch lockfiles such as `pnpm-lock.<branch>.yaml`.
- Parsing lockfile contents or accepting arbitrary extensions.
- Changing nearest-scope inheritance, ambiguity handling, task IDs, evidence
  hashing, or generated prompts.

## Steps

### Step 1: Add failing parity tests

Add tests that prove:

- root and scoped detection both ignore `pnpm-lock.yml`;
- scoped detection recognizes `pnpm-lock.yaml` with repository-relative
  evidence;
- `eval_run` no longer has a private lockfile map (or the consistency test
  asserts the scoped path reads the registry);
- all registered npm/yarn/pnpm/bun lockfiles remain recognized.

Model the scoped test after existing target-generation tests in
`tests/test_eval_run.py`; extend
`test_lockfile_managers_single_sourced_and_include_bun` in
`tests/test_registry_consistency.py`.

**Verify**:

```bash
python3 -m unittest discover -s tests -p 'test_eval_run.py' -v
python3 -m unittest discover -s tests -p 'test_registry_consistency.py' -v
```

The `.yml` scoped-parity assertion fails before implementation.

### Step 2: Remove the private map

Delete `PKG_MANAGER_LOCKFILES` and make `_scoped_package_manager` iterate
`registry.LOCKFILE_MANAGERS.items()`. Do not duplicate or reorder the map
elsewhere.

**Verify**: the tests from Step 1 pass; existing target-aware eval tests remain
green.

### Step 3: Run repository gates

```bash
npm run check
node --check bin/cli.js
python3 scripts/check_readme_sync.py
python3 scripts/gen_adapters.py --check
python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json \
  --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts
python3 scripts/check_drift.py . --strict
python3 scripts/eval_run.py --score \
  benchmark/self-eval/results-after-graded.json \
  --tasks benchmark/self-eval/tasks.json --workdir . \
  --evidence AGENTS.md --require-current-evidence --fail-under 80
```

Expected: all exit 0; drift Grade A; self-eval 34/34 Grade A.

### Step 4: PR and merge

- Branch: `fix/045-single-source-eval-lockfiles`
- Commit: `fix(eval): single-source scoped lockfile facts`
- Open one implementation PR.
- Wait for all nine required contexts: `drift`, `lint`, `node (16/20/22)`,
  `self-test`, and `unittest (3.9/3.10/3.12)`.
- Squash-merge only when every context is green.

This is a backward-compatible **patch**.

## Done criteria

- [ ] `PKG_MANAGER_LOCKFILES` no longer exists in `eval_run.py`.
- [ ] Root and scoped eval both ignore `pnpm-lock.yml`.
- [ ] Root and scoped eval both recognize standard registered lockfiles.
- [ ] Registry consistency tests cover eval's scoped lockfile vocabulary.
- [ ] No generated task schema/ID/prompt change.
- [ ] `npm run check`, self scan, strict drift, and evidence-bound eval pass.
- [ ] Implementation PR has all nine required contexts green and is merged.

## STOP conditions

Stop instead of improvising if:

- pnpm official documentation or a real current pnpm release proves
  `pnpm-lock.yml` is a supported default lockfile (bring evidence and decide
  whether the registry should change first);
- removing the local list requires changing scope inheritance or task identity;
- any existing registered lockfile loses coverage;
- a required CI context is red/pending.

## Maintenance notes

- Lockfile vocabulary belongs only in `registry.LOCKFILE_MANAGERS`. Any future
  manager/lockfile addition must update the registry and its consistency tests,
  not an engine-local list.
- Scoped eval may still differ from root eval because nearest scope is a
  deliberate feature; it must not differ in which filenames count as facts.
