# Plan 013: Make MCP tool failures machine-visible and keep its contract current

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat b638ad7..HEAD -- bin/mcp-server.js tests/test_mcp_server.py README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: MED
- **Depends on**: none
- **Category**: correctness / DX / docs
- **Planned at**: commit `b638ad7`, 2026-07-15

## Why this matters

The MCP server is how AI clients consume the doctor programmatically. It
currently returns `isError: false` for every Python subprocess that starts,
including invalid repository paths, failed validation, and blocking drift.
Clients therefore cannot distinguish success from a failed check without
parsing tool-specific text/JSON, which defeats MCP's standard error signal and
can let an agent continue after a guard failure.

The correct contract must distinguish operational failures from expected
finding/gate exits. It should expose the underlying exit code in structured
content and set `isError` for invalid invocation/runtime failures, while keeping
valid scan/drift reports usable even when they intentionally report findings.
The same PR should correct `SKILL.md`, whose MCP passages still list only four
tools although the server and README expose six.

## Current state

- `bin/mcp-server.js:165-190` discards non-zero status from MCP semantics:

  ```js
  const result = childProcess.spawnSync(...);
  // ...
  // Some tools (e.g. drift) return a non-zero exit code to signal findings;
  // that is not a transport error.
  let text = stdout;
  if (!text && stderr) text = summarizeStderr(stderr);
  return { isError: false, text, exitCode: result.status };
  ```

- `bin/mcp-server.js:193-204` then drops `exitCode` entirely:

  ```js
  const outcome = callTool(tool, ...);
  sendResult(id, {
    content: [{ type: 'text', text: outcome.text }],
    isError: Boolean(outcome.isError),
  });
  ```

- Real reproductions on the planned commit:
  - `harness_scan`, `harness_drift`, and `harness_validate` against a nonexistent
    path return JSON with `"error"` / `"ok": false`, but MCP sends
    `isError:false`.
  - `harness_drift` with a real D1 `ERROR` exits non-zero and returns grade B,
    but MCP sends `isError:false`.
  - `harness_validate` with missing required headings returns `ok:false`, but
    MCP sends `isError:false`.
  - `harness_plan` against a nonexistent path exits successfully with an empty
    plan, showing that per-tool exit semantics must be characterized rather than
    treating every non-zero or every empty inventory identically.

- `tests/test_mcp_server.py` covers success, unknown tools, timeout, and
  read-only behavior, but never asserts subprocess `exitCode` or operational
  versus finding failures.

- The actual tool registry at `bin/mcp-server.js:32-109` contains six tools:
  `harness_scan`, `harness_drift`, `harness_validate`, `harness_plan`,
  `harness_stubs`, `harness_eval_generate`.

- README command reference correctly lists six at `README.md:610-617`, but
  `SKILL.md:391-394` and `SKILL.md:479` still list only the original four.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| MCP tests | `python3 -m unittest discover -s tests -p 'test_mcp_server.py' -v` | all pass |
