# Plan 053: Resolve nested AGENTS facts through the lexical package ancestor chain

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md` unless a reviewer maintains the index separately.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat ffcfe32..HEAD -- \
>   scripts/facts.py scripts/check_drift.py scripts/eval_run.py \
>   tests/test_check_drift.py tests/test_eval_run.py \
>   tests/test_registry_consistency.py EXTERNAL_VALIDATION.md \
>   README.md README.zh-CN.md README.ja.md README.es.md README.ko.md \
>   README.pt-BR.md README.fr.md SKILL.md AGENTS.md
> ```
>
> If any in-scope file changed, compare the "Current state" excerpts against
> live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: Plans 018, 021, 045, and 052 (DONE)
- **Category**: correctness / monorepo scope truth
- **Planned at**: commit `ffcfe32`, 2026-07-17
- **Implementation**: IN PROGRESS — PR #236 (plan) / PR #237 (impl);
  implementation branch `fix/053-resolve-nested-package-ancestors`, full local
  gates and pinned Dify validation green, awaiting required CI and merge.

## Why this matters

The AGENTS.md standard encourages nested files for package/module-specific
instructions. A deeply nested canonical file is often below its package
manifest: for example, `cli/src/commands/AGENTS.md` describes paths and commands
relative to `cli/`, not only its own `cli/src/commands/` directory or the
repository root.

Current drift logic checks exactly two roots for a nested canonical file:
the file's parent and the repository root. It skips every lexical ancestor in
between. That creates false D1/D2/D6 findings and can compare a package claim
against the wrong root fact.

At current Dify commit
`96e34e7b24a2f6b7acabb500ef847443405f4b59`,
`cli/src/commands/AGENTS.md` documents:

- `pnpm tree:gen`, declared by `cli/package.json`;
- `src/commands/tree.ts`, present at `cli/src/commands/tree.ts`;
- `src/auth/`, `src/api/`, and `src/errors/`, present below `cli/`.

The current doctor reports two D1 errors and five D2 errors for those valid
claims, dropping drift health to `0/F`. A synthetic package fixture also proves
D6 compares nested Node/package-manager declarations against the repository
root instead of the nearest ancestor package.

## Mechanical reproduction

Repository shape:

```text
repo/
  package.json                 # root:test, Node 18, npm
  .nvmrc                       # 18
  package-lock.json
  cli/
    package.json               # tree:gen, Node 20
    .nvmrc                     # 20
    pnpm-lock.yaml
    src/
      auth/
      commands/
        AGENTS.md
        tree.ts
```

Nested instructions:

```text
Use Node 20 and `pnpm` in this package.
Run `pnpm run tree:gen`.
The registry is `src/commands/tree.ts`.
```

Current output:

```text
D1 Unknown package.json script `tree:gen`
D2 Referenced path `src/commands/tree.ts` does not exist
D6 AGENTS.md claims Node 20 but root `.nvmrc` pins Node 18
D6 AGENTS.md claims Node 20 but root `package.json` requires Node 18
```

All package facts are present at the lexical ancestor `cli/`.

## Current state

### Drift scopes expose only parent + root

`scripts/check_drift.py:535-555`:

```python
def drift_scopes(root):
    root = Path(root).resolve()
    scopes = [{"root": root, "path": "AGENTS.md", "is_root": True}]
    for rel_path in nested_agents(root):
        scopes.append(
            {
                "root": root / Path(rel_path).parent,
                "path": rel_path,
                "is_root": False,
            }
        )
    return scopes
```

`scripts/check_drift.py:714-724`:

```python
fallback_root = root if not scope["is_root"] else None
scoped.extend(d1_command_drift(scope["root"], text, fallback_root=fallback_root))
scoped.extend(d2_path_drift(scope["root"], text, fallback_root=fallback_root))
scoped.extend(d6_fact_drift(scope["root"], text, fallback_root=fallback_root))
scoped.extend(d7_markdown_link_drift(scope["root"], text, fallback_root=fallback_root))
```

Each check has bespoke two-root logic. There is no representation for the
ancestor chain `cli/src/commands → cli/src → cli → repo`.

### Target-aware eval already has the right primitive

`scripts/eval_run.py:611-622`:

```python
def _ancestor_dirs(fact_root, repo_root):
    current = Path(fact_root).resolve()
    repo_root = Path(repo_root).resolve()
    dirs = []
    while True:
        dirs.append(current)
        if current == repo_root:
            return dirs
        if repo_root not in current.parents:
            raise ValueError("effective scope escapes repository")
        current = current.parent
```

