[English](README.md) | [简体中文](README.zh-CN.md) | **日本語**

# 🩺 AI Harness Doctor

リポジトリ内の AI agent 設定（`AGENTS.md` / `CLAUDE.md` / `.cursorrules` / copilot-instructions / `GEMINI.md` ...）を監査・統合・保護する、checkup→treat→follow-up→efficacy のパイプラインです。

[![CI](https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml/badge.svg)](https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml)
[![npm version](https://img.shields.io/npm/v/ai-harness-doctor.svg)](https://www.npmjs.com/package/ai-harness-doctor)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![Node >=16](https://img.shields.io/badge/Node-%3E%3D16-green.svg)

## Why

Agent 設定のドリフトは、リポジトリに起きる慢性的な不調です。N 個のツールが N 個のルールファイルを読み、同じ指示がコピーされ、コマンドは古くなり、パスは移動し、Codex のような約 32KB のコンテキスト制限では静かに切り捨てられることもあります。結果として、agent は自信ありげに古い指示や矛盾した指示に従います。

AI Harness Doctor は、その状態を 1 つの canonical `AGENTS.md`、最小限の tool stub、drift gate、任意の before/after 効果測定へ整理します。

## Benchmark

このプロジェクトの差別化ポイントです。demo repo ではコードと package manifest を一切変えず、agent が読む設定レイヤーだけを変えています。

| Metric | Before: messy conflicting configs | After: canonical `AGENTS.md` |
|---|---:|---:|
| 正解した客観タスク | 3/7 | 7/7 |
| タスク平均レイテンシ | 20.2s | 11.4s |
| 捕捉された総コスト | $1.81 | $1.19 |

範囲: 7 個の客観タスク、単回実行、demo repo、runner は `claude -p`、Claude CLI 2.1.202。再現手順は [`benchmark/`](benchmark/) と [`benchmark/README.md`](benchmark/README.md) の 3 コマンドを参照してください。

## Quick Start

Claude Code 向けにインストール（デフォルト）:

```bash
npx ai-harness-doctor install
```

他 agent の adapter をインストール:

```bash
npx ai-harness-doctor install --agent codex
npx ai-harness-doctor install --agent cursor
npx ai-harness-doctor install --agent gemini
npx ai-harness-doctor install --agent all
```

対応している場合、ユーザー home ではなく現在のプロジェクトへインストール:

```bash
npx ai-harness-doctor install --project
npx ai-harness-doctor install --agent all --project
```

Claude Code slash commands:

| Command | 内容 | 例 |
|---|---|---|
| `/harness-doctor` | フルパイプライン: phases 0→2。phase 3 は明示要求時のみ | `/harness-doctor .` |
| `/harness-scan` | Phase 0 checkup: inventory、size、overlap、conflict | `/harness-scan ~/repo` |
| `/harness-treat` | Phase 1 treatment: plan、ユーザーによる conflict 裁定、canonical `AGENTS.md`、stub、validate | `/harness-treat .` |
| `/harness-drift` | Phase 2 follow-up: drift guard と修復アドバイス | `/harness-drift .` |
| `/harness-eval` | Phase 3 efficacy validation: before/after タスク指標 | `/harness-eval .` |

人間と CI 向けの素の CLI:

```bash
npx ai-harness-doctor scan .
npx ai-harness-doctor plan . -o merge-plan.md
npx ai-harness-doctor stubs . --apply
npx ai-harness-doctor drift . --strict
npx ai-harness-doctor eval --tasks tasks.json --label after --workdir . -o results-after.json
```

## Updating

コピー方式のインストールは `~/.ai-harness-doctor/manifest.json` に記録されます。以前インストールしたすべての対象へ最新 package files を再デプロイするには、次を実行します:

```bash
npx ai-harness-doctor@latest update
```

対話的なコマンドは npm を最大 1 日 1 回だけ確認し、`npx ai-harness-doctor@latest update` のような更新ヒントを表示することがあります。この確認を無効にするには `AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1` を設定してください。素の `npx` CLI を単発で使う場合、最新版が必要なら `ai-harness-doctor@latest` を明示してください。

本当の hot update が必要な場合は、package を永続的にインストールしてから payload を link します:

```bash
npm i -g ai-harness-doctor
ai-harness-doctor install --link
npm update -g ai-harness-doctor
```

`--link` では Claude の `~/.claude/skills/ai-harness-doctor` が global package を指し、他の adapters も同じ package root を指すため、`npm update -g ai-harness-doctor` で playbook が即時に全体へ反映されます。Windows では directory link に junction を使います。

### Long-term guard

treat phase で canonical root `AGENTS.md` を作成した後、follow-up guard suite をインストールします:

```bash
npx ai-harness-doctor guard . --apply
```

4 つの repo-tracked guardrail を入れます:

- `.git/hooks/pre-commit` が `ai-harness-doctor drift .` を実行し、`AI_HARNESS_DOCTOR_SKIP=1` を escape hatch として尊重します。
- `.github/workflows/harness-drift.yml` は path-aware PR drift gate です。
- `.github/workflows/harness-checkup.yml` は週次で scan + drift を実行し、1 つの drift issue を作成または更新します。
- `AGENTS.md` には marker 付き maintenance contract が追加され、build/test/convention 変更時の同期更新を促します。

これらだけを削除するには:

```bash
npx ai-harness-doctor guard . --remove --apply
```

## Works with

| Surface | Support |
|---|---|
| Claude Code | native skill と `.claude/commands` または `~/.claude/commands` の slash commands。 |
| OpenAI Codex CLI | `~/.codex/prompts/` 向け prompt adapters。 |
| Cursor | `.cursor/commands/` 向け command adapters。 |
| Gemini CLI | `~/.gemini/commands/harness/` 向け TOML custom commands。Google は 2026-06-18 に個人 tier 向け Gemini CLI を retired しました。enterprise Gemini Code Assist は影響を受けず、これらの adapters は enterprise / existing installs で引き続き使えます。 |
| Windsurf / Cline / others | Universal mode: agent にインストール済み PLAYBOOK を示し、「run phase N」と伝える。 |
| Humans & CI | `npx ai-harness-doctor ...` を直接実行。agent は不要。 |

正直な注記: Claude 以外の adapter は薄いポインタで、検証は軽めです。コマンド形式が変わっていたら issue をください。

## The four phases

| Phase | Script | Artifact | Stop condition |
|---|---|---|---|
| 0 — Checkup / scan | `scripts/scan.py` | 人間向けまたは JSON の health report | migration scope をユーザーが確認したところで停止。 |
| 1 — Treat / canonicalize | `scripts/canonicalize.py --plan`, `--write-stubs`, `--validate` | merge plan、canonical `AGENTS.md`、minimal stubs | すべての conflict が人間に裁定されるまで停止。 |
| 2 — Follow-up / drift guard | `scripts/check_drift.py` | drift report と CI/pre-commit exit code | check pass、または修復アドバイス提示で停止。 |
| 3 — Efficacy eval | `scripts/eval_run.py` | before/after JSON と Markdown report | 指標が出たところで停止。 |

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

AI Harness Doctor は Claude Code 公式 `/init` と補完関係にあります。`/init` は config をゼロから bootstraps し、AI Harness Doctor は既存の sprawl を diagnose、consolidate、guard、validate します。本 project の `SKILL.md` は明示的に `/init` の lane に入りません。

Legend: ✅ built-in / △ partial or different approach / ❌ not a stated feature.

| Dimension | AI Harness Doctor | [Ruler](https://github.com/intellectronica/ruler) | [rulesync](https://github.com/dyoshikawa/rulesync) |
|---|---|---|---|
| Canonical-source model | △ `AGENTS.md` 自体が canonical + minimal stubs。 | △ `.ruler/` central source を agent-specific files へ配布。 | △ `.rulesync/` unified rules を 20+ tools へ生成。 |
| Consolidate FROM existing configs | ✅ Treat phase が existing configs を consolidates。 | ❌ Not a stated feature in their docs. | ✅ existing `CLAUDE.md` / `.cursorrules` から reverse IMPORT。 |
| Conflict detection with file:line evidence | ✅ Scan/plan reports が file:line evidence を引用。 | ❌ Not a stated feature in their docs. | ❌ Not a stated feature in their docs. |
| Overlap % metrics | ✅ scan reports に built-in。 | ❌ Not a stated feature in their docs. | ❌ Not a stated feature in their docs. |
| Size/truncation warnings | ✅ scan/drift に built-in。 | ❌ Not a stated feature in their docs. | ❌ Not a stated feature in their docs. |
| Re-divergence guard on hand-edited files | ✅ D3 drift guard が stub re-divergence を検出。 | △ regeneration で別アプローチとして解決。 | △ regeneration で別アプローチとして解決。 |
| CI / pre-commit gate | ✅ `guard` suite が pre-commit、PR gate、weekly checkup をインストール。 | △ CI で regenerate 可能。 | △ CI で regenerate 可能。 |
| Before/after efficacy eval with real benchmark | ✅ [`benchmark/`](benchmark/) 参照。 | ❌ Not a stated feature in their docs. | ❌ Not a stated feature in their docs. |
| Distribution breadth | △ 4 agents + universal pointer。 | ✅ Multiple agent-specific outputs。 | ✅ 20+ tools。 |
| MCP config propagation | ❌ Not supported. | ✅ Built-in MCP config propagation。 | ❌ Not a stated feature in their docs. |

Note: regeneration と guarding はどちらも有効な philosophy です。Ruler/rulesync は generated outputs を disposable にし、AI Harness Doctor は canonical `AGENTS.md` と minimal stubs を guard します。

As of 2026-07, based on each project's public documentation — see their repos for the latest.

## Repository layout

```text
SKILL.md                         # skill playbook と phase stop conditions
bin/cli.js                       # npm CLI と installer
commands/                        # Claude Code slash commands
adapters/                        # Codex, Cursor, Gemini, universal pointers
scripts/                         # Python stdlib の deterministic mechanics
references/                      # migration と conflict resolution references
assets/                          # templates と CI/pre-commit examples
benchmark/                       # 実際の before/after eval data
tests/                           # stdlib unittest suite
```

## Roadmap v2

- Repo harness-ification: project scripts の CLI 化、verification gates、doc layering。
- より多様な language、repo shape、multi-turn workflow 向けの eval task packs。
- command format が安定した agent adapters の追加。
- Antigravity CLI adapter (when its custom-command format is documented)。

## Contributing

Bug report と focused PR を歓迎します。scripts は deterministic、stdlib-only を保ち、`python3 -m unittest discover -s tests -v` を通してください。

## License

MIT. Copyright (c) NieZhuZhu.
