# Plan 069: Report the harness maturity ladder in scan

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and honor every STOP condition. Update the plan index
> only when actual merge/check evidence exists.
>
> **Drift check**:
>
> ```bash
> git diff --stat a6f6932..HEAD -- \
>   scripts/scan.py scripts/scan_render.py scripts/registry.py \
>   scripts/canonicalize.py tests/test_scan.py \
>   README.md README.zh-CN.md README.ja.md README.es.md README.ko.md \
>   README.pt-BR.md README.fr.md SKILL.md
> ```
>
> If `find_gaps`, `build_project_snapshot`, the G5–G8 retirement comment, or the
> scan exit-code precedence changed semantically, rerun the audit before
> implementing.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW–MED (additive report section; default exit semantics unchanged;
  the only new exit path sits behind a new opt-in flag)
- **Depends on**: none hard; reuses contracts landed by Plans 052/053 (facts
  containment) and 061 (AGENTS.md headroom discipline)
- **Category**: product / feature (premium-upgrade loop)
- **Planned at**: commit `a6f6932`, 2026-07-20
- **Status**: DONE — plan PR
  [#301](https://github.com/NieZhuZhu/ai-harness-doctor/pull/301);
  implementation PR
  [#302](https://github.com/NieZhuZhu/ai-harness-doctor/pull/302), squash merge
  `3da9a77`; both passed all nine required contexts.

## Implementation evidence

- `report["maturity"]` ships with the contract shape: cumulative levels
  0 Ungoverned → 4 Evidenced, per-item present/absent statuses with evidence
  strings, `next.missing` remedies naming only packaged commands, and a
  five-item advisory list that never gates a level. Monorepo package
  sub-reports carry no ladder; `--repos-file` rows carry a pre-suppression
  row-level maturity summary and the batch table gained the Maturity column.
- G1–G4 predicates were extracted into shared helpers
  (`missing_required_sections` / `non_minimal_stubs` /
  `missing_guard_workflows`) consumed by both `find_gaps` and
  `compute_maturity`; all pre-existing gap tests passed untouched, and the
  ladder is provably independent of `--no-gaps` and baseline suppression.
- Draft-marker literals moved to `registry.py`
  (`DRAFT_INFERRED_MARKER`/`DRAFT_SUGGESTED_MARKER`); `canonicalize.py`
  aliases them (identity-asserted in tests). `GUARD_PROVIDER_GATE_FILES`
  literal-syncs against `bin/cli.js` via a test.
- `--min-maturity` (int or level name) exits 5 with precedence
  security > gaps > maturity > semantic > conflicts in both single-repo and
  batch paths; default exit semantics unchanged; `--no-maturity` mirrors the
  `--no-gaps` pop contract; SARIF carries no maturity results.
- Pre-PR adversarial review (4 lenses, per-finding verification) confirmed
  five defects, all fixed and test-pinned: batch-column suppression asymmetry,
  missing `has_agents` gate on M3/M5 (hard-failing remedy), comment-line CI
  probe false positive, A2 evidence hardcoding `.yaml`, and README.zh-CN
  translating the level names the tool prints in English.
- Final local evidence: 23-test `MaturityTests` + updated batch-precedence
  unit test; `tests/test_scan.py` 202/202; `npm run check` lint + 923 Python /
  51 Node tests green (`check:package` verified with CI-supported npm 10.9.8);
  `check_readme_sync.py` seven aligned; `gen_adapters.py --check` unchanged;
  gated self-checkup scan exit 0; strict drift 100/A. Self-scan reports this
  repository at Level 2 (Canonicalized), next rung the maintenance-contract
  block — an honest deficit, not a false positive.
- PR #302 head passed all nine required contexts with zero unresolved
  threads and was squash-merged as `3da9a77`; the implementation branch was
  deleted.

## Why this matters

Scan today answers "what is wrong with the harness files you have" (security,
semantic, conflicts, overlaps) and, narrowly, "which mandatory files are
missing" (G1–G4). It never answers the adoption question users actually ask:
**"what is still missing before this repository is genuinely harnessed, and
what do I do next?"** The four-phase doctrine (Checkup → Treat → Follow-up →
Efficacy) already defines the answer as a ladder — a repo with a canonical
`AGENTS.md` is further along than one with scattered tool files; one whose CI
defends that file is further along still; one with eval evidence is at the top
— but no report surfaces where a repo stands on that ladder or what the next
rung requires.

The raw signals all exist: the instruction-file inventory, G1–G4, and
`project_snapshot`'s facts. What's missing is one deterministic view that
assembles them into "you are at Level N; Level N+1 needs X and Y; run Z". That
view also gives batch scans an adoption metric that today's flat gap count
cannot express (a repo missing one section and a repo with no guidance at all
both just show "gaps").

**Precedent this plan must respect, not reverse**: G5–G8 (pre-commit hook,
maintenance contract, MCP config, permission config) were deliberately demoted
from gap findings to `project_snapshot` facts because they are "stack-dependent
judgement calls rather than mandatory infrastructure" (scan.py:195-201,
1715-1719; enforced by tests/test_scan.py:2744-2747). The maturity ladder is
designed around that line, in two ways. First, level membership is
*definitional, not normative*: "Guarded" is defined by the artifacts
`guard --apply` installs, and the report states which level a repo is at — it
never emits a severity, never fails the default exit code, and never claims a
repo *must* climb. Second, every stack-dependent signal (MCP, permissions,
local hooks, debt baselines) appears only in a clearly labeled advisory list
that can never gate a level. The maintenance-contract and CI-guard signals do
appear as level criteria — but as the *definition of the Guarded rung*, without
severity or default exit impact, which is a different contract from the retired
"always-WARN gap" shape that G5–G8 rightly abandoned.