Scoped package-manager, Node, and Python fact selection already consume this
chain and prefer the nearest unambiguous ancestor. Plan 045 single-sourced
lockfile vocabulary; Plan 052 added repository-root path mapping. Drift should
reuse the same lexical containment primitive rather than inventing a third
scope model.

### Existing drift contracts to preserve

- `tests/test_check_drift.py:
  test_nested_scope_accepts_explicit_root_commands_and_paths` proves root facts
  remain a last fallback.
- `test_nested_scope_without_local_manifest_still_checks_root_scripts` proves a
  root-only unknown script still fails.
- `test_nested_scope_without_local_facts_falls_back_for_d6` proves root D6 facts
  remain authoritative when no nearer facts exist.
- Plan 052 tests pin repository `.gitignore` mapping and nested attribution.
- D7 Markdown links are resolved relative to the canonical file's directory.
  That is standard Markdown behavior and is not part of this fix.

## Target contract

1. Add one contained lexical ancestor helper shared by eval and drift:
   `scope_parent → ... → repository_root`, ordered nearest-first.
2. The helper rejects a scope outside the repository and follows no external
   symlink as an ancestor fact source.
3. D1 package scripts/Make targets:
   - a command is valid when explicitly declared by any directory on the
     lexical ancestor chain, checked nearest-first;
   - a nearer manifest does not hide an explicit repository-root script: the
     existing root-command compatibility contract remains;
   - do not union arbitrary sibling package scripts;
   - repository root remains the last fallback;
   - an unknown command after the complete chain remains an error.
4. D1 yarn/pnpm binary passthrough:
   - check installed/declared dependencies along the same ancestor chain;
   - retain the existing canonical-scope fallback in which a parent
     `AGENTS.md` may describe a binary supplied by one of its own descendants;
   - do not use that fallback for scripts, paths, Node, or package-manager
     facts, and do not search outside the canonical scope subtree.
5. D2 path resolution:
   - for token `T`, check `scope_parent/T`, then each lexical ancestor `/T`,
     ending at `repo_root/T`;
   - accept the first contained existing path;
   - never search siblings or arbitrary subtree suffixes for nested scopes;
   - a nested canonical scope may retain suffix lookup inside its own subtree
     for conventions such as descendant `_shared/` / `_strategies/` folders;
   - root `AGENTS.md` keeps the existing conservative subtree-suffix behavior
     established by Plans 014/018;
   - Plan 052 ignore matching receives the final repository-relative candidate
     spellings and keeps repository-owned `.gitignore` semantics.
6. D6 Node/package-manager facts:
   - use the nearest ancestor that provides facts;
   - once a directory provides relevant facts, do not fall through to a farther
     ancestor; preserve the current per-source Node mismatch behavior and the
     current competing-lockfile ambiguity behavior at that directory;
   - do not compare a valid package claim against a conflicting repository-root
     default once nearer package facts exist;
   - repository root remains the fallback when the full nearer chain is silent.
7. D7 does not use package ancestors. Markdown links remain relative to the
   canonical Markdown file's directory; repository-root fallback behavior stays
   compatible.
8. Finding schema, canonical-file attribution, baselines, SARIF, PR review,
   health weights, and exit codes remain unchanged.
9. Root AGENTS behavior remains byte-compatible.
10. The ancestor chain is computed once per nested scope and reused by D1/D2/D6,
    not rebuilt for every token/check.
11. Python 3.9 standard library only; no runtime dependency.

## Design

### Shared lexical ancestor primitive

Move/generalize `_ancestor_dirs` from `scripts/eval_run.py` into
`scripts/facts.py`, for example:

```python
def ancestor_dirs(scope_root, repository_root):
    """Return contained lexical directories nearest-first through repo root."""
```

`eval_run.py` imports/reuses it. Keep a compatibility alias only if tests or
external callers require it; otherwise remove the private duplicate and add a
consistency test.

Do not infer package roots from prose. The chain is purely lexical and bounded
by the audited repository.

### Scope record owns the chain

Extend each `drift_scopes()` record with `ancestors`, computed once:

```python
{
    "root": canonical_parent,
    "path": "cli/src/commands/AGENTS.md",
    "is_root": False,
    "ancestors": [canonical_parent, ..., repository_root],
}
```

Pass the chain to D1/D2/D6 through an additive internal argument. Preserve
direct helper-call compatibility by deriving a two-root/lexical chain when only
the historical arguments are supplied.

### Nearest-first facts, not broad union

Use small facts-layer helpers where they deepen the module:

- first ancestor with `package.json` scripts;
- first ancestor with Makefile targets;
- nearest Node fact set;
- nearest package-manager fact set;
- path candidate spellings along the chain.

