# Plan 043: Fall back to the deterministic judge when an LLM returns unparseable output

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md`.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 3f0c017..HEAD -- \
>   scripts/eval_run.py tests/test_eval_run.py \
>   README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md
> ```
>
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against live code before proceeding. If
> `parse_judge_output`, `llm_judge`, `run_judge`, or `grade_answer` changed
> materially, treat that as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: bug (correctness — eval health integrity)
- **Planned at**: commit `3f0c017`, 2026-07-16
- **Implementation**: TODO

## Why this matters

`eval_run.py`'s LLM-as-judge has a documented, load-bearing contract: **every
failure mode — no API key, network error, malformed response — returns `None`
so grading gracefully falls back to the built-in deterministic keyword judge.**
That promise is stated in three places (the module banner, the `llm_judge`
docstring, and the `grade_answer` docstring).

The malformed-response case does **not** honor it. When a real LLM judge returns
HTTP 200 with a body that is not the expected JSON verdict — a truncated
response, a model that prepended prose, or an OpenAI-compatible proxy that
returns a 200 error envelope — `parse_judge_output` returns a **non-`None`**
sentinel verdict `{"passed": False, "score": None, "reason": "judge output was
not valid JSON"}`. `llm_judge` returns that sentinel unchanged, and `grade_answer`
treats any non-`None` verdict as authoritative, so the task is silently graded a
**hard fail** instead of falling back to the keyword judge.

This is exactly the "false health" bug class this repo treats as high priority
(cf. Plans 030/033/038/041): a recoverable, non-exceptional judge hiccup silently
lowers the Phase 3 pass rate and can flip `--fail-under` / `--check-regression`
gates. The network-error and no-key paths already fall back correctly; only the
malformed-content path leaks the sentinel.

## Mechanical reproduction

Against `main@3f0c017`, with a fake HTTP layer (no real API key needed):

```bash
python3 - <<'PY'
import sys
sys.path.insert(0, "scripts")
import eval_run

def fake_post(url, headers, payload, timeout):
    # HTTP 200, but the model returned prose instead of a JSON verdict.
    return {"choices": [{"message": {"content": "Sorry, I cannot comply."}}]}

eval_run._http_post_json = fake_post
import os
os.environ["OPENAI_API_KEY"] = "sk-test"
verdict = eval_run.llm_judge("the answer", "must mention X", provider="openai")
print("llm_judge returned:", verdict)
print("falls back (None)?", verdict is None)
PY
```

Observed on `3f0c017`:

```
llm_judge returned: {'passed': False, 'score': None, 'reason': 'judge output was not valid JSON', 'raw': 'Sorry, I cannot comply.', 'judge': 'llm:openai', 'model': 'gpt-4o-mini'}
falls back (None)? False
```

Expected after this plan: `llm_judge` returns `None` for unparseable model
output, so `grade_answer` falls through to `builtin_judge`.

## Current state

### `parse_judge_output` returns a non-None sentinel on unparseable input

`scripts/eval_run.py:1300-1326`:

```python
def parse_judge_output(stdout):
    """Parse an LLM-as-judge verdict. ..."""
    raw = bounded_process_output(stdout).strip()
    data = None
    try:
        data = json.loads(raw)
    except Exception:
        match = re.search(r"\{.*\}", raw, re.S)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                data = None
    if not isinstance(data, dict):
        return {"passed": False, "score": None, "reason": "judge output was not valid JSON", "raw": raw}
    passed = data.get("passed")
    score = data.get("score")
    if passed is None and isinstance(score, (int, float)) and not isinstance(score, bool):
        passed = score >= 0.5
    return {"passed": bool(passed), "score": score, "reason": data.get("reason", ""), "raw": raw}
```

### `llm_judge` returns the sentinel unchanged instead of `None`

`scripts/eval_run.py:1569-1575`:

```python
    except Exception as exc:  # noqa: BLE001 - any failure must fall back, never crash
        print(f"llm judge ({provider}) failed, falling back to keyword judge: {exc}", file=sys.stderr)
        return None
    verdict = parse_judge_output(content)
    verdict["judge"] = "llm:" + provider
    verdict["model"] = used_model
    return verdict
```

The `except` correctly returns `None` for network/shape errors (e.g. a missing
`choices[0].message.content` key raises and is caught). But a **successful**
`content` string that simply is not JSON flows through `parse_judge_output` into
a non-`None` sentinel verdict that is returned as authoritative.

