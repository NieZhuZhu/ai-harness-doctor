# Plan 029: Bind generated task evidence into eval freshness automatically

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 150d1c9..HEAD -- scripts/eval_run.py tests/test_eval_run.py tests/test_cli.py bin/mcp-server.js tests/test_mcp_server.py README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json benchmark/self-eval/results-after-graded.json benchmark/self-eval/README.md EXTERNAL_VALIDATION.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: Plan 027 (safe fact/evidence paths)
- **Category**: correctness / efficacy / direction / tests / docs
- **Planned at**: commit `150d1c9`, 2026-07-16

## Why this matters

Target-aware generation now records the exact repository paths that establish
each expected answer, but the execution/freshness pipeline ignores those task
records. A caller can generate scoped tasks from
`packages/api/package.json` and `pnpm-lock.yaml`, stamp only `AGENTS.md`, then
change the package manifest while strict evidence verification still exits 0.

The stored task checks and score may therefore remain “current” according to
the gate while the facts they claim to measure have changed. The generated
`evidence` field must become executable provenance: run, matrix, regrade, and
score should automatically bind every declared source, while preserving
explicit `--evidence` for hand-written tasks and additional context.

## Current state

- Plan 026 intentionally added safe source paths to scoped tasks:

  ```json
  {
    "id": "scope:packages%2Fapi:test:api",
    "scope": "packages/api",
    "target": "packages/api/x.py",
    "evidence": ["packages/api/package.json"],
    "check": {"type": "regex", "value": "..."}
  }
  ```

- `scripts/eval_run.py:120-148` builds a result manifest only from the CLI list:

  ```python
  def build_evidence_manifest(tasks_path, evidence_paths, workdir):
      ...
      for raw in evidence_paths or []:
          ...
          files.append({"path": logical, "sha256": _sha256_file(resolved)})
  ```

  `attach_evidence_manifest()` calls it only when `args.evidence` is non-empty.
  It never parses task records for evidence.

- `verify_current_evidence()` at `scripts/eval_run.py:160-208` recomputes the
  same explicit list. Strict score therefore proves only task-file bytes and
  manually named evidence, not generated fact sources.

- Run, multi-round, matrix, and regrade all call
  `attach_evidence_manifest()`. Score calls `verify_current_evidence()`. One
  shared effective-evidence resolver can cover every mode without duplicating
  behavior.

- The audit generated four scoped tasks from:

  ```text
  packages/api/package.json
  pnpm-lock.yaml
  ```

  It then regraded/stamped a result with only `--evidence AGENTS.md`, modified
  `packages/api/package.json` from Vitest to Jest, and ran:

  ```bash
  eval --score RESULT --tasks TASKS --workdir REPO \
    --evidence AGENTS.md --require-current-evidence
  ```

  The command exited 0. The stored manifest listed only `AGENTS.md`; the task's
  own two evidence paths were absent.

- The resulting health recomputed from stored answers was 50/F, but strict
  freshness still passed. Health and freshness are separate gates; a stale
  golden answer must fail freshness before score interpretation.

- Plan 026 explicitly deferred automatic binding:

  ```text
  evidence identifies expected-answer sources but does not replace the existing
  explicit eval result evidence manifest. A future integration must design that
  binding deliberately.
  ```

  This plan is that measured follow-up, not a duplicate of Plan 015 or 026.

- Some generated facts are directory-existence facts (`components-dir`).
  The current manifest accepts regular files only. Automatically binding task
  evidence must define directory freshness without hashing an entire source
  tree or treating unrelated child edits as stale.

## Target contract

1. Parse the task file once and derive a deterministic union of every task
   `evidence` path plus every explicit `--evidence` path.
2. Task evidence is untrusted input. Every entry must be a non-empty string,
   resolve inside `--workdir`, and name an existing regular file or directory.
   Escapes/external symlinks/malformed entries fail closed with concise errors.
