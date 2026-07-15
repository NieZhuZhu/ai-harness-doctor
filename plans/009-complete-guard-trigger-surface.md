# Plan 009: Make PR guard triggers cover every security and semantic scan input

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat b3dd9e3..HEAD -- assets/agent-tools.json scripts/scan.py scripts/registry.py assets/guard/harness-drift.yml .github/workflows/harness-drift.yml tests/test_action_metadata.py tests/test_cli.py README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md`
> If any in-scope file changed, compare the current-state excerpts below with
> live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: security / correctness / CI
- **Planned at**: commit `b3dd9e3`, 2026-07-15

## Why this matters

The shipped GitHub PR guard runs the complete scan gate, including
`--fail-on-security`, but its `pull_request.paths` list watches only a subset of
the files the scanner consumes. A PR that changes MCP settings, Claude
permissions/hooks, nested agent rules, or several supported ecosystem manifests
can introduce a HIGH security finding or semantic contradiction without
starting the guard. The weekly checkup may find it later, but the documented
“PR hard block” guarantee is false for those changes.

The trigger surface should be derived from the same registry/fact vocabulary as
the scan rather than maintained as another drifting list.

## Current state

- `assets/guard/harness-drift.yml:4-21` watches:

  ```yaml
  paths:
    - package.json
    - package-lock.json
    - pnpm-lock.yaml
    - Makefile
    - pyproject.toml
    - AGENTS.md
    - CLAUDE.md
    - .cursorrules
    - .windsurfrules
    - .github/copilot-instructions.md
    - GEMINI.md
    - .clinerules
    - .cursor/rules/**
    - .ai-harness-doctor/scan-baseline.json
    - .github/workflows/**
  ```

- `.github/workflows/harness-drift.yml:8-27` has a similar adapted list plus
  local source paths.

- The scan security surface is broader:
  `scripts/scan.py:78-96` reads `.mcp.json`, `.cursor/mcp.json`,
  `.vscode/mcp.json`, `.gemini/settings.json`,
  `.claude/settings.json`, `.claude/settings.local.json`, subagents, commands,
  and settings hooks/permissions.

- The config-file registry at `assets/agent-tools.json:3-90` additionally scans:
  - `AGENT.md`, `CLAUDE.local.md`, nested `**/CLAUDE.md`;
  - `.cursor/rules/*.md`;
  - `.windsurf/rules/*`;
  - `.github/instructions/*.instructions.md`;
  - nested Gemini/Cline/Continue/Roo/Trae files.

- `scripts/scan.py:206-231` recognizes Go, Node, Python, Rust, Ruby, PHP, Java,
  .NET, Elixir, Dart, and Swift manifests. Semantic facts also consume runtime
  pins and lockfiles from `scripts/facts.py`/`scripts/semantic.py`.

- `assets/guard/harness-drift.yml:40-56` nevertheless executes:

  ```bash
  scan . --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts
  drift . --strict
  ```

- `README.md:174-179` describes the PR gate as defense against hook bypass and
  claims refactors necessarily touch watched files. The uncovered settings and
  MCP files disprove that assumption.

- Existing tests (`tests/test_cli.py:104-149`,
  `tests/test_action_metadata.py:94-145`) check a few literal trigger lines but
  do not compare workflow paths with the scanner's input contract.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Metadata/guard tests | `python3 -m unittest discover -s tests -p 'test_action_metadata.py' -v && PYTHONPATH=tests python3 -m unittest tests.test_cli -v` | all pass |
| Registry consistency | `python3 -m unittest discover -s tests -p 'test_registry_consistency.py' -v` | all pass |
| Workflow lint | `go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7` | exit 0 |
| Template lint | `go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7 assets/guard/harness-drift.yml` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | OK |
| Full gate | `npm run check` | exit 0 |
| Self guard | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts && python3 scripts/check_drift.py . --strict` | exit 0; drift grade A |

## Scope

**In scope**:

- `assets/agent-tools.json`
- `scripts/registry.py`
- `scripts/scan.py` only if trigger metadata must move there
- `assets/guard/harness-drift.yml`
- `.github/workflows/harness-drift.yml`
- `tests/test_action_metadata.py`
- `tests/test_registry_consistency.py`
- `tests/test_cli.py`
- synchronized READMEs
- `SKILL.md`
- `AGENTS.md`
- `plans/README.md`

**Out of scope**:

- Changing scan finding logic or severity.
- Changing GitLab/Codebase event matching; this plan addresses GitHub path
  filtering.
- Enabling remote repository security settings.
- Running the GitHub workflow on every PR with no path filter unless deriving a
  complete stable filter proves infeasible.
- Adding a general user ignore/config language.

## Git workflow

- Branch: `fix/complete-guard-trigger-surface`
- Commit: `fix(guard): cover every scanned PR input`
- One focused PR, squash-merge only after all CI checks pass.
- Do not publish a version in this PR.

## Steps

### Step 1: Define the trigger contract in one deterministic source

Add machine-readable trigger metadata rather than another test-only list. The
preferred shape is:

- registry tool entries continue owning their instruction `scan_patterns`;
- one registry/helper constant owns extended surfaces (MCP/settings/hooks/
  commands/subagents), project fact files, runtime pins, lockfiles, and the
  baseline path;
- a helper returns normalized GitHub path globs in deterministic order.

The contract must include at least:

- every canonical/tool `scan_pattern`;
- every extended surface from `MCP_CONFIG_FILES`, `SUBAGENT_PATTERNS`,
  `COMMAND_PATTERNS`, and settings files;
- fact inputs for D1/D2/D6/D7/D8 and semantic analysis:
  `package.json`, relevant lockfiles/workspace files, Makefiles, Python/Go/Rust/
  Ruby/Java/PHP/.NET/Elixir/Dart/Swift manifests and version pins;
- `.gitignore` because ignored dotenv/path classification depends on it;
- `.ai-harness-doctor/scan-baseline.json`;
- `.ai-harness-doctor/rules/**` only if custom rules are ever enabled by a
  shipped guard (currently they are not; document the decision).

Normalize `**/` forms deliberately. GitHub workflow path syntax and Python glob
syntax are not assumed byte-identical; conversion must be explicit and tested.

**Verify**: unit tests show every scanner input family maps to at least one
GitHub trigger glob and output order is stable.

### Step 2: Generate or validate the shipped GitHub path list

Choose one maintainable mechanism:

1. generate the `paths:` block in `assets/guard/harness-drift.yml` from the
   helper as part of an existing repo-maintenance generator; or
2. keep the YAML human-edited but add a deterministic contract test that parses
   its path lines and requires a superset of the helper output.

Prefer generation if it can be added without introducing a second YAML
templating system. If keeping a validated list, include a clear source comment
above it.

The test must fail if a future registry tool or semantic fact input is added
without updating the guard trigger. Do not use PyYAML; the project is stdlib
only and static text helpers already exist in `tests/test_action_metadata.py`.

**Verify**: deliberately remove `.mcp.json` in a local scratch copy of the text
and confirm the contract helper reports it missing; restore it before
continuing.

### Step 3: Synchronize the self-bootstrap workflow

Update `.github/workflows/harness-drift.yml` with the same consumer input paths,
plus repository-maintenance paths required to test unmerged local code
(`scripts/**`, `bin/**`, tests/metadata as appropriate).

Keep the documented adapted-copy distinction:

- shipped template executes packaged CLI;
- self workflow executes local CLI/scripts;
- common external input paths must stay synchronized.

Add tests that compare the common trigger subset while allowing the self
workflow's explicit local-only additions.

**Verify**: actionlint passes and a static test proves both workflows cover
MCP/settings/nested config and ecosystem fact inputs.

### Step 4: Add behavior-focused trigger regressions

In `tests/test_action_metadata.py` and/or `tests/test_cli.py`, assert examples
from each high-risk family:

- security: `.mcp.json`, `.claude/settings.json`,
  `.claude/settings.local.json`;
- nested configs: `**/CLAUDE.md`, `.github/instructions/**`,
  `.cursor/rules/**`, `.clinerules/**`, `.continue/rules/**`;
- semantic facts: representative Node, Python, Go, Rust, Java, Ruby manifests
  and runtime pins;
- baseline: `.ai-harness-doctor/scan-baseline.json`;
- local self-only code paths.

Avoid a fragile assertion for every formatting line; derive expected sets and
compare normalized values.

**Verify**: focused tests pass on Python 3.9 and 3.12.

### Step 5: Correct the public guarantee and maintenance rules

Update synchronized README guard prose and `SKILL.md` to explain that the path
filter is generated/validated from the scan input registry. Update `AGENTS.md`
with the invariant that adding a scanned surface or fact file must update the
guard trigger source and tests.

Do not claim custom plugins are executed in CI unless `--allow-plugins` is
actually enabled.

**Verify**: docs sync, full gate, self scan, and strict drift.

## Test plan

- Contract tests for registry-input → GitHub-glob mapping.
- Template vs. self-workflow common-set comparison.
- Representative high-risk paths from security, config, and every ecosystem.
- Future-registry-entry test: add a synthetic registry entry in-memory and
  prove it affects expected triggers, without modifying the fixture file.
- Installer end-to-end test still writes the exact validated template.
- actionlint on both repository and shipped workflow.

## Done criteria

- [ ] A PR touching `.mcp.json` or Claude settings triggers the GitHub guard.
- [ ] Every registered instruction config pattern has a corresponding trigger.
- [ ] Every semantic/drift fact input family has a corresponding trigger.
- [ ] Shipped and self-bootstrap common path sets cannot silently diverge.
- [ ] Adding a new scanned tool/file family fails CI until its trigger contract
      is handled.
- [ ] No custom plugin execution is implied or enabled accidentally.
- [ ] `npm run check` and actionlint pass; self-drift remains grade A.
- [ ] No files outside Scope are modified.

## STOP conditions

- GitHub path filters cannot represent a scanner pattern without materially
  over-triggering or missing nested files; report the exact mismatch before
  choosing “all PRs.”
- The only viable solution requires executing untrusted custom plugins in PR CI.
- A registry change would alter scan behavior rather than adding trigger-only
  metadata.
- An in-scope workflow changed semantically since `b3dd9e3`.
- Verification fails twice after a reasonable correction.

## Maintenance notes

The trigger list is part of the security boundary, not workflow decoration.
Reviewers should reject future scanner inputs that are not represented in this
contract. Weekly checkup remains defense in depth; it is not a substitute for
blocking a PR that directly edits the unsafe input.
