# Implementation Plans

Generated and reconciled across seven deep `improve` audit batches:

- 2026-07-14 at commit `7121ce6` (plans 001–003, all complete);
- 2026-07-15 at commit `c8d2f05` (plans 004–007).
- 2026-07-15 at commit `b3dd9e3` (plans 008–010).
- 2026-07-15 at commit `b638ad7` (plans 011–013).
- 2026-07-15 at commit `73bd749` (plans 014–017).
- 2026-07-15 at commit `e4992c8` (plans 018–020).
- 2026-07-15 at commit `ced1530` (plans 021–023).

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

### 2026-07-15 post-v1.1.0 rounds

1. **Core correctness and safety** — repeated all mutation/read boundaries after
   scan baselines became repository state; audited installers, adapters,
   manifests, plugins, explicit outputs, subprocesses, and symlink behavior.
2. **CI, release, and consumer reliability** — audited the actual GitHub
   protection/settings, Action/release runs, immutable dependencies, package
   reproducibility, guard event filters, Marketplace state, and community
   health independently from the core pass.
3. **Architecture, tests, and product completeness** — audited report-shape
   traversal, PR feedback, SARIF/MCP/CLI surface symmetry, external-validation
   evidence, benchmark honesty, high-complexity modules, and roadmap options.

### 2026-07-15 post-v1.3.0 rounds

1. **Core state safety and test trust** — independently audited installer
   ownership state, HOME containment, malformed-state behavior, atomic writes,
   plugin isolation, subprocesses, and high-risk test gaps.
2. **GitHub-native output completeness** — independently audited every active
   scan/drift report family across JSON, Markdown, PR review, SARIF, monorepo
   attribution, baselines, the composite Action, and released package contents.
3. **MCP/API and consumer DX** — independently audited all six MCP tools,
   JSON-RPC/input schemas, subprocess exit semantics, error signaling,
   read-only guarantees, timeout hygiene, and documentation/API symmetry.

### 2026-07-15 post-v1.3.1 premium-project rounds

1. **Core diagnostic truth** — independently re-audited semantic/drift parity,
   monorepo path scoping, finding lifecycle, efficacy evidence, cross-engine
   invariants, performance, coverage, and external-validation claims.
2. **GitHub/public-project engineering** — independently audited community
   health, dependency updates, remote security settings, branch protection,
   contribution flows, release issue hygiene, package reproducibility, and CI.
3. **Ecosystem and product direction** — independently researched the current
   MCP stable contract, AGENTS.md ecosystem expectations, adjacent linters and
   generators, adoption evidence, and the project's audit/evidence/safety/
   efficacy differentiation.

### 2026-07-15 post-v1.4.0 rounds

1. **Core correctness and performance** — independently re-audited diagnostic
   hot paths, cross-engine parity, documentation truth, filesystem containment,
   and large-repository behavior. A measured 1,200-directory fixture confirmed
   that each otherwise-missing path token causes another full subtree walk.
2. **Action, release, and supply chain** — independently audited the live
   release/npm/Marketplace chain, Action pins and permissions, public package
   contents, lockfile sources, Dependabot, manual operations, and recent remote
   workflow runs. Two real npm Dependabot jobs failed on the private lockfile
   source, invalidating the earlier portability defer.
3. **External validity and product direction** — independently rechecked the
   AGENTS.md hierarchy standard, nested-file behavior, real public monorepos,
   adoption evidence, and deferred false-positive classes. The scanner
   reproduced a blocking global conflict for valid nearest-file package
   overrides because nested canonical scopes are currently flattened.

### 2026-07-15 post-v1.5.0 premium-project rounds

1. **Core diagnostic and evidence lifecycle** — independently traced every
   Phase 2 check, baseline identity, strict health calculation, fix rendering,
   SARIF, and PR-review path from a nested `AGENTS.md`. A synthetic package
   reproduced a complete false negative: unknown local command, missing local
   path, and broken local Markdown link all passed strict drift at 100/grade A
   because D5 inventories nested files without running D1/D2/D6/D7 on them.
2. **Privileged release and supply-chain safety** — independently audited tag
   provenance, dispatch inputs, npm credentials, provenance, remote settings,
   reruns, and Marketplace automation. Isolated shell and Git reproductions
   confirmed that manual deprecation inputs reach executable script text and
   that a matching version tag on an unmerged branch passes the current version
   check despite not being an ancestor of `main`.
