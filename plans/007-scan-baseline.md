# Plan 007: Baseline non-security scan debt so CI gates only new findings

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat c8d2f05..HEAD -- scripts/scan.py scripts/sarif.py scripts/scan_render.py tests/test_scan.py tests/test_sarif.py README.md README.zh-CN.md README.ja.md SKILL.md assets/guard AGENTS.md`
> If any in-scope file changed, compare the current-state excerpts below with
> live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: MED
- **Depends on**: `plans/004-contain-repository-mutations.md`
- **Category**: direction / DX / feature
- **Planned at**: commit `c8d2f05`, 2026-07-15

## Why this matters

`drift` has an adoption baseline, but `scan` does not. Real repositories often
have legitimate multi-stack conflicts, known semantic debt, or migration gaps;
the only choices today are a permanently red `--fail-on-*` gate or hiding an
entire section with `--no-*`. An auditable baseline lets teams adopt the doctor
immediately, keep existing debt visible, and fail only when a PR introduces a
new conflict/gap/semantic issue. Security HIGH findings must remain
unsuppressible so a baseline can never normalize a committed credential.

## Current state

- `scripts/check_drift.py:437-495` provides the exemplar:
  deterministic line-independent fingerprints, sorted no-timestamp payloads,
  tolerant missing/malformed baseline reads, and a separate `baselined` array.
- `scripts/scan.py:1324-1376` creates the single-repo report, while
  `:1594-1689` and `:1796-1838` independently aggregate multi-repo/monorepo
  fail gates.
- Scan gate flags are category-specific:
  `--fail-on-security`, `--fail-on-gaps`, `--fail-on-semantic`. Conflicts have
  no fail flag even though conflict adjudication is central to Treat.
- `scripts/sarif.py:136-202` translates root and package findings but has no
  baseline/suppression metadata.
- `scan_render.py` renders root summaries; package details live only in JSON.
- External validation rounds 1–15 document legitimate multi-stack conflicts
  and context-sensitive path findings. This evidence favors an explicit,
  reviewable baseline before a broad ignore-language DSL.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Scan tests | `python3 -m unittest tests.test_scan -v` | all pass |
| SARIF tests | `python3 -m unittest tests.test_sarif -v` | all pass |
| Python lint | `ruff check scripts tests` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | OK |
| Full gate | `npm run check` | exit 0 |
| Self scan/drift | `python3 scripts/scan.py . && python3 scripts/check_drift.py .` | scan clean; drift grade A |

## Scope

**In scope**:

- `scripts/scan.py`
- `scripts/sarif.py`
- `scripts/scan_render.py`
- `tests/test_scan.py`
- `tests/test_sarif.py`
- `README.md`, `README.zh-CN.md`, `README.ja.md`
- `SKILL.md`
- GitHub/GitLab/Codebase guard assets only to document/use the new baseline
- `AGENTS.md`

**Out of scope**:

- Suppressing HIGH security findings. They always remain active and visible.
- A general regex/path ignore DSL.
- Automatically deleting baseline entries when debt is fixed.
- Changing existing report keys, exit codes, or behavior when no baseline flag
  is supplied.
- Baseline support for eval; it already has separate trend/regression history.
- Cross-repo central baseline storage. Each scanned repo owns its baseline.

## Git workflow

- Branch: `feat/scan-baseline`
- Commit: `feat(scan): add adoption baseline for existing findings`
- Conventional Commit, English.
- Open one focused PR; squash merge after every CI check is green.

## Steps

### Step 1: Define a single finding identity model for scan

Create pure helpers that flatten root, monorepo-package, and (where applicable)
multi-repo scan findings into records with:

- category/family (`gap`, `semantic`, `conflict`; optionally warnings);
- stable rule/check id;
- message/evidence fields that identify the debt;
- repo/package prefix;
- path when present;
- no line number in the fingerprint.

Do not include security HIGH findings in the suppressible set. Keep messages
deterministic and avoid serializing full sensitive evidence.

Add unit tests for stable identity across line shifts, package-prefix
distinction, deduplication, and deterministic ordering.

**Verify**: focused helper tests pass.

### Step 2: Add `--write-baseline` and `--baseline` to scan

Match drift's user model:

```bash
ai-harness-doctor scan . --write-baseline .ai-harness-doctor/scan-baseline.json
ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json \
  --fail-on-gaps --fail-on-semantic --fail-on-conflicts
