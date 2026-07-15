# Plan 033: Derive eval health only from validated stored result records

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 777f962..HEAD -- scripts/eval_run.py tests/test_eval_run.py tests/test_cli.py README.md README.zh-CN.md README.ja.md SKILL.md benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json benchmark/self-eval/results-after-graded.json benchmark/self-eval/README.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: correctness / security / efficacy / tests / docs
- **Planned at**: commit `777f962`, 2026-07-16

## Why this matters

`eval --score` is a CI gate, but it accepts the stored `health` object as
authoritative whenever that object contains `score`. A result whose only task
failed can therefore carry a forged `100/A` health block, pass
`--fail-under 80`, append a false baseline snapshot, and make the repository's
self-eval gate green. Malformed result records are similarly inconsistent:
some shapes pass through the trusted health shortcut, while the same records
without `health` raise a raw traceback.

Stored task results are untrusted evidence, not a cached verdict. Every offline
consumer must validate the producer-compatible result shape, derive health from
the task records, and reject any persisted health fields that contradict that
derivation. This is intentionally separate from Plan 030, which validates task
definitions before paid execution; Plan 030 explicitly deferred stored result
schema validation.

## Current state

- `scripts/eval_run.py:973-1006` flattens only single-run and matrix records.
  It does not validate record containers or record fields:

  ```python
  def _collect_records(data):
      if not isinstance(data, dict):
          return []
      if isinstance(data.get("agents"), dict):
          records = []
          for agent in data["agents"].values():
              if isinstance(agent, dict):
                  records.extend(agent.get("tasks", []) or [])
          return records
      return data.get("tasks", []) or []

  def compute_health(data):
      records = _collect_records(data)
      total = len(records)
      passed = sum(1 for r in records if r.get("passed"))
      timed_out = sum(1 for r in records if r.get("timed_out"))
      ...
  ```

  A string `tasks` value is iterated as characters and fails with
  `AttributeError: 'str' object has no attribute 'get'`.

- `score_report()` at `scripts/eval_run.py:1808-1830` trusts a stored score:

  ```python
  health = data.get("health") if isinstance(data, dict) else None
  if not isinstance(health, dict) or "score" not in health:
      health = compute_health(data)
  ```

  The audit wrote a result with one record
  `{"id":"failed","passed":false,"timed_out":false}` and:

  ```json
  {
    "score": 100,
    "grade": "A",
    "passed": 1,
    "total": 1,
    "timed_out": 0,
    "pass_rate": 1
  }
  ```

  `python3 scripts/eval_run.py --score forged.json --fail-under 80 --json`
  exited `0` and printed the forged health. Replacing the task array with
  `"tasks":"not-a-list"` still exited `0` through the same shortcut.

- Multi-round files have `round_results` and a top-level derived `health`.
  `_collect_records()` does not understand that shape, so simply deleting the
  shortcut would turn valid multi-round scores into `0/F`. Each round also
  stores its own `health`, and `_round_health_score()` currently trusts it.

- Matrix files store task arrays under `agents.<name>.tasks`; single-run and
  regrade files use top-level `tasks`. Duplicate IDs are valid across agents or
  rounds but not inside one logical task array.

- `stats_report()` recomputes overall health, but
  `summarize_rounds()` consumes trusted per-round scores. `compare()` and
  `regrade()` index stored records directly and can raise on malformed
  containers. Trend files are a separate append-only baseline schema, not eval
  result files.

- `tests/test_eval_run.py:925-1008` covers normal health computation and score
  output. Evidence tests use historical health blocks that may omit newer
  additive fields such as `pass_rate`, so compatibility must not require every
  health key to be present. There are no forged-health, malformed-result,
  duplicate-record, or offline-mode parity tests.

## Target contract

1. Add one result-file loader/validator used by `--score`, `--stats`,
   `--compare`, and `--regrade`. JSON/UTF-8/schema failures produce a concise
   `result error: ...` and exit `2`, without a traceback, record content,
   answer/stdout, absolute host path, or secret-shaped value.
2. Recognize exactly the producer-compatible result families:
   - single/regraded result: top-level `tasks`;
   - multi-round result: top-level `round_results`, each with `tasks`;
   - matrix result: top-level `agents`, each agent with `tasks`.
   Reject ambiguous files that define more than one primary family.
3. Every logical task container must be a list of objects. Each record requires
   a non-empty string `id` and a boolean `passed`; optional `timed_out` must be
   boolean. Preserve all other producer fields without interpreting answer,
   stdout, usage, duration, or judge content.
