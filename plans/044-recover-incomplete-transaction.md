# Plan 044: Recover from an incomplete installer transaction directory instead of bricking

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md`.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 21c99a8..HEAD -- \
>   bin/cli.js tests/test_cli.py \
>   README.md README.zh-CN.md README.ja.md SKILL.md AGENTS.md
> ```
>
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts against live code before proceeding. If
> `recoverInstallerTransactions`, `readTransactionDirectory`,
> `beginInstallerTransaction`, or `cleanupTransaction` changed materially, treat
> that as a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: Plan 011 (DONE), Plan 037 (DONE)
- **Category**: bug (correctness — installer crash recovery robustness)
- **Planned at**: commit `21c99a8`, 2026-07-16
- **Implementation**: TODO

## Why this matters

The installer runs `recoverInstallerTransactions()` at the start of **every**
`install`/`update`/`uninstall` command, before it does anything else. Recovery
lists every subdirectory of `~/.ai-harness-doctor/transactions/` and calls
`readTransactionDirectory()` on each, which immediately `fs.lstatSync()`s the
directory's `journal.json`.

If a prior installer process was killed (SIGKILL/SIGTERM, power loss, `kill -9`)
in the narrow window **after** it created the transaction directory
(`fs.mkdirSync(dir)`) but **before** it wrote `journal.json`
(`writeTransactionJournal`), a transaction directory exists on disk with **no
journal**. On the next run, `recoverInstallerTransactions` → `readTransactionDirectory`
does `fs.lstatSync(journalPath)`, which throws `ENOENT`. That error propagates up
through `withInstallerTransaction` and calls `fail("Cannot start installer
transaction: ENOENT ... journal.json")`.

The result is a **permanently bricked installer**: because recovery runs first on
every command, the user can no longer `install`, `update`, **or** `uninstall`
anything — including the tool that would clean up the stray directory — until
they manually `rm -rf` the transaction directory. A premium tool's crash-recovery
must treat an incomplete/journal-less transaction directory as an abandoned
artifact to clean up, not a fatal error.

