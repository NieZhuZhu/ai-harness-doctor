**English** | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [Español](README.es.md) | [한국어](README.ko.md) | [Português (Brasil)](README.pt-BR.md) | [Français](README.fr.md)

# 🩺 AI Harness Doctor

**Your coding agent can sound confident while following stale repository instructions.** AI Harness Doctor audits `AGENTS.md`, `CLAUDE.md`, Cursor rules, hooks, MCP settings, and related harness files before that drift becomes a broken PR.

It helps you consolidate scattered guidance into one human-owned `AGENTS.md`, keep tool-specific files as small pointers, and measure whether the resulting harness actually improves agent answers.

<p><a href="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml"><img align="left" alt="CI" src="https://github.com/NieZhuZhu/ai-harness-doctor/actions/workflows/test.yml/badge.svg"></a> <a href="https://www.npmjs.com/package/ai-harness-doctor"><img align="left" alt="npm version" src="https://img.shields.io/npm/v/ai-harness-doctor.svg"></a> <img align="left" alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"> <img align="left" alt="Python 3.9+" src="https://img.shields.io/badge/Python-3.9%2B-blue.svg"> <img align="left" alt="Node &gt;=16" src="https://img.shields.io/badge/Node-%3E%3D16-green.svg"></p>
<br clear="left">

> In the included benchmark, canonicalization improved objective answers from **6/28 to 28/28**, removed flip-flops, reduced average latency by 27%, and reduced captured cost by 17%.

## Start in 60 seconds

Run a zero-install, read-only checkup:

```bash
npx ai-harness-doctor scan .
```

Explain which instructions apply to one path:

```bash
npx ai-harness-doctor explain . packages/api/src/handler.ts
```

Verify the Node and Python runtime:

```bash
npx ai-harness-doctor doctor --self-test
```

Check which version npx resolved:

```bash
npx ai-harness-doctor --version
```

Nothing above changes the audited repository.

## What it checks

| Area | What the doctor looks for |
|---|---|
| Inventory | Canonical files, tool rules, nested scopes, MCP, hooks, commands, permissions, and subagents. |
| Security | Plaintext secrets, broad permissions, insecure MCP transports, dangerous hook bodies, and bypass guidance. |
| Consistency | Missing scripts, moved paths, package-manager drift, runtime-version drift, broken links, and competing lockfiles. |
| Instruction quality | Oversized context, wholesale README copying, silent conflict adjudication, overlaps, and same-scope conflicts. |
| Scope | Root-to-nearest `AGENTS.md` inheritance plus bounded Claude, Cursor, and Copilot glob applicability. |
| Efficacy | Before/after task correctness, stability, latency, cost, evidence freshness, and health grade. |

Security reads stay inside the audited repository. Oversized files still receive full-file SHA-256, line-count, secret, and permission-bypass coverage; `--max-bytes` limits semantic analysis only.

## The four phases

| Phase | Goal | Main commands | Human stop point |
|---|---|---|---|
| 0 — Checkup | Discover risk, conflicts, gaps, and repository facts. | `scan`, `explain` | Confirm migration scope. |
| 1 — Treat | Build a merge plan and consolidate into canonical guidance. | `plan`, `validate`, `stubs` | Adjudicate every semantic conflict. |
| 2 — Follow-up | Prevent stale commands, paths, links, stubs, and facts. | `drift`, `guard`, `review` | Decide whether code or guidance is wrong. |
| 3 — Efficacy | Measure whether the harness improves agent behavior. | `eval` | Decide whether the evidence is sufficient. |

Scripts perform deterministic mechanics. They never silently choose npm over pnpm, select one disputed command, or semantically merge prose for you.

## Consolidate a repository

Create a reviewable plan, write `AGENTS.md`, validate it, then replace duplicated tool files with small pointers:

```bash
npx ai-harness-doctor scan .
npx ai-harness-doctor plan . -o merge-plan.md
# Write and review AGENTS.md, then:
npx ai-harness-doctor validate .
npx ai-harness-doctor stubs . --apply
npx ai-harness-doctor guard . --apply
```

You can also install the Claude Code skill and run `/harness-doctor .` or `/harness-treat .`. The agent stops for your decision whenever repository truth is ambiguous.

## Install and update

