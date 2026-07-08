[English](README.md) | **简体中文** | [日本語](README.ja.md)

# 🩺 AI Harness Doctor

给仓库的 AI harness 做医生：把散落的 agent 配置体检、合并、守护并评估，收敛到唯一 canonical `AGENTS.md`。

[![CI](https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml/badge.svg)](https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml)
[![npm version](https://img.shields.io/npm/v/ai-harness-doctor.svg)](https://www.npmjs.com/package/ai-harness-doctor)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![Node >=16](https://img.shields.io/badge/Node-%3E%3D16-green.svg)

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

安装 Claude Code skill，并在目标仓库里运行医生：

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
| `scan` | ✅ | ❌ | 默认以 0 退出；做清单、证据收集和一次安全体检。`--fail-on-security` 在出现 HIGH 级发现时以 2 退出。 |
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

为什么选择检测而不是再生成？静默“修复”drift 会拿走人的知情权。AI Harness Doctor 选择把 drift 暴露出来，因为重点不是重写文件，而是让团队注意到 repo truth 和 agent truth 已经分叉。见 [定位、非目标与对比](#定位非目标与对比)。

## 适配对象

| Surface | Support |
|---|---|
| Claude Code | 原生 skill，加 `.claude/commands` 或 `~/.claude/commands` 下的 slash commands。 |
| OpenAI Codex CLI | 面向 `~/.codex/prompts/` 的 prompt adapters。 |
| Cursor | 面向 `.cursor/commands/` 的 command adapters。 |
| Gemini CLI | 面向 `~/.gemini/commands/harness/` 的 TOML custom command adapters。Google 已于 2026-06-18 面向个人 tiers retired Gemini CLI；企业版 Gemini Code Assist 不受影响，这些 adapters 仍适用于企业/既有安装。 |
| Windsurf / Cline / others | 通用模式：让 agent 指向已安装的 playbook，并说 “run phase N”。 |
| MCP clients | `ai-harness-doctor mcp` 通过 stdio 将 `harness_scan`/`drift`/`validate`/`plan` 暴露为 MCP 工具。 |
| Humans & CI | 直接运行 `npx ai-harness-doctor ...`；不需要 agent。 |

诚实说明：非 Claude adapters 是薄指针，只做过轻量验证。如果某个命令格式变了，请提交 issue。

## 四个阶段

| 阶段 | 脚本 | 产物 | 停止条件 |
|---|---|---|---|
| 0 — 体检 / scan | `scripts/scan.py` | 面向人的或 JSON 健康报告 | 停在用户确认迁移范围时。 |
| 1 — 治疗 / canonicalize | `scripts/canonicalize.py --plan`, `--write-stubs`, `--validate` | 合并计划、canonical `AGENTS.md`、最小 stubs | 直到每个冲突都完成人工裁决才继续。 |
| 2 — 复诊 / drift guard | `scripts/check_drift.py` | Drift 报告和 CI/pre-commit 退出码 | 检查通过，或给出修复建议后停止。 |
| 3 — 疗效验证 | `scripts/eval_run.py` | Before/after JSON 和 Markdown 报告 | 产出指标后停止。 |

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

</details>

<details>
<summary><code>scan</code></summary>

检测五类问题：配置清单、体积/截断风险、重叠候选、带 file:line 证据的冲突候选，以及 nested `AGENTS.md` 文件。

它还会盘点**扩展的 harness surface**——MCP 服务器、subagents、slash 命令、hooks 和权限规则——并运行一次**安全体检**，标记按严重程度排序的发现（HIGH/MEDIUM）：

- 明文密钥（AWS / GitHub / OpenAI / Google / Slack / Anthropic 密钥、私钥块、通用的 `api_key/secret/token=...`），覆盖指令类和 MCP/settings 配置文件。
- 过于宽泛的权限，例如 `Bash(*)`、`*` 和 `defaultMode: bypassPermissions`。
- MCP 卫生问题：不安全的 `http://` 传输以及形似凭据的 env 字面量。
- 有风险的 hook/命令体：`curl … | bash`、`rm -rf`、`--dangerously-skip-permissions` 等。

默认以 0 退出。加上 `--fail-on-security` 后，只要存在任意 HIGH 级发现就以 `2` 退出，很适合作为 CI 卡点。

| Flag | 用途 |
|---|---|
| `--no-security` | 只做清单；跳过安全体检（不输出 `security` key）。 |
| `--fail-on-security` | 存在任意 HIGH 级安全发现时以 `2` 退出。 |

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
  ]
}
```

`security` 发现带有 `level`（`HIGH`/`MEDIUM`）、`category`（`secret`/`mcp`/`permission`/`hook`/`instruction`）、`path` 以及人类可读的 `message`。使用 `--no-security` 时会省略 `security` key。

</details>

<details>
<summary><code>plan</code></summary>

从 scan 输出搭建 Phase 1 合并计划：清单、重叠 clusters、冲突列表，以及 TODO 决策清单。它明确**不会**合并内容或替你选边。

它还会基于 scan 追加一个 **“Merge suggestions (semi-automatic)”** 章节：

- **Overlap consolidation** —— 每个重叠 cluster 会指明 canonical 文件（`AGENTS.md`），并以复选框列表列出要降级为 stub 的文件。
- **Conflict resolutions** —— 每个冲突信号给出一个推荐值，并附上其支撑性的 `path:line` 证据，作为可勾选项。推荐是确定性的（得到最多支撑的值，平票时按字典序决定）。

这些是供人工审阅的建议，而非自动裁决；既有的 inventory/overlap/conflict/TODO 章节都会保留。

</details>

<details>
<summary><code>validate</code></summary>

在你写好 canonical `AGENTS.md` 后验证其结构。它是对 `scripts/canonicalize.py --validate` 的只读透传。

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

默认 dry-run。`--apply` 要求 git tree 干净；`--force` 会覆盖该安全检查。

已知的工具 config 文件在 `assets/agent-tools.json` 中统一定义，这是 `scan`、`stubs`/`canonicalize` 和 `drift` 共同读取的唯一 registry，因此新增一个工具只需修改这一个文件。

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

**D6 fact drift** 会把 `AGENTS.md` 中声明的*事实*与 repo 实际情况交叉验证：Node 版本（对比 `.nvmrc` 和 `package.json` 的 `engines.node`）以及包管理器（对比实际的 lockfile——`package-lock.json`→npm、`pnpm-lock.yaml`→pnpm、`yarn.lock`→yarn）。它只标记明确的矛盾，当 `AGENTS.md` 未声明时保持沉默，因此沉默永远不会产生误报。

**Health score。** 所有发现（D1..D6）汇总为一个 0–100 的健康分，并带字母等级（A ≥90 / B ≥80 / C ≥70 / D ≥60 / F），以 `## Health score` 章节呈现（如 `Score: 85/100 (grade B)`）。加上 `--json` 后，报告会在既有字段之外新增 `score` 和 `grade` key。

`--min-score N` 在分数低于 `N` 时以非零退出——这是一个独立于 `--strict` 的 CI 卡点，两者可同时生效。

**半自动修复：`--fix`。** `--fix` 只自动修复 drift 中安全、机械化的那一部分——目前是 **D3 stub regrowth**。任何长出真实内容或丢失 `AGENTS.md` 指针的工具 stub，都会被重写回其最小的 canonical import-stub 形式（stub 主体复用自 `canonicalize.py`，因此 `--fix` 与 `stubs`/`--write-stubs` 保持同步）。

```bash
npx ai-harness-doctor drift . --fix          # DRY RUN: prints the diff, writes nothing
npx ai-harness-doctor drift . --fix --apply  # actually rewrites the regrown stubs
```

- 默认 `--fix` 是 dry run：它打印将被重写内容的 unified diff，不改动任何文件。
- `--fix --apply` 会就地重写重新长出的 stub 文件。
- 不安全的 drift（D1 命令 drift、D2 path drift、D4 size，以及任何其他语义 drift）永远不会被修改；它们会列在 **“needs manual attention”** 下，并附上可复制粘贴的修复指引。
- 一行汇总会报告 `N fixed/fixable, M need manual attention`。只要还有 drift 残留，命令就以非零退出。

</details>

<details>
<summary><code>eval</code></summary>

运行或对比 before/after agent tasks。

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

**LLM-as-judge check。** 一个任务 check 可以使用 `{ "type": "judge", "rubric": "..." }` 来完成 regex 无法表达的评分。评分委托给 `--judge-cmd "CMD_TEMPLATE"`。judge 会收到环境变量 `JUDGE_ANSWER`、`JUDGE_RUBRIC` 和 `JUDGE_INPUT`（一个临时 JSON `{answer, rubric}` 的路径），且模板占位符 `{answer}`/`{rubric}`/`{input}` 会被替换。它必须打印 `{"passed": bool, "score": number, "reason": "..."}`；若省略 `passed`，则 `score >= 0.5` 记为通过。一个离线的确定性 judge 适用于 CI。

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
- `tools/list` → 公布 `harness_scan`、`harness_drift`、`harness_validate`、`harness_plan`，各自带一个输入 schema `{ repo: string (default "."), ... }`。
- `tools/call` → 分派到匹配的 Python 脚本并返回 `{ content: [{ type: "text", text }] }`。

工具布尔值：`harness_scan`（`json`）、`harness_drift`（`json`、`strict`）、`harness_validate`（`json`）、`harness_plan`。未知的方法和工具会返回一个 JSON-RPC error 对象。

</details>

Slash command quick refs: `/harness-doctor` full pipeline; `/harness-scan` Phase 0; `/harness-treat` Phase 1; `/harness-drift` Phase 2; `/harness-eval` Phase 3.

环境变量：

| 变量 | 用途 |
|---|---|
| `AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1` | 关闭每天一次的 npm 更新提示。 |
| `AI_HARNESS_DOCTOR_SKIP=1` | 显式绕过本地 pre-commit drift hook。 |

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

- Repo harness-ification：把项目脚本 CLI 化，添加验证 gates，并清晰分层文档。
- 更丰富的 eval task packs，覆盖更多语言、仓库形态和多轮工作流。
- 随着命令格式稳定，增加更多 agent adapters。
- 等 Antigravity CLI 的 custom-command format 文档化后，添加 Antigravity CLI adapter。

## 贡献

欢迎提交 bug reports 和聚焦的 PR。请保持 scripts 确定性、仅依赖 stdlib，并通过：

```bash
python3 -m unittest discover -s tests -v
```

## License

MIT. Copyright (c) NieZhuZhu.
