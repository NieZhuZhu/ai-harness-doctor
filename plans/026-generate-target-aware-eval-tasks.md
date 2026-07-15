# Plan 026: Generate efficacy tasks for one explicit instruction scope

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 935eeb6..HEAD -- scripts/eval_run.py scripts/explain.py scripts/scan.py bin/mcp-server.js tests/test_eval_run.py tests/test_explain.py tests/test_mcp_server.py tests/test_cli.py EXTERNAL_VALIDATION.md README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json benchmark/self-eval/results-after-graded.json benchmark/self-eval/README.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED
- **Depends on**: Plan 023 (already DONE; public target/scope vocabulary)
- **Category**: direction / efficacy / dx / architecture / tests / docs
- **Planned at**: commit `935eeb6`, 2026-07-15

## Why this matters

The product now diagnoses and explains nearest-file instruction scopes, but
its zero-config efficacy generator still evaluates only repository-root facts.
In a monorepo, a package can have its own `AGENTS.md`, package manager,
commands, runtime, and test framework while `eval --generate` emits only the
root task set. A high root score can therefore say nothing about whether the
instructions nearest to actual package work are effective.

The audit reproduced this with a root npm project and
`packages/api/AGENTS.md` plus a pnpm/Vitest package: `generate_tasks(root)`
returned only the root `test` task and no package-local command, pnpm, or
framework task, while `explain` correctly identified `packages/api` as the
target's effective scope. Add an explicit `--target` projection over that
validated vocabulary. Do not expand every scope by default: one deliberate
target keeps task count, evidence, and cost reviewable on large monorepos.

## Current state

- `scripts/eval_run.py:365-479` takes only a repository root:

  ```python
  def generate_tasks(repo_root):
      root = Path(repo_root).resolve()
      ...
      pkg = _load_json_file(root / "package.json")
      pm = detect_package_manager(root)
      ...
      agents = root / "AGENTS.md"
      agents_text = agents.read_text(...) if agents.is_file() else ""
      ...
      return tasks
  ```

  Every package script, lockfile, `.nvmrc`, `go.mod`, `pyproject.toml`,
  dependency, component directory, and instruction-derived convention is read
  only from `root`.

- `scripts/eval_run.py:482-493` passes `args.generate` directly to that helper
  and writes a JSON array. `scripts/eval_run.py:1664-1668` exposes only:

  ```python
  parser.add_argument(
      "--generate",
      metavar="REPO",
      help="Auto-generate a tasks.json from repository facts ...",
  )
  ```

- `tests/test_eval_run.py:1280-1371` covers root Node/Go/Python facts and the
  root CLI. There is no target containment, scope selection, inherited fact,
  task-ID collision, or source-evidence test.

- `scripts/explain.py:21-158` already owns the public target-path vocabulary:
  - `normalize_target()` accepts contained existing/future paths and rejects
    lexical/symlink escape;
  - `build_explanation()` reuses the scanner's canonical scope model and
    returns `target`, `effective_scope`, and ordered `canonical_chain`;
  - targets under `SKIP_DIRS` are explicitly marked `excluded_by_scan`.

  Eval generation must reuse or extract this context; it must not fork path
  normalization or nearest-scope ancestry.

- `bin/mcp-server.js:118-131` advertises `harness_eval_generate` with only
  `repo`. `buildScriptArgs()` at `bin/mcp-server.js:237-255` supports
  declarative positionals and booleans. `harness_explain` already demonstrates
  a required target, but eval's target is an optional `--target` flag after
  `--generate REPO`, not a second positional.

- The public READMEs describe zero-config generation as repository facts and
  MCP as a seven-tool read-only surface. Any target extension must keep the
  three translations' fenced commands, table shape, links, and headings
  synchronized.

## Target contract

Public CLI:

```text
ai-harness-doctor eval --generate <repo-root> [--target <path>] [-o tasks.json]
```

1. Omitting `--target` preserves the current root task IDs, prompts, order,
   regexes, output array shape, and behavior byte-for-byte wherever practical.
2. `--target` accepts the same contained existing file/directory or future path
   as `explain`. Escape through `..` or an existing external symlink fails with
   a concise error. A target under an excluded scan directory fails rather than
   pretending its un-inventoried nested instructions are covered.