| Goal | Command |
|---|---|
| Install Claude Code skill for the current user | `npx ai-harness-doctor install` |
| Install Codex prompts | `npx ai-harness-doctor install --agent codex` |
| Install Cursor commands in a repository | `npx ai-harness-doctor install --agent cursor --project` |
| Install every supported adapter in a repository | `npx ai-harness-doctor install --agent all --project` |
| Redeploy the latest package to tracked installs | `npx ai-harness-doctor@latest update` |
| Remove installed adapters | `npx ai-harness-doctor uninstall --agent all` |

Copy installs are ownership-tracked. Update and uninstall preserve unowned collisions and user-edited files. Tests always use an isolated `HOME`.

## Keep it healthy in CI

Install provider-aware pre-commit, pull-request, and scheduled guards:

```bash
npx ai-harness-doctor guard . --apply
```

GitHub guards combine scan and drift into one rich PR review. Located findings become inline comments; the summary includes severity, health, evidence, repair guidance, and prioritized next steps.

Already use the pre-commit framework?

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/NieZhuZhu/ai-harness-doctor
    rev: v1.13.1
    hooks:
      - id: ai-harness-doctor-drift
      - id: ai-harness-doctor-scan
```

The weekly checkup keeps one owned incident issue current and closes it after recovery. See [`references/maintenance-contract.md`](references/maintenance-contract.md) for the repository-maintenance contract.

## GitHub Action and SARIF

The Marketplace Action runs bundled source by default and produces SARIF, Action outputs, and a Job Summary:

```yaml
- id: doctor
  uses: NieZhuZhu/ai-harness-doctor@v1
  with:
    command: scan
    path: .
- uses: github/codeql-action/upload-sarif@v4
  with:
    sarif_file: ${{ steps.doctor.outputs.sarif-file }}
```

Available outputs include `status`, severity counts, `finding-count`, `resolved-baseline-count`, and drift `health-score` / `health-grade`.

Status precedence is `findings > maintenance > ok`. A valid non-zero quality gate publishes SARIF and the summary before restoring the exact CLI exit code.

SARIF results carry stable partial fingerprints and separate scan/drift categories, so alerts survive unrelated line movement and independent uploads do not close each other.

Use `args-json` when an extra option value contains spaces or when exact/repeated argv boundaries matter:

```yaml
- uses: NieZhuZhu/ai-harness-doctor@v1
  with:
    command: drift
    path: .
    args-json: '["--baseline", ".ai-harness-doctor/drift baseline.json", "--check-baseline"]'
```

`args-json` and legacy `args` are mutually exclusive. Legacy `args` keeps first-line whitespace splitting only; neither input is shell-evaluated.

## Adopt existing debt safely

Baselines are reviewed debt registers, not ignore lists. They classify findings as new, known, or repaired:

```bash
npx ai-harness-doctor scan . --write-baseline .ai-harness-doctor/scan-baseline.json
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json \
  --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json --check-baseline
