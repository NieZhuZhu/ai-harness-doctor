**English** | [简体中文](README.zh-CN.md) | [日本語](README.ja.md)

# 🩺 AI Harness Doctor

**Your AI coding agent is confidently following stale instructions.** `CLAUDE.md`, `.cursorrules`, `GEMINI.md`, and `AGENTS.md` quietly drift apart until agents run scripts that no longer exist, edit paths that already moved, and teach `npm` in a repo that switched to `pnpm`.

AI Harness Doctor makes that drift visible, consolidates every scattered agent config into one canonical `AGENTS.md`, and guards it so your repo forgets less silently — for Claude Code, Codex, Cursor, Gemini, and plain CI. One zero-install `scan` gives you a full checkup: inventory, conflict evidence, a security audit, missing-infrastructure gaps, and a tech-stack snapshot.

<p><a href="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml"><img align="left" alt="CI" src="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml/badge.svg"></a> <a href="https://www.npmjs.com/package/ai-harness-doctor"><img align="left" alt="npm version" src="https://img.shields.io/npm/v/ai-harness-doctor.svg"></a> <img align="left" alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"> <img align="left" alt="Python 3.9+" src="https://img.shields.io/badge/Python-3.9%2B-blue.svg"> <img align="left" alt="Node &gt;=16" src="https://img.shields.io/badge/Node-%3E%3D16-green.svg"></p>
<br clear="left">

