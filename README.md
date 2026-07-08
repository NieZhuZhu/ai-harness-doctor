**English** | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

# 🩺 AI Harness Doctor

**Your AI coding agent is confidently following stale instructions.** `CLAUDE.md`, `.cursorrules`, `GEMINI.md`, and `AGENTS.md` quietly drift apart until agents run scripts that no longer exist, edit paths that already moved, and teach `npm` in a repo that switched to `pnpm`.

AI Harness Doctor makes that drift visible, consolidates every scattered agent config into one canonical `AGENTS.md`, and guards it so your repo forgets less silently — for Claude Code, Codex, Cursor, Gemini, and plain CI. One zero-install `scan` gives you a full checkup: inventory, conflict evidence, a security audit, missing-infrastructure gaps, and a tech-stack snapshot.

[![CI](https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml/badge.svg)](https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml)
[![npm version](https://img.shields.io/npm/v/ai-harness-doctor.svg)](https://www.npmjs.com/package/ai-harness-doctor)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![Node >=16](https://img.shields.io/badge/Node-%3E%3D16-green.svg)

> **In our 14-task benchmark, canonicalizing one repo took agents from 6/28 → 28/28 correct answers — and eliminated the flip-flopping where the same question got different answers on different runs.** [See the numbers ↓](#benchmark)

Try it in one command — no install, nothing written to your repo:

```bash
npx ai-harness-doctor scan .
```

## Why

Agent config drift is a repo disease. One tool reads `CLAUDE.md`, another reads `.cursorrules`, another reads `GEMINI.md`, and each file slowly becomes its own folklore: old commands, moved paths, copied style rules, contradictory package managers, and context files large enough to be truncated.

The painful part is that the agent sounds confident while following stale instructions. A new maintainer asks for the test command and gets a script that no longer exists. A refactor moves `src/components/`, but the rule file still points to `app/ui/`. A team changes npm to pnpm, but three agent surfaces keep teaching npm.

AI Harness Doctor makes that drift visible, helps a human or agent write one canonical `AGENTS.md`, downgrades old tool files to small pointers, and installs guards so the repo can forget less silently.

In our 14-task benchmark, a canonicalized repo took agents from 6/28 to 28/28 correct answers — see [Benchmark](#benchmark).

## User stories

| Persona | Pain | Commands | Outcome |
|---|---|---|---|
| New maintainer | You inherit a legacy repo with a 2-year-old `CLAUDE.md`, three generations of `.cursorrules`, and agents running nonexistent scripts. | `scan` → `/harness-treat` | You get file:line evidence, adjudicate conflicts, and replace folklore with one `AGENTS.md`. |
| Mixed-tool team | Cursor, Claude Code, and Codex users keep forking rule files every week. | `plan` → `stubs --apply` → `guard --apply` | Tool-specific files become stubs, and CI blocks re-divergence. |
| Silently rotting repo | The repo migrated npm→pnpm, directories moved, and docs never caught up. | `drift . --strict` | The path-aware drift gate catches the PR before stale instructions land. |
| Skeptic teammate | Someone calls agent config files cargo cult. | `eval --tasks ...` before/after | Real numbers settle the argument: correctness, instability, latency, and captured cost. |
| OSS maintainer | AI-generated PRs follow the wrong conventions. | `AGENTS.md` + `guard --apply` | Contributors' agents read the maintenance contract and self-check changes. |

## Quick Start

### Fastest path

Zero-install, read-only checkup — one command surfaces your harness's inventory, conflict evidence (with file:line), security findings, missing-infrastructure gaps, and a tech-stack snapshot, in seconds:

```bash
npx ai-harness-doctor scan .
```

Ready to fix it? Install the Claude Code skill and let the agent drive the full flow:

```bash
npx ai-harness-doctor install
```

Then in Claude Code:

```text
/harness-doctor .
```

Answer the conflict adjudication questions. The tool reports evidence; you decide what is true for the repo.

### Apply to your repo in 3 steps

There is deliberately no true one-click migration. Phase 1 contains semantic decisions: the tool never decides pnpm-vs-npm, test-vs-test:unit, or old path-vs-new path for you.

```bash
npx ai-harness-doctor scan .
npx ai-harness-doctor plan . -o merge-plan.md
# Write AGENTS.md from the plan, then:
npx ai-harness-doctor validate .
npx ai-harness-doctor stubs . --apply
npx ai-harness-doctor guard . --apply
```

Three ways to write `AGENTS.md`:

1. Hand-write it from `merge-plan.md` plus `assets/AGENTS.template.md`.
2. Ask your coding agent to write it, using the plan as evidence.
3. Use `/harness-treat .`: it reads the plan, asks you per conflict, writes the file, then validates.

### Requirements

- Target must be a git repo.
- Node >=16 for the `ai-harness-doctor` CLI.
- Python >=3.9, stdlib-only, for deterministic scan/plan/validate/stubs/drift/eval scripts.
- `AGENTS.md` must exist before `stubs` or `guard` writes anything.

### Install matrix

```bash
npx ai-harness-doctor install                         # Claude Code, user-level
npx ai-harness-doctor install --agent codex
npx ai-harness-doctor install --agent cursor --project
npx ai-harness-doctor install --agent gemini
npx ai-harness-doctor install --agent all --project
npx ai-harness-doctor install --link                  # link to a global package
```

### Automation matrix

| Step | CI-safe? | Writes? | Note |
|---|---:|---:|---|
| `scan` | ✅ | ❌ | Exits 0 by default; inventory, evidence, a security checkup, a gap analysis of missing harness infrastructure, and a tech-stack project snapshot. In markdown mode it also writes the full JSON report to a temp file and prints its path. `--fail-on-security` exits 2 on HIGH findings; `--fail-on-gaps` exits 3 on ERROR gaps. |
| `plan` | ✅ | Optional output file | Scaffolds a merge plan; does not merge. |
| Write `AGENTS.md` | ❌ | ✅ | Human-or-agent semantic step. |
| `validate` | ✅ | ❌ | Checks whether canonical `AGENTS.md` contains the required sections. |
| `stubs` | ✅ | With `--apply` | Requires clean tree unless `--force`. |
| `guard` | ✅ | With `--apply` | Requires git repo and existing `AGENTS.md`. |
| `drift` | ✅ | ❌ | Fails on blocking drift; `--strict` promotes notices. |

### Uninstall & rollback

```bash
npx ai-harness-doctor guard . --remove --apply
npx ai-harness-doctor uninstall --agent all
```

`guard --remove` is marker-precise: it removes only its own managed snippets and will not touch a foreign pre-commit hook. Everything else is git-revertable.

## Slash commands

| Command | Input | What the agent does | Where it STOPS | What you decide |
|---|---|---|---|---|
| `/harness-doctor` | Repo path, usually `.` | Runs the full checkup→treat→follow-up flow; eval only when requested. | Before semantic conflict resolution and before optional eval. | Migration scope, conflict truth, whether to install guards. |
| `/harness-scan` | Repo path | Runs Phase 0 inventory, size, overlap, conflict, and nested-agent detection. | After the health report. | Whether to treat the whole repo, a subdir, or selected files. |
| `/harness-treat` | Repo path, optional scan/plan output | Builds a merge plan, asks about conflicts, writes/validates canonical `AGENTS.md`, previews stubs. | Until every conflict has an explicit answer. | Which command/path/style/version is canonical. |
| `/harness-drift` | Repo path | Runs drift checks and explains repairs. | After checks pass or repair advice is given. | Whether to update repo reality or update `AGENTS.md`. |
| `/harness-eval` | Repo path + task file/results | Runs or compares before/after tasks. | When metrics or a manual protocol are produced. | Task set, runner, and whether the evidence is enough. |

## Updating

Copy installs are tracked in `~/.ai-harness-doctor/manifest.json`. To redeploy the newest package files to everything previously installed, run:

```bash
npx ai-harness-doctor@latest update
```

Interactive commands check npm at most once per day and may print an update hint such as `npx ai-harness-doctor@latest update`; set `AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1` to disable that check. Bare `npx` CLI users should pin `ai-harness-doctor@latest` when they want the newest one-off command.

For true hot updates, install the package persistently and link the payload:

```bash
npm i -g ai-harness-doctor
ai-harness-doctor install --link
npm update -g ai-harness-doctor
```

With `--link`, Claude points `~/.claude/skills/ai-harness-doctor` at the global package and other adapters point at the same package root, so `npm update -g ai-harness-doctor` updates the playbook everywhere instantly. On Windows, directory links use junctions.

## Long-term guard

> The guarantee is a detection guarantee, not an update guarantee: doc-vs-repo consistency becomes a machine-checkable condition that can fail in three places — pre-commit, PR, and a weekly checkup. Forgetting is no longer silent.

Install after the treat phase has produced a canonical root `AGENTS.md`:

```bash
npx ai-harness-doctor guard . --apply
```

The CI gate is provider-aware: pass `--provider github|gitlab|codebase` (default `auto`) to install the matching CI files. See the [`guard`](#command-reference) command reference for the per-provider file layout.

Defense in depth, strongest to weakest:

1. **Pre-commit hard block** — defends against local edits that make `AGENTS.md` stale before they leave the machine. `AI_HARNESS_DOCTOR_SKIP=1` is an explicit, auditable bypass, not a silent pass.
2. **Path-aware PR gate** — defends against hook bypass. Refactors necessarily touch watched files such as `package.json`, `Makefile`, `AGENTS.md`, and tool stubs, so CI re-checks drift on the PR.
3. **Weekly checkup + deduped issue** — defends against slow rot that touches no watched file: a new lint tool, CI Node bump, or convention change that arrives outside the usual path set.
4. **Maintenance contract in `AGENTS.md`** — defends at the source of agent behavior. Refactors are often done by agents, and every agent reads `AGENTS.md`; the doc instructs its own maintenance.

| Refactor/change | Check that should catch it |
|---|---|
| Change scripts or `Makefile` targets | D1 command drift |
| Move/delete documented paths | D2 path drift |
| Sneak rules back into `CLAUDE.md` or `.cursorrules` | D3 stub regrowth |
| Let `AGENTS.md` bloat past useful context size | D4 size/context risk |
| Bump Node version or switch package manager without updating `AGENTS.md` | D6 fact drift |

Why detection over regeneration? Silently “fixing” drift removes human awareness. AI Harness Doctor surfaces drift instead, because the important part is not rewriting files; it is making the team notice that repo truth and agent truth diverged. See [Positioning & Non-goals & Comparison](#positioning--non-goals--comparison).

## Works with

| Surface | Support |
|---|---|
| Claude Code | Native skill plus slash commands under `.claude/commands` or `~/.claude/commands`. |
| OpenAI Codex CLI | Prompt adapters for `~/.codex/prompts/`. |
| Cursor | Command adapters for `.cursor/commands/`. |
| Gemini CLI | TOML custom command adapters for `~/.gemini/commands/harness/`. Google retired Gemini CLI for individual tiers on 2026-06-18; enterprise Gemini Code Assist is unaffected, and these adapters still work for enterprise/existing installs. |
| Windsurf / Cline / others | Universal mode: point the agent at the installed playbook and say “run phase N”. |
| MCP clients | `ai-harness-doctor mcp` exposes `harness_scan`/`drift`/`validate`/`plan` as MCP tools over stdio. |
| Humans & CI | Plain `npx ai-harness-doctor ...`; no agent required. |

Honest note: non-Claude adapters are thin pointers and lightly verified. If a command format changed, please file an issue.

## The four phases

| Phase | Script | Artifact | Stop condition |
|---|---|---|---|
| 0 — Checkup / scan | `scripts/scan.py` | Human or JSON health report | Stop at user confirmation of migration scope. |
| 1 — Treat / canonicalize | `scripts/canonicalize.py --plan`, `--write-stubs`, `--validate` | Merge plan, canonical `AGENTS.md`, minimal stubs | Stop until every conflict has human adjudication. |
| 2 — Follow-up / drift guard | `scripts/check_drift.py` | Drift report and CI/pre-commit exit codes | Stop when checks pass or repair advice is given. |
| 3 — Efficacy eval | `scripts/eval_run.py` | Before/after JSON and Markdown report | Stop when metrics are produced. |

## Command reference

<details>
<summary><code>install</code></summary>

Installs the skill, slash commands, and/or adapter prompts.

| Agent | Default destination | With `--project` |
|---|---|---|
| `claude` | `~/.claude/skills/ai-harness-doctor`, `~/.claude/commands/` | `.claude/skills/ai-harness-doctor`, `.claude/commands/` |
| `codex` | `~/.codex/prompts/` + shared payload | Same adapter location; project affects payload path. |
| `cursor` | `.cursor/commands/` | `.cursor/commands/` in the target project. |
| `gemini` | `~/.gemini/commands/harness/` + shared payload | Same command location; project affects payload path. |

Adapters replace `{{PLAYBOOK}}` with the installed playbook path. Installs are recorded in `~/.ai-harness-doctor/manifest.json`, are idempotent, and can be refreshed by `update`. `--link` points at a global package instead of copying payload files; the CLI blocks unsafe `npx` cache linking and tells you to install globally first.

</details>

<details>
<summary><code>uninstall</code></summary>

Removes installed Claude skill files, slash commands, adapter prompts, and shared payloads for the requested `--agent`. `--agent all` removes every known surface. It also removes matching manifest records.

</details>

<details>
<summary><code>update</code></summary>

Redeploys every manifest-tracked copy install to the current package version. Linked installs refresh command pointers while the payload follows `npm update -g ai-harness-doctor`.

</details>

<details>
<summary><code>guard</code></summary>

Dry-run by default; use `--apply` to write. Requirements: target is a git repo and `AGENTS.md` already exists.

It manages a provider-agnostic core plus a **provider-aware CI gate**:

1. `.git/hooks/pre-commit` drift block.
2. A CI drift/checkup gate whose files depend on `--provider` (see below).
3. A marked maintenance contract in `AGENTS.md`.

`--provider github|gitlab|codebase|auto` (default `auto`) selects which CI files to install. `auto` detects the provider from `.gitlab-ci.yml` and the `origin` remote (github.com → `github`, a host containing `gitlab` → `gitlab`, any other enterprise host such as internal Codebase → `codebase`, no remote → `github`):

| Provider | CI files installed | Wiring note |
|---|---|---|
| `github` | `.github/workflows/harness-drift.yml` path-aware PR gate + `.github/workflows/harness-checkup.yml` weekly scan/drift checkup with a deduped issue. | Runs automatically on GitHub Actions. |
| `gitlab` | An includable `.gitlab/harness-ci.yml` (`harness-drift` on MRs, `harness-checkup` on schedules with an artifact). | Add `include: { local: .gitlab/harness-ci.yml }` to `.gitlab-ci.yml`. |
| `codebase` | A portable `.harness-ci/harness-guard.sh` (`drift`/`checkup` modes) + a wiring `README.md`. | Register the script as an MR check and a scheduled pipeline step. |

`AI_HARNESS_DOCTOR_SKIP=1` is the explicit auditable escape hatch for the local hook. `guard --remove --apply` removes managed snippets, cleans up **all providers'** CI files (so switching providers leaves nothing behind), and restores byte-exact pre-existing hook content when possible. Both install and remove are non-destructive: every managed file carries an `ai-harness-doctor:guard` marker, so `guard --apply` never overwrites a user-edited CI file that lacks the marker (it reports a `manual-merge` and leaves your file untouched), and `--remove` only deletes a managed file when it is byte-identical to what the tool shipped — a hand-extended hook has just its own guard block stripped out, and a modified block is skipped rather than destroyed.

</details>

<details>
<summary><code>scan</code></summary>

Detects five classes: config inventory, size/truncation risk, overlap candidates, conflict candidates with file:line evidence, and nested `AGENTS.md` files. On top of that it answers the complementary question — *what is missing* — via a gap analysis (see below).

It also inventories the **extended harness surface** — MCP servers, subagents, slash commands, hooks, and permission rules — and runs a **security checkup** that flags severity-ranked findings (HIGH/MEDIUM):

- Plaintext secrets (AWS / GitHub / OpenAI / Google / Slack / Anthropic keys, private-key blocks, generic `api_key/secret/token=...`) across instruction and MCP/settings config files.
- Over-broad permissions such as `Bash(*)`, `*`, and `defaultMode: bypassPermissions`.
- MCP hygiene issues: insecure `http://` transports and credential-shaped env literals.
- Risky hook/command bodies: `curl … | bash`, `rm -rf`, `--dangerously-skip-permissions`, and similar.

It exits 0 by default. With `--fail-on-security` it exits `2` when any HIGH-severity finding is present, which is handy as a CI gate.

It also runs a **gap analysis** that diffs the repo against a harness completeness checklist and reports mandatory infrastructure it is *missing* (not just what exists). These static checks are limited to the pieces every healthy harness needs regardless of stack: a canonical root `AGENTS.md` (`G1`), the required `AGENTS.md` sections kept in sync with `assets/AGENTS.template.md` (`G2`), tool stubs that should be minimal pointers to `AGENTS.md` (`G3`), and the drift-guard / weekly-checkup CI workflows (`G4`). Each gap carries a `level` (`ERROR`/`WARN`/`NOTICE`), an `item`, a `message`, and an actionable `suggestion`. With `--fail-on-gaps` it exits `3` when any ERROR-level gap (e.g. a missing root `AGENTS.md`) is present.

For everything that depends on the project's tech stack (rather than being universally required), scan emits a **project snapshot** — a compact, factual description of the repo that an agent/LLM can reason over:

- `tech_stack`: languages / ecosystems detected from their manifests (`go.mod`, `package.json`, `pyproject.toml`, `requirements.txt`, `Cargo.toml`, `pom.xml`, `Gemfile`, `composer.json`, …).
- `existing_files`: CI, git-hook, lint/format, and typecheck config files present, plus whether a drift-guard pre-commit hook is installed.
- `agents_sections`: the H1 sections currently in `AGENTS.md`.
- `maintenance_contract`: whether `AGENTS.md` embeds the maintenance contract.
- `mcp_tools` / `has_permissions`: configured MCP servers and whether permission rules exist.

The stack-dependent judgements that used to be static `G5`–`G8` gaps (pre-commit guard, maintenance contract, MCP config, permission config) are now facts in this snapshot, left for an agent to reason about.

**Full JSON report for agents.** In markdown mode `scan` writes the complete machine-readable report (files, surface, security, `project_snapshot`, and `gaps`) to a stable temp file — `${TMPDIR}/harness-scan-<hash>.json`, where `<hash>` is derived from the resolved repo path — and appends a `## Full JSON report` section pointing to it. An agent driving the workflow can read that file to reason over the snapshot and gaps and plan fixes, without re-parsing the markdown. The `--json` mode already prints the full report to stdout, so no temp file is written there. Use `--no-report-file` to skip writing it.

| Flag | Purpose |
|---|---|
| `--no-security` | Inventory only; skip the security checkup (drops the `security` key). |
| `--fail-on-security` | Exit `2` when any HIGH-severity security finding is present. |
| `--no-gaps` | Skip the missing / gap analysis (drops the `gaps` key). |
| `--fail-on-gaps` | Exit `3` when any ERROR-level harness gap is present. |
| `--no-snapshot` | Skip the project snapshot (drops the `project_snapshot` key). |
| `--no-report-file` | Do not write the full JSON report to a temp file (markdown mode only). |

`--json` returns (existing keys are unchanged — backward compatible):

```json
{
  "files": [],
  "warnings": [],
  "overlaps": [],
  "conflicts": [],
  "nested": [],
  "surface": {
    "mcp_servers": [],
    "subagents": [],
    "commands": [],
    "hooks": [],
    "permissions": []
  },
  "security": [
    { "level": "HIGH", "category": "secret", "path": "", "message": "" }
  ],
  "project_snapshot": {
    "tech_stack": [ { "language": "Go", "markers": ["go.mod"] } ],
    "existing_files": { "ci": [], "hooks": [], "lint_format": [], "typecheck": [], "drift_guard_hook": null },
    "agents_sections": [],
    "maintenance_contract": false,
    "mcp_tools": [],
    "has_permissions": false
  },
  "gaps": [
    { "check": "G1", "level": "ERROR", "item": "Root AGENTS.md", "message": "", "suggestion": "" }
  ]
}
```

`security` findings carry `level` (`HIGH`/`MEDIUM`), `category` (`secret`/`mcp`/`permission`/`hook`/`instruction`), `path`, and a human-readable `message`. With `--no-security` the `security` key is omitted. `gaps` entries carry `check` (`G1`–`G4`), `level` (`ERROR`/`WARN`/`NOTICE`), `item`, `message`, and `suggestion`; with `--no-gaps` the `gaps` key is omitted. `project_snapshot` is omitted with `--no-snapshot`. In markdown mode the same JSON object is also written to `${TMPDIR}/harness-scan-<hash>.json` (unless `--no-report-file` is given).

</details>

<details>
<summary><code>plan</code></summary>

Scaffolds a Phase 1 merge plan from scan output: inventory, overlap clusters, conflict list, and a TODO decision checklist. It explicitly does **not** merge content or choose a side.

It also appends a **"Merge suggestions (semi-automatic)"** section derived from the scan:

- **Overlap consolidation** — each overlap cluster names the canonical file (`AGENTS.md`) and lists the files to reduce to stubs as a checkbox list.
- **Conflict resolutions** — each conflict signal gets ONE recommended value plus its supporting `path:line` evidence as a tickable item. The recommendation is deterministic (most-supported value, ties broken lexicographically).

These are suggestions for human review, not automatic adjudication; the existing inventory/overlap/conflict/TODO sections are preserved.

</details>

<details>
<summary><code>validate</code></summary>

Validates the canonical `AGENTS.md` structure after you write it. It is a read-only passthrough to `scripts/canonicalize.py --validate`.

</details>

<details>
<summary><code>stubs</code></summary>

Downgrades existing tool files to minimal pointers after `AGENTS.md` exists.

| Tool | Downgrade strategy |
|---|---|
| Claude | `CLAUDE.md` / `.claude/CLAUDE.md` import `@AGENTS.md`. |
| Cursor | `.cursorrules` points to `AGENTS.md`; `.cursor/rules` becomes one always-apply pointer. |
| Windsurf | `.windsurfrules` becomes a pointer. |
| Copilot | `.github/copilot-instructions.md` becomes a pointer. |
| Gemini | `GEMINI.md` becomes a pointer and recommends `contextFileName`. |
| Cline | `.clinerules` becomes a pointer. |
| Roo | Detected by `scan` (`.roo/rules/*.md`) but **not** downgraded — a rules-directory tool with no single conventional stub location, so it stays scan-only. |

Dry-run by default. `--apply` requires a clean git tree; `--force` overrides that safety check.

Known tool config files are defined once in `assets/agent-tools.json`, the single registry that `scan`, `stubs`/`canonicalize`, and `drift` all read, so adding a new tool means editing that one file.

</details>

<details>
<summary><code>drift</code></summary>

Checks `AGENTS.md` against repo reality. Exit code is 0 when no blocking drift is found, 1 when errors are found. `--strict` promotes notices to errors.

Example finding lines:

- D1: `Unknown package.json script test:unit-old`
- D2: `Referenced path src/old-components does not exist`
- D3: `Tool stub CLAUDE.md regrew or lost AGENTS.md pointer`
- D4: `AGENTS.md is 41000 bytes, above 32768`
- D5: `Nested AGENTS.md inventory` (informational, non-blocking)
- D6: `AGENTS.md declares Node 18 but .nvmrc pins 20` (fact drift)

**D6 fact drift** cross-validates the *facts* declared in `AGENTS.md` against repo ground truth: the Node version (vs `.nvmrc` and `package.json` `engines.node`) and the package manager (vs the actual lockfile — `package-lock.json`→npm, `pnpm-lock.yaml`→pnpm, `yarn.lock`→yarn). It only flags clear contradictions and stays silent when `AGENTS.md` is silent, so silence never produces a false positive.

**Health score.** All findings (D1..D6) roll up into a 0–100 health score with a letter grade (A ≥90 / B ≥80 / C ≥70 / D ≥60 / F), rendered as a `## Health score` section (e.g. `Score: 85/100 (grade B)`). With `--json` the report gains `score` and `grade` keys alongside the existing fields.

`--min-score N` exits non-zero when the score is below `N` — a CI gate that is independent of `--strict`, so both can apply together.

**Semi-automatic repair: `--fix`.** `--fix` auto-repairs only the safe, mechanical subset of drift — currently **D3 stub regrowth**. Any tool stub that grew real content or lost its `AGENTS.md` pointer is rewritten back to its minimal canonical import-stub form (the stub bodies are reused from `canonicalize.py`, so `--fix` and `stubs`/`--write-stubs` stay in sync).

```bash
npx ai-harness-doctor drift . --fix          # DRY RUN: prints the diff, writes nothing
npx ai-harness-doctor drift . --fix --apply  # actually rewrites the regrown stubs
```

- Default `--fix` is a dry run: it prints a unified diff of what would be rewritten and changes no files.
- `--fix --apply` rewrites the regrown stub files in place.
- Non-safe drift (D1 command drift, D2 path drift, D4 size, and any other semantic drift) is never modified; it is listed under **"needs manual attention"** with copy-pasteable repair guidance.
- A summary line reports `N fixed/fixable, M need manual attention`. The command exits non-zero while any drift remains.

</details>

<details>
<summary><code>eval</code></summary>

Runs or compares before/after agent tasks.

`tasks.json` is an array of task records:

```json
[
  {
    "id": "test",
    "prompt": "What test command should I run? Answer with ONLY the exact command/value, no explanation.",
    "check": { "type": "regex", "value": "pnpm\\s+(run\\s+)?test\\b" },
    "timeout_s": 60
  }
]
```

Checks can be `regex` over the extracted answer, `command` executed in the workdir, or `judge` for open-ended LLM-as-judge grading. For Claude CLI JSON output, grading extracts the `result` field before matching. Usage/cost fields are captured when present. `--compare before.json after.json` writes a Markdown comparison. `--regrade results.json --tasks tasks.json` regrades recorded outputs offline. If the runner binary is missing, the command prints a manual protocol fallback instead of pretending it ran.

**Multi-agent matrix.** Run the same task set across several runners ("agents") and compare them side by side. Provide runners inline with repeatable `--runner-cmd NAME=CMD`, or via `--matrix agents.json` (a mapping of agent name → runner command template). `--matrix-report FILE` writes a Markdown matrix (rows = tasks, columns = agents, cells = pass/fail + duration, plus per-agent pass-rate summary) and `--matrix-json FILE` writes per-agent task records with a `summary` block (`passed`, `total`, `pass_rate`). The single-runner before/after/compare flow is unchanged; matrix mode activates only when `--matrix` and/or `--runner-cmd` are supplied.

```bash
npx ai-harness-doctor eval --tasks tasks.json --workdir . \
  --runner-cmd "claude=claude -p {prompt} --output-format json" \
  --runner-cmd "codex=codex exec {prompt}" \
  --matrix-report matrix-report.md --matrix-json matrix-results.json
```

**LLM-as-judge check.** A task check may use `{ "type": "judge", "rubric": "..." }` for grading that regex cannot express. Grading is delegated to `--judge-cmd "CMD_TEMPLATE"`. The judge receives env `JUDGE_ANSWER`, `JUDGE_RUBRIC`, and `JUDGE_INPUT` (path to a temp JSON `{answer, rubric}`), and template placeholders `{answer}`/`{rubric}`/`{input}` are substituted. It must print `{"passed": bool, "score": number, "reason": "..."}`; if `passed` is omitted, `score >= 0.5` counts as a pass. An offline deterministic judge works for CI.

</details>

<details>
<summary><code>mcp</code></summary>

Starts an MCP (Model Context Protocol) stdio server so agents can call the doctor's read-only capabilities as tools.

```bash
npx ai-harness-doctor mcp   # or directly: node bin/mcp-server.js
```

Transport is JSON-RPC 2.0 over newline-delimited JSON (one JSON object per line on stdin/stdout). Supported methods:

- `initialize` → `{ protocolVersion, capabilities: { tools: {} }, serverInfo: { name, version } }`.
- `notifications/initialized` → notification, no response.
- `tools/list` → advertises `harness_scan`, `harness_drift`, `harness_validate`, `harness_plan`, each with an input schema `{ repo: string (default "."), ... }`.
- `tools/call` → dispatches to the matching Python script and returns `{ content: [{ type: "text", text }] }`.

Tool booleans: `harness_scan` (`json`), `harness_drift` (`json`, `strict`), `harness_validate` (`json`), `harness_plan`. Unknown methods and tools return a JSON-RPC error object.

</details>

Slash command quick refs: `/harness-doctor` full pipeline; `/harness-scan` Phase 0; `/harness-treat` Phase 1; `/harness-drift` Phase 2; `/harness-eval` Phase 3.

Environment variables:

| Variable | Purpose |
|---|---|
| `AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1` | Disable the once-daily npm update nudge. |
| `AI_HARNESS_DOCTOR_SKIP=1` | Explicitly bypass the local pre-commit drift hook. |

`AI_HARNESS_DOCTOR_FORCE_UPDATE_CHECK` and `AI_HARNESS_DOCTOR_REGISTRY` are internal/testing knobs.

## Benchmark

Final verified results from [`benchmark/results/`](benchmark/results/):

| Side | Runs | Passed | Flip-flop tasks | Avg latency/task | Total captured cost |
|---|---|---:|---:|---:|---:|
| BEFORE: conflicting/stale configs | 14 objective tasks × 2 runs | 6/28 (21%) | 2 | 16.0s | $5.82 |
| AFTER: canonical `AGENTS.md` via this tool | 14 objective tasks × 2 runs | 28/28 (100%) | 0 | 11.7s | $4.81 |
| Delta | after - before | +22 correct attempts | -2 | -27% | -17% |

Conflicting configs do not just cause wrong answers; they cause **unstable** answers: the same question flipped between runs for `node` and `moduletype` before canonicalization, and never flipped after.

See [`benchmark/README.md`](benchmark/README.md) for methodology, tasks, grading, and reproduction commands. Honest scope: one demo repo, N=2 runs per side, objective Q&A tasks, runner `claude -p` with Claude CLI 2.1.202.

## Positioning & Non-goals & Comparison

### Positioning

AI Harness Doctor is complementary to Claude Code's official `/init`: `/init` bootstraps a config from scratch, while AI Harness Doctor diagnoses, consolidates, guards, and validates an existing sprawl. Its `SKILL.md` explicitly stays out of `/init`'s lane.

Regeneration and guarding are two valid philosophies. Ruler/rulesync make generated outputs disposable; AI Harness Doctor keeps `AGENTS.md` human-owned and guards it against drift. That is why it prefers detection over silent regeneration: when the repo changes, the team should know the agent contract changed too.

### Non-goals

- No from-scratch init; that is `/init`'s lane.
- Never adjudicates conflicts silently; it shows file:line evidence and asks a human.
- Scripts never do semantic merging.
- No unattended writes: dry-run defaults, `--apply`, and clean-tree checks are intentional.
- No language/framework style-guide generation.
- Not a bulk rules distributor; for 20+ tool fan-out, use rulesync and see the comparison below.
- No telemetry. The only network call is the once-daily npm version check, and it is disable-able.

### Comparison

Legend: ✅ built-in / △ partial or different approach / ❌ not a stated feature.

| Dimension | AI Harness Doctor | [Ruler](https://github.com/intellectronica/ruler) | [rulesync](https://github.com/dyoshikawa/rulesync) |
|---|---|---|---|
| Canonical-source model | △ `AGENTS.md` itself is canonical + minimal stubs. | △ `.ruler/` central source distributes to agent-specific files. | △ `.rulesync/` unified rules generate to 20+ tools. |
| Consolidate FROM existing configs | ✅ Treat phase consolidates existing configs. | ❌ Not a stated feature in their docs. | ✅ Reverse IMPORT from existing `CLAUDE.md` / `.cursorrules`. |
| Conflict detection with file:line evidence | ✅ Scan/plan reports cite file:line evidence. | ❌ Not a stated feature in their docs. | ❌ Not a stated feature in their docs. |
| Overlap % metrics | ✅ Built into scan reports. | ❌ Not a stated feature in their docs. | ❌ Not a stated feature in their docs. |
| Size/truncation warnings | ✅ Built into scan/drift. | ❌ Not a stated feature in their docs. | ❌ Not a stated feature in their docs. |
| Re-divergence guard on hand-edited files | ✅ D3 drift guard catches stub re-divergence. | △ Solves the problem differently by regeneration. | △ Solves the problem differently by regeneration. |
| CI / pre-commit gate | ✅ `guard` suite installs pre-commit, PR gate, and weekly checkup. | △ Can regenerate in CI. | △ Can regenerate in CI. |
| Before/after efficacy eval with real benchmark | ✅ See [`benchmark/`](benchmark/). | ❌ Not a stated feature in their docs. | ❌ Not a stated feature in their docs. |
| Distribution breadth | △ 4 agents + universal pointer. | ✅ Multiple agent-specific outputs. | ✅ 20+ tools. |
| MCP config propagation | ❌ Not supported. | ✅ Built-in MCP config propagation. | ❌ Not a stated feature in their docs. |

As of 2026-07, based on each project's public documentation — see their repos for the latest.

## Releases

- Releases are tag-driven through CI with npm provenance.
- See [`RELEASING.md`](RELEASING.md).
- Every published version has a git tag.

## Repository layout

```text
SKILL.md                         # Skill playbook and phase stop conditions
bin/cli.js                       # npm CLI and installer
bin/mcp-server.js                # MCP stdio server (harness_scan/drift/validate/plan)
commands/                        # Claude Code slash commands
adapters/                        # Codex, Cursor, Gemini, universal pointers
scripts/                         # Python stdlib deterministic mechanics
references/                      # Migration and conflict-resolution references
assets/                          # Templates, guard suite, example tasks
benchmark/                       # Real before/after eval data
tests/                           # stdlib unittest suite
RELEASING.md                     # Tag-driven release checklist
```

## Roadmap v2

- Repo harness-ification: CLI-ize project scripts, add verification gates, and layer docs cleanly.
- Richer eval task packs for more languages, repo shapes, and multi-turn workflows.
- More agent adapters as command formats stabilize.
- Antigravity CLI adapter when its custom-command format is documented.

## Contributing

Bug reports and focused PRs are welcome. Keep scripts deterministic, stdlib-only, and covered by:

```bash
python3 -m unittest discover -s tests -v
```

The repo also ships an npm-driven lint/format/test workflow (dev-only; none of it is bundled into the published package). CI runs the full suite across a Python (3.9/3.10/3.12) and Node (16/20/22) version matrix:

```bash
npm test            # Python unittest + node --test CLI suite
npm run lint        # eslint (bin) + ruff (scripts/tests) + trilingual README heading sync
npm run format      # prettier --write .   (npm run format:py for ruff format)
```

`npm run lint:docs` (aka `scripts/check_readme_sync.py`) enforces that `README.md`, `README.zh-CN.md`, and `README.ja.md` keep an identical heading skeleton, so any structural change to one README must be mirrored in the other two.

## License

MIT. Copyright (c) NieZhuZhu.