| Node syntax/lint | `node --check bin/mcp-server.js && npm run lint:js` | exit 0 |
| CLI runtime tests | `node --test bin/*.test.js` | all pass |
| Docs sync | `python3 scripts/check_readme_sync.py` | OK |
| Full gate | `npm run check` | exit 0 |
| Self checks | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts && python3 scripts/check_drift.py . --strict` | exit 0; grade A |

## Scope

**In scope**:

- `bin/mcp-server.js`
- `tests/test_mcp_server.py`
- `README.md`, `README.zh-CN.md`, `README.ja.md`
- `SKILL.md`
- `AGENTS.md`
- `plans/README.md`

**Out of scope**:

- Adding mutating MCP tools (`guard --apply`, `stubs --apply`, installer,
  baseline writes, eval agent execution).
- Changing Python script exit codes or report JSON schemas.
- Migrating to another MCP transport or SDK.
- Making all finding/gate exits transport errors and thereby hiding the report.
- Adding arbitrary CLI argument passthrough to MCP tools.
- Expanding beyond the existing six tool definitions.

## Git workflow

- Branch: `fix/mcp-tool-failure-semantics`
- Commit: `fix(mcp): expose tool failure semantics`
- One focused PR, squash-merged only after all CI checks pass.
- This is a bugfix; do not release from the feature branch.

## Steps

### Step 1: Characterize every tool's exit semantics

Extend `tests/test_mcp_server.py` with table-driven exchanges that cover:

1. operational invalid target for scan/drift/validate;
2. a valid repo with drift findings;
3. a valid repo with validation findings;
4. successful scan/drift/validate/plan/stubs/eval-generate;
5. timeout/spawn failure.

For each call, assert `isError`, visible text, and structured exit metadata.
Capture the Python CLI subprocess return code directly in test setup when
needed, so expected semantics are evidence-based rather than guessed.

**Verify**: the operational and structured-exit assertions fail against the
planned commit; existing success/timeout tests remain green.

### Step 2: Define a per-tool result policy

Add explicit metadata to each `TOOLS` definition describing which exit codes are
valid report outcomes versus operational failures. Recommended policy:

- scan: known finding/gate codes remain report outcomes when stdout is valid
  scan JSON/Markdown; invalid target/usage remains error;
- drift: blocking finding codes remain report outcomes when stdout is a valid
  drift report; invalid target/usage remains error;
- validate: validation findings are a valid report outcome but `ok:false` must
  remain machine-visible through structured metadata;
- plan/stubs/eval-generate: only documented successful report codes are valid.

Do not infer success solely from “stdout is nonempty.” Validate only the minimal
shape needed for each JSON mode, and do not parse arbitrary Markdown to detect
success.

If existing Python exit codes cannot distinguish invalid target from findings
for one tool, return a non-transport MCP result with `isError:true`,
`exitCode`, and the sanitized output rather than silently treating it as
success. Do not change Python exit codes in this PR.

**Verify**: table-driven policy tests pass and no valid finding report is lost.

### Step 3: Preserve structured exit information in MCP results

Return a result payload with:

- `content` containing the human-readable/tool JSON text;
- `isError` according to the per-tool policy;
- `structuredContent` (when supported by this server contract) containing at
  least `{ exitCode, ok }`, plus a parsed report only when JSON was explicitly
  requested and parsing succeeds.

If adding `structuredContent` conflicts with the advertised protocol version or
current clients, keep `content` unchanged and include a compact JSON metadata
content item instead. Treat that as a STOP decision to document, not something
to improvise silently.

Never expose the full argv, environment, traceback, or absolute packaged script
path. Continue using `summarizeStderr()` for operational failures.

**Verify**: clients can distinguish clean success, report-with-findings, invalid
target, timeout, and unknown tool without scraping prose.

### Step 4: Validate MCP input arguments before spawning

Reject `tools/call` arguments that are not an object or whose known properties
have the wrong types. Add `additionalProperties: false` to each input schema and
return `INVALID_PARAMS` for unknown fields instead of silently ignoring typos.

Keep `repo` optional with default `"."`; do not require it. Boolean flags must
be actual booleans, not truthy strings.

**Verify**: malformed/unknown arguments return JSON-RPC `-32602` and do not spawn
Python; existing valid calls remain byte-compatible in `content`.

### Step 5: Synchronize the six-tool public contract

Update `SKILL.md` MCP method/tool list and reference index to list all six tools,
matching `README.md` and `TOOLS`. Update synchronized README prose only for the
new failure/result metadata; keep the same fenced blocks, table structure, and
link targets across all languages.

Condense an `AGENTS.md` invariant: every MCP tool must declare input schema,
exit/result policy, read-only status, and matching tests/docs. Keep the file
below strict D4 size.

**Verify**: docs sync, focused tests, full gate, self scan, and strict drift.

## Test plan

- End-to-end stdio JSON-RPC tests:
  - all six tools listed and schema-disallow unknown properties;
  - invalid argument type / unknown argument;
  - nonexistent target;
  - clean report;
  - finding-bearing scan/drift/validate report;
  - timeout and missing Python;
  - read-only stubs/eval-generate unchanged.
- Pure/exported helper tests may be added in Node only if they reduce subprocess
  duplication; the primary contract remains real server exchange tests.
- Assert no traceback, package script path, or environment value leaks in error
  content.

## Done criteria

- [ ] Every tool call exposes a machine-readable exit code/outcome.
- [ ] Operational failures are never returned as `isError:false`.
- [ ] Finding-bearing reports remain available to the caller.
- [ ] Invalid/unknown arguments fail before Python is spawned.
- [ ] All six tools remain read-only and are documented consistently.
- [ ] Timeout and stderr sanitization behavior does not regress.
- [ ] `npm run check` passes and self-drift remains grade A.
- [ ] Only in-scope files are modified.

## STOP conditions

- The existing MCP protocol/client compatibility cannot carry structured result
  metadata without a protocol-version change.
- Python exit codes make operational failures and valid findings
  indistinguishable and the distinction cannot be made safely from explicit
  JSON mode.
- Correct semantics require changing a Python report or exit-code contract.
- The work would expose mutating CLI surfaces over MCP.
- Verification fails twice after a reasonable correction.

## Maintenance notes

MCP `isError` is a client control signal, not a synonym for “the doctor found a
problem.” Every future tool must declare both its valid report exit codes and
its operational failure codes. Keep `TOOLS`, `tools/list`, the exchange tests,
README, and `SKILL.md` synchronized as one public API.
