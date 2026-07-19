[English](README.md) | **简体中文** | [日本語](README.ja.md) | [Español](README.es.md) | [한국어](README.ko.md) | [Português (Brasil)](README.pt-BR.md) | [Français](README.fr.md)

# 🩺 AI Harness Doctor

**编码智能体可能一脸自信地遵循已经过期的仓库指令。** AI Harness Doctor 会审计 `AGENTS.md`、`CLAUDE.md`、Cursor 规则、hooks、MCP 设置及相关 harness 文件，避免这些漂移最终变成失败的 PR。

它帮助你把分散的规则合并到一份由人维护的 `AGENTS.md`，将工具专用文件降级为短指针，并衡量整理后的 harness 是否真的提高了智能体回答质量。

<p><a href="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml"><img align="left" alt="CI" src="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml/badge.svg"></a> <a href="https://www.npmjs.com/package/ai-harness-doctor"><img align="left" alt="npm version" src="https://img.shields.io/npm/v/ai-harness-doctor.svg"></a> <img align="left" alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"> <img align="left" alt="Python 3.9+" src="https://img.shields.io/badge/Python-3.9%2B-blue.svg"> <img align="left" alt="Node &gt;=16" src="https://img.shields.io/badge/Node-%3E%3D16-green.svg"></p>
<br clear="left">

## 效果证据

- **修好 harness，agent 的表现可测量地变好。** 在可复现的前后对照基准中，把互相冲突的配置整合成一份规范 `AGENTS.md` 后，agent 客观题正确数从 **6/28 提升到 28/28**，两个反复横跳的不稳定回答全部消除，相同任务的平均延迟下降 27%、记录成本下降 17% —— [方法论与原始数据](benchmark/README.md)。
- **在真实生产仓库上同样成立。** 在 trycompai/comp（约 1.7k star、活跃开发的 bun monorepo，其 `CLAUDE.md` 从 `AGENTS.md` 分叉后仍在教已过期的 `npx` 命令）上，一次治疗就让 agent 客观题从 **18/24 提升到 24/24**——治疗前它在两轮运行中都确定性地逐字复读过期文档——同时延迟下降 37%、agent 轮数减少 45%；效果边界也如实公开：在文档本就健康的 openai/codex 上发布了**无效果的 null result** —— [正面案例](benchmark/corpus/evals/comp/README.md) · [边界案例](benchmark/corpus/evals/codex/README.md)。
- **这个病在开源顶流仓库里真实存在。** 由 14 个知名仓库组成的语料库（react、vscode、n8n、ollama、transformers、dify、supabase、gemini-cli、codex、home-assistant、zed、elasticsearch、cline、ghostty，58k–247k star，以 submodule 固定版本）中 10/14 已有根 `AGENTS.md`，但一次确定性批量扫描仍在 150 个 agent 配置文件中发现 **96 个缺口、44 处指令重叠、15 处声明与代码不一致、3 处同层冲突** —— [语料库与逐仓结果](benchmark/corpus/README.md)。
- **报告的发现值得信任。** 针对真实仓库的 38 轮验证记录已产出十五次误报修复（openai/codex、microsoft/vscode、cline、gemini-cli、assistant-ui 等），每次都随回归测试发布；暂缓处理的类别公开记录、绝不隐藏 —— [外部验证日志](EXTERNAL_VALIDATION.md)。

## 60 秒开始

零安装、只读体检：

```bash
npx ai-harness-doctor scan .
```

解释某个路径会应用哪些指令：

```bash
npx ai-harness-doctor explain . packages/api/src/handler.ts
```

验证 Node 和 Python 运行时：

```bash
npx ai-harness-doctor doctor --self-test
```

查看 npx 解析到的版本：

```bash
npx ai-harness-doctor --version
```

以上命令都不会修改被审计的仓库。

## 检查内容

