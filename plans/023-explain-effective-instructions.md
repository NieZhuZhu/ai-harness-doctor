# Plan 023: Explain the effective instruction chain for any repository path

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat ced1530..HEAD -- scripts/explain.py scripts/scan.py bin/cli.js bin/cli.test.js bin/mcp-server.js commands/harness-explain.md scripts/gen_adapters.py adapters/codex/harness-explain.md adapters/cursor/harness-explain.md adapters/gemini/harness/explain.toml tests/test_explain.py tests/test_cli.py tests/test_mcp_server.py tests/test_gen_adapters.py EXTERNAL_VALIDATION.md README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json benchmark/self-eval/results-after-graded.json benchmark/self-eval/README.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED
- **Depends on**: Plan 020 (already DONE; nested lexical scope model)
- **Category**: direction / dx / architecture / tests / docs
- **Planned at**: commit `ced1530`, 2026-07-15

## Why this matters

The scanner now models nested canonical scopes and parent→child overrides, but
users still receive a repository-wide report and must mentally answer the most
operational question: “For `packages/api/src/handler.ts`, which instructions
does an agent inherit, which nearest file wins, and which related configs or
conflicts should I inspect?” This is especially costly in the monorepos the
project now claims to support.

Add a read-only `explain REPO TARGET` capability that turns the existing scope
model into a focused, deterministic answer. Expose it consistently through the
npm CLI, MCP, Claude command, and generated Codex/Cursor/Gemini adapters. Keep
the answer honest: canonical `AGENTS.md` ancestry is known effective under the
nearest-file standard, while tool-specific config files are only
**diagnostically associated** with scopes unless their own applicability
language is modeled.

## Current state

- `scripts/scan.py:888-1001` already contains the deterministic scope engine:

  ```python
  def instruction_scope_map(files):
      """Return canonical scope rows plus each config file's effective scope."""
      ...
      return rows, file_scopes, parent_by_scope

  def analyze_scoped_conflicts(files):
      """Return ``(instruction_scopes, conflicts, non-blocking overrides)``."""
      ...
      return scope_rows, conflicts, overrides
  ```

  Canonical scope roots are parent directories of `AGENTS.md`/`AGENT.md`;
  component-safe ancestry chooses the deepest scope; same-scope differences are
  conflicts; parent→child differences are non-blocking overrides.

- `scan_repo()` at `scripts/scan.py:1451-1505` walks once through `ScanContext`,
  collects config files, then emits:

  ```python
  "conflicts": conflicts,
  "instruction_scopes": instruction_scopes,
  "scope_overrides": scope_overrides,
  "nested": nested_agents(result_files),
  ```

  No public helper currently returns the collected config entries plus their
  scope assignment for a target-path query.

- `bin/cli.js:24-42` has no `explain` usage, and `SCRIPT_COMMANDS` at
  `bin/cli.js:1181-1190` maps eight Python-backed commands but no scope query.
  Adding `explain: ['explain.py']` preserves the existing forwarding pattern and
  runtime self-test.

- `bin/mcp-server.js:37-132` advertises six read-only tools. Tool dispatch
  assumes every script receives one positional `repo` followed by boolean
  flags:

  ```javascript
  return { scriptPath, argv: [scriptPath, ...leading, repo, ...flags] };
  ```

  `harness_explain` needs a required second positional target, so positional
  argument order and required-property validation must become declarative
  without changing the six existing tools' argv.

- `scripts/gen_adapters.py:30-66` is the single source for the five generated
  agent command adapters. `bin/cli.js` separately installs the matching Claude
  commands listed by `COMMAND_NAMES`. An explain surface must update these
  sources, generate all three adapter flavors, and add
  `commands/harness-explain.md`; do not hand-maintain generated adapters.

- The README/SKILL contracts explicitly say the scope engine does **not** infer
  file-type, glob/frontmatter, external-repository, or prose applicability.
  Explain must preserve this evidence boundary rather than labeling every
  nearby Cursor/Copilot/Claude file “effective.”

## Target contract

Public CLI:

```text
ai-harness-doctor explain <repo-root> <target-path> [--json]
```

