# Plan 035: Model deterministic Cursor and Copilot rule applicability

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 777f962..HEAD -- assets/agent-tools.json scripts/registry.py scripts/scan.py scripts/scan_render.py scripts/explain.py scripts/canonicalize.py scripts/sarif.py scripts/pr_review.py tests/test_scan.py tests/test_explain.py tests/test_canonicalize.py tests/test_registry_consistency.py tests/test_sarif.py tests/test_pr_review.py README.md README.zh-CN.md README.ja.md SKILL.md EXTERNAL_VALIDATION.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: L
- **Risk**: HIGH
- **Depends on**: none
- **Category**: direction / correctness / product / DX / tests / docs
- **Planned at**: commit `777f962`, 2026-07-16

## Why this matters

AI Harness Doctor inventories modern Cursor and GitHub Copilot rule files but
treats every rule body as globally active inside its nearest lexical
`AGENTS.md` scope. Both products have structured applicability: Cursor `.mdc`
uses `alwaysApply`, `globs`, and `description`; Copilot/VS Code
`.instructions.md` uses `applyTo`. Legitimate disjoint frontend/backend rules
therefore become blocking package-manager/test/style conflicts, while ignored
plain `.cursor/rules/*.md` files are analyzed as if Cursor loaded them.

This is no longer an isolated prose heuristic. Current `microsoft/vscode`
contains 23 top-level `.instructions.md` files and current `github/docs`
contains five; official VS Code documentation also supports recursive
subdirectories. Cursor's official rule contract says plain `.md` is ignored,
and distinguishes always, path-attached, agent-selected, and manual rules.
Modeling the deterministic part of these applicability languages removes a
high-impact false-positive class and lets `explain REPO TARGET` answer which
structured rules actually match, without pretending to understand semantic
description selection or arbitrary natural-language scope.

## Current state

- `assets/agent-tools.json:18-24` and `:35-42` recognize only one directory
  level and encode no applicability semantics:

  ```json
  {
    "id": "cursor",
    "scan_patterns": [
      ".cursorrules",
      ".cursor/rules/*.mdc",
      ".cursor/rules/*.md"
    ]
  },
  {
    "id": "copilot",
    "scan_patterns": [
      ".github/copilot-instructions.md",
      ".github/instructions/*.instructions.md"
    ]
  }
  ```

  VS Code recursively searches `.github/instructions/`; Cursor documents
  nested folders under `.cursor/rules/`.

- `scan.file_info()` at `scripts/scan.py:571-662` retains a bounded semantic
  text prefix but has no internal tool ID, parsed frontmatter, or applicability
  metadata.

- `instruction_scope_map()` at `scripts/scan.py:964-1000` assigns every
  recognized config to the deepest canonical directory scope. Then
  `analyze_scoped_conflicts()` at `:1029-1094` groups every extracted signal by
  that scope:

  ```python
  for f in files:
      seen = {}
      for sig in extract_signals(f):
          seen[(sig["signal"], _conflict_key(...))] = sig
      scope = file_scopes.get(f["path"], ".")
      for (signal, key), sig in seen.items():
          by_scope.setdefault(scope, {}).setdefault(signal, {}) \
              .setdefault(key, []).append(sig)
  ```

  No target path or rule glob participates.

- `scripts/explain.py:14-18` states the limitation explicitly:

  ```python
  DIAGNOSTIC_LIMITATION = (
      "Tool-specific configs are diagnostically associated with lexical scopes; "
      "their own glob, frontmatter, and prose applicability is not inferred."
  )
  ```

  `_diagnostic_sources()` lists every recognized source on the canonical chain,
  regardless of whether it matches the target.

- A deterministic Copilot fixture with two files:

  ```yaml
  # .github/instructions/javascript.instructions.md
  ---
  applyTo: "src/**/*.js"
  ---
  Use `npm test`.
  ```

  ```yaml
  # .github/instructions/python.instructions.md
  ---
  applyTo: "scripts/**/*.py"
  ---
  Use `uv run pytest`.
  ```

  is reported as same-scope `npm`↔`uv` and
  `npm test`↔`pytest` conflicts even though the automatic domains are disjoint.
  The same false conflict reproduces with two Cursor `.mdc` rules using
  disjoint `globs`.

- A second audit fixture with root `AGENTS.md` plus one path-specific rule also
  shows the current global grouping. That fixture alone is ambiguous because
  canonical root instructions really do inherit into the target; it must not be
  used to suppress root-versus-scoped contradictions by fiat. The selected
  contract only suppresses conflicts when deterministic applicability domains
  are provably disjoint.

