# Plan 024: Scan every byte for security and identity without unbounded semantic reads

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 935eeb6..HEAD -- scripts/scan.py scripts/scan_render.py scripts/explain.py scripts/sarif.py scripts/pr_review.py tests/test_scan.py tests/test_explain.py tests/test_sarif.py tests/test_pr_review.py tests/test_cli.py EXTERNAL_VALIDATION.md README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json benchmark/self-eval/results-after-graded.json benchmark/self-eval/README.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: security / correctness / tests / docs
- **Planned at**: commit `935eeb6`, 2026-07-15

## Why this matters

The scanner labels an inventory field `sha256` and offers
`--fail-on-security`, but for any recognized instruction file larger than
`--max-bytes` both claims currently cover only the retained prefix. A secret or
permission-bypass recommendation after byte 32,768 is invisible, two files
with identical prefixes receive the same reported hash, and prefix-only
conflict/overlap results look complete.

The audit reproduced the failure with a 50,087-byte `AGENTS.md`: a
credential-shaped token and `--dangerously-skip-permissions` placed after the
default limit produced one size warning, zero security findings, and exit 0
under `--fail-on-security`. Two 60,019-byte files with identical first 32 KiB
but different package-manager declarations also received the same hash, no
conflict, and a 100% overlap claim. Preserve the bounded semantic prefix, but
stream every contained byte for file identity, line count, and high-confidence
security checks, and make every prefix-only conclusion explicitly partial.

## Current state

- `scripts/scan.py:551-591` stats an oversize file and reads only its prefix:

  ```python
  size = safe_path.stat().st_size
  if size > max_bytes:
      ...
      with safe_path.open("rb") as fh:
          data = fh.read(max_bytes)
  else:
      data = safe_path.read_bytes()
  text = data.decode("utf-8", errors="replace")
  return {
      "bytes": size,
      "lines": ...,
      "sha256": hashlib.sha256(data).hexdigest()[:12],
      "text": text,
  }
  ```

  Thus `bytes` describes the full file while `lines`, `sha256`, and `text`
  describe different, undisclosed prefix coverage.

- `scripts/scan.py:623-641` computes overlap only from each entry's `text`.
  `extract_signals()` at `scripts/scan.py:810-851` and
  `analyze_scoped_conflicts()` at `scripts/scan.py:953-1018` do the same for
  conflicts and parent/child overrides.

- `security_findings()` at `scripts/scan.py:1186-1330` calls
  `secret_hits(f["text"])` and searches the same truncated `text` for
  permission-bypass flags. The report's fail gate therefore cannot see a tail
  security finding.

- `collect_instruction_files()` at `scripts/scan.py:1468-1479` removes only the
  private `text` key. Every other `file_info()` field is presented in JSON,
  while `scripts/scan_render.py:19-26` renders `sha256` as if it covers the
  file:

  ```python
  | File | Tool | Bytes | Lines | SHA256 |
  ...
  f"| ... | `{f['sha256']}` |"
  ```

- `tests/test_scan.py:1097-1119` deliberately asserts that oversize `text` is
  bounded, which remains correct. It does not assert full-file identity,
  security coverage, line count, or honest conflict/overlap coverage.

- `scripts/explain.py` consumes the same internal file entries through
  `scan.collect_instruction_files()` and projects scoped conflicts. Any new
  evidence-boundary metadata must remain truthful in explain; do not create a
  second file-reading path there.

## Target contract

1. `--max-bytes` remains the in-memory **semantic text budget**, not a security
   boundary. An oversize file's private `text` contains at most that many input
   bytes, decoded with the existing replacement policy.
2. Every contained recognized instruction file is streamed in bounded chunks
   to calculate:
   - SHA-256 over the complete bytes;
   - exact complete-file byte and line counts;
   - high-confidence secret labels;
   - instruction permission-bypass labels.
   No complete file body or unbounded line is retained merely to obtain those
   results.