## Current state

- `find_gaps()` (scan.py:1638-1731) emits flat findings G1–G4/G9/G10; only G1
  is ERROR; `--fail-on-gaps` (exit 3) therefore effectively gates only
  "AGENTS.md exists".
- `build_project_snapshot()` (scan.py:337-348) reports facts (tech stack,
  ci/hooks/lint/typecheck file groups, drift-guard hook, agents sections,
  maintenance contract, MCP tools, permissions) with zero verdicts.
- Three scoring systems already exist (drift 0–100/A–F, eval 0–100/A–F, and
  none for gaps); a fourth numeric grade would compound the ambiguity, so this
  plan introduces **levels, not scores**.
- "Readiness" is a taken term (`canonical_readiness_findings`,
  canonicalize.py:775 — the narrow pre-mutation gate for `stubs --apply`), so
  this feature is named **maturity** everywhere.
- Draft markers `(inferred — confirm)` / `(suggested default)` live only in
  canonicalize.py (308-310), which imports scan.py — scan cannot import them
  back without a cycle.
- Exit codes 2/3/4/7/8/9 are taken; 5 and 6 are free (verified at `a6f6932`).

## Target contract

1. **Report section.** `scan_repo()` adds `report["maturity"]` computed by a
   new `compute_maturity(...)` in scan.py. Shape:

   ```json
   {
     "level": 2,
     "level_name": "Canonicalized",
     "max_level": 4,
     "levels": [
       {"level": 1, "name": "Inventoried", "achieved": true,
        "items": [{"id": "M1", "label": "...", "status": "present",
                    "evidence": "CLAUDE.md", "remedy": null}]}
     ],
     "next": {"level": 3, "name": "Guarded",
              "missing": [{"id": "M6", "label": "...",
                            "remedy": "npx ai-harness-doctor guard . --apply"}]},
     "advisory": [{"id": "A4", "label": "...", "status": "absent",
                    "note": "stack-dependent; informational only"}]
   }
   ```

2. **Levels** (0 implicit): 0 Ungoverned → 1 Inventoried → 2 Canonicalized →
   3 Guarded → 4 Evidenced, mirroring the four phases. `level` = highest N such
   that every required item of every level ≤ N is `present`. Cumulative: a repo
   with guard CI but no AGENTS.md is Level 1, not Level 3.