3. The target's `effective_scope` comes from the shared explain/scan nearest
   canonical-file model. Its scope directory is the local fact root. A target
   with no nested effective scope remains root generation; do not infer an
   instruction scope merely from a package manifest.
4. Fact inheritance is explicit and conservative:
   - package scripts, dependencies/frameworks, `go.mod`, `pyproject.toml`, and
     component directories come only from the effective scope directory;
   - package manager and runtime version may use the nearest unambiguous source
     from the scope directory toward repository root, so a workspace-level
     lockfile/engine can govern a package;
   - instruction-derived conventions inspect the ordered canonical chain
     root→nearest;
   - root package scripts/dependencies are never mislabeled as package-local
     tasks.
5. Scoped prompts name the logical scope/target so the question is not
   mistaken for repository-root guidance. Expected commands remain
   scope-relative (for example `pnpm test:api` while working in
   `packages/api`); do not invent `cd`, workspace-filter, or `--dir` syntax not
   established by repository facts.
6. Every scoped task ID is deterministic, collision-safe, and reversible:
   prefix the existing base ID with the percent-encoded POSIX scope (for
   example `scope:packages%2Fapi:test`). Root generation retains legacy IDs.
7. Scoped task records add safe provenance:

   ```json
   {
     "id": "scope:packages%2Fapi:test",
     "scope": "packages/api",
     "target": "packages/api/src/future.py",
     "evidence": ["packages/api/package.json"],
     "prompt": "...",
     "timeout_s": 120,
     "check": {"type": "regex", "value": "..."}
   }
   ```

   `evidence` contains deterministic repository-relative source paths only,
   never file contents or host absolute paths. Each task lists only the files
   that establish its expected answer.
8. `harness_eval_generate` adds optional string `target` to its closed MCP
   input schema and dispatches it as `--target <value>`. Existing calls without
   it retain their argv/results. The tool remains read-only, prints tasks to
   stdout, and never runs an agent/LLM.
9. Do not add default all-scope expansion. `--all-scopes`, workspace task
   matrices, and automatic eval execution remain deferred until external
   validation demonstrates bounded task volume and useful signal.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Eval tests | `python3 -m unittest discover -s tests -p 'test_eval_run.py' -v` | all pass |
| Explain tests | `python3 -m unittest discover -s tests -p 'test_explain.py' -v` | all pass |
| MCP tests | `python3 -m unittest discover -s tests -p 'test_mcp_server.py' -v` | all pass |
| CLI tests | `python3 -m unittest discover -s tests -p 'test_cli.py' -v` | all pass |
| Node tests | `node --test bin/*.test.js` | all pass |
| Python lint | `ruff check scripts/eval_run.py scripts/explain.py scripts/scan.py tests` | exit 0 |
| JavaScript lint | `eslint bin` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | `OK` |
| Full gate | `npm run check` | exit 0 |
| Evidence gate | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0 |
| Self scan | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0; grade A |

## Scope

**In scope**:

- `scripts/eval_run.py`
- `scripts/explain.py` and `scripts/scan.py` only for a small shared target
  context/helper extraction
- `bin/mcp-server.js`
- matching tests in `tests/test_eval_run.py`, `tests/test_explain.py`,
  `tests/test_mcp_server.py`, and `tests/test_cli.py`
- synchronized `README.md`, `README.zh-CN.md`, `README.ja.md`
- `SKILL.md`
- explicit root-vs-target validation on a real public monorepo in
  `EXTERNAL_VALIDATION.md`
- a compact scoped-eval maintenance/API invariant in `AGENTS.md`
- evidence-bound `benchmark/self-eval/` refresh after `AGENTS.md` changes
- `plans/README.md`

**Out of scope**:

- Default or automatic generation for every nested scope.
- A new package/workspace discovery engine independent of canonical
  instruction scopes.
- Evaluating a package that has no nested canonical instruction scope merely
  because it has `package.json`.
- Running generated tasks, agents, matrices, or LLM-as-judge from MCP.
- Automatically adding generated task evidence to later eval result manifests;
  this plan records task provenance but does not change the explicit
  `--evidence` result-binding contract.
- Inferring shell `cd`, package-manager filters, Turbo/Nx selectors, or commands
  not directly established by facts.
