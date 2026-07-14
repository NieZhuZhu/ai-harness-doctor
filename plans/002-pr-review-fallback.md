# Plan 002: Preserve PR feedback when inline review locations are invalid

> **Executor instructions**: Follow this plan exactly, verify each step, and
> stop on any STOP condition. Touch only in-scope files. Update
> `plans/README.md` when complete.
>
> **Drift check (run first)**:
> `git diff --stat 7121ce6..HEAD -- scripts/pr_review.py tests/test_pr_review.py .github/workflows/harness-drift.yml assets/guard/harness-drift.yml README.md README.zh-CN.md README.ja.md SKILL.md`

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: MED
- **Depends on**: none
- **Category**: bug / DX
- **Planned at**: commit `7121ce6`, 2026-07-14

## Why this matters

GitHub's create-review endpoint rejects an entire review when any inline
comment points at a line outside the PR diff. `pr_review.py` only checks that a
finding has a path and numeric line; a valid source line is not necessarily a
valid review line. On HTTP 422 it exits, so a drift failure can lose all
automated repair guidance. The workflow also supplies `github.sha`, which can be
the pull-request merge ref rather than the PR head commit. Feedback must degrade
to a summary comment rather than disappear.

## Current state

- `scripts/pr_review.py:249-314` promotes every finding with path + line to an
  inline comment.
- `scripts/pr_review.py:461-501` posts one review and turns every HTTP error,
  including 422, into `SystemExit`; there is no retry/fallback.
- `tests/test_pr_review.py:297-375` covers successful review posting and the
  no-inline issue-comment path, but not a rejected inline review.
- `.github/workflows/harness-drift.yml:56-69` and
  `assets/guard/harness-drift.yml:47-59` pass `github.sha`.
- For PR #103, GitHub reported head SHA
  `3b653ad99d5898358c0254539cedda18b78d6e70`, while the workflow log passed a
  different SHA to `--commit`, confirming the event SHA is not the correct
  stable head anchor.
- The repo's fallback pattern is already present: when there are no inline
  comments, `post_review` posts the complete summary to the issue-comments
  endpoint.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Targeted tests | `python3 -m unittest tests.test_pr_review -v` | all pass |
| Python lint | `ruff check scripts/pr_review.py tests/test_pr_review.py` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | OK |
| Full gate | `npm run check` | exit 0 |
| Self drift | `python3 scripts/check_drift.py .` | grade A |

## Scope

**In scope**:

- `scripts/pr_review.py`
- `tests/test_pr_review.py`
- `.github/workflows/harness-drift.yml`
- `assets/guard/harness-drift.yml`
- `README.md`
- `README.zh-CN.md`
- `README.ja.md`
- `SKILL.md`

**Out of scope**:

- Querying the GitHub diff before building comments; avoid an extra API and
  pagination complexity.
- Deduplicating or editing earlier bot comments.
- Changing review event from `COMMENT`.
- Making token/API failures block the drift gate.

## Git workflow

- Branch: `fix/pr-review-summary-fallback`
- Commit: `fix(review): fall back when inline comments fail`
- One focused PR, English description, squash merge.

## Steps

### Step 1: Add failing HTTP 422 tests

Extend `PostReviewTests` so mocked `urlopen`:

1. rejects the reviews endpoint with an HTTP 422 response;
2. then accepts the issue-comments endpoint;
3. asserts the fallback body retains the full summary/findings;
4. asserts only these two requests occur;
5. proves non-422 errors still surface rather than being silently hidden.

The production function should return the successful fallback response and the
CLI should print its URL.

**Verify**: the new fallback test fails before implementation.

### Step 2: Implement a narrow 422 fallback

Refactor the request helper enough to distinguish status 422 without losing the
existing detailed error for other statuses. When posting inline comments:

- first attempt the review endpoint;
- only if that request is rejected with 422, post the already self-contained
  summary body to `/issues/{pr}/comments`;
- do not retry inline comments individually;
- do not catch authorization, rate-limit, or server errors as success.

The summary already contains every finding's full detail, so no additional body
format is needed.

**Verify**: all `tests.test_pr_review` tests pass.

### Step 3: Anchor reviews to the PR head SHA

Change both the self-hosted workflow and shipped guard template from
`${{ github.sha }}` to `${{ github.event.pull_request.head.sha }}` for
`--commit`. Update nearby comments to explain why.

Add a static regression assertion in an appropriate existing test (prefer
`tests/test_action_metadata.py` or `tests/test_cli.py`) that both workflow
copies use the head SHA and no PR-review command uses `github.sha`.

**Verify**: targeted workflow/template tests pass.

### Step 4: Document graceful degradation

Update the synchronized READMEs and `SKILL.md`: inline feedback is attempted for
located findings; if GitHub rejects line placement, the tool posts the complete
summary instead. Keep the wording honest: permissions/network errors can still
prevent posting.

**Verify**: docs sync passes.

## Test plan

- Review endpoint succeeds: unchanged inline payload.
- Review endpoint 422: one summary issue comment succeeds.
- Review endpoint 403/500: error remains visible.
- No inline comments: existing direct summary path unchanged.
- Workflow commit anchor equals PR head SHA in both template and self-copy.

## Done criteria

- [ ] A single invalid inline location cannot discard all PR feedback.
- [ ] Non-422 GitHub failures remain errors.
- [ ] Both workflows use `github.event.pull_request.head.sha`.
- [ ] Targeted and full tests pass.
- [ ] Drift remains grade A.
- [ ] Only in-scope files and plan status changed.

## STOP conditions

- GitHub's mocked/real 422 response cannot be distinguished without changing
  the public CLI contract.
- Fallback would require posting unsanitized finding content.
- Workflow event context lacks `pull_request.head.sha` on the guarded branch.

## Maintenance notes

The summary must remain self-contained because it is the recovery path for all
inline-placement failures. Any future compact-summary refactor must retain
enough detail to repair every finding without inline threads.
