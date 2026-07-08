#!/bin/sh
# ai-harness-doctor:guard
# Portable CI entrypoint for internal Codebase / Bits / Jenkins / any runner that
# does not use GitHub Actions or GitLab CI natively. Register this script as a
# merge-request check and/or a scheduled pipeline step (see README.md next to it).
set -eu

MODE="${1:-drift}"

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
