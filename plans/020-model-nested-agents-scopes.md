# Plan 020: Make conflict diagnostics honor nested AGENTS.md scopes

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat e4992c8..HEAD -- scripts/scan.py scripts/scan_render.py scripts/canonicalize.py scripts/sarif.py scripts/pr_review.py tests/test_scan.py tests/test_canonicalize.py tests/test_sarif.py tests/test_pr_review.py EXTERNAL_VALIDATION.md README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json benchmark/self-eval/results-after-graded.json benchmark/self-eval/README.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED
- **Depends on**: Plan 018 should land first so large nested-scope fixtures do
  not retain the repeated subtree-walk cost
- **Category**: correctness / direction / architecture / tests / docs
- **Planned at**: commit `e4992c8`, 2026-07-15

## Why this matters

Nested `AGENTS.md` files are not independent global declarations. The AGENTS.md
standard says agents read the nearest file in the directory tree, with the
closest file taking precedence so each subproject can override repository-wide
guidance. The scanner inventories nested files, but its conflict engine flattens
every recognized config into one global bucket.

That makes valid monorepo overrides fail `--fail-on-conflicts`: a root using
`npm test` and `packages/api/AGENTS.md` using `pnpm test` are diagnosed as a
global contradiction even though their effective scopes differ. The audit
reproduced the false positive in a synthetic workspace and on
`mastra-ai/mastra`, a 26k-star monorepo with package-local AGENTS files. Model
the deterministic directory hierarchy, report actual same-scope conflicts, and
make intentional parent→child overrides visible as evidence rather than
blocking findings.

## Current state

- The public standard at <https://agents.md/> states: “Agents automatically read
  the nearest file in the directory tree, so the closest one takes precedence
  and every subproject can ship tailored instructions.” This plan implements
  only that explicit filesystem rule; it does not infer scope from prose.

- `scripts/scan.py:57-73` classifies both `AGENTS.md` and `AGENT.md` as canonical
  instruction files and discovers them recursively:

  ```python
  for name in reg.get("canonical", []):
      patterns.append((name, [name, f"**/{name}"]))
  ```

- `scripts/scan.py:870-903` ignores file location when grouping values:

  ```python
  def find_conflicts(files):
      by_signal = {}
      for f in files:
          ...
          by_signal.setdefault(signal, {}).setdefault(key, []).append(sig)
      ...
      if len(groups) > 1:
          conflicts.append({"signal": signal, "values": ...})
  ```

- `scan_repo()` at `scripts/scan.py:1377-1388` passes every discovered root and
  nested config to that global function, then feeds its result into G10 and the
  report:

  ```python
  conflicts = find_conflicts(files)
  report = {
      ...
      "conflicts": conflicts,
      "nested": nested_agents(result_files),
      ...
      "gaps": find_gaps(root, surface, conflicts, ctx),
  }
  ```

- Minimal reproduction at the planned commit:
  - root `AGENTS.md`: `Use npm`, `Use npm test`;
  - `packages/api/AGENTS.md`: `Use pnpm`, `Use pnpm test`;
  - a workspace manifest includes `packages/*`;
  - root `scan_repo()` reports `package_manager` and `test_command` conflicts;
  - scanning `packages/api` independently is clean.

- A stronger synthetic reproduction with three sibling package scopes reports a
  four-way `npm`/`pnpm`/`yarn`/`bun` root conflict even though sibling scopes
  never apply to the same target.

- Current `mastra-ai/mastra` evidence:
  - root `AGENTS.md` describes colocated Vitest tests;
  - `docs/AGENTS.md` uses package-local `pnpm test:*` commands;
  - `mastracode/AGENTS.md` uses both root scripts and focused `vitest run`;
  - `packages/memory/AGENTS.md` and `packages/auth/AGENTS.md` define their own
    package test commands.
  Flattening 21 AGENTS files currently emits a `test_command` conflict across
  those disjoint/effective scopes.

- Scope-unaware output propagates to:
  - Markdown: `scripts/scan_render.py:39-47`;
  - Treat plan: `scripts/canonicalize.py:90-112`;
  - baselines: `scripts/scan.py:1574-1618`;
  - SARIF: `scripts/sarif.py:209-215`;
  - PR comments: `scripts/pr_review.py:180-213`.

- This plan deliberately does **not** solve the previously deferred same-line
  example “Biome (tabs for code, 2 spaces for JSON).” File-type scope requires
  natural-language semantics, not directory precedence, and remains deferred.

