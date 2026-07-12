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
2. **Semantic path-check, no negation awareness.** `AGENTS.md` says "Do not create flat top-level provider files like `src/stream-text/openai.ts`" — documenting an anti-pattern, not asserting the path exists — but it was flagged MISSING anyway. Fixed with `registry._PATH_NEGATION_RE`: a line containing "do not"/"don't"/"never"/"avoid"/"shouldn't"/"should not" is skipped for path-existence checks.
3. **package_manager conflict, two npm phrasings misread as "use npm."** `- **pnpm**: v10+ (\`npm install -g pnpm@10\`)` (bootstrapping pnpm via npm, npm ships with Node) and `Main SDK package (\`ai\` on npm)` (the npm *registry*, not the CLI) both manufactured a bogus npm-vs-pnpm conflict against the repo's real `pnpm install`/`pnpm build` commands. Fixed by narrowing the `npm` signal pattern to exclude both phrasings.

All three were found by re-running the dev `scan.py` against the same clone after each fix and confirming the finding disappeared, then adding regression tests before moving on to the next.
