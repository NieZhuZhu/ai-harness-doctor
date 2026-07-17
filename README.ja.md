[English](README.md) | [简体中文](README.zh-CN.md) | **日本語** | [Español](README.es.md) | [한국어](README.ko.md) | [Português (Brasil)](README.pt-BR.md) | [Français](README.fr.md)

# 🩺 AI Harness Doctor

**コーディングエージェントは、古いリポジトリ指示に従いながら自信満々に振る舞うことがあります。** AI Harness Doctor は `AGENTS.md`、`CLAUDE.md`、Cursor ルール、hooks、MCP 設定などを監査し、設定の drift が壊れた PR になる前に検出します。

分散したガイダンスを人間が管理する 1 つの `AGENTS.md` に統合し、ツール固有ファイルを短い pointer に保ち、その harness が実際に回答品質を改善したか測定できます。

<p><a href="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml"><img align="left" alt="CI" src="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml/badge.svg"></a> <a href="https://www.npmjs.com/package/ai-harness-doctor"><img align="left" alt="npm version" src="https://img.shields.io/npm/v/ai-harness-doctor.svg"></a> <img align="left" alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"> <img align="left" alt="Python 3.9+" src="https://img.shields.io/badge/Python-3.9%2B-blue.svg"> <img align="left" alt="Node &gt;=16" src="https://img.shields.io/badge/Node-%3E%3D16-green.svg"></p>
<br clear="left">

> 同梱 benchmark では、canonicalization により客観的回答が **6/28 から 28/28** に改善し、flip-flop が消え、平均 latency は 27%、記録された cost は 17% 低下しました。

## 60 秒で開始

インストール不要の read-only checkup：

```bash
npx ai-harness-doctor scan .
```

特定パスに適用される指示を説明：

```bash
npx ai-harness-doctor explain . packages/api/src/handler.ts
```

Node と Python runtime を確認：

```bash
npx ai-harness-doctor doctor --self-test
```

npx が解決したバージョンを確認：

```bash
npx ai-harness-doctor --version
```

これらのコマンドは監査対象リポジトリを変更しません。

## チェック内容

| 領域 | Doctor が確認するもの |
|---|---|
| Inventory | Canonical files、tool rules、nested scopes、MCP、hooks、commands、permissions、subagents。 |
| Security | Plaintext secrets、広すぎる権限、安全でない MCP transport、危険な hook、権限 bypass 指示。 |
| Consistency | 存在しない script、移動済み path、package manager/runtime drift、broken links、競合 lockfiles。 |
| Instruction quality | 大きすぎる context、README の丸ごとコピー、silent adjudication、overlap、same-scope conflict。 |
| Scope | root から最寄り `AGENTS.md` までの継承と、bounded な Claude/Cursor/Copilot glob applicability。 |
| Efficacy | Before/after correctness、stability、latency、cost、evidence freshness、health grade。 |

Security read は監査対象リポジトリ内に限定されます。大きなファイルでも SHA-256、行数、secret、permission-bypass は全体を確認し、`--max-bytes` は semantic analysis だけを制限します。

## 4 つのフェーズ

| フェーズ | 目的 | 主なコマンド | 人間の停止点 |
|---|---|---|---|
| 0 — Checkup | Risk、conflict、gap、repository facts を発見。 | `scan`, `explain` | Migration scope を確認。 |
| 1 — Treat | Merge plan を作り canonical guidance に統合。 | `plan`, `validate`, `stubs` | Semantic conflict をすべて裁定。 |
| 2 — Follow-up | Command、path、link、stub、fact の再 drift を防止。 | `drift`, `guard`, `review` | Code と guidance のどちらが誤りか判断。 |
| 3 — Efficacy | Harness が agent behavior を改善したか測定。 | `eval` | Evidence が十分か判断。 |

Script は deterministic な機械処理だけを行います。npm と pnpm の選択、争点のある command、prose の semantic merge を勝手に決定しません。

## リポジトリを統合する

Review 可能な plan を作り、`AGENTS.md` を記述して検証し、重複した tool files を短い pointer に置き換えます：

```bash
npx ai-harness-doctor scan .
npx ai-harness-doctor plan . -o merge-plan.md
# Write and review AGENTS.md, then:
npx ai-harness-doctor validate .
npx ai-harness-doctor stubs . --apply
npx ai-harness-doctor guard . --apply
```

Claude Code skill をインストールして `/harness-doctor .` や `/harness-treat .` を実行することもできます。Repository truth が曖昧な場合、agent は停止して判断を求めます。

## インストールと更新

