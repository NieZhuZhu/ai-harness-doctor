# Plan 064: Bound and neutralize repository-controlled tokens in semantic and drift finding messages

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
>   scripts/semantic.py scripts/check_drift.py scripts/pr_review.py \
>   tests/test_semantic.py tests/test_check_drift.py tests/test_pr_review.py \
>   plans/064-bound-engine-finding-message-tokens.md plans/README.md
> ```
>
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW (narrows a capture regex to the same safe class its four sibling
  regexes already use, and rejects one character class in a link-probe filter;
  neither excludes any real console-script name or repo-relative path)
- **Depends on**: none (independent of Plan 063; both are report-surface
  hardening but touch disjoint code)
- **Category**: security / report integrity
- **Planned at**: commit `9acdafc`, 2026-07-18
- **Status**: TODO

## Why this matters

`scripts/pr_review.py` posts semantic and drift finding `message` strings
**verbatim as GitHub PR review comments** (inline and summary). Its only
sanitizer for that field, `_no_embedded_newlines` (pr_review.py:434-446), just
collapses whitespace. Its docstring justifies that as safe on the explicit
premise that "the semantic/drift engines only ever extract regex-bounded
command/path tokens." Two extractors violate that premise:

1. `scripts/semantic.py`'s `_PY_RUN_RE` captures `(\S+)` — **any** run of
   non-whitespace — unlike its four sibling command regexes
   (`_NODE_CMD_RE`, `_MAKE_CMD_RE`, `_CARGO_BIN_RE`, `_GO_PKG_RE`), which all
   use bounded character classes. A ``poetry run evil`whoami`tool`` reference
   in a scanned `AGENTS.md` is captured whole and embedded, with its backticks,
   into a `command MISMATCH` message.
2. `scripts/check_drift.py`'s D7 link-probe filter `_link_target_is_probeable`
   rejects `<`, `{`, `*`, `?`, and scheme prefixes but **not backticks**, so a
   Markdown link target like `missing\`file.md` is embedded, with its backtick,
   into a `Markdown link target \`…\` does not exist` message.

Either message breaks out of its intended single-backtick code span in the Job
Summary and — the real exposure — in the posted PR review comment, letting a
crafted scanned repository shape Markdown structure in content a reviewer or a
triaging agent may act on. This plan makes both extractors honor the bounded
premise `pr_review.py` already documents.

## Mechanical reproduction (confirm the defect is live)

```bash
tmp=$(mktemp -d)
printf '[project]\nname="x"\nversion="0"\n[project.scripts]\nreal = "x:main"\n' > "$tmp/pyproject.toml"
printf '# Project\n\nRun:\n\n```\nuv run evil`whoami`tool\n```\n\nSee [docs](missing`file.md) for details.\n' > "$tmp/AGENTS.md"
echo "--- semantic (via scan) message:"
python3 scripts/scan.py "$tmp" --json 2>/dev/null | python3 -c "import json,sys;[print(f['message']) for f in json.load(sys.stdin).get('semantic',{}).get('findings',[])]"
echo "--- drift D7 message:"
python3 scripts/check_drift.py "$tmp" 2>/dev/null | grep -i 'link target'
rm -rf "$tmp"
```

Expected on the unpatched tree:
- semantic message contains ``python run evil`whoami`tool`` (embedded backticks);
- drift message contains ``Markdown link target `missing`file.md` does not exist``
  (embedded backtick).

After this plan lands: the `uv run evil\`whoami\`tool` reference produces **no**
`command MISMATCH` finding (the backtick-bearing token is not a valid console
script name and is not captured), and the D7 link target with an embedded
backtick is **skipped** (not probed, no finding), so neither message can carry
a stray backtick.

## Current state

