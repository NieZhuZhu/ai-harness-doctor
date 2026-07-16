# Plan 054: Add structured GitHub Action arguments without shell evaluation

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md` unless a reviewer maintains the index separately.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat eac8426..HEAD -- \
>   action.yml bin/action-run.js bin/action-run.test.js \
>   tests/test_action_metadata.py .github/workflows/action-self-test.yml \
>   .github/workflows/release.yml package.json RELEASING.md \
>   references/maintenance-contract.md \
>   README.md README.zh-CN.md README.ja.md README.es.md README.ko.md \
>   README.pt-BR.md README.fr.md SKILL.md AGENTS.md
> ```
>
> If any in-scope file changed, compare the "Current state" excerpts against
> live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: Plans 022, 034, 046, and 048 (DONE)
- **Category**: direction / GitHub Action DX and safety
- **Planned at**: commit `eac8426`, 2026-07-17
- **Implementation**: IN PROGRESS — PR #239 (plan); implementation branch
  `feat/054-structured-action-args`, full local gates and actionlint green,
  awaiting implementation PR and required CI.

## Why this matters

The Marketplace Action exposes one free-form `args` string, then parses it with
Bash `read -r -a`. That interface is safe from shell evaluation but cannot
represent the CLI's full argument model:

- a baseline/rules/output path containing spaces becomes multiple argv items;
- quotes are passed as literal characters rather than grouping a value;
- a multiline YAML input silently keeps only the first line;
- there is no machine-validated boundary for argument count/type/control bytes.

This is now a current product gap, not a hypothetical edge case. Baseline
maintenance and external `--rules DIR` are public Action use cases and both take
path values. A repository or runner temp directory can legitimately contain
spaces. Direct CLI invocation handles the quoted path; the composite Action
cannot.

Add an opt-in structured input while preserving every existing consumer of
legacy `args`.

## Mechanical reproduction

Current `action.yml:92-99`:

```bash
run_args=("$INPUT_COMMAND" "$INPUT_PATH" "--sarif")
if [ -n "$INPUT_ARGS" ]; then
  read -r -a extra_args <<< "$INPUT_ARGS"
  run_args+=("${extra_args[@]}")
fi
```

Observed:

```text
args: --baseline /tmp/repo with spaces/base.json --check-baseline
argv:
  --baseline
  /tmp/repo
  with
  spaces/base.json
  --check-baseline
```

Quoting does not help:

```text
args: --baseline "/tmp/repo with spaces/base.json" --check-baseline
argv:
  --baseline
  "/tmp/repo
  with
  spaces/base.json"
  --check-baseline
```

Multiline input keeps only `--fail-on-security` and drops
`--fail-on-semantic`. A direct call with one quoted path succeeds, while the
split Action-equivalent call exits `2` with unrecognized arguments.

## Current state

### Composite wrapper owns install, execution, and report order

`action.yml`:

- validates `command` as `scan|drift`;
- selects bundled CLI or installs an npm override under `RUNNER_TEMP`;
- builds argv in Bash;
- runs the CLI once to SARIF;
- calls `bin/action-report.js`;
- restores the exact CLI exit code unless report generation itself failed.

Plan 046/048 established this ordering and output truth. The new parser must not
rerun the doctor or reimplement SARIF counts.

### Action tests are mostly structural plus real uses

- `tests/test_action_metadata.py` pins wrapper structure, package contents,
  release order, and full-SHA Action dependencies.
- `.github/workflows/action-self-test.yml` runs bundled scan/drift, exact npm
  override, security failure, baseline maintenance, and invalid-command cases
  through `uses: ./`.
- `bin/action-report.test.js` unit-tests the post-run SARIF/output helper.
- `package.json` runs `node --test bin/*.test.js`; `files: ["bin", ...]` ships
  non-test helpers.

### Action metadata inputs are strings

Composite Action metadata does not provide an array-valued input contract.
Therefore the structured value must be encoded as a string and parsed by the
Action implementation. JSON is the existing standard-library, language-neutral
format and preserves exact argv boundaries.

