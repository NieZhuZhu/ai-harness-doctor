# Plan 060: Reject unsupported batch SARIF instead of emitting Markdown

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md` unless a reviewer maintains the index separately.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 8b0d19e..HEAD -- \
>   scripts/scan.py tests/test_scan.py \
>   README.md README.zh-CN.md README.ja.md README.es.md README.ko.md \
>   README.pt-BR.md README.fr.md SKILL.md \
>   plans/060-reject-batch-sarif-format-mismatch.md plans/README.md
> ```
>
> If any in-scope file changed, compare the "Current state" excerpts against
> live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: Plans 012, 032, and 042 (DONE)
- **Category**: bug / CLI contract / CI integration / docs
- **Planned at**: commit `8b0d19e`, 2026-07-17
- **Reconciled**: REJECTED — fixed independently by direct `main` commit
  `d3a6a3e` (no associated plan/implementation PR), released in `v1.12.1` and
  retained through `v1.13.1`. Do not execute this plan again.
- **Verification**: current `origin/main` rejects batch SARIF before reading the
  repos file, keeps stdout empty, points users to aggregate `--json`, and
  retains supported batch modes. All 14 `ReposFileTests`, strict drift 100/A,
  and self-eval 38/38 pass. The commit's push `test` and `action-self-test`
  workflows succeeded, but there is no nine-context PR evidence.

## Why this matters

`scan` advertises global `--sarif`, but the `--repos-file` branch returns before
the SARIF renderer. The combination is accepted, scans every repository, exits
0, and writes a Markdown batch table to stdout. Automation expecting SARIF then
fails later with a JSON parse error or uploads the wrong artifact, while the
doctor itself reported success.

Cross-repository SARIF needs an explicit orchestration design because artifact
paths belong to different repositories. Until that exists, reject the
unsupported combination before scanning, with an actionable `--json`
alternative. Do not pretend that unrelated repositories form one code-scanning
run.

## Mechanical reproduction

For one valid repository:

```bash
python3 scripts/scan.py \
  --repos-file repos.txt \
  --sarif \
  --no-report-file
```

Observed:

```text
exit: 0
stdout: # Multi-repo Checkup Report ...
JSON parse: JSONDecodeError
```

Control:

```bash
python3 scripts/scan.py --repos-file repos.txt --json
```

emits the documented `{summary, repos}` JSON payload.

## Current state

### Batch mode exits before output precedence

`scripts/scan.py:2705-2716` validates batch incompatibilities and immediately
calls `_run_repos_file(args)`.

Single-repo output precedence appears later:

```python
if args.sarif:
    ...
elif args.as_json:
    ...
else:
    ...
```

`_run_repos_file()` implements only JSON vs Markdown and never inspects
`args.sarif`.

### Existing batch tests cover many gates, not format mismatch

`tests/test_scan.py::ReposFileTests` covers:

- positional/batch exclusivity;
- missing/empty list;
- JSON aggregate and operational errors;
- Markdown rendering;
- finding-gate precedence;
- `--no-report-file`.

Add the unsupported format case there. No SARIF translator change is needed.

### Why not synthesize one SARIF file now

Each batch entry is an unrelated repository root. A single uploaded SARIF file
would resolve artifact URIs against the repository receiving the upload, which
misattributes other repositories' files. Per-repository SARIF files and
categories require a consumer/orchestrator/output-directory contract and are a
separate feature.

## Target contract

1. `--repos-file` combined with `--sarif` exits non-zero before:
   - reading/scanning listed repositories;
   - discovering/executing plugins;
   - writing report files;
   - printing Markdown/JSON/SARIF to stdout.
2. Use exit code `1`, matching other invalid option combinations.
3. Stderr must state:
   - `--repos-file` cannot be combined with `--sarif`;
   - use `--json` for the aggregate machine-readable report;
   - per-repository SARIF is not currently emitted.
4. Stdout remains empty.
5. The rejection also applies when `--json` and `--sarif` are both present;
   SARIF must not be silently ignored or take precedence in batch mode.
6. Preserve existing validation precedence for:
   - explicit `repo_root` + `--repos-file`;
   - baseline/batch combinations.
   Document/test the chosen order rather than changing unrelated errors.
7. Single-repo `--sarif` remains unchanged.
8. Batch `--json` and Markdown remain unchanged, including exit codes 2/3/4/7/8.
9. Add a no-side-effect regression proving a listed opt-in plugin sentinel is
   not imported/executed on rejected arguments.