- Real read-only scans at the audit date:
  - `github/docs@8c0d1d6747ef40ee00588b87f7f78a7063f835f4`
    inventoried five `.instructions.md` files;
  - `microsoft/vscode@e6549ec3e40aee3e1877dd8b8c4d632574cb71be`
    inventoried 23 top-level `.instructions.md` files plus canonical scopes.
  Both worktrees stayed clean. Their rule bodies demonstrate real `applyTo`
  usage; not every existing conflict is an applicability false positive, so
  validation must preserve same-file/same-domain findings.

- Cursor's current official contract:
  - project rules use `.mdc`; plain `.md` under `.cursor/rules` is ignored;
  - `alwaysApply: true` means always active;
  - `alwaysApply: false` + `globs` means path-attached;
  - description without globs is agent-selected;
  - neither description nor globs is manual;
  - multiple glob patterns are comma-separated.

- VS Code's current official contract:
  - `.instructions.md` has optional YAML frontmatter;
  - `applyTo` is a workspace-relative glob and `**` means all files;
  - without `applyTo`, the file is not automatically attached (manual/semantic
    selection remains possible);
  - `.github/instructions/` is searched recursively.

- This project is Python 3.9 stdlib-only. It cannot add PyYAML or a general YAML
  parser. Applicability parsing must be a deliberately small, fail-closed
  frontmatter subset.

- `canonicalize.collect_stub_targets()` has bespoke top-level Cursor rule
  deletion at `scripts/canonicalize.py:608-625`. Expanding scanner discovery
  must not silently expand destructive deletion to nested rule trees. Treat
  mutation remains human-confirmed and is not the place to invent recursive
  cleanup in this feature.

## Target contract

1. Keep `assets/agent-tools.json` as the single source of recognized paths and
   add explicit applicability metadata only for the formats modeled here:
   - Cursor project `.mdc`;
   - Copilot/VS Code `.instructions.md`.
   Other tools retain current lexical behavior.
2. Discover structured rules recursively:
   - `.cursor/rules/**/*.mdc`;
   - `.github/instructions/**/*.instructions.md`.
   Keep `.cursor/rules/**/*.md` as a diagnostic candidate so the doctor can
   explain that Cursor ignores the wrong extension; do not treat its body as
   effective conflict evidence.
3. Parse only frontmatter at the start of the retained semantic text. Support
   documented scalar forms needed by the two formats:
   - quoted/unquoted strings;
   - `true` / `false`;
   - comma-separated glob strings.
   Preserve body line numbers by replacing frontmatter lines with blank lines
   before signal extraction.
4. Never implement general YAML. Anchors, aliases, tags, multiline scalars,
   nested objects/lists, duplicate control keys, unterminated frontmatter, or a
   frontmatter block truncated by `--max-bytes` are unsupported and become an
   explicit applicability warning. Their bodies remain security/overlap
   evidence but do not enter blocking conflicts.
5. Normalize each recognized source into one deterministic internal/public
   applicability record:
   - `always`: applies to every target in the source's canonical lexical scope;
   - `path`: automatic, with normalized repository-relative glob patterns;
   - `conditional`: description/semantic selection exists but cannot be decided
     from a path alone;
   - `manual`: not automatically attached;
   - `ignored`: e.g. Cursor `.md` wrong extension;
   - `invalid`: malformed/unsupported applicability metadata.
6. Validate patterns conservatively: non-empty relative POSIX globs only; reject
   absolute paths, `..` traversal, NUL/newlines, and unsupported syntax. Matching
   is read-only and component-aware. Reuse one shared wildcard matcher rather
   than forking scanner-glob semantics.
7. Blocking scan conflicts use automatic applicability domains:
   - canonical and `always` sources cover their lexical subtree;
   - `path` sources cover contained current repository paths matching at least
     one pattern and their lexical scope;
   - `conditional`, `manual`, `ignored`, and `invalid` sources do not enter
     `--fail-on-conflicts`;
   - different normalized values conflict only when their automatic domains
     intersect.
   Do not attempt symbolic glob algebra. Concrete current-path intersection is
   the evidence boundary; future unmatched paths are not claimed clean.
8. Preserve existing behavior for source records without applicability metadata
   (including direct unit-test fixtures): they remain lexical/always. Preserve
   historical root conflict shape and exit `7` for true overlapping conflicts.
9. `scan --json` adds deterministic applicability records and warnings.
   Markdown explains each structured source's mode/patterns and states when no
   current path matched. Applicability warnings are non-blocking unless they
   also produce a true existing finding; no new fail-on exit code is introduced.