## Target contract

1. Add optional input `args-json`:

   ```yaml
   args-json:
     description: "JSON array of exact extra CLI arguments."
     required: false
     default: ""
   ```

2. `args-json` decodes to an array of strings. Example:

   ```yaml
   args-json: >-
     ["--baseline", ".ai-harness-doctor/drift baseline.json",
      "--check-baseline"]
   ```

3. Legacy `args` remains backward-compatible:
   - empty → no extra args;
   - parse only the first line;
   - split on spaces/tabs exactly as current Bash `read -r -a`;
   - quotes/backslashes remain ordinary characters;
   - do not upgrade legacy input into shell/shlex semantics.
4. `args` and `args-json` are mutually exclusive. Both non-empty fails before
   CLI execution and before any Action output/summary is written.
5. Structured validation fails closed before CLI execution for:
   - invalid JSON;
   - non-array root;
   - non-string element;
   - NUL/CR/LF in an element;
   - more than 128 extra arguments;
   - one argument over 16 KiB of UTF-8;
   - raw `args-json` input over 64 KiB of UTF-8.
6. Empty strings are permitted as exact argv elements; the CLI may reject them
   according to its own parser.
7. Command stays restricted to `scan|drift`.
8. The CLI process receives:
   `command`, `path`, `--sarif`, then exact extra args.
9. Execute with Node `spawnSync` / `shell: false`; never use `eval`, `sh -c`,
   template interpolation into executable script text, or shell quoting.
10. Write child stdout directly to the requested SARIF file and inherit/pass
    stderr without buffering unbounded output.
11. Preserve exact exit semantics:
    - normal exit code `0..255` returned unchanged;
    - signal/null status maps to operational exit `1`;
    - spawn error emits one actionable, value-safe diagnostic and exits `1`;
    - argument validation failure maps to `2`.
12. Preserve Action report order:
    - if the CLI emitted valid SARIF (including a non-zero quality gate), run
      `action-report.js` once, then restore the CLI exit;
    - if validation/spawn failed before valid SARIF, do not fabricate outputs;
    - a report failure after CLI success remains fatal.
13. Bundled and npm-override CLI paths use the same helper.
14. `args-json` is included in Marketplace metadata, all seven READMEs, and
    `SKILL.md`; legacy `args` is explicitly described as whitespace-only.
15. Node 16 standard library only; no runtime dependency.

## Design

### One deep Action-run helper

Add `bin/action-run.js`, shipped in the npm package, with a small public module
interface for tests:

```javascript
parseExtraArgs({ argsJson, legacyArgs }) -> string[]
buildCliArgs({ command, repoPath, extraArgs }) -> string[]
runCli({ cli, sarifFile, command, repoPath, argsJson, legacyArgs }, deps)
```

The CLI helper should:

- validate command and inputs;
- parse exact argv;
- open the SARIF destination with stdlib `fs`;
- call `spawnSync(process.execPath, [cli, ...argv], { shell: false, ... })`;
- direct stdout to the file descriptor and stderr to the parent;
- close the descriptor in `finally`;
- return the exact child status without parsing SARIF.

Keep `action-report.js` as the only SARIF/output/summary parser.

### Thin composite script

`action.yml` continues to own:

- bundled/npm install selection;
- capturing the CLI helper status;
- invoking `action-report.js`;
- final status precedence.

It passes all Action inputs through `env`, including `INPUT_ARGS_JSON`. No input
value should be interpolated into shell source.

The Bash block should not build `run_args` anymore. It invokes:

```bash
node "$ACTION_PATH/bin/action-run.js" \
  "$cli" "$INPUT_SARIF_FILE" "$INPUT_COMMAND" "$INPUT_PATH"
```

