# Plan 040: Prevent provisional AGENTS drafts from authorizing stub destruction

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md`.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 26b07b0..HEAD -- \
>   scripts/canonicalize.py tests/test_canonicalize.py \
>   tests/test_mcp_server.py bin/cli.test.js \
>   README.md README.zh-CN.md README.ja.md SKILL.md \
>   AGENTS.md benchmark/self-eval/results-after-graded.json
> ```
>
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against live code before proceeding. Refresh the
> plan against current `main`; if draft markers, validation shape, stub
> mutation order, or MCP validate policy changed materially, treat that as a
> STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: Plans 004, 008, 011, and 037 (DONE)
- **Category**: correctness / safety
- **Planned at**: commit `26b07b0`, 2026-07-16
- **Implementation**: DONE in PR [#200](https://github.com/NieZhuZhu/ai-harness-doctor/pull/200), merge `a5c6195`

## Implementation progress

- Added one shared canonical-readiness helper for validation and stub apply.
- Exact product-owned provenance/TODO/inference/default markers now produce
  deterministic `DRAFT_REVIEW` errors; arbitrary user TODO/prose remains valid.
- Apply preflights readiness before clean-tree handling or mutation; `--force`
  cannot bypass it, while dry-run remains a byte-preserving preview.
- Regression coverage includes byte-exact source preservation, no Cursor
  pointer creation, symlinked canonical refusal, valid migration compatibility,
  and modern MCP `status:"findings"` / `isError:false`.
- Implementation PR #200 head `fd451e9` passed all nine required contexts
  (`drift`, `lint`, Node 16/20/22, `self-test`, Python 3.9/3.10/3.12) and
  squash-merged as `a5c6195`. Final gate was 719 Python + 26 Node tests, strict
  drift 100/A, and evidence-bound self-eval 34/34.

## Why this matters

Treat explicitly promises that scripts do not perform semantic merging and
that every conflict/inference is reviewed by a human before legacy instruction
sources are reduced to stubs. The generated `AGENTS.md` draft reinforces that
contract with an `Auto-drafted` provenance banner, exact `TODO` sentences, and
`(inferred — confirm)` / `(suggested default)` markers.

The deterministic gates do not enforce that promise. An untouched generated
draft contains all required headings, so `validate --json` returns
`{"ok": true}` with exit 0. Once the file is committed to satisfy the clean-tree
guard, `stubs --apply` accepts mere existence as authorization and rewrites
`CLAUDE.md` plus other tool files. The original facts can therefore be hidden
behind pointers while the canonical file still says "TODO", carries unconfirmed
guesses, and identifies itself as an auto-draft.

Git makes this recoverable, but recoverability is not correctness. A premium
doctor must not certify provisional output as healthy or let a machine-created
placeholder authorize destructive consolidation. The fix should be narrow:
recognize only this product's exact provisional markers, share one canonical
readiness check between validation and mutation, and preserve existing
library-doc, user-authored TODO, dry-run, containment, ownership, and MCP
contracts.

## Mechanical reproduction

Against `main@26b07b0`, create a small clean Git repository with:

```text
package.json        # {"scripts":{"test":"node --test"}}
package-lock.json
CLAUDE.md            # legacy truth plus a repository-specific fact
```

Then:

```bash
python3 scripts/canonicalize.py --draft "$REPO" -o "$REPO/AGENTS.md"
git -C "$REPO" add AGENTS.md
git -C "$REPO" commit -m draft
python3 scripts/canonicalize.py --validate "$REPO" --json
python3 scripts/canonicalize.py --write-stubs "$REPO" --apply
```

Observed on `26b07b0`:

```json
{
  "ok": true,
  "findings": [
    {
      "level": "NOTICE",
      "check": "STUB",
      "path": "CLAUDE.md",
      "message": "tool file not yet downgraded to stub (or regrew)"
    }
  ]
}
```

The apply command exits 0 and replaces `CLAUDE.md` with:

```markdown
@AGENTS.md
<!-- Canonical instructions live in AGENTS.md. Keep this file as an import stub only. -->
```

At that point `AGENTS.md` still contains all three classes of provisional
evidence:

```text
Auto-drafted by `ai-harness-doctor canonicalize.py --draft`
TODO: ...
(inferred — confirm)
```

The original `CLAUDE.md` repository-specific fact is no longer visible to
agents. This is a false-green validation followed by evidence-destructive
mutation.

## Current state

### Draft output self-identifies as provisional

`scripts/canonicalize.py:302-307`:

```python
DRAFT_BANNER = [
    "<!-- Auto-drafted by `ai-harness-doctor canonicalize.py --draft`. -->",
    '<!-- Lines tagged "(inferred — confirm)" are mechanical guesses derived from repository facts; -->',
    '<!-- lines tagged "(suggested default)" are safe conventions to keep. Replace every TODO, review -->',
    "<!-- each inference, and delete this banner before committing. -->",
]
```

`scripts/canonicalize.py:331-332`:

```python
INFERRED = "(inferred — confirm)"
SUGGESTED = "(suggested default)"
```

`render_draft()` emits six fixed `TODO:` prompts plus an additional exact
no-command TODO when no build/test command can be inferred. These product-owned
sentences are safer identifiers than a blanket search for the word `TODO`,
which may be legitimate repository guidance.

### Validation checks structure but not review state

`scripts/canonicalize.py:726-815`:

```python
def validate(args):
    root = Path(args.repo_root).resolve()
    findings = []
    agents = root / "AGENTS.md"
    # path / existence / size / required-heading checks...
    # tool-file STUB notices...
    errors = [f for f in findings if f.get("level") == "ERROR"]
    result = {"ok": not errors, "findings": findings}
```

The generated draft contains `Project overview`, `Build & test`, and
`Conventions`, so it satisfies every default blocking check. The banner,
unresolved TODOs, and unconfirmed values are ignored.

### Stub apply treats existence as semantic authorization

`scripts/canonicalize.py:631-675`:

```python
def write_stubs(args):
    root = Path(args.repo_root).resolve()
    if not facts.is_file_within_root(root, root / "AGENTS.md"):
        raise SystemExit("AGENTS.md must exist before writing stubs.")
    tools = [t.strip() for t in args.tools.split(",") if t.strip()]
    changes = collect_stub_targets(root, tools)
    if args.apply:
        git_clean_or_forced(root, args.force)
    # containment check, then rewrite/delete...
```

Path containment and clean-tree checks are necessary but answer different
questions:

- containment: "would this write leave the repository?";
- ownership: "is this a doctor-managed target?";
- clean tree: "can Git recover this mutation?";
- canonical readiness: "is AGENTS.md actually ready to become the only source
  of truth?"

The last question has no deterministic gate.

### Existing compatibility boundary

`validate()` deliberately relaxes section/size errors to warnings when a file is
confidently classified as end-user library/reference documentation. That
behavior is public and tested. Plan 040 must add provisional-draft errors
without turning all library docs into contributor docs.

Likewise, user-authored `TODO` prose is not proof of an ai-harness-doctor draft.
Only exact generated markers/sentences should block.

## Target contract

1. Define product-owned draft marker constants once in
   `scripts/canonicalize.py`; both draft rendering and review-state detection
   consume those constants.
2. Detect unresolved product draft state by exact, line-aware evidence:
   - the exact ai-harness-doctor auto-draft provenance marker;
   - exact generated TODO prompt sentences;
   - exact `(inferred — confirm)` markers;
   - exact `(suggested default)` markers that still tell the maintainer the line
     is provisional.
3. Do **not** reject arbitrary `TODO`, "inferred", "suggested", or HTML comments
   written by a repository owner.
4. `validate` reports unresolved generated draft state as one or more
   deterministic `ERROR` findings with a stable check id such as
   `DRAFT_REVIEW`. It returns `ok:false` and exit 1.
5. Findings identify the marker class and first line, but do not echo arbitrary
   AGENTS.md content. JSON/Markdown ordering remains deterministic.
6. A reviewed canonical file passes after all product-owned provisional markers
   and generated prompts are removed, provided existing path/size/section
   checks pass.
7. Extract or introduce one canonical-readiness helper shared by `validate` and
   `write_stubs`; do not duplicate the draft-marker list or section logic.
8. Before **any** `--write-stubs --apply` rewrite/delete, require canonical
   readiness:
   - contained, non-symlink canonical path;
   - existing regular AGENTS.md;
   - allowed size/required-section state under the current library-doc policy;
   - no unresolved generated draft markers.
9. Existing pre-migration tool files remain `NOTICE` findings and do not block
   readiness; they are the inputs the stub operation is expected to transform.
10. `--force` continues to override only the dirty-worktree guard. It must not
    bypass unsafe AGENTS paths, required headings, size failures, or unresolved
    draft markers.
11. Dry-run `--write-stubs` remains non-mutating and available for preview.
    It must clearly say that apply would be blocked when canonical readiness
    fails, or return the readiness failure without writing; choose one
    deterministic contract and document it. Prefer preserving preview utility
    unless implementation complexity would create two inconsistent planners.
12. If apply is refused, every legacy tool file and AGENTS.md remains
    byte-identical; no directory or pointer is created.
13. Existing valid canonical files, library/reference docs, custom
    `--require-sections`, symlink containment, clean-tree checks, and tool
    selection remain compatible.
14. MCP `harness_validate` returns the valid JSON finding report with
    `status:"findings"` / `isError:false`, consistent with its existing
    finding-vs-operational policy. The result is not a transport failure merely
    because `ok:false`.
15. Public docs state that heading presence alone is not approval, generated
    provisional markers block validation/apply, and removing markers represents
    an explicit maintainer review—not an automatic semantic merge.
16. `AGENTS.md` records the durable invariant: destructive stub consolidation
    must preflight canonical readiness; dirty-tree force never bypasses it.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Canonicalize tests | `python3 -m unittest discover -s tests -p 'test_canonicalize.py' -v` | exit 0 |
| MCP tests | `python3 -m unittest discover -s tests -p 'test_mcp_server.py' -v` | exit 0 |
| Node dispatch smoke | `node --test bin/*.test.js` | all pass |
| Full quality gate | `npm run check` | all lint + Python + Node tests pass |
| CLI syntax/help | `node --check bin/cli.js && node bin/cli.js help` | exit 0 |
| Self scan | `python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0, grade A |
| Evidence-bound eval | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0 |
| Package contents | `npm pack --dry-run --json` | changed shipped script/docs included |
| README synchronization | `python3 scripts/check_readme_sync.py` | exit 0 |
| Adapter synchronization | `python3 scripts/gen_adapters.py --check` | exit 0 |

## Scope

**In scope**:

- `scripts/canonicalize.py`
- `tests/test_canonicalize.py`
- `tests/test_mcp_server.py`
- `bin/cli.test.js` only if the public CLI dispatch needs an end-to-end
  validate/apply regression
- `README.md`
- `README.zh-CN.md`
- `README.ja.md`
- `SKILL.md`
- `AGENTS.md`
- `benchmark/self-eval/tasks.json` if the new invariant needs an objective task
- `benchmark/self-eval/results-after.json` if the task changes
- `benchmark/self-eval/results-after-graded.json` after AGENTS/task changes
- `benchmark/self-eval/README.md` if the task pack changes
- `EXTERNAL_VALIDATION.md` only if a real-repository read-only evidence round is
  performed
- `plans/040-require-reviewed-canonical-agents.md`
- `plans/README.md`

**Out of scope**:

- semantic merging or deciding conflicts for the user;
- proving that a human actually read every line—this gate proves only that
  explicit provisional markers were resolved;
- rejecting every arbitrary `TODO`, HTML comment, "inferred", or "suggested"
  phrase in user-authored AGENTS.md;
- requiring a signed approval file, interactive prompt, remote service, LLM, or
  reviewer identity;
- changing the generated factual guesses or conflict-default algorithm;
- changing library/reference-doc classification;
- changing what tool paths are canonicalizable;
- making MCP stubs/apply write-capable;
- bypassing readiness through `--force`;
- broad refactors of canonicalize, scanner, installer, or transaction state.

## Git workflow

- Start from latest `main` after the plan PR merges:
  `fix/040-reviewed-canonical-readiness`.
- Keep the validation/mutation correction in one implementation PR.
- Use Conventional Commits in English, for example:
  `fix(treat): require reviewed canonical instructions`.
- Do not push directly to `main`.
- Do not merge until all nine required contexts are green:
  `drift`, `lint`, `node (16)`, `node (20)`, `node (22)`, `self-test`,
  `unittest (3.9)`, `unittest (3.10)`, and `unittest (3.12)`.
- Admin bypass is allowed only for sole-maintainer approval deadlock after
  required checks are green and every discussion is resolved.

## Steps

### Step 1: Characterize the false green and evidence loss

Add one end-to-end test that:

1. creates a repo with a real legacy `CLAUDE.md` fact;
2. runs `--draft -o AGENTS.md`;
3. establishes a clean Git baseline;
4. proves current `--validate --json` falsely returns `ok:true`;
5. proves current `--write-stubs --apply` rewrites the source.

For the committed regression, invert the final expectations:

- validation exits 1 with `DRAFT_REVIEW`;
- apply exits non-zero;
- AGENTS.md and every legacy tool file retain byte-exact content.

Keep the reproduction synthetic so no public repository is mutated.

**Verify**:

```bash
python3 -m unittest discover -s tests -p 'test_canonicalize.py' -v
```

Expected before implementation: the new regression fails. Expected after each
subsequent step: it passes.

### Step 2: Single-source provisional marker detection

Refactor generated banner/TODO/annotation literals into named constants used by
both `render_draft()` and a pure helper such as:

```python
def unresolved_draft_markers(text):
    ...
```

The helper returns stable records such as `{kind, line}`. It must match exact
product-owned markers or exact generated prompts, never broad keywords.

Add focused tests for:

- untouched draft: all marker classes found;
- partially edited draft: remaining markers found with stable first lines;
- all generated markers/prompts removed: none found;
- arbitrary user `TODO`, inferred prose, suggested prose, and unrelated HTML
  comments: none found;
- repeat invocation: byte-identical record order;
- no user content echoed in records.

**Verify**:

```bash
python3 -m unittest discover -s tests -p 'test_canonicalize.py' -v
```

Expected: focused helper and draft rendering tests pass.

### Step 3: Make validation report provisional state truthfully

Add `DRAFT_REVIEW` ERROR findings to `validate()` through a canonical-only
helper. Preserve:

- current path/symlink handling;
- library-doc size/section softening;
- custom required sections;
- pre-migration `STUB` notices;
- deterministic JSON and human output.

Test untouched, partially reviewed, fully reviewed, user-authored TODO, and
library-doc cases. A generated draft must never print "validation passed."

**Verify**:

```bash
python3 -m unittest discover -s tests -p 'test_canonicalize.py' -v
```

Expected: validation returns exit 1 only for blocking canonical findings and
continues to report notices additively.

### Step 4: Preflight destructive stub apply

Extract the canonical blocking checks so `write_stubs()` can use them without
running stub-state notices against the files it is about to migrate.

For `--apply`, run readiness before:

- clean-tree/force handling;
- directory creation;
- file rewrite;
- file deletion.

Render one concise actionable error naming blocking check ids and instructing
the operator to run `validate`. Do not include arbitrary file contents.

Tests:

- untouched/partially edited draft blocks apply byte-exactly;
- `--force` does not bypass;
- missing required section blocks;
- unsafe AGENTS path blocks;
- reviewed valid canonical applies as before;
- library/reference doc with only soft warnings preserves current behavior;
- tool `STUB` notices do not block expected migration;
- readiness failure creates no Cursor pointer/directory;
- dry-run contract is explicit and non-mutating.

**Verify**:

```bash
python3 -m unittest discover -s tests -p 'test_canonicalize.py' -v
```

Expected: all mutation refusal/compatibility tests pass.

### Step 5: Preserve CLI and MCP semantics

Add:

- a Node CLI smoke only if needed to prove the packaged `validate` path returns
  the new controlled exit/report instead of an unknown-command/raw failure;
- an MCP test where `harness_validate(json:true)` sees an untouched draft and
  returns a valid structured finding report with `ok:false`,
  `status:"findings"`, `isError:false`, and exit code 1.

Do not add write capability or readiness flags to MCP `harness_stubs`.

**Verify**:

```bash
node --test bin/*.test.js
python3 -m unittest discover -s tests -p 'test_mcp_server.py' -v
```

Expected: all existing protocol versions and new finding semantics pass.

### Step 6: Synchronize public docs

Update all three READMEs and `SKILL.md`:

- draft output is provisional and intentionally fails canonical readiness until
  product markers/prompts are removed through explicit review;
- `validate` checks structure **and** unresolved generated draft state;
- `stubs --apply` preflights canonical readiness before replacing sources;
- dry-run behavior;
- `--force` is not a semantic-readiness bypass;
- this proves explicit marker resolution, not reviewer identity or correctness
  of human decisions.

Keep fenced blocks, tables, links, and headings synchronized.

**Verify**:

```bash
python3 scripts/check_readme_sync.py
python3 scripts/gen_adapters.py --check
```

Expected: both exit 0.

### Step 7: Record maintenance evidence

Add one concise AGENTS invariant and, if needed, one objective self-eval task:

> Stub consolidation preflights canonical readiness; product-owned provisional
> draft markers are blocking, and `--force` never bypasses them.

Keep AGENTS below 12 KiB by consolidating adjacent Treat text. Refresh committed
eval evidence through the documented regrade workflow and retain Grade A.

Optionally run a read-only external evidence round:

1. produce `draft` to stdout from a current public repo with `CLAUDE.md`;
2. write those bytes only into a separate synthetic wrapper, not the target;
3. prove the target worktree stayed clean and the wrapper validates as
   provisional.

Do not claim this as a public-repo mutation test.

**Verify**:

```bash
wc -c AGENTS.md
python3 scripts/eval_run.py \
  --score benchmark/self-eval/results-after-graded.json \
  --tasks benchmark/self-eval/tasks.json \
  --workdir . \
  --evidence AGENTS.md \
  --require-current-evidence \
  --fail-under 80
python3 scripts/check_drift.py . --strict
```

Expected: AGENTS below 12 KiB, evidence current at Grade A, drift Grade A.

### Step 8: Full gate, review, and PR

Run every command in "Commands you will need". Review the diff on two axes:

- standards: stdlib-only, tests, docs parity, containment, MCP read-only;
- spec: exact provisional markers, validation false-green closed, no mutation
  before readiness, no broad TODO false positives.

Open one implementation PR. Wait for all nine contexts, resolve discussions,
then squash merge and record PR/head/check/merge evidence in this plan/index.

This enforces an already documented safety/correctness contract and is a
backward-compatible **patch** unless a STOP condition requires a new public
approval artifact or breaking flag.

## Test plan

- Marker classifier:
  - full/partial/cleared generated draft;
  - exact line/kind ordering;
  - arbitrary user TODO/prose/comment non-match.
- Validate:
  - untouched draft exits 1;
  - partial draft exits 1;
  - reviewed valid canonical exits 0;
  - library-doc warnings unchanged;
  - custom required sections unchanged;
  - pre-migration stub notices remain non-blocking.
- Apply:
  - provisional, invalid-section, unsafe path all block before writes;
  - byte-exact source preservation;
  - no created pointer directory;
  - `--force` cannot bypass;
  - reviewed canonical transforms exactly as before;
  - dry-run remains non-mutating.
- MCP/CLI:
  - validate finding report remains `isError:false`;
  - no write-capable MCP surface.
- Evidence:
  - self-eval and strict drift current/green.

## Done criteria

- [ ] Untouched doctor draft makes `validate` exit 1 with `DRAFT_REVIEW`.
- [ ] Product marker detection is single-sourced with draft rendering.
- [ ] Ordinary user-authored TODO/prose is not rejected.
- [ ] Fully reviewed canonical files retain existing validation behavior.
- [ ] `stubs --apply` runs canonical readiness before any mutation.
- [ ] Readiness failure preserves every byte and creates nothing.
- [ ] `--force` does not bypass canonical readiness.
- [ ] Pre-migration STUB notices do not block valid consolidation.
- [ ] Library/reference-doc compatibility is preserved.
- [ ] MCP validate returns findings, not an operational error.
- [ ] No write-capable MCP surface is added.
- [ ] Behavior changes have tests in the same PR.
- [ ] Trilingual READMEs and `SKILL.md` are synchronized.
- [ ] `npm run check` passes.
- [ ] Self scan exits 0; strict drift is 100/100 Grade A.
- [ ] Evidence-bound self-eval is current and Grade A.
- [ ] AGENTS remains below 12 KiB and records the invariant.
- [ ] No runtime dependency was added; Python 3.9 / Node 16 remain supported.
- [ ] Implementation PR has all nine required contexts green and is merged.
- [ ] Plan/index contain final PR, CI, test, and merge evidence.

## STOP conditions

Stop and report instead of improvising if:

- reliable detection requires broad rejection of arbitrary `TODO` or prose;
- a reviewed draft needs a new signed approval file, identity, or interactive
  state rather than removal of explicit generated markers;
- canonical readiness cannot be shared without changing library-doc policy;
- correct apply behavior requires `--force` to bypass unresolved draft state;
- MCP must become write-capable;
- apply can partially mutate before a readiness error is known;
- the fix requires a schema-breaking validation result or new mandatory CLI
  flag;
- AGENTS cannot remain below 12 KiB after consolidation;
- any required CI context is red/pending or a discussion remains unresolved.

## Maintenance notes

- Generated provisional text is a product protocol. Keep rendering and
  detection single-sourced whenever draft wording changes.
- Readiness is distinct from stub state: full legacy configs are expected
  before migration and remain notices, not readiness errors.
- `--force` means "accept dirty Git state," not "ignore semantic or path
  safety."
- Exact marker removal is auditable intent, not proof that the resulting prose
  is correct. Human conflict decisions remain outside deterministic scripts.
- Future destructive Treat operations must consume the same readiness helper
  rather than inventing weaker existence checks.
