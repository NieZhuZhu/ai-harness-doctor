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
python3 scripts/scan.py /path/to/repo --fail-on-security   # non-zero exit on HIGH findings
python3 scripts/scan.py /path/to/repo --fail-on-semantic   # non-zero exit on declaration/code mismatch
python3 scripts/scan.py /path/to/repo --fail-on-conflicts  # exit 7 on live declaration conflicts
python3 scripts/scan.py /path/to/repo --no-security        # inventory only
python3 scripts/scan.py /path/to/monorepo --json           # auto-detects workspaces
python3 scripts/scan.py /path/to/repo --monorepo           # force per-package scan
python3 scripts/scan.py /path/to/repo --rules ./my-rules   # add custom rule plugins (also reads .ai-harness-doctor/rules/)
python3 scripts/scan.py /path/to/repo --sarif              # emit SARIF 2.1.0 JSON for GitHub code scanning
python3 scripts/scan.py /path/to/repo --write-baseline .ai-harness-doctor/scan-baseline.json
python3 scripts/scan.py /path/to/repo --baseline .ai-harness-doctor/scan-baseline.json \
  --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts
```

The repository-root composite `action.yml` wraps the same SARIF path for GitHub Actions. Its default `version: bundled` executes the implementation shipped in the selected Action ref, so `uses: owner/repo@tag` pins the code that actually runs; an explicit npm version/tag remains available as an override. Invalid commands, installation errors, and CLI failures propagate as failing Action steps rather than being hidden behind an empty SARIF artifact. Required self-test covers current bundled `scan`/`drift` plus an exact already-published npm override; the first two prove PR source, while the latter proves install compatibility. Release automation derives a floating tag from the package major (`1.x` → `v1`), runs both bundled commands before npm publish, then checks out the remote major tag and verifies its bundled scan plus the exact newly published npm drift override after publish. Every success path checks the SARIF driver version and keeps npm installation under `RUNNER_TEMP`; older major tags are preserved.

The scan checks the configuration-file inventory, size warnings, overlap candidates, conflict candidates, and nested `AGENTS.md` files. It also inventories the **extended harness surface** — MCP servers, subagents, slash commands, hooks, and permission rules — and runs a **security checkup** that flags plaintext secrets, overly broad permission rules (e.g. `Bash(*)`, `bypassPermissions`), insecure MCP transports, and risky hook bodies (`curl … | bash`, `rm -rf`, `--dangerously-skip-permissions`). It additionally runs a **semantic consistency** check (via `scripts/semantic.py`) that cross-checks the concrete claims in `AGENTS.md` — build/test commands, repo-relative paths, the package manager, and the Node.js version — against ground truth in `package.json`, `Makefile`, the filesystem, lockfiles, and `.nvmrc` / `engines.node`, surfacing declaration-vs-code mismatches at checkup time.

`--max-bytes` is a semantic evidence budget, not a security boundary. For an oversize recognized instruction file, the scanner retains only that prefix for overlap/conflict/override/semantic analysis, but streams the complete contained file for SHA-256, line count, secret labels, and permission-bypass labels. JSON exposes per-file `analyzed_bytes`, `truncated`, `security_scanned_bytes`, plus top-level `analysis_limits`; Markdown and explain reports state when a conclusion is prefix-only. Never infer that an unseen tail is clean from an empty bounded-semantic result.

The scanner's filesystem boundary is the audited repository root: repository-derived configs, manifests, workspace metadata, semantic facts, and default rule plugins are used only when their resolved targets remain inside that root. In-repo file symlinks stay supported and retain their lexical repo-relative report path. Explicit `--rules DIR` locations remain an intentional opt-in and may live outside the repository.

Repository mutation is stricter than scanning: `stubs --apply`, `drift --fix --apply`, and `guard --apply` / `--remove --apply` refuse a repository-derived target when the file itself or any existing parent directory is a symlink. They never follow a symlink to rewrite/delete another location. Explicit output arguments such as `draft -o PATH`, `--write-baseline FILE`, and eval result paths remain user-selected destinations and are not inferred repository mutations.

Installer mutation follows the same ownership principle. Copy payloads live under the dedicated `.ai-harness-doctor/payload/` subtree so repository baselines and custom rules are never treated as disposable package files. The versioned install manifest records every managed file/link and its digest/target. Existing malformed/unsupported manifest state or symlinked state paths fail closed without overwriting ownership evidence; valid state is atomically replaced. Install/update preserve unowned name collisions and user-edited managed files; uninstall removes only pristine owned outputs and keeps shared payloads until no installed agent references them. Legacy manifests are adopted only where existing bytes match the package-generated output.

**Monorepo / multi-package awareness.** `scan` is monorepo-aware. When it detects a workspace — npm/yarn/pnpm `workspaces` in `package.json`, a `pnpm-workspace.yaml`, or (with `--monorepo`) multiple nested `package.json` / `AGENTS.md` subtrees — it scans each detected package subdirectory too and reports per-package results plus a top-level aggregate. In markdown a `## Monorepo` section is added; in `--json` the report gains a `packages` array (one entry per package, each with the full single-repo scan shape under `report` plus a `summary`) and a `monorepo` object (`source`, `package_count`, `aggregate`). Single-repo behavior is unchanged when no workspace is detected; `--no-monorepo` forces a root-only scan.