### `grade_answer` treats any non-None verdict as authoritative

`scripts/eval_run.py:1641-1647`:

```python
        if judge_llm and judge_llm != "off":
            verdict = llm_judge(answer, rubric, provider=judge_llm, timeout=timeout, model=check.get("model"))
            if verdict is not None:
                return verdict["passed"], verdict
        if default_judge:
            verdict = builtin_judge(answer, check)
            return verdict["passed"], verdict
```

### The contract this must satisfy (three statements)

- Module banner `scripts/eval_run.py:1445-1447`: "Every failure mode — no API
  key, network error, malformed response — returns `None` so grading gracefully
  falls back to the built-in deterministic keyword judge."
- `llm_judge` docstring `scripts/eval_run.py:1512-1517`: "`None` means
  'unavailable / failed — fall back to the keyword judge': no matching API key,
  an unsupported provider, or any network/parse error."
- `grade_answer` docstring `scripts/eval_run.py:1587-1590`: "Any LLM failure (no
  key, network, parse) transparently falls back to the deterministic built-in
  judge."

### Why the other caller must stay unchanged

`parse_judge_output` has a **second** caller, `run_judge` (external
`--judge-cmd`, `scripts/eval_run.py:1426-1433`), which needs the dict return
(it attaches `exit_code`/`stderr` and, on a non-zero exit, overrides to a fail).
The external-`--judge-cmd` path deliberately has **no** LLM-style fallback (a bad
operator-supplied judge command should surface as a fail, not silently switch
graders). Therefore the fix must live at the `llm_judge` boundary, not inside
`parse_judge_output` in a way that changes what `run_judge` receives.

## Target contract

1. `parse_judge_output` marks the *unparseable* branch distinctly so a caller
   can tell "the model did not return a JSON verdict" apart from "the model
   returned a legitimate `{"passed": false}` verdict." A legitimate
   `{"passed": false, "score": 0, "reason": "wrong"}` and a bare
   `{"passed": false}` are **valid** verdicts and must NOT be treated as
   unparseable.
   - Suggested: add a boolean key (e.g. `"parse_error": True`) only on the
     `not isinstance(data, dict)` sentinel branch. Valid parses do not carry it
     (or carry `False`).
2. `llm_judge` returns `None` when `parse_judge_output` reports the parse-error
   sentinel, so `grade_answer` falls back to `builtin_judge`, satisfying the
   documented contract. A successful, well-formed verdict is returned unchanged
   (still gains `judge`/`model`).
3. `run_judge`'s behavior is **unchanged**: it still receives a dict, still
   attaches `exit_code`/`stderr`, still overrides on non-zero exit. The
   extra key is either ignored or harmless in its output. (Do not change the
   external-judge fail semantics in this plan.)
4. No change to the network/no-key/shape-error paths (already return `None`).
5. Deterministic, standard-library only, Python 3.9 compatible. No new runtime
   dependency.

## Design sketch (non-binding)

```python
# in parse_judge_output, only on the unparseable branch:
if not isinstance(data, dict):
    return {"passed": False, "score": None,
            "reason": "judge output was not valid JSON",
            "raw": raw, "parse_error": True}

# in llm_judge, after parse_judge_output(content):
verdict = parse_judge_output(content)
if verdict.get("parse_error"):
    print(f"llm judge ({provider}) returned unparseable output, "
          f"falling back to keyword judge", file=sys.stderr)
    return None
verdict["judge"] = "llm:" + provider
verdict["model"] = used_model
return verdict
```