3. Existing manually written tasks without `evidence` retain current behavior.
   Explicit `--evidence` remains supported and composes with generated sources.
4. When any task declares evidence, run/matrix/regrade automatically attach a
   manifest even if the user supplied no `--evidence`.
5. Score-time `--require-current-evidence` derives the same union from the
   current task file; callers do not need to repeat generated sources on the
   command line.
6. File evidence keeps exact SHA-256 byte fingerprints. Directory evidence
   records only existence/type and logical path, not a recursive tree hash:
   deleting, renaming, replacing with a file, or escaping becomes stale;
   unrelated child content changes do not.
7. Preserve schema-v1 compatibility for existing file-only manifests:
   - old stamped results remain verifiable with the same explicit arguments;
   - existing file entry shape stays valid;
   - additive directory metadata is deterministic and documented.
8. The manifest contains no absolute host paths, file contents, command output,
   or secrets.
9. MCP generation remains read-only and only emits task provenance; it does not
   run agents or write result manifests.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Eval tests | `python3 -m unittest discover -s tests -p 'test_eval_run.py' -v` | all pass |
| CLI tests | `python3 -m unittest discover -s tests -p 'test_cli.py' -v` | all pass |
| MCP tests | `python3 -m unittest discover -s tests -p 'test_mcp_server.py' -v` | all pass |
| Python lint | `ruff check scripts/eval_run.py tests` | exit 0 |
| JavaScript lint | `eslint bin` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | `OK` |
| Full gate | `npm run check` | exit 0 |
| Evidence gate | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0 |
| Self scan | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0; grade A |

## Scope

**In scope**:

- `scripts/eval_run.py`
- matching tests in `tests/test_eval_run.py` and `tests/test_cli.py`
- `bin/mcp-server.js` / `tests/test_mcp_server.py` only if task output or
  documentation assertions require parity updates
- synchronized `README.md`, `README.zh-CN.md`, `README.ja.md`
- `SKILL.md`
- one real generated-task freshness validation in `EXTERNAL_VALIDATION.md`
- compact efficacy-evidence invariant in `AGENTS.md`
- evidence-bound `benchmark/self-eval/` refresh
- `plans/README.md`

**Out of scope**:

- Automatic all-scope task generation.
- Running agents/LLMs from MCP or during generation.
- Inferring evidence for arbitrary hand-written tasks that declare none.
- Recursive directory tree hashing or Git-index integration.
- Changing generated task IDs, prompts, checks, scope selection, or manager
  inheritance.
- Removing explicit `--evidence`.
- Storing repository file contents in result JSON.
- Adding a runtime dependency.

## Git workflow

- Branch: `feat/generated-eval-evidence`
- Commit: `feat(eval): bind generated task evidence`
- One backward-compatible efficacy/provenance feature PR.
- Execute only after Plan 027, so unsafe external fact paths cannot enter task
  provenance.
- Do not push directly to `main`. Open an English PR, wait for all nine required
  contexts, then squash-merge and delete the branch.
- This adds public eval behavior and is minor-level.

## Steps

### Step 1: Characterize the stale generated-fact reproduction

Add a scoped temporary repo and:

1. generate tasks with package manifest/lock/canonical evidence;
2. regrade or run without manually repeating those evidence paths;
3. assert the result manifest includes the task-declared sources;
4. score with `--require-current-evidence` and no repeated generated source
   flags;
5. modify each source separately and expect exit 7 with sanitized path-only
   diagnostics;
6. restore the source and expect score success.

The initial manifest assertion and post-change exit assertion must fail at
`150d1c9`.

**Verify**: focused tests prove the current false-current result, then turn
green only after implementation.

### Step 2: Build one effective evidence resolver

Add pure helpers that:

- validate task JSON is a list of objects;
- collect each optional `evidence` list;
- reject non-list evidence, non-string/empty entries, and duplicates safely;
- union task evidence with explicit CLI evidence;
- normalize/sort logical paths deterministically.

