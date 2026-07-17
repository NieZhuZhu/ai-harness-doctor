# ai-harness-doctor self-benchmark

## Methodology

This benchmark constructs two demo repositories with identical underlying reality: `repo-before/` and `repo-after/`. Their `package.json`, `.nvmrc`, and `src/` code are the same; only the agent-facing documentation layer differs.

- `repo-before/`: no `AGENTS.md`, and stale, conflicting `CLAUDE.md`, `.cursorrules`, and `.github/copilot-instructions.md` files are present.
- `repo-after/`: uses this skill's `scan.py` and `canonicalize.py --plan` to generate the checkup and merge plan, resolves conflicts manually against repository facts, writes a single-source-of-truth `AGENTS.md`, then uses `canonicalize.py --write-stubs --apply --force` to downgrade old tool files into pointer stubs.

This benchmark keeps repository reality identical and changes only agent-facing documentation. The before repo has stale or conflicting tool docs; the after repo has one canonical `AGENTS.md` plus stubs. Tasks are graded by regex against the extracted answer text from real `claude -p ... --output-format json` output.

The reported headline uses 14 objective tasks × 2 runs per side (28 task attempts per side). The second run is included to expose answer instability rather than to claim statistical confidence.

## Environment

- Runner: `claude -p {prompt} --output-format json`
- Claude CLI: `2.1.202 (Claude Code)`
- Captured model in result JSON: `claude-fable-5`
- Date: 2026-07-07

## Tasks and grading

Each prompt ends with `Answer with ONLY the exact command/value, no explanation.` Grading extracts the Claude runner JSON envelope's `result` field when present, strips surrounding whitespace/backticks, then checks only whether that normalized answer text matches the regex. The `test` task additionally uses a negative lookahead so `test:unit` does not count as a false positive.

| id | Ground truth | Regex |
|---|---|---|
| `install` | `pnpm install` or `pnpm i` | `pnpm\s+install\|pnpm\s+i\b` |
| `test` | `pnpm test` or `pnpm run test`, without `test:unit` | `^(?![\s\S]*test:unit)[\s\S]*pnpm\s+(run\s+)?test\b` |
| `lint` | `pnpm lint` or `pnpm run lint` | `pnpm\s+(run\s+)?lint\b` |
| `node` | `20` | `\b20\b` |
| `framework` | `Vitest` | `(?i)vitest` |
| `components` | `src/components` | `src/components` |
| `commit` | `conventional commits` | `(?i)conventional` |
| `dev` | `pnpm dev` or `pnpm run dev` | `pnpm\s+(run\s+)?dev\b` |
| `typecheck` | `pnpm typecheck`, `pnpm run typecheck`, or `tsc --noEmit` | `pnpm\s+(run\s+)?typecheck\b\|tsc\s+--noEmit` |
| `coverage` | `pnpm coverage` or `pnpm run coverage` | `pnpm\s+(run\s+)?coverage\b` |
| `format` | `prettier` | `(?i)prettier` |
| `quotes` | `single` / `singleQuote` | `(?i)\bsingle\b\|singleQuote` |
| `testloc` | colocated / next to component files / `.test.tsx?`, not `__tests__` | `(?i)^(?!.*__tests__).*(colocat\|next to (the )?(source\|component)\|\.test\.tsx?)` |
| `moduletype` | ESM / ES modules / `"type": "module"` | `(?i)(\besm\b\|es modules?\|"type":\s*"module")` |

## Grading methodology note

Answers are extracted from the runner JSON envelope and normalized before regex grading. The harness initially graded raw envelopes, which meant anchored checks could fail even when the recorded model answer was correct. We caught this by dogfooding the benchmark and fixed it by offline regrading the same recorded model outputs; no Claude reruns were used for the regraded numbers below.

## Reproduce

```bash
python3 scripts/eval_run.py --tasks benchmark/tasks.json --label before --workdir benchmark/repo-before -o benchmark/results/results-before.json
python3 scripts/eval_run.py --tasks benchmark/tasks.json --label before-run2 --workdir benchmark/repo-before -o benchmark/results/results-before-run2.json
python3 scripts/eval_run.py --tasks benchmark/tasks.json --label after --workdir benchmark/repo-after -o benchmark/results/results-after.json
python3 scripts/eval_run.py --tasks benchmark/tasks.json --label after-run2 --workdir benchmark/repo-after -o benchmark/results/results-after-run2.json
python3 scripts/eval_run.py --compare benchmark/results/results-before.json benchmark/results/results-after.json -o benchmark/results/report.md
```

