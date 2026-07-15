# Plan 021: Enforce drift checks in every nested AGENTS.md scope

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat ced1530..HEAD -- scripts/check_drift.py scripts/sarif.py scripts/pr_review.py tests/test_check_drift.py tests/test_sarif.py tests/test_pr_review.py tests/test_cli.py EXTERNAL_VALIDATION.md README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json benchmark/self-eval/results-after-graded.json benchmark/self-eval/README.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: correctness / tests / docs
- **Planned at**: commit `ced1530`, 2026-07-15

## Why this matters

Phase 0 already models nested `AGENTS.md` files as nearest-file scopes, but
Phase 2 reads only the repository-root `AGENTS.md`. A package-local instruction
file can therefore name deleted scripts, files, or Markdown links and still
pass `drift --strict` with score 100/grade A. This is a false negative in the
long-term CI gate: the exact instructions nearest to package work are the ones
most likely to guide an agent, yet they are not guarded.

The audit reproduced this with a root package and
`packages/api/AGENTS.md` containing an unknown package script, a missing path,
and a broken Markdown link. `drift --json`, `drift --strict`, and
`drift --sarif` all exited 0 with no active findings; D5 only listed the file as
informational inventory. Make D1/D2/D6/D7 scope-aware while preserving the
root-only behavior of D3/D4/D8, baseline compatibility, and the read-only
filesystem contract.

## Current state

- `scripts/check_drift.py:538-565` reads one file and runs every content check
  against repository-root facts:

  ```python
  agents = root / "AGENTS.md"
  text = facts.read_text_within_root(root, agents, errors="replace") or ""
  findings = []
  findings.extend(d1_command_drift(root, text))
  findings.extend(d2_path_drift(root, text))
  findings.extend(d3_stub_regrowth(root))
  findings.extend(d4_size(root, max_bytes))
  findings.extend(d6_fact_drift(root, text))
  findings.extend(d7_markdown_link_drift(root, text))
  findings.extend(d8_competing_lockfiles(root))
  ...
  info = [
      {"check": "D5", "level": "INFO", "path": p,
       "message": "Nested AGENTS.md inventory"}
      for p in nested_agents(root)
  ]
  ```

- `nested_agents()` at `scripts/check_drift.py:437-452` already performs a
  pruned, non-symlink-following walk and rejects files resolving outside the
  audited root. It returns repository-relative POSIX paths, but callers never
  read or check those files.

- The individual content checks accept a generic fact root and text:
  - D1 reads `package.json` scripts and `Makefile` targets from the supplied
    root;
  - D2 interprets declared paths relative to the supplied root and has a lazy
    subtree index fallback;
  - D6 reads `.nvmrc`, `package.json#engines.node`, and lockfiles from the
    supplied root;
  - D7 resolves Markdown links relative to the supplied root.

  This is the correct seam: for a nested canonical file, call these checks with
  its parent directory as the scope root. Do not create a second parser.

- Root findings from D1/D2/D6/D7 historically omit `path`; the GitHub guard
  supplies `--default-path AGENTS.md`. Drift baseline identity is
  `(check, message, path)` (`scripts/check_drift.py:486-535`). Adding
  `"path": "AGENTS.md"` to old root findings would invalidate every existing
  scope-less baseline, so root finding shape must remain unchanged.

- `scripts/sarif.py:244-260` already uses a finding's `path` and otherwise
  defaults to `AGENTS.md`. `scripts/pr_review.py:536-580` already inlines a
  finding that has a safe path and positive line. A nested finding will flow
  through both surfaces correctly if it carries its repository-relative
  canonical-file path.

- Phase 0's package behavior is the compatibility model: monorepo package scans
  analyze a package-local `AGENTS.md` against facts rooted at that package.
  This plan does not invent parent-manifest inheritance or natural-language
  “run from repo root” inference.

## Target contract

1. The root `AGENTS.md` remains mandatory and is checked exactly as today.
2. Every contained, regular nested file named exactly `AGENTS.md`, excluding
   `scan.SKIP_DIRS` and external symlinks, becomes a **drift scope** whose root
   is that file's parent directory.
