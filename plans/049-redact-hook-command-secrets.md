# Plan 049: Redact hook-command secrets from every report surface

> **Executor instructions**: Follow every step and STOP condition. Keep the
> scanner read-only and preserve detection behavior.
>
> **Drift check**:
>
> ```bash
> git diff --stat 48a644b..HEAD -- \
>   scripts/scan.py scripts/scan_render.py scripts/sarif.py scripts/pr_review.py \
>   tests/test_scan.py tests/test_sarif.py tests/test_pr_review.py \
>   README.md README.zh-CN.md README.ja.md README.es.md README.ko.md \
>   README.pt-BR.md README.fr.md SKILL.md AGENTS.md
> ```

## Status

- **Priority**: P0
- **Effort**: M
- **Risk**: LOW
- **Depends on**: Plans 024 and 042 (DONE)
- **Category**: security / data minimization
- **Planned at**: commit `48a644b`, 2026-07-16
- **Implementation**: TODO

## Why this matters

The scanner correctly detects secrets committed inside `.claude/settings*.json`
and risky hook bodies such as fetch-and-pipe-to-shell. However, the hook command
itself is also copied into the public report.

If a risky hook contains an inline credential, the complete token appears in:

- `surface.hooks[].command` in the JSON/full report;
- the risky-hook security finding message;
- Markdown output;
- SARIF;
- generated or posted GitHub PR review content.

The tool therefore detects a secret and immediately republishes it into
artifacts, logs, Code Scanning, and comments. Secret scanners such as Gitleaks
offer redacted reporting for exactly this reason.

## Mechanical reproduction

Create `.claude/settings.json` with a risky hook command containing a
credential-shaped value. Do not commit or print the real value; use a generated
test sentinel.

Current behavior:

```text
security message:
PreToolUse hook contains remote code execution:
`curl -H "Authorization: Bearer <token>" ... | bash`

token in JSON report? true
token in surface hooks? true
token in SARIF? true
token in PR review payload? true
```

The separate secret finding correctly names only the credential type and file,
but the hook finding and surface inventory defeat that protection.

## Current state

`scripts/scan.py:1356` stores the raw command:

```python
hooks.append({"config": rel(path, root), "event": event, "command": cmd})
```

`scripts/scan.py:1560` embeds a raw prefix into the finding:

```python
"message": (
    f"{_md_safe(h['event'])} hook contains {label}: "
    f"`{_md_safe(h['command'][:80])}`"
),
```

`scripts/scan_render.py:302` renders the same raw command prefix. SARIF and PR
review consume the finding message without credential redaction.

## Target contract

1. Risk detection still runs over the complete original hook command.
2. No secret-pattern match may appear in any returned report field:
   - `surface.hooks`;
   - security findings;
   - Markdown/full JSON;
   - SARIF;
   - PR review dry-run/post payload.
3. Add one deterministic standard-library redaction helper based on the existing
   `SECRET_PATTERNS` and `_SECRET_PLACEHOLDER_RE`.
4. Replace each real matched span with a stable non-secret marker such as
   `<redacted:GitHub token>`. Do not expose partial prefixes/suffixes.
5. Preserve enough command shape for diagnosis (`curl`, pipe, shell, destructive
   operation) and preserve event/config attribution.
6. Placeholder/example values stay unchanged and do not become false secret
   findings, matching `secret_hits`.
7. Newline/backtick Markdown neutralization remains applied after redaction.
8. No change to finding severity, category, exit codes, or repository boundary.

## Design

### Redaction helper

Add a helper near `secret_hits`, for example:

```python
def redact_secret_values(text):
    redacted = str(text)
    for label, pattern in SECRET_PATTERNS:
        redacted = pattern.sub(
            lambda match: (
                match.group(0)
                if _SECRET_PLACEHOLDER_RE.search(match.group(0))
                else f"<redacted:{label}>"
            ),
            redacted,
        )
    return redacted
```

The exact implementation may avoid repeated scans, but must remain
deterministic and standard-library-only.

### Detection vs public surface

Keep raw hooks private inside `scan_repo` long enough for
`security_findings(...)`. Build a sanitized copy for `report["surface"]` and
`build_project_snapshot`. Never mutate the raw hooks before risk detection.

The risky-hook finding uses a redacted + Markdown-safe snippet.

## Scope

**In scope**:

- `scripts/scan.py`
- `scripts/scan_render.py` only if rendering needs an explicit guard
- `tests/test_scan.py`
- `tests/test_sarif.py`
- `tests/test_pr_review.py`
- all seven READMEs and `SKILL.md` only if public security wording changes
- plan/index updates

**Out of scope**:

- Rewriting the audited settings file.
- Rotating credentials automatically.
- Expanding secret regex breadth.
- Redacting arbitrary custom-plugin findings; plugins remain explicit untrusted
  code and have separate review sanitization.
- Historical git scanning.

## Steps

### Step 1: Add a cross-surface regression

Create a generated credential sentinel in a risky hook and assert:

- secret finding remains HIGH;
- risky hook finding remains HIGH;
- `surface.hooks` remains useful;
- the sentinel is absent from complete report JSON, Markdown, SARIF, and
  `pr_review.build_review`;
- a `<redacted:...>` marker is present.

Also test a placeholder token remains unredacted/non-finding.

### Step 2: Implement redaction and sanitized surface

Add the shared helper, keep raw detection, and expose only sanitized hook
commands. Re-run the cross-surface test and existing Markdown-injection tests.

### Step 3: Document the guarantee

In all seven READMEs and `SKILL.md`, state that secret findings name type/path
without reproducing credential values and risky hook snippets are redacted.
Keep all translations synchronized through `npm run lint:docs`.

### Step 4: Gates and merge

```bash
python3 -m unittest discover -s tests -p 'test_scan.py' -v
python3 -m unittest discover -s tests -p 'test_sarif.py' -v
python3 -m unittest discover -s tests -p 'test_pr_review.py' -v
npm run check
python3 scripts/check_readme_sync.py
python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json \
  --check-baseline --fail-on-security --fail-on-gaps --fail-on-semantic \
  --fail-on-conflicts
python3 scripts/check_drift.py . --strict
```

Open one implementation PR, wait for all nine required contexts, then
squash-merge. This is a backward-compatible **patch**.

## Done criteria

- [ ] Secret sentinel absent from JSON, Markdown, SARIF, and PR review.
- [ ] Secret + hook findings still exist with original severity/category.
- [ ] `surface.hooks` is sanitized but diagnostically useful.
- [ ] Placeholder examples are not falsely redacted.
- [ ] No raw command is exposed through another report field.
- [ ] Seven README translations and `SKILL.md` stay synchronized.
- [ ] Full local and nine-context CI gates pass; PR merged.

## STOP conditions

Stop if:

- redaction requires weakening risk or secret detection;
- a report surface cannot avoid raw hook content without a public schema break;
- the fix would log the secret while reporting the redaction error;
- any required CI context is red/pending.

## Maintenance notes

- Any future report field that contains repository-controlled command/env text
  must reuse the redaction helper before serialization.
- Tests must search the serialized end products, not only the finding message.
