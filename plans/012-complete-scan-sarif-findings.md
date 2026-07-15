# Plan 012: Emit every active scan finding family in SARIF

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat b638ad7..HEAD -- scripts/sarif.py scripts/scan.py tests/test_sarif.py tests/test_scan.py tests/test_action_metadata.py action.yml README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: correctness / product / DX
- **Planned at**: commit `b638ad7`, 2026-07-15

## Why this matters

`scan --sarif` is the repository's GitHub-native findings surface and the
composite Action's only output. It is documented as being built from the full
active report, but currently omits scan size warnings and opt-in custom rule
findings. The same findings appear in JSON, Markdown, and the combined PR review,
so GitHub Code Scanning can incorrectly look clean while another official output
reports an active issue.

Every active scan finding family needs one deterministic SARIF mapping. This
plan closes the missing two families without changing detection, plugin opt-in,
baseline membership, or exit codes.

## Current state

- `scripts/scan.py:1377-1399` builds a single-repo report containing both
  families:

  ```python
  report = {
      "warnings": warnings,
      "conflicts": conflicts,
      "security": security_findings(...),
      "semantic": semantic.analyze(...),
      "gaps": find_gaps(...),
  }
  report["custom"] = plugins.run_plugins(...)
  ```

- `scripts/scan.py:2088-2096` promises and dispatches the complete report:

  ```python
  # SARIF emission happens on the COMPLETE report (root + every package) ...
  # GitHub code scanning always receives the full set of findings ...
  print(json.dumps(sarif.scan_report_to_sarif(report), ...))
  ```

- `scripts/sarif.py:136-192` translates only `security`, `gaps`, `semantic`,
  and `conflicts`. It has no loops for `warnings` or `custom`.

- Drift SARIF already maps custom rules at `scripts/sarif.py:205-219`; scan
  should have equivalent custom-finding coverage while retaining the scan
  family/rule namespace.

- `tests/test_sarif.py:51-95` explicitly encodes the omission:

  ```python
  "custom": [{"check": "X", "level": "ERROR", "message": "ignored for scan"}],
  # overlaps and custom are skipped for scan SARIF v1.
  self.assertEqual(len(results), 4)
  ```

- Real isolated reproductions on the planned commit:
  - A 13KB `AGENTS.md` produces a `NOTICE` in `report["warnings"]`; SARIF has no
    size-warning result.
  - An opted-in deterministic plugin returning an `ERROR` finding produces
    `report["custom"]`; SARIF contains only gap results and no custom rule.

- `AGENTS.md:40` already states: "Every report family needs PR-review/SARIF
  traversal." The current implementation violates that maintenance contract.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| SARIF tests | `python3 -m unittest discover -s tests -p 'test_sarif.py' -v` | all pass |
