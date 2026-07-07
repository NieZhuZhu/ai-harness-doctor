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

## Works with

| Surface | Support |
|---|---|
| Claude Code | Native skill plus slash commands under `.claude/commands` or `~/.claude/commands`. |
| OpenAI Codex CLI | Prompt adapters for `~/.codex/prompts/`. |
| Cursor | Command adapters for `.cursor/commands/`. |
| Gemini CLI | TOML custom command adapters for `~/.gemini/commands/harness/`. |
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

| Capability | AI Harness Doctor | Hand-rolled migration | Official `/init` | Plain docs |
|---|---:|---:|---:|---:|
| Conflict detection with evidence | ✅ | △ | ❌ | ❌ |
| Overlap percentage | ✅ | △ | ❌ | ❌ |
| Size / truncation warnings | ✅ | △ | ❌ | ❌ |
| Stub downgrade with re-divergence guard | ✅ | △ | ❌ | ❌ |
| CI / pre-commit gate | ✅ | △ | ❌ | △ |
| Before/after efficacy eval | ✅ | ❌ | ❌ | ❌ |
| Multi-agent adapters | ✅ | △ | ❌ | ❌ |

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

## Contributing

Bug reports and focused PRs are welcome. Keep scripts deterministic, stdlib-only, and covered by `python3 -m unittest discover -s tests -v`.

## License

MIT. Copyright (c) NieZhuZhu.