**Nested instruction scopes.** Conflict detection implements the AGENTS.md nearest-file hierarchy mechanically: canonical file parent directories are lexical scopes, configs belong to their deepest canonical ancestor, same-scope disagreements are blocking `conflicts`, and ancestor → descendant differences are non-blocking `scope_overrides` (siblings are independent). JSON adds `instruction_scopes` and `scope_overrides`; Markdown and Treat plans preserve override evidence, while only true scoped conflicts enter baselines, SARIF, PR review, and exit `7`. Root conflict shape stays compatible; non-root conflicts add `scope`. No file-type, glob/frontmatter, external-repository, or prose scope is inferred.

**Adopting scan gates with existing debt.** `--write-baseline FILE` records the current gap, semantic, and conflict findings as a deterministic, timestamp-free debt register; `--baseline FILE` keeps those findings visible in a top-level `baselined` array and Markdown summary while excluding them from fail-on gates and SARIF. Stable identities include the family/rule, root-or-package scope, path/evidence, and structured values; line numbers are evidence, never identity. HIGH security findings are structurally excluded and remain active even if a baseline is hand-edited to contain a security-shaped entry. A missing/malformed baseline suppresses nothing. Commit and review the file, then shrink it as debt is repaired—never use it as an opaque ignore list. Monorepos preserve root/package attribution; `--repos-file` rejects baseline composition because each unrelated repository must own its own register.

**Multi-repo coverage is fail-closed.** `scan --repos-file PATH` continues
through every reachable repository and preserves all successful reports, but
any listed path that cannot be scanned contributes to `summary.error_count` and
prevents exit 0. Operational-only batch failure exits 8 after rendering; scan
finding exits retain precedence (`2` security, `3` gaps, `4` semantic, `7`
conflicts). Batch operational errors are summary-only in PR review and use a
safe repository label rather than the local resolved path.

**SARIF finding completeness.** `scan --sarif` maps every active finding family—size/truncation warnings, security, gaps, semantic mismatches, conflicts, and explicitly enabled custom rules—at root and monorepo-package scope. `drift --sarif` maps built-in and custom drift findings. Baselined debt is excluded; inventory, overlap candidates, nested-file inventory, and project snapshots remain JSON/Markdown evidence rather than findings.

**Custom rule plugins (user-extensible).** Both `scan` and `check_drift.py` can be extended with your own DETERMINISTIC rules via `scripts/plugins.py`. Rule modules are loaded from the target repo's `.ai-harness-doctor/rules/*.py` directory and/or any explicit `--rules DIR` (repeatable). Each module exposes a single function `check(root, context) -> list[dict]`, where `root` is the repo `Path` and `context` is a read-only dict containing at least `phase` (`"scan"`/`"drift"`) and `agents_text`. Findings need `level` and `message` and may add `path`, `line`, `suggestion`, and a `rule` id; they are merged into the report under a `custom` section (markdown `## Custom rule plugins` and the `--json` `custom` array). Plugins are opt-in — with no rules directory and no `--rules`, behavior is unchanged and the section stays empty. Each plugin is isolated: an import failure, a missing `check`, or a runtime exception is reported as a `level: "ERROR"` finding instead of crashing the scan/drift. See `references/example-rule-plugin.py` for a working template.

### Outputs

- A human-readable Checkup report.
- `--json` machine output with `files` (complete identity plus semantic/security coverage), `warnings`, `analysis_limits`, `overlaps`, `conflicts`, `nested`, `surface` (MCP/subagents/commands/hooks/permissions), `security` (severity-ranked findings), and `custom` (findings from user rule plugins). With `--baseline` it additively includes `baseline` and attributed `baselined` debt; in monorepo mode it also includes `packages` and `monorepo`.

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

The plan skeleton lists the inventory, overlap clusters, conflict list, and a TODO decision checklist. It also appends a **"Merge suggestions (semi-automatic)"** section derived from the scan: for each overlap cluster it recommends keeping content in the canonical `AGENTS.md` and reducing the other files to stubs (checkbox list), and for each conflict signal it proposes ONE recommended value with the supporting `path:line` evidence and a short rationale as an actionable checkbox item. The recommendation is deterministic and fact-aware: `package_manager` prefers the manager backed by the committed lockfile, `node_version` prefers the version pinned by `.nvmrc` / `engines.node`, and otherwise it falls back to the most-supported value (ties broken lexicographically) — it is a suggestion for human review, not an automatic adjudication.

