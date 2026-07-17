# Plan 058: Make the local all-green command cover the required package gate

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan in
> `plans/README.md` unless a reviewer maintains the index separately.
>
> **Drift check (run first)**:
>
> ```bash
> git diff --stat dca7e18..HEAD -- \
>   package.json CONTRIBUTING.md AGENTS.md \
>   tests/test_action_metadata.py tests/test_package_candidate.py \
>   benchmark/self-eval/tasks.json benchmark/self-eval/results-after.json \
>   benchmark/self-eval/results-after-graded.json benchmark/self-eval/README.md \
>   plans/058-make-local-check-match-required-ci.md plans/README.md
> ```
>
> If any in-scope file changed, compare the "Current state" excerpts against
> live code before proceeding. A semantic mismatch is a STOP condition.

## Status

- **Priority**: P1
- **Effort**: S
- **Risk**: LOW
- **Depends on**: Plan 057 (DONE)
- **Category**: bug / DX / CI parity / docs
- **Planned at**: commit `dca7e18`, 2026-07-17
- **Reconciled (pre-implementation, 2026-07-17)**: still TODO at
  `origin/main` `dca7e18`. No in-scope file
  changed after the previous `87ca71d` baseline; the `check` /
  `check:package`, `CONTRIBUTING.md`, `AGENTS.md`, workflow, and evidence
  contracts still match the reproduction below.
