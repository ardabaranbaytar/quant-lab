# Deploying to a VPS

One small server runs everything under `ardabaranbaytar.com`: the personal website,
quant-lab (dashboard, API, MySQL, daily bot) and StochOpt-MDP. Tested target: Ubuntu 24.04
on Hetzner Cloud (any plan with ≥ 2 GB RAM; the scripts add swap below 3 GB).

```
Internet ──80/443──► Caddy (automatic HTTPS, one file per app in /etc/caddy/sites/)
  ardabaranbaytar.com (+www)  → 127.0.0.1:3000  website.service (Next.js)
  quant.ardabaranbaytar.com   ├─ /       → /opt/quant-lab/web/dist (static React build)
                              └─ /api/*  → 127.0.0.1:8000  quantlab-api.service (uvicorn, 2 workers)
                                                  │
                                       MySQL 8 (localhost only)
                                                  ▲
                          quantlab-bot.timer → quantlab-bot.service (Mon–Fri 16:30 New York)
  stochopt.ardabaranbaytar.com├─ /       → /opt/stochopt-mdp/frontend/dist
                              └─ /api/*, /health, /docs → 127.0.0.1:8100  stochopt-api.service
```

Only ports 22, 80 and 443 are open. MySQL listens on localhost and its password is
generated on the server (`/opt/quant-lab/.env`, mode 600); it never leaves the machine.
Each app has its own system user, checkout in `/opt/<app>` and `deploy/setup_vps.sh`;
the scripts can run in any order and only ever add their own Caddy site file.

## 1. Server

Hetzner console → *Add server*: image **Ubuntu 24.04**, add your **SSH key** (safer than a
root password), location Falkenstein/Nuremberg/Helsinki (Ashburn if you want it closer to
the US exchanges; it does not matter for daily bars).

## 2. DNS (Cloudflare)

Cloudflare dashboard → the domain → *DNS* → *Records*: add four `A` records pointing at
the server's IPv4, all with **Proxy status: DNS only** (grey cloud):

| Name | Content |
|---|---|
| `@` | `<server-ip>` |
| `www` | `<server-ip>` |
| `quant` | `<server-ip>` |
| `stochopt` | `<server-ip>` |

Do this **before** step 3: Caddy requests the certificates on first start and needs the
names to resolve to the server. Check with `nslookup quant.ardabaranbaytar.com`.
Turning on the orange-cloud proxy later is optional; if you do, set *SSL/TLS* →
*Overview* to **Full (strict)**, otherwise the site ends up in a redirect loop.

## 3. Install

quant-lab and StochOpt-MDP are public, so the server downloads their scripts. The website
repo is private: copy its script from your PC.

```bash
# on your PC, inside the website/ folder
scp deploy/setup_vps.sh root@<server-ip>:setup_website.sh

# on the server
ssh root@<server-ip>
for repo in quant-lab StochOpt-MDP; do
  curl -fsSL -o "setup_${repo}.sh" \
    "https://raw.githubusercontent.com/ardabaranbaytar/${repo}/main/deploy/setup_vps.sh"
done
bash setup_quant-lab.sh      # quant.ardabaranbaytar.com
bash setup_StochOpt-MDP.sh   # stochopt.ardabaranbaytar.com
bash setup_website.sh        # ardabaranbaytar.com + www
```

The first `setup_website.sh` run creates a read-only deploy key, prints it (`ssh-ed25519 …`)
and stops. Add it on GitHub (website repo → *Settings* → *Deploy keys* → *Add deploy key*,
leave *Allow write access* unticked) and run `bash setup_website.sh` again. The key stays in
`/etc/website/` (readable by the `website` user only); `update.sh` pulls with it.

About 5–10 minutes each (the first one installs the system packages). Each script takes
another domain as its argument if needed. Then start the bot once so the dashboard has
data (the first run downloads ~3 years × 500 tickers, ~1 min):

```bash
systemctl start quantlab-bot.service && tail -n 20 /opt/quant-lab/logs/bot.log
```

## 4. Update after a push

```bash
ssh root@<server-ip> 'bash /opt/quant-lab/deploy/update.sh'      # or /opt/stochopt-mdp, /opt/website
```

Pulls the latest commit, reinstalls dependencies, rebuilds the frontend and restarts the
service (quant-lab also creates any new tables). Bot state and history stay in MySQL.

## Operations

| What | Command |
|---|---|
| API logs | `journalctl -u quantlab-api -f` (`stochopt-api`, `website`) |
| Bot log | `tail -f /opt/quant-lab/logs/bot.log` |
| Next bot run | `systemctl list-timers quantlab-bot.timer` |
| Run the bot now | `systemctl start quantlab-bot.service` |
| Access log | `tail -f /var/log/caddy/quant-lab.log` (`stochopt.log`, `website.log`) |
| Caddy sites | `ls /etc/caddy/sites/` then `systemctl reload caddy` after edits |
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