| 范围 | Doctor 检查什么 |
|---|---|
| 清单 | Canonical 文件、工具规则、嵌套作用域、MCP、hooks、commands、权限和 subagents。 |
| 安全 | 明文 secret、过宽权限、不安全 MCP transport、危险 hook 以及权限绕过指引。 |
| 一致性 | 缺失脚本、移动路径、包管理器漂移、运行时版本漂移、坏链接、多套 lockfile，以及带标签的 lint rule 或 branch ref 等安全排除误报的非路径标识符。 |
| 指令质量 | 上下文过大、照搬 README、静默裁决、重复内容和同作用域冲突。 |
| 作用域 | 从根到最近 `AGENTS.md` 的继承，以及有边界的 Claude、Cursor、Copilot glob 适用性。 |
| 效果 | 前后正确率、稳定性、延迟、成本、证据新鲜度和健康等级。 |

安全读取不会越出被审计仓库。超大文件仍会完整计算 SHA-256、行数、secret 和权限绕过；`--max-bytes` 只限制语义分析。

## 四个阶段

| 阶段 | 目标 | 主要命令 | 人工停点 |
|---|---|---|---|
| 0 — Checkup | 发现风险、冲突、缺口和仓库事实。 | `scan`, `explain` | 确认迁移范围。 |
| 1 — Treat | 生成合并计划并整理成 canonical 指令。 | `plan`, `validate`, `stubs` | 裁决每一个语义冲突。 |
| 2 — Follow-up | 防止命令、路径、链接、stub 和事实重新过期。 | `drift`, `guard`, `review` | 决定代码还是指令有误。 |
| 3 — Efficacy | 衡量 harness 是否改善智能体行为。 | `eval` | 判断证据是否充分。 |

脚本只做确定性机械工作。它不会偷偷替你选择 npm 或 pnpm，也不会裁决争议命令或自动语义合并文本。

## 整理一个仓库

先生成可审查计划，编写 `AGENTS.md`，验证后再把重复工具文件替换成短指针：

```bash
npx ai-harness-doctor scan .
npx ai-harness-doctor plan . -o merge-plan.md
# Write and review AGENTS.md, then:
npx ai-harness-doctor validate .
npx ai-harness-doctor stubs . --apply
npx ai-harness-doctor guard . --apply
```

也可以安装 Claude Code skill，然后运行 `/harness-doctor .` 或 `/harness-treat .`。仓库事实存在歧义时，智能体会停下来请你决定。

## 安装与更新

| 目标 | 命令 |
|---|---|
| 为当前用户安装 Claude Code skill | `npx ai-harness-doctor install` |
| 安装 Codex prompts | `npx ai-harness-doctor install --agent codex` |
| 在仓库中安装 Cursor commands | `npx ai-harness-doctor install --agent cursor --project` |
| 在仓库中安装全部支持的 adapters | `npx ai-harness-doctor install --agent all --project` |
| 将最新包重新部署到已追踪安装 | `npx ai-harness-doctor@latest update` |
| 删除已安装 adapters | `npx ai-harness-doctor uninstall --agent all` |

Copy 安装会追踪所有权。更新和卸载会保留非本工具所有的冲突文件及用户改动。测试必须使用隔离的 `HOME`。

## 在 CI 中长期守护

安装 provider-aware 的 pre-commit、PR 和定时 guard：

```bash
npx ai-harness-doctor guard . --apply
```

Guard 的 apply/remove 会将 Git hook、provider 文件和 `AGENTS.md` 作为一个事务。

捕获到失败时回滚，中断的变更会在下次 `--apply` 前恢复，恢复状态不安全或已被外部修改时则 fail-closed。

GitHub guard 会把 scan 与 drift 合并为一条完整 PR review。可定位发现会成为行内评论；总结包含严重度、健康分、证据、修复建议和优先级。

已经使用 pre-commit framework？

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/NieZhuZhu/ai-harness-doctor
    rev: v1.13.6
    hooks:
      - id: ai-harness-doctor-drift
      - id: ai-harness-doctor-scan
