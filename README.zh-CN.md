[English](README.md) | **简体中文** | [日本語](README.ja.md)

# 🩺 AI Harness Doctor

审计、收敛并守护仓库里的 AI agent 配置（`AGENTS.md` / `CLAUDE.md` / `.cursorrules` / copilot-instructions / `GEMINI.md` ...）：一条「体检→治疗→复诊→疗效验证」流水线。

[![CI](https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml/badge.svg)](https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml)
[![npm version](https://img.shields.io/npm/v/ai-harness-doctor.svg)](https://www.npmjs.com/package/ai-harness-doctor)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![Node >=16](https://img.shields.io/badge/Node-%3E%3D16-green.svg)

## 为什么需要

Agent 配置漂移是一种仓库慢性病：N 个工具读取 N 份规则文件，团队把同一套说明到处复制，命令会过期，路径会搬家，Codex 这类约 32KB 的上下文文件限制还可能静默截断。最后 agent 看起来很自信，实际却在执行旧规则或互相冲突的规则。

AI Harness Doctor 把这些配置收敛成单一事实源 `AGENTS.md`，把各工具文件降级为最小 stub，并补上 drift gate 与可选的前后疗效评估。

## Benchmark

这是本项目的核心差异：demo 仓库的代码与 package manifest 完全不变，只改变 agent 可读到的配置层。

| 指标 | Before：混乱且互相冲突的配置 | After：canonical `AGENTS.md` |
|---|---:|---:|
| 客观任务答对数 | 3/7 | 7/7 |
| 单任务平均耗时 | 20.2s | 11.4s |
| 捕获到的总成本 | $1.81 | $1.19 |

范围说明：7 个客观任务，单次运行，demo repo，runner 为 `claude -p`，Claude CLI 2.1.202。复现方式见 [`benchmark/`](benchmark/) 与 [`benchmark/README.md`](benchmark/README.md) 中的三条命令。

## 快速开始

安装到 Claude Code（默认）：

```bash
npx ai-harness-doctor install
```

安装其他 agent 的适配器：

```bash
npx ai-harness-doctor install --agent codex
npx ai-harness-doctor install --agent cursor
npx ai-harness-doctor install --agent gemini
npx ai-harness-doctor install --agent all
```

在支持的场景下安装到当前项目，而不是用户目录：

```bash
npx ai-harness-doctor install --project
npx ai-harness-doctor install --agent all --project
```

Claude Code slash commands：

| 命令 | 作用 | 示例 |
|---|---|---|
| `/harness-doctor` | 全流程：阶段 0→2；阶段 3 仅在明确要求时执行 | `/harness-doctor .` |
| `/harness-scan` | 阶段 0 体检：清单、体积、重叠、冲突 | `/harness-scan ~/repo` |
| `/harness-treat` | 阶段 1 治疗：计划、人工裁决冲突、编写 canonical `AGENTS.md`、stub、validate | `/harness-treat .` |
| `/harness-drift` | 阶段 2 复诊：drift guard 与修复建议 | `/harness-drift .` |
| `/harness-eval` | 阶段 3 疗效验证：前后任务指标 | `/harness-eval .` |

给人和 CI 用的裸 CLI：

```bash
npx ai-harness-doctor scan .
npx ai-harness-doctor plan . -o merge-plan.md
npx ai-harness-doctor stubs . --apply
npx ai-harness-doctor drift . --strict
npx ai-harness-doctor eval --tasks tasks.json --label after --workdir . -o results-after.json
```

## 支持哪些工具

| 入口 | 支持方式 |
|---|---|
| Claude Code | 原生 skill，加 `.claude/commands` 或 `~/.claude/commands` slash commands。 |
| OpenAI Codex CLI | 写入 `~/.codex/prompts/` 的 prompt adapters。 |
| Cursor | 写入 `.cursor/commands/` 的 command adapters。 |
| Gemini CLI | 写入 `~/.gemini/commands/harness/` 的 TOML 自定义命令。 |
| Windsurf / Cline / 其他 | 通用模式：让 agent 读取已安装的 PLAYBOOK，并说“run phase N”。 |
| 人类与 CI | 直接运行 `npx ai-harness-doctor ...`，不需要 agent。 |

诚实说明：非 Claude 适配器只是薄指针，做过轻量验证；如果某个工具的命令格式变了，欢迎提 issue。

## 四个阶段

| 阶段 | 脚本 | 产物 | 停止条件 |
|---|---|---|---|
| 0 — 体检 / scan | `scripts/scan.py` | 人类可读或 JSON 体检报告 | 停在用户确认迁移范围。 |
| 1 — 治疗 / canonicalize | `scripts/canonicalize.py --plan`、`--write-stubs`、`--validate` | 合并计划、canonical `AGENTS.md`、最小 stubs | 所有冲突完成人工裁决前不继续。 |
| 2 — 复诊 / drift guard | `scripts/check_drift.py` | drift 报告与 CI/pre-commit 退出码 | 校验通过，或给出修复建议后停止。 |
| 3 — 疗效验证 / eval | `scripts/eval_run.py` | before/after JSON 与 Markdown 报告 | 指标产出后停止。 |

示例：

```bash
npx ai-harness-doctor scan . --json
npx ai-harness-doctor plan . -o merge-plan.md
npx ai-harness-doctor stubs . --apply --force
npx ai-harness-doctor drift . --strict
npx ai-harness-doctor eval --compare results-before.json results-after.json -o eval-report.md
```

## 功能对比

| 能力 | AI Harness Doctor | 手工迁移 | 官方 `/init` | 纯文档 |
|---|---:|---:|---:|---:|
| 带证据的冲突检测 | ✅ | △ | ❌ | ❌ |
| 重叠百分比 | ✅ | △ | ❌ | ❌ |
| 体积 / 截断告警 | ✅ | △ | ❌ | ❌ |
| stub 降级与再分叉守护 | ✅ | △ | ❌ | ❌ |
| CI / pre-commit gate | ✅ | △ | ❌ | △ |
| 前后疗效 eval | ✅ | ❌ | ❌ | ❌ |
| 多 agent adapters | ✅ | △ | ❌ | ❌ |

## 仓库结构

```text
SKILL.md                         # skill playbook 与阶段停止条件
bin/cli.js                       # npm CLI 与安装器
commands/                        # Claude Code slash commands
adapters/                        # Codex、Cursor、Gemini 与通用指针
scripts/                         # Python 标准库确定性机械脚本
references/                      # 迁移与冲突处理参考
assets/                          # 模板、CI/pre-commit 示例
benchmark/                       # 真实 before/after eval 数据
tests/                           # 标准库 unittest 套件
```

## Roadmap v2

- 仓库 harness 化：把项目脚本 CLI 化、补验证 gate、做好文档分层。
- 更丰富的 eval task packs，覆盖更多语言、仓库形态与多轮流程。
- 随着各工具命令格式稳定，补充更多 agent adapters。

## 贡献

欢迎提交 bug report 和聚焦的 PR。请保持脚本确定性、仅依赖标准库，并通过 `python3 -m unittest discover -s tests -v`。

## License

MIT. Copyright (c) NieZhuZhu.