npx ai-harness-doctor scan . --baseline .ai-harness-doctor/scan-baseline.json --prune-baseline
```

`baselined` contains known debt. `resolved_baseline` contains repaired entries. Check exits `9` when cleanup is needed; prune atomically removes only repaired entries and never records new findings.

HIGH security findings are never baseline-eligible. Ordinary malformed baselines suppress nothing; explicit check or prune fails closed without writing.

## Command guide

| Command | Use it for | Writes by default? |
|---|---|---:|
| `scan` | Full checkup, security scan, gaps, conflicts, semantics, and project snapshot. | No |
| `explain` | Effective instruction chain and diagnostic scope for one path. | No |
| `plan` | Reviewable consolidation plan. | Only with output path |
| `validate` | Canonical path, size, required sections, and unresolved draft markers. | No |
| `stubs` | Preview or apply minimal tool pointers. | No |
| `drift` | D1–D8 follow-up checks, health score, baseline lifecycle, and safe D3 repair. | No |
| `guard` | Install or remove pre-commit and CI guards. | No |
| `review` | Build or post one GitHub PR review from scan/drift reports. | Only with `--post` |
| `eval` | Generate, run, compare, regrade, score, and trend efficacy tasks. | Depends on output flags |
| `mcp` | Start the read-only MCP stdio server. | No |
| `doctor` | Validate the Node/Python runtime and packaged engines. | No |

Run `npx ai-harness-doctor help` or inspect [`SKILL.md`](SKILL.md) for the complete option and behavior reference.

## Supported surfaces

| Surface | Support |
|---|---|
| Claude Code | Native skill and slash commands. |
| OpenAI Codex CLI | Prompt adapters. |
| Cursor | Project or user command adapters. |
| Gemini CLI | TOML command adapters for enterprise/existing installs. |
| MCP clients | Seven read-only tools over JSON-RPC stdio. |
| GitHub Actions | Composite Action, SARIF, Job Summary, outputs, and PR feedback. |
| GitLab / Codebase | Shared scan, drift, and optional eval gates. |
| Other agents | Universal pointer to the playbook. |

Non-Claude adapters are intentionally thin. Broad rules distribution belongs to tools such as Ruler and rulesync; this project focuses on diagnosis, evidence, safety, drift, and efficacy.

## Safety model

- Scan is read-only and excludes repository-derived external symlinks.
- Missing paths ignored by repository `.gitignore` files are treated as deliberate runtime paths; synthetic Git metadata excludes local/global rules, and Git failure preserves findings.
- A backtick `org/name` that adjacent words label as a Docker/OCI image or an RPC/API method is treated as a runtime identifier, not a checked path; the exclusion is fail-closed, and extensioned or three-plus-segment tokens stay paths.
- Nested drift resolves commands, paths, and runtime/package-manager facts through lexical package ancestors without searching sibling packages; Markdown links remain file-relative.
- Write paths refuse symlinked files or existing parent directories.
- Plugins are disabled unless `--allow-plugins` is supplied.
- Secret findings name type/path without reproducing values; risky hook snippets are redacted in JSON, Markdown, SARIF, and PR feedback.
- Installer mutations are lock-serialized, journaled, ownership-aware, and recoverable.
- MCP tools remain read-only; findings are not transport failures.
- External judges and real LLM grading are opt-in. Remote judge endpoints require HTTPS, loopback HTTP is explicit, redirects are refused, and failures fall back to the deterministic judge.
- Eval result artifacts redact high-confidence credentials from runner/judge diagnostics and matrix runner templates; grading still uses the original bounded output in memory.
- No telemetry. The optional npm update check can be disabled with `AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1`.

## Evidence and benchmark

| Side | Passed | Flip-flop tasks | Avg latency/task | Captured cost |
|---|---:|---:|---:|---:|
| Before: conflicting/stale configs | 6/28 | 2 | 16.0s | $5.82 |
| After: canonical `AGENTS.md` | 28/28 | 0 | 11.7s | $4.81 |

See [`benchmark/README.md`](benchmark/README.md) for methodology and reproduction. This is one demo repository with two runs per side; it is evidence, not a universal performance claim.

## Documentation map

| Document | Purpose |
|---|---|
| [`SKILL.md`](SKILL.md) | Complete four-phase behavior and command contract. |
| [`references/migration-decision-tree.md`](references/migration-decision-tree.md) | Choose the right migration path. |
| [`references/conflict-resolution.md`](references/conflict-resolution.md) | Human adjudication workflow. |
| [`references/tool-matrix.md`](references/tool-matrix.md) | Tool-file support and ownership. |
| [`references/maintenance-contract.md`](references/maintenance-contract.md) | Baseline, Action, guard, CI, release, and installer invariants. |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Contribution workflow and checks. |
| [`RELEASING.md`](RELEASING.md) | Tag-driven npm, GitHub Release, floating Action tag, and Marketplace flow. |
| [`EXTERNAL_VALIDATION.md`](EXTERNAL_VALIDATION.md) | Read-only validation against real repositories. |

## Project status

- Python 3.9+ and Node 16+ standard-library runtime only.
- npm releases are tag-driven with provenance.
- Stable releases move the floating major Action tag (`v1` for `1.x`).
- Feature releases use a minor bump; bugfix-only releases use a patch bump.
- Public behavior changes require synchronized documentation in every published language.

## Contributing

Issues and pull requests are welcome. Read [`CONTRIBUTING.md`](CONTRIBUTING.md), add tests with every behavior change, and keep all translated READMEs synchronized in the same PR.

For security vulnerabilities, follow [`SECURITY.md`](SECURITY.md) instead of opening a public issue.

## License

[MIT](LICENSE)
