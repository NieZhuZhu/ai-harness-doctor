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

## Round 1 detail — continuedev/continue

**Confirmed working correctly:**
- All 24 `.continue/rules/*.md` files detected, plus the nested `extensions/cli/AGENTS.md` — validates the Continue adapter shipped in v0.10.0 against a real dogfooding repo.
- `package_manager`/`test_command` conflicts (gradle in the IntelliJ-plugin rule file vs. npm/vitest in the JS/TS rule files) are legitimate evidence, not a false positive: this is a real multi-stack monorepo (JetBrains plugin + VS Code extension + core), and the file:line citations correctly point a human at exactly why. Not a bug — this is the tool doing its job of surfacing conflicting signals for adjudication rather than guessing.
- No root `AGENTS.md` yet, so G1/G4 gaps and 0 semantic mismatches are all expected.

**Bug found and fixed:** `scan --json` reported a **HIGH** severity `Generic hardcoded secret` finding for `.continue/rules/dev-data-guide.md:102` — `apiKey: "your-api-key-here"`. That's an obvious documentation placeholder, not a committed credential, but it passed every existing check (quoted, ≥12 chars, no spaces). Since `--fail-on-security` exits 2 on HIGH findings, this could have broken CI for a real adopter. Fixed by excluding common placeholder shapes (`your-`/`my-` prefixes, `example`/`sample`/`dummy`/`placeholder`/`changeme`, `<...>` bracket wrapping, `${...}` env-var interpolation, etc.) from the matched span before flagging — see `scripts/scan.py`'s `_SECRET_PLACEHOLDER_RE`.
