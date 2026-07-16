# Plan 055: Bound every GitHub PR-review network request

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md` unless a reviewer maintains the index separately.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 5d96c95..HEAD -- \
>   scripts/pr_review.py tests/test_pr_review.py \
>   references/maintenance-contract.md plans/055-bound-pr-review-network-time.md \
>   plans/README.md
> ```
>
> If any in-scope file changed, compare the "Current state" excerpts against
> live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: Plans 010 and 036 (DONE)
- **Category**: bug / CI reliability
- **Planned at**: commit `5d96c95`, 2026-07-17
- **Implementation**: DONE — PR #245 (plan) / PR #246 (impl),
  squash-merged to `main` as `2306e06`; all nine required contexts green.

## Why this matters

`ai-harness-doctor review --post` is the network delivery step used by the
shipped GitHub guard and this repository's self-bootstrap guard. Every GraphQL
identity lookup, comment-list page, summary write, and inline-review write calls
`urllib.request.urlopen()` without a timeout. A stalled connect or response can
therefore hold a PR job indefinitely instead of returning a bounded posting
failure and allowing the workflow's explicit failure/soft-failure policy to
run.

The request count is already bounded and endpoints are pinned to
`https://api.github.com`; this plan adds the missing per-request time bound and
clean transport-error handling without changing review ownership, payloads,
HTTP-422 fallback, or dry-run behavior.

## Mechanical reproduction

At `scripts/pr_review.py:849-869`, `_request()` validates the endpoint and then
opens it without a timeout:

```python
def _request(url, data=None, method="GET"):
    ...
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
```

The current `PostReviewTests._run_api()` fake accepts `*args, **kwargs` but does
not record or assert them (`tests/test_pr_review.py:726-762`). A current-HEAD
reproduction patched `urlopen`, exercised a clean summary post, and captured
three calls:

```text
POST https://api.github.com/graphql                    args=() kwargs={}
GET  .../issues/1/comments?per_page=100&page=1         args=() kwargs={}
POST .../issues/1/comments                             args=() kwargs={}
```

All three lack a positional or keyword `timeout`. Inline review writes use the
same `_request()` path and have the same unbounded behavior.

## Current state

### Posting is a deep, bounded-request module except for time

`scripts/pr_review.py` already provides:

- lazy network imports so the default `--dry-run` path stays offline;
- exact host/scheme/userinfo/port validation for every request;
- at most ten comment-list pages;
- authenticated-identity ownership checks before PATCH;
- complete summary delivery before inline comments;
- HTTP 422 inline fallback without duplicate summaries;
- compact HTTP failure rendering through `_GitHubAPIError`.

Do not replace this design or move posting into a third-party client.

### Workflow policy is intentionally different between templates

- `assets/guard/harness-drift.yml` treats review delivery as a required step.
- `.github/workflows/harness-drift.yml` appends `|| echo ...` because this
  repository intentionally tolerates token/API restrictions on fork PRs.

The Python helper must return within a bounded interval; each workflow remains
responsible for deciding whether that non-zero result is fatal. Do not add or
remove `continue-on-error` behavior in this plan.

### Runtime and test conventions

- Python runtime code is Python 3.9+ standard-library only.
- A behavior change to `scripts/*.py` requires a regression test in the same
  commit.
- Tests patch `urllib.request.urlopen`; no real GitHub request belongs in unit
  tests.
- All nine required PR checks must pass before merge.

## Target contract

1. Define one module-level, positive finite default GitHub API request timeout,
   in seconds. Use a conservative fixed value suitable for CI (recommended:
   `15` seconds).
2. Every `urlopen` call made by `post_review()` passes that timeout explicitly.
   The bound covers identity lookup, every comment page, summary POST/PATCH, and
   inline review POST through the shared `_request()` seam.
3. Keep the existing maximum of ten comment pages. This plan bounds each
   request; it does not add retries or a separate global deadline.
4. A timeout or other `urllib` transport failure becomes one concise
   `SystemExit` message identifying the HTTP method and GitHub API operation.
   Do not emit a Python traceback, token, request body, Authorization header, or
   response payload.