- `scripts/semantic.py`:
  - The four bounded sibling regexes (**semantic.py:164-173**) — the pattern to
    match:

    ```python
    _NODE_CMD_RE = re.compile(
        r"\b(npm|pnpm|bun)\s+(?:run\s+)?([A-Za-z0-9:_][A-Za-z0-9:_-]*)\b"
        r"|\byarn\s+([A-Za-z0-9:_][A-Za-z0-9:_-]*)\b"
    )
    _MAKE_CMD_RE = re.compile(r"\bmake\s+([A-Za-z0-9_.-]+)\b")
    _CARGO_BIN_RE = re.compile(r"\bcargo\s+(?:run|build|install)\b[^`\n]*?--bin[= ]\s*([A-Za-z0-9._-]+)")
    _GO_PKG_RE = re.compile(r"\bgo\s+(?:run|build|test|vet)\s+(\.{1,2}/[A-Za-z0-9._/-]+|[A-Za-z0-9._/-]+\.go)\b")
    ```

  - The unbounded outlier (**semantic.py:178**):

    ```python
    _PY_RUN_RE = re.compile(r"\b(?:poetry|pdm|uv)\s+run\s+(\S+)")
    ```

  - `declared_commands` already filters file-path captures out of the `py_run`
    result (**semantic.py:223-233**): it skips a captured `name` containing `/`
    or `\` or ending in `_PY_RUN_SCRIPT_SUFFIXES`. The captured `name` then
    reaches the finding message at **semantic.py:781-793**
    (``AGENTS.md references `{decl['tool']} run {name}` but pyproject.toml
    declares no `{name}` console script.``).
- `scripts/check_drift.py`:
  - `_link_target_is_probeable` (**check_drift.py:478-501**) — the filter that
    must reject backticks. Current relevant lines:

    ```python
        if "<" in target or "{" in target or "*" in target or "?" in target:
            return None
    ```

  - The D7 finding message embeds `target` at **check_drift.py:533**
    (``Markdown link target `{target}` does not exist``).
- `scripts/pr_review.py` — `_no_embedded_newlines` (pr_review.py:434-446) and
  its docstring stating the bounded-token premise. **Do not weaken or remove**
  this; this plan makes the premise true rather than adding a second escaper.

**Repo conventions to match**:

- Bound `_PY_RUN_RE`'s capture to the same character shape the other
  console-script regexes use. A console script / entry-point name is a Python
  identifier-ish token; `_NODE_CMD_RE` uses `[A-Za-z0-9:_][A-Za-z0-9:_-]*`. A
  safe, equivalent class for `py_run` is `[A-Za-z0-9._-]+` (allows dotted entry
  points like `pkg.module`), which still lets `declared_commands` strip anything
  with `/`, `\`, or a script suffix. Backticks, pipes, and spaces are excluded.
- Any change to `scripts/*.py` ships with matching tests in the same commit.
- Python 3.9+ standard library only. Keep the regexes anchored the same way
  (`\b…run\s+`).

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Semantic tests | `python3 -m unittest tests.test_semantic -v` | OK |
| Drift tests | `python3 -m unittest tests.test_check_drift -v` | OK |
| PR-review tests | `python3 -m unittest tests.test_pr_review -v` | OK |
| Full Python suite | `python3 -m unittest discover -s tests` | OK |
| Node tests | `npm test` | fail 0 |
| Self drift | `python3 scripts/check_drift.py . --strict` | 100/100 grade A, exit 0 |
| Full local gate | `npm run check` | exit 0 |

## Scope

**In scope**:

- `scripts/semantic.py` — bound `_PY_RUN_RE`.
- `scripts/check_drift.py` — reject backticks in `_link_target_is_probeable`.
- `tests/test_semantic.py`, `tests/test_check_drift.py` — regression tests.
- Optionally `tests/test_pr_review.py` — a shared "no finding message contains
  an unpaired backtick" assertion (see Test plan).

**Out of scope**:

- `scripts/pr_review.py` — its bounded-token premise becomes true; do not add a
  second escaper or change `_no_embedded_newlines`.
- The valid behaviors: a legitimate `uv run mytool` with a real missing console
  script must still produce its `command MISMATCH` finding; a legitimate broken
  `[text](docs/missing.md)` link must still produce its D7 finding.
- `AGENTS.md` — byte-budgeted at 10,228/10,240; do not add prose there.

## Git workflow

- Branch: `git checkout -b fix/064-bound-finding-tokens`
- Conventional Commits, English (e.g. `fix(scan): bound python-run and D7 link tokens`).
- Do NOT push or open a PR unless instructed.

## Steps

### Step 1: Bound the `_PY_RUN_RE` capture group

In `scripts/semantic.py`, change `_PY_RUN_RE` from `(\S+)` to the bounded class,
preserving the surrounding anchors and the explanatory comment above it:

```python
_PY_RUN_RE = re.compile(r"\b(?:poetry|pdm|uv)\s+run\s+([A-Za-z0-9._-]+)")
```

Note: this now stops the capture at the first character outside the class, so a
``uv run examples/simple.py`` still captures `examples` — but `declared_commands`
already discards captures containing `/` or ending in a script suffix, and a
bare `examples` with no such marker was already handled by that filter (it is a
plausible console-script name). Confirm the existing "script file, not console
script" filter at semantic.py:223-233 is unchanged.

**Verify**: run the reproduction snippet → the semantic path emits **no**
`command MISMATCH` finding for the backtick token.

### Step 2: Reject backticks in the D7 link-probe filter

In `scripts/check_drift.py`, add a backtick to the rejected character set in
`_link_target_is_probeable`:

```python
        if "<" in target or "{" in target or "*" in target or "?" in target or "`" in target:
            return None
```

**Verify**: run the reproduction snippet → the drift D7 path emits **no** finding
for the backtick-bearing link target.

### Step 3: Regression tests

- In `tests/test_semantic.py`: add a test asserting that a `uv run ev`il`tool`
  reference (backtick in the token) produces **no** `command`-category finding,
  while a clean `uv run realtool` with a declared-scripts pyproject that lacks
  `realtool` **does** produce one (proves the fix narrows only the unsafe shape).
  Use existing tests in that file as the structural pattern (look for tests that
  build a temp repo with `pyproject.toml` + `AGENTS.md` and call
  `semantic.analyze`).
- In `tests/test_check_drift.py`: add a test asserting a Markdown link target
  containing a backtick is skipped (no D7 finding), while a clean
  `[x](missing.md)` still yields a D7 ERROR. Model after the existing D7 tests
  (search for `D7` / `link target`).
- Recommended shared assertion: in whichever of the two new tests is convenient,
  assert the resulting finding `message` (when one exists) contains no unpaired
  backtick — i.e. `message.count("`") % 2 == 0`.

**Verify**: `python3 -m unittest tests.test_semantic tests.test_check_drift -v` → OK.

### Step 4: Full local verification

**Verify**:
- `python3 -m unittest discover -s tests` → OK
- `npm test` → fail 0
- `python3 scripts/check_drift.py . --strict` → 100/100 grade A
- `npm run check` → exit 0

## Test plan

- `tests/test_semantic.py`: unsafe token → no finding; safe token + missing
  script → finding present (happy path preserved).
- `tests/test_check_drift.py`: backtick link target → skipped; clean missing
  link → D7 ERROR present (happy path preserved).
- Both assert no unpaired backtick in any produced message.

## Done criteria

- [ ] Reproduction snippet: semantic emits no MISMATCH for the backtick token; D7 emits no finding for the backtick link.
- [ ] A legitimate missing `uv run realtool` console script still produces a `command` finding; a legitimate `[x](missing.md)` still produces a D7 finding (verified by the new tests).
- [ ] `python3 -m unittest discover -s tests` exits 0; new tests exist and pass.
- [ ] `npm test` fail 0; `node --check bin/cli.js` exits 0.
- [ ] `python3 scripts/check_drift.py . --strict` → 100/100 grade A.
- [ ] `npm run check` exits 0.
- [ ] `git status` shows only in-scope files modified.
- [ ] `plans/README.md` status row updated.

## STOP conditions

- The `_PY_RUN_RE` or `_link_target_is_probeable` excerpts do not match live code.
- Narrowing `_PY_RUN_RE` breaks an existing semantic test that relied on
  capturing a path-shaped or space-bearing token (investigate: that test may
  encode the very bug being fixed).
- The self-scan or an existing repo fixture starts reporting a NEW D7 or command
  finding after the change (means a legitimate target was being probed via a
  backtick — report before proceeding).
- Any AGENTS.md edit would be required.

## Maintenance notes

- If a new `poetry|pdm|uv`-style runner is added, keep its capture bounded to the
  same class; the whole point is that `pr_review.py`'s documented premise stays
  true for every engine token.
- A reviewer should confirm this plan did **not** add a second escaper in
  `pr_review.py` — the correct fix is at the extraction boundary.
- Plan 063 (redact conflict `evidence`) is the sibling report-surface fix on a
  different field/mechanism; keep the two PRs separate.