| Scan/plugin compatibility | `python3 -m unittest discover -s tests -p 'test_scan.py' -v && python3 -m unittest discover -s tests -p 'test_plugins.py' -v` | all pass |
| Action metadata | `python3 -m unittest discover -s tests -p 'test_action_metadata.py' -v` | all pass |
| Python lint | `ruff check scripts/sarif.py tests/test_sarif.py` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | OK |
| Full gate | `npm run check` | exit 0 |
| Self checks | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts && python3 scripts/check_drift.py . --strict` | exit 0; grade A |

## Scope

**In scope**:

- `scripts/sarif.py`
- `tests/test_sarif.py`
- `scripts/scan.py` only if a small shared normalization helper is necessary
- `tests/test_scan.py` only for CLI-level compatibility
- `tests/test_action_metadata.py` only for composite Action coverage
- `action.yml` only if output behavior/metadata must change
- `README.md`, `README.zh-CN.md`, `README.ja.md`
- `SKILL.md`
- `AGENTS.md`
- `plans/README.md`

**Out of scope**:

- Emitting overlaps, inventory, nested-agent inventory, or project snapshots as
  SARIF results; these are evidence/inventory, not findings.
- Executing custom plugins by default or enabling them in shipped PR workflows.
- Changing plugin severity, scan exit-code semantics, or baseline eligibility.
- Refactoring PR-review traversal.
- Uploading SARIF to GitHub; the Action continues to write a file for consumer
  workflows to upload.

## Git workflow

- Branch: `fix/complete-scan-sarif-findings`
- Commit: `fix(sarif): include all active scan findings`
- One focused PR; squash-merge after all checks pass.
- This is a bugfix unless public SARIF rule IDs require a breaking change (a
  STOP condition).

## Steps

### Step 1: Replace the omission test with characterization tests

Update `tests/test_sarif.py` so the representative scan report includes:

- one size warning with `path` and no line;
- one custom finding with `plugin`, `rule`, path, line, message, suggestion;
- an unlocated custom finding;
- equivalent package-level warning/custom entries.

Assert exact deterministic result order, rule IDs, severity mapping, messages,
and package-prefixed artifact URIs. Preserve the existing tests for security,
gaps, semantic, conflict, baseline suppression, and rules sorted by ID.

**Verify**: the new warning/custom assertions fail against the planned commit,
while existing results still pass.

### Step 2: Define stable SARIF families and rule IDs

Add short descriptions for the missing families and map:

- scan warning → `warning/size` (or another documented single stable ID), using
  source severity and the warning's own path/line;
- scan custom finding → `custom/<rule>`, falling back to `custom/custom` when a
  rule is absent, with optional path/line and suggestion.

Neutralize empty/non-string dynamic rule IDs into a safe stable token rather
than emitting malformed IDs. Keep rule ordering deterministic and do not embed
absolute plugin file paths in a rule ID.

Use the existing `_result`, `_message_text`, `sarif_level`, and package `make_uri`
helpers. Do not import `pr_review.py` or couple SARIF to Markdown rendering.

**Verify**: focused mapping tests pass and existing rule IDs are byte-identical.

### Step 3: Traverse the two active families at root and package scope

Extend `_scan_results_for_report(report, prefix)` in the same report order used
by the scan result contract. Both warning and custom paths must pass through
`make_uri`, so package-local `AGENTS.md` becomes
`packages/app/AGENTS.md`.

Do not traverse `baselined`: baseline application has already removed eligible
gap/semantic/conflict findings from active report containers, and HIGH security
is never suppressible. Keep root-before-packages ordering.

**Verify**: monorepo warning/custom tests pass; no root/package path is doubled.

### Step 4: Add CLI and Action-level regressions

Add a CLI smoke test that:

1. creates an oversized instruction file for a warning;
2. creates an opt-in deterministic plugin returning a safe synthetic finding;
3. runs `scan --allow-plugins --sarif`;
4. asserts both result families exist with valid locations and the package
   version remains correct.

If the composite Action cannot opt in to plugins through its existing `args`
surface without changing public input semantics, keep the Action test focused
on size-warning SARIF. Do not enable repository plugin execution in shipped
workflows.

**Verify**: SARIF CLI test passes on Python 3.9/3.10/3.12; Action metadata tests
remain green.

### Step 5: Correct the public SARIF contract

Update synchronized READMEs and `SKILL.md` to enumerate the active SARIF
families: size warnings, security, gaps, semantic mismatches, opt-in custom
rules, conflicts, and drift. Clarify that inventory/overlap/snapshot sections
remain JSON/Markdown evidence rather than code-scanning findings.

Keep the existing concise `AGENTS.md` invariant unless implementation reveals a
new maintenance rule; do not duplicate documentation just to touch the file.

**Verify**: docs sync, full gate, self scan, and strict drift.

## Test plan

- Pure SARIF mapping:
  - root warning/custom located and unlocated;
  - safe fallback custom rule ID;
  - suggestion included;
  - severity mapping;
  - rule descriptor sorting.
- Monorepo:
  - package-prefixed warning/custom paths;
  - root-before-package deterministic order.
- CLI:
  - oversized instruction warning appears in `--sarif`;
  - opted-in plugin finding appears once;
  - baselined debt remains absent;
  - plugin-disabled default remains absent.
- Existing scan/drift SARIF tests remain unchanged except expected additive
  results.

## Done criteria

- [ ] Every active scan warning/custom finding appears exactly once in SARIF.
- [ ] Package findings use valid repository-relative prefixed URIs.
- [ ] Dynamic custom rule IDs are stable and safe.
- [ ] Plugin execution remains explicit opt-in.
- [ ] Inventory/overlap/snapshot data is not misrepresented as findings.
- [ ] Existing rule IDs, levels, exit codes, and baseline behavior do not regress.
- [ ] `npm run check` passes and strict self-drift remains grade A.
- [ ] Only in-scope files are modified.

## STOP conditions

- Mapping custom findings requires executing plugins when `--allow-plugins` was
  not explicitly supplied.
- A safe rule ID requires changing existing published security/gap/semantic/
  conflict rule IDs.
- Package attribution cannot remain repository-relative.
- The fix needs a shared abstraction that couples SARIF to PR-review Markdown.
- Verification fails twice after a reasonable correction.

## Maintenance notes

Reviewers should compare the scan report containers with both
`_scan_results_for_report()` and `pr_review.collect_findings()` whenever a new
finding family is added. An official finding is incomplete until its JSON,
Markdown, PR-review, and SARIF behavior is explicitly tested.
