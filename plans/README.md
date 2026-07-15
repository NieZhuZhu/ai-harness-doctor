# Implementation Plans

Generated and reconciled across twelve deep `improve` audit batches:

- 2026-07-14 at commit `7121ce6` (plans 001–003, all complete);
- 2026-07-15 at commit `c8d2f05` (plans 004–007).
- 2026-07-15 at commit `b3dd9e3` (plans 008–010).
- 2026-07-15 at commit `b638ad7` (plans 011–013).
- 2026-07-15 at commit `73bd749` (plans 014–017).
- 2026-07-15 at commit `e4992c8` (plans 018–020).
- 2026-07-15 at commit `ced1530` (plans 021–023).
- 2026-07-15 at commit `935eeb6` (plans 024–026).
- 2026-07-16 at commit `150d1c9` (plans 027–029).
- 2026-07-16 at commit `704806e` (plans 030–032).
- 2026-07-16 at commit `777f962` (plans 033–035).
- 2026-07-16 at commit `43366d9` (plan 036).

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

### 2026-07-15 post-v1.6.0 premium-project rounds

1. **Core security and diagnostic truth** — independently re-audited file-read
   budgets, security gates, inventory identity, overlap/conflict evidence,
   monorepo reuse, and scan/explain parity. A 50,087-byte synthetic AGENTS.md
   proved that tail credentials and permission-bypass guidance are invisible
   after the 32 KiB semantic budget; same-prefix/different-tail files also
   receive the same reported SHA and misleadingly complete overlap/conflict
   output.
2. **Release replay and supply-chain identity** — independently audited the
   live npm/GitHub/Marketplace release chain, privileged reruns, exact/floating
   tags, package provenance, remote settings, and immutable-release controls.
   A moved same-version tag still passes version/main ancestry and skips npm
   publish without comparing the registry artifact's `gitHead`; the legitimate
   v1.6.0 `gitHead` and reproducible pack shasum establish a concrete identity
   contract, while unavailable server-side immutability remains an operational
   limitation rather than a fictitious automation claim.
3. **Monorepo efficacy and premium product direction** — independently
   re-audited Phase 3 generation, explain scope vocabulary, MCP parity, task
   identity/evidence, and bounded large-monorepo UX. A root npm + nested
   pnpm/Vitest package reproduced root-only tasks despite explain selecting the
   package scope. With Plan 023 now validated, the selected feature is explicit
   target-aware generation; automatic all-scope expansion remains deferred
   until real task volume and cost are measured.

### 2026-07-16 post-v1.7.0 premium-project rounds

1. **Fact-generation containment and truth parity** — independently audited
   root/target eval, Treat draft inference, shared fact helpers, ambiguity
   policy, symlink boundaries, and safe output. External root
   `package.json`/`.nvmrc`/`AGENTS.md` symlinks manufactured eval answers, while
   an external `CLAUDE.md` supplied a drafted command. Root competing lockfiles
   also selected the first manager instead of matching scan/drift abstention.
2. **Required-CI dependency reproducibility** — independently audited lockfile
   consumption, real main logs, Node/npm runtime behavior, package integrity,
   Dependabot, and install commands. The lint job says “No lockfile found,”
   ignores committed npm records, and creates a Yarn lock; an altered committed
   Prettier record did not affect the installed version. Exact `npm ci` now
   succeeds on the pinned Node 20.19.5/npm 10.8.2 runner.
3. **Generated efficacy evidence lifecycle** — independently traced scoped task
   provenance through generate, run, matrix, regrade, score, CLI, and MCP. Tasks
   named `package.json`/lock evidence, but result manifests included only manual
   `--evidence`; changing the package fact still passed strict freshness. This
   promotes Plan 026's explicitly deferred provenance binding follow-up.

### 2026-07-16 post-v1.8.0 premium-project rounds

1. **Eval execution safety and result trust** — independently traced task JSON
   from parse through evidence, single/multi/matrix runners, judge dispatch,
   regrade, and strict score. A valid first task executed a marker runner before
   a malformed second task raised `KeyError: 'prompt'`; no result was written.
   Evidence-only validation therefore does not protect paid execution from a
   malformed pack.
