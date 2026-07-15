# Implementation Plans

Generated and reconciled across two sets of three deep `improve` audits:

- 2026-07-14 at commit `7121ce6` (plans 001–003, all complete);
- 2026-07-15 at commit `c8d2f05` (plans 004–007).

Execute TODO plans in the order below unless dependencies say otherwise. Each
executor must read the selected plan fully, honor its STOP conditions, run every
verification gate, and update its status here.

## Audit rounds

1. **Correctness and security** — scanner filesystem boundaries, plugin
   isolation, PR review posting, installer writes, and error propagation.
2. **Action and release reliability** — exact/floating tags, reruns, npm
   publication, Marketplace reminders, permissions, and supply-chain posture.
3. **Tests, performance, architecture, and DX** — scan traversal, eval
   execution, Action inputs, CI feedback loops, duplication, and coverage.

### 2026-07-15 premium-repository rounds

1. **Core engine integrity** — mutation boundaries, symlink behavior, direct
   fact reads, safe auto-fix, subprocesses, performance, and test depth.
2. **GitHub engineering quality** — consumer guard installation, workflow
   executability, Action runtime deprecations, immutable dependency pins,
   release safety, duplicate CI, and repository security posture.
3. **Product and ecosystem direction** — the AGENTS.md specification, Ruler /
   rulesync adjacency, external-validation friction, adoption baselines,
   monorepo scoping, MCP parity, and maintainable product differentiation.

## Execution order & status

| Plan | Title | Priority | Effort | Depends on | Status |
|---|---|---:|---:|---|---|
| 001 | Keep scanner reads inside the audited repository | P1 | S | — | DONE |
| 002 | Preserve PR feedback when inline review locations are invalid | P1 | S | — | DONE |
| 003 | Prevent prereleases from replacing stable npm and Action refs | P1 | S | — | DONE |
| 004 | Refuse repository mutations through symlinks or escaping paths | P0 | M | — | TODO |
| 005 | Make installed guard workflows use only the public packaged CLI | P1 | M | 004 | TODO |
| 006 | Pin and modernize GitHub Actions while removing duplicate PR CI | P1 | M | — | TODO |
| 007 | Baseline non-security scan debt so CI gates only new findings | P2 | M | 004 | TODO |

Status values: TODO | IN PROGRESS | DONE | BLOCKED (with reason) | REJECTED
(with rationale).

## Dependency notes

- Plans 001–003 landed as separate PRs and shipped in `v1.0.1`; PR #109 closed
  the follow-up read-containment gap found by final review.
- Execute 004 first. Plans 005 and 007 introduce or exercise additional write /
  report paths and must inherit the mutation contract rather than inventing
  another safety rule.
- Plan 006 is independent and can land before or after 004/005.
- Keep one themed change per PR. Plans 005 and 007 add public CLI/report
  surfaces, so the combined release after this batch is at least a minor
  version under the repository's release policy.

## Findings considered and rejected or deferred

- **Duplicate CI and mutable Action tags (previously deferred)** — promoted to
  plan 006 after the `v1.0.1` release emitted Action runtime deprecation
  warnings and the second audit confirmed the same workflow changes can add a
  tested Dependabot update policy.
- **Action `args` cannot preserve a single argument containing spaces** —
  `action.yml` uses Bash word splitting. This is a real interface limitation,
  but the current documented flags do not require space-bearing values in the
  Action examples. Defer until the Action gains a structured-args contract.
- **Custom plugin findings do not affect built-in drift health/exit code** —
  explicitly documented and tested as additive behavior. Treat as by design,
  not a bug.
- **Post-publish floating-tag verification order** — npm publication is
  irreversible, but the exact tagged Action is self-tested before publish and
  all later steps are idempotent/recoverable on rerun. Keep the current
  compensating workflow.
- **Community-health files and remote security settings** — the public repo is
  at 57% community profile health and GitHub reports Dependabot alerts, secret
  scanning, and push protection disabled. `SECURITY.md`, issue forms, a PR
  template, Dependabot config, and repository settings are worthwhile P2 work,
  but they do not repair product behavior and are deferred until 004–007 land.
- **General refactor of `scan.py` / `eval_run.py` by file size** — both are
  large, but recent extraction of `scan_render.py`, strong regression coverage,
  and clear phase boundaries mean line count alone is not sufficient evidence
  for another refactor. Refactor only behind a concrete behavior/testability
  need.
- **Broader agent-file distribution** — Ruler and rulesync already own the
  generation/distribution niche across 20+ tools. AI Harness Doctor should keep
  differentiating on audit, evidence, safety, drift, and efficacy rather than
  cloning their generator breadth.
- **First-class scoped ignore/config language** — external validation still
  records context-sensitive cases (multi-stack conflicts, cross-repo paths,
  per-file indentation). A config language may eventually be justified, but
  plan 007's auditable baseline is the safer initial adoption mechanism; do not
  add opaque regex ignores before measuring baseline usage.