3. D1, D2, D6, and D7 run once per drift scope:
   - commands/facts are checked against that scope root;
   - backtick-declared paths are resolved using the existing D2 policy rooted
     at that scope;
   - Markdown links are resolved relative to the containing `AGENTS.md`, as
     Markdown requires.
4. A nested finding keeps its existing check/message/line shape and adds
   `"path": "<repo-relative>/AGENTS.md"`. Root findings keep their historical
   missing-path shape for baseline compatibility.
5. D3 stub ownership, D4 root context-size policy, D8 repository lockfile
   ambiguity, and custom plugin execution remain once-per-repository. D5
   remains the non-blocking inventory section; its listed files are now also
   covered by the applicable content checks.
6. Nested errors participate in `ok`, health score/grade, `--strict`,
   `--min-score`, baselines, `--fix` manual-attention output, SARIF, PR review,
   and exit status exactly like root errors.
7. Scope evaluation is read-only. No target repository file is written, and no
   repository-derived path may escape through `..` or a symlink.

This contract intentionally covers the standard `AGENTS.md` nearest-file
hierarchy only. It does not turn every recognized tool config into a Phase 2
canonical file, and it does not add a second meaning for registry
`AGENT.md`.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Drift tests | `python3 -m unittest discover -s tests -p 'test_check_drift.py' -v` | all pass |
| SARIF tests | `python3 -m unittest discover -s tests -p 'test_sarif.py' -v` | all pass |
| PR review tests | `python3 -m unittest discover -s tests -p 'test_pr_review.py' -v` | all pass |
| Consumer integration | `python3 -m unittest discover -s tests -p 'test_cli.py' -v` | all pass |
| Python lint | `ruff check scripts/check_drift.py scripts/sarif.py scripts/pr_review.py tests` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | `OK` |
| Full gate | `npm run check` | exit 0 |
| Evidence gate | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0 |
| Self scan | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0; grade A |

## Scope

**In scope**:

- `scripts/check_drift.py`
- `scripts/sarif.py` / `scripts/pr_review.py` only if an integration adjustment
  is needed after adding nested finding paths
- matching tests in `tests/test_check_drift.py`, `tests/test_sarif.py`,
  `tests/test_pr_review.py`, and `tests/test_cli.py`
- synchronized `README.md`, `README.zh-CN.md`, `README.ja.md`
- `SKILL.md`
- one read-only real-repository result in `EXTERNAL_VALIDATION.md`
- a compact maintenance invariant in `AGENTS.md`
- evidence-bound `benchmark/self-eval/` refresh after `AGENTS.md` changes
- `plans/README.md`

**Out of scope**:

- D3 canonical stub rewriting below every nested scope.
- Applying D4 size thresholds independently to nested instruction files.
- Treating nested lockfiles as D8 repository-level ambiguity.
- Running custom plugins once per nested file or changing plugin context.
- Inferring that package facts inherit from an ancestor workspace when the
  nested scope has no local fact source.
- Parsing prose such as “run this from the repository root.”
- Changing Phase 0 conflict/scope behavior delivered by Plan 020.
- Adding drift checks for `AGENT.md`, `CLAUDE.md`, Cursor frontmatter/globs, or
  other tool-specific applicability rules.
- Auto-fixing any nested semantic drift.
- Changing existing root finding messages, baseline version, or exit codes.
- Adding a runtime dependency.

## Git workflow

- Branch: `fix/nested-agents-drift`
- Commit: `fix(drift): enforce nested AGENTS scopes`
- One focused correctness PR with tests and public docs.
- Do not push directly to `main`. Open an English PR, wait for all nine
  required contexts, then squash-merge and delete the branch.
- This repairs a false negative but expands the public CI gate. Classify it as
  a backward-compatible feature for release purposes; the combined batch is at
  least minor.

## Steps

### Step 1: Add a failing end-to-end nested-scope characterization

In `tests/test_check_drift.py`, create a temporary repository with:

- a clean root `AGENTS.md` and root `package.json`;
- `packages/api/package.json` with a known `test:api` script;
- `packages/api/AGENTS.md` that references:
  - one valid local script and one removed local script;
  - one valid package-relative path and one missing package-relative path;
  - one valid package-relative Markdown link and one missing link;
