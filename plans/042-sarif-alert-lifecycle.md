# Plan 042: Make SARIF alert identity survive edits and coexist per command

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md`.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat e25d421..HEAD -- \
>   scripts/sarif.py scripts/scan.py scripts/check_drift.py \
>   tests/test_sarif.py .github/workflows/action-self-test.yml \
>   README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md
> ```
>
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against live code before proceeding. If the SARIF
> builder signature, the `scan_finding_fingerprint` identity, or the
> `--sarif` command wiring changed materially, treat that as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: Plan 012 (DONE), Plan 024 (DONE)
- **Category**: feature (premium GitHub-native output)
- **Planned at**: commit `e25d421`, 2026-07-16
- **Implementation**: DONE — PR #203 (plan) / PR #207 (impl), squash-merged to
  `main` as `8f0164a`; all nine required contexts green (a first self-test run
  failed only because an added node-comment apostrophe closed the single-quoted
  shell string, fixed in the same PR; a 3.9 `test_cli` concurrent-installer
  flake cleared on rerun).

## Why this matters

Plan 012 made `scan --sarif` and `drift --sarif` emit every active finding
family as SARIF 2.1.0, so the doctor surfaces findings in GitHub's **Security →
Code scanning** tab and as inline PR annotations. That established the format;
it did not yet make the *alert lifecycle* correct. Two GitHub-documented
mechanisms are currently missing, and both cause user-visible defects the moment
someone actually wires the SARIF into `github/codeql-action/upload-sarif`:

1. **No `partialFingerprints`.** GitHub matches results across commits with
   `partialFingerprints`; when a producer omits them, GitHub falls back to
   source-derived fingerprints (Actions upload) or, over the raw
   `/code-scanning/sarifs` API, shows **duplicate alerts**. GitHub explicitly
   recommends producers populate `partialFingerprints` themselves. Our findings
   already carry a *stable identity* — `scan.py:scan_finding_fingerprint()` —
   but it never reaches the SARIF, so every reformatted line or one-line shift
   risks closing the old alert and opening a new one.

2. **No `automationDetails.id` (category).** GitHub keys a code-scanning run to
   a category via `runs[].automationDetails.id` (interpreted as
   `category/run-id`). When two SARIF files are uploaded **for the same tool and
   commit without distinct categories, the second upload closes the first one's
   alerts**. Our own README tells users to upload both `scan` and `drift` SARIF
   from the same tool name (`ai-harness-doctor`); on a repo that runs both, the
   second upload silently wipes the first command's alerts. There is no category
   today, so `scan` and `drift` collide by construction.

A premium GitHub-native tool must make its alerts *durable* (survive unrelated
edits) and *composable* (scan and drift coexist on one commit). Both fixes are
deterministic, standard-library-only, and additive to the existing SARIF shape.

## Mechanical reproduction

Against `main@e25d421`:

```bash
python3 - <<'PY'
import json, sys
sys.path.insert(0, "scripts")
import sarif
scan = sarif.scan_report_to_sarif(
    {"security": [{"level": "HIGH", "category": "secret",
                   "path": "src/config.js", "line": 12, "message": "secret"}]},
    version="1.9.0",
)
run = scan["runs"][0]
print("scan automationDetails present:", "automationDetails" in run)
print("scan result0 has partialFingerprints:",
      "partialFingerprints" in run["results"][0])
drift = sarif.drift_report_to_sarif(
    {"findings": [{"check": "D2", "level": "ERROR", "line": 7,
                   "path": "AGENTS.md", "message": "x"}]})
drun = drift["runs"][0]
print("drift automationDetails present:", "automationDetails" in drun)
print("drift result0 has partialFingerprints:",
      "partialFingerprints" in drun["results"][0])
PY
```

Observed on `e25d421`:

```
scan automationDetails present: False
scan result0 has partialFingerprints: False
drift automationDetails present: False
drift result0 has partialFingerprints: False
```

Expected after this plan: every `run` carries `automationDetails.id` with a
per-command category (`ai-harness-doctor/scan`, `ai-harness-doctor/drift`), and
every `result` carries a deterministic `partialFingerprints` map derived from
the finding's stable identity plus its file path.

## Current state

### The SARIF builder omits both fields

`scripts/sarif.py:81-100` builds a result with only `ruleId`, `level`,
`message`, and `locations`:

```python
def _result(rule_id, level, message, uri=None, start_line=None):
    result = {
        "ruleId": rule_id,
        "level": level,
        "message": {"text": message},
    }
    if uri is None:
        result["locations"] = []
    else:
        physical = {"artifactLocation": {"uri": uri}}
        if start_line is not None:
            physical["region"] = {"startLine": start_line}
        result["locations"] = [{"physicalLocation": physical}]
    return result
```

`build_document` (`scripts/sarif.py:129-147`) assembles the run with `tool` and
`results` but no `automationDetails`.

