**English** | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

# 🩺 AI Harness Doctor

Doctor for your repo's AI harness: audit, merge, guard, and evaluate scattered agent configs into one canonical `AGENTS.md`.

[![CI](https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml/badge.svg)](https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml)
[![npm version](https://img.shields.io/npm/v/ai-harness-doctor.svg)](https://www.npmjs.com/package/ai-harness-doctor)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![Node >=16](https://img.shields.io/badge/Node-%3E%3D16-green.svg)

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

Install the Claude Code skill and run the doctor in your target repo:

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
| `scan` | ✅ | ❌ | Always exits 0; inventory and evidence only. |
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

Why detection over regeneration? Silently “fixing” drift removes human awareness. AI Harness Doctor surfaces drift instead, because the important part is not rewriting files; it is making the team notice that repo truth and agent truth diverged. See [Positioning & Non-goals & Comparison](#positioning--non-goals--comparison).

## Works with

| Surface | Support |
|---|---|
| Claude Code | Native skill plus slash commands under `.claude/commands` or `~/.claude/commands`. |
| OpenAI Codex CLI | Prompt adapters for `~/.codex/prompts/`. |
| Cursor | Command adapters for `.cursor/commands/`. |
| Gemini CLI | TOML custom command adapters for `~/.gemini/commands/harness/`. Google retired Gemini CLI for individual tiers on 2026-06-18; enterprise Gemini Code Assist is unaffected, and these adapters still work for enterprise/existing installs. |
| Windsurf / Cline / others | Universal mode: point the agent at the installed playbook and say “run phase N”. |
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

It manages four artifacts:

1. `.git/hooks/pre-commit` drift block.
2. `.github/workflows/harness-drift.yml` path-aware PR gate.
3. `.github/workflows/harness-checkup.yml` weekly scan/drift checkup with a deduped issue.
4. A marked maintenance contract in `AGENTS.md`.

`AI_HARNESS_DOCTOR_SKIP=1` is the explicit auditable escape hatch for the local hook. `guard --remove --apply` removes managed snippets and restores byte-exact pre-existing hook content when possible.

</details>

<details>
<summary><code>scan</code></summary>

Detects five classes: config inventory, size/truncation risk, overlap candidates, conflict candidates with file:line evidence, and nested `AGENTS.md` files. It always exits 0.

`--json` returns:

```json
{
  "files": [],
  "warnings": [],
  "overlaps": [],
  "conflicts": [],
  "nested": []
}
```

</details>

<details>
<summary><code>plan</code></summary>

Scaffolds a Phase 1 merge plan from scan output: inventory, overlap clusters, conflict list, and a TODO decision checklist. It explicitly does **not** merge content or choose a side.

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

Dry-run by default. `--apply` requires a clean git tree; `--force` overrides that safety check.

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

Checks can be `regex` over the extracted answer or `command` executed in the workdir. For Claude CLI JSON output, grading extracts the `result` field before matching. Usage/cost fields are captured when present. `--compare before.json after.json` writes a Markdown comparison. `--regrade results.json --tasks tasks.json` regrades recorded outputs offline. If the runner binary is missing, the command prints a manual protocol fallback instead of pretending it ran.

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

## License

MIT. Copyright (c) NieZhuZhu.
