#!/usr/bin/env bash
# Restore the database from a backup:  ./restore.sh backups/vnicorn-2026-11-20.sql.gz
set -euo pipefail
cd "$(dirname "$0")"
FILE="${1:?usage: ./restore.sh backups/vnicorn-YYYY-MM-DD.sql.gz}"
read -rp "This replaces the current data with ${FILE}. Type YES to continue: " OK
[ "$OK" = "YES" ] || exit 1
sudo docker compose stop app
sudo docker compose exec -T db psql -U vnicorn -d postgres -c "DROP DATABASE IF EXISTS vnicorn WITH (FORCE);" -c "CREATE DATABASE vnicorn OWNER vnicorn;"
gunzip -c "$FILE" | sudo docker compose exec -T db psql -q -U vnicorn -d vnicorn
sudo docker compose start app
echo "Restored from ${FILE}."
