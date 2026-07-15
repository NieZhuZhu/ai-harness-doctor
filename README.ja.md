[English](README.md) | [简体中文](README.zh-CN.md) | **日本語**

# 🩺 AI Harness Doctor

**あなたの AI コーディング agent は、古い指示に自信たっぷりに従っています。** `CLAUDE.md`、`.cursorrules`、`GEMINI.md`、`AGENTS.md` は静かにドリフトし、やがて agent はもう存在しないスクリプトを実行し、すでに移動したパスを編集し、`pnpm` に切り替えたリポジトリで `npm` を教え続けます。

AI Harness Doctor は、そのドリフトを見える化し、散らばった agent 設定を 1 つの正本 `AGENTS.md` にまとめ、それを守ってリポジトリが静かに忘れないようにします —— Claude Code、Codex、Cursor、Gemini、そして素の CI に対応。ゼロインストールの `scan` 一発で、設定インベントリ、衝突の根拠、セキュリティ監査、欠けているインフラのギャップ、技術スタックのスナップショットまでを一括で健診します。

<p><a href="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml"><img align="left" alt="CI" src="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml/badge.svg"></a> <a href="https://www.npmjs.com/package/ai-harness-doctor"><img align="left" alt="npm version" src="https://img.shields.io/npm/v/ai-harness-doctor.svg"></a> <img align="left" alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"> <img align="left" alt="Python 3.9+" src="https://img.shields.io/badge/Python-3.9%2B-blue.svg"> <img align="left" alt="Node &gt;=16" src="https://img.shields.io/badge/Node-%3E%3D16-green.svg"></p>
<br clear="left">

