# Plan 027: Confine every fact-derived generator to repository truth

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 150d1c9..HEAD -- scripts/facts.py scripts/eval_run.py scripts/canonicalize.py scripts/semantic.py tests/test_eval_run.py tests/test_canonicalize.py tests/test_registry_consistency.py tests/test_cli.py README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json benchmark/self-eval/results-after-graded.json benchmark/self-eval/README.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: security / correctness / architecture / tests / docs
- **Planned at**: commit `150d1c9`, 2026-07-16

## Why this matters

The scan, semantic, drift, scoped eval, and mutation paths now reject
repository-derived facts that resolve outside the audited repository. Two
fact-generating surfaces still bypass that contract: legacy/root
`eval --generate` directly reads root manifests and instructions, while
`canonicalize --draft` directly probes and reads several Node/Python/CLAUDE
sources.

An audited repository can therefore expose a lexical `package.json`, `.nvmrc`,
`AGENTS.md`, or `CLAUDE.md` symlink whose target is outside the repository and
make the doctor emit expected answers or draft commands from external content.
This is both a security-boundary regression and cross-engine diagnostic
inconsistency: adding `--target` to the same eval command switches it to the
safe contained path, and scan/drift disagree with the unsafe root result.

## Current state

- `scripts/facts.py:147-207` already defines the repository-wide read contract:

  ```python
  def resolve_within_root(path, root, strict=True):
      ...
      candidate.relative_to(resolved_root)
      return candidate

  def is_file_within_root(root, path):
      candidate = resolve_within_root(path, root)
      return candidate is not None and candidate.is_file()

  def read_text_within_root(root, path, errors="strict"):
      candidate = resolve_within_root(path, root)
      ...
  ```

  In-repository symlinks remain supported; external symlinks return no fact.

- Scoped eval follows that contract through `_load_contained_json()` and
  `facts.is_file_within_root()`, but root eval does not:

  ```python
  # scripts/eval_run.py:346-371
  def _load_json_file(path):
      return json.loads(Path(path).read_text(encoding="utf-8"))

  def detect_package_manager(root):
      for fname, pm in PKG_MANAGER_LOCKFILES:
          if (root / fname).is_file():
              return pm
      pkg = _load_json_file(root / "package.json")
      ...
  ```

  Root Node and convention tasks also use direct `.is_file()` /
  `.read_text()` at `scripts/eval_run.py:593-604` and `:671-674`.

- The audit created a repository whose `package.json`, `.nvmrc`, and
  `AGENTS.md` were file symlinks to sibling files outside the root. At
  `150d1c9`, valid `eval --generate REPO` exited 0 and emitted four tasks whose
  expected answers came solely from those external files:

  ```text
  package-manager = yarn
  install = yarn install
  node-version = 99
  commit-convention = conventional
  ```

  No target-path escape is needed; the unsafe files use normal lexical names at
  the repository root.

- Root package-manager generation also chooses the first lockfile in
  `PKG_MANAGER_LOCKFILES`. A synthetic repo containing both
  `pnpm-lock.yaml` and `package-lock.json` produced `pnpm` install/test tasks.
  `facts.lockfile_managers()` and drift D8 intentionally classify that state as
  ambiguous instead of selecting one side.

- `canonicalize.py` imports `facts`, but several draft helpers bypass it:

  ```python
  # scripts/canonicalize.py:384-409
  path = root / "CLAUDE.md"
  if not path.is_file():
      return []
  text = path.read_text(encoding="utf-8", errors="replace")

  # scripts/canonicalize.py:361-380
  if (root / "tests").is_dir() ...
  if pyproject.is_file() and "pytest" in pyproject.read_text(...):
      ...
  ```

  `_lockfile_backed_manager()` and `_detected_package_manager()` similarly use
  direct `.is_file()` checks.

- A contained repo with `uv.lock` and an external `CLAUDE.md` symlink
  containing one Python command produced this draft line:

  ```text
  uv run pytest external-only  # (inferred — confirm) documented in CLAUDE.md
  ```

  The source command is outside the audited repository. A separate external
  `pyproject.toml` symlink also made `_has_pytest()` return true even though the
  safe semantic package-manager reader correctly ignored the same file.

- Existing tests cover external symlinks for scan, semantic, drift, stubs,
  validation, installer state, explicit eval result evidence, and target-path
  eval. They do not cover root generation or draft fact inference.

