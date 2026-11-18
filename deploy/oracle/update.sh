#!/usr/bin/env bash
# Automatic deploys (cron, every 5 minutes): when GitHub has new commits on main, pull them and rebuild.
set -euo pipefail
cd "$(dirname "$0")"
exec 9>/tmp/vnicorn-update.lock
flock -n 9 || exit 0  # an update is already running
REPO="$(git rev-parse --show-toplevel)"
git -C "$REPO" fetch -q origin main
if [ "$(git -C "$REPO" rev-parse HEAD)" = "$(git -C "$REPO" rev-parse origin/main)" ] && [ "${1:-}" != "--force" ]; then
  exit 0
fi
echo "$(date -u +%FT%TZ) deploying $(git -C "$REPO" rev-parse --short origin/main)"
git -C "$REPO" pull -q --ff-only origin main
sudo docker compose up -d --build
sudo docker image prune -f >/dev/null 2>&1 || true
echo "$(date -u +%FT%TZ) done"
