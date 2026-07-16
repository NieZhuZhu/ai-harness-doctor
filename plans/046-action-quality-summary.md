# Plan 046: Make the GitHub Action emit composable quality outputs and a Job Summary

> **Executor instructions**: Follow every step and verification command. Stop
> on any condition in "STOP conditions"; do not improvise.
>
> **Drift check**:
>
> ```bash
> git diff --stat f434c64..HEAD -- \
>   action.yml scripts/sarif.py bin/action-report.js bin/action-report.test.js \
>   tests/test_sarif.py tests/test_action_metadata.py \
>   .github/workflows/action-self-test.yml \
>   README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md
> ```

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: Plans 012, 034, 042 (DONE)
- **Category**: feature (GitHub-native consumer DX)
- **Planned at**: commit `f434c64`, 2026-07-16
- **Implementation**: TODO

## Why this matters

The Marketplace Action currently exposes only `sarif-file`. A consuming
workflow cannot branch on a health grade, finding count, or blocking status
without opening and re-parsing the SARIF itself. The Action also writes no
`$GITHUB_STEP_SUMMARY`, so a maintainer must expand raw logs or navigate to Code
Scanning to learn whether the run was healthy.

There is a second, more important failure-path issue: the composite step runs
under `set -euo pipefail`. When `scan --fail-on-*` or `drift --strict` emits a
valid SARIF document and then exits non-zero, Bash stops before the Action can
publish outputs or a summary. The job correctly fails, but the structured
diagnostic produced by the doctor is not surfaced through the Action contract.

A premium Action should be both a gate and a composable report producer:
single execution, deterministic outputs, a readable Job Summary, and the
original CLI exit code preserved after reporting.

## Current state

`action.yml` exposes one output and immediately executes the CLI:

```yaml
outputs:
  sarif-file:
    value: ${{ steps.run.outputs.sarif-file }}
...
run: |
  set -euo pipefail
  ...
  node "$cli" "${run_args[@]}" > "$INPUT_SARIF_FILE"
  echo "sarif-file=$INPUT_SARIF_FILE" >> "$GITHUB_OUTPUT"
```

No code writes `$GITHUB_STEP_SUMMARY`. The Action self-test validates driver
version, category, fingerprints, and install containment, but no report outputs.

`scripts/sarif.py` already owns the single deterministic translation from the
scan/drift report into SARIF. It sees:

- every active SARIF finding via `results`;
- drift `ok`, `score`, and `grade`;
- the command category (`scan` vs `drift`).

That is the right point to attach producer metadata without re-running either
engine.

## Target contract

1. Each SARIF run carries an `ai-harness-doctor` property bag with:
   - `command`: `scan` or `drift`;
   - `findingCount`: total active SARIF results;
   - `errorCount`, `warningCount`, `noteCount`;
   - drift only: `ok`, `score`, `grade`.
2. Keep all existing SARIF fields, result ordering, fingerprints, and
   categories unchanged. Metadata is additive and deterministic.
3. Add a shipped Node >=16 stdlib helper, e.g. `bin/action-report.js`, that:
   - reads one SARIF file;
   - validates the expected run/property shape;
   - writes Action outputs to the path in `GITHUB_OUTPUT`;
   - appends a concise Markdown table to `GITHUB_STEP_SUMMARY`;
   - exposes a testable pure parser/renderer when required as a module.
4. Composite Action outputs:
   - existing `sarif-file`;
   - `status`: `ok` or `findings` (operational failures still fail before a
     trusted report exists);
   - `finding-count`, `error-count`, `warning-count`, `note-count`;
   - drift only: `health-score`, `health-grade`; scan uses empty values.
5. The CLI runs exactly once. Capture its exit code without swallowing it:
   disable `errexit` only around the CLI call, parse/report the completed SARIF,
   then `exit "$cli_status"`.
6. If the CLI fails before writing valid SARIF (runtime/install/argument error),
   fail with the original non-zero status and do not fabricate healthy outputs.
7. No runtime dependency; Node 16 + Python 3.9 standard library only.

## Design boundaries

**In scope**:

- `scripts/sarif.py`, `tests/test_sarif.py`
- new `bin/action-report.js` + `bin/action-report.test.js`
- `action.yml`
- `.github/workflows/action-self-test.yml`
- `tests/test_action_metadata.py`
- trilingual READMEs and `SKILL.md`
- `plans/046-action-quality-summary.md`, `plans/README.md`

