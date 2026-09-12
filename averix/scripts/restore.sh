#!/usr/bin/env bash
# Restores a backup. Destructive, and deliberately noisy about it.
#
#   ./scripts/restore.sh /var/backups/averix/averix-db-20260101-030000.dump
#
# Practise this on a copy of the server before you ever need it in anger.

set -euo pipefail

DUMP="${1:?usage: restore.sh <dump file> [storage archive]}"
STORAGE="${2:-}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"

echo "This will REPLACE the contents of the ${POSTGRES_DB:-averix} database."
echo "Dump: $DUMP"
read -r -p "Type the word restore to continue: " confirm
[ "$confirm" = "restore" ] || { echo "aborted"; exit 1; }

echo "stopping the application (the database stays up)…"
docker compose -f "$COMPOSE_FILE" stop api worker web

echo "restoring the database…"
docker compose -f "$COMPOSE_FILE" exec -T postgres \
  pg_restore -U "${POSTGRES_USER:-averix}" -d "${POSTGRES_DB:-averix}" \
  --clean --if-exists --no-owner --no-privileges < "$DUMP"

if [ -n "$STORAGE" ]; then
  echo "restoring uploads…"
  docker run --rm \
    -v averix_averix-storage:/data \
    -v "$(dirname "$(realpath "$STORAGE")"):/backup:ro" \
    alpine sh -c "rm -rf /data/* && tar xzf /backup/$(basename "$STORAGE") -C /data"
fi

echo "applying any migrations the backup predates…"
docker compose -f "$COMPOSE_FILE" run --rm migrate

echo "starting the application…"
docker compose -f "$COMPOSE_FILE" up -d

echo "done. Check https://${AVERIX_DOMAIN:-your-domain}/ready"
