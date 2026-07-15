# Plan 008: Make every installer mutation ownership-aware and preserve repository state

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update this plan's status row in
> `plans/README.md`.
>
> **Drift check (run first)**:
> `git diff --stat b3dd9e3..HEAD -- bin/cli.js bin/cli.test.js tests/test_cli.py README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md`
> If any in-scope file changed, compare the current-state excerpts below with
> live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: M
- **Risk**: MED
- **Depends on**: none
- **Category**: correctness / safety / DX
- **Planned at**: commit `b3dd9e3`, 2026-07-15

## Why this matters

Project-scoped Codex/Cursor/Gemini installs currently use the repository's
`.ai-harness-doctor/` directory as a disposable copied payload. That directory
is now also the documented home of `scan-baseline.json` and user rule plugins.
Installing, updating, or uninstalling an adapter can therefore delete the
repository's reviewed debt register and custom rules. Adapter and Claude
command files are also overwritten/deleted by fixed filename without proving
that this tool owns their current contents.

The installer must treat user/repository state as non-destructive by default:
payload bytes need their own managed subdirectory, and every existing adapter
or command must be overwritten/removed only with positive ownership evidence.

## Current state

- `bin/cli.js:123-139` recursively removes a destination before copying:

  ```js
  function copyDir(src, dest) {
    removePath(dest);
    ensureDir(dest);
    // ...
  }

  function copyPayload(dest) {
    removePath(dest);
    ensureDir(dest);
    // copies SKILL.md, scripts/, references/, assets/
  }
  ```

- `bin/cli.js:396-401` assigns two incompatible meanings to the same project
  directory:

  ```js
  function neutralPayloadPath(project) {
    return project ? path.join(project, '.ai-harness-doctor') : homePath('.ai-harness-doctor');
  }

  function neutralLinkPath(project) {
    return project ? path.join(project, '.ai-harness-doctor', 'payload') : homePath('.ai-harness-doctor', 'payload');
  }
  ```

  A copy install uses `.ai-harness-doctor/`; a link install already uses
  `.ai-harness-doctor/payload`.

- `bin/cli.js:376-387` writes generated adapters unconditionally. The Claude
  command path at `bin/cli.js:419-429` does the same through `copyFile`.

- `bin/cli.js:497-540` uninstalls payloads and every known adapter path with
  recursive/unconditional removal. For project installs, line 514 removes the
  whole `.ai-harness-doctor/` tree.

- `bin/cli.js:141-180` tracks only `{agent, project, link, installedAt}`. It
  does not record the exact paths or content digests that a particular install
  owns.

- `README.md:232` promises installs are idempotent. `AGENTS.md:56-58` requires
  repository-derived mutations to preserve safety boundaries.

- Reproduced in an isolated temporary git repository:
  - create `.ai-harness-doctor/scan-baseline.json` and
    `.ai-harness-doctor/rules/custom.py`;
  - run `install --agent cursor --project`;
  - both files are missing afterward, although the command exits 0.
  A separate isolated run confirmed a user-created
  `.cursor/commands/harness-scan.md` is overwritten at install and deleted at
  uninstall.

Follow the existing guard ownership model in `bin/cli.js:737-1017`: managed
files use positive markers/byte identity, edited files are skipped rather than
destroyed, and symlink paths are rejected.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused installer tests | `PYTHONPATH=tests python3 -m unittest tests.test_cli -v` | all pass |
| Node tests | `node --test bin/*.test.js` | all pass |
| JS syntax/lint | `node --check bin/cli.js && npm run lint:js` | exit 0 |
| Docs sync | `python3 scripts/check_readme_sync.py` | OK |
| Full gate | `npm run check` | exit 0 |
| Self checks | `python3 scripts/scan.py . && python3 scripts/check_drift.py . --strict` | no security/gap regressions; drift grade A |

## Scope

**In scope**:

- `bin/cli.js`
- `bin/cli.test.js`
- `tests/test_cli.py`
- `README.md`
- `README.zh-CN.md`
- `README.ja.md`
- `SKILL.md`
- `AGENTS.md`
- `plans/README.md`

**Out of scope**:

- Changing where scan baselines or custom rules live.
- Changing guard installation/removal semantics; use its ownership pattern as
  an exemplar only.
- Adding runtime dependencies.
- Redesigning the agent/adapters supported by the package.
- Removing backward compatibility for existing manifest records.

## Git workflow

- Branch: `fix/nondestructive-installer-ownership`
- Commit: `fix(installer): preserve user-owned harness state`
- Use one focused PR, squash-merge only after every CI check passes.
- Do not publish a version in this PR.

## Steps

### Step 1: Lock the destructive cases in end-to-end tests

Extend `tests/test_cli.py` using its existing isolated `HOME` and temporary
project helpers. Add tests that run the real Node CLI and prove:

1. A Cursor project copy install preserves byte-identical:
   - `.ai-harness-doctor/scan-baseline.json`;
   - `.ai-harness-doctor/rules/custom.py`;
   - an unrelated file below `.ai-harness-doctor/`.
2. `update` preserves the same files.
3. `uninstall --agent cursor --project` removes only managed payload/adapter
   files and preserves the baseline/rules/unrelated file.
