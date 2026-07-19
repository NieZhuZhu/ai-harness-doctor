# Phase 3 self-bootstrap — AGENTS.md efficacy eval

This directory dogfoods **Phase 3 (Efficacy)** on the `ai-harness-doctor` repo itself:
does *this repo's own* `AGENTS.md` actually steer an AI agent to correct answers?

## Methodology and evidence boundary

Because no `claude`/`codex` runner CLI is available in the eval environment, the harness
falls back to its documented **manual protocol** (`eval_run.py` prints it when the runner
binary is missing). An agent answers each task in `tasks.json` using **only** the contents
of `AGENTS.md` — no repo browsing — and the answers are graded offline by the tool's
regex regrader (`eval_run.py --regrade`) against repository ground truth.

The current Plan 067 maintenance-pack answers are **manually maintained by an AI
implementation workflow** directly from `AGENTS.md`. No `eval_run.py` runner or
judge model call was performed; the offline regex regrade is evidence-bounded,
**not an independent model benchmark**.

- `tasks.json` — 40 objective questions an agent would ask about this repo (build/test
  commands, language/runtime constraints, safety/release rules, installer/MCP policy,
  evidence freshness, repository operations, path truth, nested package facts,
  Action argv safety, the deep-improve loop, and where the core scripts live).
- `results-before.json` — answers from an agent given the **pre-fix** `AGENTS.md`.
- `results-after.json` — current Plan 067 manual-protocol answers maintained
  by AI implementation workflow from the current `AGENTS.md`; no `eval_run.py`
  runner or judge model call.
- `*-graded.json` — the same files after `--regrade` (adds `passed`/`answer`).
- `results-after-graded.json` additionally binds the exact `tasks.json` and
  `AGENTS.md` bytes through a deterministic evidence manifest. Task-declared
  fact sources join that manifest automatically; explicit evidence composes.
- `report.md` — the historical 12-task pre-fix vs post-fix comparison. The five
  newer maintenance-contract tasks have no historical before measurement and
  are deliberately not retrofitted into that claim.

The fingerprints prove that a stored result matches the current input bytes.
They do **not** prove that manually recorded answers came from a real model; the
manual-protocol label remains part of the result and this document.

## Reproduce

```bash
python3 scripts/eval_run.py --regrade benchmark/self-eval/results-after.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md -o benchmark/self-eval/results-after-graded.json
python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80
```

## Result

| | Pass rate |
|---|---|
| before (pre-fix `AGENTS.md`) | 9/12 |
| after (historical post-fix `AGENTS.md`) | 12/12 |
| current evidence-bound maintenance pack | 40/40 |

**Finding:** the three failures (`drift-script`, `scan-script`, `eval-script`) all shared one
root cause — `AGENTS.md` never named the four phase scripts (`scan.py`, `canonicalize.py`,
`check_drift.py`, `eval_run.py`) and had no directory-layout section, so an agent could not
locate the repo's core deliverables. This violated the skill's own decision rule ("stable
conventions: **project structure**, required commands …").

**Fix:** added a concise `# Project structure` section to `AGENTS.md` mapping each phase to its
script and listing the key directories. Closing that gap raised the pass rate to 12/12 while
keeping `AGENTS.md` small (progressive disclosure preserved). The drift guard stays green
(100/100, grade A) after the change.

The 2026-07-20 refresh covers objective checks for installer/guard transaction recovery,
unsuppressible HIGH security findings, MCP read-only/error semantics, semantic
release classification, isolated-HOME installer tests, eval evidence freshness,
MCP versioned wire contracts, and the public-repository operations baseline. Any change to
`AGENTS.md` or `tasks.json` now makes the self-bootstrap PR gate fail stale
evidence (exit 7) until the manual protocol is rerun and reviewed in the same
PR. The current maintenance pack also checks that public npm lockfile sources
use `registry.npmjs.org`, so GitHub-hosted Dependabot can resolve them, and that
nested instruction differences are classified as same-scope conflicts or
non-blocking ancestor-to-descendant overrides. It also checks the oversize-file
contract: `--max-bytes` bounds semantic text, while full-file identity, line
count, and high-confidence security coverage remain bounded-memory and explicit.
Release reruns are also checked: an existing npm version is skipped only after
its `gitHead` and packed tarball shasum match the exact release tag. Targeted
eval generation must preserve root IDs, isolate local scripts/dependencies, use
only nearest unambiguous inherited facts, and attach relative evidence. Root and
scoped eval plus Treat draft share one containment rule: external symlinks
supply no facts, contained symlinks keep lexical evidence, and ambiguity causes
abstention. Required lint CI is also pinned to `npm ci --ignore-scripts` over
the committed public npm lock, so the dependency graph under test is reviewed.
Generated-task evidence is executable provenance: files are byte-hashed,
directories bind existence/type only, and strict score re-derives those sources
from `tasks.json` before trusting health. The current pack also checks that task
schema validation happens before all eval side effects, weekly checkup issues
close on recovery without touching unrelated issues, and multi-repo scans report
all reachable repositories but exit 8 when any listed entry was not scanned.
It now also locks the post-v1.8.1 invariants: offline eval health is derived
from validated stored records rather than cached scores; Action tests cover
bundled scan/drift plus exact npm overrides before/after publish; and modeled
Claude/Cursor/Copilot globs may narrow automatic conflicts without turning
conditional/manual/invalid sources into effective guidance or recursive scan
discovery into recursive deletion or rewriting authority.
Destructive stub consolidation also preflights canonical readiness:
product-owned draft markers, unsafe paths, size, and required sections block
apply, while `--force` can accept only dirty-tree risk.
The newest checks bind three implementation invariants and their maintenance
workflow: repository-owned `.gitignore` truth is queried through synthetic Git
metadata and fails closed; nested D1/D2/D6 facts walk lexical ancestors without
sibling leakage while D7 remains file-relative; and `action-run.js` owns bounded
no-shell argv parsing while `action-report.js` remains the reporting authority.
They also require each deep-improve round to start from an independent
nine-category audit, land plan-only and implementation PRs behind all nine CI
contexts, verify Standards/Spec plus real evidence, squash/delete, close out the
plan in a green docs PR, and revalidate candidates instead of carrying them
forward unexamined.
The `local-all-green` task checks the local/CI parity invariant: the local
all-green `npm run check` runs lint, tests, then packed npm candidate
verification, while CI remains responsible for the Python 3.9–3.12 and
Node 16–22 matrix coverage.

The Plan 067 refresh extends the objective `secret-report-safety` task, binding
the root invariant that repository tooling must redact persisted or reported
credential values, including nested eval usage metadata. Its answer is
manually maintained from `AGENTS.md`; no
`eval_run.py` runner or judge model call was made, and the offline regex
regrade is not an independent model benchmark.

The Plan 061 refresh expands `doc-languages` to seven required locales
(English, zh-CN, ja, es, ko, pt-BR, fr) and adds a progressive-disclosure
budget + semantics contract test that keeps `AGENTS.md` under 10 240 bytes
while preserving root-level semantic invariants across both the expanded
parent wording and the compact final version.
