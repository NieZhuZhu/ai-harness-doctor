# Plan 047: Make repaired baseline debt visible, checkable, and prunable

> **Drift check**:
>
> ```bash
> git diff --stat 836ac78..HEAD -- \
>   scripts/scan.py scripts/scan_render.py scripts/check_drift.py \
>   tests/test_scan.py tests/test_check_drift.py \
>   README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md
> ```
>
> Follow every verification command and STOP condition.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: MED
- **Depends on**: Plans 007, 021 (DONE)
- **Category**: feature (baseline lifecycle / debt governance)
- **Planned at**: commit `836ac78`, 2026-07-16
- **Implementation**: TODO

## Why this matters

The doctor deliberately uses committed baselines rather than opaque ignore
rules: existing gap/semantic/conflict/drift debt stays visible while CI fails
only on new findings. That is a strong adoption contract, but the lifecycle is
only half implemented.

When a baselined problem is fixed, its entry remains in the baseline file.
Current scan/drift output shows only entries that still match; repaired entries
disappear entirely. Maintainers cannot distinguish:

- known debt still present;
- newly introduced active findings;
- resolved baseline debt that should be deleted.

Docs say “shrink the file as debt is repaired,” but the tool cannot identify or
remove the stale entries. Over time the debt register accumulates dead
suppression state, hides progress, and creates review noise. Mature baseline
systems present new / unchanged / resolved problems and support deterministic
refresh.

## Mechanical reproduction

For either scan or drift:

1. create a real finding;
2. `--write-baseline`;
3. repair the finding;
4. run with `--baseline ... --json`.

Observed today:

- active findings: empty;
- `baselined`: empty;
- stale baseline entry: absent from every report;
- no command can fail CI on stale debt or prune only repaired entries.

## Target contract

Both `scan` and `drift` gain the same lifecycle semantics while retaining their
existing version-1 baseline schemas.

1. Normal `--baseline FILE` output:
   - active/new findings remain in existing finding arrays;
   - still-present known debt remains in `baselined`;
   - baseline entries not matched by current findings appear in a deterministic
     top-level `resolved_baseline` array;
   - baseline metadata includes known/resolved counts.
2. Markdown output names resolved debt and recommends pruning; JSON is complete.
   Resolved entries do not enter SARIF, gates, scores, or PR active findings.
3. `--check-baseline` requires `--baseline FILE` and exits with one shared,
   documented maintenance exit code when `resolved_baseline` is non-empty.
   Active finding gate precedence remains unchanged.
4. `--prune-baseline` requires `--baseline FILE`, removes only resolved entries,
   rewrites the same schema deterministically, and exits 0.
   - It MUST NOT add new findings to the baseline.
   - It MUST NOT change still-matching entries.
5. Missing/malformed baseline:
   - ordinary `--baseline` keeps current fail-safe behavior (suppresses
     nothing);
   - explicit check/prune is maintenance mutation and must fail closed without
     writing.
6. Scan security findings remain ineligible. `--repos-file` remains incompatible
   with all baseline modes.
7. Node/Python dependencies unchanged; Python 3.9 stdlib only.

## Design

### Preserve baseline entries, not only fingerprints

Today both loaders discard entry payloads and return only fingerprint sets.
Introduce a small parsed baseline object per engine:

- validated version/schema state;
- canonical ordered entries;
- fingerprint → entry map.

Do not merge the scan/drift persisted schemas: scan entries contain
family/rule/package/structured values; drift entries contain check/message/path.
Share CLI wording/exit semantics, not an artificial common file format.

### Classification

Before suppression, compute the set/map of current baseline-eligible
fingerprints. Then:

- known = current ∩ baseline;
- new = current − baseline;
- resolved = baseline − current.

For scan, classification includes root and monorepo package reports. For drift,
classification includes built-in D1–D4/D6–D8 findings after scope attribution
and strict severity promotion; custom plugins stay outside the built-in
baseline schema unless already supported.

### Prune is subtractive

Write `baseline entries ∩ current fingerprints`. Never regenerate from the
whole current report because that would silently baseline newly introduced
debt. Use atomic write semantics if an existing contained helper is available;
otherwise write a same-directory temp file and `os.replace`.

## Scope

**In scope**:

- `scripts/scan.py`, `scripts/scan_render.py`
- `scripts/check_drift.py`
- `tests/test_scan.py`, `tests/test_check_drift.py`
- trilingual READMEs, `SKILL.md`
- `AGENTS.md` only in the final three-round consolidation
- plan/index updates

**Out of scope**:

- General ignore/config language or per-rule disables.
- Baseline schema version 2 or timestamps.
- Security suppression.
- Auto-baselining new findings.
- Eval baseline-history changes.

## Steps

### Step 1: Characterize stale debt

Add scan + drift tests for:

- one finding written, then repaired → `resolved_baseline` contains exact
  persisted entry;
- mixed state: one known, one resolved, one new;
- line-number shifts remain known, not resolved;
- monorepo package attribution survives.

### Step 2: Retain parsed baseline entries and classify lifecycle

Refactor each loader to retain canonical entries plus fingerprints while
preserving ordinary missing/malformed fail-safe behavior. Add
`resolved_baseline` and metadata to JSON and Markdown.

### Step 3: Add `--check-baseline`

Choose one unused exit code (same in scan/drift), document it, and preserve
existing active-gate precedence. Require `--baseline`; reject incompatible
`--write-baseline`, `--prune-baseline`, and scan `--repos-file` combinations.

### Step 4: Add deterministic `--prune-baseline`

Subtract only resolved entries and rewrite atomically. Tests must prove:

- new active findings are never added;
- still-known entries are byte/canonical-shape compatible;
- second prune is idempotent;
- malformed/missing baseline is unchanged and exits non-zero;
- no security-shaped scan entry becomes eligible.

### Step 5: Docs and gates

Update all three READMEs and `SKILL.md` with new/known/resolved semantics,
commands, and exit code.

```bash
python3 -m unittest discover -s tests -p 'test_scan.py' -v
python3 -m unittest discover -s tests -p 'test_check_drift.py' -v
npm run check
python3 scripts/check_readme_sync.py
python3 scripts/gen_adapters.py --check
python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json \
  --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts
python3 scripts/check_drift.py . --strict
```

Open one feature PR, wait for all nine required contexts, then squash-merge.
This is a backward-compatible **minor** feature.

## Done criteria

- [ ] Scan/drift reports distinguish new, known, and resolved baseline debt.
- [ ] Markdown/JSON surface resolved entries; SARIF/gates/scores do not.
- [ ] Shared maintenance exit code is documented and tested.
- [ ] Prune is subtractive, deterministic, atomic, idempotent.
- [ ] Missing/malformed check/prune fails closed without writes.
- [ ] New findings and security findings are never auto-baselined.
- [ ] Full local and nine-context CI gates pass; PR merged.

## STOP conditions

Stop if:

- implementation requires changing existing baseline schemas;
- prune cannot be proven subtractive;
- malformed maintenance operations would write or suppress findings;
- check-baseline would override existing security/gap/semantic/conflict/drift
  gate precedence;
- any required CI context is red/pending.

## Maintenance notes

- Baselines are debt registers, not ignore lists. Any new baseline feature must
  preserve new/known/resolved classification and subtractive pruning.
- If future custom plugin baselines are desired, design their identity/schema
  separately; do not silently fold arbitrary plugin records into version 1.
