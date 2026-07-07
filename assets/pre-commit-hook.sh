#!/bin/sh
set -eu

python3 .claude/skills/ai-harness-doctor/scripts/check_drift.py .
