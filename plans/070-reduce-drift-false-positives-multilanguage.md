# Plan 070: Reduce path/command false positives on multi-language monorepos

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and honor every STOP condition. Update the plan index
> only when actual merge/check evidence exists.
>
> **Drift check**:
>
> ```bash
> git diff --stat e52d091..HEAD -- \
>   scripts/registry.py scripts/facts.py scripts/check_drift.py \
>   scripts/semantic.py tests/test_check_drift.py tests/test_semantic.py
> ```
>
> If `registry.declared_paths`, `facts.build_subtree_path_index`,
> `check_drift.d1_command_drift`/`d2_path_drift`/`d7_markdown_link_drift`, or
> `semantic.compare_paths`/`_MAKE_CMD_RE` changed semantically since `e52d091`,
> rerun the audit below before implementing.

## Status

- **Priority**: P1
- **Effort**: M–L
- **Risk**: MED (precision heuristics on the shared path/command classifiers;
  every rule must suppress only with positive evidence so real drift stays
  visible; no message shapes, flags, or exit semantics change)
- **Depends on**: none hard; extends the classifier doctrine accumulated by the
  branch-ref / npm-scope / placeholder / code-expr rules already in
  `registry.declared_paths`
- **Category**: correctness / false-positive reduction
- **Planned at**: commit `e52d091`, 2026-07-21

## Why this matters

