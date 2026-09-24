#!/usr/bin/env bash
# Step the paper bot once and append the output to logs/bot.log.
# Used by the systemd timer and by cron. Safe to re-run: processed days are skipped.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p logs
{
  echo "=== $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  .venv/bin/python -m quantlab.bot run --name "${BOT_NAME:-sp500-pairs}"
} >> logs/bot.log 2>&1