The target may name an existing file/directory or a future path that does not
yet exist. It must resolve lexically inside the repository; absolute paths are
accepted only when contained. Existing symlink components that escape the root
are rejected. The command never creates the target.

JSON schema (additive version 1):

```json
{
  "schema_version": 1,
  "repo": ".",
  "target": {
    "path": "packages/api/src/handler.ts",
    "exists": true,
    "kind": "file",
    "excluded_by_scan": false
  },
  "effective_scope": "packages/api",
  "canonical_chain": [
    {"path": "AGENTS.md", "scope": ".", "parent": null},
    {
      "path": "packages/api/AGENTS.md",
      "scope": "packages/api",
      "parent": "."
    }
  ],
  "diagnostic_sources": [
    {"path": "AGENTS.md", "tool": "AGENTS.md", "scope": "."}
  ],
  "scope_overrides": [],
  "conflicts": [],
  "limitations": [
    "Tool-specific configs are diagnostically associated, not claimed effective."
  ]
}
```

Exact field names may be tightened before implementation, but the following
semantics are mandatory:

1. `canonical_chain` is ordered root→nearest and contains only canonical files
   whose scope is an ancestor of the target. Under the AGENTS.md standard these
   are the known instruction inheritance chain.
2. `effective_scope` is the deepest canonical ancestor, or `"."` when no nested
   canonical file applies. If no root canonical file exists, the chain may be
   empty; do not invent one.
3. `diagnostic_sources` lists every recognized config assigned by Plan 020's
   lexical model to a scope on the canonical chain. It must use wording that
   does not claim Cursor/Copilot/Claude frontmatter or glob applicability.
4. `scope_overrides` includes only existing scan override records on the target
   chain. `conflicts` includes true same-scope conflicts on that chain, with
   root scope normalized explicitly to `"."` in explain output.
5. The command derives all scope/conflict/override data from the same scan
   helpers. It does not duplicate signal extraction, path-component ancestry,
   or registry lists.
6. Ordering is deterministic. No absolute host paths or file contents appear in
   JSON/Markdown.
7. A target below `scan.SKIP_DIRS` is explicitly marked
   `excluded_by_scan: true`; canonical ancestry may still be shown, but the
   report must warn that nested configs inside the excluded subtree are not
   inventoried.
8. Markdown presents: target summary, canonical chain, diagnostic sources,
   relevant overrides/conflicts, and limitations. `--json` prints only the JSON
   object.
9. The capability is read-only in CLI and MCP. It executes no plugins by
   default and exposes no `--allow-plugins` option in this plan.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Explain tests | `python3 -m unittest discover -s tests -p 'test_explain.py' -v` | all pass |
| CLI tests | `python3 -m unittest discover -s tests -p 'test_cli.py' -v` | all pass |
| Node unit tests | `node --test bin/*.test.js` | all pass |
| MCP tests | `python3 -m unittest discover -s tests -p 'test_mcp_server.py' -v` | all pass |
| Adapter tests | `python3 -m unittest discover -s tests -p 'test_gen_adapters.py' -v` | all pass |
| Adapter gate | `python3 scripts/gen_adapters.py --check` | all generated adapters match |
| Python lint | `ruff check scripts/explain.py scripts/scan.py tests` | exit 0 |
| JavaScript lint | `eslint bin` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | `OK` |
| Full gate | `npm run check` | exit 0 |
| Evidence gate | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0 |
| Self scan | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0; grade A |

## Scope

**In scope**:

- new `scripts/explain.py`
- a small extraction/helper in `scripts/scan.py` so scan and explain share one
  config inventory + scope model
- new `tests/test_explain.py` and matching CLI/MCP/adapter tests
- `bin/cli.js`, `bin/cli.test.js`
- `bin/mcp-server.js`, `tests/test_mcp_server.py`
- `commands/harness-explain.md`
- `scripts/gen_adapters.py` plus generated explain adapters under
  `adapters/{codex,cursor,gemini}/`
- synchronized `README.md`, `README.zh-CN.md`, `README.ja.md`
- `SKILL.md`
- one real target-path validation in `EXTERNAL_VALIDATION.md`
- compact maintenance/API invariants in `AGENTS.md`
- evidence-bound `benchmark/self-eval/` refresh after `AGENTS.md` changes
- `plans/README.md`