10. Update all seven READMEs and `SKILL.md` with one concise batch-output rule.
11. Do not add batch SARIF generation in this plan.

## Design

Add one preflight branch in the existing `if args.repos_file:` validation,
before `_run_repos_file(args)`:

```python
if args.sarif:
    print(
        "error: --repos-file cannot be combined with --sarif; "
        "use --json for the aggregate batch report",
        file=sys.stderr,
    )
    return 1
```

Place it after the existing root/baseline checks unless tests establish a more
consistent precedence. Do not inspect repository contents first.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Batch tests | `python3 -m unittest tests.test_scan.ReposFileTests -v` | all pass |
| SARIF controls | `python3 -m unittest tests.test_sarif -v` | all pass |
| Full gate | `npm run check` | all pass |
| Package candidate | `npm run check:package` | package candidate OK |
| README sync | `python3 scripts/check_readme_sync.py` | seven READMEs aligned |
| Self scan | current baseline/fail-on command | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | 100/100, Grade A |
| Self eval | current evidence-bound score command | all pass, Grade A |

## Scope

**In scope**:

- `scripts/scan.py`
- `tests/test_scan.py`
- all seven public READMEs
- `SKILL.md`
- `plans/060-reject-batch-sarif-format-mismatch.md`
- `plans/README.md`

**Out of scope**:

- Generating one or multiple batch SARIF files.
- Uploading SARIF to GitHub.
- New output-directory, filename, category, or orchestration flags.
- Changing `scripts/sarif.py`.
- Changing single-repo/monorepo SARIF.
- Baseline composition across repositories.
- Batch plugin policy or exit precedence.
- Runtime dependencies.

## Git workflow

- Branch: `fix/060-reject-batch-sarif`.
- Commit: `fix(scan): reject unsupported batch SARIF`.
- One focused CLI correctness PR with synchronized public docs.
- Wait for all nine required checks before squash merge.
- Bugfix-only: patch-release material.

## Steps

### Step 1: Add the current failure as a RED CLI test

Create a valid repo list and invoke `--repos-file --sarif --no-report-file`.
Assert current behavior is wrong: exit 0 and Markdown output.

Change the target assertion to exit 1, empty stdout, and actionable stderr.

### Step 2: Add preflight rejection

Implement the smallest validation branch before `_run_repos_file`. Add a
combined `--json --sarif` case and pin validation precedence against root and
baseline conflicts.

### Step 3: Prove no scan/plugin side effect

List a repository containing an opt-in plugin that would write a sentinel on
import/check. Invoke rejected args with `--allow-plugins`; assert the sentinel
does not exist and no warning claims plugin execution began.

Use only temporary synthetic repositories; never execute real untrusted plugin
code.

### Step 4: Preserve supported controls

Run existing batch JSON/Markdown/finding/operational tests and all single-repo
SARIF tests. Assert no renderer or category changed.

### Step 5: Synchronize docs and review

Document:

- batch aggregate machine format is `--json`;
- `--sarif` is single-repo/monorepo only;
- batch SARIF requires per-repository orchestration and is not silently
  approximated.

Review Standards/Spec, run all gates, open one PR, and wait for all nine
contexts.

## Test plan

- `--repos-file --sarif` rejection.
- `--repos-file --json --sarif` rejection.
- Empty stdout/actionable stderr.
- No plugin/list scan side effect.
- Existing validation precedence.
- Batch JSON and Markdown controls.
- Single-repo and monorepo SARIF controls.
- Seven-language docs.

## Done criteria

- [x] Batch SARIF never silently emits Markdown.
- [x] Invalid combination fails before scanning or plugin execution.
- [x] Aggregate JSON remains the documented machine output.
- [x] Single-repo/monorepo SARIF is unchanged.
- [x] Existing batch exit precedence is unchanged.
- [x] Seven READMEs and SKILL are synchronized.
- [ ] Full local and nine required CI checks pass.

## STOP conditions

Stop and report back if:

- a current consumer demonstrably depends on the silent Markdown behavior;
- safe batch SARIF can be implemented only by misattributing artifact paths;
- rejection occurs after plugin/scan side effects;
- supported batch JSON/Markdown or single-repo SARIF regresses;
- any required CI context is red or pending.

## Maintenance notes

- Every accepted output-format flag must control the actual stdout format.
- Do not add cross-repository SARIF until there is a concrete consumer contract
  for separate files/uploads/categories and repository-relative artifact URIs.
- Keep invalid-combination validation before target reads and opt-in code.