```

Add `--fail-on-conflicts` with a new documented non-zero exit code that does not
change existing code meanings (security 2, gaps 3, semantic 4). Baseline
suppression applies to gaps, semantic findings, and conflicts before their gate
decision. Missing/malformed baselines fail safe by suppressing nothing.

`--write-baseline` is an explicit output path and may live outside root, but it
must obey plan 004's explicit-output safety policy. The payload is versioned,
sorted, and timestamp-free.

**Verify**: no-baseline output is byte-compatible; new CLI tests cover each gate
and precedence.

### Step 3: Keep suppressed debt visible in every report shape

Add a top-level `baselined` array for root findings. Preserve package/repo
attribution in each entry; do not silently remove findings without a trace.
Markdown should state count and baseline path, and package summary counts should
distinguish active vs. suppressed debt where useful without breaking old keys.

For `--repos-file`, either support one baseline file whose entries include repo
identity, or explicitly reject composition with an actionable message. Do not
silently apply root fingerprints across unrelated repos.

**Verify**: JSON/Markdown tests cover root + monorepo and the chosen multi-repo
policy.

### Step 4: Preserve SARIF and security semantics

SARIF should emit only active findings by default so code scanning reflects the
gate, while optionally attaching suppression metadata only if SARIF 2.1.0
supports it cleanly and tests lock the shape. HIGH security findings are always
active regardless of a crafted baseline entry.

Add adversarial tests with a baseline entry shaped like a secret finding and
assert `--fail-on-security` still exits 2 and SARIF still contains the result.

**Verify**: `tests.test_sarif` and targeted scan security tests pass.

### Step 5: Integrate the adoption path into guard assets and docs

Document committing a baseline under `.ai-harness-doctor/`, reviewing it like
code, and shrinking it as debt is repaired. Add an optional, clearly marked
baseline variable/path to guard templates; do not create a baseline
automatically during `guard --apply`.

Update `AGENTS.md` with the invariant:

- baselines are transparent debt registers, not ignore files;
- security HIGH cannot be baselined;
- new finding families must define stable fingerprints and baseline behavior;
- line numbers are evidence, never identity.

**Verify**: docs sync, guard template tests, full gate, self scan/drift.

## Test plan

- Deterministic payload with no timestamp and stable sorting.
- Line shifts do not reopen debt; message/path/category changes do.
- Root and package findings with the same message remain distinct.
- Existing drift is suppressed; a newly added finding fails.
- `--fail-on-conflicts` exit code and precedence.
- Missing/malformed baseline suppresses nothing.
- HIGH security finding cannot be suppressed.
- SARIF excludes only legitimately baselined non-security findings.
- No-baseline JSON/Markdown remains unchanged apart from additive parser help.

## Done criteria

- [ ] A repo can record scan debt once and gate only new gap/semantic/conflict
      findings.
- [ ] Suppressed findings remain visible and attributed.
- [ ] HIGH security findings are impossible to baseline.
- [ ] Fingerprints are line-independent, deterministic, versioned, and tested.
- [ ] Root/monorepo behavior is supported; multi-repo behavior is supported or
      explicitly rejected.
- [ ] Existing no-baseline behavior and exit codes do not regress.
- [ ] `npm run check` exits 0; self drift remains grade A.
- [ ] No files outside Scope and `plans/README.md` are modified.

## STOP conditions

- A useful fingerprint would require storing secret values or unbounded source
  snippets.
- Conflict identity cannot be made stable without changing existing conflict
  output; report the incompatibility before changing public JSON.
- Multi-repo support would accidentally couple unrelated repositories through
  absolute machine-specific paths.
- A baseline implementation weakens `--fail-on-security` under any test.

## Maintenance notes

Baseline identity is a public compatibility surface. When changing a finding's
message, consider whether its stable identity should survive wording changes;
prefer structured category/check/path/evidence fields over hashing rendered
prose. Never turn baselines into opaque regex ignores—users must be able to
audit exactly which known debt is being accepted.