10. Applicability warnings traverse SARIF and PR review with safe path/line
    attribution and remediation. They must not be silently omitted merely
    because they do not affect `--fail-on-conflicts`.
11. `explain REPO TARGET` matches the explicit target directly, including
    future contained paths. Keep `diagnostic_sources` for schema compatibility,
    add/annotate deterministic applicability, and separate:
    - automatically applicable sources (`always` or matching `path`);
    - non-matching path sources;
    - conditional/manual/ignored/invalid sources.
    Never claim that description-based semantic selection is effective.
12. Target-specific conflicts are derived from canonical chain plus the
    automatically applicable structured sources for that target. A disjoint
    rule must not appear in the target's relevant conflict set.
13. Security scanning and full-file identity remain independent of
    applicability. Secrets and risky commands in manual, ignored, invalid, or
    non-matching rule files are still scanned exactly as today.
14. Overlap evidence remains inventory evidence across all recognized
    candidates. Treat plan suggestions may use the corrected conflict set but
    must not auto-merge, auto-adjudicate, or recursively delete structured rule
    trees.
15. `stubs --apply` retains its current explicit mutation scope. Do not turn
    recursive discovery into recursive deletion; add a regression proving
    nested rules are not deleted without a separately reviewed mutation plan.
16. Automatic all-scope eval, a generic ignore/config language, prose/file-type
    inference, and other vendors' applicability languages remain deferred.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Scan tests | `python3 -m unittest discover -s tests -p 'test_scan.py' -v` | all pass |
| Explain tests | `python3 -m unittest discover -s tests -p 'test_explain.py' -v` | all pass |
| Registry consistency | `python3 -m unittest discover -s tests -p 'test_registry_consistency.py' -v` | all pass |
| Canonicalize safety | `python3 -m unittest discover -s tests -p 'test_canonicalize.py' -v` | all pass |
| SARIF tests | `python3 -m unittest discover -s tests -p 'test_sarif.py' -v` | all pass |
| PR-review tests | `python3 -m unittest discover -s tests -p 'test_pr_review.py' -v` | all pass |
| Python lint | `ruff check scripts tests` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | `OK` |
| Full gate | `npm run check` | exit 0 |
| Self eval | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0, grade A |
| Self scan | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0, grade A |

## Scope

**In scope**:

- `assets/agent-tools.json`
- `scripts/registry.py`
- one new stdlib-only applicability helper under `scripts/` if that is cleaner
  than placing the parser in `scan.py`
- `scripts/scan.py`
- `scripts/scan_render.py`
- `scripts/explain.py`
- `scripts/sarif.py`
- `scripts/pr_review.py`
- `scripts/canonicalize.py` only for mutation-scope regression/guarding; no
  recursive delete feature
- `tests/test_scan.py`
- `tests/test_explain.py`
- `tests/test_registry_consistency.py`
- `tests/test_canonicalize.py`
- `tests/test_sarif.py`
- `tests/test_pr_review.py`
- synchronized `README.md`, `README.zh-CN.md`, `README.ja.md`
- `SKILL.md`
- `EXTERNAL_VALIDATION.md`
- `plans/README.md`

**Out of scope**:

- General YAML parsing or a PyYAML dependency.
- Semantic matching of Cursor/Copilot descriptions.
- Natural-language scopes such as “tabs for code, spaces for JSON.”
- Symbolic proof of arbitrary glob intersection.
- Claude `.claude/rules` `paths`, Windsurf/Roo/Cline applicability, IDE settings,
  ignore files, or user-global rules.
- Automatic all-scope eval generation.
- A first-class user ignore/config language.
- Auto-merging or choosing one conflict value.
- Recursive deletion/rewriting of nested rule directories.
- Changing canonical `AGENTS.md` nearest-file semantics.
- Broad Ruler/rulesync-style distribution.
- Updating `AGENTS.md`; the batch completion PR owns final durable invariants.

## Git workflow

- Branch: `feat/structured-rule-applicability`
- Commit: `feat(scan): model structured rule applicability`
- One themed backward-compatible feature/correctness PR with tests, trilingual
  docs, and real external validation.
- Do not push directly to `main`.
- Wait for all nine required contexts, then squash-merge and delete the branch.
- Feature-level under repository policy, so the combined batch release is at
  least minor unless a STOP condition exposes a breaking schema requirement.

## Steps

### Step 1: Lock the false-positive and discovery behavior in tests

Build table-driven fixtures for:

- two disjoint Copilot `applyTo` rules with conflicting signals → no blocking
  conflict;