Optionally auto-draft a starter `AGENTS.md` instead of writing it from a blank template:

```bash
python3 scripts/canonicalize.py /path/to/repo --draft                 # print to stdout
python3 scripts/canonicalize.py /path/to/repo --draft -o AGENTS.md    # write (refuses to overwrite without --force)
```

The draft fills every canonical section with deterministic, fact-derived starter content reused from `scan.py` / `semantic.py` — detected tech stack, build/test commands from `package.json` scripts and `Makefile` targets, the lockfile-backed package manager, detected CI/lint/type-check tooling, and default resolutions for every reported conflict. Inferred lines are tagged `(inferred — confirm)` and safe conventions `(suggested default)`; a banner reminds the human to review and edit every line before committing. The draft is a starting point, **not** a substitute for the human authoring step below.

Then the agent manually writes (or reviews and edits the draft into) the root `AGENTS.md`. The scripts do not perform semantic merging.

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

`--validate` requires the `Project overview`, `Build & test`, and `Conventions` headings by default. Override the required set with `--require-sections` (comma-separated); a missing heading is reported as a `SECTION` finding (ERROR, or WARN for a library/reference doc):

```bash
python3 scripts/canonicalize.py --validate /path/to/repo --require-sections "Project overview,Build & test,Security"
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
python3 scripts/check_drift.py /path/to/repo --min-score 80
python3 scripts/check_drift.py /path/to/repo --sarif        # emit SARIF 2.1.0 JSON for GitHub code scanning
python3 scripts/check_drift.py /path/to/repo --write-baseline .ai-harness-doctor/drift-baseline.json  # record current drift
python3 scripts/check_drift.py /path/to/repo --baseline .ai-harness-doctor/drift-baseline.json         # fail only on NEW drift
```

Checks:

- D1: command drift, comparing referenced commands against `package.json` scripts and `Makefile` targets.
- D2: path drift, checking whether backtick-quoted paths exist.
- D3: stub re-divergence, checking size and the `AGENTS.md` pointer.
- D4: `AGENTS.md` size.
- D5: nested `AGENTS.md` inventory, informational and non-blocking.
- D6: fact drift, cross-validating claims declared in `AGENTS.md` against repo ground truth — the Node version (vs `.nvmrc` and `package.json` `engines.node`) and the package manager (vs the lockfile that actually exists: `package-lock.json`→npm, `pnpm-lock.yaml`→pnpm, `yarn.lock`→yarn). It only flags clear contradictions and stays silent when `AGENTS.md` is silent.
- D7: Markdown-link drift, checking whether repo-relative Markdown link targets (`[text](path)`) in `AGENTS.md` still exist. Complements D2 (which only probes backtick-quoted tokens); URLs, anchors, and out-of-repo targets are ignored, so it never probes outside the repo.
- D8: competing lockfiles, flagging when lockfiles for more than one package manager are committed together (e.g. both `package-lock.json` and `pnpm-lock.yaml`) so the intended manager is ambiguous. Reported for manual attention — the tool never guesses which lockfile to delete.

**Nested drift scopes.** D5 itself remains non-blocking inventory, but every contained nested `AGENTS.md` it discovers is also guarded by D1/D2/D6/D7. Local facts/paths win; repository-root facts/paths are a conservative fallback for instructions that explicitly say to run from or reference the root. Those findings carry the nested canonical-file path into strict health, baselines, `--fix` manual attention, SARIF, and PR review. D3/D4/D8 and custom plugins still run once at repository scope. Historical root findings keep their implicit `AGENTS.md` path, so scope-less v1 baseline entries remain compatible.

All findings (D1..D8) roll up into a 0-100 **health score** with a letter grade (A/B/C/D/F), rendered as a `## Health score` section and exposed via the `score`/`grade` keys in `--json`. Use `--min-score N` to fail CI when the score drops below `N`; this gate is independent of `--strict` and both can apply together.

#### Semi-automatic repair: `--fix`

`--fix` auto-repairs ONLY the safe, mechanical subset of drift — currently **D3 stub regrowth**: any tool stub (`CLAUDE.md`, `.cursorrules`, `.github/copilot-instructions.md`, `GEMINI.md`, `.clinerules`, `.cursor/rules/*`, …) that grew real content or lost its `AGENTS.md` pointer is rewritten back to its minimal canonical import-stub form. The canonical stub bodies are reused directly from `canonicalize.py` (its `STUBS` mapping), so `--fix` and `canonicalize.py --write-stubs` stay in sync.

```bash
python3 scripts/check_drift.py /path/to/repo --fix          # DRY RUN: prints the diff, writes nothing
python3 scripts/check_drift.py /path/to/repo --fix --apply  # actually rewrites the regrown stubs
```