4. IDs must be unique inside one task array. The same ID may repeat in another
   round or agent because those arrays are independent.
5. Derive canonical health from validated records for every family:
   - single: its task array;
   - multi-round top level: all task-runs across all rounds;
   - matrix: all task records across all agents;
   - per-round stats: each round's own records.
6. Never use a persisted `health` value as the score source. If a health object
   exists, every canonical key it contains (`score`, `grade`, `passed`,
   `total`, `timed_out`, `pass_rate`) must equal the newly derived value.
   Historical blocks may omit additive keys; unknown extra keys are ignored.
   A non-object health field or any contradictory present key is a result error.
7. Missing health remains valid and is derived. Empty but structurally valid
   task collections retain the current `0/F` result.
8. Strict evidence freshness remains ordered before threshold/baseline effects,
   but only after result structure is known safe. For a valid result, stale
   evidence still exits `7`; low health still exits `5`; regression still exits
   `6` under the existing precedence.
9. Invalid or contradictory results must not print a health verdict, append a
   baseline snapshot, mutate a regrade output, write a comparison report, or
   run a judge/runner.
10. Existing valid result JSON written by single, multi-round, matrix, and
    regrade modes remains byte-compatible. This plan validates reads; it does
    not introduce a required result `schemaVersion`.
11. `--trend` baseline history is out of scope and retains its separate schema.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused eval tests | `python3 -m unittest discover -s tests -p 'test_eval_run.py' -v` | all pass |
| CLI forwarding tests | `python3 -m unittest discover -s tests -p 'test_cli.py' -v` | all pass |
| Python lint | `ruff check scripts/eval_run.py tests/test_eval_run.py tests/test_cli.py` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | `OK` |
| Full gate | `npm run check` | exit 0 |
| Self eval | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0, grade A |
| Self scan | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0, grade A |

## Scope

**In scope**:

- `scripts/eval_run.py`
- `tests/test_eval_run.py`
- `tests/test_cli.py` only if packaged exit/error forwarding needs coverage
- synchronized `README.md`, `README.zh-CN.md`, `README.ja.md`
- `SKILL.md`
- `benchmark/self-eval/` only if recomputation exposes a real committed
  inconsistency
- `plans/README.md`

**Out of scope**:

- Changing task-definition preflight from Plan 030.
- Adding a required result schema version or JSON Schema dependency.
- Trusting an external signature or remote attestation.
- Changing runner, judge, grading, evidence fingerprint, or generated-task
  semantics.
- Validating arbitrary answer/stdout/judge/usage payload contents.
- Changing baseline-history (`--trend`) schema.
- Repairing or rewriting malformed result files automatically.
- General `eval_run.py` refactoring based on file size.
- Updating `AGENTS.md`; the batch completion PR owns final durable invariants.

## Git workflow

- Branch: `fix/eval-result-integrity`
- Commit: `fix(eval): derive health from validated results`
- One focused backward-compatible correctness/security PR.
- Do not push directly to `main`.
- Wait for all nine required contexts, then squash-merge and delete the branch.
- Patch-level unless producer-compatible committed results cannot satisfy the
  validator; that is a STOP condition rather than permission to break them.

## Steps

### Step 1: Add failing result-integrity characterizations

Create table-driven tests for:

- forged stored health over failed records;
- malformed `tasks`, `round_results`, `agents`, agent, and record containers;
- missing/empty/wrong-type `id`;
- non-boolean `passed` / `timed_out`;
- duplicate IDs inside one array versus allowed repeats across rounds/agents;
- ambiguous primary result families;
- malformed/non-object/partially historical/contradictory health blocks;
- invalid JSON and non-object roots.

For the load-bearing CLI regression, run the exact forged result through
`--score --fail-under 80 --json` and assert exit `2`, no health JSON on stdout,
no traceback, and a metadata-only `result error`. Repeat with
`"tasks":"not-a-list"` both with and without a forged health block.

**Verify**: the forged-health cases fail against `777f962` because they exit
`0`; the malformed-no-health case exposes a traceback.

### Step 2: Implement one pure stored-result validator

Add a dedicated `ResultFileError` and pure helpers that:

- classify the single/multi/matrix family;
- validate each logical task array and record;
- return deterministic flattened records plus per-round/per-agent views;
- derive health with the existing grade/rounding rules;
- compare only canonical persisted health keys that are actually present.

Do not reuse task-definition validation: result records and task definitions
are different schemas. Do not inspect untrusted answer/stdout content for error
messages.

