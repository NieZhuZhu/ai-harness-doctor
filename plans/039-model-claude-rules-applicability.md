# Plan 039: Model Claude Code project rules and their path applicability

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md`.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat c141268..HEAD -- \
>   assets/agent-tools.json scripts/applicability.py scripts/scan.py \
>   scripts/explain.py scripts/scan_render.py scripts/sarif.py \
>   tests/test_registry_consistency.py tests/test_scan.py tests/test_explain.py \
>   tests/test_sarif.py tests/test_pr_review.py \
>   README.md README.zh-CN.md README.ja.md SKILL.md \
>   EXTERNAL_VALIDATION.md AGENTS.md benchmark/self-eval/results-after-graded.json
> ```
>
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against live code before proceeding. Refresh the
> implementation against current `main`; if the registry/applicability/scope
> contracts changed materially, treat that as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED
- **Depends on**: Plans 020, 023, and 035 (DONE)
- **Category**: direction / correctness
- **Planned at**: commit `c141268`, 2026-07-16
- **Implementation**: TODO

## Why this matters

Claude Code officially treats recursively discovered
`.claude/rules/**/*.md` files as project instructions. A rule without
frontmatter is always loaded; a rule with `paths` frontmatter is loaded when
Claude works with a matching file. This is no longer an experimental or niche
surface: current public repositories such as `bitwarden/clients` and
`algolia/instantsearch` commit these rules.

AI Harness Doctor currently recognizes root/nested `CLAUDE.md` but does not
recognize `.claude/rules/` at all. Such files are absent from inventory,
complete-file secret/security scanning, overlap evidence, conflict analysis,
SARIF, PR review, and `explain TARGET`. This is a product-level blind spot:
the project advertises itself as a doctor for Claude Code harness
configuration, yet a first-party Claude Code instruction surface can carry a
stale command, conflicting package-manager declaration, unsafe instruction, or
credential without appearing in the diagnosis.

The repository already has the correct architectural seam. Plan 035 added a
bounded, standard-library-only applicability engine for Cursor and
Copilot/VS Code, current-path conflict domains, future-target `explain`,
complete security scanning for invalid metadata, and a hard boundary that
recursive discovery does not authorize recursive Treat deletion. Extend that
seam for Claude rules rather than creating a parallel parser or scope model.

## Audit evidence

### Official contract

Anthropic's current Claude Code documentation at
`https://code.claude.com/docs/en/claude-md.md` states:

- all Markdown files under `.claude/rules/` are discovered recursively;
- rules without `paths` frontmatter load unconditionally with the same
  priority as `.claude/CLAUDE.md`;
- `paths` is a YAML list of project-relative glob patterns;
- multiple patterns and brace expansion are supported;
- glob character classes such as `[abc]` are supported, and a literal `[` can
  be escaped;
- project rules may be symlinked, but this project's existing repository
  boundary remains stricter: external symlink content must not influence an
  audit.

The implementation must model only the deterministic metadata required for
diagnosis. It must not become a generic YAML parser.

### Real repositories

GitHub code search on 2026-07-16 found current public examples including:

- `bitwarden/clients:.claude/rules/i18n.md` — block-list `paths` covering
  `apps/**/*.html`, `apps/**/*.ts`, `libs/**/*.html`, and `libs/**/*.ts`;
- `jrsoftware/issrc:.claude/rules/iss.md` — inline-list
  `paths: ["**/*.iss"]`;
- `SSWConsulting/SSW.VerticalSliceArchitecture:.claude/rules/domain.md` —
  block-list `paths` scoped to a domain subtree;
- `algolia/instantsearch:.claude/rules/e2e.md` — no frontmatter, therefore an
  always-loaded rule.

At audit time GitHub reported roughly 13k stars for `bitwarden/clients` and 4k
for `algolia/instantsearch`. This is sufficient ecosystem evidence to prefer a
real compatibility feature over adding more speculative agent filenames.

### Mechanical reproduction

Against planned commit `c141268`, create:

```text
repo/
├── AGENTS.md                    # "Use pnpm."
├── scripts/a.py
└── .claude/rules/python.md      # paths: scripts/**/*.py; "Use uv."
```

Then run:

```bash
python3 scripts/scan.py "$REPO" --json
python3 scripts/explain.py "$REPO" scripts/a.py --json
```

Observed on `c141268`:

- `scan.files` contains only `AGENTS.md`;
- `scan.conflicts` is empty because the Claude rule is never collected;
- `explain.diagnostic_sources` contains only `AGENTS.md`;
- therefore neither the rule's scoped declaration nor any secret/security
  content can reach report, SARIF, or PR-review surfaces.

Expected after this plan:

- the rule is inventoried as Claude Code;
- its complete bytes are security-scanned;
- its structured applicability is `path` with one current match;
- the scoped package-manager conflict is reported for `scripts/a.py`, but not
  for an unrelated target;
- `explain` calls it `automatic` only for matching existing or future targets.

## Current state

### The registry omits Claude rules

`assets/agent-tools.json:9-15`:

```json
{
  "id": "claude",
  "label": "Claude Code",
  "scan_patterns": ["CLAUDE.md", "CLAUDE.local.md", ".claude/CLAUDE.md", "**/CLAUDE.md"],
  "stub_paths": ["CLAUDE.md", ".claude/CLAUDE.md"],
  "stub_kind": "import",
  "stub_content": "@AGENTS.md\n<!-- Canonical instructions live in AGENTS.md. Keep this file as an import stub only. -->\n",
  "canonicalizable": true
}
```

`assets/agent-tools.json` is the single source of truth for recognized
instruction files. Adding an ad hoc glob in `scan.py` would violate the
repository's registry invariant.

### The applicability engine has the reusable bounded seam

`scripts/applicability.py:14-23`:

```python
MODES = {"always", "path", "conditional", "manual", "ignored", "invalid"}
SUPPORTED_FORMATS = {
    "cursor-mdc",
    "cursor-ignored-md",
    "copilot-instructions",
}
_CONTROL_FIELDS = {
    "cursor-mdc": {"alwaysApply", "description", "globs"},
    "copilot-instructions": {"applyTo", "description", "name"},
}
```

`scripts/applicability.py:59-111` currently accepts scalar frontmatter only.
That is sufficient for Cursor/Copilot's deliberately bounded subset, but
Claude's documented `paths` shape is normally a block sequence and real
repositories also use an inline sequence. Extending the parser must be
format-aware so existing accepted/rejected Cursor/Copilot inputs do not change
accidentally.

`scripts/applicability.py:125-149` currently rejects every `[`/`]`:

```python
if any(ch in value for ch in "[]"):
    raise FrontmatterError(
        "glob patterns use unsupported character-class syntax"
    )
```

Claude documents character classes. Support a bounded, validated class dialect
for Claude rather than silently treating documented patterns as invalid.

### Scan and explain already share applicability

`scripts/scan.py:1701-1748` collects registry-matched files, preserves complete
identity/security coverage, and binds path rules to the current contained file
index. `scripts/scan.py:985-1054` makes only overlapping automatic domains
blocking conflicts.

`scripts/explain.py:89-128` classifies one concrete existing/future target:

```python
if app["mode"] == "always":
    return "automatic"
if app["mode"] == "path":
    return (
        "automatic"
        if scan.applicability.matches(app.get("patterns", []), target_path)
        else "non-matching"
    )
return app["mode"]
```

Do not duplicate this logic for Claude. A correctly normalized
`{"mode": "always"|"path", "patterns": [...]}` record should flow through the
existing conflict and explain engines.

### Recursive reads must not expand write authority

Plan 035 established and tested that recursive Cursor/Copilot discovery does
not authorize recursive Treat deletion. Preserve the same boundary for Claude:

- scan/read/security/report `.claude/rules/**/*.md`;
- keep `stub_paths` limited to `CLAUDE.md` and `.claude/CLAUDE.md`;
- do not delete, rewrite, or synthesize files under `.claude/rules/`;
- `stubs --apply` and `drift --fix --apply` retain their current ownership and
  symlink safety contracts.

