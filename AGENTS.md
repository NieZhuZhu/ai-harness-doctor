# Project overview

This repository contains the `ai-harness-doctor` Claude Code skill. It audits, consolidates, guards, and evaluates AI harness configuration files around a canonical `AGENTS.md`.

# Project structure

- `SKILL.md` — the skill contract and the four-phase workflow (Checkup → Treat → Follow-up → Efficacy).
- `scripts/` — deterministic Python engines:
  - `scan.py` — Phase 0 inventory/security scan, monorepo results, structured applicability, and debt baselines.
  - `semantic.py` — Phase 0 declaration-vs-code facts for Node, Python, Go, Rust, Java, and Ruby.
  - `applicability.py` — bounded Claude/Cursor/Copilot applicability; no general YAML.
  - `canonicalize.py` — Phase 1 merge plan, `--draft`, tool-stub downgrade, and validation.
  - `check_drift.py` — Phase 2 root/nested D1–D8 guard, health, `--fix`, and baselines.
  - `explain.py` — read-only target-path projection of scan's canonical scope, diagnostic-source, override, and conflict evidence.
  - `plugins.py` — opt-in deterministic `.ai-harness-doctor/rules/*.py` engine; plugin failures become `ERROR` findings instead of crashing.
  - `eval_run.py` — Phase 3 Efficacy: before/after + matrix eval runner and LLM-as-judge grading.
  - `pr_review.py` — Phase 2/3 CI helper: combines active scan+drift JSON (root/package/batch) into one attributed GitHub review; `--dry-run` prints it, `--post` uses the stdlib REST client.
  - `gen_adapters.py` — repo-maintenance tool (not shipped in the npm package): regenerates the per-command `adapters/` from a single source; `--check` gates re-divergence in CI.
- `bin/cli.js` — npm CLI/installer/forwarder; `bin/mcp-server.js` — MCP stdio; `bin/runtime.js` — Python resolver; `bin/action-run.js` / `bin/action-report.js` — Action argv and SARIF reporting.
- `assets/` — templates: `assets/AGENTS.template.md` and the `assets/guard/` suite; `references/` — progressive-disclosure docs.
- `commands/`, `adapters/` — Claude/Codex/Cursor/Gemini/universal command pointers. Edit `scripts/gen_adapters.py`, then regenerate; do not hand-edit generated adapter flavors.
- `tests/` — Python unittest + Node CLI smoke tests; `benchmark/` — self-benchmark and efficacy eval fixtures.

# Build & test

Run the full test suite from the repository root:

```bash
python3 -m unittest discover -s tests -v
npm test
node --check bin/cli.js
node bin/cli.js help
```

# Conventions

- Python scripts must use Python 3.9+ standard library only.
- `assets/agent-tools.json` is the single source for scanned/canonicalized/drifted agent configs via `scripts/registry.py`; add tools there, not in engine-local lists. `bin/cli.js`'s `AGENTS` is intentionally separate installer-target metadata.
- `bin/cli.js` must use Node >=16 standard library only; do not add npm runtime dependencies.
- Scripts stay deterministic and never semantically merge; those decisions remain in `SKILL.md` and human review.
- Stub apply requires canonical readiness (no product draft markers; safe path/size/sections); `--force` only accepts dirty-tree risk.
- `--max-bytes` bounds semantic text only; full-file SHA/line/security stays bounded-memory. Mark prefix-only evidence; never call a prefix digest a file SHA or claim unseen tails clean.
- Instruction scope is lexical: same-scope differences conflict; descendant differences are non-blocking overrides. Structured applicability stays registry-sourced, bounded/fail-closed, and full-byte security scanned; conditional/manual/invalid/ignored stays diagnostic. Never infer prose scopes or grant mutation authority from recursive discovery.
- Explain reuses scan scope/containment: canonical files form the chain; modeled rules may apply automatically, while unmodeled sources stay diagnostic. Keep CLI/MCP/adapter contracts synchronized.
- Path truth is repository-owned: contained `.gitignore` rules may explain absence; synthetic Git metadata excludes host state and fails closed. Nested D1/D2/D6 use `facts.ancestor_dirs` nearest-first without sibling leakage; D7 stays file-relative.
See `references/maintenance-contract.md`.
- Baseline: HIGH security ineligible; repaired debt: exit 9.
- Action: `findings > maintenance > ok`; `action-run.js`: bounded `args-json`/legacy `shell:false` argv; `action-report.js` owns outputs; bundled scan/drift + exact npm pre/post-publish.
- Guard/PR sync; exact-title issue upsert; recovery comment/close; unrelated issues untouched; never expose host paths/baselined debt.
- CI/release: `npm ci --ignore-scripts`; committed `package-lock.json`/`registry.npmjs.org`; lint/tests/packed candidate; reruns: `gitHead`/packed shasum; secret scanning/push protection; required checks/resolved conversations; admin bypass: self-approval, never red/pending.
- Installer state authorizes deletion; parsing fails closed; replacement is atomic.
- Eval validates tasks/results before side effects; runner and explicit judge exit 0 are prerequisites for a passing record; failed runner output is never judged. Derive health from records, require cached agreement, then verify evidence freshness before gates. Refresh committed results honestly.
- Validate the complete eval task pack before any runner, judge, evidence hash, or write. Task-declared evidence joins explicit evidence automatically: files bind exact hashes, directories bind existence/type, all before trusting health.
- Targeted eval reuses explain scope/containment. Keep root IDs; use local scripts/deps, nearest clear manager/runtime, inherited canonical rules, relative evidence, and no automatic all-scope expansion.
- Root/scoped eval and Treat draft share `facts.py` containment and ambiguity semantics; external symlinks never supply facts, contained symlinks keep lexical evidence, and competing managers cause abstention.
- MCP tools stay read-only. Sync negotiated-version wire shapes, required/closed schemas, exit policies, stdio tests, and docs; findings are not operational failures, and legacy clients must not receive modern-only fields.
- English is canonical; sync zh-CN, ja, es, ko, pt-BR, and fr via `scripts/check_readme_sync.py` per PR. `npm run lint:docs` enforces heading levels, fenced code, table shape, and link targets; translate prose only.
- Shipped guards/pre-commit hooks call only packaged public CLI commands usable without a local `scripts/` tree; behavior changes need an end-to-end consumer fixture. Self-bootstrap copies may use local code only when labeled.