## Target contract

Use these deterministic definitions:

1. A **canonical scope root** is the parent directory of a discovered canonical
   `AGENTS.md` or `AGENT.md`; the repository root is `"."`.
2. For any discovered instruction/config file, its **effective diagnostic
   scope** is the deepest canonical scope root that is an ancestor of that
   file's lexical repository-relative path; if none is nested, use `"."`.
3. A **blocking conflict** requires different normalized values for the same
   signal inside the same effective diagnostic scope.
4. Different sibling scopes do not conflict because they cannot both be the
   nearest canonical file for one target.
5. Different ancestor/descendant scope values are **declared overrides**:
   non-blocking evidence that the nearer scope changes inherited guidance.
6. Scope is derived only from contained lexical paths. Never parse prose, glob
   applicability frontmatter, or external-repository references in this plan.

These are diagnostic scopes, not a claim that every supported third-party tool
implements AGENTS.md precedence identically. Same-scope tool-specific files
remain conflict evidence because agents may read them alongside the canonical
file.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Scanner tests | `python3 -m unittest discover -s tests -p 'test_scan.py' -v` | all pass |
| Treat tests | `python3 -m unittest discover -s tests -p 'test_canonicalize.py' -v` | all pass |
| SARIF tests | `python3 -m unittest discover -s tests -p 'test_sarif.py' -v` | all pass |
| PR review tests | `python3 -m unittest discover -s tests -p 'test_pr_review.py' -v` | all pass |
| Python lint | `ruff check scripts/scan.py scripts/scan_render.py scripts/canonicalize.py scripts/sarif.py scripts/pr_review.py tests` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | OK |
| Full gate | `npm run check` | exit 0 |
| Evidence gate | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0 |
| Self scan | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0; grade A |

## Scope

**In scope**:

- `scripts/scan.py`
- `scripts/scan_render.py`
- `scripts/canonicalize.py`
- `scripts/sarif.py` and `scripts/pr_review.py` only to preserve scoped
  attribution for true conflicts
- matching tests in `tests/`
- synchronized READMEs and `SKILL.md`
- `EXTERNAL_VALIDATION.md`
- compact maintenance invariant in `AGENTS.md`
- evidence-bound `benchmark/self-eval/` refresh after `AGENTS.md` changes
- `plans/README.md`

**Out of scope**:

- Natural-language parsing of “for JSON”, “in the backend”, or “in repository
  X” clauses.
- Per-extension/glob/frontmatter applicability for Cursor, Copilot, or other
  tool-specific rule formats.
- A general rules generator or Ruler/rulesync-style distribution system.
- Changing semantic declaration-vs-code or Phase 2 D1/D2 checks.
- Treating intentional overrides as SARIF/PR-review findings.
- Automatically editing, merging, or deleting nested AGENTS files.
- Changing conflict exit code 7 or suppressing genuine same-scope conflicts.
- Adding a runtime dependency.

## Git workflow

- Branch: `feat/scoped-conflict-diagnostics`
- Commit: `feat(scan): model nested instruction scopes`
- One backward-compatible feature PR with additive JSON/Markdown evidence.
- Do not push or open a PR unless the operator instructed it. When instructed,
  squash-merge only after every required check is green.

## Steps

### Step 1: Characterize hierarchy cases before changing behavior

Add focused temporary-repository tests covering:

1. root `npm` + nested `pnpm` → no blocking conflict; one parent→child override;
2. root `npm` + root `CLAUDE.md` `pnpm` → root same-scope conflict;
3. nested `AGENTS.md` `pnpm` + nested `CLAUDE.md` `npm` → nested same-scope
   conflict;
4. sibling nested scopes `pnpm` and `yarn` → neither conflict nor override
   between siblings;
5. root→package→package/subdir chain → nearest canonical ancestor and ordered
   override evidence;
6. no nested canonical file → existing conflict JSON stays unchanged except for
   explicitly documented additive fields;
7. `AGENT.md` follows the registry's canonical classification;
8. skipped directories and external symlinks never create scopes.

At least the first case must fail against `e4992c8`, proving the regression.

**Verify**: new characterization fails only on the current flattening behavior;
existing conflict tests stay green.

### Step 2: Build a lexical canonical-scope map

In `scripts/scan.py`, add pure helpers that:

- collect canonical file paths from the already-built `files` inventory using
  `registry.load_canonical()`;
