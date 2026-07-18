# Plan 062: Redact MCP credentials from every scan-report surface

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md` unless a reviewer maintains the index separately.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 11e3a71..HEAD -- \
>   scripts/scan.py scripts/redaction.py scripts/scan_render.py \
>   tests/test_scan.py tests/test_action_metadata.py \
>   AGENTS.md SKILL.md \
>   README.md README.zh-CN.md README.ja.md README.es.md README.ko.md \
>   README.pt-BR.md README.fr.md \
>   benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json \
>   benchmark/self-eval/results-after-graded.json benchmark/self-eval/README.md \
>   plans/062-redact-mcp-surface-secrets.md plans/README.md
> ```
>
> If any in-scope file changed, compare the "Current state" excerpts against
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: S–M
- **Risk**: LOW (report-only sanitization over an existing shared redactor;
  raw detection and findings stay unchanged)
- **Depends on**: Plans 049 and 051 (DONE — shared high-confidence redaction
  patterns and cross-surface testing already exist)
- **Category**: security / data minimization / report integrity
- **Planned at**: commit `11e3a71`, 2026-07-18
- **Status**: DONE — implemented on `fix/062-redact-mcp-surface-secrets`
  and merged via PR
  [#273](https://github.com/NieZhuZhu/ai-harness-doctor/pull/273)
  (reviewed head `fc2fc5056b1970525e8865c43b1d3679b9836754`, squash merge
  `b9fb8a3391441146a7c6959f56f294160ae800ee`), closeout recorded
  2026-07-18; the remote implementation branch was deleted.

## Implementation and verification evidence (closeout, 2026-07-18)

- **Plan-first sequence**: plan-only PR
  [#272](https://github.com/NieZhuZhu/ai-harness-doctor/pull/272) passed 9/9
  required checks before merging as `68d5e878`; implementation then proceeded
  in PR [#273](https://github.com/NieZhuZhu/ai-harness-doctor/pull/273).
- **Implementation review and merge**: the final reviewed head
  `fc2fc5056b1970525e8865c43b1d3679b9836754` had 9/9 required checks
  SUCCESS and zero unresolved review threads. Standards/Spec review was
  PASS. Admin bypass was used only for the sole-maintainer self-approval
  deadlock, never over red or pending CI.
- **Test-first RED**: against the implementation parent (plan merge
  `68d5e87876c3bd4a116c61c5d30a3ca3c58ffb0c`), the new MCP artifact test
  failed at the raw `command`, `url`, serialized JSON, rendered Markdown, and
  temporary full-report assertions before production code changed. The new
  repository-contract assertion independently failed on the parent's old
  commit-only Safety wording.
- **Historical compatibility RED**: copying the final repository-contract test
  to Plan 061's pre-compaction parent `1d6b1f8` still produced exactly the
  intended sole budget failure (`12231 > 10240`), with no semantic subtest
  failures.
- **Test matrix**: 8/8 mutation probes passed including the raw spy
  boundary (raw MCP data stays available for security detection while
  only the public surface is sanitized). Focused suites passed scan 176,
  action metadata 38, eval 135, SARIF 38, and PR review 42 tests.
- **Full suite**: Python 849 tests passing, Node 51 tests passing,
  `npm test` green, `npm run check` green including packed candidate.
- **Repository health**: self scan exited 0; strict drift scored 100/Grade A.
- **Docs and contract**: README sync passed 7/7; SKILL.md updated;
  `AGENTS.md` is 10,228 bytes (within the ≤ 10,240-byte budget) with
  SHA-256 `fa6e4fed67007d2f639346178081de1f929539e932c2a245c78dbec584f5d51b`.
- **Self-eval**: 40/40 tasks pass at 100/Grade A with honest
  manual-protocol notes; `tasks.json` SHA
  `f137b1271e32a31ec4c99b640ff15122a88b7bbd7e205183153d3c026d8417b0`.
- **Scope proof (16 files)**: `redaction.py`, `scan_render.py`,
  `plans/`, `package.json`, and `.github/workflows/` are unchanged.
  Changes are confined to `scan.py`, test files, public contract docs
  (7 READMEs + SKILL.md + AGENTS.md), and self-eval evidence.

## Why this matters

The scanner correctly raises HIGH secret findings for credentials embedded in
MCP configuration, but `scan_mcp()` also copies each repository-controlled MCP
server `command` and `url` verbatim into `surface.mcp_servers`. That public
surface is serialized to `--json`, rendered into Markdown/stdout, and written
to the default 0600 temporary full report. The doctor therefore detects a
credential and immediately persists the same value into logs and artifacts.

This is the same data-minimization failure family Plan 049 fixed for hook
commands, but MCP inventory was not included in that implementation. The fix
must reuse the existing `redact_secret_values()` boundary, keep raw MCP data
available for security detection, and expose only a report-safe copy. It must
not weaken secret detection, hide server attribution, or redesign the public
report.

## Mechanical reproduction

Reproduced independently on `11e3a71` in a temporary repository on
2026-07-18. The sentinel is generated at runtime and must never be committed or
printed by an implementation test.

The fixture contains:

- a minimal `AGENTS.md`;
- `.mcp.json` with one MCP server;
- the same generated credential-shaped sentinel inside both `command` and
  `url`.

The current report facts are:

```text
secret findings:                 2
JSON contains sentinel:          true
Markdown contains sentinel:      true
temporary full report contains:  true
surface command contains:        true
surface URL contains:            true
security finding message contains sentinel: false
```

The finding itself is already safe — it names type and path only. The leak is
the independent inventory object:

```python
report["surface"]["mcp_servers"][0]["command"]
report["surface"]["mcp_servers"][0]["url"]
```

## Current state

All excerpts and line references below were re-verified at `11e3a71`.

### MCP discovery returns raw repository-controlled strings

`scripts/scan.py:1264-1292`:

```python
def scan_mcp(root, ctx=None):
    ...
    for name, cfg in block.items():
        cfg = cfg if isinstance(cfg, dict) else {}
        url = cfg.get("url") or cfg.get("endpoint") or ""
        transport = cfg.get("type") or ("remote" if url else "stdio")
        env = cfg.get("env") if isinstance(cfg.get("env"), dict) else {}
        servers.append(
            {
                "config": rel(path, root),
                "name": name,
                "transport": transport,
                "command": str(cfg.get("command", "")),
                "url": str(url),
                "env_keys": sorted(env.keys()),
            }
        )
```

`name`, `transport`, `command`, `url`, and environment-map keys are controlled
by the audited repository. A newline/backtick in these values is also capable
of breaking the Markdown presentation even when it is not a credential.

### The raw object is published before serialization

`scripts/scan.py:1860-1895`:

```python
mcp = scan_mcp(root, ctx)
hooks = scan_hooks(root, ctx)
safe_hooks = public_hooks(hooks)
...
surface = {
    "mcp_servers": mcp,
    ...
    "hooks": safe_hooks,
}
...
"security": security_findings(root, files, mcp, hooks, permissions, ctx),
```

The design already distinguishes raw hook data (for detection) from
`safe_hooks` (for reports), but publishes raw MCP data directly.

### Markdown renders the public object verbatim

`scripts/scan_render.py:290-296`:

```python
for s in mcp:
    where = s["url"] or s["command"] or "(unspecified)"
    lines.append(
        f"  - `{s['name']}` ({s['transport']}) → `{where}` — {s['config']}"
    )
```

`write_report_file()` then writes the complete report dictionary to an
unpredictable 0600 temp file. Its filesystem safety is correct; the problem is
that the report object still contains the credential.

### The correct redaction seam already exists

`scripts/scan.py:1370-1379`:

```python
def public_hooks(hooks):
    """Return report-safe hook inventory while retaining diagnostic shape."""
    return [
        {
            **hook,
            "event": _md_safe(hook.get("event", "")),
            "command": redact_secret_values(hook.get("command", "")),
        }
        for hook in hooks
    ]
```

`scripts/redaction.py:72-91` single-sources `secret_hits()` and
`redact_secret_values()`, including placeholder and code-identifier
exemptions. Do not create another regex list.

### Existing tests prove only the hook boundary and MCP env omission

`tests/test_scan.py:2172-2228` checks a generated hook credential across JSON,
Markdown, SARIF, and PR review. `tests/test_scan.py:2352-2377` checks that MCP
`env` values are omitted from the surface, but does not place a credential in
`command`, `url`, server name, transport, or an env key. There is no test for
the default full-report temp file.

### Public wording is hook-specific

The safety model in every README currently says:

```markdown
Secret findings name type/path without reproducing values; risky hook snippets
are redacted in JSON, Markdown, SARIF, and PR feedback.
```

`SKILL.md` similarly promises only that hook inventory is redacted. Public
behavior changes must update English and all six translations in one PR.

### Root guidance is evidence-bound and has a 10 KiB budget

`AGENTS.md` is 10,227 bytes, and the repository contract enforces
`<= 10,240`. Its Safety line currently says:

```markdown
- Never commit secrets, tokens, or credentials.
```

The exact proposed replacement is:

```markdown
- Never commit or report secrets or credentials.
```

That replacement is one byte larger (10,228 bytes total), preserves the
credential prohibition, adds the report boundary, and stays under the budget.
Do not add a new root bullet or raise the budget.

## Vetted findings and prioritization

The independent nine-category audit on `11e3a71` also reproduced or verified
the following candidates. They are recorded in `plans/README.md`, but are not
part of Plan 062:

- guard multi-file apply can leave a pre-commit hook installed after a later
  workflow write fails (correctness, M effort, broader rollback design);
- eval `usage` string metadata is not included in Plan 051 redaction
  (security, S);
- a stored record can say `passed: true` while carrying an explicit non-zero
  runner/judge exit (test/integrity, S);
- root-generated eval tasks discard already-computed evidence and root Node
  runtime inference does not abstain on conflicting pins (architecture, M/S);
- `actionlint` is promised but not executed by required gates (tests/DX, S);
- `npm run format` rewrites 130 tracked files and makes current eval evidence
  stale (DX, policy/migration decision);
- current release/pre-commit/version prose is ahead of the last fully
  successful release, and the release guide conflicts with PR-only governance
  (docs, S);
- Node 16/20 and Python 3.9 support lines are EOL (migration, breaking);
- provider-neutral reports, eval-gate config, read-only MCP eval verification,
  and public JSON schema identities are grounded direction options.

The MCP report leak ranks first because it is a reachable default scan path,
re-persistes a credential the scanner already recognizes, has HIGH security
impact, and has a small existing redaction seam plus deterministic end-to-end
tests. The other candidates remain separate plans/features rather than being
mixed into this security patch.

## Target contract

All items are required:

1. Security detection continues to inspect the complete original MCP config and
   raw MCP server data. Existing HIGH secret findings, insecure HTTP findings,
   credential-shaped env-key findings, severities, categories, paths, and scan
   exit codes are unchanged.
2. Every repository-controlled string published under
   `surface.mcp_servers` is report-safe:
   - `name`;
   - `transport`;
   - `command`;
   - `url`;
   - every `env_keys` item.
   Repository-controlled MCP names/keys interpolated into security finding
   messages are subject to the same boundary; safe inventory must not coexist
   with a leaking finding message.
3. `command`, `url`, names, transport labels, and env keys reuse
   `redact_secret_values()` for complete high-confidence secret spans. No
   prefix/suffix of a matched credential remains.
4. The same public strings are Markdown-safe: embedded newlines collapse and a
   repository-controlled backtick cannot close the renderer's inline-code
   span. Reuse `_md_safe`; do not create a renderer-only escape vocabulary.
5. Placeholder/example values preserve the shared redactor's existing
   semantics and are not converted into findings.
6. The generated sentinel is absent from:
   - the complete report object / serialized `--json`;
   - rendered Markdown;
   - the default full JSON temp report;
   - monorepo package reports and batch `repos` reports (inherited through
     `scan_repo`, not a second implementation);
   - SARIF and PR-review payloads (recall guard; they should remain safe even
     though inventory is not currently mapped as a finding).
7. A stable `<redacted:TYPE>` marker remains in the public MCP inventory so the
   diagnostic is useful. Config attribution and transport/command-vs-URL shape
   remain available.
8. The public JSON shape remains additive-compatible: no MCP server field is
   removed or renamed.
9. `--no-security` may suppress the findings section but must not re-expose raw
   MCP fields. `--fail-on-security` retains its current exit behavior.
10. `scripts/redaction.py` patterns and exemptions remain the single source.
    Do not expand secret detection in this plan.
11. All seven README translations and `SKILL.md` state that
    repository-controlled hook and MCP command/URL inventory is redacted before
    report serialization.
12. `AGENTS.md` carries the stable “never commit or report secrets” invariant,
    stays `<= 10,240` bytes, and its repository-contract test pins the Safety
    section wording.
13. The self-eval pack adds one objective root-guidance task for the
    no-secret-report rule, remains 100/Grade A, and binds the exact current
    `AGENTS.md` and task bytes. Refresh notes honestly: no `eval_run.py`
    runner/judge model call; answers manually maintained by the AI
    implementation workflow; offline regex regrade is not an independent model
    benchmark.

## Design

### Preserve raw detection and publish a sanitized copy

Mirror the existing `public_hooks()` split:

```python
def public_mcp_servers(servers):
    safe = []
    for server in servers:
        safe.append(
            {
                **server,
                "name": _md_safe(
                    redact_secret_values(server.get("name", ""))
                ),
                "transport": _md_safe(
                    redact_secret_values(server.get("transport", ""))
                ),
                "command": _md_safe(
                    redact_secret_values(server.get("command", ""))
                ),
                "url": _md_safe(
                    redact_secret_values(server.get("url", ""))
                ),
                "env_keys": [
                    _md_safe(redact_secret_values(key))
                    for key in server.get("env_keys", [])
                ],
            }
        )
    return safe
```

The exact formatting may differ, but the ownership must not:

```python
raw_mcp = scan_mcp(root, ctx)
safe_mcp = public_mcp_servers(raw_mcp)

surface["mcp_servers"] = safe_mcp
security_findings(..., raw_mcp, raw_hooks, ...)
```

`build_project_snapshot()` receives the safe `surface`; it only needs server
names. Do not mutate `raw_mcp` in place before `security_findings()`.

`security_findings()` must still inspect raw values for detection, but any raw
MCP `name` or env-key string interpolated into a finding message must pass
through `redact_secret_values()` and then `_md_safe()`. Do not solve safe
inventory while leaving a second leak in finding attribution.

### Keep rendering dumb

The preferred fix is a safe public report object, not one redactor in JSON and
another in `scan_render.py`. `render_surface()` should be able to render
`surface.mcp_servers` without seeing raw values. A small defense assertion or
comment in `scan_render.py` is acceptable only if review proves it is needed;
do not add a second secret-pattern implementation there.

### Test serialized end products

Model the new regression after
`ExtendedSurfaceTests.test_hook_secret_is_redacted_from_every_report_surface`.
Generate the sentinel through string concatenation. Assert both:

- the raw fixture causes HIGH secret findings and the expected MCP transport
  diagnostics;
- every serialized end product excludes the sentinel and includes a redaction
  marker.

Create and unlink a real `write_report_file()` output so the temp-report
boundary is tested, not inferred from `json.dumps(report)`.

SARIF and PR review currently carry findings, not extended-surface inventory.
Their assertions are negative recall guards only: require sentinel absence, but
do not require an MCP-inventory redaction marker in those two artifacts. The
marker must be present in JSON/Markdown/temp-report inventory.

Also cover:

- a placeholder remains unchanged/non-finding;
- newline/backtick text cannot inject a Markdown line/fence;
- `--no-security` still exposes only the safe inventory;
- name/env-key sentinels are sanitized in both inventory and finding
  attribution while raw env-value detection remains attributed correctly.

### Root guidance and self-eval

Replace, do not append, the Safety line in `AGENTS.md`. Add a section-scoped
assertion to the existing repository-contract test in
`tests/test_action_metadata.py` and keep the 10,240-byte assertion last.

Add one task such as:

```json
{
  "id": "secret-report-safety",
  "prompt": "May repository tooling commit or report secret credential values? Answer briefly.",
  "timeout_s": 120,
  "check": {
    "type": "regex",
    "value": "(?i)(?:no|never).*(?:commit|report).*(?:secret|credential)"
  }
}
```

The manual answer must be derivable from `AGENTS.md` alone. Keep task order
stable by placing it with the other safety tasks; update the self-eval README
count and explanation.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused scan tests | `python3 -m unittest discover -s tests -p 'test_scan.py' -v` | all pass |
| Repository contract | `python3 -m unittest discover -s tests -p 'test_action_metadata.py' -v` | all pass; AGENTS budget green |
| README/docs sync | `python3 scripts/check_readme_sync.py` | seven READMEs aligned |
| Regrade self-eval | `python3 scripts/eval_run.py --regrade benchmark/self-eval/results-after.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md -o benchmark/self-eval/results-after-graded.json` | updated evidence-bound artifact |
| Score self-eval | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | all tasks pass; 100/Grade A |
| Full local gate | `npm run check` | lint, Python/Node tests, packed candidate all pass |
| Self scan | `python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json --check-baseline --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts --no-report-file` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | 100/100, Grade A |
| Diff hygiene | `git diff --check` | exit 0 |

## Scope

**In scope**:

- `scripts/scan.py`
- `tests/test_scan.py`
- `tests/test_action_metadata.py`
- `AGENTS.md`
- `SKILL.md`
- `README.md`
- `README.zh-CN.md`
- `README.ja.md`
- `README.es.md`
- `README.ko.md`
- `README.pt-BR.md`
- `README.fr.md`
- `benchmark/self-eval/tasks.json`
- `benchmark/self-eval/results-after.json`
- `benchmark/self-eval/results-after-graded.json`
- `benchmark/self-eval/README.md`
- `plans/062-redact-mcp-surface-secrets.md` and `plans/README.md` only for the
  later closeout PR

**Conditionally in scope only if the preferred safe-object design cannot meet a
test without it**:

- `scripts/scan_render.py` — renderer defense only; no duplicate patterns

**Out of scope**:

- `scripts/redaction.py` pattern/placeholder/identifier behavior — reuse it
  byte-for-byte unless a failing existing test proves the shared helper itself
  is broken; that is a STOP condition for this plan.
- Expanding secret regex breadth, entropy detection, PII detection, encryption,
  or historical Git scanning.
- Eval `usage` metadata redaction (separate reproduced Plan 051 follow-up).
- Guard-apply transactions, stored eval exit evidence, actionlint, formatter
  policy, release docs, runtime-version migrations, MCP eval verification, or
  public report schema versioning.
- Removing MCP fields, hiding server existence, or changing scan/SARIF/PR
  finding identity, severity, category, or exit codes.
- Writing into the audited repository.

## Git workflow

- This plan lands first as a plan-only PR and must pass all nine required
  contexts before implementation starts.
- Implementation branch: `fix/062-redact-mcp-surface-secrets`.
- Commit: `fix(scan): redact MCP surface secrets`.
- One smallest backward-compatible security patch PR; no direct push to
  `main`.
- Run Standards/Spec review against this plan and include the mechanical
  sentinel matrix in the PR body.
- Wait for all nine required checks, require zero unresolved threads, then
  squash-merge and delete the implementation branch.
- Land a final plans-only closeout PR with the reviewed head, merge SHA,
  evidence, and all done criteria checked.
- Release classification: bugfix/security hardening → patch if released alone.

## Steps

### Step 1: Add a failing MCP cross-surface regression (RED)

Add a generated-sentinel test in `tests/test_scan.py` before changing
production code.

It must prove the current leak by asserting:

- HIGH secret findings still exist;
- the sentinel is absent from the complete report JSON, Markdown, temp report,
  SARIF, and PR-review payload;
- a redaction marker exists in `surface.mcp_servers.command/url` and in the
  JSON/Markdown/temp-report inventory that contains those fields;
- config/name/transport attribution remains;
- the temp file is cleaned in `finally`.

**Verify**:

```bash
python3 -m unittest discover -s tests -p 'test_scan.py' -v
```

Expected RED: only the new MCP report-safety test fails because the sentinel is
still present in `surface.mcp_servers` and its serialized report surfaces.

### Step 2: Add the report-safe MCP boundary

Implement `public_mcp_servers()` next to `public_hooks()` and use it only for
the public `surface`. Keep raw MCP data flowing to `security_findings()`.

Sanitize every repository-controlled public MCP string with the shared
redactor, then `_md_safe`. Preserve the field names/list shape.

**Verify**:

```bash
python3 -m unittest discover -s tests -p 'test_scan.py' -v
```

Expected GREEN: the new sentinel matrix and all existing scan/security tests
pass.

### Step 3: Add recall and injection guards

Extend the focused tests for:

- placeholder values;
- command and URL credentials;
- server name, transport, and env-key strings;
- embedded newline/backtick content;
- `--no-security`;
- monorepo and batch inheritance if the primary unit test does not already
  exercise their nested report shape.

Do not merely test the helper. Serialize the final report artifacts.

**Verify**:

```bash
python3 -m unittest discover -s tests -p 'test_scan.py' -v
python3 -m unittest discover -s tests -p 'test_sarif.py' -v
python3 -m unittest discover -s tests -p 'test_pr_review.py' -v
```

### Step 4: Update every public contract

Update English plus all six translated READMEs and `SKILL.md` to say that
repository-controlled hook and MCP command/URL inventory is redacted before
JSON/Markdown/report serialization. Translate prose only; keep headings, code,
tables, and link targets aligned.

Replace the exact `AGENTS.md` Safety line with the one-byte-larger
no-commit/no-report invariant. Add a section-scoped repository-contract
assertion and leave the 10 KiB budget unchanged.

**Verify**:

```bash
wc -c AGENTS.md
python3 scripts/check_readme_sync.py
python3 -m unittest discover -s tests -p 'test_action_metadata.py' -v
```

Expected: `AGENTS.md <= 10240`; seven READMEs aligned; focused metadata tests
green.

### Step 5: Refresh self-eval evidence honestly

Add the objective no-secret-report task and its manual answer. Update the
self-eval README count/explanation and note to Plan 062. Do not invoke any
runner or judge model. Run only offline regex regrade and score with current
evidence.

**Verify**:

```bash
python3 scripts/eval_run.py \
  --regrade benchmark/self-eval/results-after.json \
  --tasks benchmark/self-eval/tasks.json \
  --workdir . \
  --evidence AGENTS.md \
  -o benchmark/self-eval/results-after-graded.json
python3 scripts/eval_run.py \
  --score benchmark/self-eval/results-after-graded.json \
  --tasks benchmark/self-eval/tasks.json \
  --workdir . \
  --evidence AGENTS.md \
  --require-current-evidence \
  --fail-under 80
```

Expected: 40/40 tasks pass, score 100/Grade A, evidence SHA values match disk,
and notes accurately state the manual AI implementation protocol.

### Step 6: Run all gates and review

```bash
npm run check
python3 scripts/check_readme_sync.py
python3 scripts/scan.py . \
  --baseline .ai-harness-doctor/scan-baseline.json \
  --check-baseline \
  --fail-on-security \
  --fail-on-gaps \
  --fail-on-semantic \
  --fail-on-conflicts \
  --no-report-file
python3 scripts/check_drift.py . --strict
git diff --check
```

Standards review must confirm stdlib-only deterministic sanitization, no
duplicate pattern source, all-language docs, and a current self-eval artifact.
Spec review must trace the generated sentinel through every final report
surface and prove raw detection remains unchanged.

Open the implementation PR only after local gates are green. Wait for all nine
required contexts and zero unresolved threads before merge.

## Test plan

- Generated credential in MCP `command` and `url`:
  - HIGH finding remains;
  - sentinel absent from report JSON/Markdown/default temp report;
  - marker present in sanitized MCP inventory.
- Generated credential-shaped server name/transport/env key:
  - safe public strings;
  - finding attribution remains safe and useful.
- Placeholder/example:
  - no false secret finding;
  - placeholder semantics unchanged.
- Markdown injection:
  - embedded newline/backtick cannot create an extra list item, heading, or
    code span.
- `--no-security`:
  - findings hidden as requested;
  - raw inventory still never leaks.
- Monorepo/batch:
  - nested `report.surface.mcp_servers` inherits the same boundary without a
    separate redactor.
- Repository contract:
  - Safety section contains “never commit or report secrets/credentials”;
  - `AGENTS.md <= 10240`.
- Self-eval:
  - new task passes;
  - all task IDs unique;
  - evidence hashes current.

## Done criteria

- [x] A generated MCP credential is absent from final JSON, Markdown, temp
      report, SARIF, and PR-review serialization.
- [x] `surface.mcp_servers` keeps all existing fields and carries stable
      redaction markers instead of raw matched values.
- [x] Raw MCP data still drives all existing security findings, severity, and
      exits.
- [x] All repository-controlled public MCP strings are redacted and
      Markdown-safe; placeholders retain existing behavior.
- [x] `--no-security`, monorepo, and batch reports cannot bypass sanitization.
- [x] No new secret-pattern or renderer-local redaction implementation exists.
- [x] All seven READMEs and `SKILL.md` document the MCP inventory guarantee.
- [x] `AGENTS.md` records the no-report invariant and remains within 10 KiB.
- [x] The expanded self-eval pack is current and 100/Grade A with honest
      manual-protocol notes (40/40 tasks).
- [x] Focused tests, `npm run check`, package candidate, self scan, strict drift,
      and all nine required CI contexts pass.
- [x] Standards/Spec review passes, PR is squash-merged, branch deleted, and
      plans-only closeout is merged.

## STOP conditions

Stop and report instead of improvising if:

- the sentinel can reach another report field not listed here;
- the fix would require redacting before security detection or changing a
  finding/exit;
- removing the leak requires deleting/renaming MCP report fields;
- the shared redactor must change its detection/exemption semantics;
- `AGENTS.md` cannot stay `<= 10,240` without deleting an unrelated invariant
  or increasing the budget;
- public behavior cannot be described consistently in every required README;
- self-eval cannot stay evidence-current and 100/A;
- any required CI context is red/pending or a review conversation unresolved.

## Maintenance notes

- Any future report field carrying repository-controlled command, URL, name,
  env-key, or free text must use a report-safe copy before serialization.
- Keep raw-versus-public variable naming explicit in `scan_repo`; raw values
  are for detection, public values are for reports.
- Cross-surface tests must inspect final serialized artifacts. A helper-only
  test is insufficient.
- Plan 062 closes MCP inventory only. Eval usage metadata and guard
  transactions remain separately recorded candidates.