The first two bullets above are fact readers for one directory, not a stop rule:
D1 may continue through later lexical ancestors to preserve explicit root
commands. Do not use `all_package_scripts`, `all_package_names`, or
`all_package_dependency_names` for nested scope resolution: those walk siblings
and can turn an unrelated package into false validity. Existing root-only
conservative uses may remain.

### D2 and Plan 052

For each declared token, produce contained ancestor candidates nearest-first.
Existing candidate wins. If all are absent, convert each to repository-relative
form and ask the Plan 052 batch ignore helper once. A token is deliberately
absent when an applicable repository-owned ignore rule matches the candidate at
the scope where it is documented.

For nested scopes, do not invoke a repository-wide suffix index after the
lexical chain misses: that would reintroduce sibling false validity. A suffix
index bounded to the canonical scope root is compatible and preserves
descendant conventions. Root scopes keep the old repository-wide index.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Targeted tests | `python3 -m unittest tests.test_check_drift tests.test_eval_run tests.test_registry_consistency -v` | all pass |
| Full gate | `npm run check` | lint + all Python/Node tests pass |
| README sync | `python3 scripts/check_readme_sync.py` | seven READMEs aligned |
| Self scan | `python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json --check-baseline --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts --no-report-file` | exit 0 |
| Self drift | `python3 scripts/check_drift.py . --strict` | 100/100 Grade A |
| Self eval | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | 34/34 Grade A |

## Scope

**In scope**:

- `scripts/facts.py`
- `scripts/check_drift.py`
- `scripts/eval_run.py`
- `tests/test_check_drift.py`
- `tests/test_eval_run.py`
- `tests/test_registry_consistency.py`
- `EXTERNAL_VALIDATION.md`
- all seven READMEs and `SKILL.md`
- `plans/053-resolve-nested-package-ancestors.md`
- `plans/README.md`

**Out of scope**:

- Changing Phase-0 scan package reports or semantic analysis.
- Natural-language scope inference.
- Searching sibling packages or all subtree suffixes for nested scopes.
- Changing D7 Markdown-link semantics.
- Adding `AGENTS.override.md` or another canonical filename.
- Treating every manifest ancestor as a new canonical instruction scope.
- Per-file-type conflict clauses.
- Docker image, RPC method, or generic `org/name` identifier heuristics.
- Automatic all-scope eval expansion.
- Schema, baseline-version, severity, health-weight, or exit-code changes.
- Runtime dependencies or Python newer than 3.9.

## Git workflow

- Branch: `fix/053-resolve-nested-package-ancestors`.
- Commit:
  `fix(drift): resolve nested facts through package ancestors`.
- One focused correctness PR; do not push directly to `main`.
- Wait for all nine required checks before squash merge:
  `drift`, `lint`, Node 16/20/22, Python 3.9/3.10/3.12, and `self-test`.

## Steps

### Step 1: Pin the full false-positive matrix

Create one synthetic repository with conflicting root and package facts:

- root npm/Node 18/root-only script;
- `cli/` pnpm/Node 20/`tree:gen`;
- nested `cli/src/commands/AGENTS.md`;
- valid package-relative path plus a genuinely missing sibling path.

Assert before implementation:

- valid `tree:gen` incorrectly triggers D1;
- valid `src/commands/tree.ts` incorrectly triggers D2;
- D6 incorrectly cites root Node/npm facts;
- genuine unknown command/path still fail;
- D7 link behavior remains document-relative.

Add separate tests for:

- two intermediate ancestor levels;
- nearest ancestor wins over farther/root facts;
- silent intermediate directories fall through;
- sibling package facts do not satisfy a declaration;
- external symlink ancestor cannot supply facts;
- root scope behavior is unchanged.

**Verify**:

```bash
python3 -m unittest tests.test_check_drift -v
```

Expected before implementation: new package-ancestor assertions fail. After
implementation: all pass.

### Step 2: Extract and share lexical ancestor traversal

Move the bounded helper into `facts.py`. Update target-aware eval to reuse it
without changing generated task IDs, facts, or evidence paths.

Add parity tests proving:

- nearest-first order;
- root included exactly once;
- outside-root scope raises/rejects;
- no external symlink fact source;
- existing scoped eval fixtures serialize identically.

**Verify**:

```bash
python3 -m unittest tests.test_eval_run tests.test_registry_consistency -v
```

Expected: every existing target-aware generation test remains green.

### Step 3: Make D1 consume the full chain

Replace bespoke local/root variables with nearest-first ancestor facts.