- normalize each parent directory to `"."` or a repository-relative POSIX path;
- assign every file to its deepest canonical ancestor using path-component
  comparison, not string-prefix guessing (`packages/a` must not match
  `packages/ab`);
- expose parent relationships deterministically.

Reuse `ScanContext`'s existing contained inventory. Do not walk the repository
again and do not resolve external paths to manufacture a scope.

Recommended additive report shape:

```json
"instruction_scopes": [
  {"path": "AGENTS.md", "scope": ".", "parent": null},
  {
    "path": "packages/api/AGENTS.md",
    "scope": "packages/api",
    "parent": "."
  }
]
```

If both `AGENTS.md` and `AGENT.md` exist in one directory, keep deterministic
registry order and treat the directory as one scope; the two files can still
conflict within it.

**Verify**: pure tests cover root, nested, sibling, similarly prefixed
directories, duplicate canonical names, skipped paths, and stable ordering.

### Step 3: Separate conflicts from declared overrides

Refactor signal analysis without changing extraction regexes:

- preserve each signal's source `path`, `line`, and evidence;
- attach its computed diagnostic scope;
- group conflicts by `(scope, signal, normalized value)`;
- emit a blocking conflict only when a single scope has 2+ values;
- compare ancestor/descendant scopes for the same signal and emit non-blocking
  override records when the child's values differ from inherited parent
  values;
- never compare siblings as an override chain.

Recommended additive override shape:

```json
"scope_overrides": [
  {
    "signal": "package_manager",
    "parent_scope": ".",
    "scope": "packages/api",
    "parent_values": ["npm"],
    "values": ["pnpm"],
    "evidence": [/* existing safe path/line records */]
  }
]
```

For a true non-root conflict, add `"scope": "packages/api"` to that conflict.
Keep root conflict output backward-compatible by omitting or using the agreed
canonical root representation consistently. Extend baseline identity with a
non-empty scope only; existing scope-less v1 baseline entries must still load
and match root conflicts.

Do not label every child repetition as an override: if normalized values are
the same as inherited values, it is consistent inheritance and needs no record.

**Verify**: all hierarchy cases pass; current root-only conflict fixtures and
baseline tests remain compatible.

### Step 4: Make scopes actionable without turning overrides into failures

Update Markdown rendering:

- add an `Instruction scopes` section listing each canonical file, its scope,
  and parent;
- label true conflict scope where non-root;
- add a `Declared scope overrides (non-blocking)` section with parent/child
  values and file:line evidence;
- explicitly say overrides are expected nearest-file behavior and are excluded
  from `--fail-on-conflicts`.

Update Treat plan rendering so it asks humans to adjudicate only true
same-scope conflicts. Include scope overrides as context to preserve while
consolidating; never recommend collapsing every nested AGENTS file into the
root.

Update SARIF and PR review for **true scoped conflicts only**:

- include the non-root scope in the message/evidence;
- preserve package-prefix attribution;
- do not traverse `scope_overrides` as findings.

**Verify**: Markdown snapshots, Treat output, SARIF, PR review, fail-on gate, and
baseline tests prove overrides are visible but non-blocking.

### Step 5: Validate against a real nested-AGENTS monorepo

Use a disposable checkout of current `mastra-ai/mastra` (or another public repo
with at least three nested AGENTS scopes if that repo becomes unavailable).
Run the development checkout read-only:

```bash
python3 scripts/scan.py /path/to/mastra --json --fail-on-conflicts
```

Manually inspect every remaining conflict:

- cross-scope root/package test-command variation must appear as non-blocking
  override evidence, not one global conflict;
- any same-scope conflict must retain both values and source lines;
- no files in the target repository may change.

Log the date, selected commit, scope count, before/after finding class, and PR
in `EXTERNAL_VALIDATION.md`. Do not claim the full four-phase chain if only scan
was run.

**Verify**: hash or `git status --porcelain` confirms the target stayed clean;
the new log has an honest evidence boundary.

### Step 6: Document the model and maintenance contract

Synchronize the three READMEs and `SKILL.md`:

- nearest canonical file precedence;
- deterministic lexical scope definition;
- same-scope conflict vs non-blocking override;
- additive JSON keys and Markdown sections;
- explicit non-goals (no prose/file-type scope inference).

Add a compact `AGENTS.md` invariant that scope-aware behavior remains
single-sourced, deterministic, and covered across Markdown/baseline/SARIF/PR
review. Keep the file below strict D4.

