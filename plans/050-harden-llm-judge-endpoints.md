# Plan 050: Keep LLM judge API keys on trusted endpoints

> **Drift check**:
>
> ```bash
> git diff --stat 60dd32f..HEAD -- \
>   scripts/eval_run.py tests/test_eval_run.py \
>   README.md README.zh-CN.md README.ja.md README.es.md README.ko.md \
>   README.pt-BR.md README.fr.md SKILL.md AGENTS.md
> ```

## Status

- **Priority**: P0
- **Effort**: M
- **Risk**: MED
- **Depends on**: Plan 043 (DONE)
- **Category**: security / credential transport
- **Planned at**: commit `60dd32f`, 2026-07-16
- **Implementation**: DONE — PR #228 (plan) / PR #229 (impl), squash-merged to
  `main` as `2f9784d`; all nine required contexts green.

## Why this matters

Real-LLM judging sends `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` to an
environment-configurable base URL through Python stdlib `urllib`.

The current code validates neither scheme nor origin and uses the default
redirect handler. Python's handler copies every request header except content
headers into the redirected request. A cross-origin 302 therefore forwards
`Authorization` and `x-api-key` to the redirect target.

An accidental `http://` endpoint also sends the real key in clear text. This is
a credential-boundary defect, not an SSRF finding: custom compatible endpoints
are intentional, but key transport must remain explicit and secure.

## Mechanical reproduction

Use two local generated HTTP servers:

1. Server A receives the authenticated POST and returns a 302 to Server B.
2. Server B records request headers and returns JSON.
3. Call `_http_post_json` with generated sentinel headers.

Observed:

```text
Server B Authorization: Bearer generated-sentinel
Server B x-api-key: generated-sentinel-2
```

The default `urllib.request.HTTPRedirectHandler.redirect_request` removes only
`Content-Length` and `Content-Type`; auth headers survive cross-origin redirects.

## Current state

`scripts/eval_run.py:1487` uses:

```python
req = urllib.request.Request(url, data=body, headers=merged, method="POST")
with urllib.request.urlopen(req, timeout=timeout) as resp:
    return json.loads(resp.read().decode("utf-8"))
```

`OPENAI_BASE_URL` and `ANTHROPIC_BASE_URL` are concatenated directly with API
paths. The surrounding `llm_judge` catches network/parse exceptions and falls
back to the deterministic judge, so validation can reuse that failure contract.

## Target contract

1. Authenticated judge endpoints must be HTTPS.
2. Explicit loopback development endpoints may use HTTP only for:
   - `localhost`;
   - `127.0.0.0/8`;
   - `::1`.
   This supports local OpenAI-compatible servers without allowing remote clear
   text.
3. Reject embedded username/password, fragments, malformed hosts, and unsupported
   schemes. Define whether query strings are allowed; recommended: reject them
   because the code appends fixed API paths.
4. Authenticated POST requests do not follow redirects. Treat any 3xx as a
   judge failure and fall back.
5. Error messages never include headers, API keys, payload answer/rubric, or a
   URL containing userinfo.
6. Default official endpoints and valid HTTPS-compatible endpoints keep working.
7. No third-party dependency; Python 3.9 standard library only.

## Design

### Endpoint validator

Add a pure helper based on `urllib.parse.urlsplit` and `ipaddress`:

- normalize/remove trailing slash;
- require absolute URL and hostname;
- allow `https`;
- allow `http` only for loopback;
- reject `username`, `password`, `fragment`, and query;
- return the safe normalized base.

Validation happens before headers are built/sent.

### No-redirect opener

Use a custom `HTTPRedirectHandler` whose `redirect_request` always raises an
`HTTPError`, or an equivalent opener installed only for `_http_post_json`.
Never strip-and-follow: judge API paths are expected to be final endpoints.

The existing broad `llm_judge` catch converts the safe exception to `None`, so
`grade_answer` falls back to the built-in judge.

## Scope

**In scope**:

- `scripts/eval_run.py`
- `tests/test_eval_run.py`
- all seven READMEs and `SKILL.md`
- plan/index updates

**Out of scope**:

- Removing custom base URLs.
- Certificate pinning or custom CA configuration.
- Proxy environment behavior.
- Retries or provider SDKs.
- Changing judge fallback or grading semantics.

## Steps

### Step 1: Add deterministic endpoint tests

Test:

- official HTTPS endpoints accepted;
- custom HTTPS endpoint accepted and normalized;
- remote HTTP rejected before `_http_post_json`;
- loopback HTTP accepted for localhost, 127.x, and `::1`;
- userinfo, query, fragment, relative URL, unsupported scheme rejected;
- diagnostics contain no generated key.

### Step 2: Add redirect integration test

Run local redirect and sink servers with generated sentinel headers. After the
fix:

- `_http_post_json` raises on the 302;
- sink receives no request;
- no auth sentinel appears in stderr.

Also prove a direct local loopback HTTP response still works.

### Step 3: Implement validation and no-redirect transport

Keep `_http_post_json` stdlib-only and testable. Apply the validator to both
OpenAI and Anthropic branches before auth headers are created.

### Step 4: Document the endpoint contract

In all seven READMEs and `SKILL.md`, document HTTPS-only remote judge endpoints,
the loopback HTTP exception, no redirects, and deterministic fallback.

### Step 5: Gates and merge

```bash
python3 -m unittest discover -s tests -p 'test_eval_run.py' -v
npm run check
python3 scripts/check_readme_sync.py
python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json \
  --check-baseline --fail-on-security --fail-on-gaps --fail-on-semantic \
  --fail-on-conflicts
python3 scripts/check_drift.py . --strict
```

Open one implementation PR, wait for all nine contexts, then squash-merge. This
is a backward-compatible security **patch**. Remote `http://` custom endpoints
will intentionally fail safe; local loopback remains supported.

## Done criteria

- [ ] Remote HTTP judge base URL sends no request.
- [ ] Cross-origin and same-origin redirects send no follow-up request.
- [ ] Generated auth sentinels never reach redirect sink or diagnostics.
- [ ] Loopback HTTP and ordinary HTTPS endpoints still work.
- [ ] Both OpenAI and Anthropic branches use the same validator.
- [ ] Seven READMEs and `SKILL.md` document the boundary.
- [ ] Full local and nine-context CI gates pass; PR merged.

## STOP conditions

Stop if:

- secure validation would require removing all local compatible-server support;
- redirect refusal cannot be scoped to judge requests;
- fallback diagnostics would echo a key or userinfo;
- any required CI context is red/pending.

## Maintenance notes

- New authenticated providers must reuse the same endpoint validator and
  no-redirect transport.
- Tests must use generated sentinels and local servers only; never real keys.
