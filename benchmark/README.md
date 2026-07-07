# ai-harness-doctor self-benchmark

## Methodology

This benchmark constructs two demo repositories with identical underlying reality: `repo-before/` and `repo-after/`. Their `package.json`, `.nvmrc`, and `src/` code are the same; only the agent-facing documentation layer differs.

- `repo-before/`: no `AGENTS.md`, and stale, conflicting `CLAUDE.md`, `.cursorrules`, and `.github/copilot-instructions.md` files are present.
- `repo-after/`: uses this skill's `scan.py` and `canonicalize.py --plan` to generate the checkup and merge plan, resolves conflicts manually against repository facts, writes a single-source-of-truth `AGENTS.md`, then uses `canonicalize.py --write-stubs --apply --force` to downgrade old tool files into pointer stubs.

This benchmark keeps repository reality identical and changes only agent-facing documentation. The before repo has stale or conflicting tool docs; the after repo has one canonical `AGENTS.md` plus stubs. Tasks are graded by regex against real `claude -p ... --output-format json` output.

The reported headline uses 14 objective tasks × 2 runs per side (28 task attempts per side). The second run is included to expose answer instability rather than to claim statistical confidence.

## Environment

- Runner: `claude -p {prompt} --output-format json`
- Claude CLI: `2.1.202 (Claude Code)`
- Captured model in result JSON: `claude-fable-5`
- Date: 2026-07-07

## Tasks and grading

Each prompt ends with `Answer with ONLY the exact command/value, no explanation.` Grading checks only whether runner stdout matches the regex. The `test` task additionally uses a negative lookahead so `test:unit` does not count as a false positive.

| id | Ground truth | Regex |
|---|---|---|
| `install` | `pnpm install` or `pnpm i` | `pnpm\s+install\|pnpm\s+i\b` |
| `test` | `pnpm test` or `pnpm run test`, without `test:unit` | `^(?![\s\S]*test:unit)[\s\S]*pnpm\s+(run\s+)?test\b` |
| `lint` | `pnpm lint` or `pnpm run lint` | `pnpm\s+(run\s+)?lint\b` |
| `node` | `20` | `\b20\b` |
| `framework` | `Vitest` | `(?i)vitest` |
| `components` | `src/components` | `src/components` |
| `commit` | `conventional commits` | `(?i)conventional` |
| `dev` | `pnpm dev` or `pnpm run dev` | `^pnpm\s+(run\s+)?dev\b` |
| `typecheck` | `pnpm typecheck`, `pnpm run typecheck`, or `tsc --noEmit` | `^(pnpm\s+(run\s+)?typecheck\b|tsc\s+--noEmit)$` |
| `coverage` | `pnpm coverage` or `pnpm run coverage`, not Jest | `^(?!.*jest)pnpm\s+(run\s+)?coverage\b` |
| `format` | `prettier` | `(?i)^prettier$` |
| `quotes` | `single` | `(?i)^single$` |
| `testloc` | colocated / next to component files / same directory | `(?i)^(?!.*__tests__).*?(colocat|next to|src/components.*\.test\.|same (directory|folder))` |
| `moduletype` | ESM / ES modules, not CommonJS | `(?i)^(?=.*(esm|es modules?))(?!.*commonjs).*` |

## Reproduce

```bash
python3 scripts/eval_run.py --tasks benchmark/tasks.json --label before --workdir benchmark/repo-before -o benchmark/results/results-before.json
python3 scripts/eval_run.py --tasks benchmark/tasks.json --label before-run2 --workdir benchmark/repo-before -o benchmark/results/results-before-run2.json
python3 scripts/eval_run.py --tasks benchmark/tasks.json --label after --workdir benchmark/repo-after -o benchmark/results/results-after.json
python3 scripts/eval_run.py --tasks benchmark/tasks.json --label after-run2 --workdir benchmark/repo-after -o benchmark/results/results-after-run2.json
python3 scripts/eval_run.py --compare benchmark/results/results-before.json benchmark/results/results-after.json -o benchmark/results/report.md
```

## Actual results

| Side | Runs | Passed | Flip-flop tasks | Avg duration/task | Total captured cost (USD) |
|---|---|---:|---:|---:|---:|
| before | `before` + `before-run2` | 4/28 | 2 | 16.041s | 5.820612 |
| after | `after` + `after-run2` | 16/28 | 0 | 11.651s | 4.810770 |
| delta | after - before | +12 tasks | -2 | -4.389s | -1.009842 |

- Headline: before 4/28 passed; after 16/28 passed; improvement +12 passing task attempts.
- Answer instability metric: before had 2 flip-flop tasks (`node, moduletype`); after had 0 flip-flop tasks.
- Single-run comparison in `results/report.md`: before 2/14 → after 8/14 for the first run pair.

See `results/results-before.json`, `results/results-before-run2.json`, `results/results-after.json`, `results/results-after-run2.json`, and `results/report.md` for details.

## Honest limitations

- Single demo repo; results may not generalize to larger or different repositories.
- Only N=2 runs per side; the repeated run is enough to reveal instability, not enough for confidence intervals.
- Small sample: 14 objective Q&A tasks, 28 task attempts per side.
- Results depend on the installed Claude Code CLI/model behavior at run time.
- The demo intentionally isolates documentation effects; it does not benchmark editing quality or multi-turn workflows.
- Regex grading is intentionally simple and may not capture all semantically equivalent answers.