> **In our 14-task benchmark, canonicalizing one repo took agents from 6/28 → 28/28 correct answers — and eliminated the flip-flopping where the same question got different answers on different runs.** [See the numbers ↓](#benchmark)

Try it in one command — no install, nothing written to your repo:

```bash
npx ai-harness-doctor scan .
```

> **Repository boundary:** the read-only scanner never follows a repository-derived config, manifest, workspace, semantic-fact, or default-plugin symlink outside the audited repository. In-repo file symlinks remain supported and keep their lexical repo-relative report path; explicitly supplied `--rules DIR` paths remain an intentional opt-in.
>
> **Mutation boundary:** write-capable `stubs --apply`, `drift --fix --apply`, and `guard --apply` / `--remove --apply` refuse repository-derived targets whose file or existing parent directory is a symlink. They never rewrite or delete through a symlink; explicit output paths such as `draft -o` and baseline output files remain deliberate user-selected destinations.

## Why

Agent config drift is a repo disease. One tool reads `CLAUDE.md`, another reads `.cursorrules`, another reads `GEMINI.md`, and each file slowly becomes its own folklore: old commands, moved paths, copied style rules, contradictory package managers, and context files large enough to be truncated.

The painful part is that the agent sounds confident while following stale instructions. A new maintainer asks for the test command and gets a script that no longer exists. A refactor moves `src/components/`, but the rule file still points to `app/ui/`. A team changes npm to pnpm, but three agent surfaces keep teaching npm.

AI Harness Doctor makes that drift visible, helps a human or agent write one canonical `AGENTS.md`, downgrades old tool files to small pointers, and installs guards so the repo can forget less silently.

In our 14-task benchmark, a canonicalized repo took agents from 6/28 to 28/28 correct answers — see [Benchmark](#benchmark).

## User stories

| Persona | Pain | Commands | Outcome |
|---|---|---|---|
| New maintainer | You inherit a legacy repo with a 2-year-old `CLAUDE.md`, three generations of `.cursorrules`, and agents running nonexistent scripts. | `scan` → `/harness-treat` | You get file:line evidence, adjudicate conflicts, and replace folklore with one `AGENTS.md`. |
| Mixed-tool team | Cursor, Claude Code, and Codex users keep forking rule files every week. | `plan` → `stubs --apply` → `guard --apply` | Tool-specific files become stubs, and CI blocks re-divergence. |
| Silently rotting repo | The repo migrated npm→pnpm, directories moved, and docs never caught up. | `drift . --strict` | The path-aware drift gate catches the PR before stale instructions land. |
| Skeptic teammate | Someone calls agent config files cargo cult. | `eval --tasks ...` before/after | Real numbers settle the argument: correctness, instability, latency, and captured cost. |
| OSS maintainer | AI-generated PRs follow the wrong conventions. | `AGENTS.md` + `guard --apply` | Contributors' agents read the maintenance contract and self-check changes. |

## Quick Start

### Fastest path

Zero-install, read-only checkup — one command surfaces your harness's inventory, conflict evidence (with file:line), security findings, missing-infrastructure gaps, and a tech-stack snapshot, in seconds:

```bash
npx ai-harness-doctor scan .
npx ai-harness-doctor explain . packages/api/src/handler.ts
```

`explain` answers a focused scope question without modifying files: which canonical `AGENTS.md` chain applies to the target, which recognized configs are diagnostically associated, and which scoped overrides/conflicts are relevant.

Ready to fix it? Install the Claude Code skill and let the agent drive the full flow:

```bash
npx ai-harness-doctor install
```

Then in Claude Code:

```text
/harness-doctor .
```

Answer the conflict adjudication questions. The tool reports evidence; you decide what is true for the repo.

### Apply to your repo in 3 steps

There is deliberately no true one-click migration. Phase 1 contains semantic decisions: the tool never decides pnpm-vs-npm, test-vs-test:unit, or old path-vs-new path for you.

```bash
npx ai-harness-doctor scan .
npx ai-harness-doctor plan . -o merge-plan.md
# Write AGENTS.md from the plan, then:
npx ai-harness-doctor validate .
npx ai-harness-doctor stubs . --apply
npx ai-harness-doctor guard . --apply
```

Three ways to write `AGENTS.md`:

1. Hand-write it from `merge-plan.md` plus `assets/AGENTS.template.md`.
2. Ask your coding agent to write it, using the plan as evidence.
3. Use `/harness-treat .`: it reads the plan, asks you per conflict, writes the file, then validates.

### Requirements

- Target must be a git repo.
- Node >=16 for the `ai-harness-doctor` CLI.
- Python >=3.9, stdlib-only, for deterministic scan/explain/plan/validate/stubs/drift/review/eval scripts.
- Run `ai-harness-doctor doctor --self-test` to verify the Node + Python runtime; set `AI_HARNESS_DOCTOR_PYTHON` to pin a specific interpreter.
- `AGENTS.md` must exist before `stubs` or `guard` writes anything.

### Install matrix

```bash
npx ai-harness-doctor install                         # Claude Code, user-level
npx ai-harness-doctor install --agent codex
npx ai-harness-doctor install --agent cursor --project
npx ai-harness-doctor install --agent gemini
npx ai-harness-doctor install --agent all --project
npx ai-harness-doctor install --link                  # link to a global package
```

### Automation matrix

| Step | CI-safe? | Writes? | Note |
|---|---:|---:|---|
| `scan` | ✅ | Only with `--write-baseline` | Exits 0 by default; inventory, evidence, security, gaps, semantic consistency, conflicts, and a project snapshot. `--fail-on-security`/`--fail-on-gaps`/`--fail-on-semantic`/`--fail-on-conflicts` exit 2/3/4/7. `--write-baseline` explicitly records non-security debt. |
| `explain` | ✅ | ❌ | Explains canonical inheritance and diagnostic scope evidence for one existing or future contained path. |
| `plan` | ✅ | Optional output file | Scaffolds a merge plan; does not merge. |
| Write `AGENTS.md` | ❌ | ✅ | Human-or-agent semantic step. |
| `validate` | ✅ | ❌ | Checks whether canonical `AGENTS.md` contains the required sections. |
| `stubs` | ✅ | With `--apply` | Requires clean tree unless `--force`. |
| `guard` | ✅ | With `--apply` | Requires git repo and existing `AGENTS.md`. |
| `drift` | ✅ | ❌ | Fails on blocking drift; `--strict` promotes notices. |
| `review` | ✅ | Only with `--post` | Converts scan/drift JSON into rich GitHub PR feedback; dry-run JSON by default. |

### Uninstall & rollback

```bash
npx ai-harness-doctor guard . --remove --apply
npx ai-harness-doctor uninstall --agent all
```

`guard --remove` is marker-precise: it removes only its own managed snippets and will not touch a foreign pre-commit hook. Everything else is git-revertable.

## Slash commands

| Command | Input | What the agent does | Where it STOPS | What you decide |
|---|---|---|---|---|
| `/harness-doctor` | Repo path, usually `.` | Runs the full checkup→treat→follow-up flow; eval only when requested. | Before semantic conflict resolution and before optional eval. | Migration scope, conflict truth, whether to install guards. |
| `/harness-scan` | Repo path | Runs Phase 0 inventory, size, overlap, conflict, and nested-agent detection. | After the health report. | Whether to treat the whole repo, a subdir, or selected files. |
| `/harness-treat` | Repo path, optional scan/plan output | Builds a merge plan, asks about conflicts, writes/validates canonical `AGENTS.md`, previews stubs. | Until every conflict has an explicit answer. | Which command/path/style/version is canonical. |
| `/harness-drift` | Repo path | Runs drift checks and explains repairs. | After checks pass or repair advice is given. | Whether to update repo reality or update `AGENTS.md`. |
| `/harness-eval` | Repo path + task file/results | Runs or compares before/after tasks. | When metrics or a manual protocol are produced. | Task set, runner, and whether the evidence is enough. |
| `/harness-explain` | Repo path + target path | Shows the canonical chain, diagnostic sources, scoped overrides/conflicts, and limitations. | After presenting read-only scope evidence. | Whether the scoped guidance is intentional; the command makes no edits. |

## Updating

Copy installs are tracked in `~/.ai-harness-doctor/manifest.json`. To redeploy the newest package files to everything previously installed, run:

```bash
npx ai-harness-doctor@latest update
```

Interactive commands check npm at most once per day and may print an update hint such as `npx ai-harness-doctor@latest update`; set `AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1` to disable that check. Bare `npx` CLI users should pin `ai-harness-doctor@latest` when they want the newest one-off command.

For true hot updates, install the package persistently and link the payload:

```bash
npm i -g ai-harness-doctor
ai-harness-doctor install --link
npm update -g ai-harness-doctor
```

With `--link`, Claude points `~/.claude/skills/ai-harness-doctor` at the global package and other adapters point at the same package root, so `npm update -g ai-harness-doctor` updates the playbook everywhere instantly. On Windows, directory links use junctions.

## Long-term guard

> The guarantee is a detection guarantee, not an update guarantee: doc-vs-repo consistency becomes a machine-checkable condition that can fail in three places — pre-commit, PR, and a weekly checkup. Forgetting is no longer silent.

Install after the treat phase has produced a canonical root `AGENTS.md`:

```bash
npx ai-harness-doctor guard . --apply
```

The CI gate is provider-aware: pass `--provider github|gitlab|codebase` (default `auto`) to install the matching CI files. See the [`guard`](#command-reference) command reference for the per-provider file layout.

Every provider's merge-request guard now runs the full scan gate (`--fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts`) before drift. If the repository has explicitly reviewed and committed `.ai-harness-doctor/scan-baseline.json`, the guard uses it for pre-existing non-security debt; it never creates or updates that file, and HIGH security findings remain blocking. Scheduled checkups preserve both scan and drift reports and fail when either gate fails.

On a pull request, the GitHub guard template does two more things. First, it captures the active `scan --json` and `drift --json` results without re-running either gate, then passes both reports to one `ai-harness-doctor review` invocation for **complete, actionable PR feedback**. Security, size warnings, gaps, semantic mismatches, custom findings, conflicts, and drift are included; monorepo findings retain package-prefixed repository paths. Baselined scan debt remains visible in scan JSON but is not reposted as an active failure. Independent `--repos-file` batch findings retain a non-absolute repository label and stay summary-only, because they cannot safely attach to one repository's PR diff. Located single-repo findings become inline comments with the rule, severity, finding, AI-agent impact, available evidence, and suggested fix. The final summary includes health score/grade, severity distribution, inline-vs-summary delivery counts, a complete findings index, collapsible full details for every finding, and prioritized next steps; it carries a stable `<!-- ai-harness-doctor:pr-review -->` marker. Repeat `--report PATH` to combine reports in one dry-run or post. If GitHub rejects an inline placement with HTTP 422, the tool preserves all guidance by posting that complete summary as a general PR comment instead; permission, network, rate-limit, and server errors remain visible. A clean report instead explains the covered checks and confirms that no action is required. It is dry-run by default (prints the JSON payload, never touches the network) and only posts with `--post` using `GITHUB_TOKEN`. Second, it runs an **eval evidence + health gate**. Results produced/regraded from tasks that declare `evidence` automatically carry those fact sources in deterministic evidence metadata; repeatable `--evidence FILE` adds manual sources such as `AGENTS.md`. `eval --score ... --tasks ... --workdir ... --evidence AGENTS.md --require-current-evidence --fail-under <N>` re-derives task-declared sources and exits `7` for stale/missing evidence before applying the existing health threshold (exit `5`). File evidence uses SHA-256; directory evidence binds existence and type without recursively hashing children. Fingerprints prove byte identity or directory identity, not that manual answers came from a real model. Generic shipped guards keep eval optional; this repository's self-guard requires its committed result. Every shipped guard command runs through the packaged CLI and works in a fresh consumer repository with no copied `scripts/` tree. Inline PR review feedback is GitHub-only; the GitLab/Codebase templates share the scan and optional eval gates without provider-specific inline comments.

Defense in depth, strongest to weakest:

1. **Pre-commit hard block** — defends against local edits that make `AGENTS.md` stale before they leave the machine. `AI_HARNESS_DOCTOR_SKIP=1` is an explicit, auditable bypass, not a silent pass.
2. **Every-PR gate** — defends against hook bypass without a `paths` / `paths-ignore` filter. Security and semantic inputs include MCP/settings files, nested agent rules, ecosystem manifests, and any repository-relative path referenced by `AGENTS.md`; no finite allow-list can cover that dynamic D2/D7 surface safely.
3. **Weekly checkup + deduped issue** — defends against slow rot between pull requests: environmental changes, dependency behavior shifts, or conventions that become stale without a repository edit.
4. **Maintenance contract in `AGENTS.md`** — defends at the source of agent behavior. Refactors are often done by agents, and every agent reads `AGENTS.md`; the doc instructs its own maintenance.

| Refactor/change | Check that should catch it |
|---|---|
| Change scripts or `Makefile` targets | D1 command drift |
| Move/delete documented paths | D2 path drift |
| Sneak rules back into `CLAUDE.md` or `.cursorrules` | D3 stub regrowth |
| Let `AGENTS.md` bloat past useful context size | D4 size/context risk |
| Bump Node version or switch package manager without updating `AGENTS.md` | D6 fact drift |
| Delete a doc/config file that `AGENTS.md` still links to | D7 Markdown-link drift |
| Commit lockfiles for two different package managers | D8 competing lockfiles |

Why detection over regeneration? Silently “fixing” drift removes human awareness. AI Harness Doctor surfaces drift instead, because the important part is not rewriting files; it is making the team notice that repo truth and agent truth diverged. See [Positioning & Non-goals & Comparison](#positioning--non-goals--comparison).

Adopting the gate on a repo that already drifted? `drift --write-baseline FILE` records today's findings once, then `drift --baseline FILE` suppresses exactly those so CI fails only on new drift — the same on-ramp ruff, mypy, and detekt offer. Baseline fingerprints ignore line numbers, suppressed findings stay visible under a `baselined` array, and the health score counts only new drift, so a fully baselined repo still reads grade A.

### Pre-commit framework

Already standardized on [pre-commit](https://pre-commit.com)? Add the drift and scan guards straight to your `.pre-commit-config.yaml` instead of running `guard --apply`:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/NieZhuZhu/ai-harness-doctor
    rev: v1.3.0
    hooks:
      - id: ai-harness-doctor-drift
      - id: ai-harness-doctor-scan
```

`ai-harness-doctor-drift` blocks the commit when `AGENTS.md` drifts from repository facts; `ai-harness-doctor-scan` fails on HIGH security findings. Both run over the whole repository (`pass_filenames: false`, `always_run: true`) and need Node and Python 3 on the machine. Add flags with `args:` (for example `["--strict"]` to escalate drift notices), and skip a single commit with pre-commit's own `SKIP=ai-harness-doctor-drift git commit ...`.

## Works with

| Surface | Support |
|---|---|
| Claude Code | Native skill plus slash commands under `.claude/commands` or `~/.claude/commands`. |
| OpenAI Codex CLI | Prompt adapters for `~/.codex/prompts/`. |
| Cursor | Command adapters for `.cursor/commands/`. |
| Gemini CLI | TOML custom command adapters for `~/.gemini/commands/harness/`. Google retired Gemini CLI for individual tiers on 2026-06-18; enterprise Gemini Code Assist is unaffected, and these adapters still work for enterprise/existing installs. |
| Windsurf / Cline / others | Universal mode: point the agent at the installed playbook and say “run phase N”. |
| MCP clients | `ai-harness-doctor mcp` exposes `harness_scan`/`drift`/`validate`/`plan`/`stubs`/`eval_generate`/`explain` as MCP tools over stdio. |
| Humans & CI | Plain `npx ai-harness-doctor ...`; no agent required. |

Honest note: non-Claude adapters are thin pointers and lightly verified. If a command format changed, please file an issue.

## The four phases

| Phase | Script | Artifact | Stop condition |
|---|---|---|---|
| 0 — Checkup / scan | `scripts/scan.py` | Human or JSON health report | Stop at user confirmation of migration scope. |
| 1 — Treat / canonicalize | `scripts/canonicalize.py --plan`, `--write-stubs`, `--validate` | Merge plan, canonical `AGENTS.md`, minimal stubs | Stop until every conflict has human adjudication. |
| 2 — Follow-up / drift guard | `scripts/check_drift.py` | Drift report and CI/pre-commit exit codes | Stop when checks pass or repair advice is given. |
| 3 — Efficacy eval | `scripts/eval_run.py` | Before/after JSON and Markdown report plus a 0–100 `health` score (A–F grade) | Stop when metrics are produced. |

## Command reference

<details>
<summary><code>install</code></summary>

Installs the skill, slash commands, and/or adapter prompts.

| Agent | Default destination | With `--project` |
|---|---|---|
| `claude` | `~/.claude/skills/ai-harness-doctor`, `~/.claude/commands/` | `.claude/skills/ai-harness-doctor`, `.claude/commands/` |
| `codex` | `~/.codex/prompts/` + shared payload | Same adapter location; project affects payload path. |
| `cursor` | `.cursor/commands/` | `.cursor/commands/` in the target project. |
| `gemini` | `~/.gemini/commands/harness/` + shared payload | Same command location; project affects payload path. |

Adapters replace `{{PLAYBOOK}}` with the installed playbook path. Copy payloads live in the dedicated `.ai-harness-doctor/payload/` subtree, separate from repository-owned baselines, rules, and other state. The versioned `~/.ai-harness-doctor/manifest.json` records exact managed paths and SHA-256 digests. Existing malformed/unsupported manifests and symlinked state paths fail closed and remain untouched; valid state is replaced atomically. Install/update never overwrites an unowned collision or a managed file edited after installation; it reports `manual-merge` / `modified-preserved` instead. Uninstall removes only byte-verified managed files and keeps shared payloads until the last referencing agent is removed. Legacy manifests migrate additively, retiring only byte-identical old payload files. `--link` points at a global package instead of copying payload files; the CLI blocks unsafe `npx` cache linking and tells you to install globally first.

</details>

<details>
<summary><code>uninstall</code></summary>

Removes only pristine manifest-owned Claude skill files, slash commands, adapter prompts, and shared payloads for the requested `--agent`. User-edited or unowned files are preserved and reported. `--agent all` removes every verified managed surface. It also removes matching manifest records.

</details>

<details>
<summary><code>update</code></summary>

Redeploys every manifest-tracked copy install to the current package version without replacing user-edited files. Linked installs refresh command pointers while the payload follows `npm update -g ai-harness-doctor`.

</details>

<details>
<summary><code>guard</code></summary>

Dry-run by default; use `--apply` to write. Requirements: target is a git repo and `AGENTS.md` already exists.

It manages a provider-agnostic core plus a **provider-aware CI gate**:

1. `.git/hooks/pre-commit` drift block.
2. A CI drift/checkup gate whose files depend on `--provider` (see below).
3. A marked maintenance contract in `AGENTS.md`.

`--provider github|gitlab|codebase|auto` (default `auto`) selects which CI files to install. `auto` detects the provider from `.gitlab-ci.yml` and the `origin` remote (github.com → `github`, a host containing `gitlab` → `gitlab`, any other enterprise host such as internal Codebase → `codebase`, no remote → `github`):

| Provider | CI files installed | Wiring note |
|---|---|---|
| `github` | `.github/workflows/harness-drift.yml` every-PR gate + `.github/workflows/harness-checkup.yml` weekly scan/drift checkup with a deduped issue. | Runs automatically on GitHub Actions. |
| `gitlab` | An includable `.gitlab/harness-ci.yml` (`harness-drift` on MRs, `harness-checkup` on schedules with an artifact). | Add `include: { local: .gitlab/harness-ci.yml }` to `.gitlab-ci.yml`. |
| `codebase` | A portable `.harness-ci/harness-guard.sh` (`drift`/`checkup` modes) + a wiring `README.md`. | Register the script as an MR check and a scheduled pipeline step. |

`AI_HARNESS_DOCTOR_SKIP=1` is the explicit auditable escape hatch for the local hook. `guard --remove --apply` removes managed snippets, cleans up **all providers'** CI files (so switching providers leaves nothing behind), and restores byte-exact pre-existing hook content when possible. Both install and remove are non-destructive: every managed file carries an `ai-harness-doctor:guard` marker, so `guard --apply` never overwrites a user-edited CI file that lacks the marker (it reports a `manual-merge` and leaves your file untouched), and `--remove` only deletes a managed file when it is byte-identical to what the tool shipped — a hand-extended hook has just its own guard block stripped out, and a modified block is skipped rather than destroyed.

**Self-bootstrap:** this repository runs its own guard. `.github/workflows/harness-drift.yml` and `.github/workflows/harness-checkup.yml` are adapted from the `assets/guard/` templates to run the repo's **local** scan and drift implementations instead of the published package, so changes to `scripts/` are gated by the code being changed. The reviewed `.ai-harness-doctor/scan-baseline.json` records known conflicts contributed by benchmark/test fixtures; the PR gate fails on any new scan debt or drift. Generic shipped guards keep eval optional, but this repository unconditionally gates its committed self-eval on current task/`AGENTS.md` evidence and health. Only the PR-review posting step tolerates a missing/limited token.

</details>

<details>
<summary><code>scan</code></summary>

Detects five classes: config inventory, size/truncation risk, overlap candidates, conflict candidates with file:line evidence, and nested `AGENTS.md` files. On top of that it answers the complementary question — *what is missing* — via a gap analysis (see below).

It also inventories the **extended harness surface** — MCP servers, subagents, slash commands, hooks, and permission rules — and runs a **security checkup** that flags severity-ranked findings (HIGH/MEDIUM):

- Plaintext secrets (AWS / GitHub / OpenAI / Google / Slack / Anthropic keys, private-key blocks, generic `api_key/secret/token=...`) across instruction and MCP/settings config files.
- Over-broad permissions such as `Bash(*)`, `*`, and `defaultMode: bypassPermissions`.
- MCP hygiene issues: insecure `http://` transports and credential-shaped env literals.
- Risky hook/command bodies: `curl … | bash`, `rm -rf`, `--dangerously-skip-permissions`, and similar.

For an oversized instruction file, `--max-bytes` bounds only the semantic text retained for overlap, conflict, override, and declaration analysis. The inventory SHA/line count and high-confidence secret/bypass checks still cover every byte without retaining the whole file in memory. JSON exposes `analyzed_bytes`, `truncated`, `security_scanned_bytes`, and top-level `analysis_limits`; Markdown labels prefix-only overlap evidence. An empty bounded-semantic result is never presented as proof about the unseen tail.

It exits 0 by default. With `--fail-on-security` it exits `2` when any HIGH-severity finding is present, which is handy as a CI gate.

It also runs a **gap analysis** that diffs the repo against a harness completeness checklist and reports mandatory infrastructure it is *missing* (not just what exists). These static checks are limited to the pieces every healthy harness needs regardless of stack: a canonical root `AGENTS.md` (`G1`), the required `AGENTS.md` sections kept in sync with `assets/AGENTS.template.md` (`G2`), tool stubs that should be minimal pointers to `AGENTS.md` (`G3`), and the drift-guard / weekly-checkup CI workflows (`G4`). It also enforces both `SKILL.md` [Named anti-patterns](SKILL.md#named-anti-patterns) that otherwise have no backing code: **Wholesale Dumping** (`G9`) — `AGENTS.md` sharing more than half its normalized lines with `README.md`, a sign content was copied wholesale instead of distilled into agent-specific, non-inferable rules; and **Silent Adjudication** (`G10`) — `AGENTS.md` declaring one side of a live signal conflict (e.g. `pnpm` over `npm`) with no trace the other side was ever surfaced for the repo owner to adjudicate. Each gap carries a `level` (`ERROR`/`WARN`/`NOTICE`), an `item`, a `message`, and an actionable `suggestion`. With `--fail-on-gaps` it exits `3` when any ERROR-level gap (e.g. a missing root `AGENTS.md`) is present.

For everything that depends on the project's tech stack (rather than being universally required), scan emits a **project snapshot** — a compact, factual description of the repo that an agent/LLM can reason over:

- `tech_stack`: languages / ecosystems detected from their manifests (`go.mod`, `package.json`, `pyproject.toml`, `requirements.txt`, `Cargo.toml`, `pom.xml`, `Gemfile`, `composer.json`, …).
- `existing_files`: CI, git-hook, lint/format, and typecheck config files present, plus whether a drift-guard pre-commit hook is installed.
- `agents_sections`: the H1 sections currently in `AGENTS.md`.
- `maintenance_contract`: whether `AGENTS.md` embeds the maintenance contract.
- `mcp_tools` / `has_permissions`: configured MCP servers and whether permission rules exist.

The stack-dependent judgements that used to be static `G5`–`G8` gaps (pre-commit guard, maintenance contract, MCP config, permission config) are now facts in this snapshot, left for an agent to reason about.

It also runs a **semantic consistency** check that compares what `AGENTS.md` *declares* against what the code actually *is*, so stale instructions surface at checkup time (not just in the Phase 2 drift gate). It is **multi-ecosystem** — beyond Node/npm it understands Python (`pyproject.toml` / `setup.py` / `requirements.txt`, with pip/poetry/uv/pdm/pipenv), Go (`go.mod`), Rust (`Cargo.toml`), Java (`pom.xml` / `build.gradle`), and Ruby (`Gemfile` / `.ruby-version`, with bundler). It cross-checks build/test commands (`npm run <script>` / `make <target>`, plus `cargo run --bin <name>`, `go run ./<pkg>`, and `poetry run <script>`) against `package.json` scripts, `Makefile` targets, Cargo binary targets, Go package paths, and pyproject console scripts; backtick-quoted repo-relative paths against the filesystem; the declared package manager against each ecosystem's committed lockfile/manifest (including bundler via `Gemfile.lock`); and the declared language/runtime version against the ecosystem's pin (`.nvmrc` / `engines.node`, `requires-python` / `.python-version`, the `go.mod` `go` directive, `Cargo.toml` `rust-version`, the Java compiler level, and `.ruby-version` / the `Gemfile` `ruby` directive). Each finding carries a `category` (`command`/`path`/`package_manager`/`node_version`/`python_version`/`go_version`/`rust_version`/`java_version`/`ruby_version`), a `level` (`MISMATCH`/`MISSING`), the `declared` value, the `actual` fact, an optional `line`, and a `suggestion`. With `--fail-on-semantic` it exits `4` when any declaration contradicts the code.

**Adoption baseline for existing scan debt.** A repository can record its current gap, semantic, and conflict debt once, commit the transparent register, and then gate only new findings:

```bash
npx ai-harness-doctor scan . --write-baseline .ai-harness-doctor/scan-baseline.json
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json \
  --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts
```

The versioned baseline is deterministic, timestamp-free, and uses structured identities containing the finding family/rule, root-or-package scope, path/evidence, and message while treating line numbers as evidence rather than identity. Suppressed debt stays visible in the top-level `baselined` array and a Markdown baseline summary, but it is excluded from fail-on decisions and SARIF. HIGH security findings never enter the baseline and always remain active; a crafted security-shaped entry is ignored. Missing or malformed baseline files suppress nothing. Monorepo root/package identities are distinct. `--repos-file` is intentionally incompatible with scan baselines because each unrelated repository must own its own debt register. Review baseline changes like code and shrink the file as debt is repaired; it is not a regex ignore list.

**Full JSON report for agents.** In markdown mode `scan` writes the complete machine-readable report (files, surface, security, `project_snapshot`, `semantic`, and `gaps`) to a stable temp file — `${TMPDIR}/harness-scan-<hash>.json`, where `<hash>` is derived from the resolved repo path — and appends a `## Full JSON report` section pointing to it. An agent driving the workflow can read that file to reason over the snapshot and gaps and plan fixes, without re-parsing the markdown. The `--json` mode already prints the full report to stdout, so no temp file is written there. Use `--no-report-file` to skip writing it.

**Monorepo / multi-package awareness.** `scan` is monorepo-aware. When it detects a workspace — npm/yarn/pnpm `workspaces` in `package.json`, a `pnpm-workspace.yaml`, or (with `--monorepo`) multiple nested `package.json` / `AGENTS.md` subtrees — it additionally scans each detected package subdirectory and reports per-package results plus a top-level aggregate. The markdown report gains a `## Monorepo` section (a per-package table plus an aggregate line), and `--json` gains a top-level `packages` array (one entry per package, each with the same scan shape under `report`, plus a `summary`) and a `monorepo` object (`source`, `package_count`, `aggregate`). Single-repo behavior is unchanged when no workspace is detected; use `--no-monorepo` to force a root-only scan, or `--monorepo` to force detection.

**Nested instruction scopes.** Conflict diagnostics follow the AGENTS.md nearest-file rule without guessing from prose: each `AGENTS.md` / `AGENT.md` parent directory is a lexical scope, and every config file belongs to its deepest canonical ancestor. Only different values inside the same scope are blocking `conflicts`; ancestor → descendant differences are non-blocking `scope_overrides`, while sibling scopes are independent. JSON adds `instruction_scopes` and `scope_overrides`; Markdown and Treat plans show both so intentional overrides stay auditable and are not collapsed into root stubs. Non-root true conflicts carry `scope` through baselines, SARIF, and PR review. This does not infer file-type, glob/frontmatter, or prose scopes.

**Custom rule plugins.** `scan` (and `drift`) can be extended with your own DETERMINISTIC rules. Drop Python modules in the target repo's `.ai-harness-doctor/rules/*.py` directory and/or pass `--rules DIR` (repeatable). Each module exposes `def check(root, context) -> list[dict]:` returning findings (`level`, `message`, optional `path`/`line`/`suggestion`, and a `rule` id); `context` carries the run `phase` and the `AGENTS.md` text. Findings are merged into a `custom` section (markdown `## Custom rule plugins` and the `--json` `custom` array). Plugins are opt-in — with no rules directory and no `--rules`, behavior is unchanged. A plugin that fails to import or raises at runtime is isolated and reported as a `level: "ERROR"` finding instead of crashing the scan; see `references/example-rule-plugin.py` for a template.

**Multi-repo batch mode.** `scan --repos-file PATH` scans every repository listed in `PATH` (one path per line; blank lines and `#` comments ignored) instead of a single `repo_root`, and prints an org-wide health summary — for the "Mixed-tool team" and "OSS maintainer" personas that otherwise have no story beyond running the tool once per repo by hand. Each repo is scanned independently at its own root (this mode does not expand monorepo packages within a repo); a path that does not resolve to a directory is reported under "Repos that could not be scanned" instead of aborting the whole batch. `--json` returns `{ summary: { repo_count, error_count, aggregate }, repos: [{ path, resolved, name, has_agents_md, summary, report } | { path, resolved, error }] }`. All four `--fail-on-*` gates consider every scanned repo, so this mode is CI-gateable across a whole org. Mutually exclusive with the `repo_root` positional argument and with `--baseline` / `--write-baseline`.

**GitHub-native findings (SARIF).** Both `scan` and `drift` accept `--sarif` to emit a SARIF 2.1.0 document to stdout, so findings surface in GitHub's Security tab and as inline PR annotations. `--sarif` takes precedence over `--json`/markdown and is built from the active report (root + every monorepo package) regardless of any `--no-*` output suppression. Scan SARIF includes size/truncation warnings, security findings, gaps, semantic mismatches, conflicts, and explicitly opted-in custom-rule findings; drift SARIF includes built-in and custom drift findings. Inventory, overlap candidates, nested-file inventory, and project snapshots remain evidence in JSON/Markdown rather than code-scanning findings. Legitimately baselined non-security debt is omitted; HIGH security findings always remain. Source levels map to SARIF levels (`HIGH`/`ERROR`→`error`, `MEDIUM`/`WARN`/`NOTICE`→`warning`, everything else→`note`).

```bash
# Emit SARIF 2.1.0 to a file for GitHub code scanning
npx ai-harness-doctor scan . --sarif > ai-harness-doctor.sarif
npx ai-harness-doctor drift . --sarif > drift.sarif
```

A reusable composite GitHub Action ships at the repo root (`action.yml`) so any repo can run the tool and upload SARIF in two steps:

```yaml
# .github/workflows/harness-sarif.yml (excerpt)
- uses: NieZhuZhu/ai-harness-doctor@v1
  with:
    command: scan
    path: .
- uses: github/codeql-action/upload-sarif@v4
  with:
    sarif_file: ai-harness-doctor.sarif
```

The example keeps major tags readable. In production workflows, pin external
Actions to a reviewed full commit SHA and keep the `owner/action@vN` major as an
adjacent update hint; Dependabot can then refresh the pin safely.

By default, the Action runs the implementation bundled with the selected Action ref, so the `uses:` version is the code that actually executes. Set the optional `version` input only when you intentionally want to run a different npm version or tag. Installation and CLI failures propagate to the workflow instead of leaving an empty SARIF file behind in a green job.

| Flag | Purpose |
|---|---|
| `--no-security` | Inventory only; skip the security checkup (drops the `security` key). |
| `--fail-on-security` | Exit `2` when any HIGH-severity security finding is present. |
| `--no-gaps` | Skip the missing / gap analysis (drops the `gaps` key). |
| `--fail-on-gaps` | Exit `3` when any ERROR-level harness gap is present. |
| `--no-semantic` | Skip the semantic consistency check (drops the `semantic` key). |
| `--fail-on-semantic` | Exit `4` when any AGENTS.md declaration contradicts the code. |
| `--fail-on-conflicts` | Exit `7` when any conflicting harness declaration is present. |
| `--baseline FILE` | Suppress only gap/semantic/conflict debt recorded in `FILE`; security is never suppressible. |
| `--write-baseline FILE` | Write the current non-security scan debt to a deterministic baseline and exit `0`. |
| `--no-snapshot` | Skip the project snapshot (drops the `project_snapshot` key). |
| `--no-report-file` | Do not write the full JSON report to a temp file (markdown mode only). |
| `--monorepo` | Force monorepo mode: scan each package subdir even without a workspace config (falls back to nested `package.json` / `AGENTS.md` subtrees). |
| `--no-monorepo` | Disable monorepo detection; scan only the repo root. |
| `--repos-file PATH` | Scan every repo listed in `PATH` and print a cross-repo summary instead of a single repo (see above). Mutually exclusive with `repo_root`. |
| `--rules DIR` | Load custom rule plugins from `DIR` (repeatable); merged into the `custom` section alongside `.ai-harness-doctor/rules/`. |
| `--no-custom` | Skip custom rule plugins (drops the `custom` key). |
| `--sarif` | Emit SARIF 2.1.0 JSON to stdout for GitHub code scanning (precedence over `--json`). |

`--json` returns (existing keys are unchanged — backward compatible):

```json
{
  "files": [],
  "warnings": [],
  "overlaps": [],
  "conflicts": [],
  "nested": [],
  "surface": {
    "mcp_servers": [],
    "subagents": [],
    "commands": [],
    "hooks": [],
    "permissions": []
  },
  "security": [
    { "level": "HIGH", "category": "secret", "path": "", "message": "" }
  ],
  "project_snapshot": {
    "tech_stack": [ { "language": "Go", "markers": ["go.mod"] } ],
    "existing_files": { "ci": [], "hooks": [], "lint_format": [], "typecheck": [], "drift_guard_hook": null },
    "agents_sections": [],
    "maintenance_contract": false,
    "mcp_tools": [],
    "has_permissions": false
  },
  "gaps": [
    { "check": "G1", "level": "ERROR", "item": "Root AGENTS.md", "message": "", "suggestion": "" }
  ],
  "custom": [
    { "level": "ERROR", "rule": "plugin-load", "plugin": ".ai-harness-doctor/rules/broken.py", "message": "", "suggestion": "" }
  ],
  "semantic": {
    "checked": 0,
    "mismatches": 0,
    "findings": [
      { "category": "command", "level": "MISMATCH", "line": 12, "declared": "npm run lint", "actual": "no such package.json script", "message": "", "suggestion": "" }
    ]
  }
}
```

`security` findings carry `level` (`HIGH`/`MEDIUM`), `category` (`secret`/`mcp`/`permission`/`hook`/`instruction`), `path`, and a human-readable `message`. With `--no-security` the `security` key is omitted. `gaps` entries carry `check` (`G1`–`G4`), `level` (`ERROR`/`WARN`/`NOTICE`), `item`, `message`, and `suggestion`; with `--no-gaps` the `gaps` key is omitted. `semantic` carries `checked` (declarations verified), `mismatches`, and `findings` (each with `category`, `level`, optional `line`, `declared`, `actual`, `message`, `suggestion`); with `--no-semantic` the `semantic` key is omitted. `project_snapshot` is omitted with `--no-snapshot`. `custom` holds findings from user rule plugins (each with `level`, `message`, `plugin`, `rule`, and optional `path`/`line`/`suggestion`); with `--no-custom` the `custom` key is omitted. In markdown mode the same JSON object is also written to `${TMPDIR}/harness-scan-<hash>.json` (unless `--no-report-file` is given). In monorepo mode the report also gains a top-level `packages` array and a `monorepo` summary.

</details>

<details>
<summary><code>plan</code></summary>

Scaffolds a Phase 1 merge plan from scan output: inventory, overlap clusters, conflict list, and a TODO decision checklist. It explicitly does **not** merge content or choose a side.

It also appends a **"Merge suggestions (semi-automatic)"** section derived from the scan:

- **Overlap consolidation** — each overlap cluster names the canonical file (`AGENTS.md`) and lists the files to reduce to stubs as a checkbox list.
- **Conflict resolutions** — each conflict signal gets ONE recommended value plus its supporting `path:line` evidence as a tickable item, together with a short **rationale**. The recommendation is deterministic and fact-aware: for `package_manager` it prefers the manager backed by the committed lockfile, for `node_version` it prefers the version pinned by `.nvmrc` / `engines.node`, and otherwise it falls back to the most-supported value (ties broken lexicographically).

These are suggestions for human review, not automatic adjudication; the existing inventory/overlap/conflict/TODO sections are preserved.

</details>

<details>
<summary><code>draft</code></summary>

Auto-drafts a **starter `AGENTS.md`** filled with concrete, fact-derived content instead of an empty skeleton. Invoked as `npx ai-harness-doctor draft <repo> [-o AGENTS.md]` (or directly as `python3 scripts/canonicalize.py <repo> --draft [-o AGENTS.md]`); a read-only passthrough of the scan, it never mutates the scanned repo.

The draft fills every canonical section (`Project overview`, `Build & test`, `Conventions`, `Testing requirements`, `Safety`, `Commit & PR`) using deterministic repository facts reused from `scan.py` / `semantic.py`:

- detected tech stack (from manifests such as `package.json`, `pyproject.toml`, …);
- build/test commands derived from `package.json` `scripts` and `Makefile` targets, using the package manager backed by the committed lockfile;
- detected CI, lint/format, and type-check tooling;
- **default resolutions for every conflict** scan reports (e.g. prefer the lockfile-backed package manager), each with a rationale.

Every inferred line is tagged `(inferred — confirm)` and safe conventions `(suggested default)`, and a banner reminds the human to review and edit before committing. Without `-o` it prints to stdout; with `-o PATH` it writes the file and refuses to overwrite an existing file unless `--force` is given.

</details>

<details>
<summary><code>validate</code></summary>

Validates the canonical `AGENTS.md` structure after you write it. It is a read-only passthrough to `scripts/canonicalize.py --validate`.

By default it requires the `Project overview`, `Build & test`, and `Conventions` headings. Pass `--require-sections` with your own comma-separated list to change which headings are mandatory (a missing one is reported as a `SECTION` finding):

```bash
python3 scripts/canonicalize.py --validate . --require-sections "Project overview,Build & test,Security"
```

</details>

<details>
<summary><code>stubs</code></summary>

Downgrades existing tool files to minimal pointers after `AGENTS.md` exists.

| Tool | Downgrade strategy |
|---|---|
| Claude | `CLAUDE.md` / `.claude/CLAUDE.md` import `@AGENTS.md`. |
| Cursor | `.cursorrules` points to `AGENTS.md`; `.cursor/rules` becomes one always-apply pointer. |
| Windsurf | `.windsurfrules` becomes a pointer. |
| Copilot | `.github/copilot-instructions.md` becomes a pointer. |
| Gemini | `GEMINI.md` becomes a pointer and recommends `contextFileName`. |
| Cline | `.clinerules` becomes a pointer. |
| Roo | Detected by `scan` (`.roo/rules/*.md`) but **not** downgraded — a rules-directory tool with no single conventional stub location, so it stays scan-only. |
| Continue | `.continuerules` points to `AGENTS.md`; `.continue/rules/*.md` is detected by `scan` but not downgraded. |
| Trae | Detected by `scan` (`.trae/rules/project_rules.md`) but **not** downgraded — same shape as Roo, no single conventional stub location. |

Dry-run by default. `--apply` requires a clean git tree; `--force` overrides that safety check.

Known tool config files are defined once in `assets/agent-tools.json`, the single registry that `scan`, `stubs`/`canonicalize`, and `drift` all read, so adding a new tool means editing that one file.

In the same spirit, the per-command Codex/Cursor/Gemini adapters under `adapters/` are generated from a single source: `scripts/gen_adapters.py` renders all 18 files (6 commands × 3 flavors) from one command table, `python3 scripts/gen_adapters.py --check` (also `npm run lint:adapters`) fails CI when a committed adapter drifts from that source, and `npm run gen:adapters` regenerates them.

</details>

<details>
<summary><code>drift</code></summary>

Checks `AGENTS.md` against repo reality. Exit code is 0 when no blocking drift is found, 1 when errors are found. `--strict` promotes notices to errors.

Example finding lines:

- D1: `Unknown package.json script test:unit-old`
- D2: `Referenced path src/old-components does not exist`
- D3: `Tool stub CLAUDE.md regrew or lost AGENTS.md pointer`
- D4: `AGENTS.md is 41000 bytes, above 32768`
- D5: `Nested AGENTS.md inventory` (informational, non-blocking)
- D6: `AGENTS.md declares Node 18 but .nvmrc pins 20` (fact drift)
- D7: `Markdown link target references/runbook.md does not exist` (Markdown-link drift)
- D8: `Competing package-manager lockfiles committed (package-lock.json, pnpm-lock.yaml)`

**Nested drift scopes.** D5 remains informational inventory, but every contained nested `AGENTS.md` it lists is also checked by D1/D2/D6/D7 with local facts/paths first and repository-root facts/paths as a conservative fallback for explicitly root-scoped guidance. Nested findings carry their canonical-file path through strict health, baselines, `--fix` manual guidance, SARIF, and PR review. D3/D4/D8 and custom plugins remain once-per-repository checks, and existing root findings keep their scope-less baseline identity.

**D6 fact drift** cross-validates the *facts* declared in `AGENTS.md` against repo ground truth: the Node version (vs `.nvmrc` and `package.json` `engines.node`) and the package manager (vs the actual lockfile — `package-lock.json`→npm, `pnpm-lock.yaml`→pnpm, `yarn.lock`→yarn). It only flags clear contradictions and stays silent when `AGENTS.md` is silent, so silence never produces a false positive.

**D7 Markdown-link drift** probes repo-relative Markdown link targets (`[text](path)`) in `AGENTS.md` and flags those pointing at a file or directory that no longer exists. It complements D2 (which only checks backtick-quoted tokens); URLs, in-page anchors, and out-of-repo targets are ignored, so it never probes outside the repo.

**D8 competing lockfiles** flags a repo that commits lockfiles for more than one package manager (e.g. both `package-lock.json` and `pnpm-lock.yaml`), which makes the intended manager ambiguous. It is reported for manual attention — the tool never guesses which lockfile to delete.

**Health score.** All findings (D1..D8) roll up into a 0–100 health score with a letter grade (A ≥90 / B ≥80 / C ≥70 / D ≥60 / F), rendered as a `## Health score` section (e.g. `Score: 85/100 (grade B)`). With `--json` the report gains `score` and `grade` keys alongside the existing fields.

`--min-score N` exits non-zero when the score is below `N` — a CI gate that is independent of `--strict`, so both can apply together.

**Semi-automatic repair: `--fix`.** `--fix` auto-repairs only the safe, mechanical subset of drift — currently **D3 stub regrowth**. Any tool stub that grew real content or lost its `AGENTS.md` pointer is rewritten back to its minimal canonical import-stub form (the stub bodies are reused from `canonicalize.py`, so `--fix` and `stubs`/`--write-stubs` stay in sync).

```bash
npx ai-harness-doctor drift . --fix          # DRY RUN: prints the diff, writes nothing
npx ai-harness-doctor drift . --fix --apply  # actually rewrites the regrown stubs
```

- Default `--fix` is a dry run: it prints a unified diff of what would be rewritten and changes no files.
- `--fix --apply` rewrites the regrown stub files in place.
- Non-safe drift (D1 command drift, D2 path drift, D4 size, D7 Markdown-link drift, D8 competing lockfiles, and any other semantic drift) is never modified; it is listed under **"needs manual attention"** with copy-pasteable repair guidance.
- A summary line reports `N fixed/fixable, M need manual attention`. The command exits non-zero while any drift remains.

</details>

<details>
<summary><code>eval</code></summary>

Runs or compares before/after agent tasks.

**Zero-config tasks.** You don't have to hand-write `tasks.json` — `--generate REPO` derives a deterministic task set from contained repository facts (`package.json` scripts/engines/deps, lockfiles, `.nvmrc`, `go.mod`, `pyproject.toml`, and `AGENTS.md` conventions), with a regex check encoding each true fact so a higher score directly reflects whether `AGENTS.md` helped. External symlink targets cannot supply facts, while safe in-repo symlinks keep their lexical evidence paths; ambiguous package-manager/runtime sources cause abstention instead of a guessed answer. Add `--target PATH` to evaluate one explicit nearest-file instruction scope: scripts/dependencies come only from that scope, package manager/runtime may use the nearest unambiguous ancestor, and canonical conventions inherit root → nearest. Scoped IDs are percent-encoded and each task carries repository-relative `scope`, `target`, and `evidence`. Root generation stays compatible; all-scope expansion is deliberately not automatic.

```bash
npx ai-harness-doctor eval --generate . -o tasks.json   # auto-generate tasks from repo facts
npx ai-harness-doctor eval --generate . --target packages/api/src/index.ts -o api-tasks.json
```

`tasks.json` is an array of task records:

```json
[
  {
    "id": "test",
    "prompt": "What test command should I run? Answer with ONLY the exact command/value, no explanation.",
    "check": { "type": "regex", "value": "pnpm\\s+(run\\s+)?test\\b" },
    "timeout_s": 60
  }
]
```

Checks can be `regex` over the extracted answer, `command` executed in the workdir, or `judge` for open-ended LLM-as-judge grading. Before run, multi-round, matrix, regrade, or strict score does anything else, the complete task array is validated: every task needs a unique non-empty `id`, a non-empty `prompt`, a supported `check` object, and (when present) a finite positive `timeout_s` plus valid evidence/judge fields. An invalid pack exits `2` with a concise `task error` before any runner, LLM/judge, evidence hash, result write, or baseline update; prompts and task contents are never echoed in the diagnostic. For Claude CLI JSON output, grading extracts the `result` field before matching. Usage/cost fields are captured when present. `--compare before.json after.json` writes a Markdown comparison. `--regrade results.json --tasks tasks.json` regrades recorded outputs offline. With `--workdir`, run, matrix, and regrade automatically stamp every source listed in task-level `evidence`; repeatable `--evidence FILE` adds manual or extra sources. Files retain exact SHA-256 fingerprints, while directories bind only their repository-relative path, existence, and type—not recursive child bytes. At score time, `--require-current-evidence` derives the task sources again from the same `--tasks` file, combines any repeated explicit evidence, and rejects stale results (exit `7`) before checking health. Hand-written tasks with no declared or explicit evidence keep the legacy unstamped behavior, and old unstamped results remain scoreable without the strict flag. If the runner binary is missing, the command prints a manual protocol fallback instead of pretending it ran.

**Multi-agent matrix.** Run the same task set across several runners ("agents") and compare them side by side. Provide runners inline with repeatable `--runner-cmd NAME=CMD`, or via `--matrix agents.json` (a mapping of agent name → runner command template). `--matrix-report FILE` writes a Markdown matrix (rows = tasks, columns = agents, cells = pass/fail + duration, plus per-agent pass-rate summary) and `--matrix-json FILE` writes per-agent task records with a `summary` block (`passed`, `total`, `pass_rate`). The single-runner before/after/compare flow is unchanged; matrix mode activates only when `--matrix` and/or `--runner-cmd` are supplied.

```bash
npx ai-harness-doctor eval --tasks tasks.json --workdir . \
  --runner-cmd "claude=claude -p {prompt} --output-format json" \
  --runner-cmd "codex=codex exec {prompt}" \
  --matrix-report matrix-report.md --matrix-json matrix-results.json
```

**LLM-as-judge check.** A task check may use `{ "type": "judge", "rubric": "..." }` for grading that regex cannot express. When `--judge-cmd "CMD_TEMPLATE"` is provided it takes priority: the judge receives env `JUDGE_ANSWER`, `JUDGE_RUBRIC`, and `JUDGE_INPUT` (path to a temp JSON `{answer, rubric}`), and template placeholders `{answer}`/`{rubric}`/`{input}` are substituted. It must print `{"passed": bool, "score": number, "reason": "..."}`; if `passed` is omitted, `score >= 0.5` counts as a pass. An offline deterministic judge works for CI.

**Real-LLM & built-in judge.** When no `--judge-cmd` is supplied, `judge` checks can be graded by a real LLM via `--judge-llm {auto,openai,claude,off}` (default `off` — the deterministic built-in keyword judge, so an ambient API key never silently reroutes grading to a real model; opt in explicitly with `auto`): `auto` calls OpenAI when `OPENAI_API_KEY` is set, else Claude when `ANTHROPIC_API_KEY` is set, using only the Python standard library (no SDKs). Model/endpoint are configurable via `OPENAI_MODEL`/`OPENAI_BASE_URL`, `ANTHROPIC_MODEL`/`ANTHROPIC_BASE_URL`, or `--judge-model`. Any failure (no key, network, malformed reply) transparently falls back to a deterministic, dependency-free built-in keyword judge (verdict `{passed, score, reason, judge:"builtin"}`; LLM verdicts are tagged `judge:"llm:openai"`/`"llm:claude"`). The keyword judge grades in priority order: `check.expect` — regex patterns that must ALL match (case-insensitive); `check.reject` — patterns that must NOT match; otherwise keyword coverage from the free-text `check.rubric` / `check.criteria`, passing at `>= check.min_score` (default `0.5`). Pass `--judge-llm off` for keyword-only grading, or `--no-default-judge` to require an external `--judge-cmd`.

```bash
npx ai-harness-doctor eval --tasks tasks.json --workdir . --label after --judge-llm auto   # real LLM judge, keyword fallback
```

**Health score.** Every eval also computes a one-click efficacy health score = pass rate across all task records, expressed `0–100` with an A–F letter grade (A ≥90 / B ≥80 / C ≥70 / D ≥60 / F). It is embedded as a `health` key in both single-run results (`{"tasks":...}`) and matrix results (`{"agents":...}`), and printed as a summary line (`health score: N/100 (grade X), P/T tasks passed`). Timeouts count as failures. `--score PATH` prints the health score for an existing results/matrix JSON (add `--json` for machine output), and `--fail-under N` exits code `5` when the health score is below `N` (a CI gate).

**Multi-round stability (`--rounds`).** `--rounds N` (N > 1) runs the whole task set N times and aggregates stability statistics, which is how you surface *flaky* tasks that pass on some runs and fail on others. The results JSON then carries `rounds`, `round_results` (each round's full task records + per-round `health`), a per-task `task_stats` array (`runs`, `passed`, `failed`, `timed_out`, `pass_rate`, `flaky`), and a `stats` summary (`mean_health`, `variance`, `stddev`, `min_health`, `max_health`, `health_scores`, `flaky_tasks`, `flaky_count`). A task is `flaky` when it neither passes every round nor fails every round. Overall `health` is the pass rate across every task-run, and `--fail-under N` gates on it. `--rounds 1` (the default) keeps the legacy single-round output shape byte-for-byte unchanged. `--stats PATH` re-aggregates an existing multi-round results file offline (add `--json` for machine output, `--fail-under N` to gate).

```bash
npx ai-harness-doctor eval --tasks tasks.json --workdir . --label nightly --rounds 5   # run 5x, aggregate stability stats
npx ai-harness-doctor eval --stats results-nightly.json --json                         # re-analyze an existing multi-round file
```

**Baseline, trend & regression.** Persist each run's health as an append-only baseline history (`--baseline FILE` + `--save-baseline`), recording timestamp, label, score/grade, pass counts, and the target repo's git commit/branch. `--check-regression` compares the current score to the most recent prior snapshot and exits `6` when it drops by at least `--regression-threshold` points (default `5`); `--trend FILE` renders the history as a Markdown table with per-snapshot deltas and regression flags. It composes with any run mode and with `--score`.

```bash
npx ai-harness-doctor eval --tasks tasks.json --workdir . --label after -o results.json \
  --baseline baselines/history.json --save-baseline --check-regression   # save + gate on regressions
npx ai-harness-doctor eval --trend baselines/history.json                  # render the recorded trend
```

</details>

<details>
<summary><code>explain</code></summary>

Explains the instruction evidence relevant to one contained file, directory, or future path:

```bash
npx ai-harness-doctor explain . packages/api/src/handler.ts
npx ai-harness-doctor explain . packages/api/src/future.ts --json
```

The schema-version-1 JSON contains `target`, `effective_scope`, root→nearest `canonical_chain`, `diagnostic_sources`, relevant `scope_overrides` / same-scope `conflicts`, and explicit `limitations`. Existing and future paths are accepted; contained absolute paths are normalized to repository-relative paths. Escapes and external-symlink targets fail closed. Targets under `.git`, `node_modules`, `dist`, `build`, or `__pycache__` are marked `excluded_by_scan`, because configs inside those subtrees are not inventoried.

Only canonical files are described as the effective inheritance chain. Cursor, Copilot, Claude, and other recognized configs are **diagnostically associated**, not claimed effective: this command does not infer tool-specific glob/frontmatter/prose applicability, merge instruction text, execute plugins, or modify files.

</details>

<details>
<summary><code>mcp</code></summary>

Starts an MCP (Model Context Protocol) stdio server so agents can call the doctor's read-only capabilities as tools.

```bash
npx ai-harness-doctor mcp   # or directly: node bin/mcp-server.js
```

Transport is JSON-RPC 2.0 over newline-delimited JSON (one JSON object per line on stdin/stdout). Supported methods:

- `initialize` → negotiates stable MCP `2025-11-25` or legacy `2024-11-05` from the client's requested `protocolVersion` and returns `{ protocolVersion, capabilities: { tools: {} }, serverInfo: { name, version } }`; unsupported versions receive the server's latest stable version.
- `notifications/initialized` → notification, no response.
- `tools/list` → advertises `harness_scan`, `harness_drift`, `harness_validate`, `harness_plan`, `harness_stubs`, `harness_eval_generate`, `harness_explain`, each with a closed input schema.
- `tools/call` → dispatches to the matching Python script and keeps the human/tool output in `content[0]`; `content[1]` is a compact JSON metadata text block with `{ kind, exitCode, ok, status, report? }`. Under MCP `2025-11-25`, the same metadata is also returned as standard `structuredContent`; under `2024-11-05` it remains text-only.

Tool arguments: `harness_scan` (`json`), `harness_drift` (`json`, `strict`), `harness_validate` (`json`), `harness_plan`, `harness_stubs`, `harness_eval_generate` (optional `target`), and `harness_explain` (required `target`, optional `json`). All seven tools are read-only; `harness_stubs` never receives `--apply`, `harness_eval_generate` never receives `-o` or runs an agent/LLM, and `harness_explain` never executes plugins or writes. Each advertised input schema rejects missing required fields, unknown properties, and wrong types before Python starts. Modern tools also advertise read-only/non-destructive/idempotent/closed-world annotations and a typed result-envelope `outputSchema`; legacy tools omit fields their protocol does not define. Metadata `status` is `ok`, `findings`, or `error`: explicitly requested valid JSON finding reports remain available with `isError: false`, while invalid targets, runtime failures, timeouts, malformed reports, and conservatively ambiguous non-zero text reports set `isError: true`. For backward compatibility, a client that calls tools before initialize gets the historical 2024 result shape; valid initialize handshakes select the wire version for the connection. Unknown methods/tools and invalid arguments return JSON-RPC error objects. The server remains stdio-only and does not advertise roots, resources, prompts, sampling, or HTTP transport.

</details>

<details>
<summary><code>doctor</code></summary>

Single-entrypoint runtime self-test for the dual Node + Python runtime. It resolves the Python interpreter through the same shared resolver the Python-backed subcommands use, then reports Node, the resolved Python 3 interpreter, every Python engine, and the MCP server file. It exits non-zero when any check fails.

```bash
npx ai-harness-doctor doctor --self-test   # human-readable runtime table
npx ai-harness-doctor doctor --json        # machine-readable runtime report
```

Python is discovered in priority order: `AI_HARNESS_DOCTOR_PYTHON`, then `PYTHON`, then `python3`, then `python`; only a Python **3** interpreter is accepted. When it is missing, every Python-backed subcommand (`scan`, `explain`, `plan`, `validate`, `stubs`, `drift`, `review`, `eval`) fails with the same clean, actionable message — install Python 3 or set `AI_HARNESS_DOCTOR_PYTHON` — instead of a raw stack trace.

</details>

Slash command quick refs: `/harness-doctor` full pipeline; `/harness-scan` Phase 0; `/harness-treat` Phase 1; `/harness-drift` Phase 2; `/harness-eval` Phase 3; `/harness-explain` target-path scope evidence.

Environment variables:

| Variable | Purpose |
|---|---|
| `AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1` | Disable the once-daily npm update nudge. |
| `AI_HARNESS_DOCTOR_SKIP=1` | Explicitly bypass the local pre-commit drift hook. |
| `AI_HARNESS_DOCTOR_PYTHON` | Pin the Python 3 interpreter used by every Python-backed subcommand. |

`AI_HARNESS_DOCTOR_FORCE_UPDATE_CHECK` and `AI_HARNESS_DOCTOR_REGISTRY` are internal/testing knobs.

## Benchmark

Final verified results from [`benchmark/results/`](benchmark/results/):

| Side | Runs | Passed | Flip-flop tasks | Avg latency/task | Total captured cost |
|---|---|---:|---:|---:|---:|
| BEFORE: conflicting/stale configs | 14 objective tasks × 2 runs | 6/28 (21%) | 2 | 16.0s | $5.82 |
| AFTER: canonical `AGENTS.md` via this tool | 14 objective tasks × 2 runs | 28/28 (100%) | 0 | 11.7s | $4.81 |
| Delta | after - before | +22 correct attempts | -2 | -27% | -17% |

Conflicting configs do not just cause wrong answers; they cause **unstable** answers: the same question flipped between runs for `node` and `moduletype` before canonicalization, and never flipped after.

See [`benchmark/README.md`](benchmark/README.md) for methodology, tasks, grading, and reproduction commands. Honest scope: one demo repo, N=2 runs per side, objective Q&A tasks, runner `claude -p` with Claude CLI 2.1.202.

## Positioning & Non-goals & Comparison

### Positioning

AI Harness Doctor is complementary to Claude Code's official `/init`: `/init` bootstraps a config from scratch, while AI Harness Doctor diagnoses, consolidates, guards, and validates an existing sprawl. Its `SKILL.md` explicitly stays out of `/init`'s lane.

Regeneration and guarding are two valid philosophies. Ruler/rulesync make generated outputs disposable; AI Harness Doctor keeps `AGENTS.md` human-owned and guards it against drift. That is why it prefers detection over silent regeneration: when the repo changes, the team should know the agent contract changed too.

### Non-goals

- No from-scratch init; that is `/init`'s lane.
- Never adjudicates conflicts silently; it shows file:line evidence and asks a human.
- Scripts never do semantic merging.
- No unattended writes: dry-run defaults, `--apply`, and clean-tree checks are intentional.
- No language/framework style-guide generation.
- Not a bulk rules distributor; for 20+ tool fan-out, use rulesync and see the comparison below.
- No telemetry. The only network call is the once-daily npm version check, and it is disable-able.

### Comparison

Legend: ✅ built-in / △ partial or different approach / ❌ not a stated feature.

| Dimension | AI Harness Doctor | [Ruler](https://github.com/intellectronica/ruler) | [rulesync](https://github.com/dyoshikawa/rulesync) |
|---|---|---|---|
| Canonical-source model | △ `AGENTS.md` itself is canonical + minimal stubs. | △ `.ruler/` central source distributes to agent-specific files. | △ `.rulesync/` unified rules generate to 20+ tools. |
| Consolidate FROM existing configs | ✅ Treat phase consolidates existing configs. | ❌ Not a stated feature in their docs. | ✅ Reverse IMPORT from existing `CLAUDE.md` / `.cursorrules`. |
| Conflict detection with file:line evidence | ✅ Scan/plan reports cite file:line evidence. | ❌ Not a stated feature in their docs. | ❌ Not a stated feature in their docs. |
| Overlap % metrics | ✅ Built into scan reports. | ❌ Not a stated feature in their docs. | ❌ Not a stated feature in their docs. |
| Size/truncation warnings | ✅ Built into scan/drift. | ❌ Not a stated feature in their docs. | ❌ Not a stated feature in their docs. |
| Re-divergence guard on hand-edited files | ✅ D3 drift guard catches stub re-divergence. | △ Solves the problem differently by regeneration. | △ Solves the problem differently by regeneration. |
| CI / pre-commit gate | ✅ `guard` suite installs pre-commit, PR gate, and weekly checkup. | △ Can regenerate in CI. | △ Can regenerate in CI. |
| Before/after efficacy eval with real benchmark | ✅ See [`benchmark/`](benchmark/). | ❌ Not a stated feature in their docs. | ❌ Not a stated feature in their docs. |
| Distribution breadth | △ 4 agents + universal pointer. | ✅ Multiple agent-specific outputs. | ✅ 20+ tools. |
| MCP config propagation | ❌ Not supported. | ✅ Built-in MCP config propagation. | ❌ Not a stated feature in their docs. |

As of 2026-07, based on each project's public documentation — see their repos for the latest.

## Releases

- Releases are tag-driven through CI with npm provenance.
- Each release self-tests the tagged Action before npm publish, moves the matching floating major Action tag (`v1` for `1.x`), verifies it as a consumer would, and opens a Marketplace confirmation reminder.
- See [`RELEASING.md`](RELEASING.md).
- Every published version has a git tag.

## Repository layout

```text
SKILL.md                         # Skill playbook and phase stop conditions
bin/cli.js                       # npm CLI and installer
bin/mcp-server.js                # MCP stdio server (scan/drift/validate/plan/stubs/eval_generate/explain)
commands/                        # Claude Code slash commands
adapters/                        # Codex, Cursor, Gemini, universal pointers
scripts/                         # Python stdlib deterministic mechanics
references/                      # Migration and conflict-resolution references
assets/                          # Templates, guard suite, example tasks
benchmark/                       # Real before/after eval data
tests/                           # stdlib unittest suite
RELEASING.md                     # Tag-driven release checklist
```

## Roadmap v2

- Repo harness-ification: CLI-ize project scripts, add verification gates, and layer docs cleanly.
- Richer eval task packs for more languages, repo shapes, and multi-turn workflows.
- More agent adapters as command formats stabilize.
- Antigravity CLI adapter when its custom-command format is documented.

## Contributing

Bug reports and focused PRs are welcome. Use the repository's issue forms, read [`SUPPORT.md`](SUPPORT.md) for routing, follow [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md), and report vulnerabilities privately through [`SECURITY.md`](SECURITY.md)—never paste secrets, private repository content, or exploit details into a public issue. Keep scripts deterministic, stdlib-only, and covered by:

```bash
python3 -m unittest discover -s tests -v
```

The repo also ships an npm-driven lint/format/test workflow (dev-only; none of it is bundled into the published package). CI runs the full suite across a Python (3.9/3.10/3.12) and Node (16/20/22) version matrix:

```bash
npm test            # Python unittest + node --test CLI suite
npm run lint        # eslint (bin) + ruff (scripts/tests) + trilingual README structure sync
npm run format      # prettier --write .   (npm run format:py for ruff format)
```

`npm run lint:docs` (aka `scripts/check_readme_sync.py`) enforces that `README.md`, `README.zh-CN.md`, and `README.ja.md` keep an identical heading skeleton, so any structural change to one README must be mirrored in the other two.

## License

MIT. Copyright (c) NieZhuZhu.
