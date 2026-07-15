# Plan 036: Keep one current AI Harness Doctor summary per pull request

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md` — unless a reviewer dispatched you and told you they
> maintain the index.
>
> **Drift check (run first)**:
> `git diff --stat 43366d9..HEAD -- scripts/pr_review.py tests/test_pr_review.py README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md benchmark/self-eval/results-after-graded.json`
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against the live code before proceeding; on a
> mismatch, treat it as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: bug
- **Planned at**: commit `43366d9`, 2026-07-16

## Why this matters

The public `review --post` path gives every summary a stable
`<!-- ai-harness-doctor:pr-review -->` marker, but it never reads or updates a
previous marker comment. Every PR push therefore creates another complete
summary. PR #189 reproduced the production failure: its two head commits left
two byte-identical clean summaries from `github-actions[bot]`. On longer PRs,
obsolete clean/failing summaries obscure the current harness verdict and make
the final review less trustworthy.

Make the marker an ownership-safe upsert key: every run must leave one current
general summary comment owned by the authenticated poster, while located
findings can still be delivered inline. The summary is the complete durable
state. A rejected inline placement must not create a second summary, and
permission/rate-limit/network/server failures must remain visible rather than
being treated as success.

## Current state

- `scripts/pr_review.py:34-36` defines a stable marker but only describes a
  possible future supersede:

  ```python
  # Identifying marker embedded in every summary/general comment body so re-runs
  # can recognize (and, if desired, supersede) a prior ai-harness-doctor review.
  MARKER = "<!-- ai-harness-doctor:pr-review -->"
  ```

- `scripts/pr_review.py:867-894` always performs a POST. With inline findings it
  creates one review whose body contains the summary; without inline findings
  it creates one issue comment. HTTP 422 creates another issue comment:

  ```python
  if comments:
      url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews"
      ...
      return _request(url, data, "POST")
      ...
      return _request(url, {"body": payload.get("body", "")}, "POST")
  ...
  return _request(url, {"body": payload.get("body", "")}, "POST")
  ```

- `tests/test_pr_review.py:695-890` covers direct review POST, summary POST,
  inline 422 fallback, and non-422 failure. It has no two-run/upsert,
  pagination, ownership, or stale-summary replacement coverage.

- `README.md:177` and `SKILL.md:257` promise a stable marker and complete final
  summary, but not a single-current-comment lifecycle.

- Live production evidence from PR #189:

  ```text
  issue comment 4986156908, github-actions[bot], 2026-07-15T23:11:16Z
  issue comment 4986172262, github-actions[bot], 2026-07-15T23:13:52Z
  ```

  Both bodies are byte-identical and begin with `MARKER`. Each was created by
  the GitHub Actions app after a different head commit.

- Follow the existing stdlib-only `_request` wrapper and mocked
  `urllib.request.urlopen` pattern in `tests/test_pr_review.py`. Do not add an
  HTTP or GitHub SDK dependency.

## Target contract

1. `--dry-run` stays pure/offline and byte-compatible. It does not list or
   update comments.
2. `--post` always publishes the complete `payload["body"]` as one general
   issue comment lifecycle:
   - list PR issue comments with bounded pagination;
   - find marker comments owned by the current authenticated poster;
   - update the newest owned marker comment with PATCH when present;
   - otherwise create one with POST.
3. Never edit a marker comment from another user/app. Determine the current
   poster identity from authenticated GitHub API metadata. The GitHub Actions
   installation-token path and ordinary user/PAT path must both be covered. If
   identity cannot be established safely, create a new marker comment rather
   than editing an unproven owner.
4. If legacy duplicate marker comments owned by the same poster exist, update
   only the newest. Do not delete, hide, minimize, or edit older comments:
   cleanup is destructive and is outside this plan.
5. Located findings remain inline:
   - upsert the complete summary first;
   - then POST a review carrying inline comments and no second complete marker
     summary body;
   - if inline placement returns 422, return the already-upserted complete
     summary as successful delivery without another POST;
   - non-422 inline errors still fail visibly.
6. A clean run has no inline review and only upserts the summary.
7. Pagination must be bounded and deterministic. Follow GitHub `Link` headers
   or an explicit capped page loop; do not silently inspect only the first 30
   comments. Reject cross-host pagination links.
8. All requests retain authorization, API-version, content-type, accept, and
   user-agent headers. API error bodies remain visible through
   `_GitHubAPIError`.
9. The returned response and CLI message must identify the durable summary
   URL. Do not claim a duplicate inline review URL as the current summary.
10. Update public English, Simplified Chinese, and Japanese documentation in
    lockstep. Keep fenced code byte-identical and table/link counts aligned.
11. Record the durable invariant concisely in `AGENTS.md`, refresh the
    evidence-bound self-eval artifact honestly, and keep `AGENTS.md` below the
    repository's strict context-size threshold.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused tests | `python3 -m unittest discover -s tests -p 'test_pr_review.py' -v` | all pass |
| Docs sync | `npm run lint:docs` | headings/code/tables/links aligned |
| Full gate | `npm run check` | all Python and Node tests pass |
| CLI smoke | `node --check bin/cli.js && node bin/cli.js help` | exit 0 |
| Self scan | `python3 scripts/scan.py . --fail-on-security` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | 100/100, grade A |
| Eval regrade | `python3 scripts/eval_run.py --regrade benchmark/self-eval/results-after.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md -o benchmark/self-eval/results-after-graded.json` | writes graded result |
| Eval gate | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | 33/33, grade A |

## Scope

**In scope**:

- `scripts/pr_review.py`
- `tests/test_pr_review.py`
- `README.md`
- `README.zh-CN.md`
- `README.ja.md`
- `SKILL.md`
- `AGENTS.md`
- `benchmark/self-eval/results-after-graded.json`
- `plans/README.md` (status/evidence only)
- `plans/036-upsert-pr-review-summary.md` (status/evidence only)

**Out of scope**:

- `.github/workflows/harness-drift.yml` and guard templates: they already call
  the public `review --post` path and should inherit the behavior.
- Deleting/minimizing historical duplicate comments.
- Reusing or deleting old inline review comments across different head SHAs.
- Changing finding collection, severity, Markdown detail, Action inputs, or
  scan/drift exit codes.
- GitLab/Codebase provider-specific commenting.
- Adding runtime dependencies or changing authentication secrets/permissions.

## Git workflow

- Branch: `fix/036-pr-review-summary-upsert`
- Commit message: `fix(review): upsert the PR summary comment`
- Land through one English PR. Do not push directly to `main`.
- Required before merge: drift, lint, Node 16/20/22, self-test, and Python
  3.9/3.10/3.12 all successful. Admin bypass may resolve only the
  sole-maintainer approval deadlock after every check is green.

## Steps

### Step 1: Add a failing two-run lifecycle harness

Extend `PostReviewTests` with a stateful fake GitHub API that simulates:

1. clean first run: list has no owned marker, POST one summary;
2. clean second run: list returns the prior owned marker, PATCH it, no second
   POST;
3. failing-to-clean transition: the same comment ID receives the new complete
   body;
4. foreign marker plus owned marker: only the owned marker is PATCHed;
5. legacy duplicates: newest owned marker is PATCHed; older comments are
   untouched;
6. marker on a later page: pagination finds it;
7. unsafe cross-host `Link`: stop following it and do not send the token;
8. inline success: summary upsert plus one inline review, with no complete
   marker body duplicated in the review;
9. inline 422: summary upsert only, no fallback summary POST;
10. inline 403/429/5xx: error remains fatal after the summary update.

Assert methods, endpoints, request order, bodies, ownership selection, and
headers. Tests must fail against `43366d9`.

**Verify**: focused tests fail specifically because `post_review` only POSTs
and never lists/PATCHes a summary.

### Step 2: Implement an ownership-safe paginated comment upsert

Refactor the nested request helper only as much as necessary to support:

- GET without a JSON request body;
- response headers for bounded pagination;
- PATCH/POST JSON bodies;
- the same error conversion for all methods.

Add small private helpers for authenticated poster identity, safe next-page
selection, owned-marker selection, and summary upsert. Keep all network imports
inside `post_review` or its post-only helpers so dry-run/import remains offline.
Use `urllib.parse` for URL validation; send the bearer token only to
`api.github.com`.

When identity is unavailable, fail safe by POSTing a new marker rather than
PATCHing an unproven comment. Never select a comment merely because its body
contains the public marker.

**Verify**: lifecycle/pagination/ownership tests pass; dry-run test still proves
no network call.

### Step 3: Separate durable summary delivery from inline annotations

Upsert the complete general summary before attempting inline placement. For
located findings, submit the review comments with an empty or short marker-free
body that does not duplicate the complete summary. If GitHub returns 422,
return the summary response because the complete repair guidance is already
durably present. Preserve fatal behavior for every other inline API error.

Do not convert all findings to summary-only; inline annotations are a public
product feature and must remain covered.

**Verify**: existing inline body/detail assertions and the new request-order /
no-duplicate tests pass.

### Step 4: Document the single-current-summary contract

Update the corresponding prose in all three READMEs and `SKILL.md`: reruns
upsert one owned marker summary, inline findings remain annotations, and 422
does not duplicate the summary. Do not change code blocks or unrelated product
claims.

Add one concise `AGENTS.md` invariant near the existing PR-review/report
delivery rule. Regrade the current manual-protocol result so the evidence hash
matches; do not change answers or claim a fresh external-model benchmark.

**Verify**: docs sync, 33/33 strict evidence gate, `AGENTS.md` size, self scan,
and strict drift all pass.

### Step 5: Run full gates and capture real PR evidence

Run every command above. Open the PR and push one harmless follow-up commit only
if needed to exercise a second workflow run. Verify through the GitHub API that
the PR has exactly one owned marker summary comment and that its `updated_at`
advances instead of a second marker appearing. Do not manually delete comments
to manufacture the result.

**Verify**:

```bash
gh api repos/NieZhuZhu/ai-harness-doctor/issues/<PR>/comments --paginate \
  --jq '[.[] | select(.body | contains("<!-- ai-harness-doctor:pr-review -->"))]'
