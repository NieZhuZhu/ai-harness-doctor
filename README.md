**English** | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

# 🩺 AI Harness Doctor

Audit, consolidate & guard your repo's AI agent configs (`AGENTS.md` / `CLAUDE.md` / `.cursorrules` / copilot-instructions / `GEMINI.md` ...) with a checkup→treat→follow-up→efficacy pipeline.

[![CI](https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml/badge.svg)](https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml)
[![npm version](https://img.shields.io/npm/v/ai-harness-doctor.svg)](https://www.npmjs.com/package/ai-harness-doctor)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![Node >=16](https://img.shields.io/badge/Node-%3E%3D16-green.svg)

## Why

Agent config drift is a repo disease: N tools read N rule files, teams copy-paste the same instructions everywhere, commands rot, paths move, and Codex-sized 32KB context files can be silently truncated. The result is a confident agent following stale or contradictory rules.

AI Harness Doctor turns that mess into one canonical `AGENTS.md`, minimal tool stubs, drift gates, and an optional before/after efficacy run.

## Benchmark

This is the differentiator: the demo keeps code and package manifests identical, changing only the agent-facing config layer.

| Metric | Before: messy conflicting configs | After: canonical `AGENTS.md` |
|---|---:|---:|
| Objective tasks correct | 3/7 | 7/7 |
| Avg latency per task | 20.2s | 11.4s |
| Captured total cost | $1.81 | $1.19 |

Scope: 7 objective tasks, single run, demo repo, runner `claude -p` using Claude CLI 2.1.202. See [`benchmark/`](benchmark/) to reproduce with the three commands in [`benchmark/README.md`](benchmark/README.md).

## Quick Start

Install for Claude Code (default):

```bash
npx ai-harness-doctor install
```

Install adapters for other agents:

```bash
npx ai-harness-doctor install --agent codex
npx ai-harness-doctor install --agent cursor
npx ai-harness-doctor install --agent gemini
npx ai-harness-doctor install --agent all
```

Install into the current project instead of the user home where supported:

```bash
npx ai-harness-doctor install --project
npx ai-harness-doctor install --agent all --project
```

Claude Code slash commands:

| Command | What it does | Example |
|---|---|---|
| `/harness-doctor` | Full pipeline: phases 0→2; phase 3 only on request | `/harness-doctor .` |
| `/harness-scan` | Phase 0 checkup: inventory, size, overlap, conflicts | `/harness-scan ~/repo` |
| `/harness-treat` | Phase 1 treatment: plan, user conflict adjudication, canonical `AGENTS.md`, stubs, validate | `/harness-treat .` |
| `/harness-drift` | Phase 2 follow-up: drift guard and repair advice | `/harness-drift .` |
| `/harness-eval` | Phase 3 efficacy validation: before/after task metrics | `/harness-eval .` |

Bare CLI for humans and CI:

```bash
npx ai-harness-doctor scan .
npx ai-harness-doctor plan . -o merge-plan.md
npx ai-harness-doctor stubs . --apply
npx ai-harness-doctor drift . --strict
npx ai-harness-doctor eval --tasks tasks.json --label after --workdir . -o results-after.json
```

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

### Long-term guard

After the treat phase has produced the canonical root `AGENTS.md`, install the follow-up guard suite:

```bash
npx ai-harness-doctor guard . --apply
```

It installs four repo-tracked guardrails:

- `.git/hooks/pre-commit` runs `ai-harness-doctor drift .` and honors `AI_HARNESS_DOCTOR_SKIP=1`.
- `.github/workflows/harness-drift.yml` is a path-aware PR drift gate.
- `.github/workflows/harness-checkup.yml` runs weekly scan + drift and creates/updates one drift issue.
- `AGENTS.md` gets a marked maintenance contract reminding contributors to update it with build/test/convention changes.

Remove exactly those pieces with:

```bash
npx ai-harness-doctor guard . --remove --apply
```

## Works with

| Surface | Support |
|---|---|
| Claude Code | Native skill plus slash commands under `.claude/commands` or `~/.claude/commands`. |
| OpenAI Codex CLI | Prompt adapters for `~/.codex/prompts/`. |
| Cursor | Command adapters for `.cursor/commands/`. |
| Gemini CLI | TOML custom command adapters for `~/.gemini/commands/harness/`. Google retired Gemini CLI for individual tiers on 2026-06-18; enterprise Gemini Code Assist is unaffected, and these adapters still work for enterprise/existing installs. |
| Windsurf / Cline / others | Universal mode: point the agent at the installed PLAYBOOK and say “run phase N”. |
| Humans & CI | Plain `npx ai-harness-doctor ...`; no agent required. |

Honest note: non-Claude adapters are thin pointers and lightly verified. If a command format changed, please file an issue.

## The four phases

| Phase | Script | Artifact | Stop condition |
|---|---|---|---|
| 0 — Checkup / scan | `scripts/scan.py` | Human or JSON health report | Stop at user confirmation of migration scope. |
| 1 — Treat / canonicalize | `scripts/canonicalize.py --plan`, `--write-stubs`, `--validate` | Merge plan, canonical `AGENTS.md`, minimal stubs | Stop until every conflict has human adjudication. |
| 2 — Follow-up / drift guard | `scripts/check_drift.py` | Drift report and CI/pre-commit exit codes | Stop when checks pass or repair advice is given. |
| 3 — Efficacy eval | `scripts/eval_run.py` | Before/after JSON and Markdown report | Stop when metrics are produced. |

Examples:

```bash
npx ai-harness-doctor scan . --json
npx ai-harness-doctor plan . -o merge-plan.md
npx ai-harness-doctor stubs . --apply --force
npx ai-harness-doctor drift . --strict
npx ai-harness-doctor eval --compare results-before.json results-after.json -o eval-report.md
```

## Feature comparison

### Positioning

AI Harness Doctor is complementary to Claude Code's official `/init`: `/init` bootstraps a config from scratch, while AI Harness Doctor diagnoses, consolidates, guards, and validates an existing sprawl. Its `SKILL.md` explicitly stays out of `/init`'s lane.

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

Note: regeneration and guarding are two valid philosophies: Ruler/rulesync make generated outputs disposable, while AI Harness Doctor guards a canonical `AGENTS.md` plus minimal stubs.

As of 2026-07, based on each project's public documentation — see their repos for the latest.

## Repository layout

```text
SKILL.md                         # Skill playbook and phase stop conditions
bin/cli.js                       # npm CLI and installer
commands/                        # Claude Code slash commands
adapters/                        # Codex, Cursor, Gemini, universal pointers
scripts/                         # Python stdlib deterministic mechanics
references/                      # Migration and conflict-resolution references
assets/                          # Templates and CI/pre-commit examples
benchmark/                       # Real before/after eval data
tests/                           # stdlib unittest suite
```

## Roadmap v2

- Repo harness-ification: CLI-ize project scripts, add verification gates, and layer docs cleanly.
- Richer eval task packs for more languages, repo shapes, and multi-turn workflows.
- More agent adapters as command formats stabilize.
- Antigravity CLI adapter (when its custom-command format is documented).

## Contributing

Bug reports and focused PRs are welcome. Keep scripts deterministic, stdlib-only, and covered by `python3 -m unittest discover -s tests -v`.

## License

MIT. Copyright (c) NieZhuZhu.