The helper reads the two extra-args inputs from environment, or accepts all
values through explicit opaque argv plus env. Prefer env for user-controlled
JSON to match privileged-input hardening conventions.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Node tests | `node --test bin/*.test.js` | all pass |
| Metadata tests | `python3 -m unittest tests.test_action_metadata -v` | all pass |
| Full gate | `npm run check` | all lint/tests pass |
| README sync | `python3 scripts/check_readme_sync.py` | seven READMEs aligned |
| Action lint | `actionlint` | exit 0 |
| Self scan | `python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json --check-baseline --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts --no-report-file` | exit 0 |
| Self drift | `python3 scripts/check_drift.py . --strict` | 100/100 Grade A |
| Self eval | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | 34/34 Grade A |
| Pack | `npm pack --dry-run --json` | includes `bin/action-run.js` |

## Scope

**In scope**:

- `action.yml`
- new `bin/action-run.js`
- new `bin/action-run.test.js`
- `tests/test_action_metadata.py`
- `.github/workflows/action-self-test.yml`
- `.github/workflows/release.yml` only where tagged/published Action validation
  must exercise or assert the new helper/package content
- `package.json` only if scripts/files need adjustment
- `RELEASING.md`
- `references/maintenance-contract.md`
- all seven READMEs and `SKILL.md`
- `plans/054-add-structured-action-args.md`
- `plans/README.md`

**Out of scope**:

- Removing or changing legacy `args`.
- A shell/shlex parser for legacy input.
- Adding typed booleans for every scan/drift option.
- Expanding Action command beyond `scan|drift`.
- Running eval/review/plugins automatically.
- Changing SARIF/output schemas or status precedence.
- Automatically uploading SARIF to Code Scanning.
- Changing guard templates that invoke the CLI directly.
- Third-party runtime dependencies or `@actions/core`.
- Secrets, release credentials, Marketplace categories, or remote settings.

## Git workflow

- Branch: `feat/054-structured-action-args`.
- Commit: `feat(action): add structured extra arguments`.
- One focused feature PR; do not push directly to `main`.
- Wait for all nine required checks before squash merge:
  `drift`, `lint`, Node 16/20/22, Python 3.9/3.10/3.12, and `self-test`.
- This is a backward-compatible public feature and therefore minor-release
  material under repository policy.

## Steps

### Step 1: Characterize legacy behavior and structured validation

Add `bin/action-run.test.js` before implementation.

Legacy cases:

- empty input;
- repeated spaces/tabs;
- quote characters remain literal/split;
- multiline keeps first line only;
- no shell metacharacter execution.

Structured cases:

- path containing spaces preserved as one item;
- repeated flags and empty string preserved in order;
- malformed/non-array/non-string/control-byte/size-limit inputs fail;
- Unicode limit cases prove bounds use `Buffer.byteLength(..., "utf8")`;
- legacy + structured conflict fails.

**Verify**:

```bash
node --test bin/action-run.test.js
```

Expected before implementation: module missing/test RED. After each vertical
slice: the corresponding case passes.

### Step 2: Implement parser and exact process runner

Implement `action-run.js` with injectable `spawnSync`/filesystem seams only
where needed for deterministic tests.

Test:

- exact `process.execPath` + CLI argv;
- `shell: false`;
- stdout fd points to SARIF file;
- stderr inherited;
- environment inherited without logging;
- exact normal exit;
- spawn error and signal/null handling;
- descriptor closes on every branch;
- no CLI spawn for parse/validation errors.

Do not parse SARIF here.

**Verify**: all Node tests pass on Node 16/20/22-compatible syntax.

### Step 3: Wire the composite Action

Add `args-json` metadata/env and replace Bash argv construction with the helper.
Keep npm install, report ordering, and final status precedence unchanged.

Update structural tests to assert:

- `INPUT_ARGS_JSON` is passed only via env;
- `read -r -a` no longer owns structured execution;
- helper runs once;
- report helper still runs once after CLI helper;
- no `eval`, `sh -c`, `bash -c`, or `|| true`;
- `args` and `args-json` descriptions state their distinct contracts.

**Verify**:

```bash
python3 -m unittest tests.test_action_metadata -v
node --test bin/*.test.js
```

### Step 4: Add real composite fixtures

