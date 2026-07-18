# Plan 063: Redact and Markdown-neutralize conflict-signal evidence before it reaches any report surface

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md` unless a reviewer maintains the index separately.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 9acdafc..HEAD -- \
>   scripts/scan.py scripts/scan_render.py \
>   tests/test_scan.py \
>   references/maintenance-contract.md \
>   plans/063-redact-conflict-signal-evidence.md plans/README.md
> ```
>
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: S
- **Risk**: LOW (report-only sanitization; conflict *detection* keys on
  `signal`+`value`, never on `evidence`, so display-only text is changed)
- **Depends on**: Plans 049, 051, 062 (DONE — the shared
  `redaction.redact_secret_values` redactor and `scan._md_safe` Markdown
  neutralizer already exist and are the exact tools reused here)
- **Category**: security / data minimization / report integrity
- **Planned at**: commit `9acdafc`, 2026-07-18
- **Status**: TODO

## Why this matters

`scripts/scan.py`'s conflict-detection path records, for every matched
package-manager / node-version / formatter / test-command signal, the **entire
raw source line** of the scanned repository's `AGENTS.md` / `CLAUDE.md` / etc.
as its `evidence` field. That raw line is copied verbatim into
`report["conflicts"]` and `report["scope_overrides"]`, then written to the
on-disk JSON report and rendered into the scan Markdown that the shipped
`assets/guard/harness-checkup.yml` workflow posts to a **public GitHub Issue**
via `gh issue create --body` / `gh issue comment --body`.

Every other repository-controlled string surfaced by this scanner (hook
commands — Plan 049; MCP `command`/`url`/env — Plan 062; eval artifacts —
Plan 051) is run through `redaction.redact_secret_values` and, for Markdown,
`scan._md_safe`. The conflict `evidence` field is the one remaining surface
that bypasses **both**. A single scanned line that combines a conflict keyword
with a credential-shaped value (`- run \`pnpm install\` with token
ghp_…`) is therefore reproduced byte-for-byte in the JSON report, the Job
Summary, and the auto-filed issue — a credential leak in exactly the class this
project spent three prior plans closing. Independently of secrets, an
unbalanced backtick or pipe in that raw line corrupts the rendered Markdown and
can plant text a human or triaging agent misreads as instruction.

This plan sanitizes `evidence` **once, at the point it is captured**, so every
downstream consumer (conflicts, overrides, JSON, Markdown) inherits the safe
value with no per-surface change.

## Mechanical reproduction (do this first to confirm the defect is live)

```bash
tmp=$(mktemp -d)
sent="ghp_$(python3 -c 'import secrets,string;print("".join(secrets.choice(string.ascii_letters+string.digits) for _ in range(36)))')"
printf '# Project\n\n- Install with `npm install` using token %s here\n' "$sent" > "$tmp/AGENTS.md"
printf '# Claude\n\n- Install with `pnpm install` using token %s here\n' "$sent" > "$tmp/CLAUDE.md"
python3 scripts/scan.py "$tmp" --json 2>/dev/null | python3 -c "import json,sys;r=json.load(sys.stdin);print('LEAK in conflicts JSON:', '$sent' in json.dumps(r['conflicts']))"
python3 scripts/scan.py "$tmp" 2>/dev/null | grep -A3 'Conflict candidates'
rm -rf "$tmp"
```

Expected on the unpatched tree: `LEAK in conflicts JSON: True`, and the
rendered Markdown shows the full ``` `npm install` using token ghp_… ``` line.
After this plan lands, the same commands must print `LEAK in conflicts JSON:
False` and show a redacted token.

## Current state

- `scripts/scan.py` — Phase 0 scanner. Relevant regions:
  - `extract_signals(...)` captures each signal, currently storing the raw
    line as `evidence` (**scan.py:924-931**):

    ```python
                signals.append(
                    {
                        "signal": signal,
                        "value": actual,
                        "path": file_entry["path"],
                        "line": lineno,
                        "evidence": line.strip(),
                    }
                )
    ```

  - `analyze_scoped_conflicts(...)` copies every key **except `_domain`** of
    each signal entry (so `evidence` included) into both `conflict["values"]`
    (**scan.py:1171-1183**) and `scope_overrides[].evidence`
    (**scan.py:1207-1223**). No call site here redacts or escapes.
  - The shared helpers already exist in this module:
    - `redaction.redact_secret_values` is imported (used at
      **scan.py:1403-1517** for MCP/hook fields).
    - `scan._md_safe(value)` (**scan.py:1382-1395**) collapses whitespace and
      replaces backticks — the exact Markdown neutralizer used for MCP/hook
      report strings.
