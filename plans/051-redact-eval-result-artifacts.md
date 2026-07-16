# Plan 051: Redact secrets before persisting eval result artifacts

> **Drift check**:
>
> ```bash
> git diff --stat 2f9784d..HEAD -- \
>   scripts/scan.py scripts/eval_run.py scripts/redaction.py \
>   tests/test_scan.py tests/test_eval_run.py \
>   README.md README.zh-CN.md README.ja.md README.es.md README.ko.md \
>   README.pt-BR.md README.fr.md SKILL.md AGENTS.md
> ```

## Status

- **Priority**: P0
- **Effort**: L
- **Risk**: MED
- **Depends on**: Plans 049 and 050 (DONE)
- **Category**: security / persisted artifact minimization
- **Planned at**: commit `2f9784d`, 2026-07-16
- **Implementation**: DONE — PR #230 (plan) / PR #231 (impl),
  squash-merged to `main` as `69d7aac`; all nine required contexts green.

## Why this matters

The eval runner stores up to 1 MiB each of runner stdout/stderr in result JSON.
It also stores the extracted answer and external-judge raw output/stderr.

Agents execute inside the audited repository. A buggy or hostile task can print
an API key, token, JWT, or private-key header. That value is then written to
`results.json`, matrix/round results, regraded artifacts, and any CI artifact or
commit containing those files.

Plan 049 added deterministic secret redaction for scanner report text, but eval
has no equivalent boundary. Persisted eval evidence should preserve enough
diagnostic text for grading/debugging without serializing high-confidence
credentials.

## Mechanical reproduction

Use a generated sentinel in runner stdout:

```text
runner: printf 'answer <generated-token>\\n'
result:
  stdout: "answer <generated-token>\\n"
  answer: "answer <generated-token>"
token persisted? true
```

The same applies to timeout output, runner stderr, and external judge
`raw`/`stderr`.

## Current state

`scripts/eval_run.py:1760`:

```python
stdout = bounded_process_output(proc.stdout)
stderr = bounded_process_output(proc.stderr)
answer = extract_answer(stdout)
record = {
    "stdout": stdout,
    "answer": answer,
    "stderr": stderr,
}
```

The raw answer is also passed to `grade_answer`, which may call an external or
LLM judge. Redacting before grading could change task semantics, so detection,
grading, usage parsing, and persistence must be separated deliberately.

`run_judge` stores parsed verdict `raw` plus judge stderr. Timeout records store
captured stdout/stderr directly.

## Target contract

1. Detection/grading uses bounded raw process output exactly as before:
   - `extract_answer` for grading sees raw bounded stdout;
   - regex/command/judge behavior and pass/fail are unchanged;
   - usage parsing sees raw stdout.
2. Before a record is returned or written, redact secret spans in:
   - runner `stdout`;
   - stored `answer`;
   - runner `stderr`;
   - external judge `raw`;
   - external judge `stderr`;
   - timeout stdout/stderr/answer.
3. Use the same high-confidence patterns and placeholder semantics as scan.
   Extract them into one small standard-library module such as
   `scripts/redaction.py`; scan and eval must not maintain divergent copies.
4. Replace complete matched spans with stable `<redacted:TYPE>` markers. Never
   keep prefixes/suffixes.
5. Preserve bounded-output truncation and output schema. No new mandatory field.
6. Stored redaction is irreversible by design. Offline `--regrade` uses the
   redacted stored stdout and must remain deterministic.
7. Manual result files supplied by users are not automatically rewritten unless
   `--regrade` writes them; validators never echo their contents in errors.
8. No third-party dependency; Python 3.9 standard library only.

## Design

### Shared redaction module

Move secret regexes, placeholder detection, `secret_hits`, and
`redact_secret_values` into a small `scripts/redaction.py`.