```

Expected: one current bot-owned marker summary after at least two workflow
executions.

## Test plan

- Model after `PostReviewTests`' mocked `urllib.request.urlopen` seam.
- Cover clean and finding reports; first create and subsequent update.
- Cover ownership, pagination, duplicate legacy markers, and unsafe next links.
- Cover inline POST success, 422 recovery, and non-422 failure.
- Preserve dry-run no-network coverage.
- Run the real PR API read-back after two workflow executions.

## Done criteria

- [ ] A second clean post PATCHes the existing owned marker comment.
- [ ] Clean/finding transitions leave one current summary comment.
- [ ] Foreign marker comments are never updated.
- [ ] Pagination is bounded and never forwards credentials cross-host.
- [ ] Inline findings remain inline.
- [ ] Inline 422 creates no duplicate summary; other errors remain fatal.
- [ ] Dry-run stays offline and output-compatible.
- [ ] Trilingual docs and `SKILL.md` describe the lifecycle truthfully.
- [ ] `AGENTS.md` records the invariant, stays below threshold, and self-eval is
      current at 33/33.
- [ ] Full local gate and all nine required PR contexts pass.
- [ ] Real PR read-back shows one owned marker after at least two runs.

## STOP conditions

Stop and report instead of improvising if:

- GitHub's API does not expose enough authenticated identity to distinguish an
  owned marker from a foreign marker without trusting attacker-controlled body
  text.
- Updating an owned issue comment requires broader workflow permissions than
  current `pull-requests: write`.
- A complete summary cannot be upserted before inline review creation without
  losing required inline findings.
- Supporting pagination would require forwarding the token away from
  `api.github.com`.
- The change requires deleting/minimizing historical comments or changing
  branch protection/workflow permissions.
- Any in-scope contract changed since `43366d9` invalidates the excerpts.

## Maintenance notes

- `MARKER` is public and forgeable; ownership, not marker text alone, authorizes
  PATCH.
- The durable issue comment is the current state. Inline comments are
  commit/diff annotations and may remain historical across head SHAs.
- If GitHub changes pagination or Actions token identity metadata, fail safe by
  creating a new summary rather than editing an unproven owner.
- Reviewers should inspect request ordering, host validation, and 422 behavior
  more closely than Markdown wording.
