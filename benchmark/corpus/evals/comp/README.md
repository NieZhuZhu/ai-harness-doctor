# Real-repo before/after eval: trycompai/comp (positive result)

The boundary companion to the [codex null-result eval](../codex/README.md): the same
protocol, run against a repository whose harness defect sits in the channel the
[self-benchmark](../../../README.md) predicts matters — **agent docs that are wrong
about commands** — instead of stale file paths. Together the two evals bracket the
efficacy claim with real repositories on both sides.

## How this repository was selected (disease-targeted sampling)

Star-ranked corpora select for healthy docs: top-tier projects keep their command
documentation correct because humans use it daily. To find a real instance of the
harmful defect class we inverted the sampling — selecting by *symptom*:

1. GitHub code search for repositories containing `.cursorrules` files that mention
   package managers or test tooling (7 query slices, 948 unique repositories).
2. GraphQL batch triage: keep active, non-fork repos that also carry `AGENTS.md` or
   `CLAUDE.md` (247 remained; 27 at ≥200 stars).
3. One deterministic `scan.py --repos-file` batch over shallow clones of those 27:
   12 repos surfaced command-class conflicts.
4. Lockfile adjudication of every flagged repo: most were multi-stack evidence or
   prose false positives; two were genuinely wrong docs. `trycompai/comp` was chosen
   because its wrong claims live in `CLAUDE.md` — the file the eval runner (Claude
   Code) actually reads — whereas `selfxyz/self`'s wrong claims live in
   `.cursorrules`, which this runner never loads.

## The disease

`trycompai/comp` (Comp AI, ~1.7k stars, actively developed compliance-automation
platform) at clone commit `b04358de0850e61c3ee45c40b8905a14d2307f96`:

- Root `bun.lock` and `"packageManager": "bun@1.3.4"` — the repository runs on bun.
- `AGENTS.md` and `CLAUDE.md` overlap 95.8% (a forked near-duplicate pair) but have
  **diverged in both directions**:
  - `CLAUDE.md` still tells agents `npx vitest run`, `npx jest`, and
    `npx turbo run typecheck --filter=@trycompai/api`; `AGENTS.md` was updated to
    `bunx` for all three.
  - `AGENTS.md` carries an 18-line API endpoint contract section absent from
    `CLAUDE.md`; `CLAUDE.md` carries a mandatory responsive-design rule absent from
    `AGENTS.md`. Neither file is a superset.
- The root `.cursorrules` directs readers to `CLAUDE.md` — the stale side — "for
  comprehensive project rules".
- 19 harness config files in total (15 `.cursor/rules/*.mdc`, `.cursorrules`, the
  root pair, and a nested `apps/api/CLAUDE.md`).

`scan.py` surfaced the pair via the 95.8% overlap cluster and a `test_command`
conflict whose citations point at exactly the divergent line in each file; the
bun-vs-npx wrongness was then adjudicated against the lockfile.

## Treatment

The tool's actual Phase 1 flow, applied to the root pair only:

1. `canonicalize.py --plan` (inventory, overlap cluster, conflict list).
2. Conflict resolution against repository facts: `bunx` wins (lockfile +
   `packageManager`); the responsive-design rule is merged into `AGENTS.md` so it
   becomes a true superset; canonical `Project overview` / `Build & test` /
   `Conventions` headings mapped onto the existing structure.
3. `canonicalize.py --write-stubs --tools claude --apply --force` downgrades
   `CLAUDE.md` to an `@AGENTS.md` import stub. (The tool's readiness gate refused
   the stub until step 2 made `AGENTS.md` canonical — the fail-closed design
   working as documented.)

Post-treatment scan: overlap cluster gone (1 → 0); the remaining `test_command`
conflict value (vitest vs jest) is legitimate multi-stack evidence (the app tests
with vitest, the API with jest). `.cursor/rules/*`, `.cursorrules`, and the nested
`apps/api/CLAUDE.md` were deliberately left untouched.

## Tasks

12 objective regex-graded tasks ([`tasks.json`](tasks.json)): 3 *conflict* tasks
targeting the commands `CLAUDE.md` states incorrectly, 9 *controls* covering facts
that are identical (and correct) in both conditions — including facts documented
only in `AGENTS.md`, only in `CLAUDE.md`, or in both. Every task's ground truth and
regex was adversarially verified against the pinned clone by 12 independent
reviewer agents before any paid run; 8 regexes were tightened or relaxed as a
result (e.g. `\b375\b` failed on the doc's own `375px` phrasing; `bun run test\b`
wrongly accepted `test:watch`).

Runner: `claude -p {prompt} --output-format json` (CLI `2.1.212 (Claude Code)`,
captured model `claude-fable-5`), 2 runs per side, interleaved
before → after → before → after. Date: 2026-07-17. Total captured cost: 9.87 USD.

