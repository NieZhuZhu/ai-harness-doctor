# External validation log

Real-world spot checks: run `ai-harness-doctor scan` (dev checkout, not just the
published npm package) against popular open-source repos with known AI-authored
contributions, and see whether it holds up outside our own fixtures and
benchmark demo repo. This is read-only against the target repo — nothing is
ever written back to it. Findings that reveal a real bug, false positive, or
missing coverage in this tool get fixed here, with their own PR and (once
merged) a patch release; findings that are just "this repo doesn't have
AGENTS.md yet" are not actionable and are logged as clean runs.

| # | Repo | Date | Why this repo | Result | Fix (if any) |
|---|------|------|----------------|--------|---------------|
| 1 | [continuedev/continue](https://github.com/continuedev/continue) | 2026-07-12 | Popular AI coding agent, dogfoods its own `.continue/rules/*.md` config format (adapter added in v0.10.0) and has a nested `extensions/cli/AGENTS.md` | 1 HIGH false positive found and fixed (see below); G1/G4 gaps and the package_manager/test_command conflicts are correct, expected behavior for a repo that hasn't adopted a canonical root AGENTS.md yet | [#74](https://github.com/NieZhuZhu/ai-harness-doctor/pull/74) → v0.11.1 |
| 2 | [Aider-AI/aider](https://github.com/Aider-AI/aider) | 2026-07-12 | Well-known AI pair-programming CLI, popular, publicly known for using itself to write a large share of its own commits | Clean — no recognized agent config file at all (no `CLAUDE.md`/`AGENTS.md`/`.cursorrules`/etc.), only the standard G1/G4 "not adopted yet" gaps. Nothing to fix; this tool has no bespoke-instruction-file format ai-harness-doctor would be expected to recognize. | — |
| 3 | [vercel/ai](https://github.com/vercel/ai) | 2026-07-12 | Popular AI SDK, has a real root `AGENTS.md` + `CLAUDE.md` + a nested `packages/ai/AGENTS.md`, pnpm workspace monorepo | 3 false positives found and fixed (see below): 2 in the semantic engine, 1 in package-manager conflict detection | [#75](https://github.com/NieZhuZhu/ai-harness-doctor/pull/75) → v0.11.2 |
| 4 | [simonw/llm](https://github.com/simonw/llm) | 2026-07-12 | Popular Python LLM CLI/library, actively AI-assisted development, has a real (if minimal) root `AGENTS.md` | Clean — real `AGENTS.md` exists but only has two H2 sections ("Setting up a development environment", "Building the documentation"), neither matching our template's 6 canonical section names, so all 6 are correctly reported missing (G2). Verified no other agent-config files exist that we're failing to detect. Not a bug: this is the tool accurately reporting a real repo that hasn't adopted the canonical template, exactly like G1/G4. | — |
| 5 | [anthropics/claude-agent-sdk-python](https://github.com/anthropics/claude-agent-sdk-python) | 2026-07-12 | Official Claude Agent SDK, small/clonable, real `CLAUDE.md` with genuine command/path content | Clean — only `CLAUDE.md` exists (no root `AGENTS.md`), correctly flagged G1. Zero conflicts/security/semantic findings; `block/goose` and `sst/opencode` were tried first but both timed out cloning (large Go/Rust monorepos) — noting so a future round doesn't repeat the same timeout blindly. | — |
| 6 | [better-auth/better-auth](https://github.com/better-auth/better-auth) | 2026-07-12 | Popular TS auth library, real root `AGENTS.md` + `CLAUDE.md`, unusually explicit/directive writing style ("ALWAYS use X", "NEVER run Y") | 3 false positives found (see below); one deliberately deferred (indent_style "tabs for code, 2 spaces for JSON" — both values are simultaneously true for different file types, which needs real per-file-type scoping to fix correctly, not a quick regex; logging it rather than rushing a narrow heuristic) | [#76](https://github.com/NieZhuZhu/ai-harness-doctor/pull/76) → v0.11.3 |
| 7 | [charmbracelet/crush](https://github.com/charmbracelet/crush) | 2026-07-12 | Popular Go-based terminal AI coding agent, real root `AGENTS.md` + 2 nested `AGENTS.md` | 1 false positive found and fixed (Go import/module paths misread as filesystem paths); also confirmed 2 **real** findings are genuine repo drift, not a tool bug — see below | [#77](https://github.com/NieZhuZhu/ai-harness-doctor/pull/77) → v0.11.4 |
| 8 | [pydantic/pydantic-ai](https://github.com/pydantic/pydantic-ai) | 2026-07-13 | Popular Python provider-agnostic agent framework; real root `AGENTS.md` + a full `CLAUDE.md` duplicate + `.claude/settings.json` permission allow-list + ten nested `*/AGENTS.md`. First round to run the **full four-stage chain** (scan → treat → check_drift → eval), not just `scan`. | 2 false positives found and fixed (see below): 1 in the Phase-0 security permission audit (19 spurious HIGH findings), 1 in the Phase-2 D3 stub-regrowth drift gate (a full-duplicate config wrongly reported as a regrown stub) | [#79](https://github.com/NieZhuZhu/ai-harness-doctor/pull/79) → v0.12.0 |
| 9 | [mastra-ai/mastra](https://github.com/mastra-ai/mastra) | 2026-07-13 | Large TS pnpm-workspace monorepo AI framework, real root `AGENTS.md` + nested package configs + a `.claude/skills/` tree; picked to stress the monorepo-aware scan + drift on a big multi-package tree | Clean — scan 0 security findings, drift 100/grade A, 0 conflicts. Monorepo command/path signals all resolved correctly. Nothing to fix. | — |
| 10 | [crewAIInc/crewAI](https://github.com/crewAIInc/crewAI) | 2026-07-13 | Popular Python multi-agent framework, real root `AGENTS.md`; Python/uv stack cross-check | Clean — scan 0 security findings, drift 100/grade A, 0 conflicts/semantic mismatches. Accurately reports a healthy canonical config. Nothing to fix. | — |
| 11 | [All-Hands-AI/OpenHands](https://github.com/All-Hands-AI/OpenHands) | 2026-07-14 | Popular Python+TS AI software-engineer agent, large 28 KB root `AGENTS.md` with many backtick-quoted paths across frontend/backend; ran the **full four-stage chain** (scan → treat → check_drift → eval) | 1 false positive found and fixed (see below): a gitignored runtime `.env` path (`frontend/.env`) reported as a MISSING path in the Phase-0 semantic scan and the Phase-2 D2 drift gate. The remaining 12 path findings are **genuine drift** in OpenHands' own `AGENTS.md` (files renamed/moved during the V1 restructuring, e.g. `action-type.ts`→`action-type.tsx`, `openhands/cli/utils.py` gone) plus paths explicitly attributed to a separate `software-agent-sdk` repo — the tool correctly doing its job, verified by direct filesystem search | [#97](https://github.com/NieZhuZhu/ai-harness-doctor/pull/97) → v0.15.2 |
| 12 | [BerriAI/litellm](https://github.com/BerriAI/litellm) | 2026-07-14 | Popular Python LLM proxy/SDK, unusually rich harness surface: root `AGENTS.md` + `CLAUDE.md` + `GEMINI.md` + a nested Rust workspace (`litellm-rust/**/AGENTS.md`,`CLAUDE.md`) + a JS dashboard (`ui/litellm-dashboard/**`) | Clean — scan 0 security findings, drift 100/grade A. The 3 reported conflicts (`package_manager` cargo↔npm, `test_command` cargo↔pytest, `formatter` eslint↔prettier) are **legitimate multi-stack evidence**, not false positives: this repo genuinely spans a Python proxy, a Rust workspace, and a JS dashboard, and the file:line citations point a human at exactly why (same category as round 1's continuedev multi-stack conflicts). Nothing to fix. | — |
| 13 | [openai/openai-agents-python](https://github.com/openai/openai-agents-python) | 2026-07-14 | Official OpenAI Agents SDK for Python, real root `AGENTS.md` + a `CLAUDE.md` duplicate; Python/uv stack cross-check with 47 semantic checks | Clean — scan 0 security findings, 0 semantic mismatches across 47 checks, drift 95/grade A. The single `D4 NOTICE` (17.9 KB `AGENTS.md` context bloat) is a legitimate, non-failing observation. Nothing to fix. | — |

| 14 | [openai/codex](https://github.com/openai/codex) | 2026-07-14 | Popular Rust-based AI coding agent (the reference `codex` CLI); large 22 KB root `AGENTS.md` explicitly scoped to the `codex-rs/` Rust workspace, plus a nested `codex-rs/tui/.../AGENTS.md` | 5 false positives found and fixed (subdirectory-scoped paths resolved only against the repo root — see below); the remaining findings are correct (`mcp_connection_manager.rs` is genuine drift after a file rename; `thread/read`/`app/list` are RPC-method examples, a separate class left unfixed) | [#96](https://github.com/NieZhuZhu/ai-harness-doctor/pull/96) → v0.15.3 |
| 15 | [sst/opencode](https://github.com/sst/opencode) | 2026-07-14 | Popular TS AI coding agent; large workspace with a root `AGENTS.md` + 9 nested `packages/*/AGENTS.md`. Previously timed out cloning (round 5); revisited on a full local checkout | 2 false positives found and fixed (same subdirectory-scoped path root cause — `src/config`, `src/system-context` live under `packages/*`). Same fix/PR as round 14. | [#96](https://github.com/NieZhuZhu/ai-harness-doctor/pull/96) → v0.15.3 |
| 16 | [google-gemini/gemini-cli](https://github.com/google-gemini/gemini-cli) | 2026-07-15 | Official Gemini CLI; real root `AGENTS.md`/`GEMINI.md` on a modern TS stack that declares the standard ESLint+Prettier toolchain | 1 false positive found and fixed (see below): the complementary ESLint+Prettier pair was reported as a `formatter` conflict. | [#125](https://github.com/NieZhuZhu/ai-harness-doctor/pull/125) → v1.1.2 |
| 16 | [block/goose](https://github.com/block/goose) | 2026-07-15 | Popular Rust/TS AI agent; large workspace previously timed out cloning (rounds 1/5), revisited on a full local checkout; its docs declare both ESLint and Prettier | Same ESLint+Prettier `formatter` false positive as gemini-cli — confirms the class reproduces across repos. Same fix/PR as gemini-cli. | [#125](https://github.com/NieZhuZhu/ai-harness-doctor/pull/125) → v1.1.2 |
| 16 | [cline/cline](https://github.com/cline/cline) | 2026-07-15 | Popular VS Code AI coding agent; root `AGENTS.md` uses existence-negation prose ("There are no per-package npm lockfiles") while genuinely declaring pnpm | 1 false positive found and fixed (see below): the existence-negated `npm` was extracted as a declared `package_manager`, manufacturing a false npm↔pnpm conflict. | [#125](https://github.com/NieZhuZhu/ai-harness-doctor/pull/125) → v1.1.2 |
| 17 | [mastra-ai/mastra](https://github.com/mastra-ai/mastra) | 2026-07-15 | Revisited the 26k-star TS pnpm monorepo at `9fcb1db9`, now with 21 canonical AGENTS scopes, to validate nearest-file conflict semantics against current real instructions | Read-only dev `scan --json --fail-on-conflicts`: the former cross-root/package `test_command` conflict became 10 non-blocking scope overrides; two genuine same-scope `pnpm test`↔`vitest` conflicts remain in `mastracode` and `packages/memory` and correctly keep exit 7. Target `git status` was byte-identical before/after. Scan only; no Treat/Drift/Eval claim. | This PR |
| 18 | [mastra-ai/mastra](https://github.com/mastra-ai/mastra) | 2026-07-15 | Revisited at `bd2f1d27` with 20 nested `AGENTS.md` files to validate Phase 2's new nested command/path/fact/link coverage and attributed SARIF | Read-only dev `drift --json` + `--sarif`: the first implementation surfaced 7 false positives (root-scoped commands/paths, pnpm binary/option syntax, generated output, and an ESLint rule id). After local-first + root-fallback scope resolution and shared parser corrections, both modes returned 0 findings, 100/grade A, and 0 SARIF results. Target `git status` hash stayed byte-identical before/after. Drift only; no Scan/Treat/Eval claim. | This PR |
| 19 | [mastra-ai/mastra](https://github.com/mastra-ai/mastra) | 2026-07-15 | Reused `bd2f1d27` and its 21 canonical scopes to validate target-path `explain` against the existing Phase 0 scope model | Read-only dev CLI on `packages/memory/src/index.ts`, sibling `packages/core/src/index.ts`, and future `packages/playground/src/future-explain.ts`: each root→nearest chain, relevant overrides, and same-scope conflicts matched filtered `scan --json --no-monorepo` records exactly. Existing/future targets resolved correctly, repeated JSON was deterministic, and the target `git status` hash stayed byte-identical. Scan + Explain only; no Treat/Drift/Eval claim. | This PR |
| 20 | [VRSEN/agency-swarm](https://github.com/VRSEN/agency-swarm) | 2026-07-15 | Real 41,093-byte root `AGENTS.md` at `4fb6452e`, selected to validate oversize evidence instead of relying only on a synthetic tail fixture | Read-only dev `scan --json --no-monorepo` reported the complete 41,093 bytes, 500 lines, full-file SHA prefix `bf10a627cba7`, `analyzed_bytes=32768`, `truncated=true`, and `security_scanned_bytes=41093`; `analysis_limits` named conflict/overlap/override/semantic as prefix-bounded, security was clean, and the target `git status` hash stayed byte-identical. This validates evidence coverage, not a claim that the unseen semantic tail has no conflicts. | This PR |
| 21 | [mastra-ai/mastra](https://github.com/mastra-ai/mastra) | 2026-07-15 | Current 21-scope pnpm monorepo at `67879dd0`, selected to validate explicit target-aware eval generation and bounded task volume | Read-only dev generation produced 9 legacy root tasks, 11 `packages/memory` tasks, and 12 `packages/core` tasks. Scoped IDs were disjoint (`scope:packages%2F...`), each task selected only its package scripts/dependencies, and inherited pnpm/Node facts named only root `package.json` / `pnpm-lock.yaml` evidence. No sibling package path appeared in either task set, no agent/LLM ran, and the target `git status` hash stayed byte-identical. This validates explicit targets only; it makes no automatic all-scope cost claim. | This PR |
| 22 | [mastra-ai/mastra](https://github.com/mastra-ai/mastra) | 2026-07-16 | Reused clean commit `67879dd090ba1c3b35026a906b9fa0da8c5fcb9c` and target `packages/memory/src/index.ts` to validate generated-task provenance as an executable freshness gate | Dev generation emitted 11 tasks whose effective evidence was exactly root `package.json`, `pnpm-lock.yaml`, and `packages/memory/package.json`. Offline regrade with no repeated generated-source flags stored all three automatically. A byte change to the package manifest then made strict score (only `--tasks`, `--workdir`, `--require-current-evidence`) exit 7 with `stale eval evidence: evidence changed: packages/memory/package.json`. The source file was restored byte-for-byte, strict score passed again, no agent/LLM ran, and the target worktree remained clean. | This PR |
| 23 | [mastra-ai/mastra](https://github.com/mastra-ai/mastra) | 2026-07-16 | Reused clean commit `67879dd090ba1c3b35026a906b9fa0da8c5fcb9c` and `packages/memory/src/index.ts` to validate complete task-pack preflight before paid execution | Dev generation reproduced the same byte-identical 11-task scoped pack from round 22. In an isolated copy of that JSON, a twelfth final task omitted `prompt`; a marker-only local runner then received zero calls, no result file was written, and eval exited 2 with only `task error: task 11 field \`prompt\` must be a non-empty string`. No agent/LLM/judge ran, no source file changed, and the Mastra worktree remained clean. | This PR |
| 24 | [mastra-ai/mastra](https://github.com/mastra-ai/mastra) + [VRSEN/agency-swarm](https://github.com/VRSEN/agency-swarm) | 2026-07-16 | Reused two clean public checkouts plus one deliberately missing local path to validate organization-scale batch coverage failure | Read-only dev `scan --repos-file --json` completed reports for Mastra `67879dd090ba1c3b35026a906b9fa0da8c5fcb9c` (26 instruction files) and agency-swarm `4fb6452e5341d94916831b549ea2dad3072261ac` (3 instruction files), recorded the missing third entry as `error_count=1`, then exited 8 with a coverage-only diagnostic. Both real worktrees stayed clean. No remote clone/API, baseline composition, plugin, agent, or LLM was used. | This PR |
| 25 | [github/docs](https://github.com/github/docs) + [microsoft/vscode](https://github.com/microsoft/vscode) | 2026-07-16 | Validate structured Copilot applicability against two large first-party repositories rather than only synthetic globs | Read-only dev scan/explain on sparse clean checkouts: github/docs `8c0d1d6747ef40ee00588b87f7f78a7063f835f4` classified all 5 `.instructions.md` files as path rules; `content/example.md` automatically selected all + three content rules while `src/example.ts` selected all + code only. VS Code `e6549ec3e40aee3e1877dd8b8c4d632574cb71be` classified 23 rules (13 path, 10 conditional), including bounded nested brace expansion; `buildNext.instructions.md` was automatic for `build/next/index.ts` and non-matching for `src/vs/editor/test.ts`. Remaining same-file/same-domain quote/test findings were retained. Sparse checkout means zero-current-match notices prove only the checked-out files, not stale upstream globs; both worktrees stayed clean. No Treat mutation, plugin, agent, or LLM ran. | This PR |
| 26 | [bitwarden/clients](https://github.com/bitwarden/clients) | 2026-07-16 | Validate first-party Claude Code `paths` block-list rules on a large production monorepo | Read-only dev `scan --no-monorepo --json` + `explain` on sparse clean checkout `44c808ea278b472c3e092ce5dc6f57b62a0c4b70`: `.claude/rules/i18n.md` was inventoried as Claude Code, parsed as a 4-pattern path rule with 617 matches in the sparse `apps/browser/src` checkout, selected `automatic` for `apps/browser/src/main.ts`, and `non-matching` for `README.md`; no applicability/security warning. Match count and unrelated repository findings are bounded by sparse contents, not a claim about the full upstream tree. Worktree stayed clean; no Treat, plugin, agent, or LLM ran. | This PR |
| 27 | [algolia/instantsearch](https://github.com/algolia/instantsearch) | 2026-07-16 | Validate official no-frontmatter Claude project rules as always-on rather than malformed/manual | Read-only dev `scan --no-monorepo --json` + `explain` on sparse clean checkout `997a511f7ca034c92fcc53bd707c6448cf1bfdcf`: `.claude/rules/e2e.md` was inventoried as Claude Code, classified `always` with no applicability/security warning, and selected `automatic` for `README.md`. Sparse checkout limits unrelated finding evidence; the worktree stayed clean and no Treat, plugin, agent, or LLM ran. | This PR |
| 28 | [QwenLM/qwen-code](https://github.com/QwenLM/qwen-code) | 2026-07-16 | TS agent CLI (a diverged fork of gemini-cli); root `AGENTS.md` + `CLAUDE.md` on a Node monorepo. Ran the **full four-stage chain** (scan → treat → check_drift → eval) | 1 false positive found and fixed (see below): "vitest framework" plus `npm run test:integration:...` were read as a competing `vitest`↔`npm test` `test_command` conflict, tripping `--fail-on-conflicts`. The remaining findings — 5 `.qwen/*` MISSING paths (dirs the doc labels "git-ignored" runtime scratch) and `scripts/copy-assets.ts` — are logged as a deferred gitignored-declared-path class plus genuine drift. | [#204](https://github.com/NieZhuZhu/ai-harness-doctor/pull/204) → v1.9.1 |
| 28 | [langgenius/dify](https://github.com/langgenius/dify) | 2026-07-16 | Large Python+TS monorepo with a deep nested `AGENTS.md` tree (`api/`, `cli/`, `web/`, `e2e/`, `packages/`) + `.claude/settings.json` + a `.claude/skills/` tree; picked to stress multi-stack scan/drift | Same `test_command` false positive reproduces (`cli/AGENTS.md` line `pnpm test  # vitest`) — confirms the class across two independent repos; same fix/PR. The genuine `uv`↔`pnpm` `package_manager` conflicts (Python `api/` + JS `web/`) are correctly retained, and the ~50 D2 drift findings are genuine aspirational-doc drift plus a package-root-relative nested-scope resolution nuance logged for a future round. | Same fix/PR → v1.9.1 |
| 28 | [letta-ai/letta](https://github.com/letta-ai/letta) | 2026-07-16 | Python agent framework (legacy Letta server, maintenance mode); real root `AGENTS.md` | No actionable tool bug: the single `letta/letta` MISSING path is a Docker **image** reference (the "`letta/letta` image") misread as a filesystem path — an `org/name` token class logged for a future round (same family as round 7's Go import paths). Scan/drift otherwise consistent. | — |
| 29 | [QwenLM/qwen-code](https://github.com/QwenLM/qwen-code) | 2026-07-17 | Revisit the five round-28 `.qwen/*` runtime-scratch false positives against the current committed ignore/re-inclusion rules | Read-only dev `scan --json --no-monorepo` + `drift --json` on clean shallow checkout `f8e6e893166d567df94e82e1d53745e4862f6e38`: semantic checked 34 declarations with 0 mismatches and no path finding; D2 retained only genuine `scripts/copy-assets.ts` drift. All five ignored runtime paths disappeared, while `.qwen/commands`, skills, agents, and team-memory re-inclusions were not broadly suppressed. Target HEAD and the empty `git status --porcelain` SHA-256 stayed byte-identical. Scan + Drift only; no Treat, plugin, agent, judge, or Eval ran. | This PR |
| 30 | [langgenius/dify](https://github.com/langgenius/dify) | 2026-07-17 | Revisit round-28 package-root-relative nested drift against a current deep `cli/src/commands/AGENTS.md` scope | Read-only dev `drift --json` on clean sparse checkout `96e34e7b24a2f6b7acabb500ef847443405f4b59`: lexical ancestor resolution removed exactly seven old findings and added none — two duplicate-line `tree:gen` D1 occurrences collapse to one fingerprint, five package-relative D2 findings under `cli/src/commands`, plus the same class under `e2e/features/agent-v2`. The remaining 70 findings and 0/F health are bounded by the sparse checkout and include genuine/other deferred classes; this round proves only the seven-finding delta. Target HEAD and empty status hash stayed unchanged. Drift only; no Scan, Treat, plugin, agent, judge, or Eval ran. | This PR |
| 31 | [microsoft/vscode](https://github.com/microsoft/vscode) (+ 13 more via the new `benchmark/corpus/`) | 2026-07-17 | First benchmark-corpus batch: `scan --repos-file` over 14 well-known repos (react, n8n, vscode, ollama, transformers, dify, supabase, gemini-cli, codex, home-assistant, zed, elasticsearch, cline, ghostty) pinned as shallow submodules; vscode pinned at `e1b183798f02` | 1 false positive found and fixed (see below): the whole 14-repo batch reported exactly one HIGH security finding, and it was the TypeScript signature `handle(..., token: CancellationToken)` in vscode's Copilot-extension `AGENTS.md` misread as a `Generic hardcoded secret`. Post-fix re-scan: 0 HIGH findings across all 14 repos, every other aggregate number unchanged (150 config files, 96 gaps, 44 overlaps, 3 conflicts, 15 semantic mismatches, 10/14 repos with root `AGENTS.md`). Committed results live in `benchmark/corpus/results/`. | [#255](https://github.com/NieZhuZhu/ai-harness-doctor/pull/255) |
| 32 | [letta/letta](https://github.com/letta-ai/letta) (round 28) + [openai/codex](https://github.com/openai/codex) (round 14/31 retained corpus evidence) | 2026-07-17 | Adjudicate and fix the previously-logged `org/name` runtime-identifier false-positive class: Letta's `letta/letta` Docker image and Codex's `thread/read` / `app/list` RPC-method tokens reported MISSING by Phase-0 and Phase-2 D2 | Bugfix (see below): a bounded same-line context classifier now excludes tokens explicitly labeled as Docker/OCI images or RPC/API methods while keeping every real filesystem reference checked; ambiguity stays fail-closed and extensioned/three-plus-segment tokens are always paths. Regression tests across `tests/test_registry_consistency.py`, `tests/test_semantic.py`, and `tests/test_check_drift.py`; full `npm run check` green and self-checkup grade A unchanged. | (this PR) → v1.12.1 |
| 33 | [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph) | 2026-07-17 | Active Python monorepo whose root `AGENTS.md` is fully mirrored into a sibling `CLAUDE.md`; ran the **full four-stage chain** (scan → treat → check_drift → eval) | 1 false positive found and fixed (see below): `treat --plan` overlap consolidation told the user to "reduce `AGENTS.md` to an import stub pointing at `AGENTS.md`" — collapsing the canonical single source of truth into a stub pointing at itself — whenever the root `AGENTS.md` fully overlaps a sibling harness file. Scan/drift were otherwise clean (no HIGH security, no conflicts). | This PR |
| 34 | [RooCodeInc/Roo-Code](https://github.com/RooCodeInc/Roo-Code) | 2026-07-17 | Large active TypeScript agent monorepo with a single root `AGENTS.md`; ran the **full four-stage chain** as an over-suppression cross-check | Clean run: 0 HIGH security, 0 conflicts, `check_drift --strict` found no blocking drift, and the branch-name/stub fixes below suppressed no real path. Only informational gap-analysis WARNs (missing canonical section headings) remain; no actionable tool bug. | This PR |
| 35 | [mem0ai/mem0](https://github.com/mem0ai/mem0) | 2026-07-17 | Active Python repo whose `CLAUDE.md` is a symlink to `AGENTS.md`; ran the **full four-stage chain** | 2 false positives found and fixed (see below): (a) the example git branch name in "Create a feature branch from `main` (e.g., `feature/my-new-feature`)" was flagged as a MISSING path by both the Phase-0 semantic scan and the Phase-2 D2 `--strict` gate; (b) the same self-referential import-stub suggestion as round 33 (100% `AGENTS.md`↔`CLAUDE.md` overlap). The remaining `.mem0-integration/` D2 finding is a runtime-artifact directory, logged as a deferred class. | This PR |
| 36 | [openai/codex](https://github.com/openai/codex) (corpus pin `3151954`) | 2026-07-17 | First Phase-3 before/after efficacy eval against a real corpus repository instead of the controlled demo pair: does fixing the 4 genuinely stale path references that `scan.py` flags in an otherwise healthy `AGENTS.md` move task-level metrics? | **Null result, published** (see below): 24/24 vs 24/24 objective task attempts, 0 flip-flop tasks on both sides, latency/turn/cost deltas within single-run noise — a strong self-verifying runner heals stale path references at the cost of at most one extra exploration turn, so the self-benchmark effect saturates on this defect class. The eval also re-adjudicated the round-32 runtime-identifier closure against the real upstream sentence: `thread/read`/`app/list` still fire because the RPC cue sits 54 characters before the token, outside the classifier's 40-character window (the round-32 regression test used an adjacent-cue paraphrase, not the upstream line). Classifier widening deferred. Full data: `benchmark/corpus/evals/codex/`. | This PR (benchmark data + docs; no engine change) |
| 37 | [trycompai/comp](https://github.com/trycompai/comp) (disease-targeted, pinned `b04358d`) + 26-repo `.cursorrules` sweep | 2026-07-17 | Counterpart to round 36: find a real repo whose defect sits in the *wrong-command* channel (the one the self-benchmark predicts matters) via symptom-targeted sampling — 948 `.cursorrules` repos → 247 with `AGENTS.md`/`CLAUDE.md` → 27 (≥200★) scanned in one `--repos-file` batch → 12 with command-class conflicts → lockfile adjudication | **Positive result, published** (see below): comp's `CLAUDE.md` forked from `AGENTS.md` (95.8% overlap) and still teaches `npx` on a bun monorepo; one Phase-1 treatment run took the runner 18/24 → 24/24 with the 3 conflict tasks failing deterministically before (verbatim stale-doc echo, both runs) and −37% wall / −45% turns / −19% cost after. The sweep also produced 5 candidate false-positive classes for future adjudication (`bun run --filter '<pkg>' <script>` parsed as script `run`; backtick ellipsis paths like `apps/app/src/app/api/...`; a negation-context slip, "any attempt to use npm will fail", read as a pm signal; script-name tokens like `npm run test:bun` read as a bun signal; prose tokens like "real-npm-consumer" read as an npm signal) — logged, not yet fixed. Full data: `benchmark/corpus/evals/comp/`. | This PR (benchmark data + docs; no engine change) |
| 38 | [assistant-ui/assistant-ui](https://github.com/assistant-ui/assistant-ui) | 2026-07-18 | Active TS pnpm monorepo (Vercel-AI-SDK chat UI); 14 KB root `AGENTS.md` + nested `packages/cloud-ai-sdk/AGENTS.md` + `.claude/`, an oxlint/oxfmt toolchain that documents native lint rules and a GitButler branch convention. Ran the **full four-stage chain** (scan → treat → check_drift → eval) | 2 false positives found and fixed (see below): (a) oxlint rule ids `react/exhaustive-deps` and `react/rules-of-hooks` misread as MISSING two-segment paths by the Phase-0 semantic scan and the Phase-2 D2 gate; (b) the GitButler workspace ref in "If the current branch is `gitbutler/workspace`" misread as a MISSING path (its `gitbutler/` prefix is not a conventional branch-type prefix, so the existing branch guard did not cover it). The remaining D2 finding — the broken Markdown link `../cloud/AGENTS.md` in the nested `packages/cloud-ai-sdk/AGENTS.md` — is **genuine drift** in the repo's own config (target `packages/cloud/AGENTS.md` does not exist), verified by direct filesystem search; drift went F(35)→B(80) after the two fixes, leaving only that real finding plus the size notice. | This PR → v1.13.3 |
| 38 | [elie222/inbox-zero](https://github.com/elie222/inbox-zero) | 2026-07-18 | Active TS repo with an unusually rich harness surface: root `AGENTS.md` + `CLAUDE.md` stub + `.cursor/` + `.claude/` + a `copilot/` tree. Ran the full four-stage chain as an over-suppression cross-check | No engine change. The single semantic/D2 path finding — `utils/example.test.ts` in "Co-locate unit tests next to source files (e.g., `utils/example.test.ts`)" — is an explicitly-illustrative example path (preceded by "e.g."), a distinct "example-path" class deferred rather than rushing a narrow "e.g."-cue heuristic. Scan otherwise clean (0 security, 0 conflicts), eval generated 8 fact-derived tasks. Logged for a future round. | — (deferred class) |
| 38 | [google/adk-python](https://github.com/google/adk-python) | 2026-07-18 | Google Agent Development Kit; real root `AGENTS.md` on a Python/uv stack, picked as a non-TS cross-check for the round | Clean — scan 0 security findings, 0 semantic mismatches, 0 conflicts, drift 100/grade A. Eval generated a single deterministic `python-version` task (correctly abstaining on the uv/pip package-manager ambiguity rather than guessing). Accurately reports a healthy canonical config. Nothing to fix. | — |

**Loop status:** rounds 1-38 complete. Round 38 ran the full four-stage chain across assistant-ui/assistant-ui, elie222/inbox-zero, and google/adk-python and fixed two Phase-0/Phase-2 path false-positive classes surfaced by assistant-ui — prose-labelled linter rule ids (`react/exhaustive-deps`, `react/rules-of-hooks`) and a non-prefixed branch ref named by a strong equative cue (`gitbutler/workspace` in "the current branch is …") — plus a pre-existing CI-red README regression (all seven README pre-commit `rev:` pins were left at `v1.13.1` while `package.json` shipped `1.13.2`); released as v1.13.3. inbox-zero surfaced a deferred "example path" class (`utils/example.test.ts` behind an "e.g.") and adk-python came back clean (drift 100/A). Round 37 completes the efficacy bracket opened by round 36: disease-targeted sampling found trycompai/comp, whose stale `CLAUDE.md` (forked from `AGENTS.md`, still teaching `npx` on a bun monorepo) produced deterministic wrong answers that one Phase-1 treatment run eliminated (18/24 → 24/24, −37% latency), and logged five deferred false-positive candidates from the 26-repo sweep. Round 36 publishes the first real-repo Phase-3 before/after eval (openai/codex at the corpus pin) as an honest null result — task-level metrics saturate when the only doc defects are stale path references in otherwise-healthy docs — and logs that the round-32 runtime-identifier closure does not cover the real codex sentence (RPC cue 54 chars from the token, outside the 40-char window; widening deferred). Rounds 33-35 (langchain-ai/langgraph, RooCodeInc/Roo-Code, mem0ai/mem0) ran the full four-stage chain and fixed two false-positive classes — an example git branch name (`feature/my-new-feature`) misread as a missing path by both the Phase-0 semantic scan and the Phase-2 D2 `--strict` gate, and a self-referential import-stub suggestion that told users to reduce the canonical `AGENTS.md` to a stub pointing at itself; released as v1.12.2. Round 32 (bugfix) also closes the previously-logged `org/name` runtime-identifier class — Letta's `letta/letta` Docker image (logged in round 28) and OpenAI Codex's `thread/read` / `app/list` RPC-method examples (retained from round 14/31) — via one bounded same-line context classifier shared by Phase-0 and Phase-2 D2. Round 11 (v0.15.2) added a dotenv false-positive fix found by running the full four-stage chain against OpenHands; rounds 12-13 (litellm, openai-agents-python) came back clean; rounds 14-15 (v0.15.3) fixed one shared subdirectory-scoped-path false-positive class found across openai/codex and sst/opencode. Round 16 (v1.1.2) fixed two conflict-detection false-positive classes — the complementary ESLint+Prettier formatter pair (google-gemini/gemini-cli, block/goose) and existence-negated tool names (cline/cline). Rounds 17–19 validate nested scan scope, nested drift, and target-path explain semantics against current Mastra; round 20 validates complete identity/security coverage plus honest bounded-semantic evidence on a real oversize AGENTS.md; round 21 validates bounded explicit-scope efficacy generation on current Mastra; round 22 proves generated fact sources are automatically freshness-bound; round 23 proves the complete task pack fails before any paid runner side effect; round 24 proves batch coverage stays complete but cannot return a false green when one listed repo is absent; round 25 validates deterministic path/conditional applicability and target explain behavior on current first-party GitHub and VS Code rule sets; rounds 26–27 validate Claude Code block-list and always-on project rules on current Bitwarden and Algolia checkouts. Round 28 (v1.9.1) fixed a `test_command` conflict false positive — a package-manager test command (`npm`/`pnpm test`) plus the framework it invokes (`vitest`) — reproduced by running the full four-stage chain across QwenLM/qwen-code and langgenius/dify. Round 29 closes the deferred Qwen gitignored-runtime-path class while preserving the independent `scripts/copy-assets.ts` drift; round 30 closes Dify's lexical package-ancestor class without changing unrelated sparse findings.

## Round 1 detail — continuedev/continue

**Confirmed working correctly:**
- All 24 `.continue/rules/*.md` files detected, plus the nested `extensions/cli/AGENTS.md` — validates the Continue adapter shipped in v0.10.0 against a real dogfooding repo.
- `package_manager`/`test_command` conflicts (gradle in the IntelliJ-plugin rule file vs. npm/vitest in the JS/TS rule files) are legitimate evidence, not a false positive: this is a real multi-stack monorepo (JetBrains plugin + VS Code extension + core), and the file:line citations correctly point a human at exactly why. Not a bug — this is the tool doing its job of surfacing conflicting signals for adjudication rather than guessing.
- No root `AGENTS.md` yet, so G1/G4 gaps and 0 semantic mismatches are all expected.

**Bug found and fixed:** `scan --json` reported a **HIGH** severity `Generic hardcoded secret` finding for `.continue/rules/dev-data-guide.md:102` — `apiKey: "your-api-key-here"`. That's an obvious documentation placeholder, not a committed credential, but it passed every existing check (quoted, ≥12 chars, no spaces). Since `--fail-on-security` exits 2 on HIGH findings, this could have broken CI for a real adopter. Fixed by excluding common placeholder shapes (`your-`/`my-` prefixes, `example`/`sample`/`dummy`/`placeholder`/`changeme`, `<...>` bracket wrapping, `${...}` env-var interpolation, etc.) from the matched span before flagging — see `scripts/scan.py`'s `_SECRET_PLACEHOLDER_RE`.

## Round 3 detail — vercel/ai

**Confirmed working correctly:** root `AGENTS.md` + `CLAUDE.md` + nested `packages/ai/AGENTS.md` all detected; the `AGENTS.md`↔`CLAUDE.md` 100%-overlap finding is accurate (they're identical files — normal for repos maintaining a `CLAUDE.md` pointer/duplicate alongside the canonical file).

**3 false positives found and fixed:**

1. **Semantic command-mismatch, monorepo-blind.** Root `AGENTS.md` documents `pnpm test:node` / `pnpm build:watch` / `pnpm test:edge` / `pnpm test:watch` as commands to "run from within a package directory (e.g., `packages/ai`)" — real scripts, but only declared in `packages/ai/package.json`, not the workspace root's. The semantic engine only ever checked `package_scripts(root)`, so it flagged all four as MISMATCH. Fixed with a new `facts.all_package_scripts()` — a lazy, `os.walk`-pruned union of every `package.json` in the repo — used as a fallback only when the root lookup would otherwise flag a MISMATCH.
2. **Semantic path-check, no negation awareness.** `AGENTS.md` says "Do not create flat top-level provider files like `src/stream-text/openai.ts`" — documenting an anti-pattern, not asserting the path exists — but it was flagged MISSING anyway. Fixed with a negation check (later generalized into `registry.negated_spans()` in round 6 — see below): a line containing "do not"/"don't"/"never"/"avoid"/"shouldn't"/"should not" is skipped for path-existence checks.
3. **package_manager conflict, two npm phrasings misread as "use npm."** `- **pnpm**: v10+ (\`npm install -g pnpm@10\`)` (bootstrapping pnpm via npm, npm ships with Node) and `Main SDK package (\`ai\` on npm)` (the npm *registry*, not the CLI) both manufactured a bogus npm-vs-pnpm conflict against the repo's real `pnpm install`/`pnpm build` commands. Fixed by narrowing the `npm` signal pattern to exclude both phrasings.

All three were found by re-running the dev `scan.py` against the same clone after each fix and confirming the finding disappeared, then adding regression tests before moving on to the next.

## Round 6 detail — better-auth/better-auth

**3 false positives found:**

1. **Negation-blindness was bigger than round 3's fix covered.** `AGENTS.md` reads "ALWAYS use `pnpm` (never npm, yarn, or bun)" and "NEVER run `pnpm test` (runs all packages). Use `vitest path/to/test -t <pattern>`" — both explicitly reject the alternatives they mention, about as unambiguous as prose gets, yet `package_manager` and `test_command` conflict detection read every named tool as a competing declaration, manufacturing a 4-way and a 2-way conflict. Root cause: round 3's negation fix only covered path-existence checking, not signal extraction, and it worked by skipping the WHOLE line — which would also have thrown away the real asserted `pnpm` value here. Generalized into `registry.negated_spans(line)`: a negation trigger word plus everything up to the next `.`/`;`/`)` becomes a "negated span" (deliberately NOT comma-terminated, so "never npm, yarn, or bun" stays one span), and both `scan.extract_signals` and `registry.declared_paths` now check a match's own start position against those spans instead of blanket-skipping. `declared_paths`'s original whole-line skip was upgraded to this same position-aware form.
2. **Package self-import specifier misread as a filesystem path.** "Use `getTestInstance()` from `better-auth/test`" was flagged MISSING — `better-auth/test` is a package.json `exports` subpath import (this monorepo has `packages/better-auth/package.json` named exactly `better-auth`), not a repo-relative path. Fixed with a new `facts.all_package_names()` (shares its repo walk with `all_package_scripts()` via a new internal `_walk_package_jsons` helper); a path whose first segment matches a real package name in the repo is no longer flagged.
3. **Deferred, not fixed:** `indent_style` conflict from "Biome (tabs for code, 2 spaces for JSON)" — both values are simultaneously true, just scoped to different file types. Neither the negation fix nor the self-import fix apply; correctly handling "X for A, Y for B" needs real per-file-type scoping, which is a bigger design question than a quick regex. Left as a known false positive rather than rushing a narrow pattern-match that would likely just move the false positive somewhere else.

## Round 7 detail — charmbracelet/crush

**Confirmed 2 findings are real, not a tool bug:** `AGENTS.md` documents `go test ./internal/llm/prompt` and `go test ./internal/tui/components/core`, but `internal/llm/` doesn't exist at all — the actual location is `internal/agent/prompt` (renamed), and there is no `tui` directory anywhere under `internal/` (removed/restructured). Verified with a direct filesystem search before concluding this is genuine drift in the target repo's own docs, not a false positive — exactly the disease this tool exists to catch.

**1 false positive found and fixed:** Go import/module paths misread as filesystem paths. `AGENTS.md` says "The module path is `github.com/charmbracelet/crush`" (its own `go.mod` module line) and lists dependencies like "`charm.land/bubbletea/v2`", "`charm.land/fantasy`" — all flagged MISSING. Go import paths are conventionally `domain.tld/org/pkg[/vN]`; added `registry._GO_IMPORT_HOST_RE`, matching when a multi-segment token's first component looks like a hostname (contains a non-leading `.`). **Caught a bug in my own fix before shipping:** the first version didn't gate on the token actually containing `/`, so it also matched bare single-segment filenames like `go.mod`/`Cargo.toml` (which legitimately contain a dot) and broke `test_backtick_path_detection_single_sourced_across_stages`. Fixed by requiring `"/" in token` before the hostname check — full test suite caught this immediately, nothing shipped broken.


## Round 8 detail — pydantic/pydantic-ai, mastra-ai/mastra, crewAIInc/crewAI

First round to run the **full four-stage chain** (scan → treat → check_drift → eval) rather than `scan` alone. mastra and crewAI both came back clean (scan 0 security findings, drift 100/grade A); the two false positives below both came from pydantic-ai, and both would break a real adopter's CI.

**FP 1 — Phase-0 security flagged Claude Code's recommended per-command scoping as "unrestricted execution".** `.claude/settings.json` uses the standard `Bash(cmd:*)` allow-list (`Bash(git log:*)`, `Bash(rg:*)`, `Bash(ls:*)`, `Bash(gh pr view:*)`, `Bash(uv run:*)`, `Bash(make:*)`, …). `BROAD_PERMISSION_RE`'s third alternative `:\s*\*\s*\)$` matched every one of them, producing **19 HIGH findings** claiming each "grants unrestricted execution". But `cmd:*` scopes the `*` to a single named command's arguments — it is the opposite of unrestricted. This is a `--fail-on-security` CI killer for any repo following Claude Code's documented scoping guidance. Fixed so a rule is broad only when the **command itself** is a wildcard (`Bash(*)`, `Bash(*:*)`, `Execute(*)`, `Shell(*)`, bare `*`); the wildcard-command case is still caught.

**FP 2 — Phase-2 D3 reported a full-duplicate config as a "regrown pointer stub".** pydantic-ai keeps `CLAUDE.md` as a byte-identical duplicate of its 13 KB `AGENTS.md`, and that file lists ten nested `dir/AGENTS.md` links (`docs/AGENTS.md`, `pydantic_ai_slim/pydantic_ai/AGENTS.md`, …). The D3 guard's discriminator was `"AGENTS.md" in text and len(data) > STUB_POINTER_MAX_BYTES`, so any incidental mention or link tripped it — D3 emitted an **ERROR that fails `drift --strict`** for a file that was never a managed pointer stub. Fixed by requiring a real pointer signal (`@AGENTS.md` import directive, or the canonical "instructions live in AGENTS.md" redirect phrase that `canonicalize.py` writes) before flagging regrowth. Genuine regrown stubs (which retain that pointer line) are still caught; the existing "independent doc with no pointer" test and the new "full duplicate that only links to nested AGENTS.md" test both stay silent.

**Net effect on pydantic-ai:** scan security 19 HIGH → 0; drift 80/grade B (D3 ERROR, exit 1) → 95/grade A (exit 0). The remaining `D4 NOTICE` (13 KB AGENTS.md context-bloat) is a legitimate, non-failing observation.


## Round 11 detail — All-Hands-AI/OpenHands, BerriAI/litellm, openai/openai-agents-python

Ran the **full four-stage chain** (scan → treat → check_drift → eval) against three new repos. litellm and openai-agents-python came back clean; the one false positive below came from OpenHands, and it would break a real adopter's `--fail-on-semantic` scan and `drift` gate.

**FP — gitignored runtime `.env` path reported as a MISSING path.** OpenHands' `AGENTS.md` documents its frontend config under "Set in `frontend/.env` or as environment variables". A runtime `.env` file is deliberately gitignored and never committed — the doc references it as the place to *put* local config, not as a path the repo is expected to contain — so probing `root/frontend/.env` always misses and the shared path classifier (`registry.declared_paths`, used by both the Phase-0 semantic scan and the Phase-2 D2 drift gate) flagged it MISSING. A committed `.env` would itself be the bug this tool warns about, so the fix skips conventionally-gitignored dotenv files (`.env`, `frontend/.env`, `.env.local`, `.env.production`, …) from path-existence checks. The committed **template** variants (`.env.example`, `.env.sample`, `.env.template`, `.env.dist`, `.env.defaults`) are deliberately kept checkable, because those *are* meant to be tracked and a reference to a missing one is genuine drift. Added as `registry._is_gitignored_dotenv`, with regression tests in `tests/test_semantic.py` (dotenv-not-flagged + template-still-flagged).

**Confirmed the remaining OpenHands findings are real, not a tool bug:** the other 12 path findings are genuine drift in OpenHands' own `AGENTS.md` — files renamed or moved during the V1 restructuring (`frontend/src/types/action-type.ts` now `.tsx`; `openhands/cli/utils.py`, `openhands/utils/llm.py`, `openhands/llm/llm.py`, `openhands/app_server/integrations/vscode` all gone), plus a `.pr/` scratch directory and a block of paths explicitly attributed to a separate `software-agent-sdk` repo. Verified by direct filesystem search before concluding — exactly the disease this tool exists to catch. (The cross-repo-attributed-path class — paths a doc explicitly says live "in the `X` repo" — is logged here as a candidate for a future round; it needs section-context tracking the line-by-line classifier doesn't yet do, so it is deliberately not rushed into a narrow heuristic.)

**litellm & openai-agents-python — clean:** litellm scans 0 security findings and drifts 100/grade A across an unusually rich surface (root `AGENTS.md`+`CLAUDE.md`+`GEMINI.md`, a nested Rust workspace, and a JS dashboard); its 3 reported conflicts are legitimate multi-stack evidence (cargo/pytest/npm all genuinely present), not false positives. openai-agents-python scans 0 security findings and 0 semantic mismatches across 47 checks, drift 95/grade A, with only a non-failing `D4` size NOTICE.


## Round 14-15 detail — openai/codex + sst/opencode (one shared root cause)

Both repos tripped the **same** semantic false positive, so they share one fix and PR (#96 → v0.15.3). The Phase-0 semantic check resolved every backtick-quoted path against the **repo root only**, but a root `AGENTS.md` frequently scopes a whole section to a subdirectory and then writes paths relative to *that* subdirectory.

**codex (5 FPs).** The root `AGENTS.md` opens with *"In the codex-rs folder where the rust code lives"* and documents `Cargo.toml`, `Cargo.lock`, `app-server-protocol/src/protocol/common.rs`, `app-server/README.md`, and (generically) `pyproject.toml`. All of these exist under `codex-rs/` (or elsewhere in the tree), none at the repo root, so all 5 were reported `MISSING` — a `--fail-on-semantic` CI killer for a repo whose docs are perfectly accurate. The remaining flagged paths are **correct**: `codex-rs/codex-mcp/src/mcp_connection_manager.rs` is genuine drift (the file was renamed to `connection_manager.rs`), and `thread/read` / `app/list` are RPC-method-name examples (a distinct backtick class, deliberately left for a future round rather than rushing a heuristic).

**opencode (2 FPs).** The root `AGENTS.md` references `src/config` and `src/system-context`, which live at `packages/opencode/src/config` and `packages/core/src/system-context`. Both were reported `MISSING`.

**Fix.** `facts.path_resolves_in_subtree(root, token)`, consulted lazily just before a would-be `MISSING`:

- A **multi-segment** token resolves when it exists as a trailing path under any pruned directory in the repo (so `src/config` matches `packages/opencode/src/config`, `app-server/README.md` matches `codex-rs/app-server/README.md`).
- A **bare single-segment** token resolves only when it is a well-known build-manifest basename that exists anywhere. That basename set is `registry.KNOWN_ROOT_FILES` — the *same* set the path detector uses to emit single-segment tokens at all — so the resolver and the detector can never drift apart (the TD-02 duplication trap this tool exists to catch).

The walk is `os.walk` with `SKIP_DIRS` pruning and only runs on an otherwise-missing token, so the common no-finding path never pays for a repo walk. Four regression tests were added (`tests/test_semantic.py`): subdir-scoped multi-segment paths and subdir manifests are silenced; a fully-qualified path with no matching basename and a manifest present nowhere both stay `MISSING` so genuine drift is never masked.

**Net effect:** codex semantic 11 → 6 findings (5 FPs removed, real drift preserved); opencode 2 → 0.

**2026-07-15 Phase-2 follow-up (Plan 014):** the original rounds 14–15
verification proved the Phase-0 semantic fix, but it did not add the equivalent
subtree-resolution call to D2. A minimal local reproduction (`src/config`
present only under `packages/app/`) therefore passed `scan --json` and still
failed `drift --json`. The follow-up reuses
`facts.path_resolves_in_subtree()` in D2 and adds a cross-engine parity test;
this is a correction to the evidence boundary, not a claim that the external
repositories were freshly re-scanned.


## Round 16 detail — google-gemini/gemini-cli + block/goose + cline/cline (two conflict-detection false positives)

Round 16 targeted three widely-used agents and surfaced two distinct conflict-detection false-positive classes, both fixed in #125 → v1.1.2.

**ESLint + Prettier misread as a formatter conflict (gemini-cli, goose).** `scan.find_conflicts` reported a `formatter` conflict whenever a doc named both `prettier` and `eslint`, treating them as mutually exclusive values. But they are the complementary, standard JS/TS combination — Prettier formats, ESLint lints, and they are explicitly designed to run together — so declaring both is the recommended setup, not a conflict. Reproduced independently on google-gemini/gemini-cli and block/goose. **Fix:** when every distinct `formatter` value is a subset of `{prettier, eslint}`, skip the conflict; a genuine `biome`-vs-`{prettier,eslint}` conflict is still reported because biome is an all-in-one alternative to that stack, not part of it.

**Existence negation misread as a declaration (cline/cline).** `registry._NEGATED_CLAUSE_RE` covered directive negations (`do not`/`never`/`avoid`/...) but not *existence* negations. cline's root `AGENTS.md` says "There are no per-package npm lockfiles" — an assertion that npm is **absent** — yet `npm` inside that clause was extracted as a declared `package_manager` signal and manufactured a false npm↔pnpm conflict against the real pnpm declaration. **Fix:** extend the negation clause with `there are no`, `there is no`, `there's no`, `have no`, and `has no`, reusing the same position-aware span mechanism (from round 6) so a real positive declaration earlier on the same line still registers.

**Tests.** `FormatterConflictTests` (ESLint+Prettier does not conflict; biome+prettier still does) and `NegatedExistenceClauseTests` (existence-negated npm is neither extracted nor turned into a conflict) in `tests/test_scan.py`.


## Round 28 detail

Ran the full four-stage chain (scan → treat → check_drift → eval) against three active, previously-unvalidated AI repos with real harness configs.

**Package-manager test command + framework misread as a `test_command` conflict (qwen-code, dify).** `scan.find_conflicts` treats the `test_command` signal values as mutually exclusive, but the signal registry mixes test *frameworks* (`jest`/`vitest`/`pytest`) with package-manager *runner* commands (`npm test`/`pnpm test`). A `pnpm test` (or `npm test`) command simply invokes the underlying JS framework, so a doc that declares both — QwenLM/qwen-code's "vitest framework" alongside `npm run test:integration:...`, and langgenius/dify's `cli/AGENTS.md` line `pnpm test  # vitest` — manufactured a bogus `vitest`↔`npm/pnpm test` conflict and tripped `--fail-on-conflicts`. **Fix:** mirror the round-16 ESLint+Prettier handling — suppress the conflict only when a conflicting component is exactly one framework (`jest`/`vitest`/`mocha`) plus one or more package-manager runners (`npm`/`pnpm`/`yarn test`). Genuine conflicts remain: two rival frameworks (`jest` vs `vitest`) still conflict, and a cross-stack command (`pytest` vs `pnpm test`, `go test` vs `npm test`) still conflicts. dify's genuine `uv`↔`pnpm` `package_manager` conflict (Python `api/` + JS `web/`) is untouched.

**Tests.** `TestFrameworkVsRunnerConflictTests` in `tests/test_scan.py` covers both false-positive shapes (`pnpm test`+vitest, `npm test`+"vitest framework") and both genuine-conflict guards (jest-vs-vitest, pytest-vs-pnpm-test).

**Logged, not fixed this round.**

- **Gitignored declared paths flagged MISSING (qwen-code).** The root `AGENTS.md` documents `.qwen/issues/`, `.qwen/pr-drafts/`, `.qwen/pr-reviews/`, `.qwen/investigations/`, and `.qwen/scripts/` as runtime scratch dirs explicitly labeled "git-ignored" (and matched by `.gitignore` `.qwen/*`). Both the Phase-0 semantic check and the Phase-2 D2 gate flag them as MISSING paths. This generalizes round 11's dotenv special-case into a broader "doc references an intentionally-gitignored path" class; a robust fix (respect `.gitignore` for path-existence checks) is deferred to keep this a tight patch.
- **`org/name` Docker image reference misread as a path (letta).** letta's `AGENTS.md` mentions "the `letta/letta` image"; `letta/letta` is a Docker image reference, not a filesystem path, but D2 reports it MISSING — same family as round 7's Go-import-path tokens.
- **Package-root-relative nested-scope path resolution (dify).** `cli/src/commands/AGENTS.md` references `src/commands/tree.ts`, `src/auth/`, etc. written relative to the `cli/` package root; drift resolves against repo root and the doc's own directory but not the enclosing package root, so paths that exist at `cli/src/...` are reported MISSING. Entangled with genuine aspirational-doc drift in dify's docs, so deferred for a dedicated round.


## Round 31 detail — microsoft/vscode via the benchmark corpus

First round driven by the new `benchmark/corpus/` (14 well-known repos pinned as shallow
submodules, scanned in one `scan --repos-file` batch — see `benchmark/corpus/README.md`).
The batch reported exactly **one** HIGH security finding across all 14 repositories.

**FP — TypeScript type annotation misread as a hardcoded secret.** vscode's
`extensions/copilot/src/extension/chatSessions/claude/AGENTS.md` documents a handler
signature: `handle(args: string, stream: ChatResponseStream | undefined, token:
CancellationToken)`. The `Generic hardcoded secret` pattern's unquoted branch
(`[A-Za-z0-9+/_\-.]{16,}`) matched `token: CancellationToken` — a purely alphabetic,
mixed-case *type identifier*, not a credential. Real secrets of that length are
high-entropy and virtually always carry digits or symbols, so the fix ([#255](https://github.com/NieZhuZhu/ai-harness-doctor/pull/255))
exempts unquoted all-alpha mixed-case values via `redaction.is_identifier_annotation`,
shared by the in-memory and streaming security paths. Recall guards: values with digits,
all-lowercase values, and quoted values still flag; the placeholder logic is untouched.

**Confirmed corpus evidence retained, not adjudicated:** the batch's other findings (96
gaps, 44 overlaps, 3 conflicts, 15 semantic mismatches — including codex's known
RPC-method-token class from round 14) are committed as unadjudicated evidence in
`benchmark/corpus/results/` for future rounds; this round only claims the vscode secret
FP and its fix.

## Round 32 detail — letta/letta (round 28) + openai/codex (round 14/31) runtime-identifier class

Closes the `org/name` runtime-identifier false-positive class that was reproduced
and explicitly logged across earlier rounds but deferred to keep those patches
tight:

- **Docker/OCI image misread as a path (letta).** Round 28 logged that Letta's
  `AGENTS.md` mentions "the `letta/letta` image"; `letta/letta` is a Docker image
  reference, not a filesystem path, yet both the Phase-0 semantic check and the
  Phase-2 D2 gate reported it MISSING.
- **RPC/API method tokens misread as paths (openai/codex).** The codex corpus
  evidence retained in round 31 includes two-segment method tokens such as
  `thread/read` and `app/list` from the app-server RPC docs, same lexical shape,
  same false MISSING result.

**Root cause.** A backtick token like `org/name` is lexically identical whether
it names a repo-relative directory (`src/service`), a Docker image, or an RPC
method. The shared `registry.declared_paths` classifier had no way to tell them
apart, so every such token became a path-existence candidate.

**Fix.** `registry._is_labeled_runtime_identifier` adds a bounded, same-line
context check used by the single shared classifier (so Phase-0 and Phase-2 D2
stay in lockstep). Only a plain two-segment token (exactly one `/`, no dot, no
leading dot, no relative marker) is eligible; a token explicitly labeled by
adjacent words as a Docker/OCI image (`image`, `docker image`, `container
image`) or an RPC/API method (`rpc method`, `method`, `endpoint`, `operation`,
`route`) is treated as a runtime identifier and excluded. The check is
fail-closed: an explicit filesystem cue (`file`, `directory`, `folder`, `path`,
`edit`, `open`, `modify`, `repository`, ...) always wins, an unlabeled
`org/name` stays a path, and any token with an extension or three-plus segments
(e.g. a `docker/compose.yml` Compose file) is always a path regardless of nearby
prose.

**Recall guards.** Genuine missing filesystem paths still flag: `src/service`
under an "edit"/"repository" cue, a bare unlabeled `team/module`, extensioned
files, and three-plus-segment paths all remain checked. Regression tests live in
`tests/test_registry_consistency.py` (classifier + cross-stage parity),
`tests/test_semantic.py` (Phase-0 existence), and `tests/test_check_drift.py`
(Phase-2 D2).

## Round 36 detail — openai/codex real-repo before/after efficacy eval (null result)

Design: two copies of the corpus-pinned checkout
(`315195492c80fdade38e917c18f9584efd599304`); the *after* copy differs only by
fixing the 4 genuinely stale path references `scan.py` flags in the root
`AGENTS.md` (a 5-line diff; semantic mismatches 6 → 2). 12 objective regex-graded
tasks — 4 targeting the corrupted facts, 8 controls whose answers are identical
on both sides — each adversarially verified against the pinned tree by an
independent reviewer agent before any paid run (two grading regexes were
tightened as a result). Runner: `claude -p ... --output-format json`
(CLI 2.1.212, captured model `claude-fable-5`), 2 runs per side, interleaved.

Result: before 24/24, after 24/24; 0 flip-flop tasks on either side; per-task
latency noise (up to 2.4× between same-side runs) exceeded any before/after
difference; total captured cost 12.18 USD. The before-side runner did not trust
the stale paths — it verified against the file tree and self-corrected. Bracketed
with the self-benchmark (6/28 → 28/28 when docs are wrong about *conventions and
commands*), this locates the efficacy boundary: stale *path* references in
otherwise-healthy docs are self-healing for a strong agent, while wrong
*convention/command* claims are not. Published in full (data, tasks, treatment
diff, limitations) in `benchmark/corpus/evals/codex/`.

Secondary finding: the round-32 runtime-identifier closure was validated with an
adjacent-cue paraphrase ("Call RPC method `thread/read` to stream."), but on
codex's real sentence the RPC cue sits 54 characters before the token — outside
the classifier's bounded 40-character window — so `thread/read` / `app/list`
still fire at this pin. Reproduced with `registry.declared_paths` on both
sentences. The window bound is deliberate (it keeps section-level prose from
leaking into the classification), so the fix is not a mechanical widening;
logged as a deferred class.

## Round 37 detail — trycompai/comp via disease-targeted sampling (positive result)

Round 36 showed the efficacy effect saturating on a healthy top-star repo; round 37
asks the complementary question — does the effect appear on a real repo whose defect
sits in the wrong-command channel? Star-ranked sampling selects for healthy docs
(humans use top-tier command docs daily and fix them fast), so selection was inverted
to sample by symptom: GitHub code search over `.cursorrules` content (948 unique
repos), GraphQL triage for co-existing `AGENTS.md`/`CLAUDE.md` (247), one
deterministic `scan.py --repos-file` batch over the 27 candidates at ≥200 stars, 12
repos with command-class conflicts, and lockfile adjudication of each. Most flags were
multi-stack evidence or prose false positives; `trycompai/comp` (~1.7k★, active) was
genuinely diseased in the channel the eval runner reads: `CLAUDE.md` — the file
Claude Code actually loads — forked from `AGENTS.md` at 95.8% overlap and still
teaches `npx vitest run` / `npx jest` / `npx turbo run typecheck` on a repo whose
`bun.lock` and `packageManager: bun@1.3.4` mandate bun, while the root `.cursorrules`
directs readers to the stale file "for comprehensive project rules".

Treatment was the real Phase 1 flow (plan → resolve conflicts against the lockfile →
merge the one `CLAUDE.md`-only rule so `AGENTS.md` becomes a true superset → map
canonical headings → `--write-stubs` downgrades `CLAUDE.md` to an `@AGENTS.md` stub;
the readiness gate correctly refused the stub until `AGENTS.md` passed validation).
Result: before 18/24, after 24/24; the 3 conflict tasks failed deterministically
before — the runner echoed the stale `CLAUDE.md` line verbatim in both runs — and
passed in both after runs; −37% wall time, −45% agent turns, −19% cost; 9 control
tasks passed on both sides; 12 adversarial reviewer agents verified every task's
ground truth and regex against the pinned clone before any paid run. Combined with
round 36 this brackets the efficacy claim from both sides with real repositories:
wrong-convention docs cause large deterministic harm that treatment removes; stale
paths in healthy docs are self-healed. It also yields an empirical file-precedence
observation: with both files present, the runner answered from `CLAUDE.md`, so a
divergent pair poisons exactly the agents that read the stale side.

Deferred (logged, not fixed — candidates for future adjudication rounds): the sweep
surfaced five scanner false-positive classes: (a) `bun run --filter '<pkg>' <script>`
parsed as declaring a `run` script ("bun run run" on comp); (b) backtick ellipsis
paths (`apps/app/src/app/api/...`) reported MISSING; (c) negation-context slip —
getsentry/spotlight's "any attempt to use npm will fail" read as an npm signal
despite the round-16 negation class; (d) script-name tokens — uhop/stream-json's
`npm run test:bun` read as a bun package-manager signal; (e) prose tokens —
Caldis/react-zmage's "real-npm-consumer integration tests" read as an npm signal.


## Round 38 detail — assistant-ui/assistant-ui (two path false-positive classes) + README CI-red regression

Ran the full four-stage chain (scan → treat → check_drift → eval) against three active
repos with real harness surfaces: assistant-ui/assistant-ui (TS pnpm monorepo,
14 KB root `AGENTS.md` + nested `packages/cloud-ai-sdk/AGENTS.md` + `.claude/`),
elie222/inbox-zero (root `AGENTS.md` + `.cursor/` + `.claude/` + `copilot/`), and
google/adk-python (Python/uv, real root `AGENTS.md`). adk-python was clean
(0 security, 0 semantic mismatches, drift 100/grade A, 1 deterministic eval task).
inbox-zero surfaced one deferred "example path" finding (`utils/example.test.ts`
behind an explicit "e.g."). assistant-ui surfaced two genuine tool false positives,
both fixed here, and one genuine repo-drift finding correctly left untouched.

**Fix 1 — prose-labelled linter rule ids misread as paths.** assistant-ui's
`AGENTS.md` says "dependency arrays and hook rules are checked by oxlint's native
`react/exhaustive-deps` and `react/rules-of-hooks`". Both are oxlint/ESLint
`plugin/rule` identifiers, but their two-segment `word/word` shape made the
Phase-0 semantic scan and the Phase-2 D2 gate report them as MISSING paths. The
existing `facts.is_eslint_rule_identifier` only recognises rule ids quoted
verbatim in an ESLint config file; oxlint's native rules live in no such file.
A new bounded, fail-closed classifier (`registry._is_labeled_lint_rule`, shared
by both phases) now suppresses a token only when three independent signals agree:
the token has the hyphenated `plugin/rule-name` shape (`exhaustive-deps`,
`rules-of-hooks`), the same line names a concrete linter (`eslint`/`oxlint`/
`tslint`/`stylelint`/`biome`), and the same line uses the word "rule(s)". An
explicit filesystem cue (`file`, `directory`, `edit`, …) in the bounded window
always wins and keeps the token a path, so real dirs like `config/eslint`,
`packages/eslint-config`, and `ci/build-matrix` are never over-suppressed.

**Fix 2 — non-prefixed branch ref named by a strong equative cue.** assistant-ui
documents a GitButler convention: "If the current branch is `gitbutler/workspace`,
the user uses GitButler, not Git." The existing `_is_labeled_branch_ref` guard
requires the token's first segment to be a conventional branch-type prefix
(`feature/`, `fix/`, `release/`, …) — `gitbutler/` is not, so the ref was reported
MISSING. The guard now also honours a STRONG equative cue (`current branch`,
`branch is`, `branch named`, `branch called`, `on branch`) that directly names the
token as a branch, suppressing it on its own even without a conventional prefix.
An explicit filesystem cue still wins, and a bare mention of "branch" (weak cue)
without a prefix still keeps a real directory checked (`src/utils` stays a path).

After both fixes, assistant-ui's Phase-0 semantic mismatches went 3→0 and its
Phase-2 D2 health went F(35)→B(80), leaving only the **genuine** finding: the
broken Markdown link `../cloud/AGENTS.md` in `packages/cloud-ai-sdk/AGENTS.md`
(the target `packages/cloud/AGENTS.md` does not exist — verified by direct
filesystem search) plus a non-failing 14 KB context-bloat NOTICE.

**Fix 3 — pre-existing CI-red README regression.** The full test suite exposed a
regression unrelated to the target repos: the v1.13.2 release bumped
`package.json` to `1.13.2` but left all seven README pre-commit `rev:` pins at
`v1.13.1`, so `tests/test_precommit_hooks.py::test_readme_pre_commit_examples_use_current_exact_release`
was failing on `main` (7 failing subtests). All seven README pins were bumped to
match the shipped version, restoring green CI.

Regression tests live in `tests/test_registry_consistency.py`
(`test_prose_labeled_lint_rule_ids_are_not_declared_paths`,
`test_strong_branch_cue_suppresses_non_prefixed_branch_ref`), each asserting both
`registry.declared_paths` and `semantic.declared_paths` agree and that real
directories are never over-suppressed. Full `python3 -m unittest discover -s tests`
is green except the sandbox-only `test_action_metadata` checkup-shell subtests
(they shell out to a real `gh`, which the sandbox replaces with a stub; they pass
in CI). The three target worktrees were read-only throughout — nothing was ever
written back to them.