## Target contract

1. The Claude registry entry recognizes root-project
   `.claude/rules/**/*.md` and associates it with a new single-sourced
   applicability format such as `claude-rules`.
2. Workspace/package scans naturally recognize package-local
   `.claude/rules/**/*.md` because each package report receives its own root.
   Do not add a broad `**/.claude/rules/**` root pattern unless the current
   scope engine is also proven to resolve those patterns against the correct
   project root.
3. A Claude rule with no frontmatter is `always`.
4. A Claude rule with a valid non-empty `paths` field is `path`.
5. Accept the official/observed bounded sequence forms:
   - block sequence:
     `paths:\n  - "src/**/*.ts"\n  - "tests/**/*.test.ts"`;
   - inline sequence: `paths: ["**/*.iss", "src/**/*.{ts,tsx}"]`.
6. Preserve existing comma-separated scalar behavior only for formats that
   already use it. Do not reinterpret an ambiguous Claude scalar as a list
   unless official docs explicitly support that shape.
7. Support deterministic project-relative `*`, `?`, `**`, brace alternatives,
   and validated character classes for Claude's documented glob dialect.
   Reject absolute paths, `..`, home paths, NUL/newline, malformed/unclosed
   braces/classes, unsupported YAML tags/anchors/maps, nested sequences, and
   expansion above the existing bounded limit.
8. Invalid or truncated frontmatter becomes a non-blocking `invalid`
   applicability warning and contributes no conflict signal, while full-file
   identity, overlap, and security scanning still run.
9. Path rules match only current contained repository paths for scan-time
   conflicts. A rule with no current match remains a non-blocking
   `no-current-match` notice; `explain` may classify a concrete contained
   future target directly.
10. Existing Cursor and Copilot behavior, report schema, ordering, exit codes,
    baselines, SARIF rule identity, and PR-review rendering remain compatible.
11. All user-facing scan/explain/applicability documentation names Claude rules
    alongside Cursor and Copilot and accurately states the bounded parser
    contract.
12. External validation runs the development checkout read-only against at
    least:
    - `bitwarden/clients` for block-list path rules; and
    - one always-loaded or inline-list public rule repository.
    Record exact commit SHAs, commands, evidence boundary, result, and fixing
    PR in `EXTERNAL_VALIDATION.md`.
13. After implementation, `AGENTS.md` records the durable maintenance
    invariant: every newly recognized structured rule format must preserve
    registry single-sourcing, complete security/identity reads, bounded
    fail-closed metadata parsing, target-scope truth, and non-expanding Treat
    authority.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Registry/parser tests | `python3 -m unittest tests.test_registry_consistency tests.test_scan -v` | exit 0 |