## Results

| Side | Passed | Flip-flop tasks | Avg wall/task | Avg API/task | Total agent turns | Total captured cost |
|---|---:|---:|---:|---:|---:|---:|
| before | 18/24 | 0 | 15.7s | 8.3s | 44 | $5.45 |
| after | 24/24 | 0 | 9.9s | 5.2s | 24 | $4.42 |

The 3 conflict tasks failed **deterministically** on the before side — both runs,
same wrong answer, verbatim from `CLAUDE.md`:

| Task | before answer (both runs) | after answer (both runs) |
|---|---|---|
| `app-tests` | `cd apps/app && npx vitest run` | `bunx vitest run` variants ✓ |
| `api-tests` | `cd apps/api && npx jest src/<module> --passWithNoTests` | `bunx jest` variants ✓ |
| `typecheck-api` | `npx turbo run typecheck --filter=@trycompai/api` | `bunx turbo …` ✓ |

All 9 control tasks passed on both sides.

## Interpretation

- **The predicted failure mechanism is real and deterministic.** The runner did not
  explore or verify: it read `CLAUDE.md`, trusted it, and confidently echoed the
  stale command — identically in both runs. Contrast with the
  [codex eval](../codex/README.md), where stale *path* references were self-healed
  by a one-turn filesystem check: a wrong *command convention* is not cheaply
  verifiable in a Q&A setting, so the doc is the ground truth the agent uses.
- **Empirical file-precedence finding**: with both files present, this runner
  answered from `CLAUDE.md`, not `AGENTS.md` — so which of your N divergent config
  files is "the wrong one" depends on which tool is asked. Any of the 19 config
  files being stale poisons exactly the agents that read it.
- **Latency/turn effects now point the expected way**: −37% wall time, −45% agent
  turns, −19% cost. With a single canonical source the agent stopped reconciling
  two 150+-line near-duplicates on every question.
- Bracketed together: codex (healthy docs, stale paths) → no measurable effect;
  comp (wrong command docs) → +6/24 correctness, −37% latency from one treatment
  run. The tool's value concentrates exactly where its scan output says it should.

## Honest limitations

- One repository, N=2 runs per side, 12 tasks; the conflict channel is only 3
  tasks wide. The determinism of the failures (identical wrong answer, both runs)
  is the strongest signal, not the aggregate counts.
- The runner reads `CLAUDE.md` preferentially; a runner that read `AGENTS.md`
  first would have answered the 3 conflict tasks correctly on the before side
  (and would instead be exposed to the missing responsive-design rule). The
  measured delta is runner-dependent by construction.
- `bunx`-vs-`npx` wrongness is convention-level: `npx` may execute the same local
  binary in many setups. The grading follows the repository's own declared
  convention (`packageManager: bun`, its docs' explicit "never npm/yarn/pnpm").
- Q&A tasks still do not measure editing/navigation workflows.
- This clone is not a corpus submodule; reproduction pins the commit via
  `git clone` + `git checkout b04358de0850e61c3ee45c40b8905a14d2307f96`.

## Reproduce

```bash
# 1. Pin the clone
git clone https://github.com/trycompai/comp.git /tmp/comp-eval/src
git -C /tmp/comp-eval/src checkout b04358de0850e61c3ee45c40b8905a14d2307f96

# 2. Build the two sides
rsync -a --exclude='.git' /tmp/comp-eval/src/ /tmp/comp-eval/before/
rsync -a /tmp/comp-eval/before/ /tmp/comp-eval/after/

# 3. Treat the after side with the real Phase 1 flow (see Treatment above)
python3 scripts/canonicalize.py /tmp/comp-eval/after --plan
#   …resolve conflicts to bunx, merge the responsive rule, map canonical headings…
python3 scripts/canonicalize.py /tmp/comp-eval/after --write-stubs --tools claude --apply --force

# 4. Run the eval (interleaved), then compare
python3 scripts/eval_run.py --tasks benchmark/corpus/evals/comp/tasks.json --label comp-before      --workdir /tmp/comp-eval/before -o results-before.json
python3 scripts/eval_run.py --tasks benchmark/corpus/evals/comp/tasks.json --label comp-after       --workdir /tmp/comp-eval/after  -o results-after.json
python3 scripts/eval_run.py --tasks benchmark/corpus/evals/comp/tasks.json --label comp-before-run2 --workdir /tmp/comp-eval/before -o results-before-run2.json
python3 scripts/eval_run.py --tasks benchmark/corpus/evals/comp/tasks.json --label comp-after-run2  --workdir /tmp/comp-eval/after  -o results-after-run2.json
python3 scripts/eval_run.py --compare results-before.json results-after.json -o report.md
```