3. The public `sha256` field keeps its current 12-hex shape for compatibility
   but changes to the complete-file digest. Public inventory adds explicit,
   additive coverage metadata such as:

   ```json
   {
     "bytes": 50087,
     "lines": 1400,
     "sha256": "full-file-prefix",
     "analyzed_bytes": 32768,
     "truncated": true,
     "security_scanned_bytes": 50087
   }
   ```

   Exact additive field names may be tightened before implementation, but JSON
   and Markdown must unambiguously distinguish full identity/security coverage
   from bounded semantic coverage.
4. Secret values and matched command text are never stored in the inventory,
   JSON report, SARIF, PR comments, or tests. Streaming security metadata
   carries only the same safe labels/categories already returned by
   `secret_hits()` and `security_findings()`.
5. Chunk-boundary matching is correct. A recognized token or bypass flag split
   across two read chunks is found exactly once. Use a bounded overlap or an
   incremental scanner with a documented maximum retained window; do not join
   all chunks into a full string.
6. Conflict, override, and overlap extraction may remain prefix-bounded, but
   the report must not imply completeness:
   - a top-level deterministic analysis-limit record identifies every
     truncated path, full bytes, analyzed bytes, and affected report families;
   - an emitted overlap involving a truncated entry is labeled prefix-only in
     JSON and Markdown;
   - relevant conflict/override/explain output either carries partial-source
     metadata or is accompanied by the same explicit limitation record;
   - an empty conflict/overlap list cannot be presented as proof that an
     oversize file's unseen tail agrees.
7. Normal-size files preserve existing findings, ordering, exit codes, and
   report semantics. The changes are additive except that `sha256`/`lines` for
   oversize files become truthful complete-file values and tail security
   findings can now fail the existing gate.
8. Repository containment, skipped-directory behavior, one-tree-walk
   invariants, monorepo subcontexts, baselines, and plugin opt-in behavior stay
   unchanged.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Scan tests | `python3 -m unittest discover -s tests -p 'test_scan.py' -v` | all pass |
| Explain tests | `python3 -m unittest discover -s tests -p 'test_explain.py' -v` | all pass |
| GitHub output tests | `python3 -m unittest discover -s tests -p 'test_sarif.py' -v && python3 -m unittest discover -s tests -p 'test_pr_review.py' -v` | all pass |
| CLI tests | `python3 -m unittest discover -s tests -p 'test_cli.py' -v` | all pass |
| Python lint | `ruff check scripts/scan.py scripts/scan_render.py scripts/explain.py scripts/sarif.py scripts/pr_review.py tests` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | `OK` |
| Full gate | `npm run check` | exit 0 |
| Evidence gate | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0 |
| Self scan | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0; grade A |

## Scope

**In scope**:

- `scripts/scan.py`
- `scripts/scan_render.py`
- `scripts/explain.py` only where needed to preserve the shared evidence
  boundary
- `scripts/sarif.py` / `scripts/pr_review.py` only if integration changes are
  needed for newly detected tail security findings
- matching tests in `tests/test_scan.py`, `tests/test_explain.py`,
  `tests/test_sarif.py`, `tests/test_pr_review.py`, and `tests/test_cli.py`
- synchronized `README.md`, `README.zh-CN.md`, `README.ja.md`
- `SKILL.md`
- one read-only real-repository oversize validation in
  `EXTERNAL_VALIDATION.md`
- a compact evidence-coverage invariant in `AGENTS.md`
- evidence-bound `benchmark/self-eval/` refresh after `AGENTS.md` changes
- `plans/README.md`

**Out of scope**:

- Loading every oversize instruction file completely into memory.
- Full-file natural-language signal extraction, semantic merging, or
  declaration-vs-code analysis beyond the configured semantic text budget.
- Inventing a streaming parser for Markdown or tool-specific applicability.
- Printing, preserving, or snapshotting any credential value found during
  validation.
- Changing secret regexes, severity levels, baseline eligibility, fail exit
  codes, or plugin execution policy.
- Following external symlinks or changing `SKIP_DIRS`.
- Removing the size/context-bloat warning merely because security scans all
  bytes.