**Out of scope**:

- Parsing Cursor/Copilot frontmatter, globs, file extensions, ignore files, or
  natural-language applicability.
- Claiming recognized tool configs are semantically effective.
- Returning merged instruction text or choosing a winning natural-language
  instruction.
- Editing, consolidating, or generating any target repository file.
- Executing custom plugins or exposing a write-capable MCP tool.
- Scope-aware Phase 3 eval task generation. It is a separate follow-up once the
  target-path vocabulary and schema are validated.
- A general Ruler/rulesync-style config generator.
- Multi-repository `--repos-file` explain queries.
- Changing Phase 0 report schema, conflict exit code, or baseline identity.
- Adding a runtime dependency.

## Git workflow

- Branch: `feat/explain-instruction-scope`
- Commit: `feat(explain): show effective instruction chains`
- One backward-compatible feature PR.
- Do not push directly to `main`. Open an English PR, wait for all nine
  required contexts, then squash-merge and delete the branch.
- This adds public CLI/MCP/adapter surfaces and is minor-level.

## Steps

### Step 1: Characterize target-path scope answers before adding a CLI

Create `tests/test_explain.py` with temporary repositories covering:

1. root-only `AGENTS.md` → chain contains root, effective scope `"."`;
2. root + `packages/api/AGENTS.md` → target inside `packages/api/src` gets both
   root and package canonical rows in root→nearest order;
3. target in sibling package → nested API scope is absent;
4. root→package→subdir canonical chain chooses the deepest scope;
5. nonexistent future target inside a valid scope is accepted with
   `exists: false`;
6. relative and contained absolute target normalize to the same repository
   path;
7. `../` escape and an external-symlink component fail with a concise error and
   no host absolute path disclosure;
8. target under `node_modules`/another `SKIP_DIRS` entry is marked excluded;
9. missing root canonical file yields an empty canonical chain, not a
   fabricated root file.

Initially call the planned pure builder API, not a subprocess, so the desired
domain contract is fixed before rendering/dispatch.

**Verify**: tests fail because `scripts/explain.py`/the builder do not exist;
the fixtures themselves make no writes after setup.

### Step 2: Extract one shared instruction-config inventory seam

Refactor the first part of `scan.scan_repo()` into a small public helper, for
example:

```python
def collect_instruction_files(root, max_bytes=32768, ctx=None):
    """Return (internal_files_with_text, public_files, warnings, ctx)."""
```

Requirements:

- exactly one `ScanContext` walk per command;
- same `iter_matches`, `file_info`, registry order, size/truncation behavior,
  skip directories, and containment contract as current scan;
- `scan_repo()` consumes the helper without changing its JSON/Markdown output;
- explain receives the internal path/text metadata needed by
  `instruction_scope_map()` / `analyze_scoped_conflicts()` but never emits file
  contents;
- no private reimplementation of `CONFIG_PATTERNS`.

Add a scan regression asserting a representative `scan --json` payload is
unchanged by extraction.

**Verify**: existing `tests/test_scan.py` plus explain inventory tests pass; a
walk-count test proves explain performs one inventory walk.

### Step 3: Implement the deterministic explain builder and renderers

In new stdlib-only `scripts/explain.py`:

- parse/normalize the repo and target with the containment contract;
- build the config inventory once through the shared scan helper;
- call `scan.instruction_scope_map()` and
  `scan.analyze_scoped_conflicts()` rather than recreating ancestry/signals;
- calculate target scope using component tuples, not string prefixes
  (`packages/a` must not match `packages/ab`);
- filter canonical rows, diagnostic sources, overrides, and conflicts to scopes
  on the target chain;
- normalize root conflict scope to `"."` in explain only;
- sort every list deterministically;
- emit schema version 1 and the explicit limitation text;
- render concise Markdown from that same object.

Add argparse:

```text
python3 scripts/explain.py REPO TARGET [--json]
```

Invalid repo/target returns exit 1 and a concise stderr error; a valid report
returns 0 even when it contains related conflicts because explain is a query,
not a gate.