Refresh/regrade evidence-bound self-eval honestly after changing `AGENTS.md`;
add an objective task only if the new invariant cannot be tested by an existing
task. Do not claim a fresh model run.

**Verify**: docs sync, evidence freshness, score ≥80, and strict drift pass.

### Step 7: Run full gates and close the plan

Run every command in the table. Inspect changed JSON fixtures for additive
compatibility, verify only in-scope files changed, and mark Plan 020 DONE.

## Test plan

- Root vs nested differing values: override, no conflict, exit 0.
- Root same-scope tool disagreement: conflict, exit 7 with the flag.
- Nested same-scope tool disagreement: scoped conflict, exit 7.
- Sibling values: independent scopes, no conflict/override between siblings.
- Three-level chain: correct nearest parent and deterministic override order.
- Same inherited value: no noisy override.
- `AGENTS.md` + `AGENT.md` in one directory: one scope, conflict possible.
- Similar directory prefixes: component-safe ancestry.
- Existing root conflict baseline remains valid.
- Scoped conflict baseline identity distinguishes separate nested scopes.
- Overrides never enter SARIF or PR review as active findings.
- Treat output preserves legitimate nested files instead of recommending
  global collapse.

## Done criteria

- [x] Conflict gates compare values only within one deterministic diagnostic
  scope.
- [x] Parent→child differences are visible as non-blocking overrides.
- [x] Sibling scopes do not manufacture global conflicts.
- [x] Genuine root and nested same-scope conflicts still fail exit 7.
- [x] Scope metadata is visible in JSON, Markdown, and Treat output.
- [x] SARIF/PR review contain true scoped conflicts only.
- [x] Existing root baselines remain compatible; scoped identities do not
  collide.
- [x] A real nested-AGENTS public repo validates the behavior read-only and is
  logged in `EXTERNAL_VALIDATION.md`.
- [x] `npm run check`, evidence freshness, and strict drift pass.
- [x] Only in-scope files are modified.

## Completion evidence (2026-07-15)

- `scripts/scan.py` now derives canonical scopes from contained lexical
  `AGENTS.md` / `AGENT.md` paths already present in the shared file inventory;
  no extra tree walk or prose inference is used.
- Same-scope normalized values produce blocking `conflicts`; root findings keep
  their historical JSON shape, while non-root conflicts add `scope`.
  Ancestor-to-descendant differences produce deterministic non-blocking
  `scope_overrides`, and sibling scopes are never compared.
- JSON and Markdown expose `instruction_scopes` plus override evidence. Treat
  plans preserve nested canonical files (including overlap cases) instead of
  recommending root stubs. Overrides are intentionally absent from SARIF and PR
  review; true scoped conflicts retain scope there and in baseline identity.
- Characterization covers root/nested same-scope conflicts, sibling isolation,
  three-level nearest ancestors, duplicate `AGENTS.md`/`AGENT.md` scopes,
  component-safe similarly prefixed paths, no-op inherited values, exit 7,
  baseline compatibility, Treat, Markdown, SARIF, and PR review.
- Read-only external validation used `mastra-ai/mastra` commit `9fcb1db9`:
  21 canonical scopes, 10 cross-scope test-command overrides, and only two
  remaining true same-scope conflicts (`mastracode`, `packages/memory`).
  Target `git status` was identical before and after; only Phase 0 scan was run.
- The maintenance contract remains under strict D4 at 11,906 bytes, and the
  manual-protocol evidence pack was honestly refreshed to 22/22, Grade A.

## STOP conditions

- Correctness requires guessing scope from natural-language prose or file
  extensions.
- A supported config format has an explicit applicability model that
  contradicts the proposed canonical-ancestor assignment for the reproduction;
  stop and narrow that format rather than pretending one rule fits all tools.
- Existing root-only conflict reports or baselines cannot remain compatible
  without a breaking schema change.
- The change suppresses a demonstrated same-scope contradiction.
- Real-repo validation would require writing to the target checkout.
- Verification fails twice after a reasonable correction.

## Maintenance notes

Directory scope is a first-class diagnostic fact, not a semantic merge
decision. Future support for glob/frontmatter or prose-level file-type scopes
must be a separate evidence-backed feature. Reviewers should reject any patch
that makes nested overrides silently disappear: they are non-blocking, but must
remain visible and auditable.
