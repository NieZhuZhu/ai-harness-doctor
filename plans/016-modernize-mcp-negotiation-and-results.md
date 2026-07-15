# Plan 016: Negotiate modern MCP and expose standard structured results

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat 73bd749..HEAD -- bin/mcp-server.js tests/test_mcp_server.py bin/cli.js bin/cli.test.js README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: direction / protocol / DX / correctness
- **Planned at**: commit `73bd749`, 2026-07-15

## Why this matters

The MCP server is now behaviorally safe, but it advertises the first 2024
protocol forever, ignores the client's requested version, and encodes standard
machine output as a second text block. The latest stable MCP specification is
`2025-11-25`; it supports tool annotations, output schemas, and
`structuredContent`, while still requiring explicit version negotiation.

Modern clients cannot discover that all six tools are read-only or validate
their result metadata from the current server. Add correct protocol negotiation
and modern structured results without breaking older clients that require the
2024 wire shape.

## Current state

- `bin/mcp-server.js:20` hard-codes:

  ```js
  const PROTOCOL_VERSION = '2024-11-05';
  ```

- `handleRequest()` ignores initialize params and always answers 2024:

  ```js
  if (method === 'initialize') {
    sendResult(id, {
      protocolVersion: PROTOCOL_VERSION,
      capabilities: { tools: {} },
      serverInfo: { name: SERVER_NAME, version: PACKAGE_VERSION },
    });
  }
  ```

- Tool definitions already have internal `readOnly: true` and a closed
  `inputSchema`, but `tools/list` emits only name/description/inputSchema.

- `tools/call` always returns:

  ```js
  content: [
    { type: 'text', text: outcome.text },
    { type: 'text', text: JSON.stringify(resultMetadata(outcome)) },
  ]
  ```

  This compatibility workaround was correct for 2024 but is not the standard
  structured result on modern MCP.

- `tests/test_mcp_server.py` sends `initialize` with empty params and asserts
  exactly `2024-11-05`; it has no negotiation tests.

- The official stable 2025-11-25 lifecycle requires the client to send a
  supported `protocolVersion`, the server to echo it when supported or reply
  with another supported version, and the client to disconnect when it cannot
  accept the response.

- The official stable tool contract supports:
  - `annotations` including `readOnlyHint`;
  - optional `outputSchema`;
  - `structuredContent` plus serialized JSON text for backward compatibility.

- The draft spec is already preparing `2026-07-28`. Do not implement draft
  fields in this plan; target the latest **stable** spec only and centralize the
  supported-version list so another version does not require another rewrite.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| MCP tests | `python3 -m unittest discover -s tests -p 'test_mcp_server.py' -v` | all pass |
| Node syntax/lint | `node --check bin/mcp-server.js && npm run lint:js` | exit 0 |
| Node runtime tests | `node --test bin/*.test.js` | all pass |
| Docs sync | `python3 scripts/check_readme_sync.py` | OK |
| Full gate | `npm run check` | exit 0 |
| Self checks | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts && python3 scripts/check_drift.py . --strict` | exit 0; grade A |

## Suggested executor toolkit

- Use the official MCP 2025-11-25 lifecycle and tools pages as normative
  references:
  - `https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle`
  - `https://modelcontextprotocol.io/specification/2025-11-25/server/tools`
- Do not use draft `2026-07-28` fields.

## Scope

**In scope**:

- `bin/mcp-server.js`
- `tests/test_mcp_server.py`
- `bin/cli.js`, `bin/cli.test.js` only if doctor self-test reports supported
  protocol versions
- synchronized READMEs
- `SKILL.md`
- `AGENTS.md` only to update/condense the existing MCP invariant if needed;
  the final hardening plan may own the final wording
- `plans/README.md`

**Out of scope**:

- HTTP/SSE transport, authentication, roots, prompts, resources, sampling,
  elicitation, or tasks.
- Mutating MCP tools.
- An MCP SDK/runtime dependency.
- Draft protocol `2026-07-28`.
- Removing 2024 compatibility.
- Changing Python report schemas or exit codes.

## Git workflow

- Branch: `feat/modern-mcp-contract`
- Commit: `feat(mcp): negotiate structured tool results`
- Backward-compatible feature PR; squash-merge only after all CI checks pass.

## Steps

### Step 1: Characterize lifecycle negotiation

Replace the empty initialize fixture with valid initialize requests and add
table-driven exchanges for:

- client requests `2025-11-25` → server responds `2025-11-25`;
- client requests `2024-11-05` → server responds `2024-11-05`;
- unsupported/future version → server responds with latest supported stable
  version, per the spec;
- malformed initialize params → JSON-RPC `INVALID_PARAMS`;
- a non-ping request before initialize, and a tool request before the
  `initialized` notification, are handled according to the chosen lifecycle
  enforcement level.

If strict lifecycle enforcement breaks known stdio clients or the existing
`npx ... mcp` integration contract, enforce negotiation/version correctness but
defer request-order rejection; document and test that explicit compatibility
decision.

**Verify**: new negotiation assertions fail against `73bd749`; existing tool
calls remain available after a complete initialize handshake.

### Step 2: Centralize session protocol state

Replace the singleton constant with:

- an ordered immutable supported-version list containing stable
  `2025-11-25` and legacy `2024-11-05`;
- latest stable version;
- per-connection negotiated version set by initialize.

Do not infer a version from later requests. Keep stdio newline transport and
one server process/one connection semantics.

**Verify**: negotiation tests pass; initialize remains deterministic.

### Step 3: Advertise modern tool schemas only on the modern protocol

For negotiated `2025-11-25`, emit:

- existing closed `inputSchema`;
- `annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint:
  true, openWorldHint: false }` where semantically accurate;
- an `outputSchema` for the standard result metadata
  `{ kind, exitCode, ok, status, report? }`.

Use a schema permissive enough for tool-specific parsed reports under `report`
while keeping required metadata typed. For negotiated 2024, preserve its legal
tool shape and do not emit fields absent from that schema.

**Verify**: tools/list tests assert modern annotations/schema and byte-compatible
legacy field set.

### Step 4: Return structuredContent with a compatibility text copy

For modern protocol calls:

- keep human/tool output in `content[0]`;
- keep serialized metadata in a text content item as recommended for backward
  compatibility;
- also return the same object in top-level `structuredContent`;
- ensure it conforms to every advertised `outputSchema`.

For 2024 calls, preserve the existing two-text-item shape and omit
`structuredContent`.

Continue to distinguish `ok`, `findings`, and `error`; do not turn findings into
execution errors.

**Verify**: all six tools pass modern and selected legacy result-shape tests;
structured and serialized metadata are deep-equal.

### Step 5: Add protocol-aware negative tests

Cover:

- malformed/unknown arguments;
- invalid target;
- finding-bearing JSON reports;
- timeout/missing Python;
- no traceback/argv/environment leakage;
- no modern-only fields in 2024 tools/results.

Use real stdio exchanges as the primary contract. Export helpers only when that
reduces duplicate policy logic.

**Verify**: focused suite passes on Node 16/20/22 and Python 3.9/3.10/3.12 CI.

### Step 6: Synchronize the public contract

Update synchronized READMEs and `SKILL.md` with:

- supported protocol versions and negotiation;
- modern structured result and legacy fallback;
- read-only annotations/output schemas;
- no claim of HTTP or other unsupported capabilities.

Condense the existing MCP invariant in `AGENTS.md` if implementation creates a
new maintenance rule; keep strict drift Grade A.

**Verify**: docs sync, full gate, self checks, and package dry-run.

## Test plan

- Initialize negotiation: latest, legacy, unsupported, malformed.
- tools/list modern vs legacy field sets.
- tools/call modern structuredContent equals serialized metadata.
- Output schema required fields for all six tools.
- Legacy result remains two text items and no structuredContent.
- Existing findings/error/input/timeout/read-only regressions remain.

## Done criteria

- [ ] Latest stable and legacy protocols negotiate correctly.
- [ ] Modern clients receive annotations, output schemas, and structuredContent.
- [ ] Legacy 2024 clients retain their legal existing shape.
- [ ] Every structured result conforms to the advertised schema.
- [ ] All six tools remain read-only.
- [ ] No draft-only field or runtime dependency is introduced.
- [ ] `npm run check` passes and strict self-drift remains Grade A.
- [ ] Only in-scope files are modified.

## STOP conditions

- Supporting 2025-11-25 requires an SDK/runtime dependency.
- A known client demonstrably rejects the spec-valid negotiated response and no
  version-specific compatibility path is possible.
- Correct output schemas require changing Python report contracts.
- The implementation would expose mutation, network transport, or draft fields.
- Verification fails twice after a reasonable correction.

## Maintenance notes

Protocol version is session state, not a package-global display string. Future
MCP upgrades must add a negotiated version and version-gated wire tests before
using new fields. Keep internal outcome policy independent from wire encoding.