- overlapping Copilot patterns → conflict retained;
- two disjoint Cursor `globs` rules → no conflict;
- Cursor `alwaysApply: true` against a matching path rule → overlap/conflict;
- conditional/manual Cursor rules → inventory but no blocking conflict;
- plain Cursor `.md` → ignored applicability warning, no signal conflict;
- nested Cursor/Copilot directories → discovered recursively;
- existing root/nested canonical conflicts → unchanged;
- source objects without applicability metadata → legacy behavior unchanged.

Add target-explain cases showing frontend/backend targets receive different
automatic sources and conflict sets.

**Verify**: disjoint and recursive cases fail against `777f962`.

### Step 2: Extend the registry without creating another tool list

Add registry applicability metadata and recursive patterns for only Cursor and
Copilot. Extend `tests/test_registry_consistency.py` so every declared
applicability kind has one known parser and the scan still derives paths from
the registry.

Carry an internal tool ID from match discovery into file analysis without
changing the existing public `tool` label. Do not hard-code path checks in
multiple engines.

**Verify**: registry tests prove recursive patterns and parser-kind ownership
are single-sourced.

### Step 3: Implement a bounded, fail-closed frontmatter parser

Create a pure parser for the documented scalar subset. It must:

- accept CRLF/LF, quoted/unquoted scalar strings, and booleans;
- split comma-separated globs after scalar decoding;
- reject duplicate control keys and unsupported YAML constructs;
- preserve original body line numbers with blank frontmatter placeholders;
- distinguish missing metadata from malformed/truncated metadata;
- sanitize diagnostics to field/path/line only.

Use no external packages and never interpret tags, anchors, aliases, or object
construction.

**Verify**: pure tests cover valid modes, malformed syntax, traversal/absolute
patterns, duplicate keys, CRLF, BOM policy, and truncated frontmatter.

### Step 4: Compute deterministic applicability domains once per scan

Attach normalized applicability to each internal file record and expose a safe
public projection. Use the existing contained file index to calculate current
matches for `path` rules. Respect canonical lexical scope boundaries as well as
the rule's repository-relative patterns.

Keep security over the original complete file. Feed a line-preserving body view
to signal extraction so frontmatter does not become prose evidence.

Represent no-current-match honestly; do not equate it with an invalid rule or a
proof about future files.

**Verify**: repeated scan JSON is deterministic, paths stay repository-relative,
and no extra tree walk is introduced.

### Step 5: Make conflict analysis intersect automatic domains

Refactor `analyze_scoped_conflicts()` around signal entries that carry a
deterministic domain. A conflict requires at least two normalized values and a
non-empty shared automatic domain. Keep formatter and Node-version
normalization exemptions.

For legacy callers without a scan index/applicability record, preserve current
lexical behavior. Do not suppress a canonical-global versus path rule merely
because nearby prose names a language; if both automatic domains overlap, the
conflict is real under the deterministic model.

Include concise applicability evidence on newly scoped conflict records only
when additive metadata is necessary; preserve root shape where possible.

**Verify**: disjoint false positives disappear, overlapping/root/nested true
conflicts and exit `7` remain, baselines remain deterministic, and Treat uses
the corrected report.

### Step 6: Upgrade target explain without overstating semantic selection

For one target path, classify every diagnostic source on the canonical chain:

- automatic and matching;
- automatic but non-matching;
- conditional/manual;
- ignored/invalid.

Add deterministic fields while retaining existing
`diagnostic_sources`, `canonical_chain`, `effective_scope`, and schema version
compatibility. Derive target conflicts from the canonical chain plus matching
automatic sources, not from the repository-wide conflict list alone.

Update limitation text to say Cursor/Copilot path metadata is modeled, while
description/prose/other-tool applicability remains diagnostic only.

**Verify**: existing/future target paths work; sibling/disjoint rules are absent
from relevant conflicts; conditional rules are visible but never labeled
effective.

### Step 7: Deliver applicability diagnostics everywhere

Render a Markdown applicability section with mode, patterns, match count, and
safe warnings. Extend SARIF and PR review so ignored/invalid structured rules
produce actionable path-attributed warnings. Preserve:

- non-blocking status;
- monorepo package path prefixes;
- batch summary-only safety;
- no baselined debt reposting;
- deterministic rule IDs/messages.

Do not convert non-matching valid rules into errors. If a NOTICE is emitted for
zero current matches, explain that future paths may still match.

**Verify**: JSON/Markdown/SARIF/PR-review fixtures carry the same warnings and
paths; no new absolute-path or frontmatter-content leak appears.

### Step 8: Protect Treat mutation boundaries

