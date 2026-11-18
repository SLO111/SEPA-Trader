#!/usr/bin/env bash
# Daily database backup (cron 03:30): a compressed copy in ./backups, the last 14 days kept.
# Optional off-server copy: set RCLONE_REMOTE in .env (e.g. oci:vnicorn-backups) after configuring rclone (see GHID.md).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p backups
FILE="backups/vnicorn-$(date -u +%Y-%m-%d).sql.gz"
sudo docker compose exec -T db pg_dump -U vnicorn -d vnicorn --no-owner --no-privileges | gzip > "$FILE"
find backups -name 'vnicorn-*.sql.gz' -mtime +14 -delete
REMOTE="$(grep '^RCLONE_REMOTE=' .env 2>/dev/null | cut -d= -f2- || true)"
if [ -n "$REMOTE" ] && command -v rclone >/dev/null 2>&1; then
  rclone copy "$FILE" "$REMOTE" && rclone delete --min-age 15d "$REMOTE" || echo "off-server copy failed"
fi
echo "$(date -u +%FT%TZ) backup $FILE ($(du -h "$FILE" | cut -f1))"
