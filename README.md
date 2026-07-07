# ai-harness-doctor

AI harness doctor audits, consolidates, guards, and evaluates repository agent configuration. It turns scattered instructions into a canonical `AGENTS.md`. Scripts are deterministic mechanics only; semantic merge decisions stay with the agent and human owner.

## 定位

`ai-harness-doctor` 给仓库的 agent 配置层做四阶段治理：阶段 0 体检、阶段 1 治疗、阶段 2 复诊、阶段 3 疗效验证。目标是把 `AGENTS.md`、`CLAUDE.md`、`.cursorrules`、`.cursor/rules/*.mdc`、`.windsurfrules`、`.github/copilot-instructions.md`、`GEMINI.md`、`.clinerules` 等散落配置收敛到单一事实源 `AGENTS.md`。

## 为什么需要

多 agent 工具会读取不同配置文件；团队经常把同一规则复制到多处，随后命令、路径、偏好和安全边界开始漂移。结果是 agent 行为不稳定、上下文膨胀，甚至被 32KB 左右的上下文文件限制静默截断。本 skill 用扫描、stub 降级、drift guard 和 eval 把配置治理变成可复诊的流程。

## 安装

克隆或复制到用户级 skill 目录：

```bash
mkdir -p ~/.claude/skills
git clone <repo-url> ~/.claude/skills/ai-harness-doctor
```

或放到项目级目录：

```bash
mkdir -p .claude/skills
cp -R /path/to/ai-harness-doctor .claude/skills/ai-harness-doctor
```

## 四阶段 walkthrough

### 阶段 0 体检（Scan / 审计）

```bash
python3 scripts/scan.py /path/to/target-repo
python3 scripts/scan.py /path/to/target-repo --json
```

输出配置文件清单、大小告警、重叠候选、冲突候选和嵌套 `AGENTS.md`。

### 阶段 1 治疗（Canonicalize / 收敛迁移）

```bash
python3 scripts/canonicalize.py --plan /path/to/target-repo -o merge-plan.md
```

agent 按计划和人工裁决手工编写 root `AGENTS.md`。然后预览 / 应用 stub：

```bash
python3 scripts/canonicalize.py --write-stubs /path/to/target-repo
python3 scripts/canonicalize.py --write-stubs /path/to/target-repo --apply
python3 scripts/canonicalize.py --validate /path/to/target-repo
```

写入默认 dry-run，`--apply` 要求目标仓库是 clean git repo；可用 `--force` 覆盖。

### 阶段 2 复诊（Drift Guard / 漂移治理）

```bash
python3 scripts/check_drift.py /path/to/target-repo
python3 scripts/check_drift.py /path/to/target-repo --json
python3 scripts/check_drift.py /path/to/target-repo --strict
```

检查命令、路径、stub 再分叉、体积和嵌套 `AGENTS.md`。

### 阶段 3 疗效验证（Eval / 有效性验证）

```bash
python3 scripts/eval_run.py --tasks assets/tasks.example.json --label before --workdir /path/to/target-repo -o results-before.json
python3 scripts/eval_run.py --tasks assets/tasks.example.json --label after --workdir /path/to/target-repo -o results-after.json
python3 scripts/eval_run.py --compare results-before.json results-after.json -o eval-report.md
```

如果 runner 缺失，脚本会输出手工记录协议。

## 目录结构

```text
SKILL.md                         # skill 入口
scripts/                         # deterministic CLI mechanics
references/                      # 迁移和冲突处理参考
assets/                          # 模板与示例
tests/                           # stdlib unittest suite
```

## 开发与测试

```bash
python3 -m unittest discover -s tests -v
```

所有脚本只依赖 Python 3.9+ 标准库。

## v2 roadmap

- 仓库 harness 化：把项目脚本 CLI 化、补验证 gate、文档分层。
- 更细粒度的 monorepo 局部规则治理。
- 更丰富的 eval 指标，如探索文件数、token 趋势和任务稳定性。

## License

MIT. Copyright (c) NieZhuZhu.