- `scripts/scan_render.py` — renders the raw evidence into a single-backtick
  Markdown span in the "Conflict candidates" section (**scan_render.py:59-61**):

  ```python
                evidence = "; ".join(f"{e['path']}:{e['line']} `{e['evidence']}`" for e in entries)
                lines.append(f"  - `{value}`: {evidence}")
  ```

  This code needs **no change** once `evidence` is sanitized at source, but its
  behavior is part of the verification.
- `scripts/pr_review.py` already rebuilds conflict evidence from `path`/`line`
  only (`_conflict_evidence`, pr_review.py:162-186) and never reads the raw
  `evidence` string — so PR review is already safe and is **out of scope**.

**Repo conventions to match** (inline, since the executor has not seen them):

- The exemplar for cross-surface secret sanitization is
  `tests/test_scan.py:2225` `test_mcp_secret_is_redacted_from_every_report_surface`
  — it builds a `ghp_` + `"B"*24` sentinel, asserts the raw value still reaches
  `security_findings` (detection stays on raw bytes), then asserts the sentinel
  is absent and `"<redacted:GitHub token>"` present in the JSON, Markdown, and
  temp-report surfaces. Model the new test on it.
- `redaction.redact_secret_values(text)` returns the text with each secret
  match replaced by `<redacted:LABEL>` (e.g. `<redacted:GitHub token>`).
- Any change to `scripts/*.py` ships with matching tests in the same commit
  (`AGENTS.md` "Testing requirements").
- Python 3.9+ standard library only.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused scan tests | `python3 -m unittest tests.test_scan -v` | OK |
| Full Python suite | `python3 -m unittest discover -s tests` | OK |
| Node tests | `npm test` | fail 0 |
| Self scan | `python3 scripts/scan.py .` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | Score 100/100 (grade A), exit 0 |
| README sync | `python3 scripts/check_readme_sync.py` | OK across 7 READMEs |
| Full local gate | `npm run check` | exit 0 (lint + tests + packed candidate) |

## Scope

**In scope** (the only files you should modify):

- `scripts/scan.py` — sanitize `evidence` in `extract_signals`.
- `tests/test_scan.py` — add the regression test.
- `references/maintenance-contract.md` — **only if** you record a one-line
  invariant; keep it short (see STOP conditions re: AGENTS.md byte budget).

**Out of scope** (do NOT touch):

- `scripts/scan_render.py` — the render change is unnecessary once the source
  is sanitized; changing it too would double-escape.
- `scripts/pr_review.py` — already safe (rebuilds from `path:line`).
- `AGENTS.md` — it currently sits at 10,228 bytes against a 10,240-byte budget
  enforced by `tests/test_action_metadata.py:38`; adding a line breaks that
  test. Do not add invariant prose there.
- The conflict-detection logic (`_conflict_key`, grouping) — `evidence` is
  display-only and must not change which conflicts are detected.

## Git workflow

- Branch off current `main`: `git checkout -b fix/063-redact-conflict-evidence`
- Conventional Commits, English. Example from `git log`:
  `fix(scan): redact MCP surface secrets`.
- One themed change. Do NOT push or open a PR unless the operator instructed it.

## Steps

### Step 1: Sanitize `evidence` at capture in `extract_signals`

In `scripts/scan.py`, change the `evidence` value stored in `extract_signals`
so it is redacted for secrets **and** Markdown-neutralized before storage.
Replace `"evidence": line.strip(),` with:

```python
                        "evidence": _md_safe(redact_secret_values(line)),
```

`_md_safe` already collapses surrounding whitespace (it calls `.split()`), so
the explicit `.strip()` is subsumed. Confirm `_md_safe` is defined in the same
module (it is, at scan.py:1382) and `redact_secret_values` is imported (it is).

