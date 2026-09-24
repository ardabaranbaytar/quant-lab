# Deploying to a VPS

One small server runs everything: the dashboard, the API, MySQL and the daily bot.
Tested target: Ubuntu 24.04 on Hetzner Cloud (any plan with ≥ 2 GB RAM; the script adds
swap below 3 GB).

```
Internet ──80/443──► Caddy (automatic HTTPS)
                      ├─ /        → web/dist (static React build)
                      └─ /api/*   → 127.0.0.1:8000  quantlab-api.service (uvicorn, 2 workers)
                                          │
                               MySQL 8 (localhost only)
                                          ▲
                  quantlab-bot.timer → quantlab-bot.service (Mon–Fri 16:30 New York)
```

Only ports 22, 80 and 443 are open. MySQL listens on localhost and its password is
generated on the server (`/opt/quant-lab/.env`, mode 600); it never leaves the machine.

## 1. Server

Hetzner console → *Add server*: image **Ubuntu 24.04**, add your **SSH key** (safer than a
root password), location Falkenstein/Nuremberg/Helsinki (Ashburn if you want it closer to
the US exchanges; it does not matter for daily bars).

## 2. Domain (optional, needed for HTTPS)

Point an `A` record (e.g. `quant.example.com`) at the server's IPv4 **before** step 3;
Caddy requests the certificate on first start. Without a domain the site is served over
plain HTTP on the IP; you can add a domain later by re-running the script with it.

## 3. Install

```bash
ssh root@<server-ip>
curl -fsSLO https://raw.githubusercontent.com/ardabaranbaytar/quant-lab/main/deploy/setup_vps.sh
bash setup_vps.sh quant.example.com      # or: bash setup_vps.sh   (no domain)
```

About 5–10 minutes. The script prints the dashboard URL at the end. Then start the bot
once so the dashboard has data (the first run downloads ~3 years × 500 tickers, ~1 min):

```bash
systemctl start quantlab-bot.service && tail -n 20 /opt/quant-lab/logs/bot.log
```

## 4. Update after a push

```bash
ssh root@<server-ip> 'bash /opt/quant-lab/deploy/update.sh'
```

Pulls `main`, reinstalls dependencies, rebuilds the frontend, creates any new tables and
restarts the API. Bot state and history stay in MySQL.

## Operations

| What | Command |
|---|---|
| API logs | `journalctl -u quantlab-api -f` |
| Bot log | `tail -f /opt/quant-lab/logs/bot.log` |
| Next bot run | `systemctl list-timers quantlab-bot.timer` |
| Run the bot now | `systemctl start quantlab-bot.service` |
| Access log | `tail -f /var/log/caddy/quant-lab.log` |
| DB backup | `mysqldump quantlab \| gzip > quantlab-$(date +%F).sql.gz` |

## Moving your local bot history (optional)

By default the server's bot starts fresh. To keep the local one instead, before its first
server run:

```bash
# on your PC (MySQL 8 client)
mysqldump -u root -p quantlab bot_states bot_equity paper_fills bot_events > bot.sql
scp bot.sql root@<server-ip>:/tmp/
# on the server
mysql quantlab < /tmp/bot.sql && rm /tmp/bot.sql
```

## Public API limits

`POST /backtests` and `POST /research/pairs` download prices and use CPU, so each API
worker runs one of them at a time (`QUANTLAB_MAX_HEAVY_JOBS=1`, two workers); extra
requests get `429 Server busy`. Read-only endpoints (the bot page, history) are never
limited. The GitHub Actions bot workflow is not needed on this setup; leave its
`BOT_DATABASE_URL` secret unset so it skips itself, otherwise the bot would be stepped twice.