## Multi-agent matrix and judge (methodology note)

The eval harness now also supports running the same task set across several runners ("agents") in one pass and grading open-ended answers with an LLM-as-judge check. This is a methodology extension only — the headline numbers below are still the single-runner before/after comparison and are **not** regenerated with these modes.

- **Matrix mode**: `eval_run.py --matrix agents.json` (or repeatable `--runner-cmd NAME=CMD`) runs each task against every agent and emits a Markdown matrix (`--matrix-report`) and JSON (`--matrix-json`) with a per-agent `summary` (`passed`, `total`, `pass_rate`). It lets a repo compare, e.g., `claude` vs `codex` on the same before/after documentation without changing the tasks or grading.
- **Judge check**: a task check of `type: "judge"` delegates grading to `--judge-cmd`, which returns `{"passed", "score", "reason"}`. This is intended for semantically-graded prompts that regex cannot capture; it does not replace the objective regex tasks used for the headline results.

To keep the reported numbers reproducible and honest, the tables in this file continue to use the objective regex tasks and the single `claude -p` runner described above; matrix/judge results, if run, should be reported separately with their own runner and judge configuration.

## Multi-repo corpus (breadth companion)

This before/after benchmark proves the efficacy story in depth on one controlled repo
pair. Its breadth companion lives in [`corpus/`](corpus/README.md): 14 well-known
open-source repositories (react, vscode, n8n, ollama, transformers, dify, supabase,
gemini-cli, codex, home-assistant, zed, elasticsearch, cline, ghostty) pinned as shallow
git submodules and scanned in one deterministic `scan.py --repos-file` batch. The corpus
measures the Phase-0 checkup against real, diverse harness surfaces at exact commits; it
involves no agent calls and does not change the headline numbers below.

## Real-repo evals (boundary companions)

Two real repositories have been put through this same before/after protocol, chosen to
sit on opposite sides of the efficacy boundary:

- **openai/codex** ([`corpus/evals/codex/`](corpus/evals/codex/README.md)) — healthy
  command docs, 4 stale *path* references fixed. Honestly published **null result**
  (24/24 vs 24/24): a strong self-verifying runner heals stale paths on its own.
- **trycompai/comp** ([`corpus/evals/comp/`](corpus/evals/comp/README.md)) — a bun
  monorepo whose `CLAUDE.md` forked from `AGENTS.md` and still teaches stale `npx`
  commands; found by disease-targeted sampling of 948 `.cursorrules` repositories.
  **Positive result**: one Phase-1 treatment run (resolve conflicts against the
  lockfile, merge to a single canonical `AGENTS.md`, stub `CLAUDE.md`) took the runner
  from 18/24 to 24/24, with the 3 conflict tasks failing *deterministically* before —
  the agent echoed the stale doc verbatim in both runs — and −37% wall time, −45%
  agent turns, −19% cost after.

Together they locate the boundary: wrong *convention/command* docs cause large,
deterministic harm that treatment removes; stale *path* references in otherwise-healthy
docs are self-healed by a strong agent. The controlled pair below remains the headline
efficacy benchmark; the real-repo evals are its external validity check.

## Actual results

| Side | Runs | Passed | Flip-flop tasks | Avg duration/task | Total captured cost (USD) |
|---|---|---:|---:|---:|---:|
| before | `before` + `before-run2` | 6/28 | 2 | 16.041s | 5.820612 |
| after | `after` + `after-run2` | 28/28 | 0 | 11.651s | 4.810770 |
| delta | after - before | +22 tasks | -2 | -4.389s | -1.009842 |

- Headline: before 6/28 passed; after 28/28 passed; improvement +22 passing task attempts.
- Answer instability metric: before had 2 flip-flop tasks (`node, moduletype`); after had 0 flip-flop tasks.
- Single-run comparison in `results/report.md`: before 3/14 → after 14/14 for the first run pair.

See `results/results-before.json`, `results/results-before-run2.json`, `results/results-after.json`, `results/results-after-run2.json`, and `results/report.md` for details.

## Honest limitations

- Single demo repo; results may not generalize to larger or different repositories.
- Only N=2 runs per side; the repeated run is enough to reveal instability, not enough for confidence intervals.
- Small sample: 14 objective Q&A tasks, 28 task attempts per side.
- Results depend on the installed Claude Code CLI/model behavior at run time.
- The demo intentionally isolates documentation effects; it does not benchmark editing quality or multi-turn workflows.
- Regex grading is intentionally simple and may not capture all semantically equivalent answers.