3. **Product explainability and ecosystem direction** — independently mapped
   the CLI/MCP/adapter surfaces, current nearest-file scope model, zero-config
   eval generation, and adjacent scope-debugging workflows. The selected
   direction is a read-only `explain REPO TARGET` projection over existing
   scope evidence; scope-aware eval generation remains the next follow-up after
   that target-path vocabulary and public schema are validated.

## Execution order & status

| Plan | Title | Priority | Effort | Depends on | Status |
|---|---|---:|---:|---|---|
| 001 | Keep scanner reads inside the audited repository | P1 | S | — | DONE |
| 002 | Preserve PR feedback when inline review locations are invalid | P1 | S | — | DONE |
| 003 | Prevent prereleases from replacing stable npm and Action refs | P1 | S | — | DONE |
| 004 | Refuse repository mutations through symlinks or escaping paths | P0 | M | — | DONE |
| 005 | Make installed guard workflows use only the public packaged CLI | P1 | M | 004 | DONE |
| 006 | Pin and modernize GitHub Actions while removing duplicate PR CI | P1 | M | — | DONE |
| 007 | Baseline non-security scan debt so CI gates only new findings | P2 | M | 004 | DONE |
| 008 | Make every installer mutation ownership-aware and preserve repository state | P0 | M | — | DONE |
| 009 | Make PR guard triggers cover every security and semantic scan input | P0 | M | — | DONE |
| 010 | Deliver every active scan finding as attributed PR feedback | P1 | M | 009 | DONE |
| 011 | Make installer manifest state fail closed and write atomically | P0 | M | — | DONE |
| 012 | Emit every active scan finding family in SARIF | P1 | S | — | DONE |
| 013 | Make MCP tool failures machine-visible and keep its contract current | P1 | S | — | DONE |
| 014 | Restore subtree-scoped path parity between scan and drift | P0 | S | — | DONE |
| 015 | Bind eval results to the evidence they claim to score | P1 | M | — | DONE |
| 016 | Negotiate modern MCP and expose standard structured results | P1 | M | — | DONE |
| 017 | Establish a verifiable public-repository trust baseline | P1 | M | 014–016 | DONE |
| 018 | Index subtree path resolution once per diagnostic run | P1 | M | — | DONE |
| 019 | Restore public-registry dependency update automation | P0 | S | — | DONE |
| 020 | Make conflict diagnostics honor nested AGENTS.md scopes | P1 | L | 018 | DONE |
| 021 | Enforce drift checks in every nested AGENTS.md scope | P0 | M | — | IN PROGRESS |
| 022 | Reject untrusted inputs and off-main tags in privileged npm workflows | P0 | S | — | IN PROGRESS |
| 023 | Explain the effective instruction chain for any repository path | P1 | L | 020 (done) | IN PROGRESS |

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
- Plans 008 and 009 are independent P0 fixes and may land in either order, but
  keep them as separate PRs. Execute 010 only after 009 so the workflow that
  posts complete scan feedback is guaranteed to run for every scanned input.
- Plan 008 is a bugfix unless its manifest migration changes public behavior in
  a breaking way (a STOP condition). Plans 009–010 improve guard behavior and
  together make the next combined release at least minor.
- Execute 011 first because manifest state authorizes later installer
  mutations; keep it isolated from output/API changes. Plans 012 and 013 are
  independent and may land in either order as separate PRs.
- Plans 011–013 are bugfixes under the current contracts unless a STOP condition
  forces a breaking schema/protocol change. A combined release is patch-only if
  every implementation remains backward-compatible.
- Execute Plan 014 first because it fixes a reproduced cross-engine false
  positive with the smallest blast radius. Plans 015 and 016 are independent
  backward-compatible features and should remain separate PRs.
- Execute Plan 017 last: it records the final maintenance contract in
  `AGENTS.md`, then applies remote GitHub settings only after all code changes
  and their CI contexts exist on main.
- Plan 014 is patch-level. Plans 015–016 add public capabilities, so a combined
  release after this batch is at least minor unless a STOP condition forces a
  breaking protocol/schema change.
- Plans 018 and 019 are independent. Execute 019 early because the repository's
  newly enabled dependency-update control is currently failing in production.
  Plan 018 should land before 020 so real large nested-scope validation inherits
  the one-index path behavior rather than amplifying the measured traversal
  cost.