- Adding a runtime dependency.

## Git workflow

- Branch: `fix/complete-oversize-scan-evidence`
- Commit: `fix(scan): cover oversize file security and identity`
- One focused security/correctness PR with tests and synchronized public docs.
- Do not push directly to `main`. Open an English PR, wait for all nine
  required contexts, then squash-merge and delete the branch.
- This repairs false-negative and misleading-evidence behavior without
  removing a public field. By itself it is patch-level.

## Steps

### Step 1: Add failing end-to-end oversize characterizations

Extend `tests/test_scan.py` with temporary repositories covering:

1. a credential-shaped token after `max_bytes` is reported as a HIGH security
   finding, while the value itself is absent from serialized output;
2. `--dangerously-skip-permissions` after `max_bytes` is reported as a MEDIUM
   instruction finding;
3. CLI `scan --json --fail-on-security` exits 2 for the tail credential;
4. two oversize files with the same prefix and different tails have different
   complete-file hashes;
5. complete line count includes tail lines while `text` stays bounded;
6. a secret split at a streaming chunk boundary is detected once;
7. a normal-size file keeps its existing hash, line count, findings, and no
   truncation limitation;
8. an external file symlink remains unread and no external sentinel appears.

Add report-shape tests for the chosen coverage fields and analysis-limit
records. For same-prefix/different-tail conflict and overlap fixtures, assert
that the output is explicitly prefix-only rather than asserting a false
complete conclusion.

**Verify**: the tail-security, full-hash, full-line-count, and coverage
assertions fail against `935eeb6`; existing containment tests remain green.

### Step 2: Stream complete identity and security metadata in one bounded pass

Refactor `file_info()` around a small pure/bounded streaming helper:

- resolve containment before opening, as today;
- read fixed-size binary chunks;
- update one SHA-256 object and exact byte/newline counters;
- retain no more than `max_bytes` for semantic `text`;
- feed decoded text through a bounded carry window sufficient for every
  current security/risky-instruction pattern;
- deduplicate labels found in overlapping windows;
- derive final line count from total newlines plus whether the non-empty file
  ends in a newline;
- return private safe label sets for `security_findings()` plus public coverage
  metadata.

Document why the carry bound is sufficient and add a test that would fail if a
future pattern exceeds it without updating the bound. If a generic helper
cannot prove that relationship, STOP rather than silently choosing an
arbitrary overlap.

Do not call `Path.read_bytes()` for an oversize file and do not append chunks
to an unbounded list. Keep deterministic label and file ordering.

**Verify**: focused `FileInfoStatBeforeReadTests` and new streaming-boundary
tests pass; a patched/spied reader proves no individual retained semantic
buffer exceeds the configured budget.

### Step 3: Consume safe full-file security labels

Change `security_findings()` so recognized instruction files use the
stream-derived secret and permission-bypass labels, not `f["text"]`, while
retaining current finding categories/messages/severities. Raw MCP/settings
files continue through their existing contained `ScanContext` paths.

Ensure internal-only label/carry fields are removed from `result_files`.
Explicitly enumerate internal keys or construct the public inventory shape;
do not rely on removing only `text`, which would accidentally expose future
scanner state.

**Verify**: tail findings reach JSON, Markdown, SARIF, PR-review conversion,
and the existing `--fail-on-security` exit policy without containing the
matched secret.

### Step 4: Make bounded semantic evidence explicit everywhere

Add deterministic analysis-limit records during
`collect_instruction_files()`/`scan_repo()` and render them in
`scan_render.py`. Update overlap records and wording so a truncated input says
“analyzed prefix” with byte coverage instead of claiming whole-file
similarity. Attach or propagate enough partial-source information for scoped
conflicts/overrides and `explain` to avoid claiming the unseen tail was
analyzed.

Keep complete-file reports byte-compatible where feasible. Any additive field
must have one documented meaning across root scan, monorepo package scan,
multi-repo output, explain, and GitHub-native findings.