| Explain/SARIF/review tests | `python3 -m unittest tests.test_explain tests.test_sarif tests.test_pr_review -v` | exit 0 |
| Full quality gate | `npm run check` | all lint + Python + Node tests pass |
| CLI syntax/help | `node --check bin/cli.js && node bin/cli.js help` | exit 0 |
| Self scan | `python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0, grade A |
| Evidence-bound eval | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0 |
| Package contents | `npm pack --dry-run --json` | includes changed shipped registry/scripts/docs |
| README synchronization | `python3 scripts/check_readme_sync.py` | exit 0 |
| Adapter synchronization | `python3 scripts/gen_adapters.py --check` | exit 0 |

## Scope

**In scope**:

- `assets/agent-tools.json`
- `scripts/applicability.py`
- `scripts/scan.py` only if shared applicability/report wording needs a
  format-neutral correction
- `scripts/explain.py`
- `scripts/scan_render.py`
- `scripts/sarif.py` only if a new regression proves generic applicability
  routing is incomplete
- `tests/test_registry_consistency.py`
- `tests/test_scan.py`
- `tests/test_explain.py`
- `tests/test_sarif.py`
- `tests/test_pr_review.py`
- `README.md`
- `README.zh-CN.md`
- `README.ja.md`
- `SKILL.md`
- `EXTERNAL_VALIDATION.md`
- `AGENTS.md`
- `benchmark/self-eval/results-after-graded.json` when the AGENTS evidence hash
  changes
- `plans/039-model-claude-rules-applicability.md`
- `plans/README.md`

**Out of scope**:

- a generic YAML parser or any runtime dependency;
- user-level `~/.claude/rules/` or managed organization policy outside the
  audited repository;
- following an external rule symlink despite Claude Code supporting shared
  external symlinks — repository audit containment wins;
- inferring natural-language or description-selected applicability;
- root scanning every nested `**/.claude/rules/**` without project-root
  semantics;
- deleting, rewriting, or replacing `.claude/rules/` during Treat/stubs/fix;
- generating Claude rules from AGENTS.md;
- changing canonical AGENTS.md nearest-file inheritance;
- changing existing fail-on exit codes, baseline identity, or health scoring;
- broad refactors of `scan.py`, `applicability.py`, or report renderers.

## Git workflow

- Start the implementation branch from the latest `main` after this plan PR
  merges: `feat/039-claude-rules-applicability`.
- Keep this one themed feature in one implementation PR.
- Use Conventional Commits in English, for example:
  `feat(scan): model Claude project rules`.
- Do not push directly to `main`.
- Do not merge until all nine required contexts are green:
  `drift`, `lint`, `node (16)`, `node (20)`, `node (22)`, `self-test`,
  `unittest (3.9)`, `unittest (3.10)`, and `unittest (3.12)`.
- Admin bypass is allowed only for the sole-maintainer approval deadlock after
  required checks are green and all discussions are resolved.

## Steps

### Step 1: Add Claude project rules to the registry without write authority

Update the Claude entry in `assets/agent-tools.json`:

- add the root-project recursive `.claude/rules/**/*.md` scan pattern;
- map that exact pattern to the new `claude-rules` applicability format;
- leave `stub_paths`, `stub_kind`, and `stub_content` unchanged.

Update registry consistency tests so the new format is proven single-sourced
and the recursive read pattern is proven absent from canonicalize/drift
mutation targets.

**Verify**:

```bash
python3 -m unittest tests.test_registry_consistency -v
```

Expected: all tests pass; the registry is the only declaration of the new scan
pattern and format.

### Step 2: Implement a bounded Claude frontmatter parser

Extend `scripts/applicability.py` through the existing `classify()` contract.
Prefer small format-specific helpers over making the existing scalar parser
silently accept arbitrary YAML.

Required cases:

- no frontmatter → `always`, original body preserved;
- empty/absent `paths` in a valid frontmatter block → `always` only if that
  exact shape is valid under the official contract; otherwise fail closed;
- block and inline `paths` sequences → `path`;
- line-preserving frontmatter blanking so conflict evidence points at the
  original body line;
- deterministic de-duplication and bounded brace expansion;
- safe character-class compilation for Claude only;
- malformed field/sequence/glob → `invalid`, empty `signal_text`.

Do not loosen Cursor/Copilot acceptance as a side effect. Add unit tests that
run the same old malformed corpus before and after the new Claude cases.

**Verify**:

```bash
python3 -m unittest tests.test_scan.ApplicabilityParserTests -v
```

Expected: old Cursor/Copilot cases and new Claude cases all pass.

### Step 3: Prove inventory, security, conflicts, and target explanation

Add integration tests in `tests/test_scan.py` and `tests/test_explain.py` for:

1. recursive Claude rule inventory;
2. always-loaded rule conflict behavior;
3. block-list and inline-list path rules;
4. disjoint versus overlapping current domains;
5. existing and future target explanation;
6. no-current-match notice;
7. invalid/truncated frontmatter excluded from conflict signals;
8. complete tail-secret detection and no secret value in output;
9. external symlink exclusion and in-repo lexical path retention;
10. package-local rules through monorepo subcontexts;
11. line numbers after frontmatter;
12. deterministic repeat output and one shared inventory walk.

Use the existing Plan-035 tests as the structural pattern. Avoid
format-specific branches in the conflict engine when the normalized
applicability object already expresses the needed domain.

**Verify**:

```bash
python3 -m unittest tests.test_scan tests.test_explain -v
```

Expected: all tests pass and the original reproduction now inventories and
scopes the Claude rule.

### Step 4: Prove every public finding surface and preserve mutation boundaries

Add regression assertions that Claude applicability warnings and conflicts
flow through:

- Markdown;
- SARIF;
- PR-review summary/inline formatting.

Add a dry-run and apply containment test proving `stubs` and `drift --fix`
never delete or rewrite files under `.claude/rules/`. Read discovery must not
become mutation ownership.

**Verify**:

```bash
python3 -m unittest \
  tests.test_canonicalize tests.test_check_drift \
  tests.test_sarif tests.test_pr_review -v
