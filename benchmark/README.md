# ai-harness-doctor self-benchmark

## Methodology

This benchmark constructs two demo repositories with identical underlying reality: `repo-before/` and `repo-after/`. Their `package.json`, `.nvmrc`, and `src/` code are the same; only the agent-facing documentation layer differs.

- `repo-before/`: no `AGENTS.md`, and stale, conflicting `CLAUDE.md`, `.cursorrules`, and `.github/copilot-instructions.md` files are present.
- `repo-after/`: uses this skill's `scan.py` and `canonicalize.py --plan` to generate the checkup and merge plan, resolves conflicts manually against repository facts, writes a single-source-of-truth `AGENTS.md`, then uses `canonicalize.py --write-stubs --apply --force` to downgrade old tool files into pointer stubs.

This benchmark keeps repository reality identical and changes only agent-facing documentation. The before repo has stale or conflicting tool docs; the after repo has one canonical `AGENTS.md` plus stubs. Tasks are graded by regex against real `claude -p ... --output-format json` output.

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

## Reproduce

```bash
python3 scripts/eval_run.py --tasks benchmark/tasks.json --label before --workdir benchmark/repo-before -o benchmark/results/results-before.json
python3 scripts/eval_run.py --tasks benchmark/tasks.json --label after --workdir benchmark/repo-after -o benchmark/results/results-after.json
python3 scripts/eval_run.py --compare benchmark/results/results-before.json benchmark/results/results-after.json -o benchmark/results/report.md
```

## Actual results

- Before: 3/7 passed, average duration 20.206s, captured total cost USD 1.812925.
- After: 7/7 passed, average duration 11.393s, captured total cost USD 1.191250.
- Improvement: +4 passing tasks; the fixed tasks were install command, test command, test framework, and component directory.

See `results/results-before.json`, `results/results-after.json`, and `results/report.md` for details.

## Honest limitations

- Single run only; no repeated trials or confidence intervals.
- Small sample: 7 objective Q&A tasks.
- Results depend on the installed Claude Code CLI/model behavior at run time.
- The demo intentionally isolates documentation effects; it does not benchmark editing quality or multi-turn workflows.
- Regex grading is intentionally simple and may not capture all semantically equivalent answers.