> **私たちの 14 タスク benchmark では、リポジトリを正本化することで agent の正答が 6/28 → 28/28 に改善し、同じ質問が実行のたびに違う答えになる「ブレ」も解消しました。** [数値を見る ↓](#benchmark)

インストール不要、リポジトリには何も書き込まない一発コマンドで試せます:

```bash
npx ai-harness-doctor scan .
```

> **Repository boundary:** read-only scanner は、repository 由来の config、manifest、workspace、semantic fact、default plugin の symlink が audited repository の外を指す場合、そのリンクをたどりません。repository 内の file symlink は引き続きサポートされ、lexical repo-relative report path を保持します。明示的に指定した `--rules DIR` path は、意図された opt-in として引き続き利用できます。

## Why

Agent 設定のドリフトは、リポジトリに起きる病気です。あるツールは `CLAUDE.md` を読み、別のツールは `.cursorrules` を読み、また別のツールは `GEMINI.md` を読みます。そうして各ファイルは少しずつ独自の言い伝えになっていきます。古いコマンド、移動済みのパス、コピーされたスタイルルール、矛盾するパッケージマネージャー、そして切り捨てられるほど大きくなったコンテキストファイルです。

つらいのは、agent が古い指示に従っているのに自信たっぷりに見えることです。新しいメンテナーがテストコマンドを尋ねると、もう存在しないスクリプトが返ってきます。リファクタで `src/components/` が移動しても、ルールファイルはまだ `app/ui/` を指しています。チームが npm から pnpm に切り替えても、3 つの agent 向け窓口が npm を教え続けます。

AI Harness Doctor は、そのドリフトを見える化し、人間または agent が 1 つの正本 `AGENTS.md` を書けるようにし、古いツール別ファイルを小さなポインタへ降格し、リポジトリが静かに忘れていかないよう guard を入れます。

私たちの 14 タスク benchmark では、正本化したリポジトリで agent の正答が 6/28 から 28/28 へ改善しました — 詳細は [Benchmark](#benchmark) を参照してください。

## User stories

| Persona | Pain | Commands | Outcome |
|---|---|---|---|
| 新任メンテナー | 2 年前の `CLAUDE.md`、3 世代分の `.cursorrules`、存在しないスクリプトを実行する agent が残る legacy repo を引き継いだ。 | `scan` → `/harness-treat` | file:line の根拠を得て、衝突を裁定し、言い伝えを 1 つの `AGENTS.md` に置き換える。 |
| 複数ツール併用チーム | Cursor、Claude Code、Codex の利用者が毎週ルールファイルを分岐させてしまう。 | `plan` → `stubs --apply` → `guard --apply` | ツール別ファイルが stub になり、CI が再分岐をブロックする。 |
| 静かに腐っていく repo | npm→pnpm に移行し、ディレクトリも移動したのに、docs が追いついていない。 | `drift . --strict` | パスを理解する drift gate が、古い指示が入る前に PR を止める。 |
| 懐疑的なチームメイト | agent 設定ファイルなんて cargo cult だと言う人がいる。 | `eval --tasks ...` before/after | correctness、instability、latency、captured cost という実測値で議論を終わらせる。 |
| OSS メンテナー | AI 生成 PR が間違った慣習に従ってしまう。 | `AGENTS.md` + `guard --apply` | コントリビューターの agent がメンテナンス契約を読み、自分の変更を自己点検する。 |

## Quick Start

### Fastest path

インストール不要・読み取り専用の健診 —— 一発のコマンドで、harness の設定インベントリ、衝突の根拠（file:line 付き）、セキュリティの発見、欠けているインフラのギャップ、技術スタックのスナップショットを数秒で提示します:

```bash
npx ai-harness-doctor scan .
```

修正に取りかかりますか？ Claude Code skill をインストールし、agent にフロー全体を駆動させます:

```bash
npx ai-harness-doctor install
```

続いて Claude Code で実行します。

```text
/harness-doctor .
```

衝突の裁定質問に答えてください。ツールは根拠を報告しますが、リポジトリにとって何が真実かを決めるのはあなたです。

### Apply to your repo in 3 steps

意図的に、完全なワンクリック移行は用意していません。Phase 1 には意味判断が含まれます。pnpm-vs-npm、test-vs-test:unit、old path-vs-new path を、ツールが勝手に決めることはありません。

```bash
npx ai-harness-doctor scan .
npx ai-harness-doctor plan . -o merge-plan.md
# Write AGENTS.md from the plan, then:
npx ai-harness-doctor validate .
npx ai-harness-doctor stubs . --apply
npx ai-harness-doctor guard . --apply
```

`AGENTS.md` を書く方法は 3 つあります。

1. `merge-plan.md` と `assets/AGENTS.template.md` をもとに手で書く。
2. plan を根拠として、coding agent に書かせる。
3. `/harness-treat .` を使う。plan を読み、衝突ごとに質問し、ファイルを書き、検証します。

### Requirements

- 対象は git repo である必要があります。
- `ai-harness-doctor` CLI には Node >=16 が必要です。
- 決定的な scan/plan/validate/stubs/drift/eval scripts には Python >=3.9 が必要です。stdlib-only です。
- `ai-harness-doctor doctor --self-test` を実行して Node + Python ランタイムを検証できます。`AI_HARNESS_DOCTOR_PYTHON` で特定のインタプリタを固定できます。
- `stubs` または `guard` が何かを書き込む前に、`AGENTS.md` が存在している必要があります。

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
| `scan` | ✅ | ❌ | デフォルトで 0 で終了します。inventory、evidence、security checkup、不足しているインフラの gap analysis、semantic consistency チェック（AGENTS.md の宣言 vs コードの事実）、および技術スタックの project snapshot を行います。markdown モードでは完全な JSON レポートを一時ファイルに書き出し、そのパスを出力します。`--fail-on-security` は HIGH の findings があれば 2 で終了し、`--fail-on-gaps` は ERROR の gap があれば 3 で終了し、`--fail-on-semantic` は宣言とコードの矛盾があれば 4 で終了します。 |
| `plan` | ✅ | Optional output file | merge plan の土台を作ります。merge はしません。 |
| Write `AGENTS.md` | ❌ | ✅ | 人間または agent による意味判断のステップです。 |
| `validate` | ✅ | ❌ | 正本 `AGENTS.md` に必要な sections が含まれているか確認します。 |
| `stubs` | ✅ | With `--apply` | `--force` がない限り clean tree が必要です。 |
| `guard` | ✅ | With `--apply` | git repo と既存の `AGENTS.md` が必要です。 |
| `drift` | ✅ | ❌ | blocking drift で失敗します。`--strict` は notices を昇格します。 |

### Uninstall & rollback

```bash
npx ai-harness-doctor guard . --remove --apply
npx ai-harness-doctor uninstall --agent all
```

`guard --remove` は marker 単位で正確に動きます。自分が管理する snippets だけを削除し、外部の pre-commit hook には触れません。それ以外は git で revert できます。

## Slash commands

| Command | Input | What the agent does | Where it STOPS | What you decide |
|---|---|---|---|---|
| `/harness-doctor` | Repo path、通常は `.` | 健診→治療→経過観察のフロー全体を実行します。eval は要求された場合のみです。 | 意味的な衝突解決の前、および任意の eval の前。 | 移行範囲、衝突における真実、guards を入れるかどうか。 |
| `/harness-scan` | Repo path | Phase 0 の inventory、size、overlap、conflict、nested-agent 検出を実行します。 | health report の後。 | repo 全体を治療するか、subdir か、選んだファイルだけにするか。 |
| `/harness-treat` | Repo path、任意の scan/plan output | merge plan を作り、衝突について質問し、正本 `AGENTS.md` を書いて検証し、stubs をプレビューします。 | すべての衝突に明示的な回答が出るまで。 | どの command/path/style/version を正本にするか。 |
| `/harness-drift` | Repo path | drift checks を実行し、修復方法を説明します。 | checks が pass するか、修復アドバイスが出た後。 | repo の実態を更新するか、`AGENTS.md` を更新するか。 |
| `/harness-eval` | Repo path + task file/results | before/after tasks を実行または比較します。 | metrics または manual protocol が出た時点。 | task set、runner、証拠として十分かどうか。 |

## Updating

コピー方式のインストールは `~/.ai-harness-doctor/manifest.json` で追跡されます。以前インストールしたすべての場所へ最新 package files を再デプロイするには、次を実行します。

```bash
npx ai-harness-doctor@latest update
```

対話コマンドは npm を最大 1 日 1 回だけ確認し、`npx ai-harness-doctor@latest update` のような更新ヒントを表示することがあります。この確認を無効にするには `AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1` を設定してください。素の `npx` CLI を使う場合、単発コマンドでも最新版が必要なら `ai-harness-doctor@latest` を明示してください。

本当の hot updates が必要なら、package を永続的にインストールして payload を link します。

```bash
npm i -g ai-harness-doctor
ai-harness-doctor install --link
npm update -g ai-harness-doctor
```

`--link` を使うと、Claude は `~/.claude/skills/ai-harness-doctor` から global package を指し、他の adapters も同じ package root を指すため、`npm update -g ai-harness-doctor` によって playbook が即座に全体へ反映されます。Windows では directory links に junctions を使います。

## Long-term guard

> これは更新を保証するものではなく、検出を保証するものです。doc-vs-repo の整合性は machine-checkable な条件になり、pre-commit、PR、weekly checkup の 3 か所で失敗できるようになります。忘却は、もう静かには起きません。

treat phase で正本となる root `AGENTS.md` ができた後にインストールします。

```bash
npx ai-harness-doctor guard . --apply
```

CI gate は provider-aware です。`--provider github|gitlab|codebase`（デフォルト `auto`）を渡すと、対応する CI files をインストールします。provider ごとの file layout は [`guard`](#command-reference) の command reference を参照してください。

pull request では、GitHub guard テンプレートはさらに 2 つのことを行います。1 つ目は、drift の検出結果を**実行可能な PR review feedback**として表示することです。`scripts/pr_review.py` は `check_drift.py --json`（または `scan.py --json`）のレポートを読み取り、1 つの review の投稿を試みます。位置を特定できる検出結果は、rule、severity、finding、AI agent への影響、利用可能な evidence、suggested fix を含む inline comment になります。最終 summary には health score/grade、severity distribution、inline と summary の件数、全 findings の index、各 finding の折りたたみ可能な完全な詳細、優先順位付き next steps が含まれ、安定した `<!-- ai-harness-doctor:pr-review -->` marker が付きます。GitHub が無効な inline 位置を HTTP 422 で拒否した場合、すべての修正ガイダンスを維持するため、この完全な summary を通常の PR comment として投稿します。permission、network、rate-limit、server error は引き続き明示されます。clean report の場合は、対象となった checks と action 不要であることを明示します。デフォルトは dry-run（JSON payload を出力し、ネットワークには一切触れません）で、`--post` 時のみ `GITHUB_TOKEN` を使って投稿します。2 つ目は、**eval health-score gate** の実行です。`python3 scripts/eval_run.py --score <コミット済み results.json> --fail-under <N>` により、eval health score が閾値を下回ると CI を失敗（exit 5）させます。PR review feedback は GitHub 限定で、GitLab/Codebase テンプレートは eval gate のみを得ます。

Defense in depth、強い順です。

1. **Pre-commit hard block** — ローカル編集がマシンを出る前に `AGENTS.md` を古くしてしまうことを防ぎます。`AI_HARNESS_DOCTOR_SKIP=1` は明示的で監査可能な bypass であり、静かな pass ではありません。
2. **Path-aware PR gate** — hook bypass を防ぎます。リファクタは必然的に `package.json`、`Makefile`、`AGENTS.md`、tool stubs など watched files に触れるため、CI が PR 上で drift を再チェックします。
3. **Weekly checkup + deduped issue** — watched file に触れない遅い腐敗を防ぎます。新しい lint tool、CI Node bump、通常の path set の外から来る convention change などです。
4. **Maintenance contract in `AGENTS.md`** — agent の振る舞いの源で防ぎます。リファクタは agent によって行われることが多く、すべての agent が `AGENTS.md` を読みます。この doc は自分自身のメンテナンスを指示します。

| Refactor/change | Check that should catch it |
|---|---|
| scripts や `Makefile` targets を変更する | D1 command drift |
| 文書化された paths を移動/削除する | D2 path drift |
| `CLAUDE.md` や `.cursorrules` に rules をこっそり戻す | D3 stub regrowth |
| `AGENTS.md` を有用な context size を超えて肥大化させる | D4 size/context risk |
| `AGENTS.md` を更新せずに Node version を上げたり package manager を切り替えたりする | D6 fact drift |
| `AGENTS.md` がまだ Markdown link で参照している doc/config file を削除する | D7 Markdown-link drift |
| 2 つの異なる package manager の lockfile を commit する | D8 competing lockfiles |

なぜ regeneration ではなく detection なのか。ドリフトを静かに「修正」すると、人間の認識が消えてしまいます。AI Harness Doctor は代わりに drift を表面化します。大事なのはファイルを書き換えることではなく、repo の真実と agent の真実がズレたことにチームが気づくことだからです。[Positioning & Non-goals & Comparison](#positioning--non-goals--comparison) も参照してください。

すでにドリフトした repo に gate を導入したいですか。まず `drift --write-baseline FILE` で現在の findings を一度記録し、次に `drift --baseline FILE` でそれらだけを正確に抑制すれば、CI は新しい drift でのみ失敗します——ruff・mypy・detekt が提供するのと同じ導入パスです。baseline のフィンガープリントは行番号に依存せず、抑制された findings は `baselined` 配列で引き続き可視化され、health score は新しい drift のみを数えるため、完全に baseline 化した repo でも grade A のままです。

## Works with

| Surface | Support |
|---|---|
| Claude Code | native skill に加え、`.claude/commands` または `~/.claude/commands` 配下の slash commands。 |
| OpenAI Codex CLI | `~/.codex/prompts/` 向け prompt adapters。 |
| Cursor | `.cursor/commands/` 向け command adapters。 |
| Gemini CLI | `~/.gemini/commands/harness/` 向け TOML custom command adapters。Google は 2026-06-18 に個人 tier 向け Gemini CLI を retired しました。enterprise Gemini Code Assist は影響を受けず、これらの adapters は enterprise/existing installs で引き続き動作します。 |
| Windsurf / Cline / others | Universal mode: agent にインストール済み playbook を示し、「run phase N」と伝えます。 |
| MCP clients | `ai-harness-doctor mcp` は `harness_scan`/`drift`/`validate`/`plan`/`stubs`/`eval_generate` を stdio 経由の MCP tools として公開します。 |
| Humans & CI | 素の `npx ai-harness-doctor ...`。agent は不要です。 |

正直な注記: Claude 以外の adapters は薄いポインタで、検証は軽めです。command format が変わっていた場合は issue を立ててください。

## The four phases

| Phase | Script | Artifact | Stop condition |
|---|---|---|---|
| 0 — 健診 / scan | `scripts/scan.py` | 人間向けまたは JSON の health report | migration scope について user confirmation が得られたところで停止。 |
| 1 — 治療 / canonicalize | `scripts/canonicalize.py --plan`, `--write-stubs`, `--validate` | Merge plan、正本 `AGENTS.md`、minimal stubs | すべての conflict が人間に裁定されるまで停止。 |
| 2 — 経過観察 / drift guard | `scripts/check_drift.py` | Drift report と CI/pre-commit exit codes | checks が pass するか、修復アドバイスが出たところで停止。 |
| 3 — 効果検証 | `scripts/eval_run.py` | Before/after JSON と Markdown report、加えて 0–100 の `health` スコア（A–F グレード） | metrics が出たところで停止。 |

## Command reference

<details>
<summary><code>install</code></summary>

skill、slash commands、adapter prompts の一部または全部をインストールします。

| Agent | Default destination | With `--project` |
|---|---|---|
| `claude` | `~/.claude/skills/ai-harness-doctor`, `~/.claude/commands/` | `.claude/skills/ai-harness-doctor`, `.claude/commands/` |
| `codex` | `~/.codex/prompts/` + shared payload | 同じ adapter location。project は payload path に影響します。 |
| `cursor` | `.cursor/commands/` | target project 内の `.cursor/commands/`。 |
| `gemini` | `~/.gemini/commands/harness/` + shared payload | 同じ command location。project は payload path に影響します。 |

Adapters は `{{PLAYBOOK}}` を installed playbook path に置き換えます。Installs は `~/.ai-harness-doctor/manifest.json` に記録され、冪等で、`update` によって refresh できます。`--link` は payload files をコピーする代わりに global package を指します。CLI は安全でない `npx` cache linking をブロックし、先に global install するよう案内します。

</details>

<details>
<summary><code>uninstall</code></summary>

指定された `--agent` について、インストール済みの Claude skill files、slash commands、adapter prompts、shared payloads を削除します。`--agent all` は既知のすべての surface を削除します。対応する manifest records も削除します。

</details>

<details>
<summary><code>update</code></summary>

manifest で追跡されているすべての copy install を、現在の package version へ再デプロイします。Linked installs は command pointers を refresh し、payload は `npm update -g ai-harness-doctor` に追随します。

</details>

<details>
<summary><code>guard</code></summary>

デフォルトは dry-run です。書き込むには `--apply` を使います。要件: target は git repo であり、`AGENTS.md` がすでに存在していること。

provider に依存しない core と、**provider-aware な CI gate** を管理します。

1. `.git/hooks/pre-commit` drift block.
2. CI の drift/checkup gate。ファイルは `--provider` に依存します（下記参照）。
3. A marked maintenance contract in `AGENTS.md`.

`--provider github|gitlab|codebase|auto`（デフォルト `auto`）で、どの CI files をインストールするか選びます。`auto` は `.gitlab-ci.yml` と `origin` remote から provider を検出します（github.com → `github`、`gitlab` を含む host → `gitlab`、内部 Codebase など他の enterprise host → `codebase`、remote なし → `github`）:

| Provider | インストールされる CI files | Wiring note |
|---|---|---|
| `github` | `.github/workflows/harness-drift.yml` path-aware PR gate + `.github/workflows/harness-checkup.yml` weekly scan/drift checkup with a deduped issue。 | GitHub Actions で自動的に実行されます。 |
| `gitlab` | include 可能な `.gitlab/harness-ci.yml`（`harness-drift` は MR で、`harness-checkup` は schedule で artifact 付き）。 | `.gitlab-ci.yml` に `include: { local: .gitlab/harness-ci.yml }` を追加します。 |
| `codebase` | ポータブルな `.harness-ci/harness-guard.sh`（`drift`/`checkup` modes）+ wiring 用 `README.md`。 | script を MR check と scheduled pipeline step として登録します。 |

`AI_HARNESS_DOCTOR_SKIP=1` は local hook の明示的で監査可能な escape hatch です。`guard --remove --apply` は managed snippets を削除し、**すべての provider** の CI files をクリーンアップし（provider を切り替えても何も残りません）、可能な場合は byte-exact な既存 hook content を復元します。install も remove も非破壊的です。管理対象ファイルにはすべて `ai-harness-doctor:guard` マーカーが付与されるため、`guard --apply` はマーカーを持たないユーザー編集済みの CI ファイルを決して上書きしません（`manual-merge` を報告し、ファイルはそのまま残します）。また `--remove` は、管理対象ファイルがツールの出力と byte 単位で一致する場合にのみ削除します。手動で拡張された hook からは自身の guard ブロックだけを取り除き、変更済みのブロックは破壊せずスキップします。

**Self-bootstrap:** このリポジトリは自身の guard を実行します。`.github/workflows/harness-drift.yml` と `.github/workflows/harness-checkup.yml` は `assets/guard/` テンプレートから改変され、公開版の `npx -y ai-harness-doctor` ではなくリポジトリの**ローカル** CLI（`node bin/cli.js drift . --strict`）を実行します。そのため `scripts/` への変更は、まさに変更対象のコード自身によって gate されます。eval gate は soft（commit 済みの結果 JSON が存在する場合のみ有効）を維持し、PR review ステップは token の欠如/制限を許容するため、この guard がリポジトリ自身の CI を赤くすることはありません。

</details>

<details>
<summary><code>scan</code></summary>

5 つのクラスを検出します。config inventory、size/truncation risk、overlap candidates、file:line evidence 付き conflict candidates、nested `AGENTS.md` files です。さらに補完的な問い——*何が不足しているか*——を gap analysis で答えます（下記参照）。

さらに、**拡張された harness surface**——MCP servers、subagents、slash commands、hooks、permission rules——を inventory し、深刻度でランク付けした findings（HIGH/MEDIUM）を報告する **security checkup** を実行します:

- 平文の secrets（AWS / GitHub / OpenAI / Google / Slack / Anthropic の keys、private-key blocks、汎用の `api_key/secret/token=...`）を instruction および MCP/settings config files 全体で検出。
- `Bash(*)`、`*`、`defaultMode: bypassPermissions` などの過度に広い permissions。
- MCP の hygiene 問題: 安全でない `http://` transports と、credential 形式の env literals。
- 危険な hook/command 本文: `curl … | bash`、`rm -rf`、`--dangerously-skip-permissions` など。

デフォルトで 0 で終了します。`--fail-on-security` を付けると、HIGH-severity の finding が 1 つでもあれば `2` で終了し、CI gate として便利です。

さらに **gap analysis** を実行し、リポジトリを harness 完全性チェックリストと diff して、*不足している*必須インフラ（既存のものだけでなく）を報告します。これらの静的チェックは、スタックに関係なくどんな健全な harness にも必要な部分のみを対象とします。canonical なルート `AGENTS.md`（`G1`）、必須の `AGENTS.md` セクション（`assets/AGENTS.template.md` と同期、`G2`）、`AGENTS.md` を指す最小 pointer であるべき tool stub（`G3`）、drift-guard / 週次 checkup の CI workflow（`G4`）です。さらに、`SKILL.md` の中でこれまで裏付けとなるコードが無かった 2 つの[Named anti-patterns](SKILL.md#named-anti-patterns)を両方とも検出します: **Wholesale Dumping**（`G9`）——`AGENTS.md` が正規化した行の半分以上を `README.md` と共有している状態で、内容が agent 専用の推論不可能なルールへと蒸留されるのではなく、丸ごとコピーされたことを示します。そして **Silent Adjudication**（`G10`）——`AGENTS.md` が、まだ解消されていない signal の衝突（例: `npm` に対する `pnpm`）のどちらか一方を、もう一方をリポジトリ所有者の裁定に委ねた痕跡を残さないまま選んでいる状態を示します。各 gap は `level`（`ERROR`/`WARN`/`NOTICE`）、`item`、`message`、実行可能な `suggestion` を持ちます。`--fail-on-gaps` を付けると、ERROR レベルの gap（例: ルート `AGENTS.md` の欠落）が 1 つでもあれば `3` で終了します。

プロジェクトの技術スタックに依存する部分（普遍的に必須ではないもの）については、scan は **project snapshot** を出力します。これは agent/LLM が推論できる、コンパクトで事実ベースのリポジトリ記述です。

- `tech_stack`: manifest から検出した言語 / エコシステム（`go.mod`、`package.json`、`pyproject.toml`、`requirements.txt`、`Cargo.toml`、`pom.xml`、`Gemfile`、`composer.json` など）。
- `existing_files`: 存在する CI、git hook、lint/format、typecheck の設定ファイル、および drift-guard の pre-commit hook が導入されているか。
- `agents_sections`: 現在の `AGENTS.md` の H1 セクション。
- `maintenance_contract`: `AGENTS.md` に maintenance contract が埋め込まれているか。
- `mcp_tools` / `has_permissions`: 設定済みの MCP server、および permission ルールの有無。

かつて静的な `G5`–`G8` gap だったスタック依存の判断（pre-commit guard、maintenance contract、MCP 設定、permission 設定）は、この snapshot の事実となり、agent が判断できるよう委ねられます。

さらに **semantic consistency（意味的整合性）** チェックを実行し、`AGENTS.md` が*宣言*している内容と、コードの*事実*を突き合わせます。これにより、古くなった記述が（Phase 2 の drift ゲートだけでなく）checkup の時点で表面化します。これは**マルチエコシステム**対応で、Node/npm に加えて Python（`pyproject.toml` / `setup.py` / `requirements.txt`、pip/poetry/uv/pdm/pipenv）、Go（`go.mod`）、Rust（`Cargo.toml`）、Java（`pom.xml` / `build.gradle`）、Ruby（`Gemfile` / `.ruby-version`、bundler）を理解します。ビルド/テストコマンド（`npm run <script>` / `make <target>` に加えて `cargo run --bin <name>`、`go run ./<pkg>`、`poetry run <script>`）を `package.json` の scripts・`Makefile` の target・Cargo のバイナリターゲット・Go のパッケージパス・pyproject のコンソールスクリプトと、バッククォートで囲まれたリポジトリ相対パスをファイルシステムと、宣言されたパッケージマネージャを各エコシステムのコミット済み lockfile/マニフェスト（`Gemfile.lock` による bundler の照合を含む）と、宣言された言語/ランタイムのバージョンを各エコシステムのピン（`.nvmrc` / `engines.node`、`requires-python` / `.python-version`、`go.mod` の `go` ディレクティブ、`Cargo.toml` の `rust-version`、Java のコンパイラレベル、`.ruby-version` / `Gemfile` の `ruby` ディレクティブ）と照合します。各 finding は `category`（`command`/`path`/`package_manager`/`node_version`/`python_version`/`go_version`/`rust_version`/`java_version`/`ruby_version`）、`level`（`MISMATCH`/`MISSING`）、`declared`（宣言値）、`actual`（実際の事実）、任意の `line`、`suggestion` を持ちます。`--fail-on-semantic` を付けると、宣言がコードと矛盾する場合に `4` で終了します。

**agent 向けの完全な JSON レポート。** markdown モードでは、`scan` は完全な機械可読レポート（files、surface、security、`project_snapshot`、`semantic`、`gaps`）を安定した一時ファイル `${TMPDIR}/harness-scan-<hash>.json`（`<hash>` は解決済みのリポジトリパスから導出）に書き出し、末尾に `## Full JSON report` セクションを追加してそのパスを示します。ワークフローを駆動する agent はこのファイルを読み、markdown を再解析することなく snapshot と gap をもとに推論と修正計画を立てられます。`--json` モードはすでに完全なレポートを stdout に出力するため、一時ファイルは書かれません。`--no-report-file` で書き込みをスキップできます。

**モノレポ / マルチパッケージ対応。** `scan` はモノレポに対応しています。ワークスペース（`package.json` の npm/yarn/pnpm `workspaces`、`pnpm-workspace.yaml`、または `--monorepo` 指定時の複数のネストした `package.json` / `AGENTS.md` サブツリー）を検出すると、検出した各パッケージのサブディレクトリを追加でスキャンし、パッケージごとの結果とトップレベルの集計を報告します。markdown レポートには `## Monorepo` セクション（パッケージごとの表と集計行）が追加され、`--json` にはトップレベルの `packages` 配列（パッケージごとに 1 件、`report` 配下に同じ形のスキャン結果と `summary`）と `monorepo` オブジェクト（`source`、`package_count`、`aggregate`）が追加されます。ワークスペースが検出されない場合は単一リポジトリの挙動は変わりません。`--no-monorepo` でルートのみのスキャンを強制し、`--monorepo` で検出を強制できます。

**カスタムルールプラグイン。** `scan`（および `drift`）は、独自の決定論的ルールで拡張できます。対象リポジトリの `.ai-harness-doctor/rules/*.py` ディレクトリに Python モジュールを置くか、`--rules DIR`（繰り返し指定可）を渡します。各モジュールは `def check(root, context) -> list[dict]:` を公開し、findings（`level`、`message`、任意の `path`/`line`/`suggestion`、および `rule` id）を返します。`context` には実行の `phase` と `AGENTS.md` のテキストが入ります。findings は `custom` セクション（markdown の `## Custom rule plugins` と `--json` の `custom` 配列）にマージされます。プラグインはオプトインです——ルールディレクトリも `--rules` もなければ挙動は変わりません。インポートに失敗したり実行時に例外を投げるプラグインは隔離され、スキャンをクラッシュさせる代わりに `level: "ERROR"` の finding として報告されます。テンプレートは `references/example-rule-plugin.py` を参照してください。

**マルチリポジトリ・バッチモード。** `scan --repos-file PATH` は、単一の `repo_root` の代わりに `PATH` に列挙された各リポジトリ（1 行 1 パス、空行と `#` コメントは無視）をスキャンし、組織横断の health summary を出力します——これまで手動でリポジトリごとに実行する以外に手段のなかった "Mixed-tool team" / "OSS メンテナー" persona 向けです。各リポジトリはそれぞれ自身のルートで独立にスキャンされます（このモードではリポジトリ内の monorepo パッケージ展開は行いません）。ディレクトリとして解決できないパスは、バッチ全体を中断させることなく "Repos that could not be scanned" に列挙されます。`--json` は `{ summary: { repo_count, error_count, aggregate }, repos: [{ path, resolved, name, has_agents_md, summary, report } | { path, resolved, error }] }` を返します。`--fail-on-security` / `--fail-on-gaps` / `--fail-on-semantic` はスキャンされた全リポジトリを考慮するため、このモードは組織全体の CI ゲートとして使えます。`repo_root` の位置引数とは排他的です。

**GitHub ネイティブな findings（SARIF）。** `scan` と `drift` はいずれも `--sarif` を受け付け、SARIF 2.1.0 ドキュメントを stdout に出力します。これにより findings が GitHub の Security タブや PR のインラインアノテーションに表示されます。`--sarif` は `--json`/markdown より優先され、`--no-*` による抑制に関係なく完全なレポート（ルート + すべての monorepo パッケージ）から生成されます。ソースレベルは SARIF レベルにマッピングされます（`HIGH`/`ERROR`→`error`、`MEDIUM`/`WARN`/`NOTICE`→`warning`、それ以外→`note`）。

```bash
# Emit SARIF 2.1.0 to a file for GitHub code scanning
npx ai-harness-doctor scan . --sarif > ai-harness-doctor.sarif
npx ai-harness-doctor drift . --sarif > drift.sarif
```

再利用可能な composite GitHub Action がリポジトリのルート（`action.yml`）に同梱されているので、どのリポジトリでも 2 ステップでツールを実行し SARIF をアップロードできます：

```yaml
# .github/workflows/harness-sarif.yml (excerpt)
- uses: NieZhuZhu/ai-harness-doctor@v1
  with:
    command: scan
    path: .
- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: ai-harness-doctor.sarif
```

Action はデフォルトで選択した Action ref に同梱された実装を実行するため、`uses:` で指定したバージョンが実際に動くコードになります。別の npm バージョンまたはタグを意図的に使う場合に限り、任意の `version` input を設定してください。インストールまたは CLI の失敗は workflow にそのまま伝播し、空の SARIF ファイルを残したままジョブが成功扱いになることはありません。

| Flag | Purpose |
|---|---|
| `--no-security` | inventory のみ。security checkup をスキップします（`security` key を出力しません）。 |
| `--fail-on-security` | HIGH-severity の security finding があれば `2` で終了します。 |
| `--no-gaps` | gap analysis をスキップします（`gaps` key を出力しません）。 |
| `--fail-on-gaps` | ERROR レベルの harness gap があれば `3` で終了します。 |
| `--no-semantic` | semantic consistency チェックをスキップします（`semantic` key を出力しません）。 |
| `--fail-on-semantic` | AGENTS.md の宣言がコードと矛盾する場合に `4` で終了します。 |
| `--no-snapshot` | project snapshot をスキップします（`project_snapshot` key を出力しません）。 |
| `--no-report-file` | 完全な JSON レポートを一時ファイルに書き出しません（markdown モードのみ）。 |
| `--monorepo` | モノレポモードを強制します。ワークスペース設定がなくても各パッケージのサブディレクトリをスキャンします（ネストした `package.json` / `AGENTS.md` サブツリーにフォールバック）。 |
| `--no-monorepo` | モノレポ検出を無効化し、リポジトリのルートのみをスキャンします。 |
| `--repos-file PATH` | `PATH` に列挙された各リポジトリをスキャンし、単一リポジトリの代わりにクロスリポジトリのサマリーを出力します（上記参照）。`repo_root` とは排他的です。 |
| `--rules DIR` | `DIR` からカスタムルールプラグインを読み込みます（繰り返し指定可）。`.ai-harness-doctor/rules/` と共に `custom` セクションへマージされます。 |
| `--no-custom` | カスタムルールプラグインをスキップします（`custom` key を出力しません）。 |
| `--sarif` | GitHub code scanning 向けに SARIF 2.1.0 JSON を stdout に出力します（`--json` より優先）。 |

`--json` returns（既存の keys は変更なし——後方互換）:

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
  ],
  "custom": [
    { "level": "ERROR", "rule": "plugin-load", "plugin": ".ai-harness-doctor/rules/broken.py", "message": "", "suggestion": "" }
  ],
  "semantic": {
    "checked": 0,
    "mismatches": 0,
    "findings": [
      { "category": "command", "level": "MISMATCH", "line": 12, "declared": "npm run lint", "actual": "no such package.json script", "message": "", "suggestion": "" }
    ]
  }
}
```

`security` の findings は `level`（`HIGH`/`MEDIUM`）、`category`（`secret`/`mcp`/`permission`/`hook`/`instruction`）、`path`、および人間が読める `message` を持ちます。`--no-security` では `security` key は省略されます。`gaps` の entries は `check`（`G1`–`G4`）、`level`（`ERROR`/`WARN`/`NOTICE`）、`item`、`message`、`suggestion` を持ちます。`--no-gaps` では `gaps` key は省略されます。`semantic` は `checked`（照合した宣言数）、`mismatches`、`findings`（各 finding は `category`、`level`、任意の `line`、`declared`、`actual`、`message`、`suggestion`）を持ちます。`--no-semantic` では `semantic` key は省略されます。`--no-snapshot` では `project_snapshot` が省略されます。`custom` はユーザールールプラグインの findings を保持します（各 finding は `level`、`message`、`plugin`、`rule`、および任意の `path`/`line`/`suggestion`）。`--no-custom` では `custom` key は省略されます。markdown モードでは、同じ JSON オブジェクトが `${TMPDIR}/harness-scan-<hash>.json` にも書き出されます（`--no-report-file` を指定した場合を除く）。モノレポモードでは、レポートにトップレベルの `packages` 配列と `monorepo` サマリーも追加されます。

</details>

<details>
<summary><code>plan</code></summary>

scan output から Phase 1 の merge plan を組み立てます。inventory、overlap clusters、conflict list、TODO decision checklist を含みます。content を merge したり、どちらかを選んだりは明示的に **しません**。

さらに、scan から導出した **「Merge suggestions (semi-automatic)」** section を追記します:

- **Overlap consolidation** —— 各 overlap cluster は canonical file（`AGENTS.md`）を示し、stub に落とすべき files を checkbox list で列挙します。
- **Conflict resolutions** —— 各 conflict signal に推奨値を 1 つ与え、それを裏付ける `path:line` evidence を tick 可能な item として付け、短い **rationale**（根拠）も添えます。推奨は決定的かつ事実ベースです。`package_manager` は committed lockfile が裏付ける manager を優先し、`node_version` は `.nvmrc` / `engines.node` が固定するバージョンを優先し、それ以外は最も支持された値にフォールバックします（同点の場合は辞書順）。

これらは人間のレビュー用の suggestions であり、自動裁定ではありません。既存の inventory/overlap/conflict/TODO sections は保持されます。

</details>

<details>
<summary><code>draft</code></summary>

空の skeleton ではなく、具体的で事実由来の内容を埋めた **スターター `AGENTS.md`** を自動ドラフトします。`npx ai-harness-doctor draft <repo> [-o AGENTS.md]`（または直接 `python3 scripts/canonicalize.py <repo> --draft [-o AGENTS.md]`）として起動します。scan の read-only passthrough で、スキャン対象 repo を一切変更しません。

ドラフトは `scan.py` / `semantic.py` の決定的な repository facts を再利用し、すべての canonical section（`Project overview`、`Build & test`、`Conventions`、`Testing requirements`、`Safety`、`Commit & PR`）を埋めます:

- 検出された tech stack（`package.json`、`pyproject.toml` などの manifest から）;
- `package.json` の `scripts` と `Makefile` targets から導出した build/test コマンド（committed lockfile が裏付ける package manager を使用）;
- 検出された CI、lint/format、type-check ツール;
- scan が報告する **すべての conflict の default 解決策**（例: lockfile が裏付ける package manager を優先）と、その rationale。

推論された行はすべて `(inferred — confirm)`、安全な既定の慣習は `(suggested default)` とタグ付けされ、先頭の banner が commit 前のレビュー・編集を促します。`-o` なしでは stdout に出力し、`-o PATH` ではファイルに書き込みますが、既存ファイルは `--force` を付けない限り上書きを拒否します。

</details>

<details>
<summary><code>validate</code></summary>

正本 `AGENTS.md` を書いた後、その構造を検証します。`scripts/canonicalize.py --validate` への read-only passthrough です。

デフォルトでは `Project overview`、`Build & test`、`Conventions` の見出しを必須とします。独自のカンマ区切りリストを `--require-sections` に渡すと、どの見出しを必須にするかを変更できます（欠けている見出しは `SECTION` の指摘として報告されます）：

```bash
python3 scripts/canonicalize.py --validate . --require-sections "Project overview,Build & test,Security"
```

</details>

<details>
<summary><code>stubs</code></summary>

`AGENTS.md` が存在した後で、既存の tool files を最小限のポインタへ降格します。

| Tool | Downgrade strategy |
|---|---|
| Claude | `CLAUDE.md` / `.claude/CLAUDE.md` import `@AGENTS.md`. |
| Cursor | `.cursorrules` points to `AGENTS.md`; `.cursor/rules` becomes one always-apply pointer. |
| Windsurf | `.windsurfrules` becomes a pointer. |
| Copilot | `.github/copilot-instructions.md` becomes a pointer. |
| Gemini | `GEMINI.md` becomes a pointer and recommends `contextFileName`. |
| Cline | `.clinerules` becomes a pointer. |
| Roo | `scan` で検出されます（`.roo/rules/*.md`）が、降格は**されません**。単一の慣例的な stub 位置を持たない rules-directory 型ツールのため、scan-only のままです。 |
| Continue | `.continuerules` が `AGENTS.md` へのポインタになります。`.continue/rules/*.md` は `scan` で検出されますが降格はされません。 |
| Trae | `scan` で検出されます（`.trae/rules/project_rules.md`）が、降格は**されません**。Roo と同様、単一の慣例的な stub 位置を持ちません。 |

デフォルトは dry-run です。`--apply` には clean git tree が必要です。`--force` はその safety check を上書きします。

既知のツール config ファイルは `assets/agent-tools.json` に一元定義されています。これは `scan`、`stubs`/`canonicalize`、`drift` がすべて読み込む唯一の registry なので、新しいツールの追加はこのファイル 1 つを編集するだけで済みます。

同じ考え方で、`adapters/` 配下のコマンド別 Codex/Cursor/Gemini アダプターは単一ソースから生成されます。`scripts/gen_adapters.py` が 1 つのコマンド表から全 15 ファイル（5 コマンド × 3 フレーバー）を描画し、`python3 scripts/gen_adapters.py --check`（`npm run lint:adapters` も同じ）は commit 済みのアダプターがそのソースからドリフトすると CI を失敗させ、`npm run gen:adapters` で再生成します。

</details>

<details>
<summary><code>drift</code></summary>

`AGENTS.md` を repo reality と照合します。Exit code は blocking drift がなければ 0、errors があれば 1 です。`--strict` は notices を errors に昇格します。

Example finding lines:

- D1: `Unknown package.json script test:unit-old`
- D2: `Referenced path src/old-components does not exist`
- D3: `Tool stub CLAUDE.md regrew or lost AGENTS.md pointer`
- D4: `AGENTS.md is 41000 bytes, above 32768`
- D5: `Nested AGENTS.md inventory` (informational, non-blocking)
- D6: `AGENTS.md declares Node 18 but .nvmrc pins 20` (fact drift)
- D7: `Markdown link target references/runbook.md does not exist` (Markdown-link drift)
- D8: `Competing package-manager lockfiles committed (package-lock.json, pnpm-lock.yaml)`

**D6 fact drift** は `AGENTS.md` で宣言された *facts* を repo の ground truth と cross-validate します。Node version（`.nvmrc` と `package.json` の `engines.node` と照合）と package manager（実際の lockfile と照合——`package-lock.json`→npm、`pnpm-lock.yaml`→pnpm、`yarn.lock`→yarn）です。明確な矛盾のみを flag し、`AGENTS.md` が沈黙している場合は沈黙するため、沈黙が false positive を生むことはありません。

**D7 Markdown-link drift** は `AGENTS.md` 内の repo 相対 Markdown link target（`[text](path)`）を probe し、すでに存在しない file や directory を指す link を flag します。D2（backtick で囲まれた token のみを probe）を補完します。URL、ページ内 anchor、repo 外の target は無視されるため、repo の外を probe することはありません。

**D8 competing lockfiles** は複数の package manager の lockfile を同時に commit している repo（例: `package-lock.json` と `pnpm-lock.yaml` の両方）を flag します。どの package manager を意図しているのか曖昧になるためです。これは manual attention として報告されます——どの lockfile を削除すべきか、tool が推測することはありません。

**Health score.** すべての findings（D1..D8）を 0–100 の health score に集約し、letter grade（A ≥90 / B ≥80 / C ≥70 / D ≥60 / F）を付け、`## Health score` section として表示します（例: `Score: 85/100 (grade B)`）。`--json` を付けると、report は既存の fields に加えて `score` と `grade` keys を持ちます。

`--min-score N` は score が `N` を下回ると non-zero で終了します——`--strict` から独立した CI gate なので、両方を同時に適用できます。

**半自動修復: `--fix`。** `--fix` は drift のうち安全で機械的な subset のみを自動修復します——現在は **D3 stub regrowth** です。real content が育ってしまった、あるいは `AGENTS.md` pointer を失った tool stub は、最小の canonical import-stub の形に書き戻されます（stub 本体は `canonicalize.py` から再利用されるため、`--fix` と `stubs`/`--write-stubs` は同期を保ちます）。

```bash
npx ai-harness-doctor drift . --fix          # DRY RUN: prints the diff, writes nothing
npx ai-harness-doctor drift . --fix --apply  # actually rewrites the regrown stubs
```

- デフォルトの `--fix` は dry run です。書き換え対象の unified diff を出力し、ファイルは変更しません。
- `--fix --apply` は育ってしまった stub files をその場で書き換えます。
- 安全でない drift（D1 command drift、D2 path drift、D4 size、D7 Markdown-link drift、D8 competing lockfiles、その他あらゆる semantic drift）は決して変更されません。**「needs manual attention」** の下に、コピペ可能な repair guidance 付きで列挙されます。
- summary line が `N fixed/fixable, M need manual attention` を報告します。drift が残っている限り、command は non-zero で終了します。

</details>

<details>
<summary><code>eval</code></summary>

before/after agent tasks を実行または比較します。

**ゼロコンフィグのタスク。** `tasks.json` を手書きする必要はありません。`--generate REPO` はリポジトリの事実（`package.json` の scripts/engines/deps、ロックファイル、`.nvmrc`、`go.mod`、`pyproject.toml`、および `AGENTS.md` の規約）から決定的なタスクセットを導出し、各 check は真の事実を regex でエンコードします。したがってスコアが高いほど `AGENTS.md` が効いたかどうかを直接反映します：

```bash
npx ai-harness-doctor eval --generate . -o tasks.json   # auto-generate tasks from repo facts
```

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

Checks は extracted answer に対する `regex`、workdir で実行する `command`、または open-ended な LLM-as-judge grading のための `judge` にできます。Claude CLI JSON output の場合、grading は matching の前に `result` field を抽出します。Usage/cost fields は存在する場合に捕捉されます。`--compare before.json after.json` は Markdown comparison を書きます。`--regrade results.json --tasks tasks.json` は recorded outputs を offline で再採点します。runner binary がない場合、この command は実行したふりをせず、manual protocol fallback を表示します。

**Multi-agent matrix.** 同じ task set を複数の runner（"agents"）で実行し、並べて比較します。runner は繰り返し可能な `--runner-cmd NAME=CMD` でインラインに、または `--matrix agents.json`（agent 名 → runner command template の mapping）で指定します。`--matrix-report FILE` は Markdown matrix（行 = tasks、列 = agents、cell = pass/fail + duration、加えて agent ごとの pass-rate summary）を書き、`--matrix-json FILE` は agent ごとの task records を `summary` block（`passed`、`total`、`pass_rate`）付きで書きます。single-runner の before/after/compare フローは変わりません。matrix mode は `--matrix` および/または `--runner-cmd` が指定された場合にのみ有効化されます。

```bash
npx ai-harness-doctor eval --tasks tasks.json --workdir . \
  --runner-cmd "claude=claude -p {prompt} --output-format json" \
  --runner-cmd "codex=codex exec {prompt}" \
  --matrix-report matrix-report.md --matrix-json matrix-results.json
```

**LLM-as-judge check.** task check は、regex では表現できない grading のために `{ "type": "judge", "rubric": "..." }` を使えます。`--judge-cmd "CMD_TEMPLATE"` が指定されている場合はそれが優先されます：judge は env `JUDGE_ANSWER`、`JUDGE_RUBRIC`、`JUDGE_INPUT`（一時 JSON `{answer, rubric}` へのパス）を受け取り、template placeholders `{answer}`/`{rubric}`/`{input}` が置換されます。judge は `{"passed": bool, "score": number, "reason": "..."}` を出力する必要があります。`passed` が省略された場合、`score >= 0.5` を pass とみなします。offline の決定的な judge は CI に適しています。

**実 LLM と組み込み judge。** `--judge-cmd` が指定されない場合、`judge` check は `--judge-llm {auto,openai,claude,off}`（デフォルト `off` —— 決定的な組み込みキーワード judge。環境に存在する API key が採点を黙って実モデルに切り替えることは決してなく、`auto` で明示的にオプトインします）で実 LLM により採点できます：`auto` は `OPENAI_API_KEY` があれば OpenAI を、なければ `ANTHROPIC_API_KEY` があれば Claude を、Python 標準ライブラリのみで呼び出します（SDK 不要）。モデル/エンドポイントは `OPENAI_MODEL`/`OPENAI_BASE_URL`、`ANTHROPIC_MODEL`/`ANTHROPIC_BASE_URL`、または `--judge-model` で設定できます。あらゆる失敗（key なし、ネットワークエラー、不正な応答）は、決定的で依存関係のない組み込みキーワード judge に透過的にフォールバックします（判定は `{passed, score, reason, judge:"builtin"}`；LLM の判定は `judge:"llm:openai"`/`"llm:claude"` とタグ付けされます）。キーワード judge は優先順位で採点します：`check.expect` —— すべて一致（大文字小文字を区別しない）する必要がある regex；`check.reject` —— 一致してはならない regex；それ以外はフリーテキストの `check.rubric` / `check.criteria` から導出したキーワード網羅率で、`>= check.min_score`（デフォルト `0.5`）のとき pass となります。`--judge-llm off` でキーワードのみの採点、`--no-default-judge` で外部の `--judge-cmd` を必須にできます。

```bash
npx ai-harness-doctor eval --tasks tasks.json --workdir . --label after --judge-llm auto   # real LLM judge, keyword fallback
```

**Health score.** すべての eval は、ワンクリックの効果 health score = すべての task record にわたる pass rate も計算します。`0–100` で表され、A–F の letter grade（A ≥90 / B ≥80 / C ≥70 / D ≥60 / F）が付きます。これは single-run results（`{"tasks":...}`）と matrix results（`{"agents":...}`）の両方に `health` key として埋め込まれ、要約行（`health score: N/100 (grade X), P/T tasks passed`）として表示されます。timeout は failure として数えられます。`--score PATH` は既存の results/matrix JSON の health score を表示し（`--json` で機械可読出力）、`--fail-under N` は health score が `N` を下回ると exit code `5` で終了します（CI gate）。

**マルチラウンド安定性（`--rounds`）。** `--rounds N`（N > 1）はタスクセット全体を N 回実行し、安定性統計を集計します。これにより、一部の実行では pass し他では fail する *flaky*（不安定）なタスクを可視化できます。この場合、results JSON には `rounds`、`round_results`（各ラウンドの完全な task record とラウンドごとの `health`）、per-task の `task_stats` 配列（`runs`、`passed`、`failed`、`timed_out`、`pass_rate`、`flaky`）、および `stats` 要約（`mean_health`、`variance`、`stddev`、`min_health`、`max_health`、`health_scores`、`flaky_tasks`、`flaky_count`）が含まれます。あるタスクは、全ラウンドで pass するわけでも全ラウンドで fail するわけでもないとき `flaky` になります。全体の `health` はすべての task-run にわたる pass rate であり、`--fail-under N` はこれに対する gate です。`--rounds 1`（デフォルト）は従来の single-round 出力構造をバイト単位で変更しません。`--stats PATH` は既存のマルチラウンド results ファイルをオフラインで再集計します（`--json` で機械可読出力、`--fail-under N` で gate）。

```bash
npx ai-harness-doctor eval --tasks tasks.json --workdir . --label nightly --rounds 5   # run 5x, aggregate stability stats
npx ai-harness-doctor eval --stats results-nightly.json --json                         # re-analyze an existing multi-round file
```

**ベースライン、トレンドと回帰。** 各実行の health score を追記専用のベースライン履歴として保存します（`--baseline FILE` + `--save-baseline`）。タイムスタンプ、label、スコア/グレード、pass 数、および対象リポジトリの git commit/branch を記録します。`--check-regression` は現在のスコアを直近の履歴スナップショットと比較し、`--regression-threshold` 分（デフォルト `5`）以上低下したとき exit code `6` で終了します。`--trend FILE` は履歴をスナップショットごとの差分と回帰フラグ付きの Markdown 表として表示します。任意の実行モードおよび `--score` と組み合わせられます。

```bash
npx ai-harness-doctor eval --tasks tasks.json --workdir . --label after -o results.json \
  --baseline baselines/history.json --save-baseline --check-regression   # save + gate on regressions
npx ai-harness-doctor eval --trend baselines/history.json                  # render the recorded trend
```

</details>

<details>
<summary><code>mcp</code></summary>

MCP（Model Context Protocol）stdio server を起動し、agents が doctor の read-only な機能を tools として呼び出せるようにします。

```bash
npx ai-harness-doctor mcp   # or directly: node bin/mcp-server.js
```

Transport は newline-delimited JSON 上の JSON-RPC 2.0 です（stdin/stdout で 1 行につき 1 つの JSON object）。サポートされる methods:

- `initialize` → `{ protocolVersion, capabilities: { tools: {} }, serverInfo: { name, version } }`。
- `notifications/initialized` → notification、response なし。
- `tools/list` → `harness_scan`、`harness_drift`、`harness_validate`、`harness_plan`、`harness_stubs`、`harness_eval_generate` を、それぞれ input schema `{ repo: string (default "."), ... }` 付きで広告します。
- `tools/call` → 対応する Python script へ dispatch し、`{ content: [{ type: "text", text }] }` を返します。

Tool booleans: `harness_scan`（`json`）、`harness_drift`（`json`、`strict`）、`harness_validate`（`json`）、`harness_plan`、`harness_stubs`、`harness_eval_generate`。`harness_stubs`（Phase 1 の stub 降格プレビュー）と `harness_eval_generate`（Phase 3 のタスクセット bootstrap）は MCP 上では常に read-only です。どちらも `--apply`/`-o` を受け取ることはないため、diff のプレビューまたは生成された JSON の出力しかできず、リポジトリへの書き込みは一切行いません。未知の methods と tools は JSON-RPC error object を返します。

</details>

<details>
<summary><code>doctor</code></summary>

Node + Python のデュアルランタイム向けの単一エントリポイント runtime self-test です。Python 子コマンドと同じ共有 resolver を通じて Python インタプリタを解決し、Node、解決された Python 3 インタプリタ、各 Python engine、および MCP server ファイルを報告します。いずれかのチェックが失敗すると非ゼロで終了します。

```bash
npx ai-harness-doctor doctor --self-test   # human-readable runtime table
npx ai-harness-doctor doctor --json        # machine-readable runtime report
```

Python は優先順位順に検出されます: `AI_HARNESS_DOCTOR_PYTHON`、次に `PYTHON`、次に `python3`、次に `python`。Python **3** インタプリタのみが受け入れられます。存在しない場合、すべての Python 子コマンド（`scan`、`plan`、`validate`、`stubs`、`drift`、`eval`）は、raw stack trace ではなく同じ明確で実行可能なメッセージ（Python 3 をインストールするか `AI_HARNESS_DOCTOR_PYTHON` を設定する）で失敗します。

</details>

Slash command quick refs: `/harness-doctor` full pipeline; `/harness-scan` Phase 0; `/harness-treat` Phase 1; `/harness-drift` Phase 2; `/harness-eval` Phase 3.

Environment variables:

| Variable | Purpose |
|---|---|
| `AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1` | once-daily npm update nudge を無効化します。 |
| `AI_HARNESS_DOCTOR_SKIP=1` | local pre-commit drift hook を明示的に bypass します。 |
| `AI_HARNESS_DOCTOR_PYTHON` | すべての Python 子コマンドが使用する Python 3 インタプリタを固定します。 |

`AI_HARNESS_DOCTOR_FORCE_UPDATE_CHECK` and `AI_HARNESS_DOCTOR_REGISTRY` are internal/testing knobs.

## Benchmark

[`benchmark/results/`](benchmark/results/) から得た最終検証済み結果です。

| Side | Runs | Passed | Flip-flop tasks | Avg latency/task | Total captured cost |
|---|---|---:|---:|---:|---:|
| BEFORE: conflicting/stale configs | 14 objective tasks × 2 runs | 6/28 (21%) | 2 | 16.0s | $5.82 |
| AFTER: canonical `AGENTS.md` via this tool | 14 objective tasks × 2 runs | 28/28 (100%) | 0 | 11.7s | $4.81 |
| Delta | after - before | +22 correct attempts | -2 | -27% | -17% |

矛盾した configs は、単に誤答を生むだけではありません。**不安定な** 回答を生みます。canonicalization 前には `node` と `moduletype` で同じ質問の答えが run 間で反転しましたが、後には一度も反転しませんでした。

methodology、tasks、grading、reproduction commands は [`benchmark/README.md`](benchmark/README.md) を参照してください。正直な範囲: one demo repo、各 side N=2 runs、objective Q&A tasks、runner `claude -p` with Claude CLI 2.1.202。

## Positioning & Non-goals & Comparison

### Positioning

AI Harness Doctor は Claude Code 公式 `/init` と補完関係にあります。`/init` は config をゼロから bootstrap しますが、AI Harness Doctor は既存の sprawl を診断し、統合し、守り、検証します。`SKILL.md` は明示的に `/init` の lane には入りません。

Regeneration と guarding はどちらも有効な思想です。Ruler/rulesync は generated outputs を disposable にします。AI Harness Doctor は `AGENTS.md` を人間が所有するものとして保ち、drift から守ります。だからこそ、静かな regeneration ではなく detection を好みます。repo が変わったとき、agent contract も変わったことをチームが知るべきだからです。

### Non-goals

- from-scratch init はしません。それは `/init` の lane です。
- 衝突を静かに裁定することはありません。file:line evidence を示し、人間に尋ねます。
- Scripts は semantic merging を行いません。
- unattended writes はしません。dry-run defaults、`--apply`、clean-tree checks は意図的な設計です。
- language/framework style-guide generation はしません。
- bulk rules distributor ではありません。20+ tool fan-out には rulesync を使い、下の comparison を参照してください。
- telemetry はありません。唯一の network call は once-daily npm version check で、無効化できます。

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
- Each release self-tests the tagged Action before npm publish, moves the matching floating major Action tag (`v1` for `1.x`), verifies it as a consumer would, and opens a Marketplace confirmation reminder.
- See [`RELEASING.md`](RELEASING.md).
- Every published version has a git tag.

## Repository layout

```text
SKILL.md                         # Skill playbook and phase stop conditions
bin/cli.js                       # npm CLI and installer
bin/mcp-server.js                # MCP stdio server (harness_scan/drift/validate/plan/stubs/eval_generate)
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

- Repo harness-ification: project scripts を CLI 化し、verification gates を追加し、docs をきれいに階層化する。
- より多くの languages、repo shapes、multi-turn workflows に対応する richer eval task packs。
- command formats が安定したら、さらに agent adapters を追加する。
- custom-command format が文書化されたら、Antigravity CLI adapter を追加する。

## Contributing

Bug reports と focused PRs を歓迎します。scripts は deterministic、stdlib-only を保ち、次で cover してください。

```bash
python3 -m unittest discover -s tests -v
```

リポジトリには npm ベースの lint/format/test ワークフローも同梱されています（開発専用で、公開パッケージには含まれません）。CI は Python（3.9/3.10/3.12）と Node（16/20/22）のバージョンマトリクスで全スイートを実行します。

```bash
npm test            # Python unittest + node --test CLI suite
npm run lint        # eslint (bin) + ruff (scripts/tests) + trilingual README structure sync
npm run format      # prettier --write .   (npm run format:py for ruff format)
```

`npm run lint:docs`（すなわち `scripts/check_readme_sync.py`）は `README.md`、`README.zh-CN.md`、`README.ja.md` が同一の見出し骨格を保つことを強制します。したがって、いずれかの README の構造変更は他の 2 つにも反映する必要があります。

## License

MIT. Copyright (c) NieZhuZhu.
