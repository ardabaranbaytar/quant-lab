#!/usr/bin/env bash
# Deploy the latest main on the server:  sudo bash /opt/quant-lab/deploy/update.sh
# Pulls, installs Python deps, rebuilds the frontend, migrates tables, restarts the API.
# `--no-pull` skips git (used by setup_vps.sh on the first install).
set -euo pipefail

APP=/opt/quant-lab
USER_NAME=quantlab
[ "$(id -u)" -eq 0 ] || { echo "run as root (sudo)"; exit 1; }

# Run as the app user (owns the checkout); caches stay inside the git-ignored .cache.
as_app() {
  sudo -u "$USER_NAME" -H env XDG_CACHE_HOME="$APP/.cache" npm_config_cache="$APP/.cache/npm" \
    bash -c "cd $APP && $*"
}

if [ "${1:-}" != "--no-pull" ]; then
  as_app "git pull --ff-only"
fi

as_app "[ -d .venv ] || python3 -m venv .venv"
as_app ".venv/bin/pip install -q --upgrade pip"
as_app ".venv/bin/pip install -q -e '.[api]'"
as_app "cd web && npm ci --no-audit --no-fund && npm run build"
# Creates missing tables (new models) without touching existing data.
as_app ".venv/bin/python -c 'from quantlab.db import init_db; init_db()'"

# Units may have changed in the repo.
if [ -f /etc/systemd/system/quantlab-api.service ]; then
  cp "$APP"/deploy/systemd/quantlab-{api.service,bot.service,bot.timer} /etc/systemd/system/
  systemctl daemon-reload
  systemctl restart quantlab-api.service
  # Two uvicorn workers import pandas/statsmodels first: retry for up to ~30 s, not one fixed sleep.
  for _ in $(seq 1 15); do
    curl -fsS -o /dev/null http://127.0.0.1:8000/health 2>/dev/null && break
    sleep 2
  done
  curl -fsS http://127.0.0.1:8000/health >/dev/null || {
    echo "API did not become healthy within 30 s; recent log:" >&2
    journalctl -u quantlab-api -n 20 --no-pager >&2 || true
    exit 1
  }
  echo "API healthy at $(as_app "git log -1 --format='%h %s'")"
fi
