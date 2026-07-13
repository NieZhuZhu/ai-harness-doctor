[English](README.md) | **简体中文** | [日本語](README.ja.md)

# 🩺 AI Harness Doctor

**你的 AI 编码 agent 正自信满满地照着过时指令干活。** `CLAUDE.md`、`.cursorrules`、`GEMINI.md`、`AGENTS.md` 悄悄漂移，直到 agent 跑起早已不存在的脚本、改动早已搬走的路径，还在一个已经切到 `pnpm` 的仓库里教 `npm`。

AI Harness Doctor 让这种漂移可见，把散落的 agent 配置收敛到唯一 canonical `AGENTS.md`，并守护它，让仓库不再悄悄遗忘 —— 支持 Claude Code、Codex、Cursor、Gemini 以及纯 CI。一条零安装的 `scan` 就能给你一份完整体检：配置清单、冲突证据、安全审计、缺失的基础设施缺口，以及技术栈快照。

<p><a href="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml"><img align="left" alt="CI" src="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml/badge.svg"></a> <a href="https://www.npmjs.com/package/ai-harness-doctor"><img align="left" alt="npm version" src="https://img.shields.io/npm/v/ai-harness-doctor.svg"></a> <img align="left" alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"> <img align="left" alt="Python 3.9+" src="https://img.shields.io/badge/Python-3.9%2B-blue.svg"> <img align="left" alt="Node >=16" src="https://img.shields.io/badge/Node-%3E%3D16-green.svg"></p>
<br clear="left">