**Verify**: pure validator tests pass for every generated family and historical
health blocks with omitted additive fields.

### Step 3: Route score and stats through canonical derived health

Make `score_report()` load a validated result and always use derived health.
For multi-round input, flatten all round records rather than falling through
the old single/matrix collector. Make `_round_health_score()` and
`summarize_rounds()` use validated/derived round health, never a stored score.

Validate before `verify_current_evidence()`, then retain valid-result exit
precedence: stale evidence `7`, regression `6`, low threshold `5`. Ensure
`apply_baseline()` receives only derived health.

**Verify**:

- forged/malformed score and stats fail with exit `2`;
- valid single/multi/matrix score and stats return their record-derived value;
- invalid input cannot append to a baseline history.

### Step 4: Make compare and regrade fail closed on malformed records

Use the shared loader with mode-specific accepted families:

- `compare` accepts producer-compatible single/regraded task results and rejects
  malformed or ambiguous inputs before writing its Markdown report;
- `regrade` validates the stored single-result records before mutating any
  record or output, while task definitions still go through Plan 030's loader.

If current documented behavior requires comparing matrix or multi-round files,
stop and expand the contract explicitly rather than silently flattening them.

**Verify**: malformed compare/regrade inputs produce no output mutation and no
traceback; existing valid tests remain green.

### Step 5: Lock producer/consumer parity

Generate deterministic single, two-round, matrix, and regraded files through
the live producer paths. Feed each file back into the relevant offline
consumers and assert:

- record-derived health equals the persisted health;
- every present persisted canonical field agrees;
- serialized producer files are unchanged;
- duplicate IDs remain scoped per round/agent;
- evidence-stamped and legacy unstamped valid results remain readable.

Add one test that tampers only with stored health after generation; the
original must score successfully and the tampered copy must fail.

**Verify**: the focused suite covers every result producer and offline
consumer without network/model calls.

### Step 6: Document result trust and refresh self evidence only if needed

Update all three READMEs and `SKILL.md`: stored health is a consistency cache,
not authority; offline consumers validate result records, derive health, and
reject contradictions before thresholds, regression snapshots, or writes.
Document the accepted single/multi/matrix families and concise error boundary.

Run the committed self-eval score gate. If validation exposes a real mismatch,
investigate the producer and regenerate artifacts honestly; never hand-edit
health merely to satisfy the gate. If it is already consistent, leave benchmark
artifacts untouched.

**Verify**: docs sync, focused/full tests, self-eval, self scan, and strict
drift.

## Test plan

- Pure result-family and record-schema tables.
- Forged health and partial historical health compatibility.
- Single/multi/matrix producer→consumer round trips.
- Per-round health/stats recomputation.
- Duplicate ID boundaries.
- Score/stats/compare/regrade failure parity.
- Invalid-result no-output/no-baseline-mutation assertions.
- Strict-evidence and threshold/regression exit precedence.
- Sanitized diagnostics with no traceback or record content.

## Done criteria

- [ ] No offline result consumer treats stored health as authoritative.
- [ ] Forged health over failed records cannot pass `--fail-under`.
- [ ] Single, multi-round, and matrix records derive correct canonical health.
- [ ] Contradictory present health fields fail closed; omitted historical fields
      remain compatible.
- [ ] Malformed containers/records produce `result error` with exit `2`.
- [ ] Invalid results cannot mutate outputs or baseline history.
- [ ] Valid stale evidence still exits `7`; low derived health still exits `5`.
- [ ] Current producer JSON remains byte-compatible.
- [ ] Trilingual docs and `SKILL.md` describe the trust boundary.
- [ ] Full local and nine required CI gates pass.

## STOP conditions

Stop and report back if:

- A committed or documented producer-compatible result violates the proposed
  record contract.
- Correct health requires interpreting answer text, judge prose, or another
  untrusted free-form payload.
- Compatibility requires continuing to trust a contradictory stored score.
- Compare is documented to flatten matrix/multi-round input in a way not
  represented above.
- Fixing the bug requires a breaking required `schemaVersion`.
- Verification fails twice after a reasonable scoped fix.

## Maintenance notes

- Stored results are inputs at every offline boundary, even when this tool
  originally produced them.
- Any new result family must define its logical task arrays and canonical
  health derivation in the shared validator before an offline mode accepts it.
- Persisted health may accelerate human inspection but can never authorize a
  threshold, regression snapshot, or CI success without record recomputation.
- Keep task-definition and result-record validation separate; they protect
  different trust boundaries.