# Testing requirements

- Any change to `scripts/*.py` or `bin/cli.js` must ship with matching tests in the same commit; do not land behavior changes without test coverage.
- Test fixtures live under `tests/fixtures/` and are read-only inputs — never modify or regenerate them to make a test pass.
- Installer tests follow Safety's isolated-HOME rule.

# Safety

- Installer tests: isolated temporary `HOME`; never write real agent config dirs.
- Scanning logic must treat the audited repository as read-only; never mutate or write back into the repo being scanned.
- Repository-derived reads/probes/mutations use `scripts/facts.py` or the matching `bin/cli.js` guard helper. External symlinks neither affect output nor receive writes; mutations refuse symlinked files/parents. Only documented explicit inputs/outputs may be external.
- Never commit secrets, tokens, or credentials.
- The eval / LLM-as-judge harness makes external model calls — be mindful of cost and token usage when running or expanding it.

# Operational workflows

Four repeatable loops reproduce repository maintenance through one gate/release scheme.

- **External validation** — run the dev checkout read-only against varied real OSS repos and log repo/commit, date, scope, evidence boundary, result, clean worktree, and fixing PR in `EXTERNAL_VALIDATION.md`. Non-adoption alone is clean, not a bug.
- **Incremental quality-check (bugfix) loop** — baseline on latest `main` (green `npm run check` + self-checkup at grade A), then find ONE high-value real issue (a `--fail-on-security` or `drift --strict` false positive, or a cross-engine inconsistency), reproduce it, and fix it with a matching regression test. No finding → no release.
- **Premium-upgrade (feature) loop** — research ecosystem/product gaps, score impact × feasibility, then ship 1–3 stdlib-only items with tests and every public README.
- **Deep improve loop** — independently audit all nine categories on current `main`, reconcile prior plans, and mechanically reproduce one top item. Land plan-only → nine green contexts → test-first implementation → Standards/Spec + real evidence → nine green → squash/delete → green plan closeout. Revalidate every candidate each round.

**Shared gate & release.** One smallest stdlib-only PR; update every published-language README and `SKILL.md` for public behavior. Require lint, Python 3.9–3.12, Node 16–22, self-drift, and eval evidence green; squash/delete. From current main: feature=minor, fix=patch, breaking=major. Verify npm provenance/Release; stable moves `latest`/`vN` and opens one Marketplace reminder, prerelease uses `next` only.

# Commit & PR

- See `CONTRIBUTING.md` for the full contribution workflow (when to open an issue, the PR checklist, and releasing).
- Use Conventional Commits for messages, e.g. `feat(scan): ...`, `fix(drift): ...`, `docs(agents): ...`, `refactor(...)`, `chore(...)`. Commit messages are written in English.
- Land changes through pull requests; do not push directly to `main`.
- Opening an issue first is optional: do it for larger features, externally reported bugs, or anything that benefits from a public record, and link it with `Closes #<n>`. Small, unambiguous changes may go straight to a PR.
- Every behavior change to `scripts/*.py` or `bin/cli.js` must ship with matching tests in the same commit/PR (see Testing requirements).
- Before opening a PR, run the full test suite (see Build & test) and a self-checkup with `python3 scripts/scan.py .` and `python3 scripts/check_drift.py .`; keep the drift health score at grade A.
- Keep every required README listed in `scripts/check_readme_sync.py` synchronized in the same PR whenever public behavior or README content changes.