- **Status**: DONE — implemented on `fix/058-local-check-parity` and merged via
  PR [#267](https://github.com/NieZhuZhu/ai-harness-doctor/pull/267)
  (reviewed head `c343d14bfb7cf86fd26742b271c327bdeb470a99`, squash merge
  `b62b32539d07fe5b9122f30275c8b6566917c6fe`), closeout recorded 2026-07-18.

## Implementation and verification evidence (closeout, 2026-07-18)

- **Implementation PR**: [#267](https://github.com/NieZhuZhu/ai-harness-doctor/pull/267),
  reviewed head `c343d14bfb7cf86fd26742b271c327bdeb470a99`, squash-merged to
  `main` as `b62b32539d07fe5b9122f30275c8b6566917c6fe`; the feature branch was
  deleted after merge.
- **Required CI**: exactly 9/9 required checks SUCCESS on the reviewed head —
  drift, lint, self-test, Node 16/20/22, and unittest Python 3.9/3.10/3.12 —
  with zero unresolved review threads before squash merge. Admin bypass was
  used only for the sole-maintainer self-approval deadlock, never over a red
  or pending check.
- **Local gates on the implementation head**: the exact new local aggregate ran
  green — lint, then 844 Python + 51 Node tests, then the packed candidate
  verifier; the focused manifest/workflow suite passed 37 tests.
- **Evidence refresh**: self-eval regraded and scored 39/39, 100/Grade A;
  strict drift 100/Grade A; `AGENTS.md` is 12,231 bytes, under the 12,288-byte
  strict limit.
- **Workflow invariants**: `.github/workflows/test.yml` is unchanged and the
  required lint job still invokes the candidate verifier exactly once; no
  matrix duplication and no runtime/package/release behavior change.
- **Process deviation (recorded, not repaired)**: this plan was written and
  reviewed locally before implementation, but its plan-only PR was never
  landed on `main` first — implementation PR #267 merged while plans 058–060
  existed only in the local audit checkout. This closeout PR records that
  history truthfully rather than rewriting it to look like the standard
  plan-PR-then-implementation-PR loop.

## Why this matters

Plan 057 made packed-candidate verification part of the required `lint` CI
context and release preflight, but the documented local "single all green"
command still runs only lint plus source tests. A contributor can therefore run
the command the repository calls authoritative, see green, and open a PR that
fails the required package gate.

Make `npm run check` compose the same package candidate verifier after lint and
tests, then update the contributor and agent contracts. Keep CI's explicit
single candidate step so it remains visible in job logs and is not multiplied
across matrix jobs.

## Mechanical reproduction

Current `package.json`:

```json
{
  "check": "npm run lint && npm test",
  "check:package": "python3 scripts/check_package_candidate.py"
}
```

Current `CONTRIBUTING.md:51-56`:

```markdown
npm run check          # lint (eslint + ruff + docs + adapters) then tests
...
`npm run check` is the single "all green" entry point
(`npm run lint && npm test`).
```

Current required CI independently runs:

```yaml
- name: Lint (eslint + ruff + docs + adapters)
  run: npm run lint
- name: Verify packed npm candidate
  run: npm run check:package
```

A direct manifest check confirms:

```text
checkIncludesCandidate=false
REPRODUCED: documented local all-green command omits required candidate gate
```

## Current state

### The candidate verifier is already deep and green

`scripts/check_package_candidate.py`:

- creates isolated pack/install/HOME/cache roots;
- packs the exact checkout candidate;
- validates required and forbidden inventory;
- installs the local tarball offline with lifecycle scripts disabled;
- executes the installed package's JSON doctor self-test;
- uses finite argv-based subprocesses.

This plan must compose that existing command; do not duplicate package logic in
npm, docs, or another script.

### Required CI intentionally runs the verifier once

`.github/workflows/test.yml` runs `npm run check:package` exactly once inside
the required `lint` job. The Node 16/20/22 matrix does not repeat it. Preserve
that layout: changing `npm run check` must not force the workflow to call
`npm run check`, because the lint job already runs lint and package verification
as distinct, observable stages while Python/Node tests run in their matrices.

### AGENTS.md and self-eval are evidence-bound

`AGENTS.md` uses "green `npm run check`" as the bugfix-loop baseline. Once the
command becomes the full local gate, add one compact package-candidate invariant
without exceeding the 12 KiB strict drift limit. Any AGENTS byte change requires
an honest manual-protocol refresh/regrade of `benchmark/self-eval/`.

## Target contract

1. `package.json#scripts.check` runs, in fail-fast order:
   - `npm run lint`;
   - `npm test`;
   - `npm run check:package`.
2. The candidate runs only after lint and source tests pass.
3. `check:package` remains a separately callable script and the required
   workflow keeps its explicit one-time step.
4. `.github/workflows/test.yml` must not switch to `npm run check` or run the
   candidate more than once.
5. `CONTRIBUTING.md` describes `npm run check` as lint + Python/Node tests +
   packed candidate verification.
6. The root `AGENTS.md` records that local all-green verification includes the
   packed candidate, and that CI still owns matrix coverage.
7. Add a deterministic test asserting:
   - exact check command order;
   - `check:package` remains independently defined;
   - required CI invokes it exactly once;
   - no Node/Python matrix duplication.
8. Refresh self-eval tasks/results only as needed to bind the new AGENTS bytes
   and to ask one objective question about the local all-green gate. Do not
   claim an external model run.
9. Keep `AGENTS.md` below 12 KiB and strict drift at Grade A.
10. No runtime/package contents, release behavior, or required status contexts
    change.

## Design

Use the simplest npm composition:

```json
"check": "npm run lint && npm test && npm run check:package"
```

Extend `tests/test_action_metadata.py` or
`tests/test_package_candidate.py` with one manifest/workflow contract test.
Prefer the former because it already owns required-workflow structure; avoid
adding a new test module for one assertion.

Add one self-eval task whose answer can be derived solely from current
`AGENTS.md`, for example:

```text
What does the local all-green command verify?
```

The regex must require lint/tests and packed candidate concepts without
hard-coding irrelevant word order.

## Commands you will need

| Purpose | Command | Expected on success |
|---|---|---|
| Manifest/workflow tests | `python3 -m unittest discover -s tests -p 'test_action_metadata.py' -v` | all pass |
| Candidate smoke | `npm run check:package` | package candidate OK |
| Full local gate | `npm run check` | lint, tests, then candidate all pass |
| README/docs | `python3 scripts/check_readme_sync.py` | seven READMEs aligned |
| Self-eval regrade | `python3 scripts/eval_run.py --regrade benchmark/self-eval/results-after.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md -o benchmark/self-eval/results-after-graded.json` | refreshed evidence-bound output |
| Self-eval score | `python3 scripts/eval_run.py --score benchmark/self-eval/results-after-graded.json --tasks benchmark/self-eval/tasks.json --workdir . --evidence AGENTS.md --require-current-evidence --fail-under 80` | all tasks pass, Grade A |
| Self scan | `python3 scripts/scan.py . --baseline .ai-harness-doctor/scan-baseline.json --check-baseline --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts --no-report-file` | exit 0 |
| Strict drift | `python3 scripts/check_drift.py . --strict` | 100/100, Grade A |

## Scope

**In scope**:

- `package.json`
- `CONTRIBUTING.md`
- `AGENTS.md`
- `tests/test_action_metadata.py`
- `tests/test_package_candidate.py` only if the manifest assertion belongs
  naturally there
- `benchmark/self-eval/tasks.json`
- `benchmark/self-eval/results-after.json`
- `benchmark/self-eval/results-after-graded.json`
- `benchmark/self-eval/README.md`
- `plans/058-make-local-check-match-required-ci.md`
- `plans/README.md`

**Out of scope**:

- Changing `.github/workflows/test.yml` execution layout.
- Running candidate verification in every matrix job.
- Changing `check:package` implementation or package inventory.
- Release workflow behavior.
- README translations; contributor/agent maintenance docs are sufficient.
- Adding npm lifecycle scripts.
- Changing required status contexts or branch protection.
- Runtime dependencies.

## Git workflow

- Branch: `fix/058-local-check-parity`.
- Commit: `fix(ci): include package candidate in local check`.
- One focused bugfix PR; do not push directly to `main`.
- Wait for all nine required checks before squash merge.
- Bugfix/DX correction: patch-release material if released alone.

## Steps

### Step 1: Pin the current mismatch as a failing test

Add a test that parses `package.json` and `.github/workflows/test.yml`. Before
the manifest change, require it to fail because `check` omits
`npm run check:package`.

The same test must assert the required workflow still calls the candidate
exactly once, independently from the local aggregate.

**Verify**:

```bash
python3 -m unittest discover -s tests -p 'test_action_metadata.py' -v
```

Expected before Step 2: RED only on local aggregate parity.

### Step 2: Compose the candidate into the local gate

Append `&& npm run check:package` after `npm test` in the check script. Preserve
short-circuit order and the standalone script.

**Verify**:

```bash
npm run check
```

Expected: source lint/tests pass first, then one final
`package candidate OK: ai-harness-doctor@<version>`.

### Step 3: Correct maintainer and agent contracts

Update `CONTRIBUTING.md` comments/prose and one compact AGENTS invariant. Do not
change public product README behavior.

Keep AGENTS under 12 KiB by tightening nearby wording if necessary, without
dropping existing hard constraints.

### Step 4: Refresh evidence honestly

Add/refresh the objective self-eval task, manual-protocol answer, graded output,
date/note, and evidence hashes. Record that no external runner/model was used.

### Step 5: Run gates and review

- **Standards**: exact npm command order, deterministic tests, compact AGENTS,
  honest evidence refresh.
- **Spec**: local aggregate includes candidate; CI remains exactly once; no
  runtime/release changes.

Open one PR, wait for all nine contexts, then squash merge.

## Test plan

- Manifest order and exact standalone candidate command.
- Required CI exactly-once assertion.
- Full `npm run check` executes candidate last.
- Evidence-bound self-eval task.
- Strict AGENTS size/health.

## Done criteria

- [x] `npm run check` is lint → source tests → package candidate.
- [x] `check:package` remains independently callable.
- [x] Required CI still executes candidate exactly once.
- [x] Contributor and AGENTS contracts describe the real gate.
- [x] Self-eval is current, honest, and Grade A (39/39, 100/A).
- [x] AGENTS remains under 12 KiB (12,231 bytes) and strict drift 100/A.
- [x] Full local and nine required CI checks pass (9/9 on PR #267).

## STOP conditions

Stop and report back if:

- composing `check:package` makes required CI execute it more than once;
- the candidate cannot run after tests without relying on changed artifacts;
- AGENTS cannot remain under 12 KiB without removing a hard constraint;
- self-eval cannot express the gate as an objective evidence-only task;
- any required CI context is red or pending at merge time.

## Maintenance notes

- Keep one authoritative local aggregate and one explicit CI candidate step.
- Future required local-only gates must either join `npm run check` or stop
  calling it the single all-green command.
- Matrix compatibility remains CI-owned; local `npm run check` proves the
  current environment plus candidate packaging.