- Validate scripts and Make targets against the nearest declaring namespace,
  then continue through the remaining lexical ancestors so an explicit
  repository-root command remains valid. Do not scan siblings or descendants.
- Check yarn/pnpm passthrough dependencies on lexical ancestors only.
- Preserve package-manager builtins and prose guards.
- Keep direct `d1_command_drift` callers compatible.

**Verify**: D1 synthetic package tests pass; unknown local/root/sibling commands
still fail with unchanged messages.

### Step 4: Make D2 consume lexical candidates

Resolve every token against the full chain. Reuse Plan 052's repository-relative
ignore batch. Root scope retains the existing subtree index; nested scopes do
not search siblings.

**Verify**:

- package-relative valid path passes;
- missing package path fails;
- sibling-only path fails;
- ignored package runtime path passes;
- external symlink/path containment tests stay green.

### Step 5: Make D6 select nearest ancestor facts

For Node and package manager, inspect ancestor directories nearest-first.

- nearest facts stop farther fallback;
- a contradictory fact set at one level abstains according to existing
  ambiguity policy;
- root is used only when every nearer level is silent;
- finding text remains unchanged when a mismatch is genuine.

**Verify**: package Node 20/pnpm claim passes against package facts despite
conflicting root Node 18/npm; deliberately wrong package claims still produce
D6.

### Step 6: Validate current Dify read-only

Use clean sparse checkout
`96e34e7b24a2f6b7acabb500ef847443405f4b59`.

```bash
python3 scripts/check_drift.py /path/to/dify --json
```

Expected for `cli/src/commands/AGENTS.md`:

- the two `tree:gen` D1 errors disappear;
- the five package-relative D2 errors disappear;
- unrelated/genuine findings remain;
- target HEAD and `git status --porcelain` hash are unchanged.

Record exact checkout scope and evidence boundary in
`EXTERNAL_VALIDATION.md`. Sparse checkout does not prove unrelated repository
findings are complete. Do not claim Scan/Treat/Eval validation.

### Step 7: Document and gate

All seven READMEs and `SKILL.md` must describe lexical package-ancestor fact
resolution for nested drift and state that D7 remains Markdown-relative.

Run every command in the command table, perform a two-axis Standards/Spec review,
then open one implementation PR. Wait for all nine contexts before squash merge.

This is a backward-compatible correctness fix and patch-level unless a STOP
condition requires public schema/exit changes.

## Test plan

- Shared ancestor helper: order, root once, containment, symlink safety.
- Eval parity: existing target-aware generation unchanged.
- D1: nearest script/Make/dependency bin, silent fallback, sibling rejection,
  genuine unknown retained.
- D2: nearest path, intermediate package path, root fallback, sibling rejection,
  Plan 052 ignore mapping, genuine missing retained.
- D6: nearest Node/manager, conflicting root ignored after nearer truth,
  ambiguous nearer facts do not fall through, genuine mismatch retained.
- D7: explicit regression proving no package-root fallback.
- Root report schema/messages and nested attribution unchanged.
- Current Dify sparse read-only validation.

## Done criteria

- [x] Current Dify nested CLI scope loses exactly the reproduced false D1/D2
      findings without suppressing unrelated drift.
- [x] Synthetic D1/D2/D6 package-ancestor matrix passes.
- [x] Sibling package facts never validate a nested declaration.
- [x] D7 remains document-relative.
- [x] Eval and drift share one contained ancestor primitive.
- [x] Root behavior, finding schemas, attribution, baselines, SARIF, and exits
      remain compatible.
- [x] Seven README translations, `SKILL.md`, and external validation are current.
- [x] Full local gates pass.
- [ ] All nine PR checks pass; implementation is
      squash-merged.

## STOP conditions

Stop and report back if:

- correct behavior requires parsing prose to identify a package;
- a sibling package or arbitrary subtree suffix must be searched;
- D7 must change from Markdown-relative semantics;
- nearest contradictory facts cannot preserve fail-closed ambiguity;
- eval task generation changes unexpectedly after helper extraction;
- root finding messages/schema/baseline identity must change;
- more than one repository walk per drift run is required;
- a runtime dependency or Python newer than 3.9 is needed;
- any required CI context is red or pending at merge time.

## Maintenance notes

- Lexical ancestors are fact roots, not new instruction scopes. Canonical scope
  remains defined only by nearest `AGENTS.md`.
- Keep one ancestor helper in `facts.py`; eval and drift must not fork it.
- Reviewers should scrutinize sibling leakage, nearest-fact stopping,
  Plan 052 ignore mapping, and D7 non-change.
- Package-root inference should stay mechanical. Natural-language "run from
  root/package" cues remain out of scope.
