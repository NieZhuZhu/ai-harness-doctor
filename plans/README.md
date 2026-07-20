# Implementation Plans

Generated and reconciled across the deep `improve` audit batches below:

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
- 2026-07-16 at commit `660977e` (plan 037).
- 2026-07-16 at commit `a2a7227` (plan 038).
- 2026-07-16 at commit `c141268` (plan 039).
- 2026-07-16 at commit `26b07b0` (plan 040).
- 2026-07-16 at commit `e25d421` (plans 041 landed; plan 042).
- 2026-07-17 at commit `7e03467` (plan 052).
- 2026-07-17 at commit `ffcfe32` (plan 053).
- 2026-07-17 at commit `eac8426` (plan 054).
- 2026-07-17 at commit `5d96c95` (plan 055).
- 2026-07-17 at commit `725128d` (plan 056).
- 2026-07-17 at commit `30675ba` (plan 057).
- 2026-07-17 at commit `8b0d19e` (plans 058–060).
- 2026-07-18 at commit `8034dc4` (plan 061).
- 2026-07-18 at commit `11e3a71` (plan 062).
- 2026-07-18 at commit `9acdafc` (plans 063–065).

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

### 2026-07-16 post-v1.9.0 improve round 2

1. **Installer lifecycle and failure recovery** — independently re-audited
   copy/link install, update, uninstall, shared payloads, manifest ownership,
   cross-platform paths, update checks, mutation ordering, and fault injection.
   Existing ownership and atomic-manifest controls remain strong, but they are
   not one transaction: injected final manifest failure leaves first-install
   files without a manifest and removes uninstall files while preserving the
   old manifest. The selected repair is a durable contained rollback journal
   with expected next-manifest digest recovery, not a writeability preflight or
   memory-only catch block.

### 2026-07-16 post-v1.9.0 improve round 3

1. **Eval runner, judge, cost, and protocol truth** — independently audited
   single/multi-round/matrix execution, shell-template boundaries, process-group
   timeout, task command checks, external/LLM/builtin judges, health, usage,
   output persistence, and MCP exposure. Shell templates remain an explicit
   operator interface and task substitutions are quoted; MCP does not expose
   paid execution. The reproduced defect is operational false success: a
   runner that prints a matching answer then exits 9 and an external judge that
   prints a passing verdict then exits 7 both produce passing records and
   100/A health. Plan 038 makes exit success authoritative across all modes.

### 2026-07-16 premium-project loop 1 round 1

1. **Claude Code project-rule compatibility** — independently researched the
   current first-party Claude Code instruction contract, GitHub adoption,
   registry coverage, structured applicability, security reads, conflict
   domains, target explain, report delivery, and Treat ownership. Claude
   recursively loads `.claude/rules/**/*.md`; rules without frontmatter are
   always-on and `paths` lists select matching files. Current Bitwarden and
   Algolia repositories use both scoped and always-on forms, but the doctor
   inventories neither: a synthetic rule remained absent from scan files,
   conflicts, and explain sources. Plan 039 extends the existing bounded
   applicability seam without generic YAML, external reads, or recursive
   mutation authority.

### 2026-07-16 premium-project loop 1 round 2

1. **Treat canonical-readiness truth** — independently audited draft
   provenance, validation, stub mutation ordering, library-doc compatibility,
   MCP validate semantics, Git recovery, and human-adjudication claims. An
   untouched `--draft` output carries explicit auto-draft/TODO/inference
   markers but passes `validate` because it has the required headings. After
   committing that draft, `--write-stubs --apply` exits 0 and replaces a real
   `CLAUDE.md`, hiding its repository-specific truth behind the unreviewed
   canonical file. Plan 040 single-sources exact provisional markers and
   preflights canonical readiness before destructive consolidation without
   rejecting arbitrary user TODOs or weakening library-doc behavior.

### 2026-07-16 premium-project loop 1 round 3

1. **Eval baseline-history integrity** — independently audited the last
   result-JSON consumer family Plan 033 explicitly deferred: the
   `--baseline`/`--save-baseline`/`--check-regression`/`--trend` history store.
   Every other offline consumer (`--score`/`--stats`/`--compare`/`--regrade`)
   validates records and exits `2` with a concise `result error`, but a
   malformed history store (a list whose entries are not dicts, or a scalar
   `score`) makes `--trend` and `--check-regression` crash with an uncaught
   `AttributeError` traceback (exit 1), while a non-numeric/absent score is
   silently ignored. Plan 041 gives the history store the same fail-closed
   validation and derives regression/trend only from validated numeric
   snapshots, without changing the append-only schema or valid histories.

### 2026-07-16 premium-project loop 2 round 1

1. **GitHub-native alert lifecycle correctness** — independently traced the
   Plan 012 SARIF surface end to end into GitHub code scanning's documented
   ingestion rules. Every emitted `result` omits `partialFingerprints` and every
   `run` omits `automationDetails.id`, so (a) an unrelated edit or line shift can
   close and re-open the same alert, and (b) uploading both `scan` and `drift`
   SARIF for one commit — exactly what the README instructs — makes the second
   upload close the first command's alerts because both share the tool name and
   an empty category. The repository already computes a stable, line-insensitive
   finding identity (`scan.scan_finding_fingerprint`) for baselines, so the fix
   reuses that identity model rather than inventing one. Plan 042 adds
   deterministic per-result fingerprints and per-command categories additively,
   without importing `scan.py` into `sarif.py`, changing rule ids/levels, or
   emitting SARIF for batch mode.

### 2026-07-16 improve loop round (parallel correctness/security/tests/DX audit)

1. **LLM-judge fallback contract** — independently audited the Phase 3
   judge path with parallel read-only category sweeps (correctness, security,
   tests, tech-debt/DX). `eval_run.py`'s LLM-as-judge documents in three places
   that "no key / network error / malformed response" all return `None` so
   grading falls back to the deterministic keyword judge, but the malformed path
   does not: on an HTTP-200 response whose content is not the expected JSON
   verdict, `parse_judge_output` returns a non-`None` sentinel
   (`{"passed": False, "reason": "judge output was not valid JSON"}`) and
   `llm_judge` returns it unchanged, so `grade_answer` records a silent hard fail
   instead of falling back — a false-health defect matching the Plan 030/033/038/
   041 class. Plan 043 marks the unparseable branch and maps it to `None` at the
   `llm_judge` boundary, leaving the external `--judge-cmd` path and valid-verdict
   logic untouched.

### 2026-07-16 improve loop round 2 (installer crash-recovery robustness)

1. **Incomplete transaction directory bricks the installer** — independently
   traced the installer crash-recovery path (`recoverInstallerTransactions` →
   `readTransactionDirectory`), which runs before every install/update/uninstall.
   `beginInstallerTransaction` creates the transaction directory
   (`fs.mkdirSync`) and only later writes `journal.json`; a process killed in
   that window leaves a journal-less directory. On the next run,
   `readTransactionDirectory` does `fs.lstatSync(journalPath)`, throws `ENOENT`,
   and `withInstallerTransaction` turns it into a fatal "Cannot start installer
   transaction" — so recovery, which runs first on every command, permanently
   bricks install/update/uninstall until the stray directory is removed by hand.
   The same failure is the recurring `unittest (3.9)` flake in
   `test_concurrent_installer_fails_without_recovering_live_transaction`. Plan 044
   makes recovery treat a genuinely journal-absent directory as an abandoned
   artifact (contained cleanup + continue) while keeping every present-but-
   invalid/unsafe journal fatal (Plan 011/037 security preserved).

### 2026-07-16 improve loop round 3 (eval fact-source parity)

1. **Scoped eval uses a divergent private lockfile vocabulary** — independently
   traced root and target-aware package-manager generation. Root eval, scan,
   drift, and Treat use `registry.LOCKFILE_MANAGERS` through
   `facts.lockfile_managers`, but `_scoped_package_manager` iterates a private
   `PKG_MANAGER_LOCKFILES` list that additionally recognizes the non-standard
   `pnpm-lock.yml`. A synthetic package mechanically reproduced the split:
   registry/root detection returned no manager while `--target` confidently
   generated a pnpm task bound to `packages/app/pnpm-lock.yml`. Current pnpm
   documentation names `pnpm-lock.yaml`; this is engine-local drift, not a
   missing registry entry. Plan 045 removes the private list, reuses the
   registry, and extends the consistency gate so scope can change fact
   precedence but never the vocabulary of valid facts.

### 2026-07-16 premium-project loop 3 round 1 (Action consumer contract)

1. **Composable GitHub Action quality report** — researched the repository-root
   composite Action against the current SARIF and GitHub environment-file
   workflow. The Action exposes only `sarif-file`, writes no Job Summary, and
   runs under `set -e`; a valid `--fail-on-*` / `drift --strict` SARIF therefore
   exits before the Action can publish structured context. Plan 046 adds
   deterministic SARIF producer metadata, a shipped Node 16 stdlib report helper,
   Action status/count/health outputs, and `$GITHUB_STEP_SUMMARY`, while running
   the doctor once and restoring the exact CLI exit code after reporting.

