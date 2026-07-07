---
name: ai-harness-doctor
description: 给仓库的 AI harness 配置层做体检-治疗-复诊-疗效验证，触发于 AGENTS.md、CLAUDE.md、.cursorrules、copilot-instructions、迁移/统一/整理 agent 配置、agent 配置体检、agent config drift、consolidate agent configs、AI harness audit 等场景。
---

# ai-harness-doctor

一句话定位：给仓库的 AI harness 配置层做「体检 → 治疗 → 复诊 → 疗效验证」，把散落、漂移的 agent 配置收敛为单一事实源 `AGENTS.md`，并持续守护。

## 何时使用

- 仓库里同时存在 `AGENTS.md`、`CLAUDE.md`、`.cursorrules`、`.cursor/rules/*.mdc`、`.windsurfrules`、`.github/copilot-instructions.md`、`GEMINI.md`、`.clinerules` 等多份规则。
- 用户要求「迁移 / 统一 / 整理 agent 配置」「agent 配置体检」「检查 agent config drift」「consolidate agent configs」「AI harness audit」。
- 需要把多工具配置降级为指向 `AGENTS.md` 的最小 stub，并建立 CI / pre-commit drift guard。

## 何时不用

- 不做从零 init 空仓库：这会撞官方 `/init`。
- 不做仓库 harness 化重构：脚本 CLI 化、验证 gate、文档分层等归 v2。
- 不生成语言 / 框架专属规范：例如从零写 React、Go、Python 规范归 v2 或项目专项。
- 不替用户裁决语义冲突：脚本只做确定性机械动作，语义合并、去重、冲突裁决由 agent 引导人工完成。

## 阶段 0 体检（Scan / 审计）

### 输入

- 目标仓库根目录。
- 可选体积阈值，默认 `32768` bytes（Codex `project_doc_max_bytes` 常见默认）。

### 动作

运行只读扫描：

```bash
python3 scripts/scan.py /path/to/repo
python3 scripts/scan.py /path/to/repo --json
```

检查内容：配置文件清单、大小告警、重叠候选、冲突候选、嵌套 `AGENTS.md`。

### 产物

- 人类可读的「体检报告」。
- `--json` 机器输出：`files`、`warnings`、`overlaps`、`conflicts`、`nested`。

### 明确停止条件

停在「用户确认迁移范围」：全仓、子目录或指定文件。未确认前不要进入治疗。

## 阶段 1 治疗（Canonicalize / 收敛迁移）

### 输入

- 阶段 0 报告。
- 用户确认的迁移范围。
- 人工裁决后的冲突结论。

### 动作

先生成合并计划骨架：

```bash
python3 scripts/canonicalize.py --plan /path/to/repo -o merge-plan.md
```

然后由 agent 手工编写 root `AGENTS.md`。脚本不会做语义合并。

`AGENTS.md` 存在后，预览 / 应用工具 stub 降级：

```bash
python3 scripts/canonicalize.py --write-stubs /path/to/repo
python3 scripts/canonicalize.py --write-stubs /path/to/repo --apply
```

写入脚本默认 dry-run；`--apply` 前要求目标仓库是 git repo 且工作树干净，可用 `--force` 覆盖。

最后校验：

```bash
python3 scripts/canonicalize.py --validate /path/to/repo
python3 scripts/canonicalize.py --validate /path/to/repo --json
```

### 产物

- canonical root `AGENTS.md`。
- 多工具最小 stub：`CLAUDE.md`、`.cursorrules`、`.windsurfrules`、`.cursor/rules/agents-md.mdc`、`copilot-instructions`、`GEMINI.md`、`.clinerules`。
- 校验报告。

### 明确停止条件

停在「所有冲突已人工裁决」。规则打架时绝不擅自决定；列出冲突、证据和建议，请用户或仓库 owner 裁决。

## 阶段 2 复诊（Drift Guard / 漂移治理）

### 输入

- 已收敛的目标仓库。
- root `AGENTS.md` 与工具 stub。

### 动作

运行 drift guard：

```bash
python3 scripts/check_drift.py /path/to/repo
python3 scripts/check_drift.py /path/to/repo --json
python3 scripts/check_drift.py /path/to/repo --strict
```

检查：

