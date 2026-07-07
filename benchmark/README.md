# ai-harness-doctor self-benchmark

## 方法 / Methodology

本 benchmark 构造两个事实完全相同的 demo repo：`repo-before/` 与 `repo-after/`。二者的 `package.json`、`.nvmrc`、`src/` 代码一致；差异只在 agent 配置文档层。

- `repo-before/`：没有 `AGENTS.md`，同时存在过期且互相冲突的 `CLAUDE.md`、`.cursorrules`、`.github/copilot-instructions.md`。
- `repo-after/`：使用本 skill 的 `scan.py` 与 `canonicalize.py --plan` 生成体检与合并计划，人工按仓库事实裁决冲突，写入单一事实源 `AGENTS.md`，再用 `canonicalize.py --write-stubs --apply --force` 将旧工具文件降级为 pointer stub。

English brief: this benchmark keeps repo reality identical and changes only agent-facing documentation. The before repo has stale/conflicting tool docs; the after repo has one canonical `AGENTS.md` plus stubs. Tasks are graded by regex against real `claude -p ... --output-format json` output.

## 环境 / Environment

- Runner: `claude -p {prompt} --output-format json`
- Claude CLI: `2.1.202 (Claude Code)`
- Captured model in result JSON: `claude-fable-5`
- Date: 2026-07-07

## 任务与评分 / Tasks and grading

每个 prompt 都以 `Answer with ONLY the exact command/value, no explanation.` 结尾。评分只看 runner stdout 中是否匹配 regex；`test` 任务额外用 negative lookahead 防止 `test:unit` 被误判通过。

| id | Ground truth | Regex |
|---|---|---|
| `install` | `pnpm install` 或 `pnpm i` | `pnpm\s+install\|pnpm\s+i\b` |
| `test` | `pnpm test` 或 `pnpm run test`，不得包含 `test:unit` | `^(?![\s\S]*test:unit)[\s\S]*pnpm\s+(run\s+)?test\b` |
| `lint` | `pnpm lint` 或 `pnpm run lint` | `pnpm\s+(run\s+)?lint\b` |
| `node` | `20` | `\b20\b` |
| `framework` | `Vitest` | `(?i)vitest` |
| `components` | `src/components` | `src/components` |
| `commit` | `conventional commits` | `(?i)conventional` |

## 复现 / Reproduce

```bash
python3 scripts/eval_run.py --tasks benchmark/tasks.json --label before --workdir benchmark/repo-before -o benchmark/results/results-before.json
python3 scripts/eval_run.py --tasks benchmark/tasks.json --label after --workdir benchmark/repo-after -o benchmark/results/results-after.json
python3 scripts/eval_run.py --compare benchmark/results/results-before.json benchmark/results/results-after.json -o benchmark/results/report.md
```

## 实际结果 / Actual results

- Before: 3/7 passed, average duration 20.206s, captured total cost USD 1.812925.
- After: 7/7 passed, average duration 11.393s, captured total cost USD 1.191250.
- Improvement: +4 passing tasks; the fixed tasks were install command, test command, test framework, and component directory.

详见 `results/results-before.json`、`results/results-after.json` 与 `results/report.md`。

## 局限 / Honest limitations

- Single run only; no repeated trials or confidence intervals.
- Small sample: 7 objective Q&A tasks.
- Results depend on the installed Claude Code CLI/model behavior at run time.
- The demo intentionally isolates documentation effects; it does not benchmark editing quality or multi-turn workflows.
- Regex grading is intentionally simple and may not capture all semantically equivalent answers.

