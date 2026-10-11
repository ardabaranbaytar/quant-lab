#!/usr/bin/env bash
# One-time setup of quant-lab on a fresh Ubuntu 24.04 server (e.g. Hetzner Cloud).
#
#   curl -fsSLO https://raw.githubusercontent.com/ardabaranbaytar/quant-lab/main/deploy/setup_vps.sh
#   sudo bash setup_vps.sh                         # quant.ardabaranbaytar.com
#   sudo bash setup_vps.sh quant.example.com       # another domain
#
# Installs MySQL (localhost only), Python venv, Node 22 (build only), Caddy,
# the API service and the daily bot timer. Shares the server with other apps:
# Caddy loads every file in /etc/caddy/sites/ and this app only adds its own
# (quant-lab.caddy); an existing /etc/caddy/Caddyfile is backed up and kept, only the
# import line is appended. Safe to re-run: existing database credentials in
# /opt/quant-lab/.env are kept.
set -euo pipefail

DOMAIN="${1:-quant.ardabaranbaytar.com}"
REPO="${REPO:-https://github.com/ardabaranbaytar/quant-lab.git}"
APP=/opt/quant-lab
USER_NAME=quantlab

[ "$(id -u)" -eq 0 ] || { echo "run as root (sudo)"; exit 1; }
. /etc/os-release
[ "${ID:-}" = ubuntu ] || echo "warning: tested on Ubuntu 24.04, this is ${PRETTY_NAME:-unknown}"
step() { echo; echo "==> $*"; }

step "System packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q git python3-venv python3-dev build-essential mysql-server caddy ufw curl ca-certificates \
  sudo openssl

if ! command -v node >/dev/null || [ "$(node -p 'process.versions.node.split(".")[0]')" -lt 20 ]; then
  step "Node.js 22 (NodeSource; only used to build the frontend)"
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y -q nodejs
fi

# Small plans: npm/vite builds and the first 500-ticker download like some headroom.
if [ "$(awk '/MemTotal/ {print $2}' /proc/meminfo)" -lt 3000000 ] && ! swapon --show | grep -q .; then
  step "2 GB swap file"
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

step "Firewall: SSH, HTTP, HTTPS only"
ufw allow OpenSSH >/dev/null 2>&1 || ufw allow 22/tcp >/dev/null  # profile needs openssh-server
ufw allow 80,443/tcp >/dev/null
ufw --force enable

step "App user and code in $APP"
id "$USER_NAME" >/dev/null 2>&1 || useradd --system --home-dir "$APP" --shell /usr/sbin/nologin "$USER_NAME"
if [ ! -d "$APP/.git" ]; then
  git clone "$REPO" "$APP"
fi
mkdir -p "$APP/.cache" "$APP/logs"
chown -R "$USER_NAME:$USER_NAME" "$APP"

step "MySQL database (listening on localhost only)"
systemctl enable --now mysql
if [ ! -f "$APP/.env" ]; then
  DB_PASS="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 32)"
  mysql <<SQL
CREATE DATABASE IF NOT EXISTS quantlab CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'quantlab'@'localhost' IDENTIFIED BY '${DB_PASS}';
ALTER USER 'quantlab'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON quantlab.* TO 'quantlab'@'localhost';
FLUSH PRIVILEGES;
SQL
  cat > "$APP/.env" <<ENV
MYSQL_USER=quantlab
MYSQL_PASSWORD=${DB_PASS}
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=quantlab
ENV
  chown "$USER_NAME:$USER_NAME" "$APP/.env"
  chmod 600 "$APP/.env"
fi

step "Python environment, frontend build, database tables"
bash "$APP/deploy/update.sh" --no-pull

step "systemd: API service + daily bot timer"
cp "$APP"/deploy/systemd/quantlab-{api.service,bot.service,bot.timer} /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now quantlab-api.service quantlab-bot.timer

step "Caddy site $DOMAIN"
mkdir -p /etc/caddy/sites /var/log/caddy
chown caddy:caddy /var/log/caddy
CADDYFILE=/etc/caddy/Caddyfile
if ! grep -qs '^import sites/\*.caddy' "$CADDYFILE"; then
  if [ ! -s "$CADDYFILE" ] || grep -qs '/usr/share/caddy' "$CADDYFILE"; then
    # Fresh server: replace the stock package Caddyfile (it only serves a welcome page).
    cat > "$CADDYFILE" <<'CADDY'
# Each app on this server drops its own site file into /etc/caddy/sites/.
import sites/*.caddy
CADDY
  else
    # Another app already owns this file (e.g. the website's site block): keep it, add the import.
    cp "$CADDYFILE" "$CADDYFILE.bak-$(date +%F-%H%M)"
    printf '\n# Each app on this server drops its own site file into /etc/caddy/sites/.\nimport sites/*.caddy\n' \
      >> "$CADDYFILE"
  fi
fi
sed "s|{\$SITE}|$DOMAIN|" "$APP/deploy/caddy/quant-lab.caddy" > /etc/caddy/sites/quant-lab.caddy
caddy validate --config "$CADDYFILE" --adapter caddyfile
# `caddy validate` runs as root and creates the log files root-owned, but the service runs as
# `caddy`: without this chown the reload fails with "permission denied" on the log file.
chown -R caddy:caddy /var/log/caddy
systemctl reload-or-restart caddy

echo
echo "Done."
echo "  Dashboard:  https://$DOMAIN"
echo "  API health: curl -s https://$DOMAIN/api/health"
echo "  Bot timer:  systemctl list-timers quantlab-bot.timer"
echo "  First bot step now (optional, ~1 min): sudo systemctl start quantlab-bot.service"
