# Plan 067: Redact secrets from nested eval usage metadata before persistence or rendering

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md` unless a reviewer maintains the index separately.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat cf96c2a..HEAD -- \
>   scripts/eval_run.py tests/test_eval_run.py \
>   README.md README.zh-CN.md README.ja.md README.es.md README.ko.md \
>   README.pt-BR.md README.fr.md SKILL.md AGENTS.md \
>   benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json \
>   benchmark/self-eval/results-after-graded.json
> ```
>
> If either in-scope implementation file changed, rerun the mechanical
> reproduction and compare the excerpts below with live code. A semantic
> mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: S
- **Risk**: LOW (extends the existing high-confidence redactor to one omitted
  result subtree; numeric usage/cost data, grading, and schema remain unchanged)
- **Depends on**: Plan 051 (DONE; established raw-grading vs persisted-redaction
  separation and the shared redactor)
- **Category**: security / persisted artifact minimization
- **Planned at**: commit `cf96c2a`, 2026-07-20
- **Status**: DONE — plan PR
  [#292](https://github.com/NieZhuZhu/ai-harness-doctor/pull/292);
  implementation PR
  [#293](https://github.com/NieZhuZhu/ai-harness-doctor/pull/293), squash merge
  `b26974f`; both passed all nine required contexts.

## Implementation evidence

- The pre-fix public runner reproduction is now an end-to-end regression: raw
  regex grading still sees the generated sentinel and passes, while the exact
  value is absent from persisted stdout/answer and nested
  `usage`/`cost`/`tokens`.
- `sanitize_json_strings()` creates an iterative JSON-compatible safe copy,
  redacts string keys/values, preserves numeric/bool/null/container values, and
  uses deterministic safe suffixes for colliding redacted keys without losing
  values or mutating the input.
- Successful and non-zero runners plus single, multi-round, matrix, and regrade
  final artifacts are covered. Matrix Markdown does not render usage and is
  checked for absence of the raw value.
- Historical/manual `--compare` input is sanitized at stdout and file report
  boundaries, table pipes/backticks/newlines are neutralized, before/after
  preference is covered, and both source files remain byte-identical.
- Standards, Spec, and security-focused `bits-code-guard` reviews found no
  remaining P0–P2 issues. Review artifacts are under
  `/tmp/ai-harness-doctor_review_067/`.
- Final local evidence on the reviewed tree: `npm run check` passed 892 Python
  tests, 51 Node tests, lint, synchronized docs/adapters, and packed candidate;
  eval-focused tests passed 146/146; scan exited 0; strict drift was 100/A;
  current-evidence self-eval was 40/40; public-registry audit reported zero
  vulnerabilities; `AGENTS.md` was 10,171 bytes.
- PR #293 head `1e9f1bc` passed `drift`, `lint`, Node 16/20/22, `self-test`,
  and Python 3.9/3.10/3.12, had zero unresolved review threads, and was
  squash-merged as `b26974f`; the implementation branch was deleted.

## Why this matters

Plan 051 redacts runner `stdout`/`answer`/`stderr` and judge diagnostics before
eval records are persisted. The same runner JSON can contain `usage`, `cost`,
`tokens`, and related metadata. `maybe_usage()` copies those values verbatim
into the record, while `sanitize_result_record()` never traverses `usage`.

A buggy or hostile runner can therefore put a credential in an arbitrary
nested string under usage metadata. The visible `stdout` copy is redacted, but
the same value is still written in plaintext to single-run, multi-round, and
matrix result JSON. `--compare` can also copy usage from a supplied historical
or manual result into Markdown. This violates the documented guarantee that
high-confidence credentials are absent from serialized eval artifacts.

Extend the existing persistence boundary rather than redacting before grading
or changing `maybe_usage()` semantics. Every nested string key/value below
`record["usage"]` must use the shared `redact_secret_values()` helper. Preserve
container shape and every non-string scalar exactly. Protect comparison
rendering independently because compare accepts existing result files that may
predate the fix and does not rewrite them.

## Current state and mechanical reproduction

### Usage extraction copies arbitrary nested values

`scripts/eval_run.py:167-182`:

```python
def maybe_usage(stdout):
    ...
    usage = {}
    for key in ["usage", "cost", "total_cost_usd", "tokens", "input_tokens", "output_tokens"]:
        if key in data:
            usage[key] = data[key]
    return usage
```

The values may be numbers, strings, lists, or nested objects. This extraction
correctly occurs on raw stdout before persistence and must keep seeing raw
values.

### The record sanitizer skips usage

`scripts/eval_run.py:203-221`:

```python
def sanitize_result_record(record):
    """Redact every persisted runner/judge text field in one task record."""
    for key in ("stdout", "answer", "stderr"):
        if isinstance(record.get(key), str):
            record[key] = redact_secret_values(record[key])
    if isinstance(record.get("judge"), dict):
        record["judge"] = sanitize_judge_info(record["judge"])
    return record
```

`run_runner_record()` calls this boundary for successful/non-zero/timeout
records and every single/round/matrix producer reuses those records. Regrade
also calls it per record. Adding nested usage sanitization here gives all
persisted result families one contract.

### Comparison renders supplied usage without sanitizing it

`scripts/eval_run.py:1989-1996`:

```python
for tid in ids:
    b, a = bmap.get(tid, {}), amap.get(tid, {})
    ...
    usage = json.dumps(a.get("usage") or b.get("usage") or {}, ensure_ascii=False)
    lines.append(f"| `{tid}` | {b.get('passed')} | {a.get('passed')} | {delta} | `{usage}` |")
```

Unlike a newly produced result, a historical/manual comparison input may
contain unredacted metadata. Rendering is a separate report boundary and must
not echo it.

### Reproduction on `main@cf96c2a`

A temporary runner printed this JSON, using a runtime-generated GitHub-token
sentinel in three nested metadata shapes:

```json
{
  "result": "ok",
  "usage": {"trace": "<sentinel>"},
  "cost": {"note": "<sentinel>"},
  "tokens": ["<sentinel>"]
}
```

Observed:

```text
eval exit: 0
sentinel in persisted result JSON: true
stdout field: every sentinel replaced with <redacted:GitHub token>
usage field: all three sentinel copies remained plaintext
```

This proves raw grading/redaction works for stdout while the secondary
`usage` persistence path bypasses it.

## Target contract

1. Detection, answer extraction, grading, judge input, and `maybe_usage()` use
   bounded raw runner output exactly as before.
2. Before returning/persisting a task record, recursively sanitize every string
   value and string object key below `record["usage"]` with the existing
   `redact_secret_values()` helper.
3. Preserve JSON-compatible structure and non-string scalars exactly:
   dictionaries remain dictionaries; lists remain lists; numbers, booleans,
   and null are unchanged.
4. Handle arbitrary combinations of dictionaries/lists without mutating the
   original extracted object in place. Return a safe copy from the sanitizer.
5. If two distinct object keys become identical after redaction, preserve both
   values without silently overwriting one by adding deterministic safe
   occurrence suffixes to the second and later keys (for example `#2`, `#3`).
   Do not keep either raw key or change non-colliding safe keys.
6. Keep the traversal bounded by the already bounded runner output. It must not
   crash an eval batch on deeply nested but JSON-decodable metadata; implement
   an iterative traversal or a clear bounded/fail-safe strategy compatible with
   Python 3.9.
7. `sanitize_result_record()` applies the recursive sanitizer whenever `usage`
   is present, including successful, non-zero, timeout, matrix/round, and
   `--regrade` records.
8. Existing numeric usage behavior is byte-compatible at the JSON value level:
   examples such as `{"usage":{"input_tokens":3},"cost":0.01}` remain equal.
9. `--compare` sanitizes the chosen before/after usage value before
   `json.dumps()` so existing/manual historical result files cannot leak into
   Markdown or stdout. It does not rewrite the input files.
10. The comparison Markdown table remains structurally valid. Escape or
    neutralize any user-controlled usage JSON characters needed to keep a
    string from breaking the backtick/table cell; reuse an existing Markdown
    neutralizer if one applies rather than creating a divergent policy.
11. Do not redact result IDs, labels, prompts, task definitions, arbitrary
    unknown top-level metadata, or numeric billing data in this plan. They are
    separate contracts and broadening scope would risk compatibility.
12. Do not change secret detection patterns, placeholder semantics, result
    schema, grading outcomes, health calculations, usage key allow-list, or
    output-size limits.
13. Python 3.9+ standard library only; no runtime dependency.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused tests | `PYTHONPATH=tests python3 -m unittest test_eval_run.MaybeUsageTests test_eval_run.EvalRunTests -v` | exit 0 |
| Full eval tests | `python3 -m unittest discover -s tests -p 'test_eval_run.py' -v` | exit 0 |
| Full gate | `npm run check` with the CI-supported npm client | lint, all tests, packed candidate pass |
| Self scan | `python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0, 100/100 grade A |
| Eval gate | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0, every task passes |
| README sync | `python3 scripts/check_readme_sync.py` | all seven READMEs aligned |
| Adapter sync | `python3 scripts/gen_adapters.py --check` | 18 adapters match |
| Dependency audit | npm 10.8.2 against `https://registry.npmjs.org`, `npm audit --audit-level=high` | zero high/critical vulnerabilities |

## Scope

**In scope**:

- `scripts/eval_run.py`
  - a small JSON-compatible nested-string sanitizer near the existing
    redaction helpers;
  - `sanitize_result_record()` usage handling;
  - comparison-report usage rendering.
- `tests/test_eval_run.py`
  - recursive sanitizer unit/edge tests;
  - successful/non-zero runner result coverage;
  - single/round/matrix/regrade serialization;
  - historical/manual comparison report.
- Public behavior docs:
  - `README.md`, `README.zh-CN.md`, `README.ja.md`, `README.es.md`,
    `README.ko.md`, `README.pt-BR.md`, `README.fr.md`;
  - `SKILL.md`.
- `AGENTS.md` only by compacting/replacing the existing eval safety invariant;
  keep it at or below 10,240 bytes.
- `benchmark/self-eval/tasks.json`, `results-after.json`, and
  `results-after-graded.json` only if `AGENTS.md` changes; refresh honestly via
  offline regrade.
- Plan/index evidence and status.

**Out of scope**:

- New secret patterns, entropy/PII detection, encryption, or key rotation.
- Redacting data before grading or before an explicitly selected judge call.
- Changing which usage keys `maybe_usage()` extracts.
- Validating/rejecting contradictory `passed` and operational evidence; this is
  a separately reproduced correctness finding.
- Root generated-task evidence, `drift --fix` transactionality, `actionlint`,
  formatter ownership, runtime floors, or product-direction work.
- Rewriting historical result files except when the operator explicitly runs
  `--regrade`.
- General-purpose recursive serialization/refactor outside eval records.

## Git workflow

- Start implementation from latest `main` after the plan-only PR merges.
- Branch: `fix/067-redact-eval-usage-metadata`
- Commit: `fix(eval): redact nested usage metadata`
- Tests and implementation land in the same commit/PR. Conventional Commit in
  English.
- Backward-compatible security bugfix: patch release.
- Do not merge until all nine required contexts are green: `drift`, `lint`,
  Node 16/20/22, `self-test`, and Python 3.9/3.10/3.12.
- Resolve every review thread. Admin bypass is only for the sole-maintainer
  self-approval deadlock after all checks are green.

## Steps

### Step 1: Add one red end-to-end usage leak test

Model after `test_runner_secret_is_redacted_after_raw_grading` and
`test_single_round_result_file_redacts_runner_secret`.

Create a temporary Python runner that prints a valid JSON envelope containing:

- an answer that passes from raw output;
- nested token sentinels in `usage`, `cost`, and `tokens`;
- ordinary numeric token/cost fields.

Run the public eval CLI into a result JSON. Assert:

- exit 0 and the task still passes;
- the exact sentinel is absent from the complete serialized result;
- redaction markers appear at every nested string location;
- numeric values and list/dict shape remain unchanged.

**Verify on unpatched `cf96c2a`**: the test fails because `usage` retains the
exact sentinel even though stdout is redacted.

### Step 2: Add the narrow recursive sanitizer

Implement one JSON-compatible safe-copy helper near
`sanitize_result_record()`. Apply `redact_secret_values()` only to strings,
including object keys. Preserve lists, dictionaries, numbers, booleans, and
null.

Add focused tests for:

- nested dict/list mixtures;
- string keys and string values;
- ordinary numeric usage byte/value compatibility;
- empty structures;
- a deep JSON-decodable structure near the supported nesting limit;
- two raw keys that redact to one placeholder (no silent value loss).

Do not call JSON serialize/deserialize as the primary implementation if that
would collapse keys or reformat numbers unexpectedly.

**Verify**: focused sanitizer tests pass, including key-collision and depth.

### Step 3: Route every record family through the safe usage copy

Extend `sanitize_result_record()` so a present usage field is replaced with
the sanitized copy after grading. Keep the existing stdout/answer/stderr and
judge behavior unchanged.

Extend the current final-artifact test matrix to put the sentinel only in
usage metadata and assert absence from:

- single result JSON;
- multi-round result JSON;
- matrix JSON and Markdown;
- regrade output;
- successful and non-zero runner records.

Timeout records normally carry `{}` usage and need only remain compatible.

**Verify**: all artifact tests pass; raw regex grading and numeric usage tests
remain green.

### Step 4: Protect historical/manual comparison rendering

Add two existing result files whose selected usage metadata contains nested
sentinels and Markdown metacharacters. Run `--compare` both to stdout and `-o`.

Sanitize the chosen usage value before rendering. Assert the exact sentinel is
absent, the marker is present, the Markdown table keeps one row/cell shape, and
neither input JSON is rewritten.

**Verify**: comparison tests pass for before-only and after-preferred usage.

### Step 5: Document the completed result-artifact guarantee

Update English and all six translations plus `SKILL.md`: high-confidence
credentials are removed from runner/judge text **and nested usage metadata**
before persistence or report rendering, while grading uses bounded raw output
in memory and numeric usage/cost remains available.

If `AGENTS.md` changes, compact the existing eval bullet rather than adding
another one, keep `wc -c AGENTS.md <= 10240`, update the objective self-eval
answer/task only as needed, and run the documented offline regrade. State
honestly that it is not a new model run.

**Verify**: README sync, AGENTS budget, current-evidence eval, scan, and drift.

### Step 6: Review, gate, and close out

Run every command in the table. Review the full diff along Standards and Spec
axes plus a security-focused local code review. Confirm no raw sentinel appears
in any generated test artifact or error output.

Open one implementation PR after the plan-only PR. Wait for all nine required
contexts, resolve every thread, squash-merge, and delete the branch. Then open a
separate plan-closeout PR with the actual evidence; merge it only after its own
nine contexts are green.

## Test plan

- Public single-run result: nested usage/cost/tokens sentinel absent.
- Raw grading unchanged while persistence is redacted.
- Recursive dict/list string keys and values.
- Numeric/bool/null and container structure preserved.
- Redacted-key collision has deterministic no-loss behavior.
- Deep JSON-compatible usage cannot crash the batch.
- Success and non-zero runner records.
- Multi-round, matrix JSON/Markdown, and regrade.
- Historical/manual `--compare` stdout/file rendering; source files unchanged.
- Existing stdout/answer/stderr/judge redaction and numeric usage tests remain
  green.

## Done criteria

- [ ] The reproduction's exact sentinel is absent from the full result JSON.
- [ ] Every nested usage string key/value uses the shared redaction marker.
- [ ] Non-string scalars and structure remain compatible; colliding redacted
      keys receive deterministic safe suffixes and lose no values.
- [ ] Raw answer grading is unchanged.
- [ ] Single, round, matrix, regrade, and comparison surfaces are covered.
- [ ] Historical/manual comparison inputs are not rewritten.
- [ ] Existing Plan 051 redaction tests and numeric usage tests remain green.
- [ ] Full eval suite and `npm run check` pass.
- [ ] Scan exits 0; strict drift is 100/A; current-evidence eval passes.
- [ ] Seven READMEs are synchronized; `AGENTS.md` is at most 10,240 bytes.
- [ ] No file outside scope or fixture input is modified.
- [ ] Implementation PR has all nine required contexts green, zero unresolved
      threads, is squash-merged, and its branch is deleted.
- [ ] A separate closeout PR records real evidence, passes all nine contexts,
      is squash-merged, and its branch is deleted.

## STOP conditions

Stop and report instead of improvising if:

- Grading would need to use redacted usage/stdout rather than bounded raw
  output.
- The fix requires changing result schema, usage key allow-list, health, judge,
  or pass/fail semantics.
- Safe occurrence suffixes cannot preserve colliding redacted keys without
  changing unrelated keys or value/container types.
- The recursive sanitizer must accept arbitrary Python object types that cannot
  arise from JSON/manual result data.
- Comparison safety would require rewriting input files.
- Any existing test intentionally expects a high-confidence credential to
  persist in usage metadata.
- A runtime dependency or Python >3.9 feature is required.
- A required verification fails twice, a CI context is red/pending, or a review
  thread remains unresolved.

## Maintenance notes

- Any future persisted task-record subtree containing repository/runner/judge
  strings must explicitly pass through the same safe-copy boundary.
- Keep raw values only in bounded process memory for grading; persisted and
  rendered surfaces are minimization boundaries.
- Reviewers should confirm recursion/depth and key-collision behavior rather
  than only checking the happy-path string value.
- The separately reproduced contradictory operational-evidence validator is
  not fixed by redaction and remains eligible for a later independent round.