Confirm no test asserts the *absence* of a `parse_error` key on a valid verdict
before adding it (grep in Step 1). If `run_judge`'s emitted JSON is snapshot-
compared anywhere, ensure the added key on the parse-error path does not break
that snapshot (the external-judge tests feed valid JSON, so the key is absent
there — verify in Step 1).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Eval tests | `python3 -m unittest discover -s tests -p 'test_eval_run.py' -v` | exit 0 |
| Full quality gate | `npm run check` | all lint + Python + Node tests pass |
| CLI syntax/help | `node --check bin/cli.js && node bin/cli.js help` | exit 0 |
| Self scan | `python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0, grade A |
| Evidence-bound eval | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0 |
| README synchronization | `python3 scripts/check_readme_sync.py` | exit 0 |
| Adapter synchronization | `python3 scripts/gen_adapters.py --check` | exit 0 |

## Scope

**In scope**:

- `scripts/eval_run.py` — `parse_judge_output` (add the marker) and `llm_judge`
  (map the marker to `None`).
- `tests/test_eval_run.py` — new regression tests.
- `README.md`, `README.zh-CN.md`, `README.ja.md`, `SKILL.md` — only if a
  user-facing sentence about LLM-judge fallback needs to match; keep trilingual
  fenced blocks/tables/links byte-synchronized.
- `AGENTS.md` — one durable invariant line only if it fits under 12 KiB.
- `plans/043-llm-judge-fallback.md`, `plans/README.md`.

**Out of scope**:

- `run_judge` external-`--judge-cmd` behavior and its exit-0-non-JSON handling
  (a separate, lower-severity item — do NOT change it here).
- `parse_judge_output`'s valid-verdict logic (the `score >= 0.5` implicit-pass
  rule and embedded-JSON extraction stay exactly as they are).
- Any change to `builtin_judge`, health scoring, or thresholds.
- Adding retries or changing timeouts.

## Git workflow

- Start from latest `main` after this plan PR merges:
  `fix/043-llm-judge-fallback`.
- One implementation PR. Conventional Commits in English, e.g.
  `fix(eval): fall back to keyword judge on unparseable LLM output`.
- Do not push directly to `main`.
- Do not merge until all nine required contexts are green: `drift`, `lint`,
  `node (16)`, `node (20)`, `node (22)`, `self-test`, `unittest (3.9)`,
  `unittest (3.10)`, and `unittest (3.12)`.
- Admin bypass is allowed only for the sole-maintainer approval deadlock after
  required checks are green and every discussion is resolved.

## Steps

### Step 1: Characterize the missing fallback

First confirm no test depends on the absence of a `parse_error` key:

```bash
grep -n "parse_error\|parse_judge_output" tests/test_eval_run.py
```

Then add regression tests (they fail against current code):

1. `llm_judge` with a `fake_post` returning HTTP 200 whose `content` is
   non-JSON prose (e.g. `"Sorry, I cannot comply."`) returns `None`.
2. `llm_judge` with a `fake_post` whose `content` is valid JSON
   (`{"passed": true, "score": 1}`) still returns a verdict with
   `passed is True` and `judge == "llm:openai"` (unchanged behavior).
3. `parse_judge_output("not json")` sets `parse_error` True; a valid
   `{"passed": false, "score": 0}` does NOT carry `parse_error` truthy and
   still yields `passed is False` (a legitimate fail is not a parse error).
4. End-to-end: a `judge` task graded with `judge_llm="openai"` and a `fake_post`
   returning non-JSON content is graded by the builtin keyword judge (assert the
   returned `judge_info` is the builtin verdict, not the `llm:openai` sentinel).

Model the new tests after the existing `LlmJudgeTests` in
`tests/test_eval_run.py` (they monkeypatch `eval_run._http_post_json` with a
`fake_post` and use `_EnvGuard(OPENAI_API_KEY="sk-test")`).

**Verify**: `python3 -m unittest discover -s tests -p 'test_eval_run.py' -v` →
the new fallback assertions fail before implementation.

### Step 2: Mark the unparseable branch and map it to a fallback

Add the `parse_error` marker on the `not isinstance(data, dict)` branch of
`parse_judge_output`, and in `llm_judge` return `None` when
`verdict.get("parse_error")` is set (with a clear stderr note that mirrors the
existing "falling back to keyword judge" wording).

**Verify**: `python3 -m unittest discover -s tests -p 'test_eval_run.py' -v` →
new tests pass; all existing `LlmJudgeTests`, `BuiltinJudgeTests`, `run_judge`
external-judge tests (`test_nonzero_external_judge_cannot_pass`,
`test_malformed_and_missing_external_judges_fail_without_fallback`) still pass
unchanged.

### Step 3: Confirm the external-judge path is untouched

Re-read `run_judge` and confirm the added key does not alter its emitted
`judge_info` for the existing external-judge tests (those feed valid JSON, so
`parse_error` is absent). Do not modify `run_judge`.

**Verify**: `python3 -m unittest discover -s tests -p 'test_eval_run.py' -v` →
external-judge tests green.

### Step 4: Synchronize docs if needed

If any README/SKILL sentence states the LLM-judge fallback conditions, make sure
"malformed / unparseable response" is included alongside "no key" and "network
error." Keep the three READMEs byte-synchronized on fenced blocks/tables/links.
If no user-facing sentence needs changing, leave docs untouched and say so.

**Verify**: `python3 scripts/check_readme_sync.py` and
`python3 scripts/gen_adapters.py --check` → both exit 0.

### Step 5: Optional invariant + evidence refresh

Only if it fits under 12 KiB, add one concise `AGENTS.md` invariant (LLM judge
falls back to the deterministic judge on no-key/network/unparseable output;
never records an unparseable response as a real fail). If you edit `AGENTS.md`
or `tasks.json`, refresh the evidence-bound self-eval via the documented regrade
workflow and keep Grade A. If not, leave the eval evidence untouched.

**Verify**:

```bash
wc -c AGENTS.md
python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json \
  --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md \
  --require-current-evidence --fail-under 80
