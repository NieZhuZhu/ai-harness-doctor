# 工具矩阵

本表用于阶段 1 治疗时决定哪些文件降级为 stub。能力与限制以官方文档为准；不确定处明确标注。

## Claude Code

- 读取文件：常见为仓库 `CLAUDE.md`，也可能读取用户级 / 父级配置；本 skill 处理 root `CLAUDE.md` 与 `.claude/CLAUDE.md`。
- import / 引用：支持 `@path` 引用文件。
- 优先级 / 合并顺序：以 Claude Code 官方解析顺序为准。
- 大小限制：以官方文档为准。
- 降级策略：`CLAUDE.md` 首行写 `@AGENTS.md`，第二行写最小注释；不复制正文。

## Codex

- 读取文件：`AGENTS.md`，包括 root 与子目录局部文件。
- import / 引用：以官方文档为准；本 skill 不依赖 import。
- 优先级 / 合并顺序：通常按目录层级应用，越靠近工作目录越具体；以官方文档为准。
- 大小限制：`project_doc_max_bytes` 默认常见为 32KB，超限可能导致上下文截断。
- 降级策略：保留 root `AGENTS.md` 为单一事实源；monorepo 可保留子目录局部 `AGENTS.md`。

## Cursor

- 读取文件：旧式 `.cursorrules`；新式 `.cursor/rules/*.mdc` 或 `.md`。
- import / 引用：规则能力随 Cursor 版本变化，以官方文档为准。
- 优先级 / 合并顺序：项目规则与全局规则的合并顺序以官方文档为准。
- 大小限制：以官方文档为准。
- 降级策略：`.cursorrules` 写 pointer；`.cursor/rules/` 下保留单个 `agents-md.mdc`，用 `alwaysApply: true` 指向 `AGENTS.md`。

## Windsurf

- 读取文件：`.windsurfrules`、`.windsurf/rules/*`。
- import / 引用：以官方文档为准。
- 优先级 / 合并顺序：以官方文档为准。
- 大小限制：以官方文档为准。
- 降级策略：保留最小 pointer，说明所有规则在 `AGENTS.md`。

## GitHub Copilot

- 读取文件：`.github/copilot-instructions.md`、`.github/instructions/*.instructions.md`。
- import / 引用：不依赖 import；本 skill 假设不能安全 import `AGENTS.md`。
- 优先级 / 合并顺序：以 GitHub Copilot 官方文档为准。
- 大小限制：以官方文档为准。
- 降级策略：保留极短 pointer note，提醒不要复制规则正文。

## Gemini CLI

- 读取文件：常见为 `GEMINI.md`；可配置 context 文件名。
- import / 引用：以官方文档为准。
- 优先级 / 合并顺序：以官方文档为准。
- 大小限制：以官方文档为准。
- 降级策略：`GEMINI.md` 写 pointer，并建议配置 `contextFileName=AGENTS.md`。

## Cline

- 读取文件：`.clinerules` 文件或 `.clinerules/` 目录下规则文件。
- import / 引用：以官方文档为准。
- 优先级 / 合并顺序：以官方文档为准。
- 大小限制：以官方文档为准。
- 降级策略：保留最小 pointer；复杂目录规则需要人工确认后再迁移。

## Roo

- 读取文件：`.roo/rules/*.md`、`.roo/rules/*.mdc` 等。
- import / 引用：以官方文档为准。
- 优先级 / 合并顺序：以官方文档为准。
- 大小限制：以官方文档为准。
- 降级策略：v1 主要扫描与报告；是否降级为 pointer 需人工确认。