- optionally a package-local lockfile or `.nvmrc` contradiction for D6.

First assert the current `ced1530` implementation emits only D5 inventory and
misses the nested errors. Then encode the target assertions:

- nested D1/D2/D6/D7 findings exist;
- each has `path == "packages/api/AGENTS.md"` and its local line;
- the valid local declarations stay silent;
- `--strict` exits non-zero and score/grade reflect active findings;
- the root file remains clean.

Add a sibling package with clean instructions so the test proves facts and
findings do not bleed between scopes.

**Verify**: the new regression assertions fail against `ced1530` for the
documented false negative, while all pre-existing root tests still pass.

### Step 2: Centralize scope enumeration and finding attribution

Refactor `scripts/check_drift.py` so one helper returns deterministic scope
records in this order:

```python
[
    {"root": repository_root, "path": "AGENTS.md", "is_root": True},
    {"root": repository_root / "packages/api",
     "path": "packages/api/AGENTS.md", "is_root": False},
]
```

Requirements:

- reuse the existing pruned `nested_agents()` walk, or replace it with one
  equally contained deterministic walk; do not add multiple filesystem walks;
- read each file through `facts.read_text_within_root(repository_root, ...)`;
- skip unreadable/external-symlink files rather than reading outside the
  audited root;
- attach the canonical file path to findings from nested scopes only;
- do not mutate the dicts returned by shared checks in a way that affects
  another scope.

Use a small helper such as `attribute_scope_findings(findings, scope)` rather
than repeating path logic after D1/D2/D6/D7.

**Verify**: unit tests cover stable root-first ordering, skipped directories,
an external file symlink, sibling scopes, and root finding shape with no
`path`.

### Step 3: Run only content-relative checks per scope

In `run_checks()`:

- loop over the root + nested scope records;
- run D1, D2, D6, and D7 with `scope["root"]` and that scope's text;
- keep D3, D4, and D8 outside the loop and rooted at the repository;
- preserve strict escalation, baseline filtering, health computation, and
  plugin execution after the complete built-in finding list is assembled;
- keep plugin context's `agents_text` as the root canonical text to avoid a
  silent plugin API change;
- derive D5 inventory from the same nested scope records so discovery cannot
  diverge.

Do not catch broad exceptions around a nested scope. The shared fact readers
already fail safely; a real programming error must remain visible to tests/CI.

**Verify**: the characterization passes; root-only fixtures have byte-compatible
JSON apart from no newly applicable nested findings; a clean nested scope keeps
exit 0 and grade A.

### Step 4: Prove every output and adoption path preserves nested identity

Add focused tests for:

1. baseline payload writes distinct root and nested findings with the same
   message;
2. an old scope-less root baseline still suppresses the corresponding root
   finding;
3. a nested baseline suppresses only the matching canonical path, not a sibling;
4. `--fix` lists nested D1/D2/D6/D7 as manual attention and writes nothing;
5. drift SARIF uses `packages/api/AGENTS.md` and the nested line;
6. PR review can inline a nested finding without `--default-path`;
7. the installed GitHub guard's combined scan+drift review retains the nested
   path in its dry-run payload.

Modify `scripts/sarif.py` or `scripts/pr_review.py` only if one of these tests
exposes a real integration defect. Their current generic path handling should
make code changes unnecessary.

**Verify**: all four focused test commands in the command table pass.

### Step 5: Validate read-only behavior on a real nested-AGENTS repository

Use a disposable checkout of `mastra-ai/mastra`, `sst/opencode`, or another
public repository with at least three nested `AGENTS.md` scopes. Record its
commit and `git status --porcelain`, then run the development checkout:

```bash
python3 scripts/check_drift.py /path/to/repo --json
python3 scripts/check_drift.py /path/to/repo --sarif
```

For every newly surfaced nested finding, directly verify the cited local
script/path/link against that package before labeling it genuine. A clean
result is acceptable and must be recorded as clean; do not manufacture a
finding. Confirm the target worktree status is byte-identical after both runs.

Append one row/detail to `EXTERNAL_VALIDATION.md` with the evidence boundary:
Phase 2 drift only, not the full four-phase chain.