| 目的 | コマンド |
|---|---|
| 現在の user に Claude Code skill をインストール | `npx ai-harness-doctor install` |
| Codex prompts をインストール | `npx ai-harness-doctor install --agent codex` |
| Repository に Cursor commands をインストール | `npx ai-harness-doctor install --agent cursor --project` |
| Repository に全 adapter をインストール | `npx ai-harness-doctor install --agent all --project` |
| 最新 package を tracked installs に再配置 | `npx ai-harness-doctor@latest update` |
| Installed adapters を削除 | `npx ai-harness-doctor uninstall --agent all` |

Copy install は ownership を追跡します。Update/uninstall は未所有の衝突や user 編集を保持します。Test は常に isolated `HOME` を使います。

## CI で健全性を維持

Provider-aware な pre-commit、PR、scheduled guard をインストール：

```bash
npx ai-harness-doctor guard . --apply
```

GitHub guard は scan と drift を 1 つの詳細な PR review に統合します。位置情報のある finding は inline comment になり、summary には severity、health、evidence、修復方法、優先順位が含まれます。

すでに pre-commit framework を利用していますか？

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/NieZhuZhu/ai-harness-doctor
    rev: v1.13.1
    hooks:
      - id: ai-harness-doctor-drift
      - id: ai-harness-doctor-scan
```

Weekly checkup は所有する incident issue を 1 つだけ更新し、回復後に閉じます。Repository maintenance contract は [`references/maintenance-contract.md`](references/maintenance-contract.md) を参照してください。

## GitHub Action と SARIF

Marketplace Action は既定で選択した ref の bundled code を実行し、SARIF、Action outputs、Job Summary を生成します：

```yaml
- id: doctor
  uses: NieZhuZhu/ai-harness-doctor@v1
  with:
    command: scan
    path: .
- uses: github/codeql-action/upload-sarif@v4
  with:
    sarif_file: ${{ steps.doctor.outputs.sarif-file }}
```

Outputs には `status`、severity counts、`finding-count`、`resolved-baseline-count`、drift の `health-score` / `health-grade` があります。

Status precedence は `findings > maintenance > ok`。Valid な non-zero quality gate は SARIF と summary を公開してから元の CLI exit code を復元します。

SARIF findings は stable partial fingerprint と独立した scan/drift category を持つため、無関係な行移動で重複せず、個別 upload が互いを close しません。

追加 option value に空白がある場合、または exact/repeated argv 境界が必要な場合は `args-json` を使用します：

```yaml
- uses: NieZhuZhu/ai-harness-doctor@v1
  with:
    command: drift
    path: .
    args-json: '["--baseline", ".ai-harness-doctor/drift baseline.json", "--check-baseline"]'