3. **Required items** (all stack-independent, all deterministic):
   - **M1 (L1)**: at least one recognized agent-instruction file anywhere,
     per the same instruction-file classification the existing inventory uses.
   - **M2 (L2)**: root `AGENTS.md` exists (same signal as G1).
   - **M3 (L2)**: every `required_sections()` heading present (same as G2).
   - **M4 (L2)**: neither canonicalize draft marker appears in AGENTS.md.
   - **M5 (L2)**: every *present* canonicalizable stub is a minimal pointer
     (same signal as G3; absent stubs never count against).
   - **M6 (L3)**: a drift gate is wired into CI: `.github/workflows/`
     `harness-drift.yml` exists, or another provider's guard file installed by
     `guard --apply` exists (GitLab/codebase targets, constants mirrored from
     bin/cli.js's installer with a literal-sync test), or a snapshot ci-group
     file contains a line invoking `ai-harness-doctor` with `drift`/`scan`, the
     composite Action (`uses: ...ai-harness-doctor@`), or `check_drift.py`.
   - **M7 (L3)**: AGENTS.md carries the maintenance-contract phrase (the
     existing snapshot bool).
   - **M8 (L4)**: a ci-group file contains a line invoking `ai-harness-doctor`
     with `eval`, or `eval_run.py`.

4. **Advisory items** (never level-gating, labeled "stack-dependent —
   informational only" in every output): A1 weekly checkup workflow
   (`harness-checkup.yml`); A2 local pre-commit guard (`.pre-commit-config.yaml`
   referencing `ai-harness-doctor`, or the snapshot `drift_guard_hook`, with
   the non-clone-durable `.git/hooks` variant labeled as such); A3 committed
   debt baselines (`.ai-harness-doctor/scan-baseline.json` /
   `drift-baseline.json`); A4 project MCP config (snapshot `mcp_tools`); A5
   committed permission policy (snapshot `has_permissions`).

5. **No signal duplication.** Extract the G1/G2/G3/G4 predicates into small
   pure helpers returning raw signals, consumed by BOTH `find_gaps()` and
   `compute_maturity()`, so the two can never drift (TD-04) and maturity stays
   independent of `--no-gaps` and baseline suppression. CI-content probes are
   line-level regex over bounded reads (`ctx`/facts containment primitives) of
   snapshot ci-group files only — no new repo walk, no YAML parsing.

6. **Draft markers move to registry.py** as shared constants
   (`DRAFT_INFERRED_MARKER`, `DRAFT_SUGGESTED_MARKER`); canonicalize.py keeps
   its existing names as aliases. Constants only — no engine logic moves.

7. **Remedies** name only packaged CLI commands (`scan`, `plan`, `validate`,
   `stubs`, `guard --apply`, `eval`) — never generated file content, per the
   deterministic-mechanics constraint.

8. **Rendering.** `render_maturity(lines, maturity)` in scan_render.py, called
   from `render_markdown` between the gaps and custom sections, gated on key
   presence like every optional section. Shows the current level line, the
   per-level checklist with evidence, a "Next: to reach Level N" remedy list,
   and the advisory list under its stack-dependent disclaimer.

9. **Flags.** `--no-maturity` pops the key via `_apply_section_flags` (mirror
   `--no-gaps`). `--min-maturity N` (integer 1–4 or level name,
   case-insensitive) exits `MATURITY_GATE_EXIT = 5` when the computed level is
   lower; precedence becomes security > gaps > maturity > semantic > conflicts,
   and the precedence comment plus SKILL.md/README exit-code docs are updated.
   Without the flag, exit behavior is unchanged for every existing invocation.

10. **Scope of computation.** Root repo reports and `--repos-file` batch rows
    get maturity (batch table gains one "Maturity" column, e.g. `2/4`);
    monorepo *package* sub-reports do NOT (guard/eval CI is a repo-level
    concept; a package-level ladder would cap at L2 and mislead). Package
    tables are unchanged.

11. **Out of the findings pipeline.** Maturity is a status report, not
    findings: it emits no SARIF results, is never baseline-eligible, and does
    not join PR review output. Documented in SKILL.md.

12. Python 3.9 stdlib only; ruff (E/F/I, py39) clean; no new dependencies.

## Scope

**In scope**:

- `scripts/scan.py`: level/item tables, signal-helper extraction,
  `compute_maturity`, report wiring, `--no-maturity`, `--min-maturity`,
  exit code 5, precedence comment, batch summary column data.
- `scripts/scan_render.py`: `render_maturity`, batch table column.
- `scripts/registry.py` + `scripts/canonicalize.py`: draft-marker constant
  relocation (aliases preserved).
- `tests/test_scan.py`: new maturity test class (see Test plan) plus a
  literal-sync test tying the provider guard-file constants to bin/cli.js.
- Seven READMEs ("What it checks" gains a Maturity row, structural parity per
  check_readme_sync.py) and `SKILL.md` (Phase 0 Outputs/Actions + flag docs +
  exit codes).
- Plan/index closeout evidence.

**Out of scope**:

- Any new subcommand, MCP tool, Action command, slash command, or adapter
  (scan's existing surfaces carry the section end-to-end).
- SARIF, baselines, and pr_review integration for maturity.
- A numeric maturity score or letter grade (levels only, by design).
- Monorepo package-level ladders and nested-AGENTS.md coverage ratios
  (future candidate, noted in Maintenance notes).
- `AGENTS.md` of this repository (its scan.py summary line already elides
  same-tier sections like gaps/semantic; leaving it untouched avoids the
  self-eval byte cascade for zero information loss).
- Emitting maturity from `check_drift.py` (Phase 2 stays drift-focused).
- Releasing (lands as `feat`; version bump follows RELEASING.md as minor).

## Commands

| Purpose | Command | Expected |
|---|---|---|
| Focused maturity tests | `PYTHONPATH=tests python3 -m unittest test_scan.MaturityTests -v` | pass |
| Full scan tests | `python3 -m unittest discover -s tests -p 'test_scan.py' -v` | pass |
| Full gate | `npm run check` with CI-supported npm | pass |
| Scan self-checkup | gated baseline scan command from `AGENTS.md` | exit 0 |
| Drift | `python3 scripts/check_drift.py . --strict` | 100/A |
| Docs | `python3 scripts/check_readme_sync.py` | seven aligned |
| Adapters | `python3 scripts/gen_adapters.py --check` | unchanged |
| Audit | npm 10.8.2, public registry, high level | zero high/critical |

## Git workflow

- Plan-only PR first.
- Implementation branch: `feat/069-report-harness-maturity`.
- Commit: `feat(scan): report the harness maturity ladder`.
- Backward-compatible feature; default CLI/exit behavior unchanged.
- Merge only after all nine required contexts and zero unresolved threads;
  squash and delete branch.
- Separate green closeout PR afterward.

## Steps

### Step 1: Red tracer tests for the ladder core

Write `MaturityTests` fixtures-by-tempdir covering the spine first: empty repo
→ level 0; lone root `CLAUDE.md` → level 1; full canonical harness (reuse the
`test_gaps_clean_when_harness_complete` construction) → level ≥ 2. Assert the
report key exists, `level_name` matches, and `next.missing` lists the exact
blocking items with remedies.

**Pre-fix expected**: KeyError on `report["maturity"]`.

### Step 2: Signal helpers + compute_maturity

Extract the G1–G4 predicates into shared signal helpers (no behavior change to
`find_gaps` — its findings must stay byte-identical, proven by existing tests).
Implement the level/item tables, `compute_maturity`, the three new bounded
probes (draft markers via registry constants; pre-commit-config reference; CI
line-level invocation regex), and report wiring. Cumulative-level and
advisory-never-gates semantics per the contract.

### Step 3: Guard/eval detection breadth

Cover M6's disjuncts (shipped workflow file, GitLab/codebase provider files
with the bin/cli.js literal-sync test, `ai-harness-doctor drift` line, Action
`uses:` line, `check_drift.py` line) and M8's (`… eval` line, `eval_run.py`),
plus negative cases: a workflow merely *installing* the package, `scan`-only
wiring not counting for M8, markers inside unrelated files not in the ci group.

### Step 4: Rendering, flags, and batch column

`render_maturity` with the advisory disclaimer; `--no-maturity` pop;
`--min-maturity` parse (int or name) with exit 5 and precedence placement;
`--repos-file` table column. Black-box CLI tests via the existing `run_json`
subprocess pattern: default exit unchanged on a gappy repo; `--min-maturity
guarded` exits 5 on a Level-2 repo and 0 on a Level-3 repo; `--json` carries
the section; `--no-maturity` removes it; SARIF output contains no maturity
results.

### Step 5: Docs

SKILL.md Phase 0: maturity in Outputs, both flags in Actions with fenced
examples, exit-code list gains 5. README "What it checks" gains the Maturity
row — mirrored structurally across all seven languages, prose translated.
Verify `check_readme_sync.py` passes.

### Step 6: Review, gate, PR, closeout

Run all commands. Standards/Spec review with explicit attention to the G5–G8
precedent framing and FP-aversion (generous crediting is acceptable; wrongful
flagging is not). Open the implementation PR, wait for nine green checks,
merge and delete, then record evidence in a separately green closeout PR.

## Test plan

- Level spine: empty → 0; any single tool file (root and nested variants) → 1;
  canonical-complete → 2; +guard workflow / +provider file / +invocation line /
  +maintenance contract → 3; +eval CI line → 4.
- Cumulative gating: guard CI without AGENTS.md stays level 1; eval CI without
  guard stays level 2.
- Each M-item individually toggles: missing section, draft marker present,
  oversized stub, contract phrase absent — each pins `next.missing` content
  and remedy strings.
- Advisory: MCP/permissions/baselines/pre-commit present or absent never
  changes `level`; statuses and labels asserted.
- Probes bounded and contained: symlinked/escaping ci files are ignored via
  facts primitives; oversized workflow reads truncate without crash.
- find_gaps regression: gap findings byte-identical before/after the helper
  extraction (existing gap tests must pass untouched).
- Flags: `--min-maturity` name and integer forms, invalid value → argparse
  error 2 (usage), gate exit 5, precedence vs `--fail-on-security` (security
  wins), `--no-maturity`, `--json`, SARIF absence, batch column presence.
- Draft-marker aliasing: canonicalize behavior unchanged (existing validate
  tests), registry constants equal the historical literals.
- Ruff/py39 compliance via the lint gate.

## Done criteria

- [ ] `report["maturity"]` present with contract shape; levels cumulative;
      advisory never gates.
- [ ] Default exit codes and `find_gaps` output unchanged for every existing
      invocation.
- [ ] `--min-maturity` gates at exit 5 with documented precedence.
- [ ] No maturity output in SARIF, baselines, or PR review.
- [ ] Batch table shows the Maturity column; package tables unchanged.
- [ ] Guard-provider constants literal-match bin/cli.js (sync test).
- [ ] Seven READMEs + SKILL.md updated and `check_readme_sync.py` green.
- [ ] Full gates, self-checkup, strict drift 100/A, adapters check, audit
      clean.
- [ ] Implementation and closeout PRs each pass nine checks, merge, and delete
      branches.

## STOP conditions

Stop if:

- Correct level computation would require LLM judgment, network access, YAML
  parsing of workflows, or a new repository walk.
- The signal-helper extraction cannot keep `find_gaps` findings byte-identical.
- Any stack-dependent signal ends up level-gating, or the feature cannot be
  expressed without re-emitting G5–G8-shaped findings.
- `--min-maturity` cannot be added without changing default exit behavior.
- README structural parity cannot be maintained across all seven languages.
- The repository's own gated self-checkup or strict drift regresses.

## Maintenance notes

- Future candidates deliberately excluded: monorepo package ladders and
  nested-AGENTS.md coverage ratios; a `--min-maturity` mode for the GitHub
  Action; surfacing maturity deltas in `pr_review.py`; accepting
  provider-specific eval gates beyond line-regex detection.
- Any new guard install target in bin/cli.js must be mirrored into the
  provider-file constants (the literal-sync test enforces this).
- If a future plan adds new required items, they must join an existing level
  or a new top rung — never retroactively tighten a lower level, so published
  level claims stay stable.