- Default `--fix` is a dry run: it prints a unified diff of what WOULD be rewritten and changes no files.
- `--fix --apply` rewrites the regrown stub files in place.
- Drift that is NOT safely auto-fixable (D1 command drift, D2 path drift, D4 size, D7 Markdown-link drift, D8 competing lockfiles, and any other semantic drift) is never modified; instead it is listed under **"needs manual attention"** with copy-pasteable repair guidance.
- A summary line reports `N fixed/fixable, M need manual attention`. The command exits non-zero while any drift remains (pending fixes in dry run, or unresolved manual items after `--apply`).

#### Adopting the gate on an existing repo: `--baseline`

A repo that already carries drift cannot flip on `--strict` without a wall of red. `--write-baseline FILE` records the current findings once, then `--baseline FILE` suppresses exactly those pre-existing findings so CI fails only on **new** drift introduced afterwards — the same adoption path ruff, mypy, and detekt offer. Fingerprints are `(check, message, path)` and ignore line numbers, so unrelated edits above a finding never re-open it. Suppressed findings are still surfaced (a `## Baseline` note and a `baselined` array in `--json`) but never count toward the score or exit code; the health score reflects only new drift, so a fully baselined repo scores grade A. The baseline file is deterministic (sorted, no timestamp) for clean diffs, and a missing or malformed baseline fails safe by suppressing nothing. Commit the baseline (e.g. under `.ai-harness-doctor/`) and shrink it as the team pays down drift.

```bash
python3 scripts/check_drift.py /path/to/repo --write-baseline .ai-harness-doctor/drift-baseline.json  # record once
python3 scripts/check_drift.py /path/to/repo --baseline .ai-harness-doctor/drift-baseline.json --strict  # gate only new drift
```

### Outputs

- Drift report.
- CI- and pre-commit-friendly failing exit codes.
- Repair advice that points to the category to fix and usually the line to inspect.

### Explicit stop condition

Stop when checks pass or repair advice has been provided. Do not rewrite semantic content during Follow-up.

### Long-term follow-up

