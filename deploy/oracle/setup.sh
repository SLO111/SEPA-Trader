#!/usr/bin/env bash
# One-time setup on a fresh Ubuntu server (Oracle Cloud Always Free, Ampere A1). Run from this folder:  bash setup.sh
set -euo pipefail
cd "$(dirname "$0")"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

say "1/5 Docker"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
fi
DOCKER="sudo docker"

say "2/5 Firewall: allow the website (ports 80 and 443)"
# Oracle's Ubuntu images block everything but SSH in the server's own firewall (iptables).
for port in 80 443; do
  sudo iptables -C INPUT -p tcp --dport "$port" -j ACCEPT 2>/dev/null || sudo iptables -I INPUT -p tcp --dport "$port" -j ACCEPT
done
if ! command -v netfilter-persistent >/dev/null 2>&1; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y iptables-persistent >/dev/null || true
fi
sudo netfilter-persistent save >/dev/null 2>&1 || true

say "3/5 Settings (.env)"
if [ ! -f .env ]; then
  IP="$(curl -fsS https://api.ipify.org || true)"
  DEFAULT_DOMAIN="${IP//./-}.sslip.io"
  read -rp "Website address (press Enter for ${DEFAULT_DOMAIN}): " DOMAIN
  DOMAIN="${DOMAIN:-$DEFAULT_DOMAIN}"
  read -rp "Administrator e-mail (the one you use on the site): " ADMIN_EMAIL
  read -rsp "Finnhub API key (Enter to skip, you can add it later in .env): " FINNHUB; echo
  PG="$(openssl rand -hex 24)"
  JWT="$(openssl rand -hex 48)"
  cp env.example .env
  sed -i \
    -e "s|^DOMAIN=.*|DOMAIN=${DOMAIN}|" \
    -e "s|^APP_URL=.*|APP_URL=https://${DOMAIN}|" \
    -e "s|^CORS_ORIGINS=.*|CORS_ORIGINS=https://${DOMAIN}|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=${PG}|" \
    -e "s|^JWT_SECRET=.*|JWT_SECRET=${JWT}|" \
    -e "s|^ADMIN_EMAIL=.*|ADMIN_EMAIL=${ADMIN_EMAIL}|" \
    -e "s|^FINNHUB_API_KEY=.*|FINNHUB_API_KEY=${FINNHUB}|" \
    .env
  chmod 600 .env
  echo "Saved .env (secrets stay on this server)."
else
  echo ".env already exists: kept as it is."
fi

say "4/5 Build and start (the first build takes ~10 minutes)"
$DOCKER compose up -d --build

say "5/5 Daily backup and automatic updates"
chmod +x backup.sh update.sh restore.sh migrate-from-render.sh
HERE="$(pwd)"
( crontab -l 2>/dev/null | grep -v "vnicorn-" ; \
  echo "30 3 * * * cd ${HERE} && ./backup.sh >> ${HERE}/backup.log 2>&1 # vnicorn-backup" ; \
  echo "*/5 * * * * cd ${HERE} && ./update.sh >> ${HERE}/update.log 2>&1 # vnicorn-update" ) | crontab -

DOMAIN="$(grep '^DOMAIN=' .env | cut -d= -f2)"
say "Done. Open https://${DOMAIN} (the certificate can take a minute the first time)."
echo "Status:  sudo docker compose ps      Logs:  sudo docker compose logs -f app"
