# Plan 061: Restore AGENTS.md progressive-disclosure headroom

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md` unless a reviewer maintains the index separately.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 8034dc4..HEAD -- \
>   AGENTS.md references/maintenance-contract.md scripts/check_drift.py \
>   tests/test_action_metadata.py \
>   benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json \
>   benchmark/self-eval/results-after-graded.json benchmark/self-eval/README.md \
>   plans/061-restore-agents-progressive-disclosure-headroom.md plans/README.md
> ```
>
> If any in-scope file changed, compare the "Current state" excerpts against
> live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW–MEDIUM (docs-only bytes, but the file is evidence-bound and
  guards this repository's own strict gate)
- **Depends on**: Plan 058 (DONE — `npm run check` now includes the packed
  candidate; its AGENTS invariant must survive compaction)
- **Category**: docs / repository contract / maintenance headroom
- **Planned at**: commit `8034dc4`, 2026-07-18
- **Status**: TODO

## Why this matters

The root `AGENTS.md` is 12,231 bytes. The repository's own drift guard,
`scripts/check_drift.py`, emits a D4 NOTICE the moment `AGENTS.md` exceeds
`12 * 1024` = 12,288 bytes, and `--strict` — which the repository's required
drift CI context and self-checkup run — promotes every NOTICE to a blocking
ERROR. That leaves **57 bytes** of headroom before the repository's own
required gate goes red.

This is not hypothetical: mechanically appending one harmless 65-byte HTML
comment (see reproduction below) makes `python3 scripts/check_drift.py .
--strict` exit 1 with a D4 finding and drops the health score from 100/A to
85/B. Any future plan that needs to record one new stable invariant in
`AGENTS.md` — exactly what Plans 017/027/029/032/035/058 each did — is blocked
or forced into ad-hoc same-PR wordsmithing under pressure.

The standing mitigation ("every plan that touches `AGENTS.md` re-checks
`wc -c` and relocates prose when needed", recorded in the plans index) has
demonstrably failed to preserve headroom: Plan 058's closeout landed at 12,231
bytes, 57 bytes under the threshold. The repository needs a *repository-owned*
budget that is deliberately lower than the product's D4 threshold, enforced by
a deterministic test, so headroom is a maintained contract instead of a
leftover.

The fix is the product's own prescription — the D4 suggestion literally says
"Move details to references/ and keep AGENTS.md concise" and "Consider
progressive disclosure" — applied to this repository: compact root bullets
whose detailed mechanics are already owned by
`references/maintenance-contract.md` into one-line actionable summaries with
links, and enforce `AGENTS.md <= 10 * 1024` bytes going forward. The product
D4 thresholds are **not** touched.

## Mechanical reproduction

All excerpts re-verified live at `8034dc4` on 2026-07-18.

Current size and headroom:

```console
$ wc -c AGENTS.md
   12231 AGENTS.md
$ python3 -c "print(12*1024 - 12231)"
57
```

`scripts/check_drift.py:346-377` (`d4_size`) — hard ERROR above `--max-bytes`
(default 32,768 per `DEFAULT_MAX_BYTES`, line 21), NOTICE above the hardcoded
`12 * 1024`:

```python
def d4_size(root, max_bytes):
    ...
    size = len(data)
    if size > max_bytes:
        return [
            {
                "check": "D4",
                "level": "ERROR",
                "message": f"AGENTS.md is {size} bytes, above {max_bytes}",
                "suggestion": "Move details to references/ and keep AGENTS.md concise.",
            }
        ]
    if size > 12 * 1024:
        return [
            {
                "check": "D4",
                "level": "NOTICE",
                "message": f"AGENTS.md is {size} bytes; context bloat risk",
                "suggestion": "Consider progressive disclosure.",
            }
        ]
    return []
```

`scripts/check_drift.py:806-811` — strict promotes the NOTICE to a blocking
ERROR:

```python
    findings.extend(d4_size(root, max_bytes))
    findings.extend(d8_competing_lockfiles(root))
    if strict:
        for f in findings:
            if f.get("level") == "NOTICE":
                f["level"] = "ERROR"
```

Reproduction (performed in a throwaway copy of the repo; the working tree was
not modified):

```console
$ printf '\n<!-- note: keep this file in sync with references documents -->\n' >> AGENTS.md
$ wc -c AGENTS.md
   12296 AGENTS.md
$ python3 scripts/check_drift.py . --strict; echo "exit=$?"
...
## D4
- **[ERROR]** AGENTS.md is 12296 bytes; context bloat risk
...
Score: 85/100 (grade B)
exit=1
```

Restored current `main` is clean:

```console
$ python3 scripts/check_drift.py . --strict; echo "exit=$?"
Score: 100/100 (grade A)
exit=0
```

Current self-eval evidence is green and byte-bound to the current file:
`benchmark/self-eval/results-after-graded.json` records
`health: 100/A, passed 39/39` and binds
`AGENTS.md sha256 df8459b607630c3873908bc2fa372a9dd31286929889f8690270a9009cfb62f5`
(verified equal to `shasum -a 256 AGENTS.md` at `8034dc4`). Any byte change to
`AGENTS.md` therefore requires an honest manual-protocol answer refresh,
regrade, and score run.

## Current state

### Measured section budget of the root file

Per-section byte counts at `8034dc4` (heading line included; total 12,231):

| Section | Bytes |
|---|---:|
| Project overview | 199 |
| Project structure | 2,051 |
| Build & test | 175 |
| Conventions | 5,302 |
| Testing requirements | 436 |
| Safety | 1,014 |
| Operational workflows | 1,648 |
| Commit & PR | 1,406 |

### The root file already routes to the maintenance contract

`AGENTS.md` links `references/maintenance-contract.md` from six bullets
(lines 46, 47, 48, 55, 57, 73, plus line 100 in Commit & PR), and
`references/maintenance-contract.md` (4,773 bytes) already owns the detailed
sections `## Baseline lifecycle`, `## SARIF and Marketplace Action`,
`## GitHub guard and feedback`, `## CI, release, and repository operations`,
and `## Installer recovery`. Its own preamble states the intended split:

```markdown
Progressive-disclosure details for repository maintainers. The root
`AGENTS.md` retains the invariants agents need on every turn; use this reference
when changing GitHub integration, baselines, CI, release, or installer state.
```

The split, however, is incomplete: several root bullets restate the contract's
detailed mechanics instead of summarizing and linking.

### Duplicated clusters (measured, line-accurate at `8034dc4`)

These five clusters total **2,870 bytes** of root text whose detailed content
is either already owned by a `references/maintenance-contract.md` section or
repeated verbatim-in-substance inside `AGENTS.md` itself. The required
reduction to reach the target budget is 12,231 − 10,240 = **1,991 bytes**, so
compacting these clusters to one-line summaries with links reaches the budget
without deleting any invariant.

- **C1 — Baseline lifecycle** (259 B): `AGENTS.md:46` restates HIGH-security
  ineligibility, line-independent identity, new/known/resolved classification,
  exit 9, and prune semantics, all owned by contract `## Baseline lifecycle`
  (lines 9–21). The bullet already ends with "See
  `references/maintenance-contract.md`."
- **C2 — SARIF/Action mechanics** (463 B): `AGENTS.md:47` and `AGENTS.md:100`
  restate fingerprints/categories, `findings > maintenance > ok` precedence,
  exact exits, `action-run.js`/`action-report.js` ownership, real `uses: ./`
  tests, and actionlint, owned by contract `## SARIF and Marketplace Action`
  (lines 25–44).
- **C3 — Guard/PR feedback/weekly issue** (445 B): `AGENTS.md:48`, `:55`, and
  `:101` restate owned-marker/batch/host-path rules, guard-copy sync, and the
  weekly exact-title issue lifecycle, owned by contract
  `## GitHub guard and feedback` (lines 48–59).
- **C4 — CI/release/repository operations** (972 B): `AGENTS.md:57`–`:61`
  restate locked `npm ci --ignore-scripts` installs (stated twice, lines 57
  and 58), matrix coverage, release-rerun `gitHead`/shasum identity, and the
  admin-bypass rule (stated twice, lines 57 and 61), owned by contract
  `## CI, release, and repository operations` (lines 63–78).
- **C5 — Installer recovery and isolated HOME** (731 B): the isolated-`HOME`
  rule is stated three times (`AGENTS.md:62` in Conventions, `:68` in Testing
  requirements, `:72` in Safety), and `:73`–`:74` restate the
  lock/journal/atomic-manifest recovery mechanics owned by contract
  `## Installer recovery` (lines 82–90).

### The self-eval pack answers from the root file

`benchmark/self-eval/tasks.json` holds exactly 39 tasks with deterministic
regex checks; the recorded protocol
(`benchmark/self-eval/results-after.json` `note`) answers "using only the
current AGENTS.md, with no repository browsing or external model call". Every
compaction therefore has a hard semantic floor: each of the 39 answers must
still be derivable from the post-compaction root file. The full ID checklist
is in "Semantic-invariant checklist" below.

### Where the repository-contract test belongs

`tests/test_action_metadata.py` already owns the deterministic repository
maintenance metadata contracts (workflow pins, guard copies, required steps,
`--evidence AGENTS.md` in the drift workflow, Dependabot, community files).
The new AGENTS budget/routing/relocation assertions belong there — a byte-only
assertion in isolation is explicitly insufficient.

## Target contract

All measurable; all must hold at implementation-PR merge time:

1. `wc -c AGENTS.md` ≤ **10,240** bytes (`10 * 1024`).
2. Strict-D4 headroom ≥ **2,048** bytes (implied by 1: 12,288 − 10,240).
3. `benchmark/self-eval`: all existing **39** task IDs still pass under the
   documented manual protocol against the post-compaction `AGENTS.md`;
   regraded and scored **39/39, 100/Grade A** with refreshed current evidence
   hashes (`--require-current-evidence` green).
4. **No stable invariant lost**: every detail removed from the root file maps
   to either (a) a retained one-line root summary or (b) a line in
   `references/maintenance-contract.md`. The implementation PR description
   must include this mapping (cluster → destination).
5. Detailed maintenance mechanics remain reachable: the root file keeps
   routing links to `references/maintenance-contract.md`, and the contract
   file contains every relocated detail.
6. A new deterministic repository-contract test (preferred home:
   `tests/test_action_metadata.py`) asserts, at minimum:
   - `AGENTS.md` byte size ≤ `10 * 1024`;
   - the root file retains its required section headings (`# Project
     overview`, `# Project structure`, `# Build & test`, `# Conventions`,
     `# Testing requirements`, `# Safety`, `# Operational workflows`,
     `# Commit & PR`) and at least one routing reference to
     `references/maintenance-contract.md`;
   - `references/maintenance-contract.md` retains the five detail-owning
     section headings (`## Baseline lifecycle`, `## SARIF and Marketplace
     Action`, `## GitHub guard and feedback`, `## CI, release, and repository
     operations`, `## Installer recovery`) plus representative relocated
     tokens chosen during implementation (e.g. the exit-9 baseline check, the
     `gitHead`/shasum rerun identity, the isolated-`HOME` rule).
   A byte-only test is insufficient and is a STOP-level review defect.
7. Product behavior unchanged: `scripts/check_drift.py` D4 thresholds,
   NOTICE/strict semantics, and `DEFAULT_MAX_BYTES` are byte-identical.
8. `python3 scripts/check_drift.py . --strict` scores 100/Grade A; the scan
   baseline gate and `npm run check` (lint → tests → packed candidate, per
   Plan 058) are green.
9. No public runtime/CLI behavior change, no package manifest/inventory
   change, no README/SKILL change: `README*` translations, `SKILL.md`,
   `assets/` templates, the `package.json` `files` list, and the packed
   tarball's file inventory are untouched. Because
   `references/maintenance-contract.md` sits inside the shipped `references/`
   directory, its prose — and therefore the packed tarball bytes — may
   change; that is expected and in scope. The packed-candidate verification
   in `npm run check` (Plan 058) must still pass on the changed contents.

## RED test design

Write the repository-contract test **first**, against the current tree:

- the byte-budget assertion must FAIL on the current 12,231-byte `AGENTS.md`
  (12,231 > 10,240) — this is the RED state proving the test bites;
- the section-heading, routing-link, and contract-section assertions must PASS
  on the current tree (they hold today and must keep holding);
- the relocated-token assertions may be written to PASS against the current
  `references/maintenance-contract.md` where the detail already exists there,
  and extended in the same commit as any detail newly moved into the contract.

Only after recording the RED run does compaction begin. GREEN is reached by
shrinking `AGENTS.md`, never by raising the budget.

## Design

Progressive disclosure with an explicit mapping, not blind deletion:

1. For each cluster C1–C5, rewrite the root bullet(s) into a single actionable
   summary line that names the invariant and links
   `references/maintenance-contract.md` for mechanics. Example shape (final
   wording is the implementer's, subject to the semantic checklist):
   *"Baselines are reviewed debt registers — HIGH security ineligible,
   line-independent identity, exit-9 repaired-entry check; lifecycle details in
   `references/maintenance-contract.md`."*
2. Collapse intra-file repetition: state the isolated-`HOME` rule once in
   Safety and reference it from Testing requirements; state the admin-bypass
   and locked-lint-install rules once.
3. If any root detail slated for removal is NOT yet present in
   `references/maintenance-contract.md`, add it to the matching contract
   section in the same commit before removing it from the root. The contract
   file has no size gate (it is not `AGENTS.md`), but keep additions tight.
4. Produce the removal map (old root line → retained summary / contract line)
   and paste it into the implementation PR body. Reviewers check the map, not
   a diff-eyeball.
5. Do not touch `# Project overview`, `# Build & test`, or the structure of
   `# Project structure`; they are small and load-bearing for self-eval
   answers (`test-suite`, `scan-script`, `drift-script`, `eval-script`,
   `guard-templates`, ...). Light tightening inside kept sections is allowed
   only if the checklist below stays green.
6. Refresh evidence honestly: re-answer any task whose source sentence was
   reworded, then `--regrade` and `--score` with `--evidence AGENTS.md
   --require-current-evidence`. Update the `note` fields with the refresh
   date and an accurate protocol statement: no `eval_run.py` runner/judge
   model call was performed, the answers were manually maintained during the
   implementation workflow from `AGENTS.md`, and the offline regex regrade
   is not a fresh independent model benchmark. (Since an AI executor may
   maintain the manual answers, do not claim "no external model call" in any
   broader sense.) Keep the task pack at 39 — add a task only if no existing
   task can prove retained semantics for a compacted invariant, and record
   why.

## Semantic-invariant checklist

Every one of the current 39 self-eval task IDs must remain answerable from the
post-compaction `AGENTS.md` alone (manual protocol). Check each explicitly
during Step 3:

`test-suite`, `python-version`, `python-deps`, `node-version`, `npm-deps`,
`semantic-merging`, `guard-templates`, `doc-languages`, `drift-script`,
`scan-script`, `eval-script`, `commit-convention`, `installer-state`,
`security-baseline`, `mcp-policy`, `release-classification`,
`installer-test-home`, `eval-evidence-gate`, `mcp-version-wire`,
`repository-operations`, `public-dependency-source`,
`nested-instruction-scope`, `oversize-scan-coverage`,
`release-rerun-identity`, `targeted-eval-generation`,
`fact-generator-containment`, `locked-lint-install`, `eval-task-preflight`,
`checkup-issue-lifecycle`, `batch-scan-coverage`, `stored-result-health`,
`action-success-matrix`, `structured-applicability`, `canonical-readiness`,
`gitignored-path-truth`, `nested-drift-ancestors`, `action-argv-contract`,
`deep-improve-loop`, `local-all-green`.

High-risk IDs whose source sentences sit inside compaction clusters —
re-answer these first: `security-baseline` (C1), `action-success-matrix` /
`action-argv-contract` (C2), `checkup-issue-lifecycle` (C3),
`locked-lint-install` / `public-dependency-source` /
`release-rerun-identity` / `repository-operations` /
`release-classification` (C4), `installer-test-home` / `installer-state`
(C5), `local-all-green` (Plan 058 invariant, must survive verbatim in
substance).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused metadata test | `python3 -m unittest discover -s tests -p 'test_action_metadata.py' -v` | RED on budget before compaction; all green after |
| Byte budget | `wc -c AGENTS.md` | ≤ 10240 |
| Self-eval regrade | `python3 scripts/eval_run.py --regrade benchmark/self-eval/results-after.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md -o benchmark/self-eval/results-after-graded.json` | refreshed evidence-bound output |
| Self-eval score | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | 39/39, 100/Grade A |
| Full local gate | `npm run check` | lint, tests, then packed candidate all pass |
| README/docs sync | `python3 scripts/check_readme_sync.py` | seven READMEs aligned (untouched) |
| Self scan | `python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json --check-baseline --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts --no-report-file` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | 100/100, Grade A, exit 0 |
| Full repo tests | `python3 -m unittest discover -s tests -v && npm test` | all pass |

## Scope

**In scope**:

- `AGENTS.md`
- `references/maintenance-contract.md`
- `tests/test_action_metadata.py` (or, only if review prefers, one focused
  existing maintenance-metadata suite — not a new module)
- `benchmark/self-eval/tasks.json` (only if a task must change per Design §6)
- `benchmark/self-eval/results-after.json`
- `benchmark/self-eval/results-after-graded.json`
- `benchmark/self-eval/README.md` (protocol/date note, as needed)
- `plans/061-restore-agents-progressive-disclosure-headroom.md` and
  `plans/README.md` (closeout)

**Out of scope**:

- `scripts/check_drift.py` — D4 thresholds, strict promotion, and
  `DEFAULT_MAX_BYTES` stay byte-identical.
- `README*.md` translations, `SKILL.md`, `assets/` templates, and the
  package manifest/inventory (`package.json` `files`, tarball file list) —
  no public runtime/CLI behavior changes, so `check_readme_sync` targets are
  untouched. Note: this does **not** mean all shipped package contents are
  byte-identical — `references/maintenance-contract.md` is in the shipped
  `references/` directory and is intentionally edited (see Scope in-scope
  and Target 9); the packed-candidate check must still pass.
- Deleting any stable invariant, weakening any gate, or reducing self-eval
  coverage below 39 tasks.
- Reformatting unrelated files (the formatter footgun is a separate deferred
  candidate; do not mix it in).
- Fresh `eval_run.py` runner/judge model runs — evidence refresh is the
  documented manual protocol plus offline regex regrade only. The refreshed
  artifacts must say exactly that (no runner/judge model call performed;
  answers manually maintained during the implementation workflow from
  `AGENTS.md`; offline regrade is not a fresh independent model benchmark)
  and must not claim "no external model call" in any broader sense, since an
  AI executor may maintain the manual answers.

## Git workflow

- This plan lands first as a plan-only PR and must be green on all nine
  required contexts before implementation starts.
- Implementation branch: `docs/061-agents-progressive-disclosure`.
- Commit: `docs(agents): restore progressive-disclosure headroom`.
- One focused implementation PR; do not push directly to `main`.
- Run the Standards/Spec review with real evidence on the implementation
  branch before merge; wait for all nine required checks; squash merge and
  delete the branch; then land the plans closeout.
- Release classification: repository docs/maintenance change with no public
  runtime/CLI behavior delta (the shipped maintenance-reference prose may
  change) — patch-level material if released alone.

## Steps

### Step 1: Pin the missing repository budget as a failing test (RED)

Add the repository-contract test described in "RED test design" to
`tests/test_action_metadata.py`.

**Verify**:

```bash
python3 -m unittest discover -s tests -p 'test_action_metadata.py' -v
```

Expected: RED **only** on the ≤10,240 budget assertion (current file is
12,231 bytes); heading/routing/contract-section assertions green.

### Step 2: Relocate and compact with an explicit mapping

Apply Design §1–§5 cluster by cluster (C1–C5). For each removed root detail,
record its destination (retained summary or contract line) in the mapping.
Add any not-yet-owned detail to `references/maintenance-contract.md` before
deleting it from the root.

**Verify**:

```bash
wc -c AGENTS.md   # <= 10240
python3 -m unittest discover -s tests -p 'test_action_metadata.py' -v  # all green
```

### Step 3: Walk the semantic-invariant checklist

Answer all 39 task IDs from the new `AGENTS.md` alone, high-risk IDs first.
Any unanswerable ID means the compaction went too far — restore or re-summarize
that invariant before proceeding (or STOP if the budget cannot hold).

### Step 4: Refresh evidence honestly

Update `benchmark/self-eval/results-after.json` answers/note under the manual
protocol, then regrade and score per the commands table. Record the refresh
date and the accurate protocol statement from Design §6: no `eval_run.py`
runner/judge model call performed, answers manually maintained during the
implementation workflow from `AGENTS.md`, offline regex regrade is not a
fresh independent model benchmark.

**Verify**: score output shows 39/39, 100/Grade A, current evidence.

### Step 5: Run all gates and review

```bash
npm run check
python3 scripts/check_readme_sync.py
python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json --check-baseline --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts --no-report-file
python3 scripts/check_drift.py . --strict
python3 -m unittest discover -s tests -v && npm test
```

- **Standards**: stdlib-only test, deterministic assertions, honest evidence
  refresh, no generated-file hand edits.
- **Spec**: every Target-contract item 1–9 verified, mapping table complete in
  the PR body.

Open one implementation PR, wait for all nine required contexts, squash merge,
delete the branch, then land the plans closeout.

## Test plan

- New repository-contract test: budget, required root headings, routing link,
  contract detail-section headings, representative relocated tokens.
- RED-first evidence recorded (budget assertion fails at 12,231 bytes).
- Self-eval 39/39 with refreshed `AGENTS.md` sha256 in
  `results-after-graded.json` evidence.
- Strict drift 100/A and scan baseline gates green.
- Full Python + Node suites and `npm run check` green.

## Done criteria

- [ ] `AGENTS.md` ≤ 10,240 bytes (≥ 2,048 bytes strict-D4 headroom).
- [ ] Deterministic repository-contract test in place; byte budget + section/
      routing/relocation assertions; RED-before/GREEN-after recorded.
- [ ] Removal map (cluster → destination) present in the implementation PR.
- [ ] All 39 self-eval tasks pass; evidence hashes current; 100/Grade A.
- [ ] `references/maintenance-contract.md` owns every relocated detail; root
      routing links intact.
- [ ] Product D4 code byte-identical; strict drift 100/A; scan gates green.
- [ ] `npm run check` and full test suites green; nine required CI contexts
      green on the implementation PR.
- [ ] No public README/SKILL change and no package manifest/inventory change
      (`check_readme_sync` untouched targets still aligned); the shipped
      `references/maintenance-contract.md` prose is the only package-content
      delta, and the packed-candidate check in `npm run check` passes on it.
- [ ] Self-eval artifact notes carry the accurate protocol statement from
      Design §6 (no `eval_run.py` runner/judge model call; manually
      maintained answers; offline regrade is not a fresh independent model
      benchmark).

## STOP conditions

Stop and report back if:

- any of the 39 existing self-eval tasks cannot be kept passing from the
  compacted `AGENTS.md` without deleting a stable invariant or padding the
  task pack;
- reaching ≤ 10,240 bytes would require removing an invariant that has no
  honest home in `references/maintenance-contract.md`;
- the implementation would need to alter `scripts/check_drift.py` D4
  thresholds, strict semantics, or any product behavior;
- the change would ripple into public READMEs, `SKILL.md`, the package
  manifest/inventory, or any shipped package file other than the intended
  `references/maintenance-contract.md` edits (whose prose/tarball-byte change
  is expected), or the packed-candidate check fails on the changed contents;
- the only achievable test is a byte-only size assertion (insufficient by
  contract);
- any required CI context is red or pending at merge time.

## Maintenance notes

- The repository budget (10,240) is intentionally below the product NOTICE
  threshold (12,288). Future plans adding AGENTS invariants spend headroom;
  when the budget test trips, relocate mechanics to
  `references/maintenance-contract.md` first — never raise the budget in the
  same PR that needs the space.
- Keep the removal-map discipline for any future compaction: every deleted
  detail maps to a summary or a contract line, reviewed as a table.
- The self-eval pack remains the semantic floor for this file; a compaction
  that survives the byte test but fails a task is a regression, not a
  cleanup.