**Verify**: target `git status --porcelain` is unchanged; JSON and SARIF agree
on nested finding paths; the log records the commit and honest result.

### Step 6: Document the guarded scope contract

Update all three READMEs and `SKILL.md`:

- D5 itself remains informational inventory;
- each listed nested `AGENTS.md` is now guarded by D1/D2/D6/D7 using its parent
  as fact/path scope;
- D3/D4/D8 and custom plugins remain repository-root checks;
- nested findings carry canonical-file paths into baselines, SARIF, and PR
  review;
- root baseline compatibility is preserved.

Keep fenced blocks, tables, links, and heading levels synchronized. In
`AGENTS.md`, add or tighten one compact invariant: changes to drift scope
enumeration must preserve root compatibility, local fact roots, contained
reads, and attributed output. Keep the file below the strict D4 threshold.

Because `AGENTS.md` is evidence-bound, refresh and regrade the committed
self-eval honestly; do not claim a model run.

**Verify**: docs sync, evidence freshness, self scan, and strict drift all pass.

### Step 7: Run the full gate and merge

Run every command in the table. Open an English PR that includes:

- the minimal false-negative reproduction;
- the root-vs-nested check boundary;
- baseline/SARIF/PR-review compatibility evidence;
- the real repository validation result;
- release classification.

Wait for `drift`, `lint`, Node 16/20/22, `self-test`, and Python
3.9/3.10/3.12 to all succeed. Admin bypass may resolve only the sole-maintainer
self-review deadlock; it must not bypass a red or pending check.

**Verify**: all nine required contexts are green before squash merge; branch is
deleted; `main` contains the squash commit.

## Test plan

- Root content checks retain historical JSON and baseline identity.
- Nested D1 checks package-local valid and missing scripts.
- Nested D2 checks package-relative valid/missing paths without cross-scope
  bleed.
- Nested D6 checks only unambiguous package-local facts.
- Nested D7 resolves links from the nested canonical file's directory.
- Clean sibling and deeper scopes stay independent.
- Skipped directories and external symlinks do not become drift scopes.
- Strict mode, score, minimum score, baseline, fix preview, SARIF, and PR review
  all consume nested findings consistently.
- Read-only external validation leaves the target checkout unchanged.

## Done criteria

- [ ] The reproduced nested D1/D2/D6/D7 false negative is detected with the
  repository-relative nested `AGENTS.md` path and local line.
- [ ] Root-only drift report/baseline behavior remains backward-compatible.
- [ ] D3/D4/D8 and plugins still run once per repository.
- [ ] Nested findings affect strict exit, health, baseline, fix/manual output,
  SARIF, and PR review consistently.
- [ ] No contained-read or symlink regression is introduced.
- [ ] A real public nested-AGENTS repository is checked read-only and logged
  with an honest evidence boundary.
- [ ] Trilingual docs and `SKILL.md` describe the new scope contract.
- [ ] `AGENTS.md` records the maintenance invariant and remains grade A.
- [ ] Every command in the command table passes.
- [ ] All nine required PR checks are green before squash merge.

## STOP conditions

Stop and report back (do not improvise) if:

- Any in-scope excerpt has changed semantically since `ced1530`.
- Correct nested behavior requires guessing whether a command should run from
  the repository root rather than the nested scope.
- The implementation would need to parse prose, frontmatter, or tool-specific
  glob applicability.
- Root findings must gain a path or baseline version must change to implement
  nested attribution.
- The solution needs more than one additional full repository walk per drift
  run.
- A target repository must be modified to perform validation.
- A step's verification fails twice after a reasonable focused fix.
- The implementation requires a runtime dependency or Python newer than 3.9.

## Maintenance notes

- `nested_agents()` becomes both inventory and execution scope discovery.
  Review any future change to it as a gate-coverage change, not a rendering
  tweak.
- D1/D2/D6/D7 must remain shared parsers; do not fork extraction logic for
  nested files.
- A nested finding's `path` is part of its baseline identity and downstream
  source location. Never replace it with the scope directory.
- Scope-aware eval generation is intentionally deferred. This plan guards
  nested instructions but does not claim Phase 3 generates package-local
  efficacy tasks.
