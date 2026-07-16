# Plan 037: Make installer filesystem changes and ownership state transactional

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md` unless a reviewer told you they maintain the index.
>
> **Drift check (run first)**:
> `git diff --stat 660977e..HEAD -- bin/cli.js tests/test_cli.py bin/cli.test.js README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md benchmark/self-eval/results-after-graded.json`
> If an in-scope file changed, compare the current-state excerpts with live
> code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: L
- **Risk**: HIGH
- **Depends on**: Plans 008 and 011 (DONE)
- **Category**: bug
- **Planned at**: commit `660977e`, 2026-07-16
- **Implementation**: in progress on `fix/037-transactional-installer`

## Implementation evidence

- The pre-fix failpoint reproduced both inconsistency classes: failed first
  install left adapter/payload files without a manifest; failed uninstall
  deleted an adapter while preserving a manifest that still claimed it.
- The implementation adds a schema-1 sidecar journal without changing manifest
  schema 2, a token-owned process lock with dead-owner recovery claim, contained
  product-managed path allow-list, exact path/backup fingerprints including
  modes, write-ahead expected states, fsync ordering, and exact next-manifest
  digest commit detection.
- Focused tests now cover caught first-install/update/uninstall failures, three
  interruption phases, idempotent recovery, concurrent commands, malformed /
  escaping / symlinked journals, tampered backups, post-crash external edits,
  lock cleanup, and update-nudge separation from the ownership ledger.
- Final local baseline before PR: 689 Python tests, 26 Node tests, 56 installer
  lifecycle tests, self-eval 33/33, strict drift 100/A, and synchronized
  trilingual docs.

## Why this matters

The ownership manifest authorizes every later installer update and deletion,
but `install`, `uninstall`, and `update` mutate adapters/payloads first and
replace the manifest last. If final manifest replacement fails, the command
returns non-zero while leaving filesystem changes committed against the old
ledger. A first install leaves unowned files that later runs treat as user
collisions; a failed uninstall deletes files while the old manifest still
claims them.

Plans 008 and 011 made individual writes ownership-aware and made
`manifest.json` replacement atomic. They did not make the *combined*
filesystem-plus-ledger operation transactional. Add a durable standard-library
transaction journal with contained path snapshots, deterministic recovery, and
an expected next-manifest digest. This must cover caught errors and process
interruption, not just the existing test-only replacement exception.

## Current state and reproduction

- `bin/cli.js:338-366` writes `manifest.json` atomically by temp file + rename.
  Its failure injection correctly preserves old manifest bytes.
- `bin/cli.js:949-1045` installs payload/adapters, cleans stale outputs, and only
  then calls `recordInstalls([], manifest)`.
- `bin/cli.js:1049-1091` deletes owned outputs before `writeManifest(manifest)`.
- `bin/cli.js:1094-1184` refreshes all installed outputs before final manifest
  replacement.
- `tests/test_cli.py:285-307` asserts only that an injected manifest replacement
  failure preserves manifest bytes and removes the manifest temp file. It does
  not assert filesystem rollback.
- Existing safety primitives to preserve:
  - `mutationPathViolation` / `assertSafeMutationPath` reject symlink parents
    and escapes;
  - `outputAllowedForRecord` rejects manifest-injected external output paths;
  - `writeOwnedFile`, `syncOwnedLink`, and `removeOwnedOutput` preserve
    unowned/edited content;
  - manifest schema 2 remains the public ownership ledger.

Verified at `660977e` with isolated `HOME` and project:

```text
FIRST_INSTALL
returncode=1
manifest_exists=false
project/.cursor/commands/harness-scan.md exists=true
project/.ai-harness-doctor/payload/SKILL.md exists=true