python3 scripts/check_drift.py . --strict
```

Expected: AGENTS below 12288 bytes, eval current at Grade A, strict drift Grade A.

### Step 6: Full gate, review, and PR

Run every command in "Commands you will need". Review the diff on two axes:

- standards: stdlib-only, matching tests, no traceback leakage, trilingual doc
  parity if touched;
- spec: unparseable LLM output → `None` → builtin fallback; valid verdicts and
  the external-judge path unchanged; no scope creep into `run_judge`.

Open one implementation PR, wait for all nine contexts, resolve discussions,
squash merge, and record PR/head/check/merge evidence here and in the index.
This is a backward-compatible **patch**.

## Test plan

- New tests (in `tests/test_eval_run.py`, modeled on `LlmJudgeTests`):
  - `llm_judge` unparseable content → `None`;
  - `llm_judge` valid content → verdict unchanged (`passed`, `judge`, `model`);
  - `parse_judge_output` sets `parse_error` only on the unparseable branch and
    a legitimate `{"passed": false}` is not flagged;
  - end-to-end `grade_answer(..., judge_llm="openai")` with unparseable content
    is graded by the builtin judge.
- Preserved: all existing eval/judge tests unchanged.

## Done criteria

- [ ] `llm_judge` returns `None` on HTTP-200 unparseable model output.
- [ ] A valid LLM verdict is still returned with `judge`/`model` set.
- [ ] `parse_judge_output` distinguishes unparseable from a legitimate fail.
- [ ] `run_judge` external-judge behavior is unchanged (tests green).
- [ ] Behavior changes ship with tests in the same PR.
- [ ] `npm run check` passes.
- [ ] Self scan exits 0; strict drift is 100/100 Grade A.
- [ ] Evidence-bound self-eval is current and Grade A (only if AGENTS/tasks edited).
- [ ] `AGENTS.md` stays below 12288 bytes (if edited).
- [ ] Trilingual READMEs + `SKILL.md` synchronized (if touched).
- [ ] No runtime dependency added; Python 3.9 / Node 16 remain supported.
- [ ] Implementation PR has all nine required contexts green and is merged.
- [ ] Plan/index contain final PR, CI, and merge evidence.

## STOP conditions

Stop and report instead of improvising if:

- distinguishing "unparseable" from a legitimate `{"passed": false}` verdict is
  not possible without changing `run_judge`'s observable output;
- an existing test asserts the exact key set of a parse-error verdict (adding a
  key would break it) — reconcile intentionally, do not silently delete the test;
- fixing the fallback appears to require touching `run_judge`, `builtin_judge`,
  or health scoring;
- `AGENTS.md` cannot stay under 12288 bytes after any consolidation;
- any required CI context is red/pending or a discussion is unresolved.

## Maintenance notes

- Keep the LLM-judge fallback and the external-`--judge-cmd` semantics distinct:
  the LLM path falls back to the deterministic judge on any failure (including
  unparseable output); the operator-supplied `--judge-cmd` path deliberately
  does not fall back and surfaces a bad judge as a fail.
- If a future change makes `run_judge` also want to distinguish parse errors,
  reuse the same `parse_error` marker rather than adding a second mechanism.
- A reviewer should confirm the marker is set ONLY on the non-dict branch and
  that valid verdicts (including bare `{"passed": false}`) never carry it.