**Out of scope**:

- Automatically uploading SARIF (consumer still controls permissions/upload).
- Changing scan/drift exit codes or fail-on semantics.
- Adding a JSON output file beside SARIF.
- Supporting `--repos-file` SARIF.
- Parsing human-readable CLI output in Bash.

## Steps

### Step 1: Add SARIF run metadata

Extend `build_document` with optional deterministic `properties`, and have
`scan_report_to_sarif` / `drift_report_to_sarif` attach the target metadata.
Counts must be derived from final active SARIF results, not raw report arrays,
so baselined debt remains excluded and every emitted family is counted.

Tests:

- scan counts error/warning/note across root + packages;
- drift exposes score/grade/ok and counts built-in + custom findings;
- empty report count is zero;
- existing SARIF document/fingerprint/category tests remain green.

### Step 2: Add the Node Action report helper

Create `bin/action-report.js` with pure functions for parsing metadata and
rendering:

- output lines (`key=value`);
- Markdown Job Summary.

CLI mode accepts the SARIF path and writes only to environment-file paths. It
must reject missing/malformed/incompatible SARIF with a concise error and
non-zero exit.

Add `bin/action-report.test.js` for scan, drift, zero findings, malformed
metadata, missing env files, and Markdown escaping.

### Step 3: Wire the composite Action without swallowing gates

In `action.yml`:

```bash
set +e
node "$cli" ... > "$INPUT_SARIF_FILE"
cli_status=$?
set -e

if node "$ACTION_PATH/bin/action-report.js" "$INPUT_SARIF_FILE"; then
  echo "sarif-file=$INPUT_SARIF_FILE" >> "$GITHUB_OUTPUT"
else
  report_status=$?
  if [ "$cli_status" -eq 0 ]; then exit "$report_status"; fi
fi
exit "$cli_status"
```

Preserve the original CLI failure as authoritative. The exact implementation
may differ, but a valid finding report must publish outputs/summary before its
non-zero gate is restored, while an operational failure must never be reported
as healthy.

### Step 4: Strengthen Action self-test

Extend `.github/workflows/action-self-test.yml` to assert:

- bundled scan/drift outputs match the SARIF metadata;
- the summary file contains the command, counts, and drift grade;
- the tail-security failure step still fails, but its SARIF/report metadata is
  complete before failure;
- exact published npm override remains compatibility-only and may predate the
  new output contract until release.

Extend `tests/test_action_metadata.py` to pin the public outputs and the
capture-report-restore-exit structure.

### Step 5: Synchronize docs

Document the new outputs and Job Summary in all three READMEs and `SKILL.md`.
Keep fenced code blocks, table shape, links, and inline comments synchronized.

### Step 6: Full gates and PR

```bash
python3 -m unittest discover -s tests -p 'test_sarif.py' -v
python3 -m unittest discover -s tests -p 'test_action_metadata.py' -v
node --test bin/action-report.test.js
npm run check
node --check bin/cli.js
python3 scripts/check_readme_sync.py
python3 scripts/gen_adapters.py --check
python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json \
  --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts
python3 scripts/check_drift.py . --strict
```

Open one implementation PR, wait for all nine required contexts, then
squash-merge. This is a backward-compatible **minor** feature.

## Done criteria

- [ ] Action outputs include status/counts and drift health.
- [ ] Every successful/finding SARIF has deterministic producer metadata.
- [ ] One CLI execution produces SARIF, outputs, and Job Summary.
- [ ] A valid non-zero findings gate reports first, then exits with the original
      CLI status.
- [ ] Operational/malformed-report failures do not fabricate outputs.
- [ ] Bundled scan/drift and tail-security failure paths are self-tested.
- [ ] Trilingual docs and `SKILL.md` are synchronized.
- [ ] Full local and nine-context CI gates pass; PR merged.

## STOP conditions

Stop if:

- the design requires running scan/drift twice;
- preserving outputs requires changing public CLI exit codes;
- metadata cannot stay additive to SARIF 2.1.0;
- a failure path would emit `status=ok` without a valid parsed report;
- any required CI context is red/pending.

## Maintenance notes

- SARIF metadata is the single source for Action outputs and summaries; never
  duplicate finding-count logic in Bash.
- New SARIF result levels or commands must extend the property producer and
  Action helper tests together.
- The published npm override in PR self-test may be one release behind; current
  source-code assertions belong to bundled invocations.
