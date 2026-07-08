---
name: ai-harness-doctor
description: Audit, canonicalize, guard, and evaluate a repository's AI harness configuration layer around AGENTS.md; triggers include AGENTS.md, CLAUDE.md, .cursorrules, copilot-instructions, 迁移/统一/整理 agent 配置、agent 配置体检, agent config drift, consolidate agent configs, and AI harness audit.
---

# ai-harness-doctor

One-line purpose: run a repository's AI harness configuration through Checkup -> Treat -> Follow-up -> Efficacy, consolidating scattered or drifting agent instructions into the single source of truth `AGENTS.md` and keeping them guarded over time.

## When to use

- The repository contains multiple rule files, such as `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `.cursor/rules/*.mdc`, `.windsurfrules`, `.github/copilot-instructions.md`, `GEMINI.md`, or `.clinerules`.
- The user asks to migrate, unify, or organize agent configs; run an agent config checkup; check agent config drift; consolidate agent configs; or audit an AI harness.
- Tool-specific configs need to be downgraded to minimal stubs pointing at `AGENTS.md`, with CI or pre-commit drift guards added afterward.

## When not to use

- Do not initialize an empty repository from scratch; that overlaps with the official `/init` flow.
- Do not perform a full harness-platform refactor, such as converting scripts into a CLI, adding validation gates, or redesigning documentation layers; those belong to v2.
- Do not generate language- or framework-specific standards from scratch, such as React, Go, or Python rules; those belong to v2 or a project-specific effort.
- Do not adjudicate semantic conflicts for the user. Scripts perform deterministic mechanical actions only; the agent guides human review for semantic merging, deduplication, and conflict resolution.

## Phase 0 — Checkup (Scan)

### Inputs

- Target repository root.
- Optional size threshold, defaulting to `32768` bytes, a common Codex `project_doc_max_bytes` default.

### Actions

Run the read-only scan:

```bash
python3 scripts/scan.py /path/to/repo
python3 scripts/scan.py /path/to/repo --json
```

The scan checks the configuration-file inventory, size warnings, overlap candidates, conflict candidates, and nested `AGENTS.md` files.

### Outputs

- A human-readable Checkup report.
- `--json` machine output with `files`, `warnings`, `overlaps`, `conflicts`, and `nested`.

### Explicit stop condition

Stop at migration-scope confirmation: whole repository, subdirectory, or selected files. Do not enter Treat before the scope is confirmed.

## Phase 1 — Treat (Canonicalize)

### Inputs

- Phase 0 report.
- User-confirmed migration scope.
- Human-adjudicated conflict decisions.

### Actions

First generate the merge-plan skeleton:

```bash
python3 scripts/canonicalize.py --plan /path/to/repo -o merge-plan.md
```

Then the agent manually writes the root `AGENTS.md`. The scripts do not perform semantic merging.

After `AGENTS.md` exists, preview or apply tool-stub downgrades:

```bash
python3 scripts/canonicalize.py --write-stubs /path/to/repo
python3 scripts/canonicalize.py --write-stubs /path/to/repo --apply
```

Writes are dry-run by default. Before `--apply`, the target must be a git repository with a clean worktree; use `--force` only when the user explicitly accepts that override.

Finally validate:

```bash
python3 scripts/canonicalize.py --validate /path/to/repo
python3 scripts/canonicalize.py --validate /path/to/repo --json
```

### Outputs

- Canonical root `AGENTS.md`.
- Minimal tool stubs: `CLAUDE.md`, `.cursorrules`, `.windsurfrules`, `.cursor/rules/agents-md.mdc`, `copilot-instructions`, `GEMINI.md`, and `.clinerules`.
- Validation report.

### Explicit stop condition

Stop when all conflicts have been human-adjudicated. Never silently decide between contradictory rules; list the conflict, evidence, and recommendation, then ask the user or repository owner to decide.

## Phase 2 — Follow-up (Drift Guard)

### Inputs

- Canonicalized target repository.
- Root `AGENTS.md` and tool stubs.

### Actions

Run the drift guard:

```bash
python3 scripts/check_drift.py /path/to/repo
python3 scripts/check_drift.py /path/to/repo --json
python3 scripts/check_drift.py /path/to/repo --strict
```

Checks:

- D1: command drift, comparing referenced commands against `package.json` scripts and `Makefile` targets.
- D2: path drift, checking whether backtick-quoted paths exist.
- D3: stub re-divergence, checking size and the `AGENTS.md` pointer.
- D4: `AGENTS.md` size.
- D5: nested `AGENTS.md` inventory, informational and non-blocking.

### Outputs

- Drift report.
- CI- and pre-commit-friendly failing exit codes.
- Repair advice that points to the category to fix and usually the line to inspect.

### Explicit stop condition

Stop when checks pass or repair advice has been provided. Do not rewrite semantic content during Follow-up.

### Long-term follow-up

After Treat completes and root `AGENTS.md` exists, install the long-term guard suite with `npx ai-harness-doctor guard /path/to/repo --apply`.
It installs only the core suite: pre-commit drift hook, CI drift/checkup gate, and `AGENTS.md` maintenance contract.
The CI gate is **provider-aware** — pass `--provider github|gitlab|codebase` (default `auto`, detected from the git remote / `.gitlab-ci.yml`):
- `github` → `.github/workflows/harness-drift.yml` + `harness-checkup.yml`
- `gitlab` → includable `.gitlab/harness-ci.yml` (add `include: { local: .gitlab/harness-ci.yml }`)
- `codebase` → portable `.harness-ci/harness-guard.sh` + wiring `README.md` for internal Codebase / Bits / any runner
Remove it with `npx ai-harness-doctor guard /path/to/repo --remove --apply` (cleans up all providers' CI files); Claude hooks are not integrated.

## Phase 3 — Efficacy (Eval)

### Inputs

- Fixed task file `tasks.json`.
- Before and after labels plus the target repository.
- Runner template, for example `claude -p {prompt} --output-format json`.

### Actions

Run tasks:

```bash
python3 scripts/eval_run.py --tasks tasks.json --label before --workdir /path/to/repo -o results-before.json
python3 scripts/eval_run.py --tasks tasks.json --label after --workdir /path/to/repo -o results-after.json
```

Compare results:

```bash
python3 scripts/eval_run.py --compare results-before.json results-after.json -o eval-report.md
```

If the runner is missing, the script prints a manual protocol instead of pretending to run an eval.

### Outputs

- Before and after JSON results.
- Markdown comparison report with pass rate, duration, and token or cost data when the runner provides it.

### Explicit stop condition

Stop when metrics have been produced. The report should answer whether this `AGENTS.md` made agent behavior more stable.

## Decision rules

### What belongs in AGENTS.md

- Only information the agent cannot directly infer from code, manifests, or CI configuration.
- Stable conventions: project structure, required commands, dangerous operations, safety boundaries, and PR or commit conventions.
- Progressive disclosure: put details in `references/`; keep only entry points and critical rules in `AGENTS.md`.

### What does not belong in AGENTS.md

- Do not wholesale-copy package scripts, README content, or framework-default standards.
- Do not keep long lists that will go stale unless a drift guard can validate them.
- Do not copy tool-stub bodies.

### When a monorepo needs local subdirectory AGENTS.md files

- Subprojects have materially different languages, commands, or safety boundaries.
- Subdirectories have independent owners or release processes.
- Root `AGENTS.md` holds global rules; local `AGENTS.md` files hold only subtree-specific differences.

### Conflict-resolution escalation path

1. Factual conflicts: prefer manifests, CI, and live code as evidence.
2. Preference conflicts: send to the owner for adjudication; the agent does not decide.
3. Stale rules: cite the source and recommend deletion, but still require confirmation.
4. Unknown cases: keep them in the plan's conflict list and block Treat completion.

## Named anti-patterns

### Wholesale Dumping

Symptom: all old content is copied verbatim into `AGENTS.md`.

Correction: keep only non-inferable rules; replace duplicated facts with references to manifests or `references/`.

### Silent Adjudication

Symptom: after finding `pnpm install` vs `npm install`, the agent chooses one directly.

Correction: list file:line evidence and ask the user or owner to adjudicate.

### Copy-Paste Stubs

Symptom: stubs copy the full rules again, causing another fork.

Correction: stubs must be pointers or imports only, with no rule body retained.

### Silent Truncation

Symptom: 32KB or 12KB size warnings are ignored.

Correction: split details into references and keep `AGENTS.md` small and deep.

### Big-Bang Migration

Symptom: all files are changed at once without phases or checkpoints.

Correction: proceed strictly through Checkup, Treat, Follow-up, and Efficacy, with a stop condition at each phase.

## References index

- `references/tool-matrix.md`: tool-specific read files, import support, priority, and downgrade strategy.
- `references/section-template.md`: recommended `AGENTS.md` section structure.
- `references/migration-decision-tree.md`: migration-scope decision tree.
- `references/conflict-resolution.md`: conflict categories, resolution rules, and escalation format.
- `assets/AGENTS.template.md`: English `AGENTS.md` template.
- `assets/guard/`: long-term follow-up guard suite templates: pre-commit, PR gate, weekly checkup, and maintenance contract.
- `commands/`: Claude Code slash commands routed to this skill by phase.
- `adapters/`: thin pointer templates for Codex, Cursor, Gemini, and universal agents.
- `bin/cli.js`: npm CLI, installer, and forwarding entry point for Python scripts.