```

每周体检只维护一个属于自己的 incident issue，并在恢复后关闭它。仓库维护合同见 [`references/maintenance-contract.md`](references/maintenance-contract.md)。

## GitHub Action 与 SARIF

Marketplace Action 默认运行所选 ref 中自带的代码，并生成 SARIF、Action outputs 和 Job Summary：

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

可用输出包括 `status`、各严重度数量、`finding-count`、`resolved-baseline-count`，以及 drift 的 `health-score` / `health-grade`。

状态优先级是 `findings > maintenance > ok`。有效的非零质量 gate 会先发布 SARIF 和总结，再恢复原始 CLI exit code。

SARIF finding 带稳定 partial fingerprint 和独立的 scan/drift category，因此无关行移动不会重复开告警，两类上传也不会互相关闭。

当额外 option value 含空格，或需要保留精确/重复 argv 边界时，请使用 `args-json`：

```yaml
- uses: NieZhuZhu/ai-harness-doctor@v1
  with:
    command: drift
    path: .
    args-json: '["--baseline", ".ai-harness-doctor/drift baseline.json", "--check-baseline"]'
```

`args-json` 与 legacy `args` 互斥。Legacy `args` 只保留首行空白切分；两种 input 都不会经过 shell evaluation。

## 安全接入既有债务

Baseline 是可审查的债务登记表，不是 ignore 列表。它将发现分为 new、known 和 repaired：

```bash
npx ai-harness-doctor scan . --write-baseline .ai-harness-doctor/scan-baseline.json
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json \
  --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json --check-baseline
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json --prune-baseline
```

`baselined` 保存 known debt，`resolved_baseline` 保存已修复条目。Check 在需要清理时以 `9` 退出；prune 只原子删除已修复条目，绝不会记录新发现。

HIGH 安全发现永远不能进入 baseline。普通损坏 baseline 不会压制任何内容；显式 check/prune 会 fail closed 且不写文件。

## 命令指南

| 命令 | 用途 | 默认写入？ |
|---|---|---:|
| `scan` | 完整体检、安全扫描、缺口、冲突、语义和项目快照。 | 否 |
| `explain` | 解释某路径的有效指令链和诊断作用域。 | 否 |
| `plan` | 生成可审查的整理计划。 | 仅在指定输出路径时 |
| `validate` | 检查 canonical 路径、大小、必需章节和未解决 draft marker。 | 否 |
| `stubs` | 预览或应用最小工具指针。 | 否 |
| `drift` | D1–D8、健康分、baseline 生命周期和安全 D3 修复。 | 否 |
| `guard` | 安装或删除 pre-commit 与 CI guard。 | 否 |
| `review` | 根据 scan/drift 报告生成或发布一条 GitHub PR review。 | 仅 `--post` 时 |
| `eval` | 生成、运行、比较、重评、打分和趋势分析。 | 取决于输出 flags |
| `mcp` | 启动只读 MCP stdio server。 | 否 |
| `doctor` | 验证 Node/Python runtime 和已打包引擎。 | 否 |

运行 `npx ai-harness-doctor help` 或查看 [`SKILL.md`](SKILL.md) 获取完整选项与行为协议。

## 支持的表面

| 表面 | 支持情况 |
|---|---|
| Claude Code | 原生 skill 和 slash commands。 |
| OpenAI Codex CLI | Prompt adapters。 |
| Cursor | Project 或 user command adapters。 |
| Gemini CLI | 面向 enterprise/既有安装的 TOML command adapters。 |
| MCP clients | 通过 JSON-RPC stdio 暴露七个只读工具。 |
| GitHub Actions | Composite Action、SARIF、Job Summary、outputs 和 PR feedback。 |
| GitLab / Codebase | 共享 scan、drift 和可选 eval gates。 |
| 其他 agents | 指向 playbook 的 universal pointer。 |

非 Claude adapter 刻意保持轻量。广泛分发规则应交给 Ruler 或 rulesync；本项目专注诊断、证据、安全、漂移与效果。

## 安全模型

- Scan 只读，并排除仓库派生的外部 symlink。
- 缺失路径若被仓库 `.gitignore` 忽略，会视为有意的 runtime 路径；synthetic Git metadata 会排除本地/全局规则，Git 失败时仍保留 finding。
- 若相邻词语将 backtick `org/name` 明确标注为 Docker/OCI image 或 RPC/API method，则视为 runtime identifier 而非受检路径；该排除是 fail-closed 的，带扩展名或三段及以上的 token 仍按路径检查。
- Nested drift 会沿 lexical package ancestors 解析 command、path、runtime/package-manager fact，且不搜索 sibling package；Markdown link 仍相对当前文件。
- 写入路径拒绝 symlink 文件或既有父目录。
- Plugins 只有显式提供 `--allow-plugins` 才会启用。
- Secret finding 只报告类型/路径而不复现值；仓库控制的 hook 和 MCP command/URL inventory 会在 JSON、Markdown 和完整报告序列化前脱敏，危险 hook 片段在 SARIF 和 PR feedback 中也会保持脱敏。
- Installer mutation 会加锁、写 journal、追踪所有权并支持恢复。
- MCP 工具保持只读；finding 不是 transport failure。
- 外部 judge 和真实 LLM grading 都是 opt-in；远程 endpoint 必须使用 HTTPS，本地 loopback HTTP 需显式配置，redirect 会被拒绝，失败会回退确定性 judge。
- Eval 结果产物和报告会脱敏 runner/judge 诊断、嵌套 usage metadata 与 matrix runner template 中的高置信凭据；数值 usage 仍保留，评分继续使用内存中的原始有界输出。
- 无遥测。可用 `AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1` 关闭可选 npm 更新检查。

## 证据与基准

| 侧 | 通过数 | 反复任务 | 平均延迟/任务 | 记录成本 |
|---|---:|---:|---:|---:|
| Before：冲突/过期配置 | 6/28 | 2 | 16.0s | $5.82 |
| After：canonical `AGENTS.md` | 28/28 | 0 | 11.7s | $4.81 |

方法和复现见 [`benchmark/README.md`](benchmark/README.md)。这是一个 demo 仓库、每侧两次运行的证据，不是普遍性能承诺。

## 文档导航

| 文档 | 用途 |
|---|---|
| [`SKILL.md`](SKILL.md) | 完整四阶段行为与命令协议。 |
| [`references/migration-decision-tree.md`](references/migration-decision-tree.md) | 选择合适迁移路径。 |
| [`references/conflict-resolution.md`](references/conflict-resolution.md) | 人工裁决流程。 |
| [`references/tool-matrix.md`](references/tool-matrix.md) | 工具文件支持与所有权。 |
| [`references/maintenance-contract.md`](references/maintenance-contract.md) | Baseline、Action、guard、CI、release 和 installer 不变量。 |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | 贡献工作流与检查。 |
| [`RELEASING.md`](RELEASING.md) | Tag 驱动的 npm、GitHub Release、浮动 Action tag 和 Marketplace 流程。 |
| [`EXTERNAL_VALIDATION.md`](EXTERNAL_VALIDATION.md) | 对真实仓库的只读验证记录。 |

## 项目状态

- Python 3.9+、Node 16+，运行时只使用标准库。
- npm release 由 tag 驱动并带 provenance。
- Stable release 会移动浮动 major Action tag（`1.x` 对应 `v1`）。
- Feature 发布使用 minor，纯 bugfix 使用 patch。
- 公共行为修改必须在同一 PR 同步所有已发布语言文档。

## 贡献

欢迎 issue 和 PR。请阅读 [`CONTRIBUTING.md`](CONTRIBUTING.md)，行为修改必须带测试，并在同一 PR 同步全部翻译 README。

安全漏洞请按 [`SECURITY.md`](SECURITY.md) 提交，不要创建公开 issue。

## 许可证

[MIT](LICENSE)
