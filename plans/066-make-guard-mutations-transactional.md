# Plan 066: Make guard install and removal transactional across every managed file

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md` unless a reviewer maintains the index separately.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat 0232401..HEAD -- \
>   bin/cli.js tests/test_cli.py bin/cli.test.js \
>   README.md README.zh-CN.md README.ja.md README.es.md README.ko.md \
>   README.pt-BR.md README.fr.md SKILL.md references/maintenance-contract.md \
>   AGENTS.md benchmark/self-eval/results-after-graded.json
> ```
>
> If any in-scope file changed since this plan was written, compare the
> "Current state" excerpts and both mechanical reproductions against the live
> code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P0
- **Effort**: M
- **Risk**: MED (the change strengthens an explicit mutation command, but it
  spans repository files and the Git common directory; rollback must never
  overwrite concurrent user edits)
- **Depends on**: Plans 004, 008, 011, 037, and 044 (DONE; their containment,
  ownership, atomic-write, transaction, and recovery contracts are exemplars,
  not a reason to couple guard state to the installer manifest)
- **Category**: correctness / security
- **Planned at**: commit `0232401`, 2026-07-19
- **Status**: DONE — plan PR
  [#289](https://github.com/NieZhuZhu/ai-harness-doctor/pull/289);
  implementation PR
  [#290](https://github.com/NieZhuZhu/ai-harness-doctor/pull/290), squash merge
  `28150ef`; both passed all nine required contexts.

## Implementation evidence

- The two pre-fix fault injections were rerun as integration tests: a caught
  install failure and a caught remove failure now restore exact pre-command
  existence, bytes, full `0o7777` mode, and transaction-created parents.
- Guard state is separate from the HOME installer ledger and lives below the
  resolved Git common directory. Journal authority is limited to the fixed
  hook/provider/`AGENTS.md` allow-list; every apply and restore rechecks lexical
  symlink containment.
- Fault tests cover install/remove crash recovery, atomic-write temp cleanup,
  a second crash during restore, explicit commit and rollback retirement
  points, post-crash external edits, malformed/tampered/escaping/symlinked
  state, live lock/owner protection, unselected-provider symlinks, every
  provider's parents/modes, and linked-worktree/common-dir recovery.
- Standards and Spec reviews found four implementation gaps before commit:
  committed cleanup could trigger a false rollback, atomic sibling temp files
  were initially unjournaled, unrelated provider symlinks were over-probed, and
  a sibling worktree could not recover the recorded worktree. Each was fixed
  with a regression test; the final `bits-code-guard` report has no remaining
  P0–P2 findings.
- Final local verification on the reviewed tree: `npm run check` passed 885
  Python tests, 51 Node tests, lint, synchronized docs/adapters, and the packed
  candidate; scan exited 0; strict drift was 100/A; current-evidence self-eval
  was 40/40 at 100/A; npm 10.8.2 public-registry audit reported zero
  vulnerabilities; `AGENTS.md` was 10,237 bytes.
- PR #290 head `1abb451` passed `drift`, `lint`, Node 16/20/22, `self-test`,
  and Python 3.9/3.10/3.12. It had zero unresolved review threads and was
  squash-merged as `28150ef`; the implementation branch was deleted.

## Why this matters

`guard --apply` and `guard --remove --apply` are one logical operation over a
Git hook, one to three provider files, and the maintenance block in
`AGENTS.md`. The current implementation validates every path first but then
writes or removes each path directly. If any later write fails, earlier changes
remain committed. A failed install can leave an active pre-commit hook without
the CI workflows or maintenance contract; a failed removal can delete the hook
while leaving the rest of the guard installed. The command exits non-zero, but
the user's repository no longer matches either the before state or the printed
plan.

This is the same consistency class that Plan 037 closed for adapter
installation, except guard state deliberately has no ownership manifest and
crosses two roots: the worktree and Git common directory. Add a guard-specific,
durable, contained transaction under the Git common directory. It must roll
back caught failures immediately, recover interrupted mutations on the next
mutating guard command, preserve every pre-command byte and mode, and fail
closed rather than overwriting a path changed after interruption.

## Current state and mechanical reproduction

### The plan is complete before mutation, but application is a naked loop

`bin/cli.js:2674-2688`:

```js
function applyGuardChanges(changes, target, hookPath) {
  const gitRoot = gitCommonDir(target);
  for (const change of changes) {
    assertSafeMutationPath(change.path === hookPath ? gitRoot : target, change.path);
  }
  for (const change of changes) {
    assertSafeMutationPath(change.path === hookPath ? gitRoot : target, change.path);
    if (change.remove) {
      removePath(change.path);
    } else if (change.write) {
      ensureDir(path.dirname(change.path));
      fs.writeFileSync(change.path, change.after, { encoding: 'utf8', mode: change.mode || 0o644 });
      if (change.mode) fs.chmodSync(change.path, change.mode);
    }
  }
}
```

The first loop rejects known symlink/escape hazards before writing, which must
remain. The second loop has no snapshot, journal, rollback, atomic per-file
replacement, or catch boundary.

`bin/cli.js:2691-2715` calls the loop directly after printing the full plan:

```js
if (apply) {
  applyGuardChanges(changes, target, gitPath(target, 'hooks/pre-commit'));
  console.log(`\nApplied ${changes.filter((change) => change.write || change.remove).length} change(s).`);
}
```

An ordinary filesystem exception therefore escapes as a Node stack trace as
well as leaving partial state.

### Install failure leaves only the first mutation

Reproduced against `main@0232401` in an isolated temporary repository. The
repository root was made non-writable after `git init`; its Git hook directory
remained writable:

```text
command:
  node bin/cli.js guard <repo> --apply --provider github
returncode: 1
failure: EACCES creating <repo>/.github/workflows
<repo>/.git/hooks/pre-commit exists: true
<repo>/.github/workflows/harness-drift.yml exists: false
<repo>/.github/workflows/harness-checkup.yml exists: false
AGENTS.md changed: false
```

The hook is applied first because `plannedGuardInstallChanges()` appends it
before provider files and `AGENTS.md` (`bin/cli.js:2568-2618`).

### Removal failure deletes only the first mutation

Starting from a complete GitHub guard install, the workflow directory was made
non-writable before removal:

```text
command:
  node bin/cli.js guard <repo> --remove --apply
returncode: 1
failure: EACCES unlinking harness-drift.yml
pre-commit hook preserved: false (it was deleted)
harness-drift.yml preserved: true
harness-checkup.yml preserved: true
AGENTS.md preserved: true
```

`plannedGuardRemoveChanges()` also orders the hook before provider files and
`AGENTS.md` (`bin/cli.js:2621-2671`), so the inverse partial state is stable and
not timing-dependent.

### Existing transaction machinery is an exemplar, not a drop-in wrapper

- `bin/cli.js:153-267` already supplies exact lexical fingerprints, atomic
  writes, durable fsync, and no-symlink tree copies.
- `bin/cli.js:417-692` supplies write-ahead snapshots and transactional file,
  directory, unlink, and symlink helpers.
- `bin/cli.js:788-1045` validates durable journals and recovers interrupted
  installer transactions without trusting journal paths.
- `bin/cli.js:1129-1179` serializes installer commands, rolls back caught
  errors, and reports a clean failure.

Do **not** call `withInstallerTransaction()` from guard. Its transaction state
is rooted in the user's HOME, its allow-list is derived from adapter install
surfaces, and commit is coupled to replacing `manifest.json`. Guard ownership
is repository-local marker/template truth; making it depend on the unrelated
global installer ledger would create a new correctness and availability bug.
Extract narrowly reusable primitives only when doing so reduces risk without
changing Plans 037/044 behavior.

## Target transaction contract

1. One `guard --apply` or `guard --remove --apply` is one transaction over all
   planned `write`/`remove` changes. It either reaches the entire printed plan
   or restores the exact pre-command state.
2. Transaction state is repository-local and untracked, below the resolved Git
   common directory (for example
   `<git-common-dir>/ai-harness-doctor/guard-transaction/`). Do not use the
   worktree, HOME installer state, or a user-configurable external path.
3. The transaction authorizes only:
   - the resolved `hooks/pre-commit` path below the same Git common directory;
   - root `AGENTS.md`;
   - the exact repository-relative file names in `GUARD_CI_FILES`.
   Journal contents never expand that allow-list.
4. Before activating a transaction, re-read every planned mutation target and
   verify it still matches the `before` state observed during planning. A
   changed path aborts with no mutation. Compare exact bytes, type, and mode;
   do not rely on the text preview or marker alone.
5. Build the complete journal and backups in a mode-`0700` temporary directory,
   fsync them, then atomically rename it to the single active transaction path.
   A crash before activation leaves no recoverable mutation and may only leave
   a safely identifiable temporary directory.
6. The mode-`0600`, versioned journal contains only the transaction kind
   (install/remove), resolved target and Git common roots, process ownership
   metadata needed for serialization, ordered authorized snapshots, and
   write-ahead expected states. Do not log file contents, credentials, or
   backups in errors/output.
7. Snapshot exact prior state for every target before the first mutation:
   absent, or regular-file bytes plus mode. Guard never mutates a symlink,
   non-file target, or arbitrary directory. Backup files stay inside the
   transaction directory and are digest-verified before restore.
8. Journal missing parent directories that guard creates, so rollback removes
   only directories that were absent before the command and remain empty.
   Never recursively delete a parent directory during rollback. If a concurrent
   actor added content, retain the journal and fail closed.
9. Before each file write/remove, durably journal the currently expected state
   and intended next state. After the mutation, verify exact resulting
   fingerprint and durably mark it complete. Per-file writes use atomic
   temp-file + rename and preserve the intended mode:
   - explicit `change.mode` wins;
   - otherwise preserve an existing regular file's mode;
   - otherwise use `0644` subject to the process umask.
10. A caught error rolls snapshots back in reverse order, restores exact bytes
    and modes, removes only transaction-created empty parents, cleans the
    transaction, and exits non-zero with a concise `ai-harness-doctor:` error
    (no raw Node stack). If rollback cannot prove the current path is the
    journaled post-mutation state, it must not overwrite it; retain recovery
    evidence and name its location without exposing backup content.
11. An abrupt exit after one or more mutations is recovered by the next
    **mutating** guard invocation for the same Git common directory before a new
    plan is applied. Recovery verifies the recorded target still resolves to
    the same repository/common directory and revalidates every path against the
    hard-coded guard allow-list. A dry-run must not silently mutate; if recovery
    is pending, report it and instruct the operator to rerun with `--apply`.
12. Serialize guard mutations for one Git common directory. If a valid active
    journal belongs to a live process, fail without recovering over it. A dead
    owner may be recovered. Present-but-malformed, symlinked, escaping,
    unauthorized, missing-backup, or digest-mismatched state fails closed and
    stays available for inspection.
13. Recovery is idempotent. A crash during rollback may be retried; already
    restored snapshots are recognized from the journaled expected/prior state.
    Clean transaction state only after every authorized path matches its prior
    fingerprint.
14. Preserve the current ownership policy byte-for-byte:
    - foreign hooks/workflows remain `manual-merge`;
    - edited managed workflows remain `skip` on remove/reinstall;
    - only pristine templates or the exact shipped hook block are removable;
    - the encoded trailing whitespace around the maintenance contract restores
      exactly.
15. Preserve containment and worktree behavior. The hook is validated relative
    to `gitCommonDir(target)`; repository files are validated relative to the
    resolved worktree. External symlinks never receive reads, backups, writes,
    or rollback.
16. Keep Node >=16 standard library only. Do not add a runtime dependency,
    change provider templates, alter public arguments, create a general-purpose
    repository transaction API, or reuse the installer manifest as guard state.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Focused guard tests | `python3 -m unittest tests.test_cli.CliIntegrationTests.test_guard_apply_rolls_back_all_files_on_mid_transaction_failure tests.test_cli.CliIntegrationTests.test_guard_remove_rolls_back_all_files_on_mid_transaction_failure tests.test_cli.CliIntegrationTests.test_guard_recovers_interrupted_transaction -v` | exit 0 |
| CLI integration tests | `python3 -m unittest tests.test_cli -v` | exit 0 |
| Node tests | `node --test bin/*.test.js` | all pass |
| Full gate | `npm run check` | lint, all Python/Node tests, and packed candidate pass |
| CLI smoke | `node --check bin/cli.js && node bin/cli.js help` | exit 0 |
| Self scan | `python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | exit 0, 100/100 grade A |
| Eval gate | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | exit 0, every task passes |
| Docs sync | `python3 scripts/check_readme_sync.py` | all seven READMEs aligned |
| Adapter sync | `python3 scripts/gen_adapters.py --check` | 18 adapters match |
| Dependency audit | `npm audit --audit-level=high` with the CI-supported npm and public registry | zero high/critical vulnerabilities |

The maintainer's local `/usr/local/bin/npm` may be npm 6 even when Node is
newer. If `npm run check` or `npm audit` fails inside npm itself rather than the
repository, use the exact npm 10.8.2 CLI (the reviewed CI-era client) with
`registry=https://registry.npmjs.org`; record the command and do not relabel a
tooling failure as a green gate.

## Scope

**In scope**:

- `bin/cli.js`
  - guard-specific state path, journal validation, serialization, snapshot,
    atomic mutation, rollback, and recovery helpers;
  - `applyGuardChanges()` and the `guard()` apply boundary;
  - narrowly shared raw fingerprint/fsync helpers only if installer behavior
    remains byte-compatible.
- `tests/test_cli.py`
  - test-first fault injection, interruption recovery, fail-closed state, mode,
    containment, concurrent-edit, and provider coverage.
- `bin/cli.test.js` only if pure guard transaction helpers are exported for
  focused tests; prefer black-box isolated-repository tests for the mutation
  contract.
- Public behavior docs:
  - `README.md`, `README.zh-CN.md`, `README.ja.md`, `README.es.md`,
    `README.ko.md`, `README.pt-BR.md`, `README.fr.md`;
  - `SKILL.md`;
  - `references/maintenance-contract.md`.
- `AGENTS.md` — replace or compact an existing mutation-state invariant; keep
  the repository-specific 10,240-byte budget.
- `benchmark/self-eval/results-after-graded.json` — refresh honestly only if
  `AGENTS.md` bytes change.
- `plans/066-make-guard-mutations-transactional.md` and `plans/README.md` for
  final evidence/status.

**Out of scope**:

- Adapter `install`/`uninstall`/`update`, manifest schema, or the existing
  HOME installer transaction and recovery semantics.
- Python `canonicalize --apply`, `check_drift --fix --apply`, or baseline
  mutation. They require separate ownership and rollback analysis.
- Changes to guard templates, their runtime behavior, provider detection, PR
  review posting, eval thresholds, or pre-commit framework hooks.
- Treating foreign/edited files as owned, introducing a new guard ownership
  manifest, or deleting transaction evidence automatically when validation is
  ambiguous.
- Cross-repository distributed transactions, network storage guarantees, or
  claims stronger than local filesystem rename/fsync semantics.
- Runtime dependencies or a broad split/refactor of the 2,700-line CLI.

## Git workflow

- Start the implementation from latest `main` after the plan-only PR merges.
- Branch: `fix/066-transactional-guard`
- Commit: `fix(guard): make repository mutations transactional`
- Tests and behavior land in the same commit/PR. Conventional Commit message in
  English.
- This is a backward-compatible bugfix: patch release unless implementation
  changes the CLI/state contract beyond this plan (a STOP condition).
- Do not merge until all nine required contexts are green: `drift`, `lint`,
  `node (16)`, `node (20)`, `node (22)`, `self-test`, `unittest (3.9)`,
  `unittest (3.10)`, and `unittest (3.12)`.
- Resolve every review conversation. Admin bypass is allowed only for the
  sole-maintainer self-approval deadlock after all required checks are green,
  never over red/pending checks.

## Steps

### Step 1: Add failing caught-error regression tests

Add test-only guard failpoints that throw after a selected completed mutation;
do not depend only on chmod/permissions, which differ by OS and CI identity.
The failpoint must be inert unless an explicit test environment variable is
set and must never accept repository input.

Write at least:

1. install, fail after the hook mutation;
2. remove from a complete install, fail after hook removal;
3. overwrite/strip case with a prior managed hook plus user lines, proving its
   exact bytes and mode return;
4. codebase provider case, whose three repository files exercise multiple
   parent directories and executable mode.

For each, snapshot the exact pre-command existence, bytes, and mode of every
planned target and relevant parent. Assert non-zero exit, no Node stack trace,
all snapshots restored, no extra empty parent directories, and no transaction
state remains after successful rollback.

**Verify on unpatched `0232401`**: new tests fail because the first mutation
survives. Existing guard idempotency, foreign-file, symlink, provider, and
remove-preservation tests remain green.

### Step 2: Introduce the contained guard transaction and preflight

Add guard-specific helpers near the guard implementation or extract only the
safe raw primitives shared with installer recovery.

- Resolve `target`, `gitCommonDir(target)`, hook, and the fixed CI/AGENTS
  allow-list before touching state.
- Re-read all planned targets as exact lexical snapshots and compare them with
  planning's `before` state. Record modes and absent parent directories.
- Prepare backups/journal in a private temporary directory under the Git common
  directory; atomically activate it.
- Validate state paths and files with `lstat`; reject symlinks and unsupported
  types.

Do not weaken `assertSafeMutationPath` or infer authorization from journal
roots/contents.

**Verify**: unit/integration tests cover absent/existing files, executable
mode, missing parents, a changed target between plan and apply, symlinked state,
malformed JSON, escaping/unauthorized path, and missing/tampered backup.

### Step 3: Route writes and removals through write-ahead state

Replace the naked `applyGuardChanges()` loop:

- journal each next expected state before mutation;
- create parent directories transactionally;
- write regular files through atomic temp + rename;
- unlink only validated regular files;
- verify the post-mutation fingerprint and update the journal;
- inject caught-error and abrupt-exit failpoints only after a completed,
  journaled mutation.

Wrap the apply boundary so ordinary failures trigger rollback and render one
clean CLI error. Keep dry-run planning byte-identical and mutation-free.

**Verify**: Step 1 tests turn green, existing install/remove/idempotency tests
remain green, and the original chmod reproductions either complete fully or
leave every pre-command state intact.

### Step 4: Recover abrupt interruption without overwriting later edits

Add a crash-only test failpoint (exit without in-process rollback) after at
least the first mutation. In fresh processes, cover:

1. interrupted install → next mutating guard invocation restores then applies
   the complete current plan;
2. interrupted remove → next mutating invocation restores then completes
   removal;
3. interruption during rollback → recovery is idempotent;
4. user modifies the journaled path after interruption → recovery refuses to
   overwrite it and retains evidence;
5. live owner → second guard mutation fails without recovery;
6. malformed/symlinked/escaping/tampered recovery state → fail closed;
7. pending recovery + dry-run → no mutation and actionable output;
8. linked worktree/common-dir behavior → hook and worktree paths remain
   correctly separated (skip only where Git worktrees are unavailable).

Tests use isolated temporary repositories and `HOME`; never touch real agent
config or Git hooks.

**Verify**: fresh-process recovery cases pass on supported platforms and leave
no state after a proved rollback/commit.

### Step 5: Document the atomic guard contract

Update the guard section in English and all six translations with one concise
user promise: caught failures roll back; interrupted applies/removals recover on
the next mutating guard command; changed/unsafe recovery state fails closed.

Update `SKILL.md` and `references/maintenance-contract.md` with the operational
boundary, including the Git-common-dir state location and no-overwrite rule.
Compact the existing `AGENTS.md` mutation invariant rather than adding an
unbounded paragraph. Keep `wc -c AGENTS.md <= 10240`.

If `AGENTS.md` changes, update the relevant self-eval answer and perform the
documented offline regrade. State honestly that this is a deterministic regex
regrade of maintained manual-protocol answers, not a new model run.

**Verify**: README sync, `wc -c`, current-evidence eval gate, self scan, and
strict drift all pass.

### Step 6: Run full gates and collect PR evidence

Run every command in the command table with a supported Node/npm/Python setup.
Inspect the complete diff for scope and ensure no test fixture was modified.
Open one implementation PR, verify Standards and Spec independently against
this plan, record the real fault-injection evidence, and wait for all nine
required contexts.

After squash merge, delete the implementation branch. Create a separate
plan-closeout PR that records merge/check/review evidence and changes Plan 066
to DONE; merge that PR only after its own nine contexts are green.

## Test plan

- Caught install failure after first mutation: exact all-path rollback.
- Caught remove failure after first mutation: exact all-path rollback.
- Existing-file overwrite and user-extended hook strip: exact byte/mode
  restoration.
- Codebase provider: three files, two repository parent trees, executable mode.
- Abrupt install/remove interruption: fresh-process recovery.
- Interruption during rollback: idempotent recovery.
- Post-crash external edit: no overwrite, evidence retained.
- Live concurrent guard mutation: serialized refusal.
- Journal/state trust boundary: symlink, malformed, escape, unauthorized target,
  missing backup, backup digest mismatch.
- Worktree/common-dir hook separation.
- Pending recovery on dry-run remains read-only.
- Existing guard dry-run, idempotency, foreign hooks/workflows, edited managed
  files, all providers, and symlink refusal remain green.

Structural patterns:

- `tests/test_cli.py:1127-1188` for full install/idempotency assertions;
- `tests/test_cli.py:1391-1454` for exact removal/user-edit preservation;
- `tests/test_cli.py:1471-1534` for fail-closed symlink mutation;
- `tests/test_cli.py:379-683` for installer fault injection, interruption,
  recovery validation, and concurrent command patterns.

## Done criteria

- [ ] Both pre-fix mechanical reproductions no longer leave partial state.
- [ ] Caught install and remove failpoints restore exact existence, bytes,
      modes, and parent-directory state and emit no raw Node stack.
- [ ] Abrupt install/remove failpoints recover in a fresh process.
- [ ] Recovery refuses to overwrite a post-crash external edit and retains
      validated evidence.
- [ ] Malformed/symlinked/escaping/tampered guard state mutates nothing.
- [ ] One live guard mutation cannot be recovered over by another process.
- [ ] Dry-run with pending recovery writes nothing.
- [ ] Existing guard ownership, provider, idempotency, worktree, and symlink
      tests pass.
- [ ] `python3 -m unittest tests.test_cli -v` exits 0.
- [ ] `node --test bin/*.test.js` exits 0.
- [ ] `npm run check` exits 0, including packed-candidate verification.
- [ ] Self scan exits 0 and strict drift reports 100/100 grade A.
- [ ] Current-evidence self-eval passes every task.
- [ ] All seven READMEs are synchronized; `AGENTS.md` is at most 10,240 bytes.
- [ ] `git status` contains only in-scope files; no fixture changed.
- [ ] Implementation PR has all nine required contexts green, no unresolved
      conversation, and is squash-merged; branch deleted.
- [ ] Closeout PR records actual evidence, turns this plan DONE, passes all nine
      required contexts, is squash-merged, and its branch is deleted.

## STOP conditions

Stop and report instead of improvising if:

- The live `applyGuardChanges()` no longer matches the naked two-loop excerpt,
  or another branch already added guard rollback/recovery.
- The implementation would need to make guard depend on
  `~/.ai-harness-doctor/manifest.json` or the HOME installer transaction.
- Safe recovery requires trusting an arbitrary target/root from journal data
  without proving it belongs to the same Git common directory and fixed guard
  allow-list.
- The proposed rollback would overwrite a path whose current fingerprint is
  not the journaled prior/expected state.
- A test requires mutating the real HOME, current repository hooks, or a shared
  non-temporary Git common directory.
- Preserving exact bytes/modes requires treating a symlink or unsupported
  special file as owned.
- The fix changes foreign-file/manual-merge ownership, provider templates,
  public syntax, or introduces a runtime dependency.
- Windows or linked-worktree behavior cannot be represented safely with the
  same lexical containment contract; report the concrete incompatibility.
- A verification fails twice after a reasonable fix, any required CI context is
  red/pending, or a review conversation remains unresolved.

## Maintenance notes

- Reviewers should scrutinize the recovery authorization boundary more than the
  happy path: journal paths are data, never authority.
- Guard state is intentionally separate from adapter installer state. If the
  two implementations later share helpers, keep roots, allow-lists, commit
  semantics, and recovery stores separate.
- Adding a new `GUARD_CI_FILES` entry must automatically add it to transaction
  authorization, planning snapshots, recovery validation, and provider tests.
- Keep the failpoints test-only and environment-controlled; they must never
  accept repository-derived values or be documented as public API.
- Core Treat/drift mutations remain separate follow-ups. Do not cite this plan
  as proof that every repository write in the product is transactional.
