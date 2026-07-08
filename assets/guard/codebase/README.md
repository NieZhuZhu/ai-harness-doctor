# Harness guard — Codebase / generic pipeline wiring

`ai-harness-doctor guard --provider codebase` installs a portable entrypoint at
`.harness-ci/harness-guard.sh`. Unlike GitHub Actions or GitLab CI, internal
Codebase / Bits pipelines vary between teams, so the guard ships a runner-agnostic
shell script that you wire into your own pipeline.

## What it does

| Mode | When to run | Behaviour |
|---|---|---|
| `harness-guard.sh drift` | On every merge request | Runs `ai-harness-doctor drift . --strict`; non-zero exit fails the check. |
| `harness-guard.sh checkup` | On a schedule (e.g. weekly) | Runs `scan` + `drift`, prints both reports, exits with the drift status. |

The script prefers a locally installed `ai-harness-doctor` and falls back to `npx`.

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

Requires Node.js 20+ on the runner (for `npx -y ai-harness-doctor`). Set
`AI_HARNESS_DOCTOR_SKIP=1` in the environment to bypass the guard for a run.