4. An unowned existing `.cursor/commands/harness-scan.md`,
   `~/.codex/prompts/harness-scan.md`,
   `~/.gemini/commands/harness/scan.toml`, or Claude command is never silently
   overwritten.
5. A managed adapter edited after install is not deleted or overwritten by
   update/uninstall; the CLI prints an actionable `manual-merge`/`skipped`
   status.
6. Existing clean installs remain idempotent.

The tests must never use the real user home.

**Verify**: the new preservation/ownership tests fail on the current
implementation for the expected reason, while pre-existing tests still pass.

### Step 2: Separate managed payload from repository state

Make copy and link installs use the same payload location:

```text
<project>/.ai-harness-doctor/payload/
~/.ai-harness-doctor/payload/
```

`copyPayload()` may replace only that managed `payload/` subtree. It must never
recursively remove the parent `.ai-harness-doctor/`.

Add a narrow legacy migration:

- Existing manifest records without per-file ownership remain readable.
- On update, old root-level managed children (`SKILL.md`, `scripts/`,
  `references/`, `assets/`) may be removed only when they can be positively
  identified as this package's payload (for example, `SKILL.md` frontmatter
  names `ai-harness-doctor` and the expected managed child set is present).
- Never remove `manifest.json`, `scan-baseline.json`, `drift-baseline.json`,
  `rules/`, or unknown files.
- New adapters must point at the new `payload/` path.

Do not infer ownership merely from the directory name.

**Verify**: project/global copy install, update, and uninstall tests preserve
all user state and leave no stale managed root-level payload after a safe
legacy migration.

### Step 3: Record exact owned files and content digests

Version the manifest schema additively. Each install record should carry the
managed output paths and the digest of the last content written (or an
equivalent deterministic ownership record). Preserve reading v1 records.

Before writing/removing an adapter or command:

- absent file: write and record ownership;
- owned file whose current digest equals the recorded digest: safe to update or
  remove;
- unowned existing file: do not overwrite; report a manual merge and leave it
  byte-identical;
- owned file edited since install: do not overwrite/delete; report it as
  modified and preserve the manifest evidence needed for later cleanup.

Use Node standard-library `crypto`; do not add dependencies. Keep manifest
writes deterministic except for existing timestamps.

For a legacy manifest with no file list, adopt a file only if it is
byte-identical to the content the current package would generate. Otherwise
preserve it as unowned.

**Verify**: focused tests cover create, idempotent update, package-content
update, user edit, unowned collision, legacy adoption, and safe uninstall.

### Step 4: Apply the ownership contract to every installer surface

Use the same helper for:

- Claude skill payload and five slash commands;
- Codex prompts;
- Cursor project commands;
- Gemini commands;
- shared neutral payload;
- copy and link modes.

Do not let uninstalling one non-Claude agent delete a shared payload while
another manifest record still needs it. Remove a payload only after the last
record that references it is removed.

Preserve current destination semantics unless the move to `payload/` requires
an adapter pointer update.

**Verify**: an `--agent all` install followed by uninstalling one agent leaves
the other three operational; final uninstall removes only pristine managed
files.

### Step 5: Document and institutionalize non-destructive ownership

Update synchronized README prose to state:

- repository state and installer payload are separate;
- existing unowned/edited files are preserved and reported;
- uninstall removes only byte-verified managed content.

Update `SKILL.md` and `AGENTS.md` with the maintenance invariant. Keep all three
README fenced blocks/table/link structure synchronized.

**Verify**: docs sync, focused tests, full gate, self scan, and strict drift.

## Test plan

- End-to-end real CLI tests in `tests/test_cli.py`; do not mock filesystem
  mutation.
- Pure manifest/digest helper tests may live in `bin/cli.test.js`.
- Required cases:
  - project baseline/rules survive install, update, uninstall;
  - global manifest survives shared-payload refresh;
  - user-owned name collision is preserved;
  - edited managed adapter is preserved;
  - pristine managed adapter is safely updated/removed;
  - shared payload reference counting;
  - legacy manifest migration;
  - symlink refusal remains intact.

## Done criteria

- [ ] No installer code recursively removes `.ai-harness-doctor/`; only its
      positively-owned `payload/` child may be replaced.
- [ ] The isolated reproduction preserves baseline and custom rule bytes across
      install, update, and uninstall.
- [ ] All adapter/command overwrites and removals require ownership evidence.
- [ ] Existing manifests migrate without losing user data.
- [ ] Multi-agent installs do not remove a shared payload prematurely.
- [ ] No writes reach the real user home during tests.
- [ ] `npm run check` exits 0 and strict self-drift remains grade A.
- [ ] No files outside Scope are modified.

## STOP conditions

- A safe migration cannot distinguish legacy managed payload from user-owned
  content without deleting unknown files.
- The proposed manifest format requires breaking existing installations rather
  than additive migration.
- Ownership enforcement requires changing public agent destination paths beyond
  the documented payload subdirectory.
- A test would touch the real home directory.
- A verification command fails twice after a reasonable correction.

## Maintenance notes

Installer ownership is a safety boundary. Future agents/adapters must register
their exact output paths and digests rather than adding another unconditional
copy/remove loop. Reviewers should scrutinize any `rmSync`, `unlinkSync`, or
`writeFileSync` added to installer flows and require a user-edit preservation
test.