## Target contract

1. Every repository-derived fact used by `eval --generate` (root or targeted)
   and `canonicalize --draft` must be discovered/read through `scripts/facts.py`
   or an existing safe semantic helper.
2. External symlink targets, lexical escapes, unreadable files, and malformed
   manifests contribute no facts and never leak host absolute paths or file
   contents into stdout/stderr.
3. Safe in-repository file/directory symlinks keep existing read compatibility
   and lexical repository-relative evidence paths.
4. Root and targeted eval use one package-manager policy:
   - exactly one contained lockfile-backed manager wins;
   - when no lockfile exists, one contained valid `packageManager` field may be
     used;
   - two or more manager values are ambiguous, so package-manager/install and
     package-script command tasks abstain rather than guessing;
   - framework/formatter facts that do not need a command runner may remain.
5. Root task IDs, prompts, ordering, regexes, and output shape remain unchanged
   for safe, unambiguous repositories.
6. Draft inference uses the same contained package scripts, lockfiles,
   Makefiles, Python metadata, tool configs, CI inventory, and instruction
   sources as scan/semantic. A skipped external fact should yield a TODO or
   fewer inferred lines, never a blocking crash.
7. Do not weaken the mutation contract, follow external symlinks for
   compatibility, or add a second containment implementation.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Eval tests | `python3 -m unittest discover -s tests -p 'test_eval_run.py' -v` | all pass |
| Treat tests | `python3 -m unittest discover -s tests -p 'test_canonicalize.py' -v` | all pass |
| Cross-engine tests | `python3 -m unittest discover -s tests -p 'test_registry_consistency.py' -v` | all pass |
| CLI integration | `python3 -m unittest discover -s tests -p 'test_cli.py' -v` | all pass |
| Python lint | `ruff check scripts/facts.py scripts/eval_run.py scripts/canonicalize.py scripts/semantic.py tests` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | `OK` |
| Full gate | `npm run check` | exit 0 |
| Evidence gate | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0 |
| Self scan | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0; grade A |

## Scope

**In scope**:

- `scripts/eval_run.py`
- `scripts/canonicalize.py`
- `scripts/facts.py` and `scripts/semantic.py` only for small shared safe fact
  helpers; do not fork parsers
- matching tests in `tests/test_eval_run.py`,
  `tests/test_canonicalize.py`, `tests/test_registry_consistency.py`, and
  `tests/test_cli.py`
- synchronized `README.md`, `README.zh-CN.md`, `README.ja.md`
- `SKILL.md`
- compact maintenance invariant in `AGENTS.md`
- evidence-bound `benchmark/self-eval/` refresh after `AGENTS.md` changes
- `plans/README.md`

**Out of scope**:

- Changing target scope ancestry, scoped task IDs, or all-scope expansion.
- Following an external symlink because its basename looks canonical.
- Rewriting every direct `Path` operation in maintenance-only scripts such as
  `check_readme_sync.py` or `gen_adapters.py`.
- Changing explicit user-selected outputs such as `draft -o`.
- Changing mutation ownership/atomicity, plugins, baselines, or exit codes.
- Adding new ecosystems, semantic merge logic, or a runtime dependency.
- Treating a malformed/unsafe fact as a security finding; safe abstention is
  the intended behavior.

## Git workflow

- Branch: `fix/fact-generator-containment`
- Commit: `fix(facts): confine generated repository evidence`
- One focused security/correctness PR around the shared fact-read invariant.
- Do not push directly to `main`. Open an English PR, wait for all nine required
  contexts, then squash-merge and delete the branch.
- This repairs unsafe false facts without removing a valid API. By itself it is
  patch-level.

## Steps

### Step 1: Characterize root eval containment and ambiguity

Add temporary-repository tests covering:

1. external `package.json` symlink cannot create manager/script/framework tasks;
2. external `.nvmrc` cannot create a Node-version task;
3. external root `AGENTS.md` cannot create a convention task;
4. one repository with all three unsafe symlinks emits no external sentinel in
   JSON or stderr and exits cleanly;
5. contained file symlinks to contained targets preserve existing tasks;
6. competing npm/pnpm and yarn/npm lockfiles produce no manager/install/script
   command tasks;
7. one valid lockfile and the no-lockfile `packageManager` fallback preserve
   root task compatibility;
