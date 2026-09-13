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
#
# The question "is there anything to back up" is asked of Docker, not of the
# API container. The API image carries the binary and nothing else — no shell,
# no coreutils — so `exec api test -d …` fails with "executable file not found"
# on a perfectly healthy deployment, and the uploads quietly never get backed
# up. The volume either exists or it does not, and Docker knows which.
STORAGE_VOLUME="$(docker volume ls -q | grep -E '(^|_)averix-storage$' | head -1 || true)"
if [ -n "$STORAGE_VOLUME" ]; then
  docker run --rm \
    -v "$STORAGE_VOLUME:/data:ro" \
    -v "$BACKUP_DIR:/backup" \
    alpine tar czf "/backup/averix-storage-$STAMP.tar.gz" -C /data .
  echo "  uploads   $(du -h "$BACKUP_DIR/averix-storage-$STAMP.tar.gz" | cut -f1)  (том $STORAGE_VOLUME)"
else
  echo "  uploads   тома нет — файлы в S3, их хранит провайдер"
fi

# ── Retention ───────────────────────────────────────────────────────────────
find "$BACKUP_DIR" -name 'averix-*' -type f -mtime "+$KEEP_DAYS" -delete
echo "  kept the last $KEEP_DAYS days"

# ── Verify ──────────────────────────────────────────────────────────────────
# A backup nobody has read back is a hope. Two checks, cheapest first.
DUMP="$BACKUP_DIR/averix-db-$STAMP.dump"

# 1. The five bytes every custom-format dump starts with. This catches what
#    actually goes wrong — an empty file, a truncated write, a disk that filled
#    up — and needs no tool the host might not have.
if [ "$(head -c 5 "$DUMP" 2>/dev/null)" != "PGDMP" ]; then
  echo "  WARNING: $DUMP is not a dump — $(du -h "$DUMP" 2>/dev/null | cut -f1). Investigate now." >&2
  exit 1
fi

# 2. The full table of contents, read back by pg_restore. It must read the file
#    as a file: the custom format needs to seek, and piping it in on stdin as
#    /dev/stdin fails with "did not find magic string in file header" even when
#    the dump is perfect. So the file is copied in and listed there.
if docker compose -f "$COMPOSE_FILE" cp "$DUMP" postgres:/tmp/verify-$STAMP.dump > /dev/null 2>&1; then
  if ! docker compose -f "$COMPOSE_FILE" exec -T postgres \
       pg_restore --list "/tmp/verify-$STAMP.dump" > /dev/null; then
    docker compose -f "$COMPOSE_FILE" exec -T postgres rm -f "/tmp/verify-$STAMP.dump" > /dev/null 2>&1 || true
    echo "  WARNING: the dump could not be read back — investigate now" >&2
    exit 1
  fi
  docker compose -f "$COMPOSE_FILE" exec -T postgres rm -f "/tmp/verify-$STAMP.dump" > /dev/null 2>&1 || true
  echo "  проверено: содержимое дампа читается"
else
  echo "  проверено: заголовок дампа на месте (полное чтение пропущено)"
fi

echo "[$(date -uIs)] backup complete and readable"
