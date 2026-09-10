#!/usr/bin/env bash
# Восстанавливает файлы клиента и его базы данных из архива, созданного backup.sh.
#
# Использование: restore.sh --user <system_user> --backup-id <id>
#
# Перед перезаписью текущих файлов клиента делает снимок «на всякий случай»
# в BACKUP_DIR/<user>/pre-restore-<timestamp>.tar.gz — если восстановление
# окажется ошибкой (не тот бэкап), это не финальная потеря данных.

set -euo pipefail

HOSTING_ROOT="${HOSTING_ROOT:-/opt/hosting}"
HOSTING_USERS_ROOT="${HOSTING_USERS_ROOT:-/home/hosting}"
BACKUP_DIR="${BACKUP_DIR:-${HOSTING_ROOT}/backups}"
PHP_BIN="${PHP_BIN:-php}"
RECORDER="${HOSTING_ROOT}/hosting/panel/bin/record-backup.php"

TARGET_USER=""
BACKUP_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user) TARGET_USER="$2"; shift 2 ;;
    --backup-id) BACKUP_ID="$2"; shift 2 ;;
    *) echo "Неизвестный аргумент: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$TARGET_USER" || -z "$BACKUP_ID" ]]; then
  echo "Использование: restore.sh --user <system_user> --backup-id <id>" >&2
  exit 1
fi
if [[ ! "$TARGET_USER" =~ ^client[0-9]{1,10}$ ]]; then
  echo "[restore] отказ: недопустимое имя пользователя '$TARGET_USER'" >&2
  exit 1
fi
if [[ ! "$BACKUP_ID" =~ ^[0-9]+$ ]]; then
  echo "[restore] отказ: backup-id должен быть числом" >&2
  exit 1
fi

BACKUP_JSON=$("$PHP_BIN" "$RECORDER" get --backup-id="$BACKUP_ID")
ARCHIVE=$(echo "$BACKUP_JSON" | php -r 'echo json_decode(file_get_contents("php://stdin"), true)["local_path"];')
CHECKSUM=$(echo "$BACKUP_JSON" | php -r 'echo json_decode(file_get_contents("php://stdin"), true)["checksum"];')

if [[ -z "$ARCHIVE" || ! -f "$ARCHIVE" ]]; then
  echo "[restore] архив не найден: '$ARCHIVE'" >&2
  exit 1
fi

if [[ -n "$CHECKSUM" ]]; then
  ACTUAL=$(sha256sum "$ARCHIVE" | awk '{print $1}')
  if [[ "$ACTUAL" != "$CHECKSUM" ]]; then
    echo "[restore] ОТКАЗ: контрольная сумма архива не совпадает (файл повреждён или подменён)" >&2
    exit 1
  fi
fi

HOME_DIR="${HOSTING_USERS_ROOT}/${TARGET_USER}"
PARENT_DIR=$(dirname "$HOME_DIR")

# Снимок текущего состояния перед перезаписью
if [[ -d "$HOME_DIR" ]]; then
  mkdir -p "${BACKUP_DIR}/${TARGET_USER}"
  tar czf "${BACKUP_DIR}/${TARGET_USER}/pre-restore-$(date -u +%Y%m%d-%H%M%S).tar.gz" \
    --exclude='tmp' -C "$PARENT_DIR" "$(basename "$HOME_DIR")" || true
fi

WORKDIR=$(mktemp -d)
tar xzf "$ARCHIVE" -C "$WORKDIR"

# Файлы: заменяем sites/ и logs/ содержимым из бэкапа (без внешних зависимостей вроде
# rsync — только tar/cp, они есть везде). tmp/ намеренно не трогаем — это runtime-мусор
# самого PHP (сессии, временные файлы загрузки), а не данные клиента.
if [[ -d "$WORKDIR/$TARGET_USER" ]]; then
  mkdir -p "$HOME_DIR"
  for sub in sites logs; do
    if [[ -d "$WORKDIR/$TARGET_USER/$sub" ]]; then
      rm -rf "${HOME_DIR:?}/${sub:?}"
      cp -a "$WORKDIR/$TARGET_USER/$sub" "$HOME_DIR/$sub"
    fi
  done
  chown -R "${TARGET_USER}:${TARGET_USER}" "$HOME_DIR"
  echo "[restore] $TARGET_USER: файлы восстановлены"
fi

# Базы данных: разворачиваем каждый .sql обратно (база должна уже существовать —
# создание базы делает JobHandler::handleCreateDatabase, restore только наполняет).
if [[ -d "$WORKDIR/databases" ]] && command -v mysql >/dev/null 2>&1; then
  for dump in "$WORKDIR"/databases/*.sql; do
    [[ -f "$dump" ]] || continue
    db=$(basename "$dump" .sql)
    if [[ ! "$db" =~ ^${TARGET_USER}_[A-Za-z0-9_]+$ ]]; then
      echo "[restore] пропуск подозрительного имени базы в архиве: $db" >&2
      continue
    fi
    mysql --default-character-set=utf8mb4 -e "CREATE DATABASE IF NOT EXISTS \`${db}\` CHARACTER SET utf8mb4" 2>/dev/null || true
    mysql --default-character-set=utf8mb4 "$db" < "$dump"
    echo "[restore] база восстановлена: $db"
  done
fi

rm -rf "$WORKDIR"
echo "[restore] $TARGET_USER: восстановление из бэкапа #$BACKUP_ID завершено"