Add a canonicalize regression with nested Cursor rule directories. Preview and
apply behavior must not recursively delete or rewrite newly discovered rules.
Existing explicitly supported top-level Cursor consolidation stays unchanged.

If product requirements demand recursive cleanup to complete Treat, stop and
write a separate mutation plan with ownership/rollback semantics rather than
expanding this PR.

**Verify**: canonicalize tests prove nested rule bytes survive both dry-run and
apply unless they were already in the historical explicit mutation set.

### Step 9: Document the evidence boundary and validate real repositories

Update all three READMEs and `SKILL.md`:

- which Cursor/Copilot fields and modes are deterministic;
- how scan conflict domains and target explain use them;
- unsupported YAML/semantic-description behavior;
- security/overlap coverage independence;
- recursive discovery and ignored `.md` diagnosis;
- no symbolic glob or prose inference.

Run the dev checkout read-only against:

1. `github/docs` at a recorded current commit:
   - inventory all recursive `.instructions.md`;
   - explain one `content/**` target and one `src/**` target;
   - verify their automatically applicable source sets differ;
   - retain any real same-domain/same-file conflicts.
2. `microsoft/vscode` at a recorded current commit:
   - inventory its structured rules;
   - explain a `build/next/**` target and an unrelated target;
   - verify `buildNext.instructions.md` matches only the first.

Record commit, rule counts/modes, target results, remaining conflicts,
limitations, and clean worktree hashes in `EXTERNAL_VALIDATION.md`. Do not call
every old conflict a fix; distinguish structured-scope changes from unrelated
signal-extraction false positives.

**Verify**: docs sync, all focused/full tests, real validation, self-eval, self
scan, and strict drift.

## Test plan

- Cursor/Copilot frontmatter scalar parser tables.
- Recursive registry discovery.
- Always/path/conditional/manual/ignored/invalid classification.
- Glob containment and concrete-domain intersection.
- Disjoint false-positive and overlapping true-conflict regressions.
- Legacy/root/nested conflict compatibility.
- Target explain matching/non-matching/future paths.
- Full security scanning independent of applicability.
- JSON/Markdown/SARIF/PR-review parity and path safety.
- Oversize/truncated frontmatter honesty.
- Canonicalize nested-rule no-delete boundary.
- Real `github/docs` and `microsoft/vscode` read-only validation.

## Done criteria

- [ ] Disjoint Cursor/Copilot automatic rules no longer create blocking
      conflicts.
- [ ] Overlapping automatic rules and canonical conflicts remain visible and
      gateable.
- [ ] Recursive structured rule directories are inventoried.
- [ ] Cursor plain `.md` is diagnosed as ignored and contributes no effective
      conflict signals.
- [ ] Unsupported/malformed/truncated metadata fails closed without a traceback.
- [ ] Explain distinguishes matching, non-matching, conditional/manual, and
      ignored/invalid sources for existing and future targets.
- [ ] Security and identity still cover every recognized file byte.
- [ ] Applicability warnings reach Markdown, SARIF, and PR review.
- [ ] Treat does not gain recursive destructive behavior.
- [ ] Real-repository validation is recorded with honest remaining findings.
- [ ] Trilingual docs and `SKILL.md` define the exact evidence boundary.
- [ ] Full local and nine required CI gates pass.

## STOP conditions

Stop and report back if:

- Official current Cursor/Copilot syntax requires a general YAML feature outside
  the bounded scalar subset for the selected core modes.
- Correct matching requires IDE state, semantic task classification, or user
  settings not present in the repository.
- A valid current producer format would be mislabeled ignored/invalid.
- Concrete path-domain intersection suppresses a reproduced overlapping
  conflict.
- Recursive discovery cannot be separated from recursive mutation safely.
- Public compatibility requires removing/renaming existing report fields or
  changing canonical scope semantics.
- The implementation starts expanding to other vendors, prose scoping, or an
  ignore language to make tests pass.
- Verification fails twice after a reasonable scoped fix.

## Maintenance notes

- Applicability is a product-specific language. Add a new vendor only with
  official syntax evidence, bounded parsing, real fixtures, and explicit
  unknown-mode behavior.
- Path matching can prove that a rule applies or does not apply to a concrete
  target/current file. It cannot prove semantic-description selection or every
  future glob intersection.
- Keep full-file security and identity independent from effective-instruction
  filtering.
- Recursive discovery is read-only evidence. Never let a registry glob
  silently authorize recursive deletion.
- If users later need Claude `paths` or additional formats, extend the shared
  applicability abstraction rather than adding path-name conditionals to
  `scan.py`.