- Keep Plans 018–020 in separate PRs. Plan 018 is a backward-compatible
  performance fix; Plan 019 is a bugfix/operations repair; Plan 020 adds
  scope/override report surfaces and is a backward-compatible feature. A
  combined release after all three is therefore minor under the repository
  policy unless a STOP condition exposes a breaking schema requirement.
- Plans 021 and 022 are independent P0 repairs and may land in either order,
  but keep them as separate PRs: one changes consumer drift coverage and one
  changes privileged repository workflows. Plan 023 builds on the already-DONE
  Plan 020 scope model; it does not need Plan 021's drift implementation.
- Execute Plan 023 only after re-reading any scope-model changes introduced
  while 021 is implemented. Explain must project the single scan scope model,
  not fork nested scope semantics merely because drift now consumes them too.
- Keep Plans 021–023 in separate PRs. Plan 022 is patch-level. Plan 021 repairs
  a false negative but expands a public gate, and Plan 023 adds CLI/MCP/adapter
  surfaces; the combined release is therefore minor unless a STOP condition
  exposes a breaking contract.

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
- **Public lockfile contains `bnpm.byted.org` resolved URLs** — portability is
  undesirable, but an isolated `npm ci` from only `package.json` +
  `package-lock.json` succeeded during this audit and runtime has zero npm
  dependencies. Defer lockfile normalization until the existing npm CI
  resolver failure is reproduced and fixed; do not mix it into safety PRs.
- **Remote GitHub security/community posture** — community profile remains 57%;
  required status checks, admin enforcement, secret scanning, push protection,
  and Dependabot security updates are disabled. These are worthwhile repository
  administration tasks, but they are remote settings/community files rather
  than product behavior; keep separate from plans 008–010.
- **MCP surface/documentation symmetry** — README correctly lists six tools,
  while two `SKILL.md` passages still list only four. This is real docs drift
  and is now included in plan 013 alongside the higher-impact MCP result
  semantics bug, rather than as a standalone docs-only change.
- **Action `args` shell word splitting** — still a real structured-argument
  limitation. No current documented Action flag needs a single whitespace-
  bearing value, so the earlier defer remains valid.
- **General large-module refactors** — `scan.py`, `eval_run.py`, and their tests
  are large, but the third audit found concrete seams and substantial coverage;
  line count alone still does not justify a risky refactor. Extract only behind
  an implemented behavior such as plan 010's report traversal.
- **Scan overlaps / inventory / snapshots in SARIF** — these are evidence and
  discovery data, not actionable findings. Plan 012 intentionally maps active
  warnings/custom findings but does not flood Code Scanning with inventory.
- **Treat every non-zero MCP exit as an MCP transport error** — rejected because
  scan/drift/validate deliberately use non-zero codes for valid finding reports.
  Plan 013 instead defines per-tool report-vs-operational policies and preserves
  finding content with structured status.
- **MCP mutation parity with the full CLI** — rejected for safety. Guard apply,
  installer, baseline writes, and agent/eval execution stay outside the
  read-only MCP surface.
- **Structured Action `args` in this batch** — still deferred. The latest audit
  found no documented Action use case requiring a whitespace-bearing single
  argument; installer state, SARIF omissions, and MCP false-success signals have
  direct reproductions and higher leverage.
- **Per-file-type conflict scoping** — still a real false-positive class
  (`tabs for code, 2 spaces for JSON`), but correctly solving it needs
  scope-aware extraction rather than another regex exception. Plan 014's
  reproduced scan/drift inconsistency is higher confidence and lower risk.
- **Cross-repository attributed paths** — OpenHands evidence shows paths can be
  explicitly owned by another repository, but safe suppression requires
  section/context attribution. Defer until a second independent reproduction
  or a structured scope model; do not infer from nearby prose heuristically.
- **Normalize private-registry URLs in package-lock.json** — fresh isolated
  `npm ci` using only the committed manifests succeeded against the public npm
  registry, and runtime dependencies remain zero. The URLs are undesirable
  provenance noise but not currently blocking contributors; do not mix a
  lockfile rewrite into Plans 014–017.