2. **GitHub operations and alert lifecycle** — independently audited live
   community/security/protection settings, recent workflows, dependency
   advisories, guard templates, and scheduled issue behavior. Remote trust
   posture is healthy (100% community profile, nine strict checks, no recent
   failed runs), but both shipped and self checkups only create/comment an
   incident issue on failure; a healthy later run has no close path.
3. **Organization-scale product reliability** — independently rechecked the
   AGENTS.md scope standard, adjacent linter/distributor positioning, batch
   scanning, external-validation boundaries, and deferred roadmap items. A
   repos list containing only a missing path reported `error_count: 1` yet
   exited 0 with all four fail-on flags, proving the advertised org-wide CI gate
   can pass without scanning one repository.

### 2026-07-16 post-v1.8.1 premium-project rounds

1. **Stored efficacy-result integrity** — independently traced existing result
   JSON through score, stats, compare, regrade, evidence freshness, thresholds,
   and baseline snapshots. A failed task plus a forged `100/A` health block
   passed `--fail-under 80`; malformed string tasks also passed when health was
   present and raised a traceback when it was absent. Plan 030's task-definition
   preflight had explicitly left this stored-result boundary for later work.
2. **GitHub Action success-contract coverage** — independently audited the
   public `command`/`version` matrix, static tests, required self-test logs, and
   tag-driven release logs. Every successful composite invocation through
   `v1.8.1` used bundled `scan`; successful bundled `drift` and exact npm
   override paths were neither required on PRs nor verified after publish.
3. **Structured rule applicability and ecosystem direction** — independently
   researched current Cursor and VS Code/Copilot rule contracts, reproduced
   false conflicts across disjoint `globs`/`applyTo` domains, and validated the
   prevalence of the format against current `github/docs` and
   `microsoft/vscode`. The selected scope is bounded deterministic
   applicability, not prose inference, general YAML, or broader rule
   distribution.

### 2026-07-16 post-v1.9.0 improve round 1

1. **Correctness, security, and PR feedback lifecycle** — independently
   re-audited untrusted repository reads/plugins, report traversal, GitHub
   posting, 422 recovery, ownership, pagination, and repeated workflow runs.
   Repo rule plugins remain safely opt-in and their malicious sentinel tests
   pass, but the stable PR-review marker is never read: PR #189 accumulated two
   byte-identical `github-actions[bot]` clean summaries after two head commits.
   The selected repair makes one owned marker comment the durable current
   summary while preserving inline findings and visible API failures.

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
| 021 | Enforce drift checks in every nested AGENTS.md scope | P0 | M | — | DONE |
| 022 | Reject untrusted inputs and off-main tags in privileged npm workflows | P0 | S | — | DONE |
| 023 | Explain the effective instruction chain for any repository path | P1 | L | 020 (done) | DONE |
| 024 | Scan every byte for security and identity without unbounded semantic reads | P0 | M | — | DONE |
| 025 | Bind idempotent release reruns to the published npm artifact | P0 | S | — | DONE |
| 026 | Generate efficacy tasks for one explicit instruction scope | P1 | L | 023 (done) | DONE |
| 027 | Confine every fact-derived generator to repository truth | P0 | M | — | DONE |
| 028 | Make lint CI install the committed npm lockfile exactly | P1 | S | — | DONE |
| 029 | Bind generated task evidence into eval freshness automatically | P1 | M | 027 | DONE |
| 030 | Validate every eval task before any runner or judge executes | P0 | M | — | DONE |
| 031 | Close the weekly harness issue when the repository recovers | P1 | S | — | DONE |
| 032 | Fail multi-repo CI when any listed repository was not scanned | P0 | S | — | DONE |
| 033 | Derive eval health only from validated stored result records | P0 | M | — | DONE |
| 034 | Self-test every public GitHub Action success path | P1 | S | — | DONE |
| 035 | Model deterministic Cursor and Copilot rule applicability | P1 | L | — | DONE |
| 036 | Keep one current AI Harness Doctor summary per pull request | P1 | M | — | IN PROGRESS |

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
- Plans 024 and 025 are independent P0 repairs and may land in either order,
  but keep them as separate PRs: one changes scanner evidence/security
  coverage and one changes privileged release rerun behavior. Plan 026 depends
  only on already-DONE Plan 023's target/scope vocabulary, not on 024/025.