**Verify**: JSON and Markdown snapshot-style assertions cover complete and
partial files; root/package/explain tests agree on the same limitation.

### Step 5: Document and externally validate the evidence boundary

Update all three READMEs and `SKILL.md` to state:

- `--max-bytes` bounds semantic/conflict/overlap text;
- identity and high-confidence security checks cover the complete file;
- partial conclusions are labeled and absence is not proof about the unseen
  tail.

Keep every fenced block, inline code comment, table row/link structure, and
heading level synchronized across the three READMEs.

Run one read-only validation against a real repository containing an oversize
recognized config (or a documented byte-exact enlarged copy in an isolated
temporary fixture if no suitable public file is available). Record repo/date,
bytes, coverage fields, security handling without secret values, and fixing PR
in `EXTERNAL_VALIDATION.md`.

Add a compact future-maintenance invariant to `AGENTS.md`, refresh the
evidence-bound self-eval artifacts, and mark Plan 024 DONE only after the PR is
merged.

**Verify**: docs sync, self scan, evidence gate, strict drift, and full gate all
pass; `AGENTS.md` remains below the repository's context-bloat threshold.

## Test plan

- Model new streaming tests after
  `FileInfoStatBeforeReadTests.test_oversize_file_reports_full_size_but_reads_only_max_bytes`
  and existing `SecurityTests`; keep all fixtures temporary and synthetic.
- Cover empty files, no-final-newline files, multibyte UTF-8 crossing a chunk,
  exact-`max_bytes`, `max_bytes + 1`, and a token split across chunks.
- Assert full digest against `hashlib.sha256(original_bytes)` and never against
  a hard-coded credential-bearing snapshot.
- Test complete vs prefix-only overlap/conflict Markdown and JSON.
- Preserve existing one-walk and monorepo-subcontext tests.
- Run the full test matrix through `npm run check`.

## Done criteria

- [ ] Tail credentials and bypass flags are detected without retaining or
      emitting their values.
- [ ] Oversize `sha256`, bytes, and lines describe the complete file.
- [ ] Semantic `text` remains bounded by `max_bytes`.
- [ ] Every prefix-only overlap/conflict/override/explain conclusion exposes
      deterministic coverage metadata.
- [ ] Normal-size scan output and all existing exit codes remain compatible.
- [ ] External symlink and skipped-directory containment tests pass.
- [ ] Three READMEs, `SKILL.md`, `EXTERNAL_VALIDATION.md`, and compact
      `AGENTS.md` maintenance guidance are current.
- [ ] `npm run check`, evidence gate, self scan, and strict drift all pass.
- [ ] No files outside the in-scope list are modified.
- [ ] Plan 024 and its index row are marked DONE after squash merge.

## STOP conditions

Stop and report back (do not improvise) if:

- In-scope code no longer matches the current-state behavior or Plan 024's
  shared scan/explain seam after the drift check.
- Correct chunk-boundary matching would require retaining an unbounded line or
  full file for any current security regex.
- A complete-file digest cannot be produced without following a path outside
  the audited repository.
- Fixing the bug requires changing the meaning of `--max-bytes` to an unbounded
  semantic read or removing existing size warnings.
- A proposed public schema removes/renames existing fields instead of using
  backward-compatible additive coverage metadata.
- A test or external validation would require storing or printing a real
  credential.
- A verification command fails twice after a reasonable scoped fix.

## Maintenance notes

- Any future security pattern must remain compatible with the documented
  streaming carry bound; reviewers should demand a cross-chunk regression test.
- `sha256` is intentionally still 12 displayed hex characters, but its source
  is now the complete file. Do not reintroduce a prefix digest under that name.
- New consumers of internal `text` must decide whether prefix coverage is
  acceptable and propagate analysis limits; absence of a finding from bounded
  semantic text is not complete-file evidence.
- Full semantic parsing and tool-specific applicability remain explicitly
  deferred. The selected change protects audit truth without turning the
  scanner into a semantic merger.