8. targeted and root generation agree when their effective scope is `"."`.

**Verify**: the external-symlink and competing-lockfile assertions fail against
`150d1c9`; normal root/scoped tests remain green.

### Step 2: Single-source safe package/runtime/instruction facts

Refactor root eval to consume contained helpers:

- use `facts.lockfile_managers()` for ambiguity-safe lockfile detection;
- add/reuse one contained JSON loader for `packageManager`, scripts, engines,
  and dependencies;
- use safe Node-version helpers rather than direct `.nvmrc` reads;
- use `facts.read_text_within_root()` for root canonical instructions;
- keep package script command generation silent when the runner is ambiguous.

Do not change safe/unambiguous root serialization. Add a golden equality test
for the current root fixture.

**Verify**: eval tests pass and the three-symlink reproduction emits no tasks
derived from external files.

### Step 3: Confine every draft inference source

Replace direct repository-derived probes in draft-only helpers with shared
facts:

- `_lockfile_backed_manager()` / `_detected_package_manager()`;
- `_has_pytest()` and `_has_ruff()`;
- `_claude_documented_commands()`;
- Python requirements/pyproject decisions;
- any Node/Make/console-script read reached by `render_draft()`.

Inventory data already produced by `scan.scan_repo()` should be reused where it
is the authoritative fact. Do not perform another unpruned tree walk.

**Verify**: draft tests cover external `CLAUDE.md`, pyproject, lockfile,
package.json, Makefile, and tool-config symlinks; no external command or marker
appears, while contained symlinks still work.

### Step 4: Lock the cross-engine invariant

Extend `tests/test_registry_consistency.py` so root eval, scoped eval, draft,
semantic, and drift share:

- lockfile-manager ambiguity semantics;
- contained package metadata reads;
- Node runtime fact sources.

Prefer comparing shared helper objects/results over source-string inspection.

**Verify**: the cross-engine tests fail if any generator reintroduces a
first-match manager or direct unsafe reader.

### Step 5: Document and preserve the maintenance contract

Update all three READMEs and `SKILL.md` to state that fact-derived generation,
not only scan/drift, honors repository containment and abstains on ambiguous
manager/runtime facts. Keep the README structure synchronized.

Add one compact invariant to `AGENTS.md`, refresh the evidence-bound self-eval,
and mark Plan 027 DONE only after merge.

**Verify**: docs sync, evidence gate, self scan, strict drift, and full gate all
pass; `AGENTS.md` stays under the repository context-bloat threshold.

## Test plan

- Use synthetic sentinel strings but never real credentials.
- Model symlink setup/skip behavior after existing scan, semantic, eval
  evidence, and canonicalize mutation tests.
- Cover file symlinks outside/inside the root and directory symlink parents.
- Cover invalid JSON separately from external JSON.
- Preserve normal root generated-task exact output and existing draft output.
- Run full Python/Node tests after focused suites.

## Done criteria

- [ ] Root and targeted eval use the same containment and manager ambiguity
      semantics.
- [ ] Draft facts cannot be supplied by external symlink targets.
- [ ] Safe in-repo symlinks remain supported.
- [ ] No external sentinel/absolute host path appears in generated output.
- [ ] Safe, unambiguous root task/draft behavior remains compatible.
- [ ] Cross-engine invariants, trilingual docs, `SKILL.md`, `AGENTS.md`, and
      self-eval evidence are current.
- [ ] `npm run check`, evidence gate, self scan, and strict drift pass.
- [ ] Plan 027 and its index row are marked DONE after squash merge.

## STOP conditions

Stop and report back (do not improvise) if:

- In-scope helpers no longer match the current-state excerpts.
- Containment requires rejecting safe in-repository symlinks.
- Root compatibility requires retaining a manager guess when two contained
  managers are present.
- A shared helper would introduce a circular import between `facts`,
  `semantic`, `eval_run`, and `canonicalize`.
- The fix requires changing explicit output paths or mutation semantics.
- A verification command fails twice after a reasonable scoped fix.

## Maintenance notes

- “Read-only” is not sufficient: repository content is untrusted data, so every
  fact-derived read must also be contained.
- Review new zero-config/draft fact sources against `scripts/facts.py` before
  accepting them.
- Root and scoped eval are two projections of one fact model; neither may have
  a weaker security or ambiguity policy.
- Ambiguity must cause abstention, not registry/order-based selection.
