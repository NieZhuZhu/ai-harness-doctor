# 阶段 3 疗效验证对比报告

Before label: `before`  
After label: `after`  
Runner: `claude -p {prompt} --output-format json`  
Claude CLI: `2.1.202 (Claude Code)`  
Captured model: `claude-fable-5`

## Headline

Pass rate: **3/7 → 7/7**（+4 tasks）。平均耗时：**20.206s → 11.393s**。JSON 中捕获总成本：**$1.812925 → $1.191250**。

## Per-task results

| Task | Ground truth | Before answer | Before | After answer | After | Duration before/after (s) | Cost before/after |
|---|---|---|---:|---|---:|---:|---:|
| `install` | `pnpm install` | `` `npm install` `` | ❌ | `` `pnpm install` `` | ✅ | 16.058 / 12.530 | 0.224460 / 0.220700 |
| `test` | `pnpm test` | `npm run test:unit` | ❌ | `pnpm test` | ✅ | 14.334 / 11.682 | 0.162670 / 0.161310 |
| `lint` | `pnpm lint` | `` `pnpm lint` `` | ✅ | `pnpm lint` | ✅ | 30.281 / 9.815 | 0.365959 / 0.160340 |
| `node` | `20` | `20` | ✅ | `20` | ✅ | 31.054 / 11.931 | 0.379101 / 0.162530 |
| `framework` | `Vitest` | `Jest` | ❌ | `Vitest` | ✅ | 10.440 / 10.036 | 0.162530 / 0.162670 |
| `components` | `src/components` | `src/ui/` | ❌ | `src/components/` | ✅ | 9.978 / 11.959 | 0.160000 / 0.160390 |
| `commit` | `conventional commits` | `Conventional Commits` | ✅ | `conventional commits` | ✅ | 29.296 / 11.796 | 0.358205 / 0.163310 |

## Notes

- No task timed out; no retry was needed.
- The before run unexpectedly answered `node` and `commit` correctly despite stale docs. This is kept as honest data.
- `lint` was correct before because `.cursorrules` already contained `pnpm lint`.
- Full raw JSON, including usage, is committed in `results-before.json` and `results-after.json`.
