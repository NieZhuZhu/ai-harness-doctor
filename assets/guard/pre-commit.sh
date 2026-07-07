#!/bin/sh
# ai-harness-doctor:guard
set -eu

# Escape hatch: AI_HARNESS_DOCTOR_SKIP=1 git commit ...
if [ "${AI_HARNESS_DOCTOR_SKIP:-}" = "1" ]; then
  echo "ai-harness-doctor guard skipped by AI_HARNESS_DOCTOR_SKIP=1"
  exit 0
fi

# Prefer a locally installed CLI when available; otherwise fall back to npx.
if command -v ai-harness-doctor >/dev/null 2>&1; then
  ai-harness-doctor drift .
else
  npx -y ai-harness-doctor drift .
fi