### A stable finding identity already exists — but only for baselines

`scripts/scan.py:2135-2160` canonicalizes a finding into a small dict and hashes
it into a stable string used for baseline suppression:

```python
def _baseline_entry(record):
    entry = {
        "family": record.get("family", ""),
        "rule": record.get("rule", ""),
        "package": record.get("package", ""),
        "path": record.get("path", ""),
        "message": record.get("message", ""),
    }
    ...
    return entry

def scan_finding_fingerprint(record):
    entry = _baseline_entry(record)
    return json.dumps(entry, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
```

This identity intentionally excludes line numbers and suggestions
(`scan.py:2084` "Line numbers and suggestions are presentation details, not
identity"). That is exactly the property GitHub wants in a fingerprint: it must
survive line shifts and cosmetic edits. But it lives in `scan.py`, is only
computed for baseline-eligible families, and never crosses into `sarif.py`.

### The `--sarif` wiring

- `scripts/scan.py:2624-2628`: `--sarif` calls
  `sarif.scan_report_to_sarif(report)` and prints it. `_run_repos_file`
  (`scan.py:2406-2444`) returns **before** the `--sarif` branch, so multi-repo
  batch mode does not emit SARIF — this plan does not change that.
- `scripts/check_drift.py:968-971`: `--sarif` calls
  `sarif.drift_report_to_sarif(report)`.
- Monorepo packages are folded into one scan run via `_scan_results_for_report`
  with a path prefix (`sarif.py:150-255`), so package findings already carry
  package-qualified URIs. They belong in the **same** run/category as the root.

### The collision this creates

`README.md:350-354` documents uploading both:

```bash
npx ai-harness-doctor scan . --sarif > ai-harness-doctor.sarif
npx ai-harness-doctor drift . --sarif > drift.sarif
```

Both carry `tool.driver.name == "ai-harness-doctor"` and no category, so
uploading both for one commit makes the second close the first's alerts.

## Target contract

1. **Per-command category.** `scan_report_to_sarif` sets
   `runs[0].automationDetails.id = "ai-harness-doctor/scan/"` and
   `drift_report_to_sarif` sets `"ai-harness-doctor/drift/"`. The trailing slash
   keeps the category well-defined with an empty run-id (per GitHub's
   `category/run-id` parsing). Expose the category via a small constant/argument
   on the builder so the two callers cannot silently converge.
2. **Deterministic per-result fingerprints.** Every `result` gains
   `partialFingerprints` with a single stable key (e.g.
   `aiHarnessDoctorIdentity`) whose value is a hex digest computed from the
   finding's *identity* — the same line-insensitive canonical dict used by
   baselines where applicable — combined with the SARIF `ruleId` and the
   artifact `uri` (so the same logical finding in two files/packages stays
   distinct). No line number, column, suggestion text, or run timestamp enters
   the fingerprint. Identical findings across two runs produce byte-identical
   fingerprints.
3. **Location-free findings still get a fingerprint.** Conflicts and unlocated
   custom/security findings (no `uri`) must still receive a deterministic
   fingerprint from their identity fields; a missing path contributes a fixed
   sentinel, never a crash.
4. **Purely additive.** `ruleId`, `level`, `message`, `locations`, `rules`
   ordering, monorepo path prefixing, baseline suppression, and every exit code
   are unchanged. Existing SARIF assertions in `tests/test_sarif.py` keep
   passing except where they now also assert the new fields.
5. **Self-contained in `sarif.py`.** Do not make `sarif.py` import `scan.py`
   (that would create a heavy dependency and a cycle risk). Re-implement the
   *small, documented* canonical-identity subset locally in `sarif.py`, or lift
   the tiny helper into a shared location both modules import. Prefer the
   local, dependency-free implementation with a test that pins it to
   `scan.scan_finding_fingerprint` for the baseline families so the two never
   drift apart.
6. **Determinism.** Same report in → byte-identical SARIF out, including
   fingerprints and category. No wall-clock, no PID, no environment input.
7. No new runtime dependency; Python 3.9 standard library only (`hashlib`,
   `json` are stdlib).

## Design sketch (non-binding)

```python
# sarif.py
import hashlib

SCAN_CATEGORY = TOOL_NAME + "/scan/"
DRIFT_CATEGORY = TOOL_NAME + "/drift/"

def _fingerprint(rule_id, uri, identity):
    payload = json.dumps(
        {"ruleId": rule_id, "uri": uri or "", "identity": identity},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
```

`_result` gains an `identity` argument (the canonical dict/tuple for that
finding) and always attaches
`result["partialFingerprints"] = {"aiHarnessDoctorIdentity": _fingerprint(...)}`.
`build_document` accepts an optional `category` and, when set, adds
`run["automationDetails"] = {"id": category}`. `scan_report_to_sarif` and
`drift_report_to_sarif` pass their category.

The identity per family should reuse the baseline canonical fields (family,
rule/check, package, path, message, and the family extras: gap `item`, semantic
`declared`/`actual`, conflict sorted `values`/`scope`). Exact key selection is
an implementation detail, but it must be **line-insensitive** and **stable**.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| SARIF tests | `python3 -m unittest discover -s tests -p 'test_sarif.py' -v` | exit 0 |
| Full quality gate | `npm run check` | all lint + Python + Node tests pass |
| CLI syntax/help | `node --check bin/cli.js && node bin/cli.js help` | exit 0 |
| Self scan | `python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0, grade A |
| Evidence-bound eval | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0 |
| README synchronization | `python3 scripts/check_readme_sync.py` | exit 0 |
| Adapter synchronization | `python3 scripts/gen_adapters.py --check` | exit 0 |
| Package contents | `npm pack --dry-run --json` | changed shipped script/docs included |

## Scope

**In scope**:

- `scripts/sarif.py` — add category + `partialFingerprints`.
- `scripts/scan.py` / `scripts/check_drift.py` — only if the identity helper is
  lifted into a shared module they both import; otherwise unchanged.
- `tests/test_sarif.py` — new assertions for category and fingerprints,
  including a determinism/parity test.
- `.github/workflows/action-self-test.yml` — assert the bundled scan/drift SARIF
  now carry `automationDetails.id` and per-result fingerprints (optional but
  recommended, since it is the public success contract).
- `README.md`, `README.zh-CN.md`, `README.ja.md`, `SKILL.md` — document the
  category + fingerprint behavior in the SARIF passage.
- `AGENTS.md` — one durable invariant line if budget allows.
- `plans/042-sarif-alert-lifecycle.md`, `plans/README.md`.

**Out of scope**:

- Emitting SARIF for `--repos-file` batch mode (it returns before `--sarif`);
  a separate plan if ever wanted.
- Changing `ruleId`s, levels, message text, or the rules array.
- Per-package or per-repo distinct categories (monorepo packages stay in one
  run; batch mode emits no SARIF). Adding those would need a real multi-category
  upload design and is explicitly deferred.
- `security-severity` properties, help URIs, or code-flow enrichment.
- Any change to baseline suppression or exit codes.

## Git workflow

- Start from latest `main` after this plan PR merges:
  `feat/042-sarif-alert-lifecycle`.
- Keep the feature in one implementation PR.
- Conventional Commits in English, e.g.
  `feat(sarif): add stable fingerprints and per-command category`.
- Do not push directly to `main`.
- Do not merge until all nine required contexts are green: `drift`, `lint`,
  `node (16)`, `node (20)`, `node (22)`, `self-test`, `unittest (3.9)`,
  `unittest (3.10)`, and `unittest (3.12)`.
- Admin bypass is allowed only for the sole-maintainer approval deadlock after
  required checks are green and every discussion is resolved.

## Steps

### Step 1: Characterize the missing fields

Add tests asserting (against current code they fail):

1. `scan_report_to_sarif(...)["runs"][0]["automationDetails"]["id"]
   == "ai-harness-doctor/scan/"`;
2. `drift_report_to_sarif(...)` category is `"ai-harness-doctor/drift/"`;
3. every scan result (located and unlocated) has a non-empty
   `partialFingerprints["aiHarnessDoctorIdentity"]`;
4. every drift result has one too.

**Verify**: `python3 -m unittest discover -s tests -p 'test_sarif.py' -v`
(new assertions fail before implementation).

### Step 2: Add category + fingerprints in the builder

Implement `SCAN_CATEGORY`/`DRIFT_CATEGORY`, the `_fingerprint` helper, the
`_result` `identity` argument, and the `build_document` `category` argument.
Route both report translators through them. Keep `rules` derivation and result
ordering byte-identical.

**Verify**: SARIF tests pass; assert nothing else in the document changed by
diffing a known report's JSON before/after only in the two new keys.

### Step 3: Pin fingerprint stability and cross-module parity

Add tests proving:

1. the same finding in two different files yields different fingerprints;
2. the same finding at a different `line` yields the **same** fingerprint
   (line-insensitive identity);
3. for a baseline-eligible family, the SARIF identity agrees with
   `scan.scan_finding_fingerprint` inputs (so baseline suppression and SARIF
   identity never diverge);
4. re-running the translator on the same report is byte-identical.

**Verify**: `python3 -m unittest discover -s tests -p 'test_sarif.py' -v`.

### Step 4: Extend the Action self-test (recommended)

In `.github/workflows/action-self-test.yml`, extend the "Validate Action
success matrix" node check so the bundled `scan` and `drift` SARIF each assert
`runs[0].automationDetails.id` equals the expected per-command category and that
at least one result carries `partialFingerprints`. Keep it a pure
success-contract assertion; do not alter the existing driver-version checks.

**Verify**: `node -e` snippet parses locally against a sample SARIF; workflow
lint (`npm run check`'s workflow structure tests) stays green.

### Step 5: Synchronize public docs

Update the "GitHub-native findings (SARIF)" passage in all three READMEs and the
matching `SKILL.md` passage: results carry stable `partialFingerprints` so
alerts survive unrelated edits, and each command uses its own
`automationDetails` category so uploading both `scan` and `drift` for one commit
no longer closes each other's alerts. Keep fenced blocks, tables, and links
byte-synchronized across the three READMEs.

**Verify**: `python3 scripts/check_readme_sync.py` and
`python3 scripts/gen_adapters.py --check` both exit 0.

### Step 6: Optional invariant + evidence refresh

If under budget, add one concise `AGENTS.md` invariant (SARIF results carry a
stable line-insensitive fingerprint and each command emits its own
`automationDetails` category). Only then refresh the evidence-bound self-eval
through the documented regrade workflow and keep Grade A. If no AGENTS/task
change is needed, leave the eval evidence untouched.

**Verify**:

```bash
wc -c AGENTS.md
python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json \
  --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md \
  --require-current-evidence --fail-under 80
python3 scripts/check_drift.py . --strict
```

Expected: AGENTS below 12 KiB, eval current at Grade A, strict drift Grade A.

### Step 7: Full gate, review, and PR

Run every command in "Commands you will need". Review the diff on two axes:

- standards: stdlib-only, matching tests, trilingual doc parity, deterministic
  output, no `scan.py` import cycle;
- spec: category exactly `ai-harness-doctor/scan|drift/`; fingerprints
  line-insensitive and stable; additive only; exit codes and rules unchanged.

Open one implementation PR, wait for all nine contexts, resolve discussions,
squash merge, and record PR/head/check/merge evidence here and in the index.
This is a backward-compatible **feature** → the next release is at least a
`minor` version.

## Test plan

- New tests:
  - scan run has `automationDetails.id == "ai-harness-doctor/scan/"`;
  - drift run has `automationDetails.id == "ai-harness-doctor/drift/"`;
  - every scan/drift result has a non-empty `aiHarnessDoctorIdentity`
    fingerprint (including unlocated conflict/custom/security results);
  - same finding, different file → different fingerprint;
  - same finding, different line → identical fingerprint;
  - baseline-family identity parity with `scan.scan_finding_fingerprint`;
  - full-document determinism (translate twice, assert byte-identical).
- Preserved tests: every existing `tests/test_sarif.py` assertion (rule
  ordering, level mapping, monorepo prefixing, baseline exclusion) unchanged
  except additive field assertions.

## Done criteria

- [ ] Scan and drift SARIF runs carry distinct `automationDetails.id`
      categories.
- [ ] Every SARIF result carries a deterministic, line-insensitive
      `partialFingerprints` entry.
- [ ] Unlocated findings still receive a fingerprint (no crash).
- [ ] SARIF identity agrees with baseline identity for baseline families.
- [ ] Output is byte-deterministic for a fixed report.
- [ ] `sarif.py` does not import `scan.py` (no cycle).
- [ ] Behavior changes have tests in the same PR.
- [ ] Trilingual READMEs and `SKILL.md` synchronized.
- [ ] `npm run check` passes; adapters + README sync green.
- [ ] Self scan exits 0; strict drift is 100/100 Grade A.
- [ ] Evidence-bound self-eval is current and Grade A.
- [ ] `AGENTS.md` stays below 12 KiB (if edited).
- [ ] No runtime dependency added; Python 3.9 / Node 16 remain supported.
- [ ] Implementation PR has all nine required contexts green and is merged.
- [ ] Plan/index contain final PR, CI, and merge evidence.

## STOP conditions

Stop and report instead of improvising if:

- making the fingerprint stable would require reading line numbers or other
  presentation details into identity;
- honoring per-command categories would need changing `tool.driver.name` or
  breaking an existing SARIF assertion in a non-additive way;
- avoiding a `scan.py` import cycle proves impossible without duplicating a
  large amount of logic (reassess the shared-helper approach and report);
- `AGENTS.md` cannot stay under 12 KiB after any consolidation;
- any required CI context is red/pending or a discussion is unresolved.

## Maintenance notes

- Keep the SARIF identity and `scan.scan_finding_fingerprint` conceptually
  aligned: both are line-insensitive canonical identities. If one gains a field,
  reconsider the other and keep the parity test meaningful.
- Categories are a public contract for consumers uploading multiple SARIF files.
  If a third `--sarif`-emitting command is ever added, give it its own category.
- Monorepo packages intentionally share one run/category; per-package categories
  would require a real multi-run upload design, not a fingerprint tweak.
