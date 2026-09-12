#!/usr/bin/env bash
# Backs up the two things that cannot be rebuilt: the database and the uploads.
#
# Everything else — images, configuration, code — comes from the repository.
# Run it from cron on the server:
#
#   0 3 * * * cd /srv/averix && ./scripts/backup.sh >> /var/log/averix-backup.log 2>&1
#
# A backup nobody has restored is a hope, not a backup. scripts/restore.sh
# does the other half; test it on a copy before you need it.

set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.production.yml}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/averix}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"

echo "[$(date -uIs)] backing up to $BACKUP_DIR"

# ── Database ────────────────────────────────────────────────────────────────
# The custom format restores selectively and compresses itself.
docker compose -f "$COMPOSE_FILE" exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-averix}" -d "${POSTGRES_DB:-averix}" -Fc \
  > "$BACKUP_DIR/averix-db-$STAMP.dump"

echo "  database  $(du -h "$BACKUP_DIR/averix-db-$STAMP.dump" | cut -f1)"

# ── Uploads ─────────────────────────────────────────────────────────────────
# Only for the filesystem storage driver. With S3 the provider holds these and
# this step is skipped.
if docker compose -f "$COMPOSE_FILE" exec -T api test -d /data/storage 2>/dev/null; then
  docker run --rm \
    -v averix_averix-storage:/data:ro \
    -v "$BACKUP_DIR:/backup" \
    alpine tar czf "/backup/averix-storage-$STAMP.tar.gz" -C /data .
  echo "  uploads   $(du -h "$BACKUP_DIR/averix-storage-$STAMP.tar.gz" | cut -f1)"
fi

# ── Retention ───────────────────────────────────────────────────────────────
find "$BACKUP_DIR" -name 'averix-*' -type f -mtime "+$KEEP_DAYS" -delete
echo "  kept the last $KEEP_DAYS days"

# ── Verify ──────────────────────────────────────────────────────────────────
# Reading the dump's table of contents proves the file is a dump rather than
# an empty file or a truncated write.
if ! docker compose -f "$COMPOSE_FILE" exec -T postgres \
     pg_restore --list /dev/stdin < "$BACKUP_DIR/averix-db-$STAMP.dump" > /dev/null; then
  echo "  WARNING: the dump could not be read back — investigate now" >&2
  exit 1
fi

echo "[$(date -uIs)] backup complete and readable"
