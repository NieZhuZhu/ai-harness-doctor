# Plan 048: Report baseline maintenance failures truthfully through SARIF and the Action

> **Drift check**:
>
> ```bash
> git diff --stat 775c31e..HEAD -- \
>   scripts/scan.py scripts/check_drift.py scripts/sarif.py \
>   bin/action-report.js action.yml \
>   tests/test_scan.py tests/test_check_drift.py tests/test_sarif.py \
>   bin/action-report.test.js tests/test_action_metadata.py \
>   .github/workflows/action-self-test.yml \
>   README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md
> ```

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: Plans 046 and 047 (DONE)
- **Category**: feature integration / correctness
- **Planned at**: commit `775c31e`, 2026-07-16
- **Implementation**: TODO

## Why this matters

Plan 047 adds a baseline-maintenance gate: scan/drift can exit `9` when repaired
baseline entries should be pruned. Plan 046 made the Marketplace Action report
valid non-zero findings gates through SARIF outputs and Job Summary before
restoring the CLI exit.

Without explicit integration, an exit-9 run has zero active SARIF results. The
Action helper therefore labels it `status=ok` and renders “No active findings,”
then the step fails. That is contradictory: the workflow is red but the
structured report claims health and gives no remediation.

A premium doctor must report maintenance debt as maintenance debt, not as an
active code finding and not as health.

## Mechanical reproduction

1. Create a real finding and write a baseline.
2. Repair the finding.
3. Run the Action with:

```yaml
with:
  command: scan
  args: "--baseline .ai-harness-doctor/scan-baseline.json --check-baseline"
```

After Plan 047, the CLI exits `9`, but SARIF has zero active results. Under the
Plan 046-only Action contract, outputs become:

```text
status=ok
finding-count=0
```

and the Job Summary says “No active findings.” The report omits the repaired
baseline entries that caused the failure.

## Target contract

1. SARIF producer metadata includes deterministic `resolvedBaselineCount`,
   derived from `report.resolved_baseline`. Resolved entries remain outside
   `results`; they are maintenance state, not Code Scanning alerts.
2. Action exposes `resolved-baseline-count`.
3. Action status precedence:
   - active results > 0 → `findings`;
   - no active results and resolved count > 0 → `maintenance`;
   - neither → `ok`.
4. Job Summary names the maintenance condition and recommends
   `--prune-baseline`; it must not say healthy.
5. The original CLI exit `9` is restored after outputs/summary are written.
6. Legacy npm-version SARIF without producer metadata remains compatible:
   active counts are derived, resolved count defaults to zero, no health or
   maintenance state is fabricated.
7. Real `uses: ./` self-test covers a baseline-maintenance failure with
   `continue-on-error` and verifies:
   - step outcome is failure;
   - `status=maintenance`;
   - `resolved-baseline-count > 0`;
   - finding count is zero;
   - SARIF metadata matches outputs;
   - normal bundled scan/drift/npm paths still report resolved count zero.

## Scope

**In scope**:

- `scripts/sarif.py`
- `bin/action-report.js`, `bin/action-report.test.js`
- `action.yml`
- `.github/workflows/action-self-test.yml`
- `tests/test_sarif.py`, `tests/test_action_metadata.py`
- baseline integration tests only as needed
- trilingual READMEs and `SKILL.md`
- plan/index updates

**Out of scope**:

- Put resolved baseline entries in SARIF `results`.
- Automatically prune from the Action.
- Change exit `9`, baseline schemas, or active gate precedence.
- Upload SARIF automatically.

## Steps

### Step 1: Add resolved baseline producer metadata

Extend `properties.aiHarnessDoctor` with `resolvedBaselineCount` for scan and
drift. Add tests for zero and non-zero resolved counts. Existing result counts,
fingerprints, categories, and health metadata remain unchanged.

### Step 2: Extend the Action helper and outputs

Add `resolved-baseline-count`; parse/validate producer metadata; derive
`maintenance` status precedence; render a Job Summary row and prune guidance.
Add Node tests for maintenance, legacy default zero, malformed/negative counts,
and environment-file output.

### Step 3: Add a real Action maintenance fixture

In `.github/workflows/action-self-test.yml`:

- build a tiny repo with one semantic/drift baseline entry that is now resolved;
- invoke `uses: ./` with `--check-baseline` and `continue-on-error`;
- assert failure outcome, exit-derived report outputs, SARIF metadata, and no
  active result.

Do not use a direct CLI invocation as the only evidence.

### Step 4: Synchronize public docs

Document Action `status=maintenance`, `resolved-baseline-count`, and that
baseline maintenance failures report before restoring exit `9`.

### Step 5: Gates and merge

```bash
python3 -m unittest discover -s tests -p 'test_sarif.py' -v
python3 -m unittest discover -s tests -p 'test_action_metadata.py' -v
node --test bin/action-report.test.js
npm run check
python3 scripts/check_readme_sync.py
python3 scripts/gen_adapters.py --check
python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json \
  --check-baseline --fail-on-security --fail-on-gaps --fail-on-semantic \
  --fail-on-conflicts
python3 scripts/check_drift.py . --strict
```

Open one implementation PR; wait for all nine required contexts; squash-merge.
This is part of the Plan 047/048 backward-compatible **minor** feature set.

## Done criteria

- [ ] Exit-9 reports `status=maintenance`, never `ok`.
- [ ] Resolved count is in SARIF metadata, Action output, and Job Summary.
- [ ] Resolved entries do not become Code Scanning results.
- [ ] Active findings still take status precedence.
- [ ] Legacy SARIF defaults resolved count to zero without fabricated health.
- [ ] Real composite Action self-test covers maintenance failure.
- [ ] Trilingual docs, full local gates, and nine CI contexts pass.

## STOP conditions

Stop if:

- truthful maintenance reporting requires turning resolved debt into SARIF
  findings;
- the Action would swallow or remap exit `9`;
- a legacy npm override would be reported as maintenance without metadata;
- any required CI context is red/pending.

## Maintenance notes

- Any future non-active maintenance gate needs an explicit producer metadata
  field and Action status; never infer it only from a non-zero exit.
- Action status precedence must stay `findings > maintenance > ok`.
