#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
stamp=$(date -u +%Y%m%dT%H%M%SZ)
target="/data/backups/study-$stamp.db"
docker compose exec -T app python -m server.manage backup "$target"
mkdir -p backups
docker compose cp "app:$target" "backups/study-$stamp.db"
chmod 600 "backups/study-$stamp.db"
printf 'Backup: %s\n' "backups/study-$stamp.db"