```

`args-json` と legacy `args` は相互排他です。Legacy `args` は first-line whitespace split のみで、どちらの input も shell-evaluate されません。

## 既存 debt を安全に導入

Baseline は review 可能な debt register であり、ignore list ではありません。Finding を new、known、repaired に分類します：

```bash
npx ai-harness-doctor scan . --write-baseline .ai-harness-doctor/scan-baseline.json
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json \
  --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json --check-baseline
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json --prune-baseline
```

`baselined` は known debt、`resolved_baseline` は repaired entry です。Check は cleanup が必要なら `9`、prune は repaired entry だけを atomic に削除し、新しい finding を記録しません。

HIGH security finding は baseline 対象外です。通常の malformed baseline は何も抑制せず、明示的な check/prune は fail closed して書き込みません。

## コマンドガイド

| コマンド | 用途 | 既定で書き込む？ |
|---|---|---:|
| `scan` | Full checkup、security、gaps、conflicts、semantics、project snapshot。 | いいえ |
| `explain` | 1 path の effective instruction chain と diagnostic scope。 | いいえ |
| `plan` | Review 可能な consolidation plan。 | Output path 指定時のみ |
| `validate` | Canonical path、size、required sections、unresolved draft markers。 | いいえ |
| `stubs` | Minimal tool pointers の preview/apply。 | いいえ |
| `drift` | D1–D8、health、baseline lifecycle、安全な D3 repair。 | いいえ |
| `guard` | Pre-commit と CI guard の install/remove。 | いいえ |
| `review` | Scan/drift report から GitHub PR review を生成・投稿。 | `--post` 時のみ |
| `eval` | Efficacy tasks の生成、実行、比較、regrade、score、trend。 | Output flags に依存 |
| `mcp` | Read-only MCP stdio server を開始。 | いいえ |
| `doctor` | Node/Python runtime と packaged engines を検証。 | いいえ |

完全な option/behavior は `npx ai-harness-doctor help` または [`SKILL.md`](SKILL.md) を参照してください。

## 対応 surface

| Surface | 対応 |
|---|---|
| Claude Code | Native skill と slash commands。 |
| OpenAI Codex CLI | Prompt adapters。 |
| Cursor | Project/user command adapters。 |
| Gemini CLI | Enterprise/既存 install 向け TOML command adapters。 |
| MCP clients | JSON-RPC stdio で 7 つの read-only tools。 |
| GitHub Actions | Composite Action、SARIF、Job Summary、outputs、PR feedback。 |
| GitLab / Codebase | 共通 scan、drift、optional eval gates。 |
| Other agents | Playbook への universal pointer。 |

Non-Claude adapter は意図的に薄い設計です。広範な rule distribution は Ruler/rulesync の領域で、本プロジェクトは diagnosis、evidence、safety、drift、efficacy に集中します。

## セーフティモデル

- Scan は read-only で、repository-derived external symlink を除外します。
- Repository の `.gitignore` が除外する missing path は意図的な runtime path とみなします。Synthetic Git metadata は local/global rule を排除し、Git failure 時は finding を維持します。
- 隣接する語が backtick `org/name` を Docker/OCI image または RPC/API method と明示的にラベル付けする場合は runtime identifier とみなし、checked path とはしません。除外は fail-closed で、拡張子付きや三段以上の token は path のまま扱います。
- Nested drift は command、path、runtime/package-manager fact を lexical package ancestor から解決し、sibling package は検索しません。Markdown link は file-relative のままです。
- Write path は symlinked file または既存 parent directory を拒否します。
- Plugin は `--allow-plugins` を明示した場合だけ有効です。
- Secret finding は type/path のみを示し値を再掲しません。危険な hook snippet は JSON、Markdown、SARIF、PR feedback で redacted になります。
- Installer mutation は lock、journal、ownership、recovery を使用します。
- MCP tools は read-only。Finding は transport failure ではありません。
- External judge と real LLM grading は opt-in。Remote endpoint は HTTPS 必須、loopback HTTP は明示的に許可し、redirect は拒否され、失敗時は deterministic judge に fallback します。
- Eval result artifact は runner/judge diagnostics と matrix runner template の高信頼 credential を redact します。Grading は引き続き memory 内の元の bounded output を使用します。
- Telemetry はありません。任意の npm update check は `AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1` で無効化できます。

## エビデンスとベンチマーク

| 側 | Passed | Flip-flop tasks | Avg latency/task | Captured cost |
|---|---:|---:|---:|---:|
| Before：conflicting/stale configs | 6/28 | 2 | 16.0s | $5.82 |
| After：canonical `AGENTS.md` | 28/28 | 0 | 11.7s | $4.81 |

方法と再現手順は [`benchmark/README.md`](benchmark/README.md) を参照してください。これは 1 つの demo repository、各側 2 runs の evidence であり、普遍的な performance claim ではありません。

## ドキュメントマップ

| ドキュメント | 目的 |
|---|---|
| [`SKILL.md`](SKILL.md) | 完全な 4-phase behavior と command contract。 |
| [`references/migration-decision-tree.md`](references/migration-decision-tree.md) | 適切な migration path を選択。 |
| [`references/conflict-resolution.md`](references/conflict-resolution.md) | Human adjudication workflow。 |
| [`references/tool-matrix.md`](references/tool-matrix.md) | Tool-file support と ownership。 |
| [`references/maintenance-contract.md`](references/maintenance-contract.md) | Baseline、Action、guard、CI、release、installer invariants。 |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Contribution workflow と checks。 |
| [`RELEASING.md`](RELEASING.md) | Tag-driven npm、GitHub Release、floating Action tag、Marketplace flow。 |
| [`EXTERNAL_VALIDATION.md`](EXTERNAL_VALIDATION.md) | Real repositories に対する read-only validation。 |

## プロジェクト状況

- Python 3.9+、Node 16+。Runtime dependency は標準ライブラリのみ。
- npm release は provenance 付き tag-driven。
- Stable release は floating major Action tag（`1.x` なら `v1`）を更新。
- Feature release は minor、bugfix-only release は patch。
- Public behavior の変更は同じ PR で全 published language docs を同期します。

## コントリビューション

Issue と PR を歓迎します。[`CONTRIBUTING.md`](CONTRIBUTING.md) を読み、behavior change には test を追加し、同じ PR ですべての translated README を更新してください。

Security vulnerability は public issue ではなく [`SECURITY.md`](SECURITY.md) に従ってください。

## ライセンス

[MIT](LICENSE)
