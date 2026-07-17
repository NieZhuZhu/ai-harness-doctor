# Real-repo before/after eval: openai/codex (null result, published)

This is a Phase 3 efficacy experiment run against a real corpus repository instead
of the controlled demo pair in [`benchmark/`](../../../README.md). We publish it
even though the headline is a **null result**, because knowing where the effect
saturates is part of an honest efficacy story.

## Question

The [self-benchmark](../../../README.md) shows a large before/after effect
(6/28 → 28/28) when agent docs are wrong about *conventions and commands*. Does
fixing the milder defect class found across the [corpus](../../README.md) —
stale file-path references in an otherwise healthy `AGENTS.md` — produce a
measurable task-level improvement on a real repository?

## Design

- **Repository**: `openai/codex` at the corpus-pinned commit
  `315195492c80fdade38e917c18f9584efd599304`, the corpus repo with the most
  semantic mismatches (6 flagged; 4 genuinely stale paths + 2 scanner false
  positives, see below).
- **before**: a pristine copy of the pinned checkout (`.git` excluded).
- **after**: the same copy where the *only* change is fixing the 4 stale path
  references that `scan.py` flags in the root `AGENTS.md` — a 5-line diff
  (one declaration appears twice):

| `AGENTS.md` declared (before) | Fixed to (after) |
|---|---|
| `codex-rs/codex-mcp/src/mcp_connection_manager.rs` | `codex-rs/codex-mcp/src/connection_manager.rs` |
| `core/context` | `codex-rs/core/src/context` |
| `core/suite` | `codex-rs/core/tests/suite` |
| `app-server-protocol/src/protocol/v2.rs` (×2) | `codex-rs/app-server-protocol/src/protocol/v2/` |

  `scan.py` semantic mismatches drop from 6 to 2 after the treatment; the 2
  remaining flags (`thread/read`, `app/list`) are JSON-RPC method names
  misidentified as paths, so they were deliberately left untouched and excluded
  from task design. This eval also re-adjudicated why they still fire: the
  round-32 runtime-identifier classifier exempts such tokens only when the
  RPC/method cue sits inside its bounded 40-character same-line window, and on
  codex's real `AGENTS.md` line the cue is 54 characters away (the round-32
  regression test used an adjacent-cue paraphrase, not the upstream sentence).
  Logged as deferred in `EXTERNAL_VALIDATION.md` round 36.
- **Tasks** ([`tasks.json`](tasks.json)): 12 objective, regex-graded questions.
  4 *intervention* tasks target facts corrupted by the stale paths; 8 *control*
  tasks ask for commands the doc states correctly and identically on both sides
  (`just fmt`, `just test`, …), to detect any accidental sabotage of the before
  side. Every task's ground truth and regex was adversarially verified against
  the pinned checkout by 12 independent reviewer agents before any eval run;
  two regexes were tightened as a result (`just fmt-check` and `just bench-e2e`
  would otherwise have been wrongly accepted).
- **Runner**: `claude -p {prompt} --output-format json` executed inside each
  copy, 2 runs per side (24 task attempts per side), interleaved
  before → after → before → after to avoid time-of-day bias.

## Environment

- Claude CLI: `2.1.212 (Claude Code)`; captured model: `claude-fable-5`
- Date: 2026-07-17
- Total captured cost across all 48 runner invocations: 12.18 USD

## Results

| Side | Passed | Flip-flop tasks | Avg wall/task | Avg API/task | Total agent turns | Total captured cost |
|---|---:|---:|---:|---:|---:|---:|
| before | 24/24 | 0 | 52.0s | 28.8s | 72 | $6.16 |
| after | 24/24 | 0 | 54.9s | 26.9s | 74 | $6.01 |

Both sides answered every question correctly in both runs, including all 4
intervention tasks on the before side. Wall/API/turn/cost differences are
within single-run noise (the same task varied by up to 2.4× between runs on
the same side). See [`results/`](results/) for the raw per-task records.

## Interpretation: where the effect saturates

The before-side agent did not trust the stale paths — it verified against the
file tree (e.g. answering `codex-rs/codex-mcp/src/connection_manager.rs` in 3
turns where the doc claimed `mcp_connection_manager.rs`) and self-corrected at
the cost of, at most, an extra exploration turn. Combined with the self-benchmark,
this brackets the efficacy claim:

- **Effect is large** when docs are wrong about *conventions and commands* —
  facts an agent cannot cheaply derive from the code (package manager, node
  version, commit style: 6/28 → 28/28 in the controlled pair).
- **Effect saturates** when the docs are otherwise healthy and the defects are
  a few stale *path* references — facts a strong agent verifies against the
  filesystem in one turn anyway. codex's `AGENTS.md` documents its commands
  accurately (all 8 control tasks passed on both sides), so there was little
  left for the treatment to improve on this task style.

Two honest caveats cut in opposite directions:

- Q&A tasks are the *easiest* case for self-correction. Stale paths plausibly
  cost more in editing/navigation workflows (changes applied to a
  wrong-but-existing location), which regex grading cannot capture; this
  experiment does not measure that channel.
- The treatment fixed only the root `AGENTS.md` (the scanner's surface). The
  adversarial reviewers found the same stale paths repeated in
  `codex-rs/app-server/README.md`, `codex-rs/docs/codex_mcp_interface.md`, and
  `.codex/skills/code-review-context/SKILL.md` in the pinned checkout, so the
  after side still contained contradicting prose outside the treated file.

## Honest limitations

- One repository, one task style, N=2 runs per side; noise on per-task latency
  is larger than any before/after difference observed.
- The runner model (`claude-fable-5`) aggressively self-verifies; weaker or
  doc-trusting runners may show a real before/after gap that this setup cannot.
- Results depend on the installed Claude Code CLI/model behavior at run time.
- Grading is regex-based on the extracted answer text, as in the self-benchmark.

## Reproduce

```bash
# 1. Initialize the pinned submodule (see ../../README.md for the corpus workflow)
git submodule update --init --depth 1 benchmark/corpus/repos/codex

# 2. Build the two sides (outside the repo to keep scans clean)
rsync -a --exclude='.git' benchmark/corpus/repos/codex/ /tmp/codex-eval/before/
rsync -a /tmp/codex-eval/before/ /tmp/codex-eval/after/
# apply the 4 declared fixes from the table above to /tmp/codex-eval/after/AGENTS.md

# 3. Verify the treatment with the scanner (6 -> 2 semantic mismatches)
python3 scripts/scan.py /tmp/codex-eval/before   # 6 mismatches
python3 scripts/scan.py /tmp/codex-eval/after    # 2 mismatches (identifier FPs)

# 4. Run the eval (interleaved), then compare
python3 scripts/eval_run.py --tasks benchmark/corpus/evals/codex/tasks.json --label codex-before      --workdir /tmp/codex-eval/before -o results-before.json
python3 scripts/eval_run.py --tasks benchmark/corpus/evals/codex/tasks.json --label codex-after       --workdir /tmp/codex-eval/after  -o results-after.json
python3 scripts/eval_run.py --tasks benchmark/corpus/evals/codex/tasks.json --label codex-before-run2 --workdir /tmp/codex-eval/before -o results-before-run2.json
python3 scripts/eval_run.py --tasks benchmark/corpus/evals/codex/tasks.json --label codex-after-run2  --workdir /tmp/codex-eval/after  -o results-after-run2.json
python3 scripts/eval_run.py --compare results-before.json results-after.json -o report.md
```