```

Expected: all tests pass; recursive Claude rules are visible in diagnostics
but byte-identical after every Treat/fix path.

### Step 5: Synchronize the public contract

Update `README.md`, `README.zh-CN.md`, `README.ja.md`, and `SKILL.md`:

- recognized Claude project-rule path;
- always versus `paths` behavior;
- bounded supported sequence/glob syntax and fail-closed limitations;
- security/identity still scan invalid/truncated rule bytes;
- `scan` conflicts use current contained paths while `explain` can assess a
  future target;
- recursive read coverage does not authorize Treat deletion.

Keep all fenced blocks byte-identical, preserve table/link parity, and avoid
claiming generic YAML compatibility.

**Verify**:

```bash
python3 scripts/check_readme_sync.py
python3 scripts/gen_adapters.py --check
```

Expected: both exit 0.

### Step 6: Validate against current public repositories

Use sparse or full clean checkouts outside this repository. Pin and record the
exact commit for each target. Run only the development checkout's read-only
`scan` and `explain`; do not run plugins, Treat, mutation, or LLM calls.

At minimum:

- `bitwarden/clients`:
  prove `.claude/rules/i18n.md` is inventoried, parsed as a path rule, and
  automatically selected for one matching app/lib target but not an unrelated
  target;
- `algolia/instantsearch` or `jrsoftware/issrc`:
  prove no-frontmatter always behavior or inline-list behavior.

Review every reported finding before calling it a product defect. Record clean
or expected findings honestly in `EXTERNAL_VALIDATION.md`, including sparse
checkout limitations.

**Verify**:

```bash
git -C "$VALIDATION_REPO_1" status --short
git -C "$VALIDATION_REPO_2" status --short
```

Expected: both target worktrees remain clean.

### Step 7: Record the durable invariant and refresh evidence

Add one concise maintenance invariant to `AGENTS.md`; keep the file below the
repository's context-bloat threshold. Regrade or refresh
`benchmark/self-eval/results-after-graded.json` only through the repository's
documented evidence-bound workflow so the committed result matches the new
AGENTS bytes and remains 33/33 Grade A.

Update this plan and `plans/README.md` with implementation PR, merge SHA,
external-validation evidence, required CI results, release classification, and
DONE status.

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

Expected: AGENTS remains below 12 KiB, eval exits 0 at 33/33 Grade A, and
strict drift exits 0 at grade A.

### Step 8: Run the full gate and land through a PR

Run every command in "Commands you will need", inspect the complete diff for
scope, then open the implementation PR with the repository template. Wait for
all nine required contexts. Resolve every review discussion before squash
merge.

This is a backward-compatible public capability and therefore a **minor**
release under the repository policy when the user later requests a release.
Do not publish a version as part of this plan unless separately instructed.

## Test plan

- Registry:
  - Claude recursive rule pattern and format are single-sourced;
  - mutation targets remain flat/owned only.
- Parser:
  - no frontmatter always-on;
  - official block list;
  - observed inline list;
  - quoting, commas, brace expansion, character classes, escaped literal
    bracket;
  - duplicate/unknown fields, maps, anchors/tags, malformed lists/classes,
    absolute/escaping paths, and expansion limit fail closed;
  - existing Cursor/Copilot corpus unchanged.
- Scan:
  - root and package inventory;
  - complete identity/security on valid/invalid/truncated files;
  - current-path match counts;
  - overlapping/disjoint conflicts;
  - no-current-match diagnostics;
  - line attribution and deterministic ordering;
  - symlink containment.
- Explain:
  - matching/non-matching/always statuses for existing and future targets;
  - only target-applicable conflicts;
  - limitations text names all modeled formats.
- Delivery:
  - Markdown, SARIF, and PR review include Claude applicability findings;
  - no recursive Treat/fix mutation.
- External:
  - one block-list and one always/inline-list public repository.

## Done criteria

- [ ] `.claude/rules/**/*.md` is recognized only through
      `assets/agent-tools.json`.
- [ ] Claude no-frontmatter, block-list, and inline-list rules receive correct
      normalized applicability.
- [ ] Documented bounded glob syntax is deterministic and unsafe/unsupported
      metadata fails closed.
- [ ] Full-file identity/security coverage survives invalid/truncated metadata.
- [ ] Scan conflicts and `explain TARGET` honor Claude rule applicability.
- [ ] Markdown, SARIF, and PR review deliver the findings.
- [ ] Treat/stubs/fix never mutate `.claude/rules/`.
- [ ] Existing Cursor/Copilot behavior and exit contracts do not regress.
- [ ] Two current public repositories are recorded in
      `EXTERNAL_VALIDATION.md` with exact evidence boundaries.
- [ ] English, Simplified Chinese, Japanese READMEs, and `SKILL.md` are
      synchronized.
- [ ] Behavior changes have tests in the same PR.
- [ ] `npm run check` passes.
- [ ] Self scan exits 0; strict drift is 100/100 Grade A.
- [ ] Evidence-bound self-eval is current and 33/33 Grade A.
- [ ] `AGENTS.md` is below 12 KiB and contains the new invariant.
- [ ] No runtime dependency was added; Python 3.9 and Node 16 remain supported.
- [ ] Implementation PR has all nine required contexts green and is merged.
- [ ] Plan/index contain the final PR, CI, external-validation, and merge
      evidence.

## STOP conditions

Stop and report instead of improvising if:

- Anthropic's current official contract differs materially from the evidence
  above, especially the project-relative `paths` base or recursive discovery;
- correct nested project-root semantics require broad
  `**/.claude/rules/**` discovery in the root report rather than package-local
  scans;
- supporting official character classes requires unsound regex translation or
  a third-party glob/YAML dependency;
- a valid rule cannot be represented by the existing normalized
  `always`/`path` applicability contract;
- recursive discovery requires deleting or rewriting rule files to make tests
  pass;
- existing Cursor/Copilot inputs change classification without an explicit,
  reviewed compatibility reason;
- external validation exposes private paths, repository contents, tokens, or
  any mutation;
- `AGENTS.md` cannot remain below 12 KiB after concise consolidation;
- any required CI context is red/pending or a review discussion remains
  unresolved.

## Maintenance notes

- `assets/agent-tools.json` remains the source of truth for recognized config
  paths and applicability formats. Future formats need registry consistency
  tests before engine changes.
- Applicability parsing is intentionally metadata-only and bounded. Do not
  evolve it into general YAML because a new tool adds one field.
- Keep two evidence boundaries distinct:
  - complete bytes for identity/security;
  - bounded semantic prefix for applicability/conflicts/overlap.
- A scanner recognizing a recursive rule tree does not own that tree.
  Mutation authority must be designed and tested separately.
- Scan conflict domains are evidence over current contained files, not a
  symbolic proof over every future glob intersection. `explain` answers a
  concrete future target directly.
- Claude Code itself permits external symlinked shared rules. AI Harness Doctor
  intentionally refuses those external bytes in repository audits; document
  this as an audit-containment limitation rather than weakening the boundary.