In `.github/workflows/action-self-test.yml`, change/add a baseline-maintenance
fixture whose repository directory **and baseline filename contain spaces**.
Pass:

```yaml
args-json: >-
  ["--baseline",
   "${{ runner.temp }}/resolved baseline repo/.ai-harness-doctor/drift baseline.json",
   "--check-baseline"]
```

Assert the Action reports `status=maintenance`,
`resolved-baseline-count=1`, then restores the expected non-zero exit.

Also add `continue-on-error` negative real-Action cases for:

- malformed JSON;
- both `args` and `args-json`;
- a structured shell-metacharacter element proving no side-effect file is
  created before argparse rejects it.

Static unit tests do not replace these `uses: ./` cases.

### Step 5: Keep release and package proof current

Ensure:

- `npm pack --dry-run --json` includes `bin/action-run.js`;
- tagged bundled preflight references the helper through `uses: ./`;
- published floating Action likewise contains/runs it;
- release structural tests assert helper inclusion/order where appropriate;
- no post-publish workflow needs a duplicate parser.

Run `actionlint` v1.7.12 (or the repository-pinned/current documented version)
over all workflows and `action.yml` where supported.

### Step 6: Document the public contract

All seven READMEs use byte-identical fenced YAML showing `args-json` for a
space-bearing baseline path. Prose explains:

- prefer `args-json` for exact/repeated/path values;
- legacy `args` is first-line whitespace splitting only;
- both inputs are mutually exclusive;
- neither input is shell-evaluated.

Update `SKILL.md`, `references/maintenance-contract.md`, and `RELEASING.md`.

**Verify**: README sync passes; no paragraph exceeds the readability budget.

### Step 7: Gates and merge

Run every command in the command table, perform a two-axis Standards/Spec
review, then open one implementation PR. Wait for all nine contexts before
squash merge.

## Test plan

- Parser: exact structured argv, legacy byte-compatible splitting, all malformed
  and limit cases, mutual exclusion.
- Runner: argv/order, shell false, fd lifecycle, stderr, exact exit and failures.
- Composite: real path-with-spaces maintenance, malformed/conflict/metacharacter
  failures, no side effects, outputs before quality-gate failure.
- Structural: metadata, env-only user input, helper/report order, package files,
  release pre/post coverage.
- Docs/actionlint/full matrix/self-bootstrap.

## Done criteria

- [ ] `args-json` preserves a baseline/rules path containing spaces as one argv
      item through a real `uses: ./` invocation.
- [x] Legacy `args` remains byte-compatible and documented as whitespace-only.
- [x] Both inputs and every malformed/oversized structured input fail before
      CLI execution.
- [x] No input reaches a shell interpreter or executable script text.
- [x] CLI/report exit and output ordering remain unchanged.
- [x] Bundled and npm-override paths share the helper.
- [x] Helper is shipped and release pre/post Action proof remains current.
- [x] Seven READMEs, `SKILL.md`, maintenance/release docs are synchronized.
- [x] `actionlint` and local gates pass.
- [ ] All nine PR checks pass; implementation is
      squash-merged.

## STOP conditions

Stop and report back if:

- composite Action metadata cannot expose a backward-compatible string input;
- exact argv requires shell evaluation or a runtime dependency;
- legacy `args` behavior must change;
- output/report ordering or exit precedence must change;
- helper cannot stream SARIF stdout without unbounded buffering;
- npm package allowlist excludes the helper and cannot be updated compatibly;
- release proof would require publishing an unverified version;
- actionlint or any required CI context is red/pending at merge time.

## Maintenance notes

- `action-run.js` owns only input/argv/process execution. `action-report.js`
  remains the sole SARIF/output/summary authority.
- Treat all Action inputs as untrusted strings. Pass them through env/argv,
  validate, and never interpolate into executable shell text.
- Any new structured option should compose through `args-json`; do not grow one
  Action input per CLI flag without a product-level reason.
- Review limits as abuse bounds, not CLI semantics. Raising them requires tests
  and does not justify shell parsing.
