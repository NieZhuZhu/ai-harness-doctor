#!/bin/sh
# ai-harness-doctor:guard
# Portable CI entrypoint for internal Codebase / Bits / Jenkins / any runner that
# does not use GitHub Actions or GitLab CI natively. Register this script as a
# merge-request check and/or a scheduled pipeline step (see README.md next to it).
set -eu

MODE="${1:-drift}"

# Escape hatch: set AI_HARNESS_DOCTOR_SKIP=1 to bypass the guard for a run
# (mirrors the local pre-commit hook). Kept auditable via the log line below.
if [ "${AI_HARNESS_DOCTOR_SKIP:-}" = "1" ]; then
  echo "ai-harness-doctor guard skipped by AI_HARNESS_DOCTOR_SKIP=1 (mode=$MODE)"
  exit 0
fi

run() {
  if command -v ai-harness-doctor >/dev/null 2>&1; then
    ai-harness-doctor "$@"
  else
    npx -y ai-harness-doctor "$@"
  fi
}

case "$MODE" in
  drift)
    # Fast gate for merge requests: fail the pipeline when the harness has drifted.
    run drift . --strict
    # Eval health-score gate (portable; mirrors the GitHub guard template).
    # Inline MR review comments are GitHub-only. This gate fails the check when
    # the committed eval results drop under the threshold; skipped when absent.
    RESULTS="benchmark/self-eval/results-after-graded.json"
    if [ -f "$RESULTS" ]; then
      python3 scripts/eval_run.py --score "$RESULTS" --fail-under 80
    else
      echo "No committed eval results at $RESULTS; skipping eval gate."
    fi
    ;;
  checkup)
    # Scheduled deep checkup: publish a scan + drift report, exit with drift status.
    run scan . > harness-scan-report.md
    set +e
    run drift . --strict > harness-drift-report.md 2>&1
    status=$?
    set -e
    echo "===== harness scan ====="
    cat harness-scan-report.md
    echo "===== harness drift ====="
    cat harness-drift-report.md
    exit "$status"
    ;;
  *)
    echo "usage: harness-guard.sh [drift|checkup]" >&2
    exit 2
    ;;
esac
