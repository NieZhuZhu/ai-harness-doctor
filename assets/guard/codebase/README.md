# Harness guard — Codebase / generic pipeline wiring

`ai-harness-doctor guard --provider codebase` installs two files:

- a portable entrypoint at `.harness-ci/harness-guard.sh` (the actual guard logic), and
- a ready-to-run Codebase pipeline at `.codebase/pipelines/harness-guard.yaml` that
  delegates to that entrypoint (`change`/MR runs `drift`, `cron`/schedule runs `checkup`).

Unlike GitHub Actions or GitLab CI, internal Codebase / Bits pipelines vary between
teams, so the guard keeps its logic in a runner-agnostic shell script and provides the
pipeline YAML as a starting point you can adapt.

## What it does

| Mode | When to run | Behaviour |
|---|---|---|
| `harness-guard.sh drift` | On every merge request | Gates new scan debt (including HIGH security) and then runs `drift . --strict`; non-zero exit fails the check. |
| `harness-guard.sh checkup` | On a schedule (e.g. weekly) | Runs gated `scan` + `drift`, prints both reports, and preserves scan-before-drift exit precedence. |

The script prefers a locally installed `ai-harness-doctor` and falls back to `npx`.
If `.ai-harness-doctor/scan-baseline.json` exists, the scan gate uses it for
pre-existing gap/semantic/conflict debt. The guard never creates or updates the
file, and HIGH security findings remain unsuppressible. Create it manually with
`ai-harness-doctor scan . --write-baseline .ai-harness-doctor/scan-baseline.json`,
review and commit it, then shrink it as debt is repaired.

## Wiring examples

**Bits / Codebase merge-request check** — add a pipeline step:

```sh
sh .harness-ci/harness-guard.sh drift
```

**Scheduled checkup** — add a scheduled pipeline / cron step:

```sh
sh .harness-ci/harness-guard.sh checkup
```

**Jenkins / generic CI**:

```groovy
stage('Harness drift') {
  steps { sh 'sh .harness-ci/harness-guard.sh drift' }
}
```

**Codebase CI (auto-installed)** — `.codebase/pipelines/harness-guard.yaml` is written
for you. It runs `drift` on MR (`change`) events and `checkup` on the `cron` schedule.
Register the cron schedule under the repo's *Codebase CI → Schedules* (only pipelines
whose YAML declares a `cron` trigger are eligible).

## Runner requirements

The runner must be able to resolve the `ai-harness-doctor` CLI. Public npm is usually
**not reachable** from internal Codebase / Bits runners, so `npx -y ai-harness-doctor`
will fail there. Do one of the following:

- **Pre-install** the CLI on the runner image: `npm i -g ai-harness-doctor`, or
- point npm at the **internal mirror** before running the guard:
  `npm config set registry https://bnpm.byted.org`.

Node.js 20+ is required in either case. `harness-guard.sh` prefers a locally installed
`ai-harness-doctor` and only falls back to `npx` when it is not on `PATH`.

Set `AI_HARNESS_DOCTOR_SKIP=1` in the environment to bypass the guard for a run
(honoured by both `harness-guard.sh` and the local pre-commit hook).