Use this helper from attach and verify. Do not separately parse evidence in
run, regrade, matrix, and score.

**Verify**: unit tests cover no evidence, explicit-only, task-only, union,
duplicates, malformed entries, escapes, and external symlinks.

### Step 3: Add file/directory evidence fingerprints compatibly

Extend manifest construction:

- regular files keep the current `{path, sha256}` shape;
- directories receive an additive deterministic type marker/digest sufficient
  to verify the same logical directory still exists;
- verification compares path, kind, and digest/type without recursing through
  children;
- legacy entries without `kind` remain regular-file compatible.

Do not hash directory contents or follow external aliases.

**Verify**: deleting/renaming/type-changing a directory returns exit 7; editing
an unrelated child does not.

### Step 4: Apply the invariant to every eval result mode

Ensure identical effective evidence in:

- single run;
- multi-round run;
- matrix;
- regrade;
- strict score verification.

When task evidence exists, attach a manifest without requiring explicit
`--evidence`. Preserve unstamped legacy behavior only for tasks with no
evidence and no explicit list.

**Verify**: mode-specific tests compare the same sorted manifest.

### Step 5: Document and validate the closed loop

Update the three READMEs and `SKILL.md`:

- generated `evidence` is automatically fingerprinted;
- explicit `--evidence` adds manual/extra sources;
- strict score derives generated sources from the task file;
- directory evidence binds existence/type, not subtree bytes.

On a real public monorepo such as Mastra, generate one scoped task set in an
isolated copy/worktree, stamp a result, change one package manifest fact, and
verify strict evidence exits 7 without an agent/LLM call. Record the exact repo
commit, target, evidence paths, and clean/source-copy boundary in
`EXTERNAL_VALIDATION.md`.

Add a compact `AGENTS.md` invariant, refresh self-eval artifacts, and mark Plan
029 DONE after merge.

**Verify**: docs sync, full gate, evidence gate, self scan, and strict drift
pass.

## Test plan

- Effective-evidence pure unit tests.
- Scoped generated-task end-to-end stale-manifest regression.
- File and directory evidence lifecycle.
- External symlink/escape and malformed task evidence.
- Single/multi-round/matrix/regrade manifest parity.
- Legacy explicit evidence and unstamped historical result compatibility.
- Published CLI forwarding smoke test; MCP remains generation-only.

## Done criteria

- [ ] Every generated task source is automatically present in result evidence.
- [ ] Strict score rejects changed package/lock/canonical facts without callers
      repeating generated paths.
- [ ] Explicit/manual evidence composes deterministically.
- [ ] Directory existence facts are freshness-bound without recursive hashing.
- [ ] Unsafe/malformed task evidence fails closed without path/content leaks.
- [ ] Legacy file-only manifests and manual tasks remain compatible.
- [ ] Real monorepo freshness validation is recorded.
- [ ] Trilingual docs, `SKILL.md`, `AGENTS.md`, and self-eval evidence are
      current.
- [ ] All repository and nine required CI checks pass.
- [ ] Plan 029 and its index row are marked DONE after squash merge.

## STOP conditions

Stop and report back (do not improvise) if:

- Plan 027 is not DONE or generated evidence can still come from external
  repository symlinks.
- Compatibility requires invalidating every existing schema-v1 result.
- Directory binding requires recursively hashing a large source tree.
- Automatic evidence would infer undeclared sources for hand-written tasks.
- MCP would need to write files or execute tasks.
- A verification command fails twice after a reasonable scoped fix.

## Maintenance notes

- Task `evidence` is public provenance, not display-only metadata after this
  plan.
- Any future generated fact must name its complete minimal source set or
  explicitly abstain.
- Freshness and health remain separate: stale inputs fail before stored pass
  rates are interpreted.
- Keep evidence diagnostics path-only and deterministic.