- `scan.py` imports/re-exports helpers if compatibility needs it.
- `eval_run.py` imports only the redaction helper.
- Full-file bytes pattern compilation in scan remains compatible; either export
  `SECRET_PATTERNS` or keep scan-specific byte compilation over the shared list.

### Raw vs persisted variables

Use explicit names:

```python
raw_stdout = bounded_process_output(proc.stdout)
raw_stderr = bounded_process_output(proc.stderr)
raw_answer = extract_answer(raw_stdout)

passed, judge = grade_answer(..., raw_answer, ...)

record["stdout"] = redact_secret_values(raw_stdout)
record["answer"] = redact_secret_values(raw_answer)
record["stderr"] = redact_secret_values(raw_stderr)
```

Sanitize judge metadata recursively only for the known text fields; do not
mutate numeric score, exit code, provider/model, usage, or health.

## Scope

**In scope**:

- new `scripts/redaction.py`
- `scripts/scan.py`
- `scripts/eval_run.py`
- `tests/test_scan.py`, `tests/test_eval_run.py`
- all seven READMEs and `SKILL.md`
- plan/index updates

**Out of scope**:

- General PII/proprietary-code classification.
- Encrypting result files or changing their schema.
- Redacting task prompts/rubrics before sending to an explicitly selected judge.
- Rewriting arbitrary historical result files without `--regrade`.
- Lower-confidence entropy heuristics.

## Steps

### Step 1: Characterize every persistence path

Add generated-sentinel tests for:

- successful runner stdout and extracted answer;
- runner stderr;
- timeout stdout/stderr/answer;
- non-zero runner output;
- external judge raw/stderr;
- single, multi-round, and matrix JSON outputs;
- regrade output.

Assert pass/fail remains the same as unredacted raw grading.

### Step 2: Extract shared redaction helpers

Move patterns/placeholders/helper into `redaction.py`, update scan imports, and
keep all scan secret-recall + Plan 049 cross-surface tests green.

### Step 3: Redact at record boundaries

Separate raw grading values from persisted fields in `run_runner_record` and
`run_judge`. Apply redaction after bounding and before record return.

Ensure exceptions/diagnostics never print raw output.

### Step 4: Test all result shapes

Run/matrix/round share `run_runner_record`; still verify serialized end products
because an aggregation path may copy another field. Regrade must not reintroduce
secrets from `answer`.

### Step 5: Document the guarantee

All seven READMEs and `SKILL.md` state that result artifacts redact
high-confidence credentials while grading uses the original bounded output in
memory.

### Step 6: Gates and merge

```bash
python3 -m unittest discover -s tests -p 'test_scan.py' -v
python3 -m unittest discover -s tests -p 'test_eval_run.py' -v
npm run check
python3 scripts/check_readme_sync.py
python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json \
  --check-baseline --fail-on-security --fail-on-gaps --fail-on-semantic \
  --fail-on-conflicts
python3 scripts/check_drift.py . --strict
```

Open one implementation PR, wait for all nine contexts, then squash-merge. This
is a backward-compatible security **patch**.

## Done criteria

- [x] Generated sentinels absent from all serialized eval result shapes.
- [x] Redacted marker present in stdout/answer/stderr/judge diagnostics.
- [x] Grading, health, usage, timeout, and exit semantics unchanged.
- [x] Scan and eval use one shared pattern source.
- [x] Placeholder examples remain unredacted/non-findings.
- [x] Plan 049 scan report tests remain green.
- [x] Seven-language docs and full local gates pass.
- [x] Nine required CI contexts pass; PR squash-merged.

## STOP conditions

Stop if:

- redaction before persistence cannot be separated from grading;
- extraction creates a scan↔eval import cycle;
- result schema must become incompatible;
- diagnostics would print the value while handling redaction failure;
- any required CI context is red/pending.

## Maintenance notes

- Any new persisted runner/judge text field must pass through the shared helper.
- Keep high-confidence patterns centralized; scan/report/eval tests should use
  generated sentinels and inspect final serialized artifacts.