- **General coverage-percentage gate** — measured Python coverage is 61% and
  Node CLI line coverage is low because real-CLI subprocess tests are not
  attributed to the parent process. High-risk paths have substantial
  end-to-end coverage; a percentage target would incentivize test-shape gaming
  without a concrete uncovered failure. Add characterization tests behind
  selected behavior instead.
- **Clone Ruler/rulesync distribution breadth** — rejected again. The strongest
  product signal is diagnostic truth, evidence freshness, safety, protocol
  integration, and efficacy—not generating disposable rules for every tool.
- **Adopt draft MCP 2026-07-28** — rejected. It is a release candidate/future
  contract at the audit date. Plan 016 targets latest stable 2025-11-25 and
  centralizes version negotiation so a later stable upgrade is incremental.
- **Enforce branch protection for administrators** — deferred because GitHub's
  self-approval restriction would deadlock the current sole maintainer's PR
  merges. Plan 017 keeps admin bypass but requires real CI contexts and
  documents that bypass must never override red checks.
- **Stale self-bootstrap “eval gate is soft” prose** — confirmed in all three
  READMEs and `SKILL.md`; the repository workflow now unconditionally requires
  evidence freshness plus health. Included in Plan 019 so the small
  public-maintenance repair leaves the operational trust docs truthful;
  generic shipped guards remain optional.
- **Manual deprecate workflow interpolates dispatch inputs directly in a shell
  command (previously deferred)** — promoted to Plan 022 after an independent
  privileged-workflow audit mechanically confirmed both input positions cross
  into shell evaluation while the job holds the npm credential. The same plan
  also closes the independently reproduced off-main matching-tag release gap.
- **Repository permits all third-party Actions and does not enforce server-side
  SHA pinning** — local structural tests already reject every unvetted or
  mutable external `uses:` reference, and all current workflow dependencies are
  full-SHA pinned. GitHub's remote `sha_pinning_required` is defense in depth,
  but changing the allowed-actions policy could disrupt Dependabot/Marketplace
  maintenance without repairing a demonstrated product failure; retain the
  tested repository-level control for this batch.
- **Action `args` shell word splitting** — rechecked and still real. No current
  documented Action flag requires preserving a whitespace-bearing value, so
  it remains below the measured path traversal, broken dependency automation,
  and nested-scope false positive.
- **Per-file-type conflict scope** — better-auth still says “tabs for code,
  2 spaces for JSON,” and the global regex still reports both values. This
  requires clause/file-type semantics and is explicitly outside Plan 020;
  directory hierarchy is standardized and deterministic, whereas prose scope
  is not. Keep deferred until another independent high-impact reproduction or
  a structured applicability model exists.
- **Cross-repository attributed paths** — still needs section/prose attribution
  and has no second independent reproduction. Plan 020 must not broaden from
  lexical nested scopes into heuristic external-repository suppression.
- **Treat nested override evidence as a blocking finding** — rejected. The
  AGENTS.md standard intentionally allows closer files to override ancestors.
  Plan 020 keeps overrides visible in JSON/Markdown/Treat context but reserves
  exit 7, SARIF, and PR-review findings for contradictory values inside one
  effective diagnostic scope.
- **Clone broad rule-distribution products** — rejected again. The selected
  work improves diagnostic truth, performance, public maintenance, and
  explainable scope evidence, preserving this project's audit/evidence/safety/
  efficacy differentiation.
- **Scope-aware zero-config eval generation** — high-value and directly
  reproduced: `eval_run.generate_tasks()` reads only root facts/`AGENTS.md`, so
  a package-local command and instruction scope produce no efficacy task.
  Defer one batch rather than designing two public scope APIs simultaneously.
  After Plan 023 validates target-path vocabulary and schema on real monorepos,
  generate package-local tasks from that contract and define collision-safe
  task IDs/evidence before implementation.
- **Claim every nearby tool config is effective for a target path** — rejected.
  Cursor/Copilot and other tools have their own frontmatter/glob semantics.
  Plan 023 may list them only as diagnostically associated sources until the
  project models and tests those applicability languages explicitly.
- **npm trusted publishing/OIDC migration** — desirable because it can remove
  the long-lived publish token, and the workflow already grants
  `id-token: write`. It still requires npmjs account-side trusted-publisher
  configuration plus a real publication proof, so a code-only plan cannot
  honestly mark it complete. Plan 022 hardens the input/ref boundary regardless
  of credential mechanism; revisit OIDC in a separately confirmed operations
  loop.