### 2026-07-16 premium-project loop 3 round 2 (baseline debt lifecycle)

1. **Resolved baseline debt is invisible and cannot be pruned safely** —
   researched the existing scan/drift debt registers against mature baseline
   systems that distinguish new, unchanged, and resolved problems. Both engines
   currently discard baseline payloads into fingerprint sets; once a finding is
   repaired, its stale baseline entry disappears from all reports and no command
   can check or remove it. Plan 047 adds explicit `resolved_baseline`, a shared
   maintenance check exit, and deterministic subtractive pruning for both
   version-1 schemas. It deliberately does not introduce an opaque ignore
   language or auto-baseline new debt.

### 2026-07-16 premium-project loop 3 round 3 (maintenance reporting integrity)

1. **Baseline maintenance gate can be reported as healthy by the Action** —
   traced the newly added exit-9 baseline lifecycle through Plan 046's SARIF
   producer metadata and Action Job Summary. A resolved-only baseline has zero
   active SARIF results, so without explicit metadata the Action emits
   `status=ok` / “No active findings” and then fails with exit 9. Plan 048 adds
   `resolvedBaselineCount`, `status=maintenance`, a resolved-count output and a
   real `uses: ./` maintenance-failure self-test, while keeping resolved debt
   outside Code Scanning results and preserving the exact exit code.

### 2026-07-16 improve loop round 4 (secret-safe diagnostics)

1. **Risky hook findings republish detected credentials** — traced one generated
   credential sentinel from `.claude/settings.json` through `scan_hooks`,
   `surface.hooks`, security finding messages, Markdown/full JSON, SARIF, and PR
   review. The scanner emits a safe type/path secret finding but separately
   copies the credential-bearing hook command into every report surface. Plan
   049 keeps detection on raw commands while exposing only deterministic
   redacted snippets, and pins the guarantee end-to-end across all artifacts.

### 2026-07-16 improve loop round 5 (LLM credential transport)

1. **LLM judge credentials cross untrusted endpoint boundaries** — traced
   `OPENAI_BASE_URL` / `ANTHROPIC_BASE_URL` through stdlib `urllib`. Remote
   `http://` endpoints receive API keys in clear text, and Python's default POST
   302 handling copies `Authorization` / `x-api-key` to a cross-origin redirect.
   Two local generated servers reproduced both sentinel headers at the redirect
   sink. Plan 050 validates HTTPS (with explicit loopback HTTP support), rejects
   unsafe URL components, disables redirects for authenticated judge requests,
   and preserves deterministic built-in fallback without logging credentials.

### 2026-07-16 improve loop round 6 (eval artifact minimization)

1. **Eval results persist credentials printed by runners and judges** — traced a
   generated token from runner stdout into both stored `stdout` and `answer` in
   `results.json`. Timeout/non-zero stderr and external-judge `raw`/`stderr`
   share the same persistence path. Plan 051 centralizes the Plan 049
   high-confidence patterns in a small redaction module, keeps raw bounded output
   for grading/usage in memory, and redacts every persisted result shape before
   serialization.

### 2026-07-17 premium-project loop 4 round 1 (ignored runtime paths)

1. **Repository-gitignored runtime paths fail accurate harness guidance** —
   independently re-audited all nine categories after Plans 001–051, then
   rechecked current AGENTS.md hierarchy guidance, Qwen Code, Dify, dependency
   posture, remote repository protection, and every deferred path class. At
   current Qwen Code commit `f8e6e893`, `.gitignore` positively ignores five
   `.qwen/*` runtime scratch directories that root `AGENTS.md` accurately
   documents; the doctor reports each as both semantic `MISSING` and `D2`.
   Plan 052 delegates nested/negated matching to Git in one contained batch,
   isolates global and `.git/info/exclude` state, and fails closed when Git
   evidence is unavailable. Package-root-relative nested paths and image/RPC
   identifiers remain independent follow-ups rather than prose heuristics.

### 2026-07-17 premium-project loop 4 round 2 (nested package facts)

1. **Nested drift skips the package ancestor between an AGENTS file and repo
   root** — independently re-audited all nine categories after Plan 052,
   including current Dify, nested AGENTS guidance, Action/MCP asymmetries,
   dependency posture, and deferred scope classes. A synthetic conflicting-root
   fixture reproduced false D1, D2, and D6 findings because drift checks only
   the canonical file parent and repository root. Current Dify commit
   `96e34e7b` still reports two false `tree:gen` D1 and five false package-path
   D2 findings from `cli/src/commands/AGENTS.md`, dropping health to 0/F.
   Plan 053 reuses target-aware eval's nearest-first lexical ancestor primitive
   for D1/D2/D6 while preserving D7 Markdown-relative semantics and rejecting
   sibling/prose inference.

### 2026-07-17 premium-project loop 4 round 3 (structured Action arguments)

1. **The Marketplace Action cannot represent exact path-valued CLI arguments**
   — independently re-audited Action/MCP/CLI parity, live workflows, release
   proof, dependency/security posture, deferred external findings, and DX after
   Plans 052–053. `action.yml` parses free-form `args` with Bash
   `read -r -a`: a baseline/rules path containing spaces becomes multiple argv
   values even when quoted, and multiline YAML silently drops every line after
   the first. The direct CLI accepts the same quoted path. Plan 054 adds an
   opt-in JSON string-array `args-json`, parsed and executed by a Node 16
   stdlib helper with `shell:false`, while preserving legacy whitespace
   splitting, Action report order, exact exits, npm overrides, and release
   verification.

### 2026-07-17 post-v1.11.0 improve round 1 (bounded PR feedback)

1. **PR review delivery has no network timeout** — independently re-audited all
   nine categories from the released `v1.11.0` baseline, including current
   dependency posture, repository protection, release/Marketplace state,
   CLI/MCP/Action parity, test gaps, formatter safety, and every network/process
   boundary. A patched current-HEAD post captured GraphQL identity, comment-list
   GET, and summary POST calls; every `urlopen` invocation had no positional or
   keyword timeout. Plan 055 adds one shared per-request bound and clean,
   secret-safe transport failure while preserving dry-run isolation, ownership,
   pagination, summary-first delivery, HTTP-422 fallback, and caller-owned
   workflow fatality.

### 2026-07-17 post-v1.11.0 improve round 2 (current pre-commit install)

1. **The public pre-commit example pins new users to `v1.3.0`** —
   independently re-audited all nine categories after Plan 055, including
   formatter write scope, public examples, CLI/MCP/Action parity, issue intake,
   distribution identity, process/network bounds, dependency posture, and test
   gaps. All seven READMEs still use immutable `rev: v1.3.0` while package/npm/
   GitHub stable is `v1.11.0`. Pre-commit officially caches `rev` as an immutable
   tag/SHA; `v1` is not a supported floating substitute. Although hook metadata
   is unchanged, the selected old runtime predates 7,013 lines of security,
   containment, nested-scope, baseline, and installer changes. Plan 056 updates
   every language to the current exact tag and derives a future-staleness test
   from `package.json`.

### 2026-07-17 post-v1.11.0 improve round 3 (packed npm candidate)

1. **Required CI and release preflight never execute the npm package
   candidate** — independently re-audited all nine categories after Plan 056,
   including release coupling, guard copies, public-surface parity, package
   inventory, input/process bounds, dependencies, remote controls, and prior
   package-test decisions. In an isolated worktree, removing only
   `"scripts/*.py"` from `package.json#files` left all Node tests,
   `npm pack --dry-run`, and bundled checkout doctor self-test green. The real
   tarball still installed successfully, but its installed doctor failed every
   Python engine as missing. Plan 057 packs once, validates inventory, installs
   the exact local tarball under isolated HOME/prefix, executes installed doctor
   before PR merge/release publish, and retains post-publish registry proof.

### 2026-07-17 post-Plan-057 independent deep research rounds

1. **Local all-green parity** — required CI now executes packed-candidate
   verification, but `npm run check` and contributor/agent docs still define the
   authoritative local gate as lint + source tests only. Plan 058 composes the
   candidate into the local aggregate while preserving exactly-once CI
   execution and evidence-bound AGENTS maintenance.
2. **Runtime identifier path precision** — current shared path extraction and
   both semantic/D2 engines reproduce three false errors for Letta's Docker
   image and Codex RPC/API method examples while a real `org/service` directory
   uses the same token shape. Plan 059 adds bounded explicit context at the one
   shared classifier, keeping ambiguity fail-closed and validating against the
   recorded external repositories.