- Merging instruction text or adjudicating conflicts/overrides.
- Parsing Cursor/Copilot frontmatter, globs, or tool-specific applicability.
- Changing the root zero-config task contract or existing result schemas.
- Adding a runtime dependency.

## Git workflow

- Branch: `feat/target-aware-eval-generation`
- Commit: `feat(eval): generate tasks for instruction scopes`
- One backward-compatible feature PR with CLI/MCP parity, tests, and
  synchronized public docs.
- Do not push directly to `main`. Open an English PR, wait for all nine
  required contexts, then squash-merge and delete the branch.
- This adds a public CLI/MCP capability and is minor-level. The combined batch
  must therefore publish a minor version unless another plan becomes breaking.

## Steps

### Step 1: Add failing target-scope characterizations

Extend `GenerateTasksTests` with a synthetic repository:

- root `AGENTS.md`, npm lock/package, root `test` script, and root-only
  framework;
- `packages/api/AGENTS.md`;
- `packages/api/package.json` with a different local test script, lint script,
  and Vitest dependency;
- a package-local or inherited package-manager fact;
- a target such as `packages/api/src/future.py`.

Assert:

1. legacy `generate_tasks(root)` still returns root IDs/facts only;
2. target generation returns package-local script/framework tasks and excludes
   root scripts/frameworks;
3. effective scope and target fields are repository-relative;
4. IDs include an encoded scope and cannot collide with root/sibling IDs;
5. evidence paths name the exact package/ancestor sources;
6. root instruction conventions are inherited through the canonical chain;
7. sibling-package facts do not bleed into API tasks;
8. future targets are accepted, while lexical/symlink escape and excluded
   targets fail.

Add CLI tests for `--generate REPO --target PATH` to stdout and `-o`, and for
rejecting `--target` without `--generate`.

**Verify**: scoped generation assertions fail against `935eeb6`; all root
generation tests remain green.

### Step 2: Extract one shared target context from explain

Refactor `scripts/explain.py` only enough to expose a pure/read-only target
context used by both explanation and eval generation, for example:

```python
{
    "target": {...},
    "effective_scope": "packages/api",
    "canonical_chain": [...],
}
```

Requirements:

- one `ScanContext` inventory per invocation;
- identical containment, future-path, skip, scope, and canonical-chain
  semantics for explain and eval;
- no raw instruction text in the public context;
- no import cycle among `scan`, `explain`, and `eval_run`;
- existing explain schema/Markdown remains unchanged.

If importing `explain` into `eval_run.py` creates a cycle, move only the shared
target normalization/context builder to a narrowly named stdlib module and
have both callers use it. Do not duplicate the logic.

**Verify**: explain regressions remain green; a paired test proves explain and
eval select the same effective scope and canonical chain for identical targets.

### Step 3: Refactor fact generation around an explicit scope

Split `generate_tasks()` into:

- a compatibility wrapper for root generation;
- a fact-source resolver with repository root, fact root, canonical chain, and
  optional target metadata;
- the existing deterministic task builders.

Implement the inheritance matrix from the Target contract. Each detected fact
must carry its repository-relative source path before it becomes a task. Use
contained reads and existing `semantic` ground-truth helpers; do not read an
ancestor or sibling merely because a local fact is missing unless the
contract explicitly permits nearest-ancestor package-manager/runtime facts.

For scoped tasks:

- percent-encode the scope with Python standard library (`urllib.parse.quote`
  with no path separator left safe);
- add scope/target/evidence;
- qualify the prompt with the logical scope;
- retain the current regex/check and timeout semantics.

For root tasks, prove output compatibility with an exact expected array or
stable golden serialization.

**Verify**: root and scoped fact tests pass across Node, Python, Go, runtime,
instruction convention, sibling isolation, and ambiguous-source abstention.

### Step 4: Expose target generation through CLI and MCP

Add `--target PATH` to `eval_run.py` and validate it is used only with
`--generate`. Convert `ValueError` from target normalization/fact resolution
to concise stderr plus non-zero exit without absolute-path or traceback
leakage.

In `bin/mcp-server.js`, generalize tool argument construction with a
declarative optional string-flag mapping, for example:

```javascript
strings: { target: '--target' }
```

