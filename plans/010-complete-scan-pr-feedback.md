# Plan 010: Deliver every active scan finding as attributed PR feedback

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat b3dd9e3..HEAD -- scripts/pr_review.py scripts/scan.py scripts/sarif.py assets/guard/harness-drift.yml .github/workflows/harness-drift.yml tests/test_pr_review.py tests/test_cli.py tests/test_action_metadata.py README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md`
> If any in-scope file changed, compare the current-state excerpts below with
> live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: Plan 009
- **Category**: correctness / DX / product
- **Planned at**: commit `b3dd9e3`, 2026-07-15

## Why this matters

The public `review` command is documented as accepting both drift and scan JSON,
but it drops scan conflicts and all findings nested under monorepo `packages`
or batch-mode `repos`. The shipped GitHub guard runs a scan gate but then posts
only a separately generated drift report, so a HIGH security finding, missing
canonical config, semantic mismatch, or conflict may fail CI without appearing
in the promised rich PR feedback.

The product's strongest GitHub-native surface should deliver one complete,
attributed review covering all active scan and drift findings while keeping
baselined debt out of active feedback and preserving the existing HTTP-422
fallback.

## Current state

- `scripts/pr_review.py:91-125` collects only:

  ```python
  container_keys = ("findings", "custom", "security", "gaps", "semantic")
  # findings/custom/security/gaps/semantic.findings are flattened
  ```

  It does not read `conflicts`, `packages`, or `repos`.

- `scripts/sarif.py:185-200` already demonstrates the expected conflict
  normalization and monorepo traversal:

  ```python
  for conflict in report.get("conflicts", []):
      signal = conflict.get("signal", "")
      values = conflict.get("values", {})
      message = f"Conflicting {signal} declarations: " + ", ".join(sorted(values.keys()))

  for package in report.get("packages", []):
      prefix = package.get("path", "")
      results.extend(_scan_results_for_report(package.get("report", {}), prefix))
  ```

- `scripts/scan.py:1759-1786` emits package entries shaped as
  `{path, name, has_agents_md, summary, report}`.

- `scripts/scan.py:1803-1848` emits batch entries shaped as
  `{path, resolved, name, has_agents_md, summary, report}` or an error entry.

- `scripts/pr_review.py:249-314` routes findings with `(path, line)` inline and
  everything else to a complete summary. Keep that behavior.

- `assets/guard/harness-drift.yml:40-76`:
  1. runs a scan gate but does not save its JSON;
  2. runs drift;
  3. generates only `drift . --json`;
  4. posts only `drift-report.json`.

- `.github/workflows/harness-drift.yml:48-82` has the same self-bootstrap
  asymmetry.

- `README.md:172` promises `review` reads `drift --json` **or** `scan --json`
  and surfaces rich findings. `SKILL.md:218-223` repeats the contract.

- A direct pure-function reproduction:

  ```python
  pr_review.collect_findings({
      "conflicts": [...],
      "packages": [{"path": "packages/a", "report": {"security": [...]}}],
      "repos": [{"path": "repo-a", "report": {"gaps": [...]}}],
  })
  ```

  currently returns `[]`.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Review tests | `python3 -m unittest discover -s tests -p 'test_pr_review.py' -v` | all pass |
| Scan/SARIF compatibility | `python3 -m unittest discover -s tests -p 'test_scan.py' -v && python3 -m unittest discover -s tests -p 'test_sarif.py' -v` | all pass |
| Guard installer tests | `PYTHONPATH=tests python3 -m unittest tests.test_cli -v` | all pass |
| Workflow metadata | `python3 -m unittest discover -s tests -p 'test_action_metadata.py' -v` | all pass |
| Workflow lint | `go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7 && go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7 assets/guard/harness-drift.yml` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | OK |
| Full gate | `npm run check` | exit 0 |
| Self checks | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts && python3 scripts/check_drift.py . --strict` | exit 0; drift grade A |

## Scope

**In scope**:

- `scripts/pr_review.py`
- `scripts/sarif.py` only if a shared normalization helper is justified
- `scripts/scan.py` only for report metadata needed for attribution
- `assets/guard/harness-drift.yml`
- `.github/workflows/harness-drift.yml`
- `tests/test_pr_review.py`
- `tests/test_cli.py`
- `tests/test_action_metadata.py`
- synchronized READMEs
- `SKILL.md`
- `AGENTS.md`
- `plans/README.md`

**Out of scope**:

- Changing scan detection/severity or baseline membership.
- Posting comments on GitLab/Codebase.
- Adding a second GitHub review per run.
- Automatically resolving conflicts.
- Reposting baselined/suppressed findings as active failures.
- Changing the existing 422 fallback or network error policy except where
  needed to carry the combined payload.

## Git workflow

- Branch: `fix/complete-scan-pr-feedback`
- Commit: `fix(review): include complete scan findings`
- One focused PR after Plan 009 is merged.
- Squash-merge after all checks pass; do not release in this PR.

## Steps

### Step 1: Define normalized review findings for every report shape

Refactor `collect_findings()` into an explicit recursive report walker. It must:

- preserve current top-level drift/scan findings;
- normalize each conflict into a finding with:
  - `rule` or `category` identifying `conflict/<signal>`;
  - `level: "WARN"`;
  - deterministic message listing sorted values;
  - structured `values`/evidence suitable for summary rendering;