- Execute 026 after re-reading any small scan/explain metadata changes from
  Plan 024. Target normalization and effective scope must remain shared, while
  bounded scan evidence and eval fact-source evidence are distinct contracts.
- Keep Plans 024–026 in separate PRs. Plans 024–025 are patch-level if their
  STOP conditions do not force breaking schemas. Plan 026 adds public CLI/MCP
  behavior, so the combined release is minor unless a STOP condition exposes a
  breaking change.

## Post-v1.6.0 completion evidence

- Plan 024 landed in PR [#163](https://github.com/NieZhuZhu/ai-harness-doctor/pull/163)
  (`5cc8c56`): complete-file identity/security with bounded semantic evidence,
  Action/SARIF/PR feedback coverage, and real 41 KB `agency-swarm` validation.
- Plan 025 landed in PR [#164](https://github.com/NieZhuZhu/ai-harness-doctor/pull/164)
  (`79f3dbb`): fail-closed npm lookup plus exact `gitHead` and reproducible pack
  shasum checks; the new step passed on a detached real `v1.6.0` checkout.
- Plan 026 landed in PR [#165](https://github.com/NieZhuZhu/ai-harness-doctor/pull/165)
  (`ade174a`): explicit target-aware CLI/MCP task generation with compatible
  root IDs, scoped evidence, containment, and Mastra root/memory/core validation.
- Every implementation PR passed all nine required contexts: drift, lint,
  Node 16/20/22, self-test, and Python 3.9/3.10/3.12. Local final validation on
  current main is 613 Python tests, 26 Node tests, strict drift 100/A, and
  evidence-bound eval 25/25.
- Release classification: Plans 024–025 are backward-compatible bug/security
  fixes; Plan 026 adds a public CLI/MCP feature. Publish the batch as the next
  minor version after this completion record merges.
- Plans 027 and 028 are independent and may land in either order. Keep them in
  separate PRs: one changes product fact-generation safety and one changes the
  repository's dependency-install gate.
- Execute Plan 029 only after 027. Automatically trusting task-declared
  evidence is safe only after every generator guarantees contained paths and
  ambiguity-safe facts.
- Keep Plans 027–029 in separate PRs. Plans 027–028 are patch-level if their
  compatibility STOP conditions do not trigger. Plan 029 adds public eval
  provenance behavior, so the combined batch is minor unless a STOP condition
  exposes a breaking schema requirement.

## Post-v1.7.0 completion evidence

- Plan 027 landed in PR [#170](https://github.com/NieZhuZhu/ai-harness-doctor/pull/170)
  (`dcd6dcc`): root/scoped eval and Treat draft now share contained fact reads,
  preserve safe lexical symlink evidence, and abstain on competing managers.
- Plan 028 landed in PR [#171](https://github.com/NieZhuZhu/ai-harness-doctor/pull/171)
  (`569db1e`): required lint CI now installs the exact committed public npm
  graph with `npm ci --ignore-scripts --no-audit --no-fund`; job `87433510938`
  installed 71 packages without Yarn or a generated lockfile.
- Plan 029 landed in PR [#172](https://github.com/NieZhuZhu/ai-harness-doctor/pull/172)
  (`d75b859`): generated task evidence now binds automatically across run,
  matrix, regrade, and strict score; file/directory semantics remain schema-v1
  compatible, and real Mastra round 22 proved package-fact staleness exits 7.
- Every implementation PR passed all nine required contexts: drift, lint,
  Node 16/20/22, self-test, and Python 3.9/3.10/3.12. Final local validation on
  current main is 634 Python tests, 26 Node tests, strict drift 100/A, and
  evidence-bound self-eval 27/27.
- `AGENTS.md` now records all three durable invariants: contained/ambiguity-safe
  fact generation, lockfile-exact lint installs, and automatic effective-
  evidence freshness with file hashing and directory type binding.
- Release classification: Plans 027–028 are backward-compatible fixes; Plan
  029 adds public eval provenance behavior. Publish the batch as the next minor
  version after this completion record merges.
- Plans 030–032 are independent and may land in any order, but keep them in
  separate PRs: eval cost-safety, GitHub incident lifecycle, and batch coverage
  are distinct review/rollback units.
- Plan 030 must preserve valid generated/hand-written task packs and result
  shapes. Plan 031 must preserve the shipped failing schedule versus this
  repository's non-failing self-checkup. Plan 032 must scan every reachable
  repo before selecting its final exit and retain 2/3/4/7 finding precedence.
- Plans 030–032 repair false-late/false-stale/false-green behavior without
  adding a new user workflow. They are patch-level if their compatibility STOP
  conditions do not trigger; a batch release is patch unless implementation
  uncovers a public feature or breaking requirement.

## Post-v1.8.0 completion evidence

- Plan 030 landed in PR [#177](https://github.com/NieZhuZhu/ai-harness-doctor/pull/177)
  (`969d135`): complete task-schema preflight now rejects malformed packs before
  any runner/LLM/judge/hash/write; Mastra round 23 proved zero calls.
- Plan 031 landed in PR [#178](https://github.com/NieZhuZhu/ai-harness-doctor/pull/178)
  (`1c4fc6b`): shipped/self weekly checkups now create/update one exact incident
  and close it with recovery evidence; extracted shell lifecycle tests cover
  create/update/recover/no-op.
- Plan 032 landed in PR [#179](https://github.com/NieZhuZhu/ai-harness-doctor/pull/179)
  (`4b38fb8`): multi-repo scans preserve all reachable reports but exit 8 for
  any unscanned entry after 2/3/4/7 precedence; round 24 validated two real
  clean public checkouts plus one missing path and safe summary-only review.
- Every implementation PR passed all nine required contexts: drift, lint,
  Node 16/20/22, self-test, and Python 3.9/3.10/3.12. Final local validation on
  current main is 648 Python tests, 26 Node tests, strict drift 100/A, and
  evidence-bound self-eval 27/27 before this completion refresh.
- `AGENTS.md` now records all three durable invariants: preflight before eval
  side effects, symmetric weekly incident lifecycle, and fail-closed batch
  coverage without resolved-path leakage.
- Release classification: Plans 030–032 are backward-compatible bug fixes.
  Publish the batch as the next patch version after this completion record
  merges.
- Plans 033–035 are independent and must land as separate PRs: stored eval
  trust, Action/release coverage, and structured product applicability have
  distinct review and rollback boundaries. Execute 033 first because it guards
  this repository's efficacy evidence; 034 may run before or after it; execute
  035 last because it has the largest public report surface.
- Plan 033 must preserve every producer-compatible single/multi/matrix result
  while refusing contradictory stored health. Plan 034 must distinguish current
  bundled-code evidence from already-published/npm artifact evidence and retain
  prerelease policy. Plan 035 must suppress only provably disjoint automatic
  domains, keep security independent, and never turn recursive discovery into
  recursive deletion.
- Plans 033–034 are backward-compatible correctness/test hardening if their STOP
  conditions do not expose a behavior bug. Plan 035 adds public structured-rule
  applicability and explain/report metadata, so the combined release is at
  least minor unless a STOP condition requires a breaking schema.
- Plan 036 is independent and must remain one bugfix PR. Its marker is public
  text, not authorization: update only a comment proven to be owned by the
  authenticated poster. Keep the complete summary as one durable issue comment,
  preserve inline annotations, and never turn 422 fallback into a second
  summary. If the ownership proof needs broader workflow permissions, stop
  rather than weakening the boundary.
- Plan 036 implementation PR #192 first head `320bd53` passed all nine required
  contexts and created marker comment `4986399749` at
  `2026-07-15T23:51:39Z`. A second workflow execution must update that same ID
  and keep the marker count at one before the plan can move from IN PROGRESS to
  DONE.

## Post-v1.8.1 completion evidence

- Plan 033 landed in PR [#184](https://github.com/NieZhuZhu/ai-harness-doctor/pull/184)
  (`2def2fb`): offline score/stats/compare/regrade now validate stored
  single/multi/matrix records, derive health, reject contradictory caches, and
  preserve historical partial-health/bare-round compatibility.
- Plan 034 landed in PR [#185](https://github.com/NieZhuZhu/ai-harness-doctor/pull/185)
  (`68662b6`): required self-test now succeeds through bundled scan, bundled
  drift, and exact public npm override; stable release preflights both bundled
  commands and verifies the new exact npm version through the floating Action.
- Plan 035 landed in PR [#186](https://github.com/NieZhuZhu/ai-harness-doctor/pull/186)
  (`4e04021`): bounded Cursor/Copilot applicability, recursive discovery,
  current-path conflict domains, target explain, SARIF/PR diagnostics, and the
  no-recursive-delete boundary shipped; github/docs + VS Code are round 25.
- Every implementation PR passed all nine required contexts: drift, lint,
  Node 16/20/22, self-test, and Python 3.9/3.10/3.12. Local final validation on
  current main is 673 Python tests, 26 Node tests, strict drift 100/A, and
  evidence-bound self-eval 33/33 after the completion refresh.
- `AGENTS.md` now records all three durable invariants: stored-result health
  derivation, complete Action command/source self-tests, and structured
  applicability without prose inference or recursive mutation authority.
- Release classification: Plans 033–034 are backward-compatible correctness
  and test hardening; Plan 035 is a public feature. Publish the batch as the
  next minor version after this completion record merges.

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
- **Structured Action `args` after v1.6.0** — `action.yml` still splits the
  free-form input with Bash word rules and cannot preserve one whitespace-
  bearing argument. This remains a real limitation, but no documented Action
  flag currently needs that shape and this batch has three mechanically
  reproduced higher-impact gaps. Keep deferred until a structured input has a
  concrete consumer.
- **Treat a size warning as sufficient security coverage** — rejected. Context
  truncation is itself useful evidence, but `--fail-on-security` must not miss
  a credential solely because it appears after an agent's context budget. Plan
  024 separates bounded semantic text from complete streaming identity/security
  coverage rather than choosing either unbounded reads or silent tails.
- **Run full semantic/conflict analysis over every oversize file** — rejected.
  It would remove the memory/context budget and make adversarial files
  unbounded. Plan 024 keeps semantic/overlap/conflict analysis prefix-bounded
  and makes that evidence boundary explicit.
- **Automatically expand zero-config eval across every nested scope** —
  deferred. The direction is valuable, but default expansion can multiply task
  count and model cost in large monorepos. Plan 026 exposes one explicit target
  with deterministic scope/evidence first; revisit `--all-scopes` only after
  external measurements.
- **Infer package scopes from manifests without AGENTS.md** — rejected for this
  feature. Phase 3 is evaluating harness efficacy, so target-aware generation
  follows the canonical instruction-scope model; generic workspace/package
  benchmarking is a different product surface.
- **Claim immutable GitHub Releases or protected exact tags from workflow
  code** — rejected. Live remote/API verification found no ruleset and no
  available release-immutability toggle. Plan 025 enforces npm identity on every
  rerun and documents server-side protection as an operations follow-up instead
  of claiming a control the repository cannot currently prove.
- **General `scan.py` / `eval_run.py` refactor after v1.7.0** — still rejected.
  File size alone is not a defect. Plans 027 and 029 use concrete containment
  and provenance seams and must not become broad module rewrites.
- **Structured Action `args` after v1.7.0** — still deferred. No documented
  Action invocation needs one whitespace-bearing argument; all three selected
  findings have current mechanical or production-log reproductions.
- **Automatic all-scope eval expansion after v1.7.0** — still deferred. Mastra
  measurements validate explicit targets but do not establish bounded model
  cost or useful default task selection across every scope.
- **Keep Yarn as an npm-ci fallback** — rejected. A fallback silently changes
  the reviewed dependency graph and restores the reproduced unlocked install.
  If locked npm CI fails again, stop and diagnose the exact runtime instead.
- **Treat generated task `evidence` as display-only provenance** — promoted to
  Plan 029. It was an explicit Plan 026 defer, but package-fact mutation now
  proves strict freshness can return success for stale generated truth.
- **Structured Action `args` after v1.8.0** — rechecked and still deferred.
  Bash word splitting cannot preserve one whitespace-bearing argument, but no
  documented Action invocation consumes such a value. The selected findings
  each have a current side-effect/CI/operations reproduction.
- **Automatic all-scope eval after v1.8.0** — still deferred. Explicit Mastra
  targets validate scope truth and evidence, but no bounded cost/task-selection
  policy exists for default expansion. Plan 030 first makes any future larger
  pack fail before paid execution.
- **Adopt `AGENTS.override.md`/custom fallback names immediately** — ecosystem
  documentation shows Codex-specific override/fallback behavior, but this
  project intentionally models the cross-tool AGENTS.md nearest-file baseline.
  Adding one tool's replacement semantics to canonical inheritance would need a
  compatibility/design plan and multiple real-repo measurements, not a regex.
- **Move guard templates from npm `@latest` to exact package versions** —
  rejected for this batch. Existing Plan 005 deliberately chose a documented
  floating update channel for long-lived guards; changing update philosophy
  needs a migration/update mechanism and is unrelated to checkup recovery.
- **Treat partial batch coverage as success with only a warning** — rejected.
  `summary.error_count` already identifies operational coverage loss and the
  mode is advertised as an org-wide CI gate. Continuing to scan good entries is
  valuable; returning 0 is not.
- **Add a generic result-JSON schema validator while fixing task preflight** —
  promoted to Plan 033 after the new independent audit forged a `100/A` health
  block over a failed record and passed the strict threshold. The plan remains
  separate from task-definition preflight and excludes trend-history schema.
- **Clone AgentLint/Ruler/rulesync feature breadth** — rejected again.
  Adjacent tools reinforce the project's differentiation on contained
  diagnostic truth, freshness, CI feedback, and efficacy evidence rather than
  more rule generation or opt-in AI analyzers.
- **Fix the stale deterministic temp-report filename prose as a standalone
  plan** — confirmed: `README.md` still describes
  `${TMPDIR}/harness-scan-<hash>.json`, while `write_report_file()` correctly
  uses an unpredictable `mkstemp` path after SEC-02. This is a small docs bug,
  but it does not outrank the three reproduced execution/operations/CI defects;
  repair it with the next user-facing scan-doc change rather than padding this
  batch with a docs-only implementation PR.
- **Enable GitHub server-side SHA pinning / restrict allowed Actions now** —
  rechecked and still not selected. Remote `sha_pinning_required` is false, but
  every current external Action is full-SHA pinned and repository tests enforce
  that invariant. Changing org/repo Action policy has a larger operational
  blast radius than the selected concrete failures and no current bypass
  reproduction.
- **Expand the registry with Kiro/Augment/Amazon Q/other rule formats now** —
  rejected for this batch. More filenames improve breadth but not diagnostic
  truth. Plan 035 first models the deterministic applicability languages of two
  already-recognized, high-adoption formats with official contracts and real
  repositories.
- **Use a generic YAML dependency for rule frontmatter** — rejected. Runtime
  remains Python 3.9 stdlib-only, and accepting arbitrary YAML would enlarge the
  parser/security surface. Plan 035 specifies only documented scalar control
  fields and fails closed on unsupported constructs.
- **Symbolically solve arbitrary glob intersections** — rejected. It is complex
  and easy to make unsound. Plan 035 uses current contained repository paths for
  scan conflict evidence and direct matching for `explain TARGET`, while
  explicitly making no claim about unmatched future intersections.
- **Make recursive Cursor/Copilot discovery authorize recursive Treat deletion**
  — rejected as a dangerous coupling of read coverage to write authority.
  Plan 035 adds an explicit no-delete regression; any broader consolidation
  needs a separate ownership/rollback plan.
- **Treat default custom rule plugins as untrusted-code execution** — rechecked
  and rejected as already fixed. `run_plugins()` returns before discovery unless
  `allow_plugins=True`; scan/drift expose an explicit warning and malicious
  sentinel tests prove default runs do not import repository code.
- **Delete or minimize historical duplicate PR summaries** — rejected for Plan
  036. The current-state contract needs a safe owned upsert, while destructive
  cleanup has a different permission/rollback risk. Update only the newest
  owned marker and leave legacy history untouched.
- **Refactor `scan.py` / `eval_run.py` because they remain large** — rejected
  again in round 1. The audit found no new behavior or testability failure that
  justifies a broad rewrite; Plan 036 has direct production evidence and a
  narrow verification seam.