3. **Batch output contract** — `scan --repos-file ... --sarif` exits 0 while
   emitting Markdown, because the batch branch returns before SARIF output
   selection. Plan 060 rejects the unsupported combination before scanning and
   directs automation to aggregate `--json`; cross-repository SARIF remains a
   separate orchestration design rather than a misattributed single file.

### 2026-07-18 post-Plan-058 improve round (repository contract headroom)

1. **Root AGENTS.md has 57 bytes of headroom before its own required strict
   gate** — independently re-audited all nine categories at `8034dc4` and
   reconciled every prior plan: 058 is DONE (PR #267, merge `b62b325`);
   059/060 are REJECTED because both defects were fixed independently in
   `d3a6a3e` with no PR. All evidence for the selected finding was re-opened
   live: `AGENTS.md` is 12,231 bytes; `check_drift.py` `d4_size` emits a D4
   NOTICE above `12 * 1024` = 12,288 bytes and `--strict` promotes every
   NOTICE to a blocking ERROR; appending one harmless 65-byte comment produced
   12,296 bytes, strict exit 1, and score 85/B, while restored current `main`
   is clean 100/A with self-eval 39/39 evidence-bound to the exact AGENTS
   sha256. The standing "re-check `wc -c` in every AGENTS-touching plan"
   mitigation demonstrably failed to preserve headroom (Plan 058 closed at
   57 bytes). Plan 061 completes the file's own progressive-disclosure
   routing — five measured duplicated clusters (2,870 bytes) restate
   mechanics already owned by `references/maintenance-contract.md` or
   repeated inside the root file — and enforces a repository-specific
   ≤ 10,240-byte budget with a deterministic section/routing/relocation test,
   leaving ≥ 2,048 bytes of headroom while product D4 stays unchanged.

   Dependency notes: land the plan-only PR green on all nine required
   contexts first; implementation follows test-first on
   `docs/061-agents-progressive-disclosure` (commit `docs(agents): restore
   progressive-disclosure headroom`), requires an honest self-eval
   refresh/regrade because results bind the AGENTS byte hash (the refreshed
   notes must state accurately that no `eval_run.py` runner/judge model call
   was performed and that the offline regex regrade is not a fresh
   independent model benchmark), keeps the task pack at 39, and is
   patch-level docs/maintenance work with no public runtime/CLI behavior
   change and no package manifest/inventory change — though the shipped
   `references/maintenance-contract.md` prose (and thus tarball bytes) may
   change, with the packed-candidate check still required green. Plan 061
   depends on Plan 058 (DONE) because the
   `local-all-green` invariant it added must survive compaction. The deferred
   formatter footgun (below) must not be mixed into this change.

   Closeout (2026-07-18): plan-only PR
   [#269](https://github.com/NieZhuZhu/ai-harness-doctor/pull/269) merged as
   `1d6b1f8` after 9/9 required checks, then implementation PR
   [#270](https://github.com/NieZhuZhu/ai-harness-doctor/pull/270) merged as
   `380085c` from reviewed head `b7a759e8` after 9/9 required checks and zero
   unresolved threads. The completed contract is 10,227 bytes with 2,061
   bytes of D4 headroom; focused tests passed 38/38, mutation probes 16/16,
   Python 845, Node 51, `npm run check` including the package candidate,
   scan, strict drift 100/A, self-eval 39/39 at 100/A with current evidence,
   and README sync 7/7.

### 2026-07-18 post-Plan-061 independent deep research round

1. **MCP inventory republishes credentials the scanner already detects** —
   independently re-audited all nine categories at `11e3a71`, reconciled every
   prior plan, and reproduced the top security finding with a runtime-generated
   sentinel in `.mcp.json`. The scanner correctly produced two HIGH secret
   findings whose messages contained no value, but the same value remained in
   `surface.mcp_servers[].command` and `.url`, serialized scan JSON, rendered
   Markdown/stdout, and the default 0600 temporary full report. Plans 049 and
   051 protect hook inventory and eval artifacts respectively; neither protects
   MCP command/URL inventory. Plan 062 keeps raw MCP data for detection, reuses
   the shared high-confidence redactor plus Markdown neutralization for a
   report-safe copy, and pins the guarantee across final artifacts.

   Vetted runner-up findings are retained below rather than mixed into the
   smallest security patch: guard install/remove lacks multi-file rollback;
   eval `usage` strings and contradictory stored runner/judge exits can bypass
   existing artifact/integrity contracts; root-generated eval evidence and
   runtime ambiguity diverge from scoped behavior; `actionlint` and exact local
   self-checkup parity are documented but not gated; current formatter scope,
   release/version docs, EOL runtimes, and several provider/MCP/report product
   directions need their own policy or compatibility decisions.

   **Round closeout (Plan 062, 2026-07-18)**: Plan 062 landed as PR #273
   (squash merge `b9fb8a3`, 9/9 required checks, zero unresolved threads,
   Standards/Spec PASS, admin bypass for sole-maintainer self-approval
   only, branch deleted). The implementation introduces `public_mcp_servers()`
   alongside `public_hooks()`, reuses the shared redactor and `_md_safe` for
   every repository-controlled MCP string, and adds an end-to-end sentinel
   matrix across JSON, Markdown, temp report, SARIF, and PR-review payloads.
   `AGENTS.md` records the no-report invariant at 10,228 bytes (SHA
   `fa6e4fe…`). Self-eval stays 40/40 at 100/Grade A with honest
   manual-protocol notes. Vetted runner-up findings (guard multi-file
   rollback, eval `usage`/exit integrity, root-vs-scoped eval parity,
   `actionlint` gating, formatter scope, release-docs truth, EOL runtimes,
   provider/MCP/report product directions) are retained for future rounds.

### 2026-07-18 post-Plan-062 independent nine-category deep audit round

Independently re-audited all nine categories at `9acdafc` (v1.13.2) with eight
parallel read-only category sweeps, reconciled every prior plan (001–062, all
DONE/REJECTED), and reproduced each selected finding live. First surfaced and
immediately fixed an urgent docs-staleness regression: the `v1.13.2` release
bumped `package.json` without the customary follow-up README pre-commit pin
sync, so `test_readme_pre_commit_examples_use_current_exact_release` was red on
`main` for all seven READMEs — landed as its own patch PR
[#276](https://github.com/NieZhuZhu/ai-harness-doctor/pull/276) (bump
`rev: v1.13.1` → `v1.13.2`). Selected three narrow, high-confidence,
independently-reproduced items for this batch:

1. **Conflict-signal `evidence` bypasses the shared redactor and Markdown
   neutralizer** — `scan.extract_signals` stores the entire raw source line as
   `evidence`; it is copied into `report["conflicts"]` and
   `report["scope_overrides"]`, then the on-disk JSON report, the scan Job
   Summary, and — via the shipped `assets/guard/harness-checkup.yml` — a public
   GitHub Issue body (`gh issue ... --body`), while every other
   repository-controlled string (hooks Plan 049, MCP Plan 062, eval Plan 051)
   is run through `redaction.redact_secret_values` + `scan._md_safe`. A crafted
   `AGENTS.md`/`CLAUDE.md` line combining a conflict keyword with a
   credential-shaped value was reproduced verbatim in the conflicts JSON and the
   rendered Markdown. `pr_review.py` is already safe (it rebuilds conflict
   evidence from `path:line`). Plan 063 sanitizes `evidence` once at the capture
   site so every consumer inherits the safe value; detection keys on
   `signal`+`value` and is unchanged.

2. **`eval --regrade` reopens Plan 038's false-success class** — `regrade()`
   recomputes `passed` for a `regex` check from stored `stdout` alone, ignoring
   the record's own `exit_code`/`timed_out`. A stored `exit_code: 9,
   stdout: "OK"` record for a regex task `"OK"` was written back `passed: true`
   and a subsequent `--score` reported a false `100/100 (grade A)`, exit 0 —
   exactly the operational-failure hole Plan 038 closed for live runs, through
   the offline entry point. Plan 065 fails the regex-regrade branch closed on
   stored operational-failure evidence while preserving the legitimate
   fix-the-regex recompute for `exit_code == 0`/absent records.

3. **Unbounded/unescaped engine tokens break `pr_review.py`'s stated safety
   premise** — `semantic._PY_RUN_RE` captures `(\S+)` (unlike its four bounded
   sibling command regexes) and `check_drift._link_target_is_probeable` does not
   reject backticks, so a crafted `poetry|pdm|uv run …` reference or a Markdown
   link target with an embedded backtick reaches a finding `message` that
   `pr_review.py` posts verbatim as an inline PR review comment — whose only
   sanitizer (`_no_embedded_newlines`) documents the false premise that "the
   engines only ever extract regex-bounded tokens." Plan 064 bounds the capture
   and rejects the backtick at the two extraction boundaries, making the premise
   true rather than adding a second escaper.

   Vetted runner-up findings retained for future rounds rather than mixed into
   these narrow patches: guard `--apply`/`--remove` multi-file writes lack the
   installer's transaction/rollback (cross-confirmed by the correctness and
   security sweeps; Plan 037 explicitly scoped it out); core `AGENTS.md`/drift
   `--fix` writes are non-atomic with zero fault-injection coverage (TESTS-01);
   the mmap byte-path secret scan is regression-tested for only 1 of 9 credential
   patterns (TESTS-02); backslash/Windows path normalization has zero test-input
   coverage and CI is ubuntu-only (TESTS-03); shipped guard shell scripts are
   substring-checked, never executed, and `assets/guard/pre-commit.sh` is missing
   from the public-command check (TESTS-04); the scan/drift baseline subsystem is
   hand-duplicated end-to-end and has already diverged in fingerprint strategy
   (DEBT-01); `bin/cli.js` is a 2,756-line four-subsystem god file (DEBT-02);
   eight of nine `scan_render` re-exports are dead (DEBT-04);
   `assets/tasks.example.json` ships in the tarball unreferenced (DEBT-05);
   `scan --repos-file` and the eval matrix run fully serial (PERF-01/02),
   `find_overlaps` re-normalizes per pair (PERF-03), `compare_commands`
   double-walks `package.json` (PERF-04); `npm run format` has no
   `.prettierignore` and would rewrite byte-locked files (DX-01); `actionlint` is
   a documented gate no workflow runs (DX-02); the documented self-checkup
   commands differ from CI's required drift gate (DX-03). Direction options
   (maintainer decisions, not defects): retire the EOL Node 16 / Python 3.9
   floor (release automation itself runs on now-EOL Node 20); extend GitLab/
   Codebase guards with inline MR review comments; add a Phase-2 drift breadth
   artifact to the 14-repo corpus; add a JetBrains Junie registry entry; widen
   installer adapters beyond 4 of 9 detected tools; productize the
   disease-targeted candidate-sampling pipeline.

   **Round closeout (Plans 063–065, 2026-07-18)**: all three implementation PRs
   merged green after 9/9 required checks, zero unresolved threads, admin bypass
   for the sole-maintainer self-approval deadlock only (never over red/pending
   CI), and their branches deleted. The urgent red-`main` docs fix landed first
   as PR [#276](https://github.com/NieZhuZhu/ai-harness-doctor/pull/276)
   (`21fb964`), then the plan-only PR
   [#277](https://github.com/NieZhuZhu/ai-harness-doctor/pull/277) (`66ab9db`).
   - **Plan 063** — PR [#278](https://github.com/NieZhuZhu/ai-harness-doctor/pull/278),
     merge `5c68d3f`. `scan.extract_signals` now sanitizes the conflict-signal
     `evidence` at its single capture site with `_md_safe(redact_secret_values(line))`;
     a new cross-surface test asserts a `ghp_…` sentinel and stray backticks are
     absent from the JSON, Markdown, and temp-report while the `package_manager`
     conflict is still detected. `AGENTS.md` unchanged (10,228 bytes).
   - **Plan 065** — PR [#279](https://github.com/NieZhuZhu/ai-harness-doctor/pull/279),
     merge `2f88e33`. `regrade()` fails the regex branch closed when a stored
     record carries operational-failure evidence (non-zero `exit_code` or
     `timed_out`); `exit_code == 0`/absent records keep recomputing. Four new
     tests cover non-zero-exit, timeout, `exit_code == 0` happy path, and
     absent-`exit_code` manual-protocol compatibility.
   - **Plan 064** — PR [#280](https://github.com/NieZhuZhu/ai-harness-doctor/pull/280),
     merge `6f5a513`. `_PY_RUN_RE` bounded to `([^\s`|]+)` and the D7
     link probe rejects backticks. Implementation note: the plan's proposed
     `[A-Za-z0-9._-]+` was corrected to `[^\s`|]+` during execution because the
     former truncates `uv run examples/simple.py` to `examples` and reintroduces
     a false positive already guarded by the existing
     `test_uv_run_script_file_not_flagged`; the chosen bound keeps `/`/`.py` in
     the capture (script-file filter intact) while excluding backtick/pipe.
   - **Final `main` state**: strict drift 100/Grade A, self-scan exit 0, Python
     853 + Node 51 green, `npm run check` (incl. packed candidate) green,
     README sync 7/7.

### 2026-07-19 post-v1.13.6 deep improve round 1

Independently re-audited all nine categories on current
`main@0232401` and reconciled Plans 001–065 (all DONE/REJECTED). The baseline
was verified rather than inferred: scan had no new gated findings, strict drift
was 100/A, evidence-bound self-eval passed 40/40, npm 10.8.2 against
`registry.npmjs.org` reported zero vulnerabilities, the latest main workflows
were green, and the remote branch read-back still required all nine documented
contexts with secret scanning/push protection enabled. The local
`/usr/local/bin/npm` is an obsolete npm 6 wired to an internal registry and
cannot execute the modern package-candidate/audit paths; that host-tool failure
is not recorded as a repository failure or a green gate.

The selected finding is **guard multi-file transaction safety**. The
`applyGuardChanges()` path validates every hook/worktree path first, then
directly applies the ordered writes/removals with no journal or rollback. Two
isolated filesystem fault injections reproduced both halves:

1. `guard --apply --provider github` with a writable Git hook directory and
   non-writable worktree root installed `.git/hooks/pre-commit`, then failed
   creating `.github/workflows`; both workflows and the `AGENTS.md` maintenance
   contract remained absent.
2. From a complete install, `guard --remove --apply` with a non-writable
   workflow directory deleted the pre-commit hook, then failed unlinking the
   first workflow; both workflows and `AGENTS.md` remained installed.

Plan 066 specifies a separate repository-local transaction below the resolved
Git common directory: fixed guard allow-list, exact byte/mode snapshots,
write-ahead expected states, atomic file replacement, caught-error rollback,
abrupt-exit recovery, live-owner serialization, and fail-closed handling of
post-crash edits or malformed/symlinked/escaping/tampered state. It explicitly
does not couple guard to the HOME installer manifest/transaction and preserves
foreign/edited-file ownership semantics.

**Round closeout (2026-07-19):** plan-only PR
[#289](https://github.com/NieZhuZhu/ai-harness-doctor/pull/289) merged as
`e7e48f7` after 9/9 required checks. Implementation PR
[#290](https://github.com/NieZhuZhu/ai-harness-doctor/pull/290) passed 9/9
required checks on reviewed head `1abb451`, had zero unresolved threads, and
was squash-merged as `28150ef`; both remote branches were deleted. The final
transaction uses Git-common-dir state, a fixed guard allow-list, exact
byte/`0o7777` mode snapshots, write-ahead file/temp/parent states, live-owner
serialization, atomic commit/rollback retirement points, and fail-closed
recovery. Fault injection covers caught failures, install/remove and
atomic-write crashes, a second recovery crash, post-crash edits, unsafe or
tampered state, all providers, and linked worktrees. Standards/Spec and
`bits-code-guard` reviews have no remaining P0–P2 findings. Local final evidence
was 885 Python + 51 Node tests, packed candidate, scan, strict drift 100/A,
current-evidence self-eval 40/40, public-registry audit with zero
vulnerabilities, and `AGENTS.md` at 10,237 bytes.

### 2026-07-20 post-Plan-066 deep improve round 2

Independently re-audited all nine categories on clean
`main@cf96c2a` after the complete Plan 066 three-PR closeout. The new baseline
was re-established rather than inherited: scan exited 0, strict drift was
100/A, current-evidence self-eval passed 40/40, the worktree was clean, recent
main workflows were green, and the remote branch read-back still required the
same nine contexts plus resolved conversations.

The selected finding is **nested eval usage metadata bypasses credential
redaction**. A temporary runner printed a passing JSON envelope with one
runtime-generated GitHub-token sentinel under `usage.trace`, `cost.note`, and a
`tokens` list. The task passed and the persisted stdout correctly replaced all
three values with `<redacted:GitHub token>`, proving Plan 051's raw-grading /
persisted-text boundary worked. The separate `usage` copy retained all three
sentinels verbatim in the result JSON because `maybe_usage()` copies arbitrary
nested values and `sanitize_result_record()` visits only
stdout/answer/stderr/judge fields. Single, multi-round, and matrix producers all
reuse that record; `--compare` also renders usage from supplied historical or
manual results without a sanitization boundary.

Plan 067 adds one JSON-compatible safe-copy sanitizer for nested usage string
keys/values, preserving numeric billing data and container shape, and applies
it at the shared task-record persistence boundary. It separately sanitizes and
Markdown-neutralizes comparison rendering because historical inputs may predate
the fix. Grading, usage extraction, secret patterns, result schema, health, and
the usage allow-list remain unchanged.

**Round closeout (2026-07-20):** plan-only PR
[#292](https://github.com/NieZhuZhu/ai-harness-doctor/pull/292) merged as
`029f8d5` after 9/9 required checks. Implementation PR
[#293](https://github.com/NieZhuZhu/ai-harness-doctor/pull/293) passed all nine
contexts on reviewed head `1e9f1bc`, had zero unresolved threads, and was
squash-merged as `b26974f`; both remote branches were deleted. The final
iterative safe-copy sanitizer covers nested string keys/values, collision-safe
suffixes, deep containers, numeric compatibility, successful/non-zero records,
single/round/matrix/regrade artifacts, and historical/manual comparison stdout
and files without rewriting inputs. Standards/Spec/security review has no
remaining P0–P2 findings. Final local evidence: 892 Python + 51 Node tests,
146 eval-focused tests, packed candidate, scan, strict drift 100/A,
current-evidence self-eval 40/40, public-registry audit with zero
vulnerabilities, and `AGENTS.md` at 10,171 bytes.

### 2026-07-20 post-Plan-067 deep improve round 3

Independently re-audited all nine categories on clean
`main@5280ad3`. Baseline scan exited 0, strict drift was 100/A,
current-evidence self-eval passed 40/40, and remote required-check/security
posture remained intact.

The selected finding is **stored result passes can contradict explicit
operational failure evidence**. Four one-record files claimed `passed:true`
while recording runner exit 9, timeout, judge exit 7, or judge
`passed:false`. Both `--score --fail-under 80` and `--stats` exited 0 and
reported 100/A for every case; the timeout record simultaneously reported one
passed task and one timeout. The shared `_validate_result_records()` checks
types for `id`/`passed`/`timed_out` but does not reconcile explicit operational
evidence before `compute_health()` trusts `passed`.

Plan 068 extends the shared read validator. It rejects only explicit
contradictions with a safe `result error`/exit 2 before health, evidence,
threshold, baseline, compare, or regrade side effects. It does not normalize
input or require operational fields, preserving manual/historical records that
omit them. Top-level failures remain valid even if other evidence looks
successful; the scope is false green.

**Round closeout (2026-07-20):** plan PR
[#295](https://github.com/NieZhuZhu/ai-harness-doctor/pull/295) merged as
`6aefcb1` after 9/9 checks. Implementation PR
[#296](https://github.com/NieZhuZhu/ai-harness-doctor/pull/296) passed 9/9 on
reviewed head `11d146a`, had zero unresolved threads, and was squash-merged as
`8e61ba3`; both branches were deleted. The shared validator now covers explicit
runner timeout/non-zero exit and judge non-zero/rejection contradictions while
preserving omitted/null operational fields, top-level failures, ungraded
regrade input, and legacy non-object judge metadata. Tasks/rounds/bare-rounds/
agents and score/stats/compare/regrade no-side-effect paths are tested.
Standards/Spec/integrity review has no remaining P0–P2 findings. Final evidence:
898 Python + 51 Node tests, 152 eval tests, packed candidate, scan, strict drift
100/A, self-eval 40/40, audit zero vulnerabilities, AGENTS 10,156 bytes.

Runner-ups were rechecked but rank lower: root-generated tasks omit fact
evidence and therefore fail closed when current evidence is required rather
than false-green; `drift --fix --apply` remains non-transactional; `actionlint`
remains documented but unenforced; broad formatter ownership and runtime-floor
changes remain policy/migration decisions.

The highest runner-up is also mechanically reproduced but deliberately kept
separate: three stored records that claimed `passed: true` while carrying,
respectively, runner `exit_code: 9`, `timed_out: true`, or judge
`exit_code: 7` all passed `--score --fail-under 80` at 100/A. Root-generated
tasks still omit fact evidence and therefore fail `--require-current-evidence`
with no manifest (fail closed rather than false green); `drift --fix --apply`
multi-file writes remain non-transactional; and `actionlint` remains a
documented but unenforced local/CI gate. Product-direction options remain
separate from these correctness/security defects.

Vetted runner-ups remain separate: the documented `actionlint` gate is not
required locally or in CI; `npm run format` still has unsafe authority over
historical evidence/generated/synchronized files; shipped provider shell
templates are mostly substring-tested rather than executed; and Node-native
coverage of the monolithic CLI remains low even though high-risk paths have
Python black-box integration tests. Direction candidates (provider-neutral eval
gate config, read-only MCP eval verification, and additive public JSON schema
versions) are product decisions, not substitutes for the reproduced mutation
integrity defect.

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
| 036 | Keep one current AI Harness Doctor summary per pull request | P1 | M | — | DONE |
| 037 | Make installer filesystem changes and ownership state transactional | P0 | L | 008, 011 | DONE |
| 038 | Prevent failed runners and judges from producing passing eval records | P0 | M | 030, 033 | DONE |
| 039 | Model Claude Code project rules and their path applicability | P1 | L | 020, 023, 035 | DONE |
| 040 | Prevent provisional AGENTS drafts from authorizing stub destruction | P1 | M | 004, 008, 011, 037 | DONE |
| 041 | Validate the eval baseline-history store before trend/regression reads | P1 | S | 033 | DONE |
| 042 | Make SARIF alert identity survive edits and coexist per command | P1 | M | 012, 024 | DONE |
| 043 | Fall back to the deterministic judge when an LLM returns unparseable output | P1 | S | — | DONE |
| 044 | Recover from an incomplete installer transaction directory instead of bricking | P1 | S | 011, 037 | DONE |
| 045 | Make scoped eval use the shared lockfile registry | P1 | S | 027, 029 | DONE |
| 046 | Make the GitHub Action emit composable quality outputs and a Job Summary | P1 | M | 012, 034, 042 | DONE |
| 047 | Make repaired baseline debt visible, checkable, and prunable | P1 | L | 007, 021 | DONE |
| 048 | Report baseline maintenance failures truthfully through SARIF and the Action | P1 | M | 046, 047 | DONE |
| 049 | Redact hook-command secrets from every report surface | P0 | M | 024, 042 | DONE |
| 050 | Keep LLM judge API keys on trusted endpoints | P0 | M | 043 | DONE |
| 051 | Redact secrets before persisting eval result artifacts | P0 | L | 049, 050 | DONE |
| 052 | Stop treating repository-gitignored runtime paths as stale | P1 | M | 014, 018, 021 | DONE |
| 053 | Resolve nested AGENTS facts through the lexical package ancestor chain | P1 | M | 018, 021, 045, 052 | DONE |
| 054 | Add structured GitHub Action arguments without shell evaluation | P1 | M | 022, 034, 046, 048 | DONE |
| 055 | Bound every GitHub PR-review network request | P1 | S | 010, 036 | DONE |
| 056 | Keep the pre-commit example on the current stable release | P1 | S | 003, 005, 019 | DONE |
| 057 | Execute the packed npm candidate before publication | P0 | M | 005, 025, 028, 034 | DONE |
| 058 | Make the local all-green command cover the required package gate | P1 | S | 057 | DONE — PR [#267](https://github.com/NieZhuZhu/ai-harness-doctor/pull/267), merge `b62b325`, 9/9 required checks |
| 059 | Distinguish Docker and RPC identifiers from repository paths | P1 | M | 014, 018, 052, 053 | REJECTED — fixed independently in `d3a6a3e`; no PR |
| 060 | Reject unsupported batch SARIF instead of emitting Markdown | P1 | S | 012, 032, 042 | REJECTED — fixed independently in `d3a6a3e`; no PR |
| 061 | Restore AGENTS.md progressive-disclosure headroom | P1 | M | 058 | DONE — PR [#270](https://github.com/NieZhuZhu/ai-harness-doctor/pull/270), merge `380085c`, 9/9 required checks |
| 062 | Redact MCP credentials from every scan-report surface | P0 | S–M | 049, 051 | DONE — PR [#273](https://github.com/NieZhuZhu/ai-harness-doctor/pull/273), merge `b9fb8a3`, 9/9 required checks |
| 063 | Redact and Markdown-neutralize conflict-signal evidence | P0 | S | 049, 051, 062 | DONE — PR [#278](https://github.com/NieZhuZhu/ai-harness-doctor/pull/278), merge `5c68d3f`, 9/9 required checks |
| 064 | Bound and neutralize semantic/drift finding-message tokens | P1 | S | — | DONE — PR [#280](https://github.com/NieZhuZhu/ai-harness-doctor/pull/280), merge `6f5a513`, 9/9 required checks |
| 065 | Make eval `--regrade` honor stored operational-failure evidence | P1 | S | 038 | DONE — PR [#279](https://github.com/NieZhuZhu/ai-harness-doctor/pull/279), merge `2f88e33`, 9/9 required checks |
| 066 | Make guard install and removal transactional across every managed file | P0 | M | 004, 008, 011, 037, 044 | DONE — PR [#290](https://github.com/NieZhuZhu/ai-harness-doctor/pull/290), merge `28150ef`, 9/9 required checks |
| 067 | Redact secrets from nested eval usage metadata before persistence or rendering | P0 | S | 051 | DONE — PR [#293](https://github.com/NieZhuZhu/ai-harness-doctor/pull/293), merge `b26974f`, 9/9 required checks |
| 068 | Reject stored eval passes that contradict explicit operational failure evidence | P0 | S | 033, 038, 065 | DONE — PR [#296](https://github.com/NieZhuZhu/ai-harness-doctor/pull/296), merge `8e61ba3`, 9/9 required checks |
| 069 | Report the harness maturity ladder in scan | P1 | M | — | DONE — PR [#302](https://github.com/NieZhuZhu/ai-harness-doctor/pull/302), merge `3da9a77`, 9/9 required checks |

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
- Plan 066 reuses the already-DONE Plans 004/037 containment and recovery
  patterns but keeps guard state independent from the adapter installer
  manifest. Land its plan-only PR first, then implement test-first from the
  resulting latest `main`; use a separate green closeout PR after the
  implementation is squash-merged.
- Plan 067 extends the already-DONE Plan 051 redaction boundary without changing
  raw grading or result schema. Land plan-only, implement the nested sanitizer
  and comparison boundary test-first, then use the same green closeout cycle.
- Plan 068 extends the shared Plan 033 stored-result validator with the
  Plans 038/065 operational truth. Keep omitted legacy fields compatible,
  implement test-first, and use the same plan/implementation/closeout cycle.
- Plan 069 is a product feature (premium-upgrade loop, user-requested): a
  deterministic maturity-ladder view assembled from existing scan signals. It
  must keep `find_gaps` output byte-identical, keep every stack-dependent
  signal advisory-only per the G5–G8 retirement precedent, and change no
  default exit semantics. Land plan-only, implement test-first, then the same
  green closeout cycle; ships as a minor release.
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
  `2026-07-15T23:51:39Z`. Second head `5673d11` passed the same nine contexts,
  kept exactly that one marker/ID, and advanced its `updated_at` to
  `2026-07-15T23:53:22Z`, proving the production GraphQL-identity upsert path.
- Plan 037 depends on the already-DONE ownership and atomic-manifest contracts
  from Plans 008/011. Keep manifest schema 2 and use a sidecar journal. Snapshot
  before every mutation; persist the exact next-manifest digest before atomic
  replacement so startup can distinguish rollback from committed cleanup.
- Plan 037 implementation is in progress on
  `fix/037-transactional-installer`. The local gate is 689 Python + 26 Node
  tests, including 56 installer lifecycle cases for caught failure,
  interruption recovery, concurrency locks, journal/backup tampering,
  containment, mode preservation, and update-nudge ledger isolation.
- Plan 037 implementation PR #194 first head `225ff9f` passed all nine required
  contexts. The final evidence head adds malformed/symlinked lock-state refusal
  and passed the full matrix again as `58bf875`. The implementation preserves
  manifest schema 2 and adds durable fsync journal recovery, idempotent
  rollback, process serialization/dead-lock claims, managed-path allow-list,
  backup/mode integrity, and a separate non-authoritative update-nudge cache.
- Plan 038 depends on task/result validation from Plans 030/033 but addresses a
  different producer boundary: process exit status must dominate stdout content.
  Preserve diagnostic records and matrix continuation; do not change overall
  eval exit semantics or remove explicit shell-template support.
- Plan 038 implementation is in progress on
  `fix/038-eval-runner-judge-exits`. Local baseline: 696 Python + 26 Node tests,
  including 113 eval tests for single/round/matrix non-zero runners, judge
  failures/no fallback, output bounds, process-group timeout, and historical
  result/evidence compatibility.
- Plan 038 implementation PR #196 head `8a63c43` passed all nine required
  contexts. Single/round/matrix now share one operational gate; runner/judge
  exit failures cannot pass, outputs are bounded, and overall CLI failure
  remains controlled by existing health/regression flags.
- Plan 039 builds on the DONE structured-scope and explain contracts from
  Plans 020/023/035. Keep Claude rule discovery in the shared registry and
  applicability engine; complete identity/security reads, current-path scan
  domains, and concrete future-target explain must stay one model. Recursive
  reads must not add `.claude/rules/` to Treat/stub/fix ownership.
- Plan 039 adds a recognized public Claude Code instruction surface and is
  therefore minor-release work if its compatibility STOP conditions do not
  expose a breaking requirement. It remains one plan PR followed by one
  implementation PR, each requiring all nine protected contexts.
- Plan 039 plan PR #197 and implementation PR #198 passed all nine required
  contexts. The implementation squash-merged as `26b07b0` with registry-backed
  Claude rule inventory, bounded `paths` applicability, complete report/Action
  coverage, Bitwarden/Algolia validation, and unchanged Treat ownership.
- Plan 040 is a separate correctness/safety repair. Exact generated provisional
  markers must fail validation, and stub apply must reuse canonical readiness
  before any write/delete. Keep ordinary TODO prose, library-doc soft warnings,
  pre-migration STUB notices, dry-run utility, and MCP's finding-vs-operational
  distinction compatible. This is patch-level unless a STOP condition requires
  a new approval artifact or breaking flag.
- Plan 040 plan PR #199 and implementation PR #200 passed all nine required
  contexts; the implementation squash-merged as `a5c6195` with a shared
  canonical-readiness helper, exact `DRAFT_REVIEW` markers, apply preflight,
  and preserved dry-run / MCP-finding semantics.
- Plan 041 depends only on the DONE Plan 033 validation model and extends it to
  the deferred history store. Keep the append-only baseline schema and every
  valid history byte-compatible; only add fail-closed validation plus
  numeric-snapshot derivation so a malformed store exits `2` with a `result
  error` instead of a traceback or a silent skip. This is patch-level unless a
  STOP condition forces a schema change.

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

- **Implement one cross-repository SARIF document in Plan 060** — rejected.
  Artifact URIs from unrelated roots would be interpreted relative to the
  repository receiving the upload. Separate SARIF files/categories/uploads need
  a concrete orchestration consumer and must not be approximated silently.
- **Globally ignore every two-segment lowercase `org/name` token** — rejected.
  Real repositories contain paths with exactly that shape. Plan 059 requires
  explicit bounded Docker/RPC/API labels and positive filesystem controls.
- **Treat Plan 057's required CI success as proof of local `npm run check`
  parity** — rejected. Direct manifest/document evidence shows the local
  aggregate still omits `check:package`; CI runs it as a separate step.
- **Promote automatic all-scope eval generation in these rounds** — deferred
  again. Explicit target generation is proven, but there is still no measured
  cost/task-selection policy for a default that may multiply paid runs across
  large monorepos.
- **Record update-check timestamps only after a successful registry response**
  — real minor DX issue, revalidated, but it delays only a best-effort update
  nudge and does not affect diagnosis, mutation, CI, or publication. It ranks
  below the three reproduced correctness/contracts above.
- **Make `npm run format` authoritative in these rounds** — deferred. Its broad
  write set is real, but choosing formatting ownership for historical evidence,
  fixtures, generated sources, workflows, and seven READMEs remains a separate
  migration decision rather than a narrow correctness repair.

- **Treat post-publish exact npm verification as sufficient package testing** —
  rejected. It catches registry/package defects only after immutable
  publication. Plan 057 keeps that proof and adds the missing pre-publication
  candidate boundary.
- **Validate only a hard-coded file list from `npm pack --dry-run`** — rejected.
  A long duplicate list can drift and still does not prove installed dispatch.
  Plan 057 combines derived/explicit inventory policy with installation and
  `doctor --self-test` against the real tarball bytes.
- **Run the package verifier in all three Node matrix jobs** — rejected as
  redundant cost and race/noise. One existing required job is enough; release
  preflight runs it independently at the exact tag.
- **Add a `prepack` or lifecycle generator to repair omissions automatically** —
  rejected. Packaging must be complete from reviewed checkout bytes, and local
  candidate install deliberately disables scripts. Generation would hide
  allowlist defects and expand the supply-chain surface.
- **Remove bundled Action preflight once candidate smoke exists** — rejected.
  The Action's checked-out wrapper/bundled behavior and the npm tarball are
  separate public distribution paths; both require pre-publish evidence.
- **Turn the transient GitHub protection HTTP 503 into a product finding** — no
  finding. The read-back failed once while recent PR enforcement and prior
  verified settings remained intact; no repository operation or product code
  depends on that ad-hoc audit call.
- **Treat the broad `npm run format` write set as Plan 056** — rejected after
  fresh isolation. The command successfully rewrites 106 tracked files plus a
  worktree-local symlink, including historical evidence and fixtures; however,
  choosing the intended formatting authority would require a separate
  policy/migration decision. It does not explain or repair the concrete public
  `rev: v1.3.0` consumer pin. Keep it as an independently scoped DX candidate.
- **Use floating `rev: v1` in the pre-commit snippet** — rejected by the
  consumer's official contract. Pre-commit assumes `rev` is immutable and
  caches it; branch/moving-tag behavior is unsupported. Plan 056 keeps an exact
  stable tag and makes release bumps update it explicitly.
- **Rely only on `pre-commit autoupdate` instead of fixing the example** —
  rejected. Autoupdate helps existing consumers who run it, but every new user
  copying the repository's primary example should start on the current stable
  release rather than an eight-minor-old runtime.
- **Change `.pre-commit-hooks.yaml` because its hash is old** — no finding. Its
  bytes are intentionally identical at `v1.3.0` and `v1.11.0`; the defect is
  the runtime ref selected by the README, not hook metadata.
- **Fix generic backtick-file \"stale refs\" from the docs sweep** — rejected as
  false leads. The reported names are examples, generated consumer paths, or
  basenames whose owning directory is explained in prose; no current broken
  public command/link was established.
- **Make `npm run format` safe in the same Plan 055 change** — rejected as a
  separate DX contract. Current `prettier --check .` reports 105 files and the
  write command can touch generated adapters, guard-template/self-copy pairs,
  seven synchronized READMEs, fixtures, and historical plans. That is a real
  maintainer footgun, but it neither causes nor fixes unbounded PR-feedback
  networking; re-audit it independently after Plan 055.
- **Add retries or one global deadline while bounding PR-review HTTP** —
  rejected. The comment scan is already bounded to ten pages, and writes are not
  uniformly safe to retry when authenticated identity is unavailable. Plan 055
  adds the smallest deterministic per-request bound; retries/global budgeting
  require a separate idempotency design and measured need.
- **Change the self-bootstrap workflow's `|| echo` posting policy** — rejected.
  The shipped template intentionally treats posting as required, while this
  repository soft-fails token/API restrictions on fork PRs. The helper must
  terminate in both cases; workflow fatality remains an explicit caller policy.
- **Dependency/security remediation after v1.11.0** — no finding. Both runtime-
  omitted and full `npm audit` reports contain zero vulnerabilities, public
  registry/release/floating-tag identity is current, branch protection still
  requires all nine contexts plus conversation resolution, and secret scanning,
  push protection, and Dependabot security updates remain enabled.
- **Refactor the large scan/eval/CLI modules in round 1** — rejected again.
  Current file size/churn did not produce a new correctness, performance, or
  testability failure. The selected network defect has one deep existing seam
  and a direct regression test.
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
- **Record `lastUpdateCheck` only after a successful registry response** —
  confirmed as a minor DX flaw, but a transient miss merely delays another
  best-effort nudge and never affects commands or installed state. Defer behind
  Plan 037's reproduced ownership inconsistency.
- **Treat atomic `manifest.json` replacement as an atomic installer command** —
  rejected. Plan 011 protects old ledger bytes but cannot roll back adapters and
  payloads already written/deleted. Plan 037 explicitly spans both surfaces.
- **Use only a preflight manifest writeability check** — rejected. Permissions,
  disk state, and process failure can change after preflight; it does not close
  the reproduced final-replacement or interruption windows.
- **Treat operator runner/judge shell templates as task-data command injection**
  — rejected. These commands are explicitly supplied by the operator; prompt,
  answer, rubric, and temp-input substitutions are shell-quoted. Plan 038 keeps
  this interface and fixes exit-status truth.
- **Add automatic all-scope/task/round/cost caps in round 3** — deferred again.
  Task preflight prevents malformed paid execution and explicit target
  generation controls scope, but no measured default budget supports a
  non-breaking cap. The selected false-success bug directly invalidates health.
- **Expose paid eval execution over MCP** — rejected for safety. MCP remains
  read-only and offers task generation only; no runner, judge, API key, or
  output-write surface should be added.
- **Add Kiro/Augment/Amazon Q filenames instead of Claude project rules** —
  rejected again in loop 1 round 1. Breadth without semantics would only expand
  inventory. Claude rules have a current first-party contract, widespread
  public evidence, and an existing deterministic scope seam to reuse.
- **Parse arbitrary YAML to support every Claude frontmatter form** — rejected.
  The required `paths` list is a small documented metadata subset; general YAML
  would violate stdlib-only constraints and enlarge the parser/security
  surface. Plan 039 specifies block/inline sequences and bounded glob syntax.
- **Follow external `.claude/rules/` symlinks because Claude Code does** —
  rejected. Runtime sharing and repository auditing have different trust
  boundaries. External bytes remain excluded; in-repo aliases retain lexical
  evidence paths.
- **Delete or rewrite recursively discovered Claude rules during Treat** —
  rejected. Read completeness does not prove write ownership. Plan 039 leaves
  the Claude stub targets flat and adds a no-recursive-mutation regression.
- **Reject every TODO in AGENTS.md** — rejected in loop 1 round 2. Repository
  owners may intentionally document TODO policies or task conventions. Plan
  040 matches only exact product-owned provisional markers/prompts.
- **Treat a clean Git tree as proof of semantic readiness** — rejected. Git
  makes stub replacement recoverable but cannot prove the generated TODOs and
  inferred conflict defaults were reviewed.
- **Let `--force` bypass unreviewed draft markers** — rejected. The flag
  currently accepts dirty-tree risk; expanding it into a semantic/path safety
  bypass would conflate unrelated trust decisions.
- **Require a signed approval sidecar or reviewer identity** — rejected as
  disproportionate and non-deterministic. Exact marker resolution is a bounded,
  reviewable intent signal; scripts still do not claim human correctness.
- **Rewrite the baseline-history schema while validating it** — rejected in
  loop 1 round 3. The append-only snapshot list is a public artifact; Plan 041
  only adds fail-closed validation and numeric-snapshot derivation, keeping
  every valid history byte-compatible.
- **Reject an entire baseline history when one snapshot is malformed** —
  rejected. A single corrupt entry should surface a concise `result error`, not
  discard a long legitimate history; Plan 041 fails closed on structural
  corruption but treats a merely missing/non-numeric score as a non-comparable
  snapshot, matching current trend rendering.
- **Add a broad result-JSON schema validator spanning all consumers** —
  rejected again. Plan 033 deliberately scoped record validation to
  score/stats/compare/regrade; Plan 041 closes only the one deferred history
  consumer rather than centralizing an over-broad validator.
- **Add GitHub Action `outputs` (health-grade/findings-count/drift-status) and a
  `$GITHUB_STEP_SUMMARY` write** — real premium-surface candidate and the
  runner-up this loop, but deferred behind Plan 042. It needs the CLI to expose
  a machine-readable grade/finding count the composite step can parse, so it is
  a larger, separate feature; the SARIF alert-lifecycle defects are already
  user-visible the moment anyone uploads the current SARIF. Revisit as its own
  plan once the fingerprint/category contract is stable.
- **Emit SARIF for `--repos-file` batch mode with per-repo categories** —
  rejected for Plan 042. Batch mode returns before the `--sarif` branch and has
  no SARIF today; giving each repo a distinct `automationDetails` category is a
  real multi-run upload design (one category per repository, coordinated with
  `upload-sarif`), not a fingerprint tweak. Monorepo packages intentionally stay
  in one run/category. Defer until batch SARIF has a concrete consumer.
- **Import `scan.py` into `sarif.py` to reuse `scan_finding_fingerprint`** —
  rejected. `sarif.py` is a light, dependency-free translation layer;
  importing the heavy scanner would risk a cycle and pull unrelated surface into
  the SARIF path. Plan 042 re-implements the small documented identity subset
  locally and pins it to `scan.scan_finding_fingerprint` with a parity test.
- **`eval_run.py` keeps a local `PKG_MANAGER_LOCKFILES` diverging from
  `registry.LOCKFILE_MANAGERS`** (improve loop round) — real, verified: the
  scoped path `_scoped_package_manager` iterates the local list (which adds
  `pnpm-lock.yml`), while `detect_package_manager` (root) and every other engine
  route through `registry.LOCKFILE_MANAGERS` via `facts.lockfile_managers`; the
  consistency test guards `detect_package_manager` but never asserts
  `PKG_MANAGER_LOCKFILES == registry.LOCKFILE_MANAGERS`. Not selected for round 1
  (narrow blast radius: only scoped `--target` eval on a `pnpm-lock.yml` repo),
  but a good self-contained round-2/3 candidate — single-source the list and add
  a consistency assertion.
- **`npm run format` has no `.prettierignore` and rewrites single-source files**
  (improve loop round) — real, verified with `prettier --check .` (91 files
  would change, including `assets/agent-tools.json`, `assets/guard/*.yml` twins,
  and the trilingual READMEs), and it is documented as a contributor command in
  all three READMEs. A genuine footgun; not selected for round 1 (DX hygiene, not
  a shipped-behavior defect). Good round-2/3 candidate — add a `.prettierignore`
  (or narrow the script to `bin/**`) so the documented command cannot desync the
  byte-locked sources.
- **`AGENTS.md` sits ~55 bytes under its own strict-mode 12288-byte failure
  threshold** (improve loop round) — real headroom risk (`check_drift.py` D4
  NOTICE at `> 12 * 1024`, promoted to blocking ERROR under `--strict`, run by
  the repo's own guards). Considered; the standing mitigation is that every plan
  that touches `AGENTS.md` re-checks `wc -c` and relocates prose to `references/`
  when needed. Track as a housekeeping candidate (relocate a dense Conventions
  bullet to `references/`) rather than a behavior fix.
- **`assets/tasks.example.json` is unreferenced and unpublished** (improve loop
  round) — verified: no `scripts`/`bin`/`tests`/docs reference and absent from
  the `package.json` `files` allowlist. Low-value cleanup candidate (delete, or
  wire into the eval docs + `files`). Not a behavior defect.
- **`llm_judge` / base-URL redirect & scheme validation, hook-command snippet in
  SARIF/PR, Treat write TOCTOU, stored eval stdout secrets, missing GitHub API
  timeout** (improve loop security sweep) — surfaced by the security sweep and
  logged for future consideration; each needs independent confirmation of a
  concrete, reachable impact before planning. Not selected for round 1 (the
  documented LLM-judge fallback contract violation in Plan 043 had the clearest
  reproduction and highest leverage). Do not treat as settled — revisit with a
  focused `security` audit.
- **`check_drift --fix` inverted unsafe-stub filter / `run_fix` remaining-count /
  `pr_review` summary-only index location** (improve loop correctness sweep) —
  CORRECTNESS-02 is locked in by an existing test (`test_fix_apply_refuses_
  external_stub_symlink`) so its "silently skip all fixable stubs when one is
  unsafe" behavior may be intended-refuse-all; the run_fix and pr_review items
  were investigated and are cosmetic/cleared. Not selected; revisit
  CORRECTNESS-02 only after confirming the intended fix-safe-vs-refuse-all
  contract with the maintainer.
- **Keep relying on per-plan `wc -c` re-checks for AGENTS.md size**
  (2026-07-18 round) — rejected as a failed mitigation, promoting the earlier
  "~55 bytes under the strict threshold" housekeeping entry to Plan 061.
  Plan 058's closeout landed `AGENTS.md` at 12,231 bytes, 57 bytes under the
  strict D4 threshold, so the standing per-plan discipline preserved no
  headroom; a repository-owned tested budget replaces it.
- **Weaken or repository-parameterize the product D4 thresholds instead**
  (2026-07-18 round) — rejected. The `12 * 1024` NOTICE, strict promotion,
  and `DEFAULT_MAX_BYTES` are shipped product semantics validated on external
  repositories; Plan 061 leaves them byte-identical and enforces the lower
  ≤ 10,240-byte budget only through this repository's own deterministic test.
- **`npm run format` rewrites tracked sources (formatter footgun)**
  (2026-07-18 round) — independently revalidated at `8034dc4` with a locked
  `npm ci --ignore-scripts` install: `prettier --check .` now reports
  128 files that `--write` would rewrite (56 plans, 31 benchmark, 10
  `.github` workflow/guard, 8 `bin`, 6 `commands`, 6 `assets`, 1
  `.ai-harness-doctor`, and 10 root docs including all seven READMEs and
  `SKILL.md`; zero test files), up from the 91 and 106 recorded in earlier
  rounds. (Those counts are the `8034dc4` baseline; the Plan 061 plan-only
  branch adds `plans/061-restore-agents-progressive-disclosure-headroom.md`,
  so the same check on that branch reports 129 files, 57 in `plans/`.) Deferred to the next round after Plan 061, not selected now:
  AGENTS headroom blocks every future stable-rule addition and has a cleaner,
  bounded fix, while formatter ownership over historical evidence, fixtures,
  generated adapters, synchronized READMEs, and workflow twins remains a
  policy/migration decision. No other candidate this round produced a
  reproduced defect that outranked these two.
- **Guard apply/remove is not a multi-file transaction** (2026-07-18 round B)
  — independently reproduced at `11e3a71`: with the Git hook directory
  writable and the repository root non-writable, `guard --apply --provider
  github` exits on the first workflow-directory write after it has already
  installed `.git/hooks/pre-commit`; workflows and the AGENTS maintenance
  contract remain absent. This is a HIGH-confidence correctness finding and a
  likely future M-sized rollback plan, but it ranks behind Plan 062's default
  scan credential persistence because guard mutation is explicit opt-in and a
  safe rollback must preserve prior bytes, modes, absent paths, and user edits
  across repository and Git-common-dir boundaries.
- **Eval result metadata still has two artifact/integrity gaps** (2026-07-18
  round B) — verified separately, not folded into Plan 062. First, Plan 051
  redacts runner/judge text fields but `maybe_usage()` copies arbitrary string
  leaves under `usage`/`cost`/token metadata into persisted single/round/matrix
  records. Second, the stored-result validator accepts an explicit
  `passed: true` record even when its present runner or judge `exit_code` is
  non-zero; a current-evidence score gate can still report 100/A. Both are
  small, high-confidence follow-ups with compatibility constraints (historical
  manual records omit exit evidence), but the MCP leak affects ordinary scan
  output and has the smaller established redaction seam.
- **Generated eval provenance/runtime parity remains asymmetric** (2026-07-18
  round B) — verified in `eval_run.generate_tasks`: fact constructors pass
  `evidence`, but the shared `add()` publishes it only for scoped target tasks,
  leaving root-generated results unable to build automatic evidence manifests.
  Root Node inference also prefers `.nvmrc` over a conflicting
  `engines.node`, while scoped inference abstains. Keep these as a dedicated
  shared-facts/eval plan; do not mix their public task-shape and abstention
  changes into report redaction.
- **`actionlint` and local self-checkup parity are documented but not required**
  (2026-07-18 round B) — revalidated. `references/maintenance-contract.md`
  requires `actionlint`, yet neither `npm run check` nor required CI invokes it;
  `CONTRIBUTING.md` also runs scan/drift without the baseline fail flags and
  strict mode used by required CI. This is a high-confidence S-sized
  verification/DX follow-up. It does not outrank a current secret leak and
  needs a pinned, reproducible actionlint installation decision.
- **Formatter ownership is still unresolved after Plan 061** (2026-07-18 round
  B) — correctly rerun at `11e3a71` in a disposable worktree. `prettier --check
  .` reports 130 tracked files; `npm run format` rewrites 6,432/6,590 lines
  across 57 plans, 31 benchmark files, 10 GitHub files, 8 Node files, 6 assets,
  6 commands, one scan baseline, and 11 root files. It also changes AGENTS and
  task bytes without refreshing `results-after-graded.json`, so strict eval
  evidence exits 7 even though README/adapters/drift checks stay green. This is
  a real DX footgun, but the correct ownership policy (ignore historical
  evidence and single sources versus adopt one mass migration) remains a
  separate plan rather than a drive-by `.prettierignore`.
- **Published-version and release-process docs are not current operational
  truth** (2026-07-18 round B) — live read-back showed npm/GitHub latest at
  `v1.13.0`, while README pre-commit examples pin `v1.13.1`; the `v1.13.1`
  release run failed, no `v1.12.2` tag exists despite one validation-log claim,
  and `RELEASING.md`'s `npm version` + `git push --follow-tags` sequence
  conflicts with PR-only main governance/off-main tag rejection. Also,
  `SKILL.md`'s custom-rule example omits required `--allow-plugins`, Cursor
  `.md` support prose contradicts diagnostic-only registry semantics, and an
  obsolete v2 boundary describes already-shipped CLI gates as future work.
  These are verified S-sized documentation fixes, but should be handled as an
  operational-truth patch after the higher-impact credential leak.
- **Node 16/20 and Python 3.9 support lines are EOL** (2026-07-18 round B) —
  verified against official release schedules. Move maintenance workflows off
  Node 20 independently; raising public `engines.node` and Python minimums is a
  breaking compatibility/major-release decision and is not appropriate inside
  Plan 062.
- **Post-Plan-061 product directions** (2026-07-18 round B) — grounded options
  retained for future feature selection: one committed provider-neutral eval
  gate config that binds score to current evidence; provider-neutral Markdown
  findings output reusing `pr_review.collect_findings`; a strictly read-only MCP
  tool to verify existing eval results (never run paid agents/judges); and
  additive `schema_version` identities for scan/drift/validate public JSON.
  These are not bugfix substitutes and require public API/docs work.
