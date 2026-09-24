#!/usr/bin/env bash
# One-time setup of quant-lab on a fresh Ubuntu 24.04 server (e.g. Hetzner Cloud).
#
#   curl -fsSLO https://raw.githubusercontent.com/ardabaranbaytar/quant-lab/main/deploy/setup_vps.sh
#   sudo bash setup_vps.sh example.com     # with a domain -> automatic HTTPS
#   sudo bash setup_vps.sh                 # no domain yet -> plain HTTP on the server IP
#
# Installs MySQL (localhost only), Python venv, Node 22 (build only), Caddy,
# the API service and the daily bot timer. Safe to re-run: existing
# database credentials in /opt/quant-lab/.env are kept.
set -euo pipefail

DOMAIN="${1:-}"
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
ufw allow OpenSSH >/dev/null
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

step "Caddy (${DOMAIN:-no domain: plain HTTP on :80})"
sed "s|{\$SITE}|${DOMAIN:-:80}|" "$APP/deploy/caddy/Caddyfile" > /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
systemctl reload-or-restart caddy

IP="$(curl -fsS -4 https://ifconfig.me || hostname -I | awk '{print $1}')"
echo
echo "Done."
echo "  Dashboard:  ${DOMAIN:+https://$DOMAIN}${DOMAIN:-http://$IP}"
echo "  API health: curl -s ${DOMAIN:+https://$DOMAIN}${DOMAIN:-http://$IP}/api/health"
echo "  Bot timer:  systemctl list-timers quantlab-bot.timer"
echo "  First bot step now (optional, ~1 min): sudo systemctl start quantlab-bot.service"