5. Existing `_GitHubAPIError` behavior for HTTP responses remains unchanged,
   including:
   - identity HTTP 403/404 falls back to create-only behavior;
   - inline HTTP 422 preserves the already-posted complete summary;
   - every other HTTP failure remains non-zero.
6. The default `--dry-run` path remains fully offline and must not import or
   invoke networking.
7. Review ownership, pagination, payload bodies, marker placement, return
   value, and summary-before-inline ordering remain unchanged.
8. Do not add a new CLI flag or environment variable. A fixed internal timeout
   is the smallest compatible bug fix; configurability needs a separately
   justified public contract.
9. Python 3.9 standard library only; no runtime dependency.

## Design

Add a named constant near the existing review constants:

```python
GITHUB_API_TIMEOUT_SECONDS = 15
```

Keep `_request()` as the single network seam and call:

```python
urllib.request.urlopen(req, timeout=GITHUB_API_TIMEOUT_SECONDS)
```

Handle `urllib.error.HTTPError` first because it is also a `URLError`. Then
handle the transport family (`urllib.error.URLError` and timeout exceptions)
without reproducing headers/body/token. Prefer a small private formatter or a
single concise branch over adding a public exception hierarchy.

The test fake should record the supplied timeout for every request. This proves
the contract across all current operation types without exposing `_request()` as
a public function.

## Commands you will need

| Purpose       | Command                                                                                                                                                                                                | Expected on success                                     |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------- |
| Focused tests | `python3 -m unittest tests.test_pr_review -v`                                                                                                                                                          | all pass                                                |
| Python lint   | `ruff check scripts/pr_review.py tests/test_pr_review.py`                                                                                                                                              | exit 0                                                  |
| Full gate     | `npm run check`                                                                                                                                                                                        | all lint/tests pass                                     |
| Self scan     | `python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json --check-baseline --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts --no-report-file`                | exit 0                                                  |
| Self drift    | `python3 scripts/check_drift.py . --strict`                                                                                                                                                            | 100/100, Grade A                                        |
| Self eval     | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | 38/38, Grade A                                          |
| CLI smoke     | `node bin/cli.js review --report /dev/null`                                                                                                                                                            | exit 0 with a deterministic zero-finding dry-run payload; never a network call |

An empty report is intentionally valid input for the dry-run builder. Success
means it terminates promptly with zero comments/findings and never enters
`post_review()`.

## Scope

**In scope**:

- `scripts/pr_review.py`
- `tests/test_pr_review.py`
- `references/maintenance-contract.md`
- `plans/055-bound-pr-review-network-time.md`
- `plans/README.md`

**Out of scope**:

- Workflow failure/soft-failure policy.
- Changes to `assets/guard/harness-drift.yml` or
  `.github/workflows/harness-drift.yml`.
- Retries, exponential backoff, rate-limit handling, or a global deadline.
- A user-configurable timeout flag or environment variable.
- GitHub Enterprise/API base URL support.
- Refactoring the nested posting helpers into a client class.
- Review payload, marker, ownership, pagination, or inline-placement changes.
- Any npm/Action/release behavior.
- Third-party dependencies.

## Git workflow

- Branch: `fix/055-bound-pr-review-network-time`.
- Commit: `fix(review): bound GitHub API requests`.
- One focused bugfix PR; do not push directly to `main`.
- Wait for all nine required checks before squash merge:
  `drift`, `lint`, Node 16/20/22, Python 3.9/3.10/3.12, and `self-test`.
- This is bugfix-only and therefore patch-release material if released alone.

## Steps

### Step 1: Make the missing bound fail as a test

Extend `PostReviewTests._run_api()` to record the timeout argument supplied to
the patched `urlopen`. Add an assertion covering a post that performs:

- GraphQL identity lookup;
- at least one comment-list GET;
- summary POST or PATCH;
- inline review POST.

Before implementation, assert the new test fails because all calls have no
timeout. After implementation, every captured call must equal the named module
constant.

**Verify**:

```bash
python3 -m unittest \
  tests.test_pr_review.PostReviewTests.test_every_github_request_uses_the_bounded_timeout \
  -v
```

Expected before implementation: RED on missing timeout. Expected after Step 2:
PASS.

### Step 2: Add the shared per-request timeout

Define `GITHUB_API_TIMEOUT_SECONDS` and pass it explicitly from `_request()` to
`urlopen`. Do not add per-caller parameters; every posting operation must use
the same bound automatically.

Keep `HTTPError` handling before the broader transport exception because
`HTTPError` is a `URLError`.

**Verify**:

```bash
python3 -m unittest tests.test_pr_review -v
```

Expected: all posting, dry-run, payload, and fallback tests pass.

### Step 3: Make timeout failure clean and secret-safe

Add a unit test whose mocked `urlopen` raises a timeout on the identity request.
Assert:

- `post_review()` terminates through `SystemExit`;
- the message names a bounded GitHub API request failure;
- the message does not contain the token, Authorization header, request body,
  marker body, or a traceback;
- no summary/review write follows the failed identity request.

Add a parallel `URLError` case only if timeout is not already represented as
that family on all supported Python versions.

**Verify**:

```bash
python3 -m unittest tests.test_pr_review.PostReviewTests -v
```

Expected: all transport, HTTP, pagination, ownership, and fallback cases pass.

### Step 4: Record the maintenance invariant

Add one concise bullet to `references/maintenance-contract.md` under GitHub
guard and feedback: all PR-feedback API calls use the shared finite request
timeout; timeout/transport failures are bounded and leave workflow fatality to
the caller.

Do not edit README translations or `SKILL.md`: no public command or output
shape changes.

### Step 5: Run the gates and review

Run every command in the table. Review along both axes:

- **Standards**: stdlib-only, tests in the same change, no workflow drift, no
  secret-bearing errors.
- **Spec**: every posting operation goes through the timeout, HTTP 422 and
  ownership semantics are unchanged, and dry-run stays offline.

Open one implementation PR and wait for all nine required contexts before
squash merge.

## Test plan

- A multi-operation post proves every operation receives the shared timeout.
- Timeout on the first request produces a concise non-secret `SystemExit`.
- Existing tests continue to cover identity fallback, ten-page bound, malformed
  comment lists, summary upsert, inline delivery, HTTP 422 fallback, and
  non-422 failures.
- Dry-run's no-network test remains unchanged and green.
- Full matrix confirms Python 3.9/3.10/3.12 compatibility.

## Done criteria

- [x] Every `post_review()` GitHub API request passes the same positive finite
      timeout explicitly.
- [x] Timeout/transport failures terminate cleanly without traceback, token,
      headers, payload, or response-body leakage.
- [x] Identity ownership, pagination, summary upsert, inline review, and HTTP
      422 behavior are byte/semantics-compatible.
- [x] `--dry-run` remains network-free.
- [x] No workflow files or public CLI/output schemas change.
- [x] Focused and full tests pass: 799 Python and 47 Node tests.
- [x] Strict drift remains 100/A and self eval remains 38/38.
- [x] All nine PR checks pass and the implementation is squash-merged.

## STOP conditions

Stop and report back if:

- supported Python versions do not share a catchable timeout/transport family;
- adding a bound requires changing workflow failure policy;
- the fix requires retries, a global deadline, or a public configuration knob;
- any request bypasses `_request()` and needs a broader posting refactor;
- handling the timeout would expose credentials or response data;
- existing ownership, pagination, or HTTP-422 tests regress;
- any required CI context is red or pending at merge time.

## Maintenance notes

- Keep all GitHub posting through `_request()` so endpoint validation, timeout,
  headers, and transport errors cannot diverge.
- The timeout is per request. With identity + ten comment pages + summary +
  inline review, total wall time remains a bounded multiple; do not describe it
  as one global deadline.
- Do not add retries casually: summary POST is not automatically idempotent
  when identity lookup is unavailable, and retry policy needs explicit
  write-safety/rate-limit design.
- Workflow callers own whether a bounded posting error fails or soft-fails the
  job.