- D1：命令漂移，核对 `package.json` scripts 与 `Makefile` targets。
- D2：路径漂移，核对反引号路径是否存在。
- D3：stub 再分叉，检查体积与 `AGENTS.md` pointer。
- D4：`AGENTS.md` 体积。
- D5：嵌套 `AGENTS.md` inventory（信息项，不阻断）。

### 产物

- drift 报告。
- 可接入 CI / pre-commit 的失败退出码。
- 修复建议：指出要改哪类内容、通常在哪一行。

### 明确停止条件

停在「校验通过或修复建议已给出」。不要在复诊阶段擅自重写语义内容。

## 阶段 3 疗效验证（Eval / 有效性验证）

### 输入

- 固定任务文件 `tasks.json`。
- before / after 两个标签与目标仓库。
- runner 模板，例如 `claude -p {prompt} --output-format json`。

### 动作

运行任务：

```bash
python3 scripts/eval_run.py --tasks tasks.json --label before --workdir /path/to/repo -o results-before.json
python3 scripts/eval_run.py --tasks tasks.json --label after --workdir /path/to/repo -o results-after.json
```

对比结果：

```bash
python3 scripts/eval_run.py --compare results-before.json results-after.json -o eval-report.md
```

runner 缺失时，脚本输出手工协议，不做伪装。

### 产物

- before / after JSON 结果。
- Markdown 对比报告：通过率、耗时、token / cost（如果 runner 输出提供）。

### 明确停止条件

停在「指标产出」。报告回答：这份 `AGENTS.md` 是否让 agent 行为更稳定。

## 决策规则

### 什么进 AGENTS.md

- 只写 agent 无法从代码、manifest、CI 配置直接推断的信息。
- 写稳定约定：项目结构、必跑命令、危险操作、安全边界、PR / commit 约定。
- 用渐进披露：细节放 `references/`，`AGENTS.md` 只保留入口与关键规则。

### 什么不进 AGENTS.md

- 不搬运 package scripts、README、框架默认规范的全文。
- 不写易过期的长列表，除非有 drift guard 能验证。
- 不复制工具 stub 正文。

### monorepo 何时用子目录局部 AGENTS.md

- 子项目语言、命令、安全边界显著不同。
- 子目录有独立 owner / release 流程。
- root 只写全局规则，局部 `AGENTS.md` 写该子树差异。

### 冲突消解升级路径

1. 事实冲突：优先以 manifest、CI、代码实况为证据。
2. 偏好冲突：提交给 owner 裁决，不由 agent 拍板。
3. 过期规则：标注来源、建议删除，但仍需确认。
4. 无法判断：保留在计划的 conflict list，阻塞治疗完成。

## 命名化反模式清单

### 全量搬运

症状：把所有旧内容原样堆进 `AGENTS.md`。

纠正：只保留不可推断的规则，重复事实改成引用 manifest 或 `references/`。

### 擅自裁决

症状：发现 `pnpm install` vs `npm install` 后直接选一个。

纠正：列出 file:line 证据，请用户或 owner 裁决。

### 复制粘贴降级

症状：stub 里又复制正文，导致再次分叉。

纠正：stub 只能是 pointer / import，不保留规则正文。

### 静默截断

症状：无视 32KB 或 12KB 体积告警。

纠正：拆分 references，保持 `AGENTS.md` 小而深。

### 一次性大爆炸

症状：不分阶段、不设检查点，直接改完所有文件。

纠正：严格按体检、治疗、复诊、疗效验证推进，每阶段都有停止条件。

## References 索引

- `references/tool-matrix.md`：各工具读取文件、import 能力、优先级与降级策略。
- `references/section-template.md`：推荐 `AGENTS.md` 章节组织。
- `references/migration-decision-tree.md`：迁移范围决策树。
- `references/conflict-resolution.md`：冲突分类、消解规则与上报格式。
- `assets/AGENTS.template.md`：英文 `AGENTS.md` 模板。
- `assets/github-actions-drift.yml`：目标仓库 CI gate 模板。
- `assets/pre-commit-hook.sh`：目标仓库 pre-commit hook 模板。
- `commands/`：Claude Code slash commands，按阶段路由到本 skill。
- `adapters/`：Codex、Cursor、Gemini 与通用 agent 的薄指针模板。
- `bin/cli.js`：npm CLI、安装器与 Python 脚本转发入口。