**Verify**: `python3 -c "import sys; sys.path.insert(0,'scripts'); import scan; print(scan.extract_signals.__code__.co_names[:1] or 'ok')"` → runs without ImportError. Then run the reproduction snippet from "Mechanical reproduction" above → `LEAK in conflicts JSON: False`.

### Step 2: Add the regression test

In `tests/test_scan.py`, add a test modeled on
`test_mcp_secret_is_redacted_from_every_report_surface` (tests/test_scan.py:2225).
The test must:

1. Write a repo with a conflicting signal that carries a `ghp_`+`"D"*24`
   sentinel on the same line in two files, e.g.
   `AGENTS.md`: ``- Install with `npm install` using token <sentinel>`` and
   `CLAUDE.md`: ``- Install with `pnpm install` using token <sentinel>`` (this
   produces a `package_manager` conflict).
2. Run `scan.scan_repo(repo, 32768)`, then `scan.write_report_file(report, repo)`.
3. Assert the sentinel is **absent** and `"<redacted:GitHub token>"` **present**
   in: `json.dumps(report)`, `scan.render_markdown(report)`, and the temp report
   file text.
4. Assert a `package_manager` conflict is still detected (the fix must not
   suppress detection): `report["conflicts"]` is non-empty and contains a
   conflict whose `signal == "package_manager"`.
5. Also assert a raw backtick embedded in a conflicting line does not survive
   into `render_markdown` unbalanced — reuse the same sentinel line but add a
   stray backtick and assert the rendered Markdown for that section has an even
   backtick count on each rendered evidence line (or, more simply, that the
   literal ``token`` breakout substring is neutralized to a single quote by
   `_md_safe`). Clean up the temp report file in a `finally` block.

**Verify**: `python3 -m unittest tests.test_scan -v 2>&1 | tail -3` → OK, with your new test named in the run.

### Step 3: Full local verification

Run the full gate.

**Verify**:
- `python3 -m unittest discover -s tests` → OK
- `npm test` → fail 0
- `python3 scripts/scan.py .` → exit 0; `python3 scripts/check_drift.py . --strict` → 100/100 grade A
- `npm run check` → exit 0

## Test plan

- New test in `tests/test_scan.py` (happy path = conflict still detected;
  regression = sentinel redacted across JSON/Markdown/temp-report; edge =
  backtick neutralized). Model structurally after
  `test_mcp_secret_is_redacted_from_every_report_surface`.
- Existing conflict tests in `tests/test_scan.py` must remain green (they assert
  conflict *shape*, not the raw evidence text; confirm none assert a full raw
  line survives — if one does, that is a STOP condition, report it).

## Done criteria

Machine-checkable. ALL must hold:

- [ ] The reproduction snippet prints `LEAK in conflicts JSON: False`.
- [ ] `python3 -m unittest discover -s tests` exits 0; the new test exists and passes.
- [ ] `npm test` reports fail 0; `node --check bin/cli.js` exits 0.
- [ ] `python3 scripts/scan.py .` exits 0; `python3 scripts/check_drift.py . --strict` prints 100/100 grade A.
- [ ] `npm run check` exits 0.
- [ ] `wc -c AGENTS.md` is unchanged (still ≤ 10,240).
- [ ] `git status` shows only in-scope files modified.
- [ ] `plans/README.md` status row updated.

## STOP conditions

Stop and report back (do not improvise) if:

- The `extract_signals` excerpt at scan.py:924-931 does not match the live code.
- An existing test asserts that a full raw source line survives verbatim in
  `report["conflicts"]`/`report["scope_overrides"]` (would mean some consumer
  depends on the raw text — investigate before changing behavior).
- Redacting `evidence` changes which conflicts are *detected* (it must not;
  detection keys on `signal`+`value`).
- Any AGENTS.md edit would be needed — it is out of scope and byte-budgeted.

## Maintenance notes

- Any future signal added to `extract_signals` inherits this sanitization for
  free because it happens at the single capture site.
- A reviewer should confirm the change is at the **capture** site (not per
  render surface) and that `scan_render.py` was left unchanged (double-escaping
  would be a smell).
- Deferred out of this plan (separate findings): SECURITY-2 (bound
  `semantic._PY_RUN_RE` and reject backticks in D7 link targets — see Plan 064)
  is a distinct extraction-boundary theme and must not be mixed in here.