UNINSTALL
returncode=1
manifest bytes unchanged=true
manifest install count=1
project/.cursor/commands/harness-scan.md exists=false
```

Both failures used
`AI_HARNESS_DOCTOR_TEST_MANIFEST_WRITE_FAILURE=1`. The first creates untracked
managed-looking content; the second destroys content while preserving stale
authorization state.

## Target transaction contract

1. `install`, `uninstall`, and `update` are logical transactions spanning all
   managed filesystem mutations and final manifest replacement.
2. Before the first mutation, create a unique transaction directory below the
   safe global state directory, for example
   `~/.ai-harness-doctor/transactions/<id>/`.
3. The journal is versioned, atomically replaced, mode `0600`, and contains
   only:
   - transaction ID/state;
   - command kind;
   - original manifest SHA-256 or explicit absence;
   - ordered path snapshots;
   - later, the SHA-256 of the exact serialized next manifest.
   Never store credentials, host environment, command arguments unrelated to
   recovery, or paths outside validated mutation roots.
4. Before each path's first mutation, durably snapshot its lexical prior state:
   - absent;
   - regular file bytes + mode;
   - symlink target;
   - directory tree needed for rollback, without following symlinks.
   Persist the journal entry and backup bytes before changing that path.
5. Snapshot a path only once. Later writes in the same transaction roll back to
   the state before the command, not an intermediate state.
6. Every installer mutation must route through transaction-aware helpers:
   file create/replace/unlink, symlink create/unlink, recursive owned-directory
   replacement, stale cleanup, and empty-parent removal. Direct mutating
   `fs.*Sync` calls in installer paths are forbidden unless the journal itself
   is being written.
7. Just before final manifest replacement:
   - serialize the exact next manifest once;
   - persist its SHA-256 as `nextManifestDigest` in the journal;
   - atomically replace manifest with those exact bytes.
8. Recovery resolves the manifest/journal crash window:
   - if current manifest digest equals `nextManifestDigest`, mutations committed;
     delete the journal only;
   - otherwise restore all snapshots in reverse order, restore original
     manifest presence/bytes, then delete the journal;
   - if journal/backup validation is malformed, escaping, symlinked, missing,
     or ambiguous, fail closed without mutating managed paths.
9. Run recovery before every strict installer manifest read for
   install/update/uninstall. The best-effort interactive update nudge must not
   recover or mutate transaction state; it silently skips when a journal is
   present.
10. On a caught mutation/final-manifest error, synchronously roll back and
    surface the original error plus rollback status. If rollback itself fails,
    keep the journal/backups and fail with explicit manual-recovery guidance.
11. Abrupt termination recovery must be testable without real `SIGKILL`.
    Add test-only failpoints after at least:
    - first managed write/delete;
    - journal receives `nextManifestDigest` but before manifest rename;
    - manifest rename but before journal cleanup.
    A fresh CLI process must recover deterministically.
12. Preserve user edits/collisions exactly. Transaction rollback must never
    overwrite a path that changed externally after its snapshot; detect digest
    mismatch and fail closed with the journal intact.
13. Keep manifest schema 2 unless a stored manifest field is strictly required.
    Prefer the sidecar journal so old packages can still read the ownership
    ledger. If schema 3 is unavoidable, STOP for a migration review.
14. Keep Node >=16 standard library only and do not alter install destinations,
    public command syntax, link/copy philosophy, or adapter contents.

## Commands you will need

| Purpose | Command | Expected |
|---|---|---|
| Installer tests | `python3 -m unittest discover -s tests -p 'test_cli.py' -v` | all pass |
| Node tests | `node --test bin/*.test.js` | all pass |
| JS lint | `npm run lint:js` | exit 0 |
| Python lint | `npm run lint:py` | exit 0 |
| Docs sync | `npm run lint:docs` | aligned |
| Full gate | `npm run check` | all pass |
| CLI smoke | `node --check bin/cli.js && node bin/cli.js help` | exit 0 |
| Self scan | `python3 scripts/scan.py . --fail-on-security` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | 100/A |
| Eval regrade | `python3 scripts/eval_run.py --regrade benchmark/self-eval/results-after.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md -o benchmark/self-eval/results-after-graded.json` | writes result |
| Eval gate | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | 33/33 A |

## Scope

**In scope**:

- `bin/cli.js`
- `tests/test_cli.py`
- `bin/cli.test.js` only for pure transaction helpers if useful
- `README.md`
- `README.zh-CN.md`
- `README.ja.md`
- `SKILL.md`
- `AGENTS.md`
- `benchmark/self-eval/results-after-graded.json`
- `plans/README.md` and this plan for status/evidence

**Out of scope**:

- Python scanner/Treat/drift mutation engines.
- Guard repository mutations (`guard --apply/remove`); they do not use the
  installer ownership manifest.
- Changing install destinations, manifest ownership semantics, adapter formats,
  or link/copy defaults.
- Network update-nudge behavior except skipping during incomplete transaction.
- Cross-device atomic rename claims between HOME and project roots.
- Automatic repair of malformed journals.
- Runtime dependencies, a database, or OS-specific filesystem watchers.

## Git workflow

- Branch: `fix/037-transactional-installer`
- Commit: `fix(installer): make ownership mutations transactional`
- One implementation PR; conventional English commit.
- Required before merge: drift, lint, Node 16/20/22, self-test, and Python
  3.9/3.10/3.12 all green. Admin bypass only after green checks and resolved
  discussions.

## Steps

### Step 1: Strengthen the failure reproductions

Extend `tests/test_cli.py` so the existing manifest-replacement failpoint proves:

- failed first Cursor project install leaves no adapter, payload, manifest, or
  transaction temp state;
- failed update restores every prior adapter/payload byte and old manifest;
- failed uninstall restores deleted adapters/payload and old manifest;
- user-edited preserved files remain byte-identical in all failures.

Assert paths and bytes, not only process status. These tests must fail against
`660977e` exactly as the reproduction above.

**Verify**: focused tests fail because adapter/payload changes survive the
manifest failure.

### Step 2: Build contained durable journal and snapshot primitives

Add small helpers near manifest state:

- canonical transaction root/path construction;
- atomic journal serialization and parsing;
- safe recursive lexical snapshot/restore without symlink following;
- digest/mode validation;
- transaction begin, snapshot-once, expected-manifest marker, commit cleanup,
  rollback, and startup recovery.

Reuse the existing mutation containment checks. Validate every journal-derived
path again before read/restore/delete. Backups must live inside the transaction
directory and use non-predictable names; journal file/dirs reject symlinks.

Unit/integration tests must cover absent/file/symlink/directory snapshots,
permissions where portable, duplicate snapshot suppression, malformed journal,
missing backup, escaping path, and external post-snapshot modification.

**Verify**: helper tests pass; malformed/escaping recovery mutates nothing.

### Step 3: Route every installer mutation through the transaction

Thread a transaction object through the installer-only mutation helpers:

- `writeOwnedFile`;
- `syncPayload`;
- `syncOwnedLink`;
- `removeOwnedOutput`;
- stale cleanup and owned directory replacement;
- empty-parent cleanup.

Do not transaction-wrap read-only planning/digest checks. Replace `fail()` calls
inside an active installer transaction with catchable typed errors or an
equivalent mechanism so outer rollback always runs before process exit. Keep
the public error prefix and exit codes compatible.

Use one transaction for `--agent all` and shared payload changes, not one per
agent.

**Verify**: first-install/update/uninstall replacement-failure tests roll back
all filesystem state and clean the completed transaction directory.

### Step 4: Close interruption windows with digest-based recovery

Compute the final manifest bytes once. Persist their digest to the journal,
then atomically write those bytes. On command startup:

- old manifest digest/absence + active journal => reverse rollback;
- exact next manifest digest + journal => committed cleanup only;
- any other state => fail closed and retain evidence.

Add subprocess failpoints for interruption after a mutation, before manifest
rename, and after manifest rename. Start a fresh process and assert the correct
rollback/commit behavior, then run ordinary update/uninstall to prove the
ledger remains usable.

**Verify**: all interruption recovery cases pass without sleeps or real signals.

### Step 5: Document and institutionalize atomic installer state

Update synchronized READMEs and `SKILL.md`: ownership-aware install/update/
uninstall either commits filesystem plus manifest together or recovers from the
durable journal on the next strict installer command. Explain that malformed or
ambiguous recovery state fails closed and never gets silently discarded.

Condense this invariant into `AGENTS.md`, keep it under the strict size
threshold, and honestly refresh the evidence-bound self-eval artifact.

**Verify**: docs sync, 33/33 evidence gate, self scan, strict drift.

### Step 6: Full verification and PR evidence

Run all commands in the table. In the PR, inspect the nine required contexts
and ensure the failure tests execute on Python 3.9/3.10/3.12 and Node
16/20/22-compatible code. Record PR/check evidence in this plan and mark DONE
only after merge.

## Test plan

- Existing final manifest replacement failure:
  first install, update, uninstall.
- Abrupt interruption:
  after first mutation, pre-manifest, post-manifest/pre-cleanup.
- Snapshots:
  absent, file, symlink, directory, mode, duplicate path.
- Recovery validation:
  malformed journal, missing backup, escape, symlinked journal path,
  unexpected current manifest digest, externally modified path.
- Ownership:
  unowned collision and user-edited managed file never overwritten.
- Modes:
  Claude/non-Claude, project/global, copy/link, shared payload, `--agent all`.
- No leaked `.tmp`, backup, or journal after successful commit/rollback.

## Done criteria

- [ ] Injected manifest failure leaves filesystem and manifest exactly as before.
- [ ] Failed first install leaves no managed residue or ownership state.
- [ ] Fresh process recovers pre-manifest interruption by rollback.
- [ ] Fresh process recognizes post-manifest commit and only cleans journal.
- [ ] Ambiguous/malformed recovery fails closed with evidence retained.
- [ ] External post-snapshot edits are never overwritten during rollback.
- [ ] All installer mutations are transaction-aware; no bypassing direct writes.
- [ ] Existing ownership, symlink, user-edit, legacy migration, shared-payload,
      copy/link, and cursor-root tests remain green.
- [ ] Manifest schema remains backward-compatible schema 2.
- [ ] Trilingual docs, SKILL, AGENTS, and self-eval are current.
- [ ] Full local gate and all nine PR contexts pass.

## STOP conditions

Stop and report if:

- A backward-compatible recovery protocol cannot distinguish manifest-committed
  from manifest-not-committed after process interruption.
- Correct rollback requires following symlinks or restoring outside validated
  mutation roots.
- Transaction support requires manifest schema 3 or breaking existing records.
- Backing up managed files can capture user-owned repository content not already
  authorized by manifest ownership.
- Windows junction/symlink restoration cannot be represented safely with
  Node 16 stdlib.
- The implementation would claim cross-filesystem atomicity rather than logical
  journal recovery.
- In-scope code has drifted from `660977e` enough to invalidate the design.

## Maintenance notes

- `manifest.json` is authorization evidence; the journal is temporary recovery
  evidence. Neither is a disposable cache.
- Journal-derived paths are untrusted local state and need the same containment
  validation as manifest-derived paths.
- Reviewers should scrutinize the exact ordering: snapshot durable, mutate,
  expected digest durable, manifest atomic replace, journal cleanup.
- Never add a new installer mutation helper without transaction snapshot
  coverage and a rollback assertion.