Do not include raw instruction text/evidence lines beyond the already-safe
conflict evidence objects the scan contract exposes. If those objects contain
more source prose than necessary for explain, project them down to
path/line/value rather than broadening data exposure.

**Verify**: builder + subprocess tests cover all nine cases and deterministic
repeat output.

### Step 4: Add the npm CLI and installed agent commands

Update `bin/cli.js`:

- add `ai-harness-doctor explain <repo> <target> [--json]` to usage/examples;
- add `explain: ['explain.py']` to `SCRIPT_COMMANDS`;
- add `harness-explain` to `COMMAND_NAMES` so install/update/uninstall ownership
  covers the Claude command.

Create `commands/harness-explain.md` following the exact discovery/safety style
of `commands/harness-scan.md`, with argument hint `[repo-path] [target-path]`.
It must instruct the agent to run the deterministic explain capability and
stop after presenting the chain; it must not ask the agent to merge or rewrite
instructions.

Add an `explain` entry to `scripts/gen_adapters.py`, regenerate all three
flavors, and update adapter-count expectations. Do not hand-edit generated
files.

Tests:

- `SCRIPT_COMMANDS` exact key set includes explain;
- help lists the syntax;
- real CLI `explain` JSON smoke test returns the expected nested chain;
- isolated-HOME install/update/uninstall owns and removes
  `harness-explain.md` without touching user files;
- generated adapters pass `--check`.

**Verify**: CLI, Node, and adapter commands in the table pass.

### Step 5: Add a seventh read-only MCP tool without special-case argv logic

Generalize `bin/mcp-server.js` tool metadata:

- add a declarative ordered positional list (existing tools default to
  `["repo"]`; explain uses `["repo", "target"]`);
- teach `validateToolArguments()` to enforce schema `required` properties;
- keep each existing tool's argv byte-equivalent;
- add `harness_explain` with required string `target`, optional boolean `json`,
  read-only annotations, closed input/output schemas, a 60-second bounded
  subprocess, and no plugin/write flags;
- add JSON shape validation for schema-version-1 explain reports;
- classify a valid explain report as `status: "ok"`, not a finding/error gate.

Do not add an explain-only branch to `buildScriptArgs`; the declarative
positional contract is the maintainable seam.

Update MCP tests:

- tools/list advertises seven tools with modern/legacy shapes;
- all seven reject nonexistent repos before spawn;
- missing required `target`, wrong type, and unknown properties return
  `INVALID_PARAMS`;
- a nested target returns the same JSON chain as the CLI;
- text mode returns Markdown;
- timeout/error sanitization and pre-initialize legacy behavior remain intact;
- all six old tools still build the same argv and return the same statuses.

**Verify**: MCP tests pass under both negotiated protocols.

### Step 6: Validate on a real monorepo and refine only the presentation

Use a disposable current checkout of `mastra-ai/mastra` (preferred because Plan
020 recorded 21 scopes) or another public monorepo with at least three nested
canonical files. Choose:

- one target under a nested canonical scope;
- one sibling target;
- one future/nonexistent target path.

Run both Markdown and JSON through the development CLI. Verify the canonical
chain directly from directory ancestry and compare relevant
overrides/conflicts with `scan --json`. Confirm the target worktree stays
clean. If output is confusing, refine labels/order only within the target
contract; do not add prose/glob inference.

Append an `EXTERNAL_VALIDATION.md` row/detail with repo commit, three target
shapes, scope-chain result, scan parity, and the read-only evidence boundary.

**Verify**: repeat JSON is byte-identical; scan/explain scope records agree;
target status is unchanged.

### Step 7: Document the public capability and maintenance contract

Update all three READMEs and `SKILL.md` with synchronized structure:

- one quick-start example;
- CLI reference and JSON field definitions;
- honest distinction between canonical effective chain and diagnostically
  associated tool configs;
- skipped-subtree/nonexistent-target behavior;
- MCP tool list/count/booleans/required target;
- installed Claude/Codex/Cursor/Gemini command availability;
- no merging, writes, plugin execution, or glob/prose inference.

