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
    npx -y ai-harness-doctor@latest "$@"
  fi
}

run_scan_gate() {
  # Optional adoption path: commit this reviewed debt register. The guard never
  # creates it, and HIGH security findings are never suppressible.
  baseline=".ai-harness-doctor/scan-baseline.json"
  if [ -f "$baseline" ]; then
    run scan . --baseline "$baseline" --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts
  else
    run scan . --fail-on-security --fail-on-gaps --fail-on-semantic --fail-on-conflicts
  fi
}

case "$MODE" in
  drift)
    # Fast gate for merge requests: fail on new scan debt or harness drift.
    run_scan_gate
    run drift . --strict
    # Eval health-score gate (portable; mirrors the GitHub guard template).
    # Inline MR review comments are GitHub-only. This gate fails the check when
    # the committed eval results drop under the threshold; skipped when absent.
    RESULTS="benchmark/self-eval/results-after-graded.json"
    if [ -f "$RESULTS" ]; then
      run eval --score "$RESULTS" --fail-under 80
    else
      echo "No committed eval results at $RESULTS; skipping eval gate."
    fi
    ;;
  checkup)
    # Scheduled deep checkup: publish both reports and preserve scan precedence.
    set +e
    run_scan_gate > harness-scan-report.md 2>&1
    scan_status=$?
    run drift . --strict > harness-drift-report.md 2>&1
    drift_status=$?
    set -e
    echo "===== harness scan ====="
    cat harness-scan-report.md
    echo "===== harness drift ====="
    cat harness-drift-report.md
    if [ "$scan_status" -ne 0 ]; then
      exit "$scan_status"
    fi
    exit "$drift_status"
    ;;
  *)
    echo "usage: harness-guard.sh [drift|checkup]" >&2
    exit 2
    ;;
esac