This same class of failure is already visible as recurring CI flake: the
concurrent-installer test intermittently fails on `unittest (3.9)` with exactly
`Cannot start installer transaction: ENOENT ... journal.json` during its recovery
step (observed on PRs #207 and #211, cleared only by re-running the job).

## Mechanical reproduction

Against `main@21c99a8`, simulate a process killed between `mkdir` and journal
write by hand-creating a journal-less transaction directory:

```bash
tmphome="$(mktemp -d)"; tmpproj="$(mktemp -d)"
echo '{}' > "$tmpproj/package.json"
mkdir -p "$tmphome/.ai-harness-doctor/transactions/1700000000000-123-abcdef"
# note: NO journal.json inside that directory
HOME="$tmphome" AI_HARNESS_DOCTOR_NO_UPDATE_CHECK=1 \
  node bin/cli.js install --agent cursor --project 2>&1 | head -3
echo "exit=$?"
```

Observed on `21c99a8`:

```
ai-harness-doctor: Cannot start installer transaction: ENOENT: no such file or directory, lstat '.../transactions/1700000000000-123-abcdef/journal.json'
exit=1
```

Every subsequent `install`/`update`/`uninstall` in that `HOME` fails the same
way until the directory is removed by hand.

Expected after this plan: recovery cleans up the journal-less directory and the
command proceeds normally (exit 0), while a directory that contains a
*present-but-malformed or unsafe* journal still fails closed exactly as today.

## Current state

### Recovery stats the journal unconditionally

`bin/cli.js:787-797` (`readTransactionDirectory`):

```js
function readTransactionDirectory(dir, allowedRoots, manifest) {
  const id = path.basename(dir);
  const stat = fs.lstatSync(dir);
  if (!stat.isDirectory() || stat.isSymbolicLink()) {
    throw new Error(`unsafe installer transaction directory: ${dir}`);
  }
  const journalPath = path.join(dir, 'journal.json');
  const journalStat = fs.lstatSync(journalPath);   // <-- throws ENOENT if absent
  if (!journalStat.isFile() || journalStat.isSymbolicLink()) {
    throw new Error(`unsafe installer transaction journal: ${journalPath}`);
  }
  ...
```

### The scan aborts on any thrown error

`bin/cli.js:984-1017` (`recoverInstallerTransactions`) iterates entries and calls
`readTransactionDirectory` directly; any thrown error propagates to
`withInstallerTransaction` (`bin/cli.js:1101-1114`), which does
`fail("Cannot start installer transaction: ${error.message}")`.

### The window that creates a journal-less directory

`bin/cli.js:1026-1059` (`beginInstallerTransaction`):

```js
  const dir = path.join(TRANSACTIONS_DIR, id);
  fs.mkdirSync(dir, { mode: 0o700 });          // (1) directory now exists
  const original = manifestState();
  ...
  if (original.kind === 'file') {
    fs.writeFileSync(path.join(dir, 'manifest-original.json'), ...); // (2)
    fsyncFile(...);
  }
  fsyncDirectory(dir);
  writeTransactionJournal(transaction);         // (3) journal.json created
```

A crash between (1) and (3) leaves a directory with no `journal.json` (and
possibly only `manifest-original.json`). `cleanupTransaction` (`bin/cli.js:954-961`)
also removes the whole directory (journal included), so a crash mid-cleanup can
briefly present the same shape.

### Existing recovery security tests (must stay green)

`tests/test_cli.py:471-517` (`test_recovery_refuses_malformed_or_escaping_transaction_journal`)
writes a `journal.json` with broken JSON and with an escaping snapshot path and
asserts recovery **fails** and does not touch anything. `:519`
(`test_recovery_refuses_symlinked_transaction_directory`) and `:575`
(`test_recovery_refuses_tampered_transaction_backup`) similarly require hard
failure. **All of these create a journal that is present but invalid/unsafe** —
none create a journal-*absent* directory. The fix must keep every one of these
failing closed.

## Target contract

1. A transaction directory whose `journal.json` is **absent** (`fs.lstatSync`
   raises `ENOENT`) is an incomplete/abandoned transaction: recovery removes that
   directory (best-effort, contained to `TRANSACTIONS_DIR`) and continues to the
   next entry, instead of throwing.
2. A transaction directory whose `journal.json` is **present but** malformed,
   has an unsafe/escaping root or snapshot, is a symlink, has a bad backup
   digest, etc., still throws and fails the command closed — unchanged from
   today (Plan 011/037 security contract preserved).
3. A **symlinked** or non-directory transaction *entry* still throws
   (unchanged — this is the `entry.isDirectory()`/symlink check in
   `recoverInstallerTransactions`, not the journal-absent case).
4. The cleanup of a journal-less directory is confined to `TRANSACTIONS_DIR`
   (reuse the existing `rawRemovePath`/containment helpers; never remove anything
   outside the transactions directory).
5. Node >= 16 standard library only; no new dependency. Deterministic.

## Design sketch (non-binding)

Distinguish "journal absent" from "journal present but invalid" at the single
`fs.lstatSync(journalPath)` call. For example, in `readTransactionDirectory`
signal the absent case distinctly:

```js
  let journalStat;
  try {
    journalStat = fs.lstatSync(journalPath);
  } catch (error) {
    if (error.code === 'ENOENT') {
      // Incomplete/abandoned transaction: dir created but journal never
      // written (crash between mkdir and journal write), or a concurrent
      // cleanup already removed it. Signal the caller to discard it.
      const incomplete = new Error('installer transaction has no journal');
      incomplete.code = 'TRANSACTION_INCOMPLETE';
      throw incomplete;
    }
    throw error;
  }
```

and in `recoverInstallerTransactions`, wrap the `readTransactionDirectory` call
so that only `TRANSACTION_INCOMPLETE` is caught and turned into a contained
cleanup of that one directory (leaving all other errors to propagate):

```js
    let transaction;
    try {
      transaction = readTransactionDirectory(dir, allowedRoots, manifestForPaths);
    } catch (error) {
      if (error.code === 'TRANSACTION_INCOMPLETE') {
        rawRemovePath(dir);   // contained to TRANSACTIONS_DIR
        continue;
      }
      throw error;
    }
```

The exact mechanism is the executor's choice, but it MUST (a) only treat a
genuinely absent journal as cleanable, (b) leave every present-but-invalid
journal fatal, and (c) confine removal to `TRANSACTIONS_DIR`.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| CLI tests | `python3 -m unittest discover -s tests -p 'test_cli.py' -v` | exit 0 |
| Node CLI tests | `npm test` | all pass |
| CLI syntax/help | `node --check bin/cli.js && node bin/cli.js help` | exit 0 |
| Full quality gate | `npm run check` | all lint + Python + Node tests pass |
| Self scan | `python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0, grade A |
| README synchronization | `python3 scripts/check_readme_sync.py` | exit 0 |
| Adapter synchronization | `python3 scripts/gen_adapters.py --check` | exit 0 |

## Scope

**In scope**:

- `bin/cli.js` — `readTransactionDirectory` (distinguish absent journal) and
  `recoverInstallerTransactions` (clean up + continue on the absent case).
- `tests/test_cli.py` — new regression test(s).
- `AGENTS.md` — one durable invariant line only if it fits under 12288 bytes
  (optional).
- `README.md`, `README.zh-CN.md`, `README.ja.md`, `SKILL.md` — only if a
  user-facing sentence about installer recovery needs it (likely none; keep the
  trilingual READMEs byte-synchronized if touched).
- `plans/044-recover-incomplete-transaction.md`, `plans/README.md`.

**Out of scope**:

- The commit/rollback/backup-digest logic (Plan 011/037) — do NOT weaken any
  present-but-invalid-journal check.
- The `installer.lock` acquisition/mutual-exclusion path.
- Changing `beginInstallerTransaction`'s write ordering (the fix is on the
  recovery side; do not attempt to make the mkdir+journal atomic).
- The MCP server, scan/drift/eval engines.

## Git workflow

- Start from latest `main` after this plan PR merges:
  `fix/044-recover-incomplete-transaction`.
- One implementation PR. Conventional Commits in English, e.g.
  `fix(cli): recover from a journal-less installer transaction directory`.
- Do not push directly to `main`.
- Do not merge until all nine required contexts are green: `drift`, `lint`,
  `node (16)`, `node (20)`, `node (22)`, `self-test`, `unittest (3.9)`,
  `unittest (3.10)`, and `unittest (3.12)`.
- Admin bypass is allowed only for the sole-maintainer approval deadlock after
  required checks are green and every discussion is resolved.

## Steps

### Step 1: Reproduce and characterize

Add a regression test in `tests/test_cli.py` (model after
`test_recovery_refuses_malformed_or_escaping_transaction_journal` at line 471 and
`test_fresh_process_recovers_interrupted_installer_transactions` at line 427):

1. Create a `~/.ai-harness-doctor/transactions/<id>/` directory with **no**
   `journal.json` (optionally containing a stray `manifest-original.json`).
2. Run `install --agent cursor --project` in an isolated `HOME`.
3. Assert: exit code `0`, the install succeeds (`.cursor` appears in the
   project), and the journal-less directory has been removed
   (`transactions/<id>` no longer exists; `transactions/` is empty or gone).

Keep the existing "refuses malformed/escaping/symlinked/tampered" recovery tests
in place — they must remain passing unchanged.

**Verify**: `python3 -m unittest discover -s tests -p 'test_cli.py' -v` → the new
test fails before implementation (recovery aborts with ENOENT), the refusal tests
pass.

### Step 2: Distinguish absent-journal from invalid-journal

Implement the absent-journal signal in `readTransactionDirectory` and the
contained cleanup + `continue` in `recoverInstallerTransactions` per the design
sketch. Do not change any present-but-invalid branch.

**Verify**: `python3 -m unittest discover -s tests -p 'test_cli.py' -v` → the new
test passes; `test_recovery_refuses_malformed_or_escaping_transaction_journal`,
`test_recovery_refuses_symlinked_transaction_directory`,
`test_recovery_refuses_tampered_transaction_backup`,
`test_fresh_process_recovers_interrupted_installer_transactions`, and
`test_concurrent_installer_fails_without_recovering_live_transaction` all still
pass.

### Step 3: Confirm containment

Confirm the cleanup path cannot remove anything outside `TRANSACTIONS_DIR`
(reuse `rawRemovePath` with the transaction dir path, which is always
`path.join(TRANSACTIONS_DIR, entry.name)`), and that a symlinked entry is still
rejected by the existing `entry.isDirectory()`/symlink guard before any cleanup.

**Verify**: `node --check bin/cli.js && node bin/cli.js help` → exit 0; `npm test`
→ all pass.

### Step 4: Optional invariant

If it fits under 12288 bytes, add one concise `AGENTS.md` invariant (installer
recovery cleans up an incomplete/journal-less transaction directory and only
fails closed on a present-but-invalid/unsafe journal). If you edit `AGENTS.md`,
refresh the evidence-bound self-eval via the documented regrade workflow and keep
Grade A. If it does not fit, skip and say so.

**Verify**:

```bash
wc -c AGENTS.md
python3 scripts/check_drift.py . --strict
```

Expected: AGENTS below 12288 bytes (if edited), strict drift Grade A.

### Step 5: Full gate, review, and PR

Run every command in "Commands you will need". Review the diff on two axes:

- standards: Node >=16 stdlib-only, matching tests, no weakening of Plan 011/037
  security checks, trilingual doc parity if touched;
- spec: absent journal → contained cleanup + continue; present-but-invalid
  journal → still fatal; symlinked entry → still fatal; cleanup confined to
  `TRANSACTIONS_DIR`.

Open one implementation PR, wait for all nine contexts, resolve discussions,
squash merge, and record PR/head/check/merge evidence here and in the index.
This is a backward-compatible **patch**.

## Test plan

- New test (in `tests/test_cli.py`): a journal-less transaction directory is
  cleaned up and the command succeeds (exit 0); the transactions dir ends empty
  or absent.
- Preserved tests: `test_recovery_refuses_malformed_or_escaping_transaction_journal`,
  `test_recovery_refuses_symlinked_transaction_directory`,
  `test_recovery_refuses_tampered_transaction_backup`,
  `test_fresh_process_recovers_interrupted_installer_transactions`,
  `test_concurrent_installer_fails_without_recovering_live_transaction` — all
  unchanged and passing.

## Done criteria

- [ ] A journal-less transaction directory is cleaned up; the command exits 0.
- [ ] A present-but-malformed/unsafe journal still fails closed (existing tests
      green).
- [ ] A symlinked/non-directory entry still fails closed.
- [ ] Cleanup is confined to `TRANSACTIONS_DIR`.
- [ ] Behavior change ships with a test in the same PR.
- [ ] `npm run check` passes; `npm test` and `python3 -m unittest ... test_cli.py`
      pass.
- [ ] Self scan exits 0; strict drift is 100/100 Grade A.
- [ ] `AGENTS.md` stays below 12288 bytes (if edited) and self-eval stays Grade A.
- [ ] No runtime dependency added; Node 16 / Python 3.9 remain supported.
- [ ] Implementation PR has all nine required contexts green and is merged.
- [ ] Plan/index contain final PR, CI, and merge evidence.

## STOP conditions

Stop and report instead of improvising if:

- distinguishing "absent journal" from "present-but-invalid journal" cannot be
  done at the `lstatSync` boundary without also catching a genuine unsafe state;
- cleaning up the journal-less directory would require removing anything outside
  `TRANSACTIONS_DIR`;
- an existing recovery-refusal test would have to change to make the new test
  pass (that means the fix is too broad — narrow it);
- `AGENTS.md` cannot stay under 12288 bytes after any consolidation;
- any required CI context is red/pending or a discussion is unresolved.

## Maintenance notes

- The root cause is a non-atomic `mkdir`-then-write-journal window in
  `beginInstallerTransaction`; this plan hardens the *recovery* side (tolerate
  the incomplete artifact) rather than making creation atomic, which keeps the
  change small and does not touch the commit/rollback contract. If creation is
  ever made atomic (e.g. write journal to a temp path and `rename` into place),
  this recovery tolerance remains correct and complementary.
- A reviewer should confirm the ENOENT tolerance is scoped to the *journal*
  stat only, and that every present-but-invalid path still throws.
- The recurring `unittest (3.9)` flake in
  `test_concurrent_installer_fails_without_recovering_live_transaction` should
  stop once recovery tolerates the incomplete directory; if it persists, capture
  the exact failing assertion and re-open.