- recurse through monorepo `packages` and prefix relative paths with the package
  path;
- recurse through batch `repos` and attach a stable repo identity to every
  finding without leaking machine-specific `resolved` absolute paths;
- ignore batch error entries as findings unless a deliberate, documented
  `scan-error` summary finding is added;
- ignore `baselined` debt as active findings;
- never duplicate a finding already emitted at the root.

Use one normalization contract shared with SARIF if practical. Do not couple
the reviewer to rendered Markdown.

**Verify**: pure tests cover root conflicts, package security/semantic/gaps,
batch repo findings, path prefixing, deterministic order, baselined exclusion,
and no duplicate root findings.

### Step 2: Preserve attribution in inline and summary feedback

For package findings:

- prefix a relative finding path with the package path;
- semantic/gap findings that conceptually target `AGENTS.md` should point at
  `<package>/AGENTS.md`;
- a line-only finding may use the package-local AGENTS path, not the root
  `default_path`.

For batch repo findings:

- batch reviews are dry-run/report use only unless all repos refer to one GitHub
  PR; keep them summary-only by default;
- include the raw repos-file label/name, never `resolved` absolute paths.

Extend `_RULE_TITLES`, `_IMPACT_BY_LABEL`, and evidence rendering so conflicts
are intelligible and sorted.

Keep all user-controlled strings newline-neutralized and keep inline comments
limited to positive integer lines.

**Verify**: tests assert exact inline paths and that cross-repo findings never
create invalid inline comments.

### Step 3: Build one combined active report in the GitHub guard

Change shipped and self-bootstrap workflows to capture both machine-readable
reports regardless of gate outcomes:

```bash
scan ... --json > scan-report.json
drift ... --json > drift-report.json
```

Then combine them deterministically before one `review --post` invocation. The
combination can be:

- a JSON list `[scanReport, driftReport]`, already supported conceptually by
  recursive collection; or
- a documented wrapper object with `reports`.

Do not run the expensive scan twice if the gate step can write JSON once and
derive/retain its exit status. If the current Markdown gate output is useful,
render it from the saved JSON or run only the minimum required second command;
prefer one scan per PR.

The review step remains `always()` and uses the PR head SHA. Consumer templates
must call only packaged CLI commands. Self-bootstrap uses local code.

**Verify**: static workflow tests prove the one posted review includes both
`scan-report.json` and `drift-report.json`; actionlint passes.

### Step 4: Add a fresh-consumer end-to-end review test

Extend `tests/test_cli.py`:

- install the GitHub guard into a repo with no local `scripts/`;
- create at least one scan-only finding (for example a HIGH security fixture
  represented without embedding a real credential value in source) and one
  drift finding;
- run packaged CLI scan/drift JSON and combine them exactly like the template;
- run `review` dry-run;
- assert both findings appear once in the final index/details and have correct
  inline-vs-summary placement.

Use generated test values that do not trip platform secret scanning. Keep HOME
isolated.

**Verify**: focused CLI and review suites pass.

### Step 5: Update the public contract and maintenance docs

Update all three READMEs and `SKILL.md`:

- GitHub guard posts one combined active scan+drift review;
- conflicts and monorepo attribution are included;
- baselined debt remains visible in scan JSON but is not posted as an active PR
  failure;
- batch reports are summary-attributed and not treated as one-repo inline
  comments.

Update `AGENTS.md` so every new report container/finding family must declare how
`review` and SARIF traverse/normalize it.

**Verify**: docs sync, full gate, self scan, and strict drift.

## Test plan

- `collect_findings` unit matrix:
  - root drift + security + gap + semantic + conflict + custom;
  - package root/path prefix;
  - package line-only semantic location;
  - nested package conflicts;
  - batch repo attribution;
  - batch error entry;
  - baselined exclusion;
  - duplicate prevention and deterministic ordering.
- `build_review` cases for rich conflict summary and package inline placement.
- Workflow static contract for one combined review.
- Fresh consumer with no `scripts/` integration.
- Existing 422 fallback, auth failure, newline injection, and deterministic body
  tests must stay green.

## Done criteria

- [ ] `review` returns every active root and package scan finding exactly once,
      including conflicts.
- [ ] Batch findings retain non-absolute repo attribution and stay safe for
      summary delivery.
- [ ] `baselined` findings are not presented as active PR failures.
- [ ] GitHub guard posts one review containing both scan and drift findings.
- [ ] Consumer workflow still works in a repo with no local `scripts/`.
- [ ] Inline locations are valid package-prefixed repo-relative paths.
- [ ] 422 fallback retains the complete combined summary.
- [ ] All focused/full tests and actionlint pass; self-drift remains grade A.
- [ ] No files outside Scope are modified.

## STOP conditions

- Combining scan and drift requires posting multiple reviews or loses the
  existing complete 422 fallback.
- Package paths cannot be converted to repository-relative paths without
  changing the public scan JSON shape.
- A batch report would expose absolute machine paths in a public comment.
- The shipped workflow would need source-repo `scripts/`.
- In-scope report shapes changed since `b3dd9e3`.
- Verification fails twice after a reasonable correction.

## Maintenance notes

Every new report container or finding family is incomplete until it has a
defined SARIF and PR-review traversal. Reviewers should test root, monorepo, and
batch shapes together so new product surfaces cannot silently disappear from
GitHub feedback.
