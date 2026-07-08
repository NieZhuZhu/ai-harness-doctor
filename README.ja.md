[English](README.md) | [简体中文](README.zh-CN.md) | **日本語**

# 🩺 AI Harness Doctor

リポジトリの AI ハーネスを診るドクターです。散らばった agent 設定を健診し、統合し、守り、効果検証して、1 つの正本 `AGENTS.md` にまとめます。

[![CI](https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml/badge.svg)](https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml)
[![npm version](https://img.shields.io/npm/v/ai-harness-doctor.svg)](https://www.npmjs.com/package/ai-harness-doctor)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![Node >=16](https://img.shields.io/badge/Node-%3E%3D16-green.svg)

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

Claude Code skill をインストールし、対象リポジトリでドクターを実行します。

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
| `scan` | ✅ | ❌ | デフォルトで 0 で終了します。inventory、evidence、security checkup を行います。`--fail-on-security` は HIGH の findings があれば 2 で終了します。 |
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

なぜ regeneration ではなく detection なのか。ドリフトを静かに「修正」すると、人間の認識が消えてしまいます。AI Harness Doctor は代わりに drift を表面化します。大事なのはファイルを書き換えることではなく、repo の真実と agent の真実がズレたことにチームが気づくことだからです。[Positioning & Non-goals & Comparison](#positioning--non-goals--comparison) も参照してください。

## Works with

| Surface | Support |
|---|---|
| Claude Code | native skill に加え、`.claude/commands` または `~/.claude/commands` 配下の slash commands。 |
| OpenAI Codex CLI | `~/.codex/prompts/` 向け prompt adapters。 |
| Cursor | `.cursor/commands/` 向け command adapters。 |
| Gemini CLI | `~/.gemini/commands/harness/` 向け TOML custom command adapters。Google は 2026-06-18 に個人 tier 向け Gemini CLI を retired しました。enterprise Gemini Code Assist は影響を受けず、これらの adapters は enterprise/existing installs で引き続き動作します。 |
| Windsurf / Cline / others | Universal mode: agent にインストール済み playbook を示し、「run phase N」と伝えます。 |
| MCP clients | `ai-harness-doctor mcp` は `harness_scan`/`drift`/`validate`/`plan` を stdio 経由の MCP tools として公開します。 |
| Humans & CI | 素の `npx ai-harness-doctor ...`。agent は不要です。 |

正直な注記: Claude 以外の adapters は薄いポインタで、検証は軽めです。command format が変わっていた場合は issue を立ててください。

## The four phases

| Phase | Script | Artifact | Stop condition |
|---|---|---|---|
| 0 — 健診 / scan | `scripts/scan.py` | 人間向けまたは JSON の health report | migration scope について user confirmation が得られたところで停止。 |
| 1 — 治療 / canonicalize | `scripts/canonicalize.py --plan`, `--write-stubs`, `--validate` | Merge plan、正本 `AGENTS.md`、minimal stubs | すべての conflict が人間に裁定されるまで停止。 |
| 2 — 経過観察 / drift guard | `scripts/check_drift.py` | Drift report と CI/pre-commit exit codes | checks が pass するか、修復アドバイスが出たところで停止。 |
| 3 — 効果検証 | `scripts/eval_run.py` | Before/after JSON と Markdown report | metrics が出たところで停止。 |

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

</details>

<details>
<summary><code>scan</code></summary>

5 つのクラスを検出します。config inventory、size/truncation risk、overlap candidates、file:line evidence 付き conflict candidates、nested `AGENTS.md` files です。

さらに、**拡張された harness surface**——MCP servers、subagents、slash commands、hooks、permission rules——を inventory し、深刻度でランク付けした findings（HIGH/MEDIUM）を報告する **security checkup** を実行します:

- 平文の secrets（AWS / GitHub / OpenAI / Google / Slack / Anthropic の keys、private-key blocks、汎用の `api_key/secret/token=...`）を instruction および MCP/settings config files 全体で検出。
- `Bash(*)`、`*`、`defaultMode: bypassPermissions` などの過度に広い permissions。
- MCP の hygiene 問題: 安全でない `http://` transports と、credential 形式の env literals。
- 危険な hook/command 本文: `curl … | bash`、`rm -rf`、`--dangerously-skip-permissions` など。

デフォルトで 0 で終了します。`--fail-on-security` を付けると、HIGH-severity の finding が 1 つでもあれば `2` で終了し、CI gate として便利です。

| Flag | Purpose |
|---|---|
| `--no-security` | inventory のみ。security checkup をスキップします（`security` key を出力しません）。 |
| `--fail-on-security` | HIGH-severity の security finding があれば `2` で終了します。 |

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
  ]
}
```

`security` の findings は `level`（`HIGH`/`MEDIUM`）、`category`（`secret`/`mcp`/`permission`/`hook`/`instruction`）、`path`、および人間が読める `message` を持ちます。`--no-security` では `security` key は省略されます。

</details>

<details>
<summary><code>plan</code></summary>

scan output から Phase 1 の merge plan を組み立てます。inventory、overlap clusters、conflict list、TODO decision checklist を含みます。content を merge したり、どちらかを選んだりは明示的に **しません**。

さらに、scan から導出した **「Merge suggestions (semi-automatic)」** section を追記します:

- **Overlap consolidation** —— 各 overlap cluster は canonical file（`AGENTS.md`）を示し、stub に落とすべき files を checkbox list で列挙します。
- **Conflict resolutions** —— 各 conflict signal に推奨値を 1 つ与え、それを裏付ける `path:line` evidence を tick 可能な item として付けます。推奨は決定的です（最も支持された値、同点の場合は辞書順）。

これらは人間のレビュー用の suggestions であり、自動裁定ではありません。既存の inventory/overlap/conflict/TODO sections は保持されます。

</details>

<details>
<summary><code>validate</code></summary>

正本 `AGENTS.md` を書いた後、その構造を検証します。`scripts/canonicalize.py --validate` への read-only passthrough です。

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

デフォルトは dry-run です。`--apply` には clean git tree が必要です。`--force` はその safety check を上書きします。

既知のツール config ファイルは `assets/agent-tools.json` に一元定義されています。これは `scan`、`stubs`/`canonicalize`、`drift` がすべて読み込む唯一の registry なので、新しいツールの追加はこのファイル 1 つを編集するだけで済みます。

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

**D6 fact drift** は `AGENTS.md` で宣言された *facts* を repo の ground truth と cross-validate します。Node version（`.nvmrc` と `package.json` の `engines.node` と照合）と package manager（実際の lockfile と照合——`package-lock.json`→npm、`pnpm-lock.yaml`→pnpm、`yarn.lock`→yarn）です。明確な矛盾のみを flag し、`AGENTS.md` が沈黙している場合は沈黙するため、沈黙が false positive を生むことはありません。

**Health score.** すべての findings（D1..D6）を 0–100 の health score に集約し、letter grade（A ≥90 / B ≥80 / C ≥70 / D ≥60 / F）を付け、`## Health score` section として表示します（例: `Score: 85/100 (grade B)`）。`--json` を付けると、report は既存の fields に加えて `score` と `grade` keys を持ちます。

`--min-score N` は score が `N` を下回ると non-zero で終了します——`--strict` から独立した CI gate なので、両方を同時に適用できます。

**半自動修復: `--fix`。** `--fix` は drift のうち安全で機械的な subset のみを自動修復します——現在は **D3 stub regrowth** です。real content が育ってしまった、あるいは `AGENTS.md` pointer を失った tool stub は、最小の canonical import-stub の形に書き戻されます（stub 本体は `canonicalize.py` から再利用されるため、`--fix` と `stubs`/`--write-stubs` は同期を保ちます）。

```bash
npx ai-harness-doctor drift . --fix          # DRY RUN: prints the diff, writes nothing
npx ai-harness-doctor drift . --fix --apply  # actually rewrites the regrown stubs
```

- デフォルトの `--fix` は dry run です。書き換え対象の unified diff を出力し、ファイルは変更しません。
- `--fix --apply` は育ってしまった stub files をその場で書き換えます。
- 安全でない drift（D1 command drift、D2 path drift、D4 size、その他あらゆる semantic drift）は決して変更されません。**「needs manual attention」** の下に、コピペ可能な repair guidance 付きで列挙されます。
- summary line が `N fixed/fixable, M need manual attention` を報告します。drift が残っている限り、command は non-zero で終了します。

</details>

<details>
<summary><code>eval</code></summary>

before/after agent tasks を実行または比較します。

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

**LLM-as-judge check.** task check は、regex では表現できない grading のために `{ "type": "judge", "rubric": "..." }` を使えます。grading は `--judge-cmd "CMD_TEMPLATE"` に委譲されます。judge は env `JUDGE_ANSWER`、`JUDGE_RUBRIC`、`JUDGE_INPUT`（一時 JSON `{answer, rubric}` へのパス）を受け取り、template placeholders `{answer}`/`{rubric}`/`{input}` が置換されます。judge は `{"passed": bool, "score": number, "reason": "..."}` を出力する必要があります。`passed` が省略された場合、`score >= 0.5` を pass とみなします。offline の決定的な judge は CI に適しています。

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
- `tools/list` → `harness_scan`、`harness_drift`、`harness_validate`、`harness_plan` を、それぞれ input schema `{ repo: string (default "."), ... }` 付きで広告します。
- `tools/call` → 対応する Python script へ dispatch し、`{ content: [{ type: "text", text }] }` を返します。

Tool booleans: `harness_scan`（`json`）、`harness_drift`（`json`、`strict`）、`harness_validate`（`json`）、`harness_plan`。未知の methods と tools は JSON-RPC error object を返します。

</details>

Slash command quick refs: `/harness-doctor` full pipeline; `/harness-scan` Phase 0; `/harness-treat` Phase 1; `/harness-drift` Phase 2; `/harness-eval` Phase 3.

Environment variables:

| Variable | Purpose |
|---|---|
| `AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1` | once-daily npm update nudge を無効化します。 |
| `AI_HARNESS_DOCTOR_SKIP=1` | local pre-commit drift hook を明示的に bypass します。 |

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
npm test            # Python unittest + node --test CLI スイート
npm run lint        # eslint (bin) + ruff (scripts/tests) + 三言語 README 見出し同期チェック
npm run format      # prettier --write .   （npm run format:py で ruff format）
```

`npm run lint:docs`（すなわち `scripts/check_readme_sync.py`）は `README.md`、`README.zh-CN.md`、`README.ja.md` が同一の見出し骨格を保つことを強制します。したがって、いずれかの README の構造変更は他の 2 つにも反映する必要があります。

## License

MIT. Copyright (c) NieZhuZhu.