> **在我们的 14-task benchmark 中，把一个仓库 canonical 化后，agent 的正确答案从 6/28 提升到 28/28 —— 同时消除了同一个问题在不同轮次答案反复横跳的情况。** [看数据 ↓](#benchmark)

一条命令就能试 —— 无需安装，不往你的仓库写任何东西：

```bash
npx ai-harness-doctor scan .
```

## 为什么

Agent 配置漂移是一种仓库病。这个工具读 `CLAUDE.md`，那个工具读 `.cursorrules`，另一个又读 `GEMINI.md`；每个文件都会慢慢长成自己的江湖传说：过期命令、搬过家的路径、复制粘贴来的风格规则、互相矛盾的包管理器，以及大到会被截断的上下文文件。

最痛的是，agent 按照陈旧指令做事时听起来依然很自信。新维护者问测试命令，得到的是早已不存在的脚本。一次重构把 `src/components/` 移走了，但规则文件还指向 `app/ui/`。团队从 npm 切到 pnpm，可三个 agent 入口还在继续教 npm。

AI Harness Doctor 让这种漂移可见，帮助人或 agent 写出唯一 canonical `AGENTS.md`，把旧工具文件降级为小指针，并安装 guard，让仓库不再悄悄遗忘。

在我们的 14-task benchmark 中，canonical 化后的仓库让 agents 的正确答案从 6/28 提升到 28/28 —— 见 [Benchmark](#benchmark)。

## 用户故事

| 角色 | 痛点 | 命令 | 结果 |
|---|---|---|---|
| 新维护者 | 你接手了一个遗留仓库：有 2 年没更新的 `CLAUDE.md`，三代 `.cursorrules`，agent 还在运行不存在的脚本。 | `scan` → `/harness-treat` | 你拿到 file:line 证据，裁决冲突，并用一个 `AGENTS.md` 取代传说。 |
| 混用工具的团队 | Cursor、Claude Code 和 Codex 用户每周都在分叉规则文件。 | `plan` → `stubs --apply` → `guard --apply` | 工具专用文件变成 stubs，CI 阻止它们再次分叉。 |
| 悄悄腐烂的仓库 | 仓库已经从 npm→pnpm，目录也搬过家，但文档从没跟上。 | `drift . --strict` | 路径感知的 drift gate 会在陈旧指令进入 PR 前拦住它。 |
| 持怀疑态度的队友 | 有人说 agent 配置文件只是 cargo cult。 | `eval --tasks ...` before/after | 用真实数字结束争论：正确率、不稳定性、延迟和捕获到的成本。 |
| OSS 维护者 | AI 生成的 PR 总是遵循错误约定。 | `AGENTS.md` + `guard --apply` | 贡献者的 agents 会读取维护契约，并对自己的改动做自检。 |

## 快速开始

### 最快路径

零安装、只读体检 —— 一条命令在几秒内呈现你的 harness 的配置清单、冲突证据（带 file:line）、安全发现、缺失的基础设施缺口，以及技术栈快照：

```bash
npx ai-harness-doctor scan .
```

想开始修复？安装 Claude Code skill，让 agent 驱动完整流程：

```bash
npx ai-harness-doctor install
```

然后在 Claude Code 中：

```text
/harness-doctor .
```

回答冲突裁决问题。工具会报告证据；由你决定仓库的真实情况。

### 用 3 步应用到你的仓库

这里刻意没有真正的一键迁移。Phase 1 包含语义决策：工具永远不会替你决定 pnpm-vs-npm、test-vs-test:unit，或 old path-vs-new path。

```bash
npx ai-harness-doctor scan .
npx ai-harness-doctor plan . -o merge-plan.md
# Write AGENTS.md from the plan, then:
npx ai-harness-doctor validate .
npx ai-harness-doctor stubs . --apply
npx ai-harness-doctor guard . --apply
```

有三种方式编写 `AGENTS.md`：

1. 根据 `merge-plan.md` 和 `assets/AGENTS.template.md` 手写。
2. 让你的 coding agent 以 plan 为证据来写。
3. 使用 `/harness-treat .`：它会读取 plan，逐个冲突向你提问，写入文件，然后验证。

### 要求

- 目标必须是 git repo。
- `ai-harness-doctor` CLI 需要 Node >=16。
- 确定性的 scan/plan/validate/stubs/drift/eval 脚本需要 Python >=3.9，且只使用 stdlib。
- 运行 `ai-harness-doctor doctor --self-test` 可校验 Node + Python 运行时；设置 `AI_HARNESS_DOCTOR_PYTHON` 可指定特定解释器。
- 在 `stubs` 或 `guard` 写入任何内容之前，`AGENTS.md` 必须已经存在。

### 安装矩阵

```bash
npx ai-harness-doctor install                         # Claude Code, user-level
npx ai-harness-doctor install --agent codex
npx ai-harness-doctor install --agent cursor --project
npx ai-harness-doctor install --agent gemini
npx ai-harness-doctor install --agent all --project
npx ai-harness-doctor install --link                  # link to a global package
```

### 自动化矩阵

| 步骤 | CI 安全？ | 会写入？ | 说明 |
|---|---:|---:|---|
| `scan` | ✅ | ❌ | 默认以 0 退出；做清单、证据收集、一次安全体检、一次缺失基建的缺口分析、一次语义一致性检查（AGENTS.md 声明 vs 代码事实），以及一份技术栈项目快照。在 markdown 模式下还会把完整 JSON 报告写入临时文件并打印其路径。`--fail-on-security` 在出现 HIGH 级发现时以 2 退出；`--fail-on-gaps` 在出现 ERROR 级缺口时以 3 退出；`--fail-on-semantic` 在声明与代码矛盾时以 4 退出。 |
| `plan` | ✅ | 可选输出文件 | 搭建合并计划；不会执行合并。 |
| Write `AGENTS.md` | ❌ | ✅ | 由人或 agent 完成的语义步骤。 |
| `validate` | ✅ | ❌ | 检查 canonical `AGENTS.md` 是否包含必需章节。 |
| `stubs` | ✅ | 使用 `--apply` 时 | 除非使用 `--force`，否则要求工作区干净。 |
| `guard` | ✅ | 使用 `--apply` 时 | 要求目标是 git repo 且已有 `AGENTS.md`。 |
| `drift` | ✅ | ❌ | 遇到 blocking drift 会失败；`--strict` 会把 notices 提升为错误。 |

### 卸载与回滚

```bash
npx ai-harness-doctor guard . --remove --apply
npx ai-harness-doctor uninstall --agent all
```

`guard --remove` 按 marker 精确移除：只删除自己管理的片段，不会碰外来的 pre-commit hook。其他内容都可以通过 git revert 回滚。

## Slash commands

| 命令 | 输入 | Agent 会做什么 | 在哪里停止 | 由你决定什么 |
|---|---|---|---|---|
| `/harness-doctor` | 仓库路径，通常是 `.` | 运行完整的体检→治疗→复诊流程；只有在请求时才运行 eval。 | 在语义冲突解决前，以及可选 eval 前。 | 迁移范围、冲突真相、是否安装 guards。 |
| `/harness-scan` | 仓库路径 | 运行 Phase 0 清单、体积、重叠、冲突和 nested-agent 检测。 | 输出健康报告后。 | 是治疗整个仓库、某个子目录，还是选定文件。 |
| `/harness-treat` | 仓库路径，可选 scan/plan 输出 | 构建合并计划，询问冲突，写入/验证 canonical `AGENTS.md`，预览 stubs。 | 直到每个冲突都有明确答案。 | 哪个命令/路径/风格/版本是 canonical。 |
| `/harness-drift` | 仓库路径 | 运行 drift 检查并解释修复方式。 | 检查通过后，或给出修复建议后。 | 是更新仓库现实，还是更新 `AGENTS.md`。 |
| `/harness-eval` | 仓库路径 + task file/results | 运行或对比 before/after tasks。 | 产出指标或手动协议时。 | 任务集、runner，以及证据是否足够。 |

## 更新

复制安装会记录在 `~/.ai-harness-doctor/manifest.json`。要把最新 package 文件重新部署到所有此前安装过的位置，运行：

```bash
npx ai-harness-doctor@latest update
```

交互式命令最多每天检查一次 npm，并可能打印类似 `npx ai-harness-doctor@latest update` 的更新提示；设置 `AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1` 可关闭检查。只临时运行裸 `npx` CLI 的用户，如果想拿到最新的一次性命令，应显式指定 `ai-harness-doctor@latest`。

如果想要真正的热更新，请持久安装 package 并链接 payload：

```bash
npm i -g ai-harness-doctor
ai-harness-doctor install --link
npm update -g ai-harness-doctor
```

使用 `--link` 时，Claude 的 `~/.claude/skills/ai-harness-doctor` 会指向全局 package，其他 adapters 也指向同一个 package root，因此 `npm update -g ai-harness-doctor` 会立刻更新所有地方的 playbook。在 Windows 上，目录链接使用 junctions。

## 长期守护

> 这里保证的是检测，不是自动更新：doc-vs-repo 一致性会变成机器可检查的条件，并且能在三个地方失败——pre-commit、PR 和每周体检。遗忘不再是静默的。

在治疗阶段产出 canonical root `AGENTS.md` 后安装：

```bash
npx ai-harness-doctor guard . --apply
```

CI 卡点是 provider 感知的：传入 `--provider github|gitlab|codebase`（默认 `auto`）以安装匹配的 CI 文件。各 provider 的文件布局见 [`guard`](#command-reference) 命令参考。

在 pull request 上，GitHub guard 模板还会多做两件事。其一，把漂移发现项作为**内联 PR review 评论**呈现：`scripts/pr_review.py` 读取 `check_drift.py --json`（或 `scan.py --json`）报告并发布一条 PR review——带有 repo 相对 `path` 的发现项会变成内联 `{path, line, body}` 评论，无位置的发现项汇总进一条带有稳定标记 `<!-- ai-harness-doctor:pr-review -->` 的总结中。它默认 dry-run（打印 JSON 负载，绝不触网），仅在 `--post` 时用 `GITHUB_TOKEN` 发布。其二，运行一个 **eval 健康分卡点**——`python3 scripts/eval_run.py --score <已提交的 results.json> --fail-under <N>`——当 eval 健康分低于阈值时使 CI 失败（退出码 5）。内联 review 评论仅限 GitHub；GitLab/Codebase 模板只获得 eval 卡点。

纵深防御，从强到弱：

1. **Pre-commit hard block** — 防止本地改动在离开机器前就让 `AGENTS.md` 过期。`AI_HARNESS_DOCTOR_SKIP=1` 是显式、可审计的绕过，而不是静默放行。
2. **Path-aware PR gate** — 防止 hook 被绕过。重构必然会触及 `package.json`、`Makefile`、`AGENTS.md` 和工具 stubs 等被监控文件，因此 CI 会在 PR 上重新检查 drift。
3. **Weekly checkup + deduped issue** — 防止不触碰监控文件的慢性腐烂：新的 lint 工具、CI Node 升级，或在常规路径集合外发生的约定变更。
4. **Maintenance contract in `AGENTS.md`** — 从 agent 行为源头防守。重构常由 agents 完成，而每个 agent 都会读取 `AGENTS.md`；这份文档会指示自己如何被维护。

| 重构/变更 | 应该捕获它的检查 |
|---|---|
| 修改 scripts 或 `Makefile` targets | D1 command drift |
| 移动/删除已文档化路径 | D2 path drift |
| 把规则偷偷写回 `CLAUDE.md` 或 `.cursorrules` | D3 stub regrowth |
| 让 `AGENTS.md` 膨胀到超过有用上下文大小 | D4 size/context risk |
| 升级 Node 版本或切换包管理器却不更新 `AGENTS.md` | D6 fact drift |
| 删除 `AGENTS.md` 仍以 Markdown 链接指向的文档/配置文件 | D7 Markdown-link drift |
| 同时提交两种包管理器的 lockfile | D8 competing lockfiles |

为什么选择检测而不是再生成？静默“修复”drift 会拿走人的知情权。AI Harness Doctor 选择把 drift 暴露出来，因为重点不是重写文件，而是让团队注意到 repo truth 和 agent truth 已经分叉。见 [定位、非目标与对比](#定位非目标与对比)。

## 适配对象

| Surface | Support |
|---|---|
| Claude Code | 原生 skill，加 `.claude/commands` 或 `~/.claude/commands` 下的 slash commands。 |
| OpenAI Codex CLI | 面向 `~/.codex/prompts/` 的 prompt adapters。 |
| Cursor | 面向 `.cursor/commands/` 的 command adapters。 |
| Gemini CLI | 面向 `~/.gemini/commands/harness/` 的 TOML custom command adapters。Google 已于 2026-06-18 面向个人 tiers retired Gemini CLI；企业版 Gemini Code Assist 不受影响，这些 adapters 仍适用于企业/既有安装。 |
| Windsurf / Cline / others | 通用模式：让 agent 指向已安装的 playbook，并说 “run phase N”。 |
| MCP clients | `ai-harness-doctor mcp` 通过 stdio 将 `harness_scan`/`drift`/`validate`/`plan`/`stubs`/`eval_generate` 暴露为 MCP 工具。 |
| Humans & CI | 直接运行 `npx ai-harness-doctor ...`；不需要 agent。 |

诚实说明：非 Claude adapters 是薄指针，只做过轻量验证。如果某个命令格式变了，请提交 issue。

## 四个阶段

| 阶段 | 脚本 | 产物 | 停止条件 |
|---|---|---|---|
| 0 — 体检 / scan | `scripts/scan.py` | 面向人的或 JSON 健康报告 | 停在用户确认迁移范围时。 |
| 1 — 治疗 / canonicalize | `scripts/canonicalize.py --plan`, `--write-stubs`, `--validate` | 合并计划、canonical `AGENTS.md`、最小 stubs | 直到每个冲突都完成人工裁决才继续。 |
| 2 — 复诊 / drift guard | `scripts/check_drift.py` | Drift 报告和 CI/pre-commit 退出码 | 检查通过，或给出修复建议后停止。 |
| 3 — 疗效验证 | `scripts/eval_run.py` | Before/after JSON 和 Markdown 报告，外加 0–100 的 `health` 健康分（A–F 等级） | 产出指标后停止。 |

## 命令参考

<details>
<summary><code>install</code></summary>

安装 skill、slash commands 和/或 adapter prompts。

| Agent | 默认目标位置 | 使用 `--project` 时 |
|---|---|---|
| `claude` | `~/.claude/skills/ai-harness-doctor`, `~/.claude/commands/` | `.claude/skills/ai-harness-doctor`, `.claude/commands/` |
| `codex` | `~/.codex/prompts/` + shared payload | 同一 adapter 位置；project 影响 payload 路径。 |
| `cursor` | `.cursor/commands/` | 目标项目中的 `.cursor/commands/`。 |
| `gemini` | `~/.gemini/commands/harness/` + shared payload | 同一 command 位置；project 影响 payload 路径。 |

Adapters 会把 `{{PLAYBOOK}}` 替换为已安装 playbook 路径。安装会记录在 `~/.ai-harness-doctor/manifest.json`，具备幂等性，并可通过 `update` 刷新。`--link` 会指向全局 package，而不是复制 payload 文件；CLI 会阻止不安全的 `npx` cache linking，并提示你先全局安装。

</details>

<details>
<summary><code>uninstall</code></summary>

移除指定 `--agent` 已安装的 Claude skill 文件、slash commands、adapter prompts 和 shared payloads。`--agent all` 会移除所有已知 surface。它也会删除匹配的 manifest records。

</details>

<details>
<summary><code>update</code></summary>

把 manifest 追踪到的每个复制安装重新部署到当前 package 版本。链接安装会刷新 command pointers，而 payload 会跟随 `npm update -g ai-harness-doctor`。

</details>

<details>
<summary><code>guard</code></summary>

默认 dry-run；使用 `--apply` 写入。要求：目标是 git repo，且 `AGENTS.md` 已存在。

它管理一个与 provider 无关的核心，外加一个 **provider 感知的 CI 卡点**：

1. `.git/hooks/pre-commit` drift block。
2. 一个 CI drift/checkup 卡点，其文件取决于 `--provider`（见下文）。
3. `AGENTS.md` 中带 marker 的 maintenance contract。

`--provider github|gitlab|codebase|auto`（默认 `auto`）选择安装哪些 CI 文件。`auto` 会从 `.gitlab-ci.yml` 和 `origin` remote 探测 provider（github.com → `github`，主机名含 `gitlab` → `gitlab`，其他企业主机（如内部 Codebase）→ `codebase`，无 remote → `github`）：

| Provider | 安装的 CI 文件 | 接线说明 |
|---|---|---|
| `github` | `.github/workflows/harness-drift.yml` path-aware PR gate + `.github/workflows/harness-checkup.yml` weekly scan/drift checkup with a deduped issue。 | 在 GitHub Actions 上自动运行。 |
| `gitlab` | 一个可 include 的 `.gitlab/harness-ci.yml`（`harness-drift` 跑在 MR 上，`harness-checkup` 跑在 schedule 上并产出 artifact）。 | 在 `.gitlab-ci.yml` 中加入 `include: { local: .gitlab/harness-ci.yml }`。 |
| `codebase` | 一个可移植的 `.harness-ci/harness-guard.sh`（`drift`/`checkup` 模式）+ 一个接线用的 `README.md`。 | 将该脚本注册为 MR 检查和定时 pipeline 步骤。 |

`AI_HARNESS_DOCTOR_SKIP=1` 是本地 hook 显式且可审计的逃生口。`guard --remove --apply` 会移除托管片段、清理**所有 provider** 的 CI 文件（这样切换 provider 不会残留任何东西），并在可能时按字节精确恢复此前已存在的 hook 内容。安装与移除都是非破坏性的：每个托管文件都带有 `ai-harness-doctor:guard` 标记，因此 `guard --apply` 绝不会覆盖缺少该标记的用户自改 CI 文件（会报告 `manual-merge` 并保持你的文件不动）；而 `--remove` 仅在托管文件与工具原始产物逐字节一致时才删除——对于被手工扩展的 hook，只会剥离它自己的 guard 块，若该块已被修改则跳过而非销毁。

**Self-bootstrap：** 本仓库运行自己的 guard。`.github/workflows/harness-drift.yml` 与 `.github/workflows/harness-checkup.yml` 由 `assets/guard/` 模板改写而来，运行本仓库的**本地** CLI（`node bin/cli.js drift . --strict`）而非发布版 `npx -y ai-harness-doctor`，因此对 `scripts/` 的任何改动都会被正在改动的代码本身所守护。eval 卡点保持“软性”（仅在已提交结果 JSON 时才生效），PR review 步骤也容忍缺失/受限的 token，因此该 guard 绝不会把本仓库自己的 CI 变红。

</details>

<details>
<summary><code>scan</code></summary>

检测五类问题：配置清单、体积/截断风险、重叠候选、带 file:line 证据的冲突候选，以及 nested `AGENTS.md` 文件。在此之上，它还回答一个互补的问题——*缺了什么*——通过缺口分析给出（见下文）。

它还会盘点**扩展的 harness surface**——MCP 服务器、subagents、slash 命令、hooks 和权限规则——并运行一次**安全体检**，标记按严重程度排序的发现（HIGH/MEDIUM）：

- 明文密钥（AWS / GitHub / OpenAI / Google / Slack / Anthropic 密钥、私钥块、通用的 `api_key/secret/token=...`），覆盖指令类和 MCP/settings 配置文件。
- 过于宽泛的权限，例如 `Bash(*)`、`*` 和 `defaultMode: bypassPermissions`。
- MCP 卫生问题：不安全的 `http://` 传输以及形似凭据的 env 字面量。
- 有风险的 hook/命令体：`curl … | bash`、`rm -rf`、`--dangerously-skip-permissions` 等。

默认以 0 退出。加上 `--fail-on-security` 后，只要存在任意 HIGH 级发现就以 `2` 退出，很适合作为 CI 卡点。

它还会运行一次**缺口分析（gap analysis）**，把仓库与一份 harness 完整性清单做 diff，报告仓库*缺失*的基建（而不仅仅是已有的）。这些静态检查只覆盖任何健康 harness 都必须具备、与技术栈无关的部分：canonical 的根 `AGENTS.md`（`G1`）、`AGENTS.md` 必备章节（与 `assets/AGENTS.template.md` 保持同步，`G2`）、应当是指向 `AGENTS.md` 的最小 pointer 的 tool stub（`G3`）、以及 drift-guard / 周度 checkup 的 CI workflow（`G4`）。它还落地执行了 `SKILL.md` 中此前没有代码支撑的两个[命名反模式](SKILL.md#named-anti-patterns)：**Wholesale Dumping**（`G9`）——`AGENTS.md` 与 `README.md` 的标准化行重叠超过一半，说明内容是整段照抄过来的，而不是提炼成 agent 专属、无法从代码推断的规则；以及 **Silent Adjudication**（`G10`）——`AGENTS.md` 在一个仍然存在的信号冲突（例如 `pnpm` 对 `npm`）里默默选了一边，却没有留下任何把另一边交给仓库负责人裁决的痕迹。每条缺口带有 `level`（`ERROR`/`WARN`/`NOTICE`）、`item`、`message` 和可执行的 `suggestion`。加上 `--fail-on-gaps` 后，只要存在任意 ERROR 级缺口（例如缺少根 `AGENTS.md`）就以 `3` 退出。

对于所有依赖具体技术栈（而非普遍必备）的部分，scan 会输出一份**项目快照（project snapshot）**——一份紧凑、事实性的仓库描述，供 agent/LLM 推断：

- `tech_stack`：从 manifest 探测出的语言/生态（`go.mod`、`package.json`、`pyproject.toml`、`requirements.txt`、`Cargo.toml`、`pom.xml`、`Gemfile`、`composer.json` 等）。
- `existing_files`：已存在的 CI、git hook、lint/format、typecheck 配置文件，以及是否安装了 drift-guard 的 pre-commit hook。
- `agents_sections`：`AGENTS.md` 当前的 H1 章节。
- `maintenance_contract`：`AGENTS.md` 是否内嵌了维护契约。
- `mcp_tools` / `has_permissions`：已配置的 MCP server，以及是否存在权限规则。

过去作为静态 `G5`–`G8` 缺口的、依赖技术栈的判断（pre-commit guard、维护契约、MCP 配置、权限配置）现在都成为该快照中的事实，交给 agent 自行推断。

它还会运行一次**语义一致性（semantic consistency）**检查，把 `AGENTS.md` 中*声明*的内容与代码*事实*做比对，让过时的说明在体检阶段就暴露出来（而不是等到 Phase 2 的 drift 门禁）。它是**多生态**的——除 Node/npm 外，还理解 Python（`pyproject.toml` / `setup.py` / `requirements.txt`，涵盖 pip/poetry/uv/pdm/pipenv）、Go（`go.mod`）、Rust（`Cargo.toml`）、Java（`pom.xml` / `build.gradle`）与 Ruby（`Gemfile` / `.ruby-version`，涵盖 bundler）。它会交叉核对：构建/测试命令（`npm run <script>` / `make <target>`，以及 `cargo run --bin <name>`、`go run ./<pkg>`、`poetry run <script>`）与 `package.json` scripts、`Makefile` targets、Cargo 二进制目标、Go 包路径、pyproject 控制台脚本；反引号包裹的仓库相对路径与文件系统；声明的包管理器与各生态已提交的 lockfile/清单（包括通过 `Gemfile.lock` 核对 bundler）；声明的语言/运行时版本与各生态的锁定（`.nvmrc` / `engines.node`、`requires-python` / `.python-version`、`go.mod` 的 `go` 指令、`Cargo.toml` 的 `rust-version`、Java 编译级别，以及 `.ruby-version` / `Gemfile` 的 `ruby` 指令）。每条发现带有 `category`（`command`/`path`/`package_manager`/`node_version`/`python_version`/`go_version`/`rust_version`/`java_version`/`ruby_version`）、`level`（`MISMATCH`/`MISSING`）、`declared`（声明值）、`actual`（真实事实）、可选的 `line` 和 `suggestion`。加上 `--fail-on-semantic` 后，只要有任何声明与代码矛盾就以 `4` 退出。

**给 agent 用的完整 JSON 报告。** 在 markdown 模式下，`scan` 会把完整的机器可读报告（files、surface、security、`project_snapshot`、`semantic`、`gaps`）写入一个稳定的临时文件——`${TMPDIR}/harness-scan-<hash>.json`，其中 `<hash>` 由解析后的仓库路径派生——并在末尾追加一节 `## Full JSON report` 指向它。驱动工作流的 agent 可以读取该文件，基于快照和缺口做推断与修复规划，而无需再解析 markdown。`--json` 模式已经把完整报告打印到 stdout，因此不会写临时文件。用 `--no-report-file` 可跳过写入。

**Monorepo / 多包感知。** `scan` 支持 monorepo。当它检测到工作区（`package.json` 中的 npm/yarn/pnpm `workspaces`、`pnpm-workspace.yaml`，或在 `--monorepo` 下的多个嵌套 `package.json` / `AGENTS.md` 子树）时，会额外扫描每个检测到的包子目录，并报告每个包的结果以及一个顶层聚合。markdown 报告会新增一节 `## Monorepo`（每个包一行的表格加一行聚合），`--json` 会新增顶层 `packages` 数组（每个包一条，`report` 下是相同结构的扫描结果，另有 `summary`）和一个 `monorepo` 对象（`source`、`package_count`、`aggregate`）。未检测到工作区时单仓行为保持不变；用 `--no-monorepo` 强制只扫描根目录，用 `--monorepo` 强制检测。

**自定义规则插件。** `scan`（以及 `drift`）可以用你自己的确定性规则来扩展。把 Python 模块放到目标仓库的 `.ai-harness-doctor/rules/*.py` 目录，和/或传入 `--rules DIR`（可重复）。每个模块暴露一个 `def check(root, context) -> list[dict]:`，返回发现项（`level`、`message`，可选的 `path`/`line`/`suggestion`，以及一个 `rule` id）；`context` 携带本次运行的 `phase` 和 `AGENTS.md` 文本。这些发现会被合并进 `custom` 一节（markdown 的 `## Custom rule plugins` 和 `--json` 的 `custom` 数组）。插件是可选加入的——没有规则目录也没有 `--rules` 时，行为保持不变。导入失败或运行时抛异常的插件会被隔离，并作为一个 `level: "ERROR"` 发现项报告，而不会让扫描崩溃；模板见 `references/example-rule-plugin.py`。

**多仓库批量模式。** `scan --repos-file PATH` 会扫描 `PATH` 中列出的每个仓库（每行一个路径；空行和 `#` 注释会被忽略），而不是单个 `repo_root`，并打印一份组织级别的健康摘要——面向"多工具混用团队"和"OSS 维护者"这两类人设，他们此前除了对每个仓库手动跑一遍之外没有别的方案。每个仓库都在自己的根目录独立扫描（该模式不会在单个仓库内部展开 monorepo 的包）；一个解析不到目录的路径会被列在"无法扫描的仓库"下，而不会中断整个批次。`--json` 返回 `{ summary: { repo_count, error_count, aggregate }, repos: [{ path, resolved, name, has_agents_md, summary, report } | { path, resolved, error }] }`。`--fail-on-security` / `--fail-on-gaps` / `--fail-on-semantic` 会综合考虑每个被扫描的仓库，因此这个模式可以作为整个组织范围的 CI 门禁。与 `repo_root` 位置参数互斥。

**GitHub 原生发现（SARIF）。** `scan` 和 `drift` 都支持 `--sarif`，将 SARIF 2.1.0 文档输出到 stdout，使发现出现在 GitHub 的 Security 页签以及 PR 内联注释中。`--sarif` 优先于 `--json`/markdown，并基于完整报告（根 + 每个 monorepo 包）生成，不受任何 `--no-*` 抑制影响。源级别映射到 SARIF 级别（`HIGH`/`ERROR`→`error`，`MEDIUM`/`WARN`/`NOTICE`→`warning`，其余→`note`）。

```bash
# Emit SARIF 2.1.0 to a file for GitHub code scanning
npx ai-harness-doctor scan . --sarif > ai-harness-doctor.sarif
npx ai-harness-doctor drift . --sarif > drift.sarif
```

仓库根目录附带一个可复用的组合式 GitHub Action（`action.yml`），任何仓库都可以用两步运行该工具并上传 SARIF：

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

| Flag | 用途 |
|---|---|
| `--no-security` | 只做清单；跳过安全体检（不输出 `security` key）。 |
| `--fail-on-security` | 存在任意 HIGH 级安全发现时以 `2` 退出。 |
| `--no-gaps` | 跳过缺口分析（不输出 `gaps` key）。 |
| `--fail-on-gaps` | 存在任意 ERROR 级 harness 缺口时以 `3` 退出。 |
| `--no-semantic` | 跳过语义一致性检查（不输出 `semantic` key）。 |
| `--fail-on-semantic` | 存在任意 AGENTS.md 声明与代码矛盾时以 `4` 退出。 |
| `--no-snapshot` | 跳过项目快照（不输出 `project_snapshot` key）。 |
| `--no-report-file` | 不把完整 JSON 报告写入临时文件（仅 markdown 模式）。 |
| `--monorepo` | 强制 monorepo 模式：即使没有工作区配置也扫描每个包子目录（回退到嵌套的 `package.json` / `AGENTS.md` 子树）。 |
| `--no-monorepo` | 关闭 monorepo 检测；只扫描仓库根目录。 |
| `--repos-file PATH` | 扫描 `PATH` 中列出的每个仓库，打印跨仓库摘要而非单仓库结果（见上文）。与 `repo_root` 互斥。 |
| `--rules DIR` | 从 `DIR` 加载自定义规则插件（可重复）；与 `.ai-harness-doctor/rules/` 一起合并进 `custom` 一节。 |
| `--no-custom` | 跳过自定义规则插件（不输出 `custom` key）。 |
| `--sarif` | 将 SARIF 2.1.0 JSON 输出到 stdout 供 GitHub code scanning 使用（优先于 `--json`）。 |

`--json` returns（已有的 key 保持不变——向后兼容）:

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

`security` 发现带有 `level`（`HIGH`/`MEDIUM`）、`category`（`secret`/`mcp`/`permission`/`hook`/`instruction`）、`path` 以及人类可读的 `message`。使用 `--no-security` 时会省略 `security` key。`gaps` 条目带有 `check`（`G1`–`G4`）、`level`（`ERROR`/`WARN`/`NOTICE`）、`item`、`message` 和 `suggestion`；使用 `--no-gaps` 时会省略 `gaps` key。`semantic` 带有 `checked`（已核对的声明数）、`mismatches` 和 `findings`（每条含 `category`、`level`、可选 `line`、`declared`、`actual`、`message`、`suggestion`）；使用 `--no-semantic` 时会省略 `semantic` key。使用 `--no-snapshot` 时会省略 `project_snapshot`。`custom` 保存来自用户规则插件的发现（每条含 `level`、`message`、`plugin`、`rule`，以及可选的 `path`/`line`/`suggestion`）；使用 `--no-custom` 时会省略 `custom` key。在 markdown 模式下，同样的 JSON 对象还会写入 `${TMPDIR}/harness-scan-<hash>.json`（除非指定 `--no-report-file`）。在 monorepo 模式下，报告还会新增顶层 `packages` 数组和一个 `monorepo` 概要。

</details>

<details>
<summary><code>plan</code></summary>

从 scan 输出搭建 Phase 1 合并计划：清单、重叠 clusters、冲突列表，以及 TODO 决策清单。它明确**不会**合并内容或替你选边。

它还会基于 scan 追加一个 **“Merge suggestions (semi-automatic)”** 章节：

- **Overlap consolidation** —— 每个重叠 cluster 会指明 canonical 文件（`AGENTS.md`），并以复选框列表列出要降级为 stub 的文件。
- **Conflict resolutions** —— 每个冲突信号给出一个推荐值，并附上其支撑性的 `path:line` 证据（作为可勾选项），以及一句简短的**理由**。推荐是确定性且基于事实的：`package_manager` 优先选择由已提交 lockfile 支撑的包管理器，`node_version` 优先选择 `.nvmrc` / `engines.node` 固定的版本，其余情况回退到得到最多支撑的值（平票时按字典序决定）。

这些是供人工审阅的建议，而非自动裁决；既有的 inventory/overlap/conflict/TODO 章节都会保留。

</details>

<details>
<summary><code>draft</code></summary>

自动起草一份填充了具体、基于事实内容的**初始 `AGENTS.md`**，而不是空骨架。调用方式为 `npx ai-harness-doctor draft <repo> [-o AGENTS.md]`（或直接调用 `python3 scripts/canonicalize.py <repo> --draft [-o AGENTS.md]`）；它是对 scan 的只读透传，绝不修改被扫描的仓库。

草稿会复用 `scan.py` / `semantic.py` 的确定性仓库事实，填充每个 canonical 章节（`Project overview`、`Build & test`、`Conventions`、`Testing requirements`、`Safety`、`Commit & PR`）：

- 检测到的技术栈（来自 `package.json`、`pyproject.toml` 等清单文件）；
- 从 `package.json` `scripts` 和 `Makefile` targets 推导的构建/测试命令，并使用由已提交 lockfile 支撑的包管理器；
- 检测到的 CI、lint/format 与类型检查工具；
- 为 scan 报告的**每个冲突**给出默认解决方案（例如优先选择 lockfile 支撑的包管理器），并附上理由。

每条推断行都标记 `(inferred — confirm)`，安全默认约定标记 `(suggested default)`，顶部横幅提醒人工在提交前审阅并修改。不带 `-o` 时打印到 stdout；带 `-o PATH` 时写入文件，且在文件已存在时拒绝覆盖，除非提供 `--force`。

</details>

<details>
<summary><code>validate</code></summary>

在你写好 canonical `AGENTS.md` 后验证其结构。它是对 `scripts/canonicalize.py --validate` 的只读透传。

默认要求包含 `Project overview`、`Build & test` 和 `Conventions` 三个标题。传入 `--require-sections` 及你自己的逗号分隔列表，即可更改哪些标题为必需（缺失的标题会报告为 `SECTION` 发现项）：

```bash
python3 scripts/canonicalize.py --validate . --require-sections "Project overview,Build & test,Security"
```

</details>

<details>
<summary><code>stubs</code></summary>

在 `AGENTS.md` 存在后，把既有工具文件降级为最小指针。

| Tool | Downgrade strategy |
|---|---|
| Claude | `CLAUDE.md` / `.claude/CLAUDE.md` import `@AGENTS.md`. |
| Cursor | `.cursorrules` points to `AGENTS.md`; `.cursor/rules` becomes one always-apply pointer. |
| Windsurf | `.windsurfrules` becomes a pointer. |
| Copilot | `.github/copilot-instructions.md` becomes a pointer. |
| Gemini | `GEMINI.md` becomes a pointer and recommends `contextFileName`. |
| Cline | `.clinerules` becomes a pointer. |
| Roo | 由 `scan` 识别（`.roo/rules/*.md`），但**不会**被降级——它是 rules-directory 类工具，没有单一的常规 stub 位置，因此保持为仅扫描（scan-only）。 |
| Continue | `.continuerules` 指向 `AGENTS.md`；`.continue/rules/*.md` 由 `scan` 识别但不会被降级。 |
| Trae | 由 `scan` 识别（`.trae/rules/project_rules.md`），但**不会**被降级——与 Roo 同样的情况，没有单一的常规 stub 位置。 |

默认 dry-run。`--apply` 要求 git tree 干净；`--force` 会覆盖该安全检查。

已知的工具 config 文件在 `assets/agent-tools.json` 中统一定义，这是 `scan`、`stubs`/`canonicalize` 和 `drift` 共同读取的唯一 registry，因此新增一个工具只需修改这一个文件。

本着同样的精神，`adapters/` 下按命令划分的 Codex/Cursor/Gemini 适配器由单一来源生成：`scripts/gen_adapters.py` 从一张命令表渲染出全部 15 个文件（5 个命令 × 3 种风格），`python3 scripts/gen_adapters.py --check`（亦即 `npm run lint:adapters`）会在任一已提交的适配器与该来源发生漂移时让 CI 失败，`npm run gen:adapters` 则用于重新生成它们。

</details>

<details>
<summary><code>drift</code></summary>

检查 `AGENTS.md` 是否符合 repo reality。没有发现 blocking drift 时退出码为 0；发现 errors 时为 1。`--strict` 会把 notices 提升为 errors。

Example finding lines:

- D1: `Unknown package.json script test:unit-old`
- D2: `Referenced path src/old-components does not exist`
- D3: `Tool stub CLAUDE.md regrew or lost AGENTS.md pointer`
- D4: `AGENTS.md is 41000 bytes, above 32768`
- D5: `Nested AGENTS.md inventory` (informational, non-blocking)
- D6: `AGENTS.md declares Node 18 but .nvmrc pins 20` (fact drift)
- D7: `Markdown link target references/runbook.md does not exist` (Markdown-link drift)
- D8: `Competing package-manager lockfiles committed (package-lock.json, pnpm-lock.yaml)`

**D6 fact drift** 会把 `AGENTS.md` 中声明的*事实*与 repo 实际情况交叉验证：Node 版本（对比 `.nvmrc` 和 `package.json` 的 `engines.node`）以及包管理器（对比实际的 lockfile——`package-lock.json`→npm、`pnpm-lock.yaml`→pnpm、`yarn.lock`→yarn）。它只标记明确的矛盾，当 `AGENTS.md` 未声明时保持沉默，因此沉默永远不会产生误报。

**D7 Markdown-link drift** 会探测 `AGENTS.md` 中 repo 相对的 Markdown 链接目标（`[text](path)`），并标记那些指向已不存在的文件或目录的链接。它补充了 D2（D2 只检查反引号包裹的 token）；URL、页内锚点以及 repo 之外的目标都会被忽略，因此它永远不会探测 repo 之外的路径。

**D8 competing lockfiles** 会标记同时提交了多个包管理器 lockfile 的 repo（例如同时存在 `package-lock.json` 和 `pnpm-lock.yaml`），因为此时无法确定预期使用哪个包管理器。它会被列为需要人工处理——工具永远不会擅自猜测该删除哪个 lockfile。

**Health score。** 所有发现（D1..D8）汇总为一个 0–100 的健康分，并带字母等级（A ≥90 / B ≥80 / C ≥70 / D ≥60 / F），以 `## Health score` 章节呈现（如 `Score: 85/100 (grade B)`）。加上 `--json` 后，报告会在既有字段之外新增 `score` 和 `grade` key。

`--min-score N` 在分数低于 `N` 时以非零退出——这是一个独立于 `--strict` 的 CI 卡点，两者可同时生效。

**半自动修复：`--fix`。** `--fix` 只自动修复 drift 中安全、机械化的那一部分——目前是 **D3 stub regrowth**。任何长出真实内容或丢失 `AGENTS.md` 指针的工具 stub，都会被重写回其最小的 canonical import-stub 形式（stub 主体复用自 `canonicalize.py`，因此 `--fix` 与 `stubs`/`--write-stubs` 保持同步）。

```bash
npx ai-harness-doctor drift . --fix          # DRY RUN: prints the diff, writes nothing
npx ai-harness-doctor drift . --fix --apply  # actually rewrites the regrown stubs
```

- 默认 `--fix` 是 dry run：它打印将被重写内容的 unified diff，不改动任何文件。
- `--fix --apply` 会就地重写重新长出的 stub 文件。
- 不安全的 drift（D1 命令 drift、D2 path drift、D4 size、D7 Markdown-link drift、D8 competing lockfiles，以及任何其他语义 drift）永远不会被修改；它们会列在 **“needs manual attention”** 下，并附上可复制粘贴的修复指引。
- 一行汇总会报告 `N fixed/fixable, M need manual attention`。只要还有 drift 残留，命令就以非零退出。

</details>

<details>
<summary><code>eval</code></summary>

运行或对比 before/after agent tasks。

**零配置任务。** 你不必手写 `tasks.json` —— `--generate REPO` 会从仓库事实（`package.json` 的 scripts/engines/deps、锁文件、`.nvmrc`、`go.mod`、`pyproject.toml`，以及 `AGENTS.md` 约定）推导出一套确定性任务，每条 check 用 regex 编码真实事实，因此更高的分数直接反映 `AGENTS.md` 是否起到了作用：

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

Checks 可以是对提取答案执行的 `regex`、在 workdir 中执行的 `command`，也可以是用于开放式 LLM-as-judge 评分的 `judge`。对于 Claude CLI JSON 输出，评分会先提取 `result` 字段再匹配。Usage/cost 字段存在时会被捕获。`--compare before.json after.json` 会写出 Markdown 对比。`--regrade results.json --tasks tasks.json` 会离线重新评分已记录输出。如果 runner binary 缺失，命令会打印手动协议 fallback，而不是假装已经运行。

**Multi-agent matrix。** 在多个 runner（“agents”）上运行同一套任务集并并排对比。可用可重复的 `--runner-cmd NAME=CMD` 内联提供 runner，或通过 `--matrix agents.json`（agent 名称 → runner 命令模板的映射）。`--matrix-report FILE` 写出一个 Markdown 矩阵（行 = 任务，列 = agents，单元格 = pass/fail + 时长，外加每个 agent 的通过率汇总），`--matrix-json FILE` 写出每个 agent 的任务记录并带一个 `summary` 块（`passed`、`total`、`pass_rate`）。单 runner 的 before/after/compare 流程保持不变；只有在提供了 `--matrix` 和/或 `--runner-cmd` 时才会激活矩阵模式。

```bash
npx ai-harness-doctor eval --tasks tasks.json --workdir . \
  --runner-cmd "claude=claude -p {prompt} --output-format json" \
  --runner-cmd "codex=codex exec {prompt}" \
  --matrix-report matrix-report.md --matrix-json matrix-results.json
```

**LLM-as-judge check。** 一个任务 check 可以使用 `{ "type": "judge", "rubric": "..." }` 来完成 regex 无法表达的评分。当提供 `--judge-cmd "CMD_TEMPLATE"` 时它优先生效：judge 会收到环境变量 `JUDGE_ANSWER`、`JUDGE_RUBRIC` 和 `JUDGE_INPUT`（一个临时 JSON `{answer, rubric}` 的路径），且模板占位符 `{answer}`/`{rubric}`/`{input}` 会被替换。它必须打印 `{"passed": bool, "score": number, "reason": "..."}`；若省略 `passed`，则 `score >= 0.5` 记为通过。一个离线的确定性 judge 适用于 CI。

**真实 LLM 与内置 judge。** 当未提供 `--judge-cmd` 时，`judge` check 可通过 `--judge-llm {auto,openai,claude,off}`（默认 `off` —— 确定性的内置关键词 judge，环境中存在的 API key 绝不会静默地把评分改由真实模型完成；需用 `auto` 显式开启）由真实 LLM 评分：`auto` 在设置了 `OPENAI_API_KEY` 时调用 OpenAI，否则在设置了 `ANTHROPIC_API_KEY` 时调用 Claude，仅使用 Python 标准库（无需 SDK）。可通过 `OPENAI_MODEL`/`OPENAI_BASE_URL`、`ANTHROPIC_MODEL`/`ANTHROPIC_BASE_URL` 或 `--judge-model` 配置模型/端点。任何失败（无 key、网络错误、返回格式错误）都会透明回退到确定性、无依赖的内置关键词 judge（结论为 `{passed, score, reason, judge:"builtin"}`；LLM 结论会被标记为 `judge:"llm:openai"`/`"llm:claude"`）。关键词 judge 按优先级评分：`check.expect` —— 必须全部匹配（不区分大小写）的 regex；`check.reject` —— 必须不匹配的 regex；否则基于自由文本 `check.rubric` / `check.criteria` 的关键词覆盖率，`>= check.min_score`（默认 `0.5`）时通过。传入 `--judge-llm off` 只用关键词评分，或 `--no-default-judge` 强制要求外部 `--judge-cmd`。

```bash
npx ai-harness-doctor eval --tasks tasks.json --workdir . --label after --judge-llm auto   # real LLM judge, keyword fallback
```

**健康分（Health score）。** 每次 eval 还会计算一个一键式疗效健康分 = 所有任务记录的通过率，以 `0–100` 表示并带 A–F 字母等级（A ≥90 / B ≥80 / C ≥70 / D ≥60 / F）。它以 `health` key 嵌入单次运行结果（`{"tasks":...}`）和矩阵结果（`{"agents":...}`），并打印为一行摘要（`health score: N/100 (grade X), P/T tasks passed`）。超时计为失败。`--score PATH` 会打印某个已有 results/matrix JSON 的健康分（加 `--json` 输出机器可读格式），`--fail-under N` 会在健康分低于 `N` 时以退出码 `5` 退出（作为 CI 门禁）。

**多轮稳定性（`--rounds`）。** `--rounds N`（N > 1）会将整个任务集运行 N 次并汇总稳定性统计，用于暴露那些有时通过、有时失败的 *flaky*（不稳定）任务。此时结果 JSON 会带上 `rounds`、`round_results`（每一轮的完整任务记录及该轮的 `health`）、一个 per-task 的 `task_stats` 数组（`runs`、`passed`、`failed`、`timed_out`、`pass_rate`、`flaky`），以及一个 `stats` 摘要（`mean_health`、`variance`、`stddev`、`min_health`、`max_health`、`health_scores`、`flaky_tasks`、`flaky_count`）。当某任务既非每轮都通过、也非每轮都失败时即为 `flaky`。总体 `health` 为所有 task-run 的通过率，`--fail-under N` 以其为门禁。`--rounds 1`（默认）会逐字节保持旧的单轮输出结构不变。`--stats PATH` 可离线重新汇总一个已有的多轮结果文件（加 `--json` 输出机器可读格式，`--fail-under N` 作为门禁）。

```bash
npx ai-harness-doctor eval --tasks tasks.json --workdir . --label nightly --rounds 5   # run 5x, aggregate stability stats
npx ai-harness-doctor eval --stats results-nightly.json --json                         # re-analyze an existing multi-round file
```

**基线、趋势与回归。** 将每次运行的健康分作为只追加的基线历史落库（`--baseline FILE` + `--save-baseline`），记录时间戳、label、分数/等级、通过计数，以及目标仓库的 git commit/branch。`--check-regression` 会把当前分数与最近一次历史快照对比，当下降至少 `--regression-threshold` 分（默认 `5`）时以退出码 `6` 退出；`--trend FILE` 会把历史渲染为带逐快照增量和回归标记的 Markdown 表格。它可与任意运行模式以及 `--score` 组合使用。

```bash
npx ai-harness-doctor eval --tasks tasks.json --workdir . --label after -o results.json \
  --baseline baselines/history.json --save-baseline --check-regression   # save + gate on regressions
npx ai-harness-doctor eval --trend baselines/history.json                  # render the recorded trend
```

</details>

<details>
<summary><code>mcp</code></summary>

启动一个 MCP（Model Context Protocol）stdio 服务器，让 agents 可以把 doctor 的只读能力当作工具来调用。

```bash
npx ai-harness-doctor mcp   # or directly: node bin/mcp-server.js
```

Transport 是基于换行分隔 JSON 的 JSON-RPC 2.0（stdin/stdout 上每行一个 JSON 对象）。支持的方法：

- `initialize` → `{ protocolVersion, capabilities: { tools: {} }, serverInfo: { name, version } }`。
- `notifications/initialized` → 通知，无响应。
- `tools/list` → 公布 `harness_scan`、`harness_drift`、`harness_validate`、`harness_plan`、`harness_stubs`、`harness_eval_generate`，各自带一个输入 schema `{ repo: string (default "."), ... }`。
- `tools/call` → 分派到匹配的 Python 脚本并返回 `{ content: [{ type: "text", text }] }`。

工具布尔值：`harness_scan`（`json`）、`harness_drift`（`json`、`strict`）、`harness_validate`（`json`）、`harness_plan`、`harness_stubs`、`harness_eval_generate`。`harness_stubs`（Phase 1 的 stub 降级预览）与 `harness_eval_generate`（Phase 3 的任务集引导生成）在 MCP 上始终是只读的：两者都不会收到 `--apply`/`-o`，因此只能预览 diff 或打印生成的 JSON，绝不会写入被扫描的仓库。未知的方法和工具会返回一个 JSON-RPC error 对象。

</details>

<details>
<summary><code>doctor</code></summary>

针对 Node + Python 双运行时的单入口运行时自检。它通过与各 Python 子命令相同的共享解析器解析 Python 解释器，然后报告 Node、解析到的 Python 3 解释器、每个 Python 引擎以及 MCP server 文件。任意一项检查失败时以非零码退出。

```bash
npx ai-harness-doctor doctor --self-test   # human-readable runtime table
npx ai-harness-doctor doctor --json        # machine-readable runtime report
```

Python 按优先级顺序发现：`AI_HARNESS_DOCTOR_PYTHON`、然后 `PYTHON`、然后 `python3`、然后 `python`；仅接受 Python **3** 解释器。当它缺失时，每个 Python 子命令（`scan`、`plan`、`validate`、`stubs`、`drift`、`eval`）都会以同一条清晰、可操作的信息失败——安装 Python 3 或设置 `AI_HARNESS_DOCTOR_PYTHON`——而不是抛出原始堆栈。

</details>

Slash command quick refs: `/harness-doctor` full pipeline; `/harness-scan` Phase 0; `/harness-treat` Phase 1; `/harness-drift` Phase 2; `/harness-eval` Phase 3.

环境变量：

| 变量 | 用途 |
|---|---|
| `AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1` | 关闭每天一次的 npm 更新提示。 |
| `AI_HARNESS_DOCTOR_SKIP=1` | 显式绕过本地 pre-commit drift hook。 |
| `AI_HARNESS_DOCTOR_PYTHON` | 指定每个 Python 子命令使用的 Python 3 解释器。 |

`AI_HARNESS_DOCTOR_FORCE_UPDATE_CHECK` 和 `AI_HARNESS_DOCTOR_REGISTRY` 是内部/测试开关。

## Benchmark

来自 [`benchmark/results/`](benchmark/results/) 的最终验证结果：

| Side | Runs | Passed | Flip-flop tasks | Avg latency/task | Total captured cost |
|---|---|---:|---:|---:|---:|
| BEFORE: conflicting/stale configs | 14 objective tasks × 2 runs | 6/28 (21%) | 2 | 16.0s | $5.82 |
| AFTER: canonical `AGENTS.md` via this tool | 14 objective tasks × 2 runs | 28/28 (100%) | 0 | 11.7s | $4.81 |
| Delta | after - before | +22 correct attempts | -2 | -27% | -17% |

冲突配置不只是会造成错误答案；还会造成**不稳定**答案：canonicalization 之前，同一个问题在 `node` 和 `moduletype` 上会在两次运行间摇摆；之后再没有摇摆。

方法、任务、评分和复现命令见 [`benchmark/README.md`](benchmark/README.md)。诚实范围：一个 demo repo，每侧 N=2 次运行，客观 Q&A tasks，runner 为 `claude -p`，Claude CLI 2.1.202。

## 定位、非目标与对比

### 定位

AI Harness Doctor 与 Claude Code 官方 `/init` 互补：`/init` 从零启动配置，而 AI Harness Doctor 诊断、收敛、守护并验证已经散落的既有配置。它的 `SKILL.md` 明确不进入 `/init` 的职责范围。

Regeneration 和 guarding 是两种有效哲学。Ruler/rulesync 让生成输出可丢弃；AI Harness Doctor 让 `AGENTS.md` 归人所有，并守护它不发生 drift。这就是它选择检测而不是静默再生成的原因：当 repo 改变时，团队也应该知道 agent contract 改变了。

### 非目标

- 不做从零 init；那是 `/init` 的职责范围。
- 永远不静默裁决冲突；它会展示 file:line 证据并询问人。
- Scripts 永远不做语义合并。
- 不做无人值守写入：默认 dry-run、`--apply` 和 clean-tree checks 都是有意设计。
- 不生成语言/框架 style-guide。
- 不是批量 rules distributor；如需 20+ 工具扇出，请使用 rulesync，并参见下方对比。
- 无 telemetry。唯一的网络调用是每天一次的 npm version check，且可关闭。

### 对比

图例：✅ 内置 / △ 部分支持或方法不同 / ❌ 公开文档未声明该特性。

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

截至 2026-07，以上基于各项目公开文档——最新情况请查看各自仓库。

## Releases

- Releases 通过 CI 按 tag 驱动，并带 npm provenance。
- 见 [`RELEASING.md`](RELEASING.md)。
- 每个发布版本都有 git tag。

## 仓库结构

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

- Repo harness-ification：把项目脚本 CLI 化，添加验证 gates，并清晰分层文档。
- 更丰富的 eval task packs，覆盖更多语言、仓库形态和多轮工作流。
- 随着命令格式稳定，增加更多 agent adapters。
- 等 Antigravity CLI 的 custom-command format 文档化后，添加 Antigravity CLI adapter。

## 贡献

欢迎提交 bug reports 和聚焦的 PR。请保持 scripts 确定性、仅依赖 stdlib，并通过：

```bash
python3 -m unittest discover -s tests -v
```

仓库还提供一套基于 npm 的 lint/format/test 工作流（仅用于开发，不会打包进发布产物）。CI 会在 Python（3.9/3.10/3.12）与 Node（16/20/22）版本矩阵上运行完整套件：

```bash
npm test            # Python unittest + node --test CLI suite
npm run lint        # eslint (bin) + ruff (scripts/tests) + trilingual README structure sync
npm run format      # prettier --write .   (npm run format:py for ruff format)
```

`npm run lint:docs`（即 `scripts/check_readme_sync.py`）会强制 `README.md`、`README.zh-CN.md`、`README.ja.md` 保持完全一致的标题骨架，因此对任一 README 的结构改动都必须同步到另外两个。

## License

MIT. Copyright (c) NieZhuZhu.