Update repository tree comments that currently list six MCP tools or five
commands. Keep all fenced code byte-identical across languages.

In `AGENTS.md`, compactly record:

- explain must reuse the scan scope model and one contained inventory;
- canonical chain vs diagnostic-source wording is a public trust boundary;
- CLI/MCP/adapter schemas and counts move together.

Keep `AGENTS.md` below the strict D4 threshold. Refresh/regrade its committed
self-eval evidence honestly; do not claim a model run.

**Verify**: docs sync, adapter gate, evidence gate, self scan, and strict drift
pass.

### Step 8: Run the full gate and merge

Run every command in the table. Open an English PR describing:

- the target-path user problem and schema;
- shared scope-engine implementation;
- containment/read-only guarantees;
- canonical-vs-diagnostic evidence boundary;
- CLI/MCP/adapter parity;
- real monorepo validation;
- minor release classification.

Wait for `drift`, `lint`, Node 16/20/22, `self-test`, and Python
3.9/3.10/3.12 to all succeed. Admin bypass may resolve only the sole-maintainer
self-review deadlock; it must not bypass a red or pending check.

**Verify**: all nine required contexts are green before squash merge; branch is
deleted; `main` contains the squash commit.

## Test plan

- Root, nested, deep, sibling, missing-root, nonexistent-target, absolute,
  escape, external-symlink, and skipped-subtree path cases.
- Component-safe ancestry for similarly prefixed directories.
- Relevant override/conflict filtering and deterministic root-scope
  normalization.
- Diagnostic source output never labels tool-specific configs effective.
- No absolute host paths or instruction contents leak.
- Scan payload stays compatible after inventory extraction.
- CLI help/forwarding/JSON/text and isolated-HOME command ownership.
- Generated Codex/Cursor/Gemini adapters stay single-sourced.
- Seven-tool MCP modern/legacy schemas, required target validation, argv,
  timeout, and error semantics.
- Real monorepo chain agrees with scan output and leaves target clean.

## Done criteria

- [ ] `ai-harness-doctor explain REPO TARGET` returns a deterministic focused
  Markdown report; `--json` returns schema version 1.
- [ ] Canonical chain/effective scope agree with Plan 020's nearest-file model.
- [ ] Tool-specific configs are labeled diagnostic, never falsely effective.
- [ ] Existing/future contained paths work; escapes and external symlinks fail
  safely; skipped subtrees are explicit.
- [ ] Explain and scan share one inventory/scope implementation and scan output
  stays backward-compatible.
- [ ] CLI, seventh MCP tool, Claude command, and generated adapters are
  synchronized and read-only.
- [ ] Real monorepo validation is logged with scan parity and a clean target.
- [ ] Trilingual docs, `SKILL.md`, and `AGENTS.md` record the public contract.
- [ ] Every command in the command table passes.
- [ ] All nine required PR checks are green before squash merge.

## STOP conditions

Stop and report back (do not improvise) if:

- Any in-scope scope-engine excerpt changed semantically since `ced1530`.
- A useful answer requires claiming tool-specific frontmatter/glob semantics or
  parsing natural-language applicability.
- Scan and explain would need separate conflict extraction or ancestry logic.
- The inventory extraction changes existing scan JSON/Markdown or walk count.
- Target containment cannot be enforced without rejecting ordinary contained
  paths or exposing absolute host paths.
- Adding explain requires a write-capable MCP surface or plugin execution.
- MCP support would require breaking the six existing tools' input or result
  schemas.
- A runtime dependency or Python newer than 3.9 is required.
- A step's verification fails twice after a reasonable focused fix.

## Maintenance notes

- `scripts/scan.py` owns scope truth. `explain.py` is a projection over that
  model, not a second scope engine.
- Preserve the semantic distinction: “canonical chain” is standards-backed;
  “diagnostic sources” is a doctor association. Changing that wording requires
  evidence and tests.
- The JSON schema is now public through CLI and MCP. Add fields rather than
  renaming/removing them in a patch/minor release.
- Scope-aware eval generation is the most valuable follow-up after real users
  validate explain output. It should consume this vocabulary rather than
  independently rediscover package scopes.
