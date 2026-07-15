# Plan 011: Make installer manifest state fail closed and write atomically

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat b638ad7..HEAD -- bin/cli.js bin/cli.test.js tests/test_cli.py README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md plans/README.md`
> If any in-scope file changed, compare the "Current state" excerpts below with
> the live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: security / correctness
- **Planned at**: commit `b638ad7`, 2026-07-15

## Why this matters

The installer manifest is the ownership ledger that makes update and uninstall
non-destructive. Today any read/parse failure is silently converted into a new
empty manifest, so the next installer command overwrites the evidence needed to
recognize previously managed files. The manifest directory and file also bypass
the installer's symlink-aware mutation guard, allowing a symlink below an
otherwise isolated `HOME` to redirect `manifest.json` writes outside that home.

Manifest state must fail closed: only a genuinely absent manifest may create
fresh state; malformed, unreadable, unsupported, or symlinked state must remain
byte-identical and produce an actionable error. Successful writes should use an
atomic same-directory replacement so interruption cannot leave truncated JSON.

## Current state

- `bin/cli.js:19-20` defines global mutable state directly below the user's
  home:

  ```js
  const MANIFEST_DIR = homePath('.ai-harness-doctor');
  const MANIFEST_PATH = path.join(MANIFEST_DIR, 'manifest.json');
  ```

- `bin/cli.js:274-291` conflates absence, malformed JSON, unsupported shape,
  and I/O failure:

  ```js
  function readManifest() {
    try {
      const parsed = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8'));
      if (!parsed || typeof parsed !== 'object') throw new Error('bad manifest');
      if (!Array.isArray(parsed.installs)) parsed.installs = [];
      // ...
      return parsed;
    } catch (_) {
      return { schemaVersion: 2, version: PACKAGE_VERSION, lastUpdateCheck: 0, installs: [] };
    }
  }

  function writeManifest(manifest) {
    ensureDir(MANIFEST_DIR);
    manifest.schemaVersion = 2;
    fs.writeFileSync(MANIFEST_PATH, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8');
  }
  ```

- Installer output writes already use the stricter boundary. For example,
  `writeOwnedFile()` calls `assertSafeMutationPath()` at `bin/cli.js:140-162`,
  and that helper rejects a target outside the root or through an existing
  symlink at `bin/cli.js:1304-1323`. Reuse this contract for manifest state
  rather than introducing a second path-safety implementation.

- `install`, `uninstall`, and `updateInstalled` all trust this manifest
  (`bin/cli.js:878`, `975`, `1019`). Losing its `installs` array means clean
  managed outputs become unowned and can no longer be safely updated/removed.

- Real isolated reproductions on the planned commit:
  - Seed isolated `HOME/.ai-harness-doctor/manifest.json` with malformed JSON,
    run `install --agent cursor --project` from an isolated repo: exit `0`;
    malformed bytes are replaced by schema v2 with one install.
  - Make isolated `HOME/.ai-harness-doctor` a symlink to an outside directory,
    run the same command: exit `0`; `outside/manifest.json` is created.

- `tests/test_cli.py` has strong ownership/symlink coverage for adapters and
  payloads (`test_project_adapter_install_refuses_symlinked_parent_directory`,
  `test_manifest_cannot_claim_and_delete_external_file`) but no equivalent
  manifest-state regression.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| JS syntax/lint | `node --check bin/cli.js && npm run lint:js` | exit 0 |
| Installer tests | `PYTHONPATH=tests PYTHONWARNINGS='ignore::ResourceWarning' python3 -m unittest tests.test_cli -v` | all pass |
| Node tests | `node --test bin/*.test.js` | all pass |
| Docs sync | `python3 scripts/check_readme_sync.py` | OK |
| Full gate | `npm run check` | exit 0 |
| Self checks | `node bin/cli.js scan . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts && python3 scripts/check_drift.py . --strict` | exit 0; grade A |

## Scope

**In scope**:

- `bin/cli.js`
- `bin/cli.test.js` only for pure exported helper tests if justified
- `tests/test_cli.py`
- `README.md`, `README.zh-CN.md`, `README.ja.md`
- `SKILL.md`
- `AGENTS.md`
- `plans/README.md`

**Out of scope**:

- Changing adapter/payload destinations or manifest schema semantics beyond
  validating the existing schema v1/v2 contract.
- Recovering ownership from arbitrary corrupt bytes.
- Auto-deleting, auto-renaming, or auto-repairing a malformed manifest.
- Changing scan/drift baseline fail-safe behavior; those are read-only debt
  registers, not installer ownership state.
- Adding dependencies or platform-specific locking packages.

## Git workflow

- Branch: `fix/installer-manifest-state`
- Commit: `fix(installer): protect manifest ownership state`
- One focused PR, squash-merged only after all CI checks pass.
- Treat this as a bugfix unless implementation requires a breaking manifest
  format change (a STOP condition).

## Steps

### Step 1: Add end-to-end fail-closed regressions

Extend `tests/test_cli.py` with real CLI subprocess tests using isolated
`ResilientTemporaryDirectory` homes and project cwd values:

1. Malformed JSON remains byte-identical after `install`, `update`, and
   `uninstall`; each command exits non-zero and names the manifest path plus an
   actionable repair/backup instruction.
2. A manifest with non-array `installs` fails closed instead of coercing it to
   `[]`.
3. A manifest with an unsupported future `schemaVersion` fails closed.
4. A symlinked `.ai-harness-doctor` parent is rejected; no outside file appears.
5. A symlinked `manifest.json` is rejected; its target remains byte-identical.
6. A missing manifest still creates valid schema v2 state.

All tests must run from the isolated project directory; never let `--project`
resolve to this repository.

**Verify**: the first five tests fail for the expected reason on the planned
commit, while the missing-manifest test passes.

### Step 2: Separate absent state from invalid state

Refactor `readManifest()` so `ENOENT` is the only condition that returns a new
manifest. Existing files must validate:

- top-level value is a JSON object (not null/array);
- `installs` is an array;
- `schemaVersion` is an accepted legacy/current version and not newer than the
  implementation;
- optional scalar fields have compatible types.

Do not drop individual records merely because an optional field is absent; the
existing `recordWithOutputs()` legacy migration remains responsible for
adopting schema-v1 records. Parse/schema/I/O errors must surface one concise
message without a JavaScript stack trace.

`maybeCheckForUpdate()` is best-effort and must not make `help` fail because the
manifest is corrupt. Give it an explicit best-effort read path that skips the
update check without writing; installer `install`/`update`/`uninstall` remain
strict.

**Verify**: focused malformed/future-schema tests pass; the existing
unreachable-registry/help test remains green.

### Step 3: Apply the mutation boundary to manifest reads and writes

Before reading or mutating state, validate `MANIFEST_PATH` against the canonical
home root with the same symlink-component contract used by guard/installer
outputs. Existing symlinks at the state directory or manifest file must be
rejected rather than followed.

Use `homePath()` (which already canonicalizes macOS `/var` aliases), not raw
`os.homedir()`, for this boundary. Do not weaken `assertSafeMutationPath()` or
allow the manifest itself as a special symlink exception.

**Verify**: both symlink tests pass on supported platforms and skip cleanly
where directory/file symlinks are unavailable.

### Step 4: Write the manifest atomically

Serialize the complete next manifest first, then write a uniquely named
same-directory temporary file and atomically rename it to `manifest.json`.
Requirements:

- create/check the safe parent before opening the temp file;
- use exclusive creation and restrictive permissions for new temp state;
- clean the temp file on any failure;
- never remove or truncate the previous manifest before the replacement is
  ready;
- preserve deterministic JSON formatting and the existing trailing newline.

Add a pure/helper-level test or a subprocess fault-injection seam proving a
failed replacement leaves the previous manifest parseable and byte-identical.
Do not add a runtime dependency.

**Verify**: install/update/uninstall flow and the new failed-write regression
pass; no temp artifacts remain.

### Step 5: Document and institutionalize manifest fail-closed behavior

Update synchronized README installer prose and `SKILL.md` to state that the
ownership manifest:

- is never silently reset when malformed/unsupported;
- rejects symlinked state paths;
- is replaced atomically.

Condense the existing installer invariant in `AGENTS.md` so future manifest
changes require fail-closed parsing, safe mutation containment, and isolated
HOME tests without pushing the file past the strict 12KB grade-A threshold.

**Verify**: docs sync, full gate, self scan, and strict drift.

## Test plan

- Real CLI tests, isolated `HOME` and cwd:
  - missing manifest creates schema v2;
  - malformed JSON preserved;
  - invalid `installs` type preserved;
  - future schema preserved;
  - symlinked state directory/file rejected with no outside write;
  - failed atomic replacement preserves previous bytes;
  - valid schema-v1 migration still works;
  - normal install/update/uninstall remains idempotent.
- Reuse the structural pattern in
  `test_project_adapter_install_refuses_symlinked_parent_directory` and
  `test_legacy_manifest_migrates_managed_payload_without_unknown_file_loss`.

## Done criteria

- [ ] Only an absent manifest creates empty state.
- [ ] Existing invalid/unsupported/unreadable manifest bytes are never changed.
- [ ] No manifest read/write follows a symlink outside canonical HOME.
- [ ] Manifest replacement is same-directory atomic and cleans temp files.
- [ ] Legacy v1 and valid v2 records remain readable.
- [ ] Interactive update nudges remain best-effort and never reset state.
- [ ] `npm run check` passes and self-drift remains grade A.
- [ ] Only in-scope files are modified.

## STOP conditions

- Preserving legacy v1 requires guessing ownership not represented by existing
  byte identity checks.
- Atomic replacement cannot be implemented consistently on Node 16 supported
  platforms without changing the manifest format.
- The fix would make ordinary `help`/read-only commands fail on manifest state.
- A test would use the real HOME or mutate this repository.
- Verification fails twice after a reasonable correction.

## Maintenance notes

The manifest is not a disposable cache; it is authorization evidence for
future writes/deletes. Reviewers should reject broad `catch` blocks that turn
existing manifest failures into empty state, direct `writeFileSync` truncation,
or any manifest path that bypasses the installer mutation boundary.
