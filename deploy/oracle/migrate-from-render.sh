#!/usr/bin/env bash
# Copy all the data from the Render database to this server (users, portfolios, ideas, history...).
# In Render: your database -> Connect -> "External Database URL" (copy it; it is a secret, paste it only here).
set -euo pipefail
cd "$(dirname "$0")"
read -rsp "Paste Render's External Database URL (hidden): " SRC; echo
case "$SRC" in *sslmode=*) ;; *\?*) SRC="${SRC}&sslmode=require" ;; *) SRC="${SRC}?sslmode=require" ;; esac
echo "Stopping the app while the data is copied..."
sudo docker compose stop app
echo "Copying (a minute or two)..."
sudo docker compose exec -T -e SRC="$SRC" db sh -c 'pg_dump --no-owner --no-privileges --clean --if-exists "$SRC"' \
  | sudo docker compose exec -T db psql -q -U vnicorn -d vnicorn -v ON_ERROR_STOP=0 >/dev/null
sudo docker compose start app
USERS="$(sudo docker compose exec -T db psql -tA -U vnicorn -d vnicorn -c 'select count(*) from users' 2>/dev/null || echo '?')"
echo "Done: ${USERS} users copied. Sign in on the new address with your usual e-mail and password."