Add optional `target` to `harness_eval_generate`'s closed schema. Preserve:

- `harness_explain`'s positional target ordering;
- all six other tools' exact argv;
- validation before Python spawn;
- read-only annotations and modern/legacy result envelopes.

Tests must inspect the generated argv and execute a real MCP target-generation
call against the synthetic monorepo.

**Verify**: MCP schema/argv/result tests and all Node tests pass; unknown/wrong
target types remain invalid params.

### Step 5: Document and externally validate bounded scoped efficacy

Update all three READMEs and `SKILL.md` with:

- root-compatible and explicit target command examples;
- exact scope/fact-inheritance semantics;
- task ID/evidence fields;
- MCP optional target;
- the deliberate absence of automatic all-scope expansion.

Keep byte-identical fenced code blocks (including inline comments), table
rows/links, and heading skeleton across translations.

Run root and at least two explicit nested targets read-only on a real public
monorepo with nested canonical instructions. Record:

- repo/commit/date and why targets were chosen;
- root vs target task counts/IDs;
- selected effective scopes and evidence paths;
- confirmation that sibling/root-only facts did not bleed;
- no agent/LLM execution or cost;
- fixing PR.

Add a compact invariant to `AGENTS.md`, refresh evidence-bound self-eval
artifacts, and mark Plan 026 DONE only after merge.

**Verify**: docs sync, full gate, evidence gate, self scan, and strict drift all
pass; `AGENTS.md` remains below the context-bloat threshold.

## Test plan

- Extend existing `GenerateTasksTests`; do not mutate checked-in fixtures.
- Cover root compatibility, root target, nested target, future target, sibling
  target, three-level canonical chain, inherited manager/runtime, local
  override, ambiguous source abstention, excluded path, `..`, and external
  symlink.
- Use two scopes with punctuation/path separators to prove ID encoding is
  collision-safe and deterministic.
- Assert evidence is sorted, relative, contained, minimal, and contains no file
  content.
- Exercise CLI stdout/output-file modes and MCP modern/legacy envelopes.
- Keep all tests read-only after temporary repository setup.

## Done criteria

- [ ] Root generation remains backward-compatible.
- [ ] `eval --generate REPO --target PATH` generates only the effective
      instruction scope's local/inherited facts under the documented matrix.
- [ ] Scoped IDs are collision-safe and every scoped task has safe fact-source
      evidence.
- [ ] Eval and explain agree on target normalization, effective scope, and
      canonical chain.
- [ ] MCP supports optional target without changing existing tool argv/results.
- [ ] No default all-scope expansion or agent/LLM execution is introduced.
- [ ] Real monorepo root/nested validation is recorded.
- [ ] Three READMEs, `SKILL.md`, compact `AGENTS.md`, and self-eval evidence are
      current.
- [ ] `npm run check`, evidence gate, self scan, and strict drift all pass.
- [ ] Plan 026 and its index row are marked DONE after squash merge.

## STOP conditions

Stop and report back (do not improvise) if:

- Plan 023's target/scope schema or helpers no longer match the current-state
  excerpts.
- Sharing target context requires duplicating nearest-scope or containment
  semantics.
- A package's expected command requires guessing a workspace selector,
  execution directory, or inherited fact not established by the contract.
- Root generation cannot remain backward-compatible without a public breaking
  task schema change.
- Target generation creates an import cycle that cannot be resolved with one
  small shared stdlib helper.
- Real validation shows explicit target task sets are still dominated by
  unrelated root/sibling facts.
- Implementing MCP target support would expose writes or run an agent/LLM.
- A verification command fails twice after a reasonable scoped fix.

## Maintenance notes

- `explain` is the source of truth for target vocabulary and canonical scope
  ancestry. Future target-aware features should consume that context rather
  than create another path model.
- Keep the fact inheritance matrix explicit. In particular, root scripts are
  not package-local just because the package lives in a workspace.
- Preserve legacy root IDs. Scoped IDs may be consumed by baselines and result
  comparisons once published, so their encoding becomes a compatibility
  contract.
- `evidence` identifies expected-answer sources but does not replace the
  existing explicit eval result evidence manifest. A future integration must
  design that binding deliberately.
- Consider `--all-scopes` only after measured public-monorepo task volume,
  usefulness, and cost justify it.