A full checkup of a real ByteDance production monorepo (Go backend + Next.js/
Electron/Swift frontends, CJK-language AGENTS.md files, ~50 nested scopes)
scored **0/100 (F)** with 135 drift findings (D1×20, D2×106, D7×9). Manual
triage classified **~92 of them as false positives** across eight root-cause
classes, all reproducible locally at `e52d091`. The F grade is noise, not
signal — and a first-run experience like that kills adoption of the drift gate
(the user's takeaway was "the tool assumes JS/Node single-language repos").

The eight classes, with their mechanics:

| Class | Count | Root cause |
|---|---:|---|
| A. Branch-name examples (`feat/agent_memory`) | 3 (D2) | branch cue words live on a previous line / are CJK (`分支`), and the example cue (`示例：`) is not recognized |
| B. Go/npm import paths (`net/http`, `uber/fx`, `Shopify/sarama`) | 11 (D2) | import paths are not repo files; no go.mod/package.json awareness |
| C. Code symbols (`core/agent.Agent`, `service.Service.MustGet…`, `remote/RemoteBus`) | 36 (D2) | `pkg/path.Type[.Method]` and exported CamelCase identifiers read as paths |
| D. Value enums (`low/medium/high`, `linux/amd64`, `.ts/.tsx`, `GetTools/Compose/Run`) | 12 (D2) | `/`-separated value lists read as multi-segment paths |
| E. `make -C <dir> <target>` | 14 (D1) | `-C` captured as the target; the real target in the `-C` directory's Makefile is never checked |
| E′. `make ep-local-*` glob | 1 (D1) | the regex truncates at `*`, reporting the prefix as a missing target |
| F. Cross-subtree refs that exist (`cmd/enterprise`, `agents/iris`) | 6 (D2) | nested scopes deliberately bound their suffix index to their own subtree |
| G. Markdown "links" inside code (`[MyStore](run, store)`, `[T](ctx, c)`) | 7 (D7) | D7 scans raw lines, including fenced blocks and inline code spans |
| H. Repo-name-prefixed paths (`kiwis/backend/…`) | 2 (D2) | one extra leading segment (the repo's own name) defeats resolution |

The classifier already embodies the correct doctrine for this: accumulate
narrow, positively-evidenced suppression rules (branch refs, npm scopes,
`<word>-name` placeholders, code-expression characters, linter rule ids,
runtime ids — each carries its found-in-the-wild provenance comment). This plan
extends the same doctrine to Go/multi-language monorepos and CJK documentation.

## Current state (verified at `e52d091`)

- `registry.declared_paths` (registry.py:482) is the single shared D2/Phase-0
  candidacy classifier (TD-03); text-only rules belong there.
- Repo-context suppressions (workspace package names, eslint rule ids, subtree
  suffix index) live caller-side, duplicated in `check_drift.d2_path_drift`
  (check_drift.py:186) and `semantic.compare_paths` (semantic.py:853) with
  mirror comments.
- `check_drift.d1_command_drift` uses `make\s+([A-Za-z0-9_.-]+)` — `-C`
  matches the class; `semantic._MAKE_CMD_RE` (semantic.py:169) has the
  identical bug. `facts.make_targets` reads one directory's Makefile.
- `facts.SubtreePathIndex` (facts.py:~525) records suffix *presence* only, no
  ambiguity information; nested scopes bound it to the scope root by design
  ("must never search sibling packages").
- `d7_markdown_link_drift` (check_drift.py:507) iterates raw
  `text.splitlines()` with no fence or inline-code-span awareness;
  `_link_target_is_probeable` accepts `run,`-shaped targets.
- Baseline fingerprints are `(check, message, path)` — suppressing a finding
  turns its baseline entry into prunable resolved debt; nothing crashes.
- Local reproduction on the audited monorepo: 135 findings (D1 20, D2 106,
  D7 9). Every `make -C` target named in its AGENTS.md exists in the `-C`
  directory's Makefile; all six class-F targets exist in the repo; class-B
  imports all appear in `backend/go.mod` (with `go.uber.org/fx` needing the
  vanity-domain rule below).

## Target contract

1. **Shared make-invocation parser** (new in facts.py, consumed by both
   `d1_command_drift` and semantic's command extraction — TD-02):
   - Tokenizes the code span after `make` on whitespace; skips `VAR=value`
     assignments and option flags; `-C DIR` (and `-f FILE`, `-I`, `-o`, `-W`,
     `-j N`) consume their argument; the first remaining bare word is the
     target (first-target-only, matching historical behavior).
   - A target containing a glob (`*`) is never validated (abstain).
   - With `-C DIR`: resolve DIR against each fact-chain directory under the
     existing containment primitives; if a Makefile is found there, validate
     the target against *that* Makefile (true-positive power retained: a typo
     in a `-C` invocation is still caught); if no Makefile resolves, abstain.
   - Without `-C`: behavior and message byte-identical to today.
2. **D7 becomes code-aware**: fenced-block lines are skipped (same fence
   tracking contract as `facts.iter_code_tokens`); a link match whose opening
   `[` sits inside an inline backtick code span is skipped; a genuine link
   whose *label* contains backticks (`` [`docs/x.md`](../docs/x.md) ``) is
   still probed — pinned by test. `_link_target_is_probeable` additionally
   rejects targets containing `,` (belt-and-suspenders; no real repo path
   contains one).
3. **Text-only candidacy rules** added to `registry.declared_paths`, each with
   a provenance comment and a false-negative guard:
   - *Dotted code symbol*: final `.`-component starts with an uppercase letter
     and contains a lowercase letter (`.Agent`, `.RDSConfig`,
     `.Service.MustGetAgentRunEvents`) → symbol, not a path. Uppercase-start
     *file extensions* stay paths via a small denylist (`Dockerfile`); all-caps
     components (`.MD`, `.SQL`) stay paths.
   - *Extension enum*: every segment matches `^\.\w+$` (`.ts/.tsx`).
   - *Numeric enum*: every segment matches `^\d+[A-Za-z]{0,3}$` (`1k/2k/4k`).
   - *Platform pair*: token is a known GOOS/GOARCH combination
     (`linux/amd64`, `linux/arm64`, `darwin/arm64`, …) from a fixed set.
   - *Identifier enum*: ≥2 extensionless identifier segments where at least one
     segment has an *internal* uppercase letter (`errorType/reason/botType`,
     `GetTools/Compose/Run`, `defaultAssistantSubagentMaxSteps/MaxFailures`,
     `Host/Port/User/Password/DBName/Params`) **or** exactly two
     uppercase-start segments where one is a substring of the other
     (`Register/Unregister`). Plain `Sources/App` / `src/Components` shapes
     remain path candidates — pinned by tests.
   - *Value-word enum*: every segment in a small curated lexicon
     (`low/medium/high`, `true/false`, `yes/no`, `on/off`) — lexicon kept
     deliberately tiny to avoid eating real directory names.
   - *Branch example cues*: `_BRANCH_CONTEXT_RE` gains CJK branch words
     (`分支`, `检出`); an example cue (`示例`, `例如`, `e.g.`, `example`) now
     counts as the weak second signal **only** when the token already carries a
     conventional branch-type prefix. The filesystem-cue override keeps
     winning.
4. **Repo-context suppressions** implemented once in facts.py and consumed by
   BOTH `d2_path_drift` and `semantic.compare_paths` (one shared predicate;
   the callers stay mirrors — TD-02/TD-03):
   - *Go import awareness*: parse `go.mod` files at fact-chain directories
     (bounded reads, containment-checked). Build a suffix set from `module` /
     `require` paths: all ≥2-segment suffixes of the path part after the host,
     plus the host's second-level-domain prepended (`go.uber.org/fx` →
     `uber/fx`). A token matching a suffix, or whose ≥2-segment prefix matches
     a suffix (subpackages: `sourcegraph/conc/pool`), is an import path, not a
     repo path. Missing/unparsable go.mod ⇒ rule inert.
   - *Go stdlib*: in a scope whose fact chain has a `go.mod`, an all-lowercase
     extensionless multi-segment token whose first segment is a known stdlib
     top-level package (`net/http`, `encoding/json`; fixed frozenset) is an
     import path.
   - *Go exported symbol*: in a go.mod scope, a dotless token whose final
     segment is `[A-Z]…` CamelCase containing a lowercase letter
     (`remote/RemoteBus`) is a symbol. Inert without go.mod in the chain —
     `components/Button` in a JS repo stays a path candidate (pinned).
   - *npm dependency imports*: union of `dependencies`/`devDependencies`/
     `peerDependencies`/`optionalDependencies` names from the fact-chain
     directories' own `package.json` files (no walk); a token whose first
     segment is a dependency name (`next/link`, `nanostores/plugin-ui.ts`) is
     a module subpath import.
   - *Repo-name prefix*: first segment equals the containment root's directory
     name AND the remainder exists under the containment root
     (`kiwis/backend/…/runtime_general.dockerfile`) → suppressed; if the
     remainder is missing the finding stays (original token, original message).
5. **Unique repo-wide suffix fallback for nested scopes**:
   `SubtreePathIndex` additionally records which suffixes are ambiguous
   (multiple sources). The repository-root index is built at most once per
   engine run (cached; today every nested scope with a miss already builds its
   own bounded index, so this is not a new walk class). A nested-scope missing
   token that resolves **uniquely** at repository level is suppressed
   (`cmd/enterprise` → the one `backend/agentsphere/cmd/enterprise`);
   ambiguous suffixes (`dal/po` exists in many modules) remain findings, so
   the historical "never search sibling packages" false-negative guard is
   preserved in the case it was built for. Root-scope behavior is unchanged.
6. **No surface changes**: no new flags, no message-shape changes, no exit
   semantic changes, no SARIF/baseline/schema changes. Suppressed findings
   simply disappear; their baseline entries become prunable resolved debt.
7. Python 3.9 stdlib only; ruff (E/F/I, py39) clean; deterministic; all reads
   through the existing containment primitives; no new repository walks beyond
   the cached root index in (5).
8. **Acceptance on the audited monorepo** (local evidence, not CI): total
   findings drop 135 → ≈43; the ~15 human-confirmed real/needs-confirmation
   issues (missing Swift test files, dead doc link `aime-plugin-dynamic-ui.md`,
   `app/api/kani.ts`, `make dev_local`/`all_local`, `pnpm starling`, …) ALL
   remain reported. CI reproduces every class with synthetic fixtures.

## Scope

**In scope**:

- `scripts/facts.py`: make-invocation parser; go.mod import-suffix reader;
  stdlib set; npm-dependency chain helper; shared non-path predicate;
  `SubtreePathIndex` ambiguity + cached root index; repo-name prefix helper.
- `scripts/registry.py`: `declared_paths` text-only rules; branch/example cue
  extensions.
- `scripts/check_drift.py`: d1 rewired through the shared make parser (with
  `-C` Makefile resolution); d2 wired to the shared predicate + unique-suffix
  fallback; d7 fence/inline-span awareness + target rejection.
- `scripts/semantic.py`: command extraction and `compare_paths` wired through
  the same shared helpers (mirror parity maintained).
- `tests/test_check_drift.py`, `tests/test_semantic.py`: one test (or small
  group) per class per engine, positive and negative.
- Plan/index closeout evidence.

**Out of scope**:

- New flags, output shapes, or exit codes; README/SKILL structural changes
  (internal precision work only — SKILL.md gains at most one sentence if any).
- A user-facing ignore/allowlist mechanism (the plugin system already exists).
- Multi-target `make a b c` parsing; cwd-convention resolution for prose like
  "在 `X/` 目录下执行 `make t`" (the `-C` fact-chain rule covers the observed
  FP class; cwd prose stays needs-confirmation).
- Exhaustive CJK cue coverage beyond the observed classes.
- Language ecosystems not observed in the audit (Rust `use` paths, JVM
  packages) — the doctrine extends naturally later.
- Releasing (lands as `fix`; version bump follows RELEASING.md).

## Commands

| Purpose | Command | Expected |
|---|---|---|
| Focused drift tests | `PYTHONPATH=tests python3 -m unittest test_check_drift -v` | pass |
| Focused semantic tests | `PYTHONPATH=tests python3 -m unittest test_semantic -v` | pass |
| Full gate | `npm run check` with CI-supported npm | pass |
| Self drift | `python3 scripts/check_drift.py . --strict` | 100/A |
| Self scan | gated baseline scan command from `AGENTS.md` | exit 0 |
| Adapters | `python3 scripts/gen_adapters.py --check` | unchanged |
| Monorepo evidence | drift+scan on the audited repo, diff vs saved baseline | ≈43 findings; all real issues retained |

## Git workflow

- Plan-only PR first.
- Implementation branch: `fix/070-drift-false-positives`.
- Commit: `fix(drift): reduce path/command false positives on multi-language monorepos`.
- No default-behavior surface changes beyond finding reduction.
- Merge only after all nine required contexts and zero unresolved threads;
  squash and delete branch.
- Separate green closeout PR afterward.

## Steps

### Step 1: Red fixtures for every class

Synthetic per-class fixtures in tests (Go monorepo with go.mod + nested
AGENTS.md; CJK branch-example doc; fenced/inline-code D7 doc; `make -C`
Makefiles; repo-name-prefixed refs; ambiguous vs unique suffixes). Assert the
current engines emit each false positive (red), and that the designated
true-positive twins are found.

### Step 2: Shared make parser + D1/semantic rewire

facts.py parser per contract (1); d1 and semantic consume it; plain-make
messages byte-identical (existing tests untouched); `-C` resolution +
glob/no-Makefile abstention; TP case: bad target in a `-C` Makefile still
flagged from both engines.

### Step 3: D7 code awareness

Fence tracking + inline-span start-position guard + `,` rejection per
contract (2); the backticked-label real-link pin.

### Step 4: Text-only classifier rules

Contract (3) in `registry.declared_paths` with per-rule provenance comments
and FN-guard tests (`Sources/App`, `src/Components`, `docs/README.MD`,
`server.Dockerfile` stay candidates).

### Step 5: Repo-context predicate + unique-suffix fallback

Contract (4)+(5) in facts.py; wire `d2_path_drift` and `semantic.compare_paths`
identically; ambiguity-aware index with cached root build; parity asserted by
running both engines over the same fixtures.

### Step 6: Monorepo evidence, gates, review, PR, closeout

Re-run the audited monorepo checkup; record before/after counts and the
retained-real-issues list in the plan. Full gates; adversarial review with
attention to FN risk (does any rule mask the drift it exists to catch?);
implementation PR → nine green checks → squash-merge → closeout PR.

## Test plan

- **E**: `make -C sub target` with target present → no finding; with target
  absent from `sub/Makefile` → D1 finding (both engines); `-C` dir without
  Makefile → abstain; `make ep-local-*` → abstain; plain `make build` behavior
  unchanged; `make sure the tests pass` prose guard still holds.
- **G**: link inside fenced block → skipped; `` `f[T](ctx, c)` `` inline →
  skipped; `` [`docs/x.md`](../missing.md) `` → still flagged; plain broken
  link → still flagged; `(run,)` target → rejected.
- **A**: `- 示例：\`feat/agent_memory\`` → suppressed; `- 示例：\`docs/setup\``
  (no branch prefix) → kept; English `Examples: \`feat/x\`` → suppressed;
  filesystem cue on the line → kept.
- **B**: go.mod require suffixes (plain, `/vN`, vanity `go.uber.org/fx`,
  subpackage `sourcegraph/conc/pool`), stdlib `net/http` with go.mod present;
  same tokens WITHOUT go.mod → still flagged; npm dep `next/link` with
  dependency present → suppressed, absent → flagged.
- **C**: dotted-symbol suppression is text-only-global; `.swift`/`.MD`/
  `.Dockerfile` final components stay flagged; `remote/RemoteBus` suppressed
  only in go.mod scopes; `components/Button` flagged in a JS repo.
- **D**: each enum shape suppressed; `Sources/App`, `pages/Home` kept;
  `domain/intent/sub_intent` (lowercase, no internal uppercase) kept.
- **F**: unique repo-wide suffix from a nested scope → suppressed; the same
  suffix existing in two sibling packages → kept; root scope unchanged.
- **H**: `<rootname>/existing/path` → suppressed; `<rootname>/missing/path` →
  kept; a first segment merely resembling the root name → kept.
- **Parity**: identical fixture results from `d2_path_drift` and
  `semantic.compare_paths` for every class.
- **Baseline**: a baseline containing a now-suppressed fingerprint reports it
  as resolved debt and `--prune-baseline` removes it.
- Ruff/py39 compliance via the lint gate.

## Done criteria

- [ ] Every class A–H has a passing suppression test and a passing
      FN-guard twin in both engines where applicable.
- [ ] Plain-make D1, root-scope D2, and all untouched-check outputs are
      byte-identical on existing fixtures (full suite green untouched).
- [ ] Monorepo evidence recorded: 135 → ≈43 with zero real-issue loss.
- [ ] Full gates, self drift 100/A, self scan exit 0, adapters unchanged.
- [ ] Implementation and closeout PRs each pass nine checks, merge, delete
      branches.

## STOP conditions

Stop if:

- Any rule requires network access, YAML/AST parsing of foreign languages, or
  non-deterministic input to decide a suppression.
- A suppression cannot be expressed with positive evidence (i.e. it would rely
  on "token merely looks unusual").
- The shared predicate cannot keep `d2_path_drift` and
  `semantic.compare_paths` in verified parity.
- Monorepo evidence shows any human-confirmed real issue disappearing.
- Plain-make/root-scope behavior cannot stay byte-identical.
- The repository's own gated self-checkup or strict drift regresses.

## Maintenance notes

- Future candidates deliberately excluded: Rust/JVM import awareness; a
  `--strict-paths` mode disabling the new suppressions; cwd-prose (`在 X 目录
  下执行`) command resolution; multi-target make parsing.
- The GOOS/GOARCH set, stdlib set, and value-word lexicon are fixed frozensets
  with provenance comments — extend only with observed-in-the-wild evidence,
  never speculatively.
- Any new suppression rule added later must follow the same shape: positive
  evidence, provenance comment, FN-guard twin test in both engines.