After Treat completes and root `AGENTS.md` exists, install the long-term guard suite with `npx ai-harness-doctor guard /path/to/repo --apply`.
It installs only the core suite: pre-commit drift hook, CI drift/checkup gate, and `AGENTS.md` maintenance contract.
Repositories already on the [pre-commit](https://pre-commit.com) framework can instead reference the shipped `.pre-commit-hooks.yaml` (`ai-harness-doctor-drift`, `ai-harness-doctor-scan`) from their `.pre-commit-config.yaml`; both hooks call only the public packaged CLI.
The CI gate is **provider-aware** — pass `--provider github|gitlab|codebase` (default `auto`, detected from the git remote / `.gitlab-ci.yml`):
- `github` → `.github/workflows/harness-drift.yml` + `harness-checkup.yml`
- `gitlab` → includable `.gitlab/harness-ci.yml` (add `include: { local: .gitlab/harness-ci.yml }`)
- `codebase` → portable `.harness-ci/harness-guard.sh` + wiring `README.md` for internal Codebase / Bits / any runner
Remove it with `npx ai-harness-doctor guard /path/to/repo --remove --apply` (cleans up all providers' CI files); Claude hooks are not integrated.

The GitHub weekly checkup owns exactly one incident title:
`🩺 Harness checkup: issues detected`. An unhealthy run creates it or appends
the current combined report; the first healthy run adds commit/run recovery
evidence and closes it; later healthy runs do nothing. Exact-title filtering is
the ownership boundary, so unrelated issues are never closed. The shipped
consumer workflow still fails when scan/drift fails. This repository's adapted
self-checkup intentionally remains non-failing and uses the incident issue as
its scheduled signal.

> **Self-bootstrap:** this repository dogfoods its own guard. `.github/workflows/harness-drift.yml` and `harness-checkup.yml` are adapted from the templates to run the repo's **local** scan/drift implementations instead of the published package, so a change to `scripts/` is gated by the code being changed. The committed scan baseline records known benchmark/test-fixture conflicts; new scan debt or drift fails the PR gate. Generic shipped guards keep eval optional, but this repository unconditionally gates its committed self-eval on current task/`AGENTS.md` evidence and health. Only PR-review posting tolerates a missing/limited token.

#### PR review comments and CI eval gate

The GitHub PR guard intentionally has no `paths` or `paths-ignore` filter and runs on every pull request. Security and semantic checks consume MCP/settings files, nested rule surfaces, ecosystem manifests, and dynamic D2/D7 dependencies: any repository-relative file named by `AGENTS.md` can become drift evidence when moved or deleted. A finite path allow-list would therefore create a silent bypass. The weekly checkup remains defense in depth for drift that appears between pull requests.

On a pull request, the GitHub guard template (`.github/workflows/harness-drift.yml`) additionally captures each active scan/drift JSON report once, combines them into **one complete PR review**, and gates CI on the eval **health score**:

```bash
# Turn a check_drift.py (or scan.py) --json report into a GitHub PR review.
ai-harness-doctor drift . --json | ai-harness-doctor review --default-path AGENTS.md   # DRY RUN: prints the payload as JSON, never posts
ai-harness-doctor review --report drift-report.json --post --pr 42 --commit "$SHA"     # posts inline comments + a summary review
# Repeat --report to combine active scan + drift findings into one review.
ai-harness-doctor review --report scan-report.json --report drift-report.json --default-path AGENTS.md
```

The public `review` command forwards to `pr_review.py` (Python 3.9 stdlib only) and reads one or more reports from repeated `--report PATH` arguments, or one report from stdin. It traverses active scan warnings/security/gaps/semantic/custom/conflicts plus drift findings, including monorepo packages; baselined debt is intentionally excluded. Package locations are prefixed into repository-relative paths. Independent multi-repo batch findings keep a non-absolute repo label and remain summary-only, never cross-repo inline comments. Findings that carry a safe repo-relative `path` and positive `line` become rich inline review comments (`{path, line, body}`) with rule, severity, finding, AI-agent impact, evidence, and suggested fix. The final summary always carries the `<!-- ai-harness-doctor:pr-review -->` marker and includes health score/grade when available, severity distribution, inline/summary delivery counts, a full findings index, expanded details for every finding, and prioritized next steps. If GitHub rejects any inline placement with HTTP 422, the complete summary is posted once as a general PR comment instead; authorization, rate-limit, network, and server errors are not treated as successful delivery. A clean report instead names the covered harness checks and confirms that no action is required. `--dry-run` (the default) prints the assembled payload and never touches the network; `--post` uses the GitHub REST API (`urllib`) with `GITHUB_TOKEN` / `GITHUB_REPOSITORY` from the environment. Line-based drift findings (D1/D2/D6, which are about `AGENTS.md`) can be attached to a file with `--default-path AGENTS.md`. The guard workflow anchors review comments to `github.event.pull_request.head.sha`, because `github.sha` may identify a synthetic merge ref. Every shipped guard template calls only packaged CLI commands, so it remains executable in a fresh consumer repository without this source repo's `scripts/` directory. Inline PR review feedback is GitHub-only; GitLab/Codebase share the scan and eval gates without provider-specific inline comments.

The same template can run an **eval evidence + health gate**. Run/matrix/regrade automatically stamp sources declared by task-level `evidence`; repeatable `--evidence FILE` adds manual or extra sources. At score time, pass the same `--tasks`, `--workdir`, any explicit evidence, and `--require-current-evidence`: the task-declared sources are re-derived and stale/missing evidence exits 7 before `--fail-under <N>` applies the existing health gate (exit 5). Files retain SHA-256 byte fingerprints; directories bind only contained logical path, existence, and type, never recursive child bytes. Fingerprints prove input identity, not that manual answers came from a real model. Without strict freshness, legacy unstamped results remain scoreable; generic guard templates therefore keep eval optional, while this repository's self-guard requires its committed result.


## Phase 3 — Efficacy (Eval)

### Inputs

- Task file `tasks.json` — hand-written, or **auto-generated from repository facts** (see below).
- Before and after labels plus the target repository.
- Runner template, for example `claude -p {prompt} --output-format json`.

### Zero-config bootstrap (auto-generate tasks)

You do not need to hand-write `tasks.json`. `--generate REPO` inspects contained target-repository ground truth — `package.json` scripts/engines/deps, lockfiles (package manager), `.nvmrc`, `go.mod`, `pyproject.toml`, plus `AGENTS.md` conventions — and emits a deterministic task set whose regex checks encode the true facts. External symlink targets supply no fact; safe in-repo symlinks retain lexical evidence paths; ambiguous package-manager/runtime facts cause abstention. Add `--target PATH` to select one explicit effective instruction scope through the same containment/nearest-file model as `explain`: scripts/dependencies stay local; package manager/runtime may use the nearest unambiguous ancestor; canonical conventions inherit root → nearest. Scoped tasks carry percent-encoded IDs plus repository-relative `scope`, `target`, and fact-source `evidence`. Root generation remains compatible, and automatic all-scope expansion is intentionally deferred.

```bash
python3 scripts/eval_run.py --generate /path/to/repo -o tasks.json
python3 scripts/eval_run.py --generate /path/to/repo --target packages/api/src/index.ts -o api-tasks.json
```

Each generated task asks the agent for a concrete fact (install command, test/lint/build command, Node/Go/Python version, test framework, formatter, commit convention, ...) and passes only when the answer matches the fact the repo actually declares — so a higher score directly reflects whether `AGENTS.md` made the agent answer correctly.

Treat draft inference follows the same fact boundary: only contained manifests,
lockfiles, Makefiles, Python tooling, CI config, and instruction sources may
contribute inferred lines. Unsafe or ambiguous sources are omitted for human
review rather than followed or silently adjudicated.

### Actions

Before any runner, matrix agent, LLM/judge, evidence hash, result write, or
baseline update, validate the complete task array. Every task needs a unique,
non-empty string `id`, a non-empty string `prompt`, a supported `check` object
(`regex`/`command`/`judge`), and an optional finite positive `timeout_s`;
evidence and judge fields are type-checked too. Invalid packs exit 2 with a
concise `task error` that names only the task index/field and never echoes the
prompt or task contents. Regrade and strict score use the same task preflight;
non-strict historical score/compare/stats remain independent of a task file but
validate their stored result records separately. Malformed single-run,
multi-round, or matrix input exits 2 with a concise `result error` before a
comparison/regrade output or baseline snapshot can be written. Trend history is
a separate append-only schema.

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

### Multi-agent eval matrix

Run the same task set across several runners ("agents") and compare them side by side. Provide runners either inline or via a matrix file:

```bash
# Inline, repeatable NAME=CMD runners
python3 scripts/eval_run.py --tasks tasks.json --workdir /path/to/repo \
  --runner-cmd "claude=claude -p {prompt} --output-format json" \
  --runner-cmd "codex=codex exec {prompt}" \
  --matrix-report matrix-report.md --matrix-json matrix-results.json

# Or a matrix file mapping agent name -> runner command template
python3 scripts/eval_run.py --tasks tasks.json --workdir /path/to/repo \
  --matrix agents.json --matrix-report matrix-report.md --matrix-json matrix-results.json
```

`agents.json` shape (a flat mapping, or `{ "agents": { ... } }`):

```json
{ "claude": "claude -p {prompt} --output-format json", "codex": "codex exec {prompt}" }
```

Outputs:

- A markdown matrix report: rows are tasks, columns are agents, each cell shows pass/fail and duration, plus a per-agent pass-rate summary.
- A JSON file with per-agent task records and a `summary` block (`passed`, `total`, `pass_rate`).

The single-runner before/after flow (`--label` + `-o` + `--compare`) is unchanged; matrix mode activates only when `--matrix` and/or `--runner-cmd` are supplied.

### LLM-as-judge check type

In addition to `regex` and `command`, a task check may use `type: "judge"` for open-ended grading:

```json
{ "id": "explain", "prompt": "Explain the install command.",
  "check": { "type": "judge", "rubric": "Answer must name pnpm as the package manager." } }
```

Grading is delegated to a configurable command supplied via `--judge-cmd "CMD_TEMPLATE"`. The judge contract:

- Env `JUDGE_ANSWER`: the produced answer text.
- Env `JUDGE_RUBRIC`: the task's `rubric` (or `criteria`) string.
- Env `JUDGE_INPUT`: path to a temp JSON file `{"answer": ..., "rubric": ...}`.
- Template placeholders `{answer}` / `{rubric}` / `{input}` are substituted (shell-quoted).

The command MUST print a single JSON object: `{"passed": bool, "score": number, "reason": "..."}`. If `passed` is omitted but a numeric `score` is present, `score >= 0.5` counts as a pass. For offline/deterministic testing, a simple script or `printf '{"passed":true,"score":1.0}'` works as the judge.

```bash
python3 scripts/eval_run.py --tasks tasks.json --label after --workdir /path/to/repo \
  --runner "claude -p {prompt} --output-format json" \
  --judge-cmd "python3 my_judge.py"
```

An external `--judge-cmd` always takes priority. When it is not supplied, `judge` checks can be graded by a **real LLM** via `--judge-llm {auto,openai,claude,off}` (default `off` — the deterministic built-in keyword judge; LLM grading must be explicitly opted into so an ambient `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` never silently reroutes grading to a real model). `auto` uses OpenAI when `OPENAI_API_KEY` is set, else Anthropic/Claude when `ANTHROPIC_API_KEY` is set; API calls use only the Python standard library (no third-party SDKs). Model and endpoint are configurable via `OPENAI_MODEL`/`OPENAI_BASE_URL` and `ANTHROPIC_MODEL`/`ANTHROPIC_BASE_URL`, or `--judge-model`. Any failure — no key, network error, malformed response — **transparently falls back to the built-in keyword judge**, so judge checks always produce a verdict. The built-in judge is deterministic and dependency-free and emits `{passed, score, reason, judge: "builtin"}`, grading in priority order: `check.expect` (a list of regex patterns that must ALL match, case-insensitive), then `check.reject` (patterns that must NOT match), otherwise keyword coverage derived from the free-text `check.rubric` / `check.criteria`, passing when coverage `>= check.min_score` (default `0.5`). An LLM verdict is tagged `judge: "llm:openai"` / `"llm:claude"`. Pass `--judge-llm off` for keyword-only grading, or `--no-default-judge` to require an external `--judge-cmd` (legacy behavior).

```bash
# Grade judge checks with a real LLM (falls back to keywords if no API key)
python3 scripts/eval_run.py --tasks tasks.json --label after --workdir /path/to/repo \
  --runner "claude -p {prompt} --output-format json" --judge-llm auto
```

### Health score

Every eval computes a one-click efficacy **health score** = pass rate across all task records, expressed `0-100` with an A-F letter grade (A ≥90 / B ≥80 / C ≥70 / D ≥60 / F). It is embedded as a `health` key in both single-run results (`{"tasks": ...}`) and matrix results (`{"agents": ...}`), and printed as a summary line: `health score: N/100 (grade X), P/T tasks passed`. Timeouts count as failures. Stored `health` is a consistency cache, never score authority: offline consumers validate records, re-derive single/multi/matrix health, and reject every present canonical health field that disagrees. Historical blocks may omit additive health fields, but a contradictory cached score cannot pass `--fail-under`, regression checks, or baseline persistence.

**Evidence freshness.** A high stored score is meaningful only for the inputs that produced it. With `--workdir`, run, matrix, and regrade parse task-level `evidence` and stamp its deterministic union with repeated explicit `--evidence FILE` inputs into result JSON. Schema version 1 keeps the legacy file shape `{path, sha256}`, adds directory entries `{path, kind: "directory"}`, and marks newly task-bound manifests with `taskEvidence: true`; directories prove existence/type only and are never recursively hashed. `--score RESULTS --tasks TASKS --workdir REPO --evidence AGENTS.md --require-current-evidence` re-derives the task sources, combines explicit sources, and exits 7 on changed tasks/files, missing/type-changed directories, missing metadata, or a different evidence set before printing/gating health. Every task evidence entry must be a non-empty contained file/directory path; escapes, external symlinks, and malformed entries fail closed before a runner executes, without storing contents or absolute host paths. Pre-feature schema-v1 manifests without the marker retain explicit-only verification with their original arguments; hand-written tasks with no declared/explicit evidence retain unstamped behavior, and omitting the strict flag keeps old result files usable for historical reporting.

```bash
# Print the health score for an existing results/matrix JSON
python3 scripts/eval_run.py --score results-after.json        # human-readable
python3 scripts/eval_run.py --score results-after.json --json  # machine-readable

# CI gate: exit code 5 when the health score is below the threshold
python3 scripts/eval_run.py --tasks tasks.json --workdir /path/to/repo -o results.json --fail-under 80
```

### Baseline, trend & regression tracking

Persist each run's health as an append-only **baseline history** (a JSON list of snapshots) so you can track efficacy over time and gate on regressions. `--save-baseline` appends the current run's health to `--baseline FILE` (recording timestamp, label, score/grade, pass counts, and the target repo's git commit/branch when available). `--check-regression` compares the current score to the most recent prior snapshot and **exits 6** when the score drops by at least `--regression-threshold` points (default `5`). `--trend FILE` renders the recorded history as a markdown table with per-snapshot deltas and regression flags. These flags compose with any run mode (`--tasks`, `--rounds`, `--matrix`) and with `--score` on an existing results file.

```bash
# Save a baseline snapshot after a run, and fail the build on a regression
python3 scripts/eval_run.py --tasks tasks.json --label after --workdir /path/to/repo -o results.json \
  --baseline baselines/history.json --save-baseline --check-regression --regression-threshold 5

# Render the recorded trend (add --json for the raw history)
python3 scripts/eval_run.py --trend baselines/history.json
```

### Multi-round stability (`--rounds`)

`--rounds N` (N > 1) runs the whole task set N times and aggregates stability statistics so you can surface **flaky** tasks — ones that pass on some runs and fail on others. The results JSON then adds `rounds`, `round_results` (each round's full task records + per-round `health`), a per-task `task_stats` array (`runs`, `passed`, `failed`, `timed_out`, `pass_rate`, `flaky`), and a `stats` summary (`mean_health`, `variance`, `stddev`, `min_health`, `max_health`, `health_scores`, `flaky_tasks`, `flaky_count`). A task is `flaky` when it neither passes every round nor fails every round. Overall `health` is the pass rate across every task-run and `--fail-under N` gates on it. `--rounds 1` (the default) keeps the legacy single-round output shape byte-for-byte unchanged. `--stats PATH` validates each stored round/task record, derives per-round and overall health, rejects contradictory cached health, then re-aggregates the multi-round file offline.

```bash
# Run the task set 5 times and aggregate flakiness + per-round health stats
python3 scripts/eval_run.py --tasks tasks.json --label nightly --workdir /path/to/repo --rounds 5 -o results-nightly.json

# Re-analyze an existing multi-round results file (add --json for machine output)
python3 scripts/eval_run.py --stats results-nightly.json --json
```

## Explain a target path

Use the same lexical scope model as Phase 0 to answer which canonical instructions apply to one file, directory, or future path:

```bash
npx ai-harness-doctor explain /path/to/repo packages/api/src/handler.ts
npx ai-harness-doctor explain /path/to/repo packages/api/src/future.ts --json
```

Schema version 1 reports the normalized `target`, `effective_scope`, root→nearest `canonical_chain`, `diagnostic_sources`, relevant `scope_overrides` / same-scope `conflicts`, and `limitations`. Existing and future contained paths are accepted; escapes and external symlinks are rejected. Targets under scanner-excluded subtrees are explicitly marked. Canonical files are standards-backed inheritance; other recognized configs are only diagnostically associated because this command does not infer tool-specific globs, frontmatter, or prose scope. It never merges text, executes plugins, or writes files.

## MCP server

The core read-only capabilities are also exposed as an MCP (Model Context Protocol) stdio server so agents can call them as tools:

```bash
npx ai-harness-doctor mcp
# or directly: node bin/mcp-server.js
```

Transport is JSON-RPC 2.0 over newline-delimited JSON (one JSON object per line on stdin/stdout). Supported methods:

- `initialize` → negotiates stable MCP `2025-11-25` or legacy `2024-11-05` from the requested protocol version (unsupported versions receive the latest stable version), then returns `{ protocolVersion, capabilities: { tools: {} }, serverInfo: { name, version } }`.
- `notifications/initialized` → notification, no response.
- `tools/list` → advertises `harness_scan`, `harness_drift`, `harness_validate`, `harness_plan`, `harness_stubs`, `harness_eval_generate`, and `harness_explain`, each with a closed input schema.
- `tools/call` → dispatches to the matching Python script, keeps its output in `content[0]`, and returns machine-readable `{ exitCode, ok, status, report? }` metadata as JSON in `content[1]`; modern connections also receive the identical standard `structuredContent`.

Tool arguments: `harness_scan` (`json`), `harness_drift` (`json`, `strict`), `harness_validate` (`json`), `harness_plan`, `harness_stubs`, `harness_eval_generate` (optional `target`), and `harness_explain` (required `target`, optional `json`). All seven are read-only. Under `2025-11-25`, tools advertise closed input schemas, read-only/non-destructive/idempotent/closed-world annotations, and an output schema for the typed metadata envelope; under `2024-11-05`, modern-only fields are omitted. Explicitly requested valid JSON finding reports return `status: "findings"` without becoming MCP execution errors; invalid targets, runtime failures, timeouts, malformed reports, and ambiguous non-zero text reports set `isError: true`. Unknown methods/tools and invalid arguments return a JSON-RPC error object. A pre-initialize direct tool call retains the historical 2024 shape for compatibility; a valid handshake selects the connection's wire version. The server remains stdio-only and does not expose mutation or other MCP capability families.

## Runtime & self-test

The CLI is a dual Node + Python runtime: the Node entrypoint dispatches every Python-backed subcommand (`scan`, `explain`, `plan`, `validate`, `stubs`, `drift`, `review`, `eval`) and the MCP server through one shared Python resolver. Python is discovered in priority order — `AI_HARNESS_DOCTOR_PYTHON`, then `PYTHON`, then `python3`, then `python` — and only a Python **3** interpreter is accepted. When no interpreter is found, every subcommand fails with the same clean, actionable message (install Python 3 or set `AI_HARNESS_DOCTOR_PYTHON`) rather than leaking a raw stack trace.

Use `doctor --self-test` to verify the runtime before running the pipeline:

```bash
npx ai-harness-doctor doctor --self-test   # table: node, python, each engine, mcp-server
npx ai-harness-doctor doctor --json        # machine-readable runtime report (exit 1 if any check fails)
```

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
- `references/example-rule-plugin.py`: a copy-paste starting point for a custom rule plugin (`check(root, context)` contract).
- `assets/AGENTS.template.md`: English `AGENTS.md` template.
- `assets/guard/`: long-term follow-up guard suite templates: pre-commit, PR gate, weekly checkup, and maintenance contract.
- `.pre-commit-hooks.yaml`: pre-commit framework hook definitions (`ai-harness-doctor-drift`, `ai-harness-doctor-scan`) for consumers who already run pre-commit.
- `commands/`: Claude Code slash commands routed to this skill by phase.
- `adapters/`: thin pointer templates for Codex, Cursor, Gemini, and universal agents. The per-command adapters are generated from a single source by `scripts/gen_adapters.py`; run `python3 scripts/gen_adapters.py` to regenerate and `python3 scripts/gen_adapters.py --check` (or `npm run lint:adapters`) to verify they match in CI.
- `bin/cli.js`: npm CLI, installer, and forwarding entry point for Python scripts.
- `bin/mcp-server.js`: MCP stdio server exposing `harness_scan`, `harness_drift`, `harness_validate`, `harness_plan`, `harness_stubs`, `harness_eval_generate`, and `harness_explain`.
