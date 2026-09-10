#!/usr/bin/env bash
# Резервное копирование клиента: файлы (tar.gz) + дампы всех его баз MariaDB.
# Кладёт архив в BACKUP_DIR, считает checksum, при настроенном BACKUP_PROVIDER
# (rclone remote) копирует наружу — бэкап только на этом же VPS не считается бэкапом.
#
# Использование:
#   backup.sh --user <system_user> [--backup-id <id>]   — один клиент
#   backup.sh --all                                      — все активные клиенты (cron/systemd timer)
#
# Ротация (см. спецификацию BACKUPS): 7 daily, 4 weekly, 3 monthly.

set -euo pipefail

HOSTING_ROOT="${HOSTING_ROOT:-/opt/hosting}"
HOSTING_USERS_ROOT="${HOSTING_USERS_ROOT:-/home/hosting}"
BACKUP_DIR="${BACKUP_DIR:-${HOSTING_ROOT}/backups}"
PHP_BIN="${PHP_BIN:-php}"
RECORDER="${HOSTING_ROOT}/hosting/panel/bin/record-backup.php"

MODE=""
TARGET_USER=""
BACKUP_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all) MODE="all"; shift ;;
    --user) TARGET_USER="$2"; MODE="one"; shift 2 ;;
    --backup-id) BACKUP_ID="$2"; shift 2 ;;
    *) echo "Неизвестный аргумент: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$MODE" ]]; then
  echo "Использование: backup.sh --all | --user <system_user> [--backup-id <id>]" >&2
  exit 1
fi

backup_one_user() {
  local user="$1"
  local backup_id="$2"

  if [[ ! "$user" =~ ^client[0-9]{1,10}$ ]]; then
    echo "[backup] отказ: недопустимое имя пользователя '$user'" >&2
    return 1
  fi

  local home="${HOSTING_USERS_ROOT}/${user}"
  if [[ ! -d "$home" ]]; then
    echo "[backup] $user: домашний каталог не найден, пропуск" >&2
    return 1
  fi

  if [[ -z "$backup_id" ]]; then
    local user_id
    user_id=$("$PHP_BIN" -r 'echo (int) substr($argv[1], 6) - 1000;' "$user")
    backup_id=$("$PHP_BIN" "$RECORDER" create --user="$user_id" --type=full)
  fi

  local stamp workdir archive
  stamp=$(date -u +%Y%m%d-%H%M%S)
  workdir=$(mktemp -d)
  archive="${BACKUP_DIR}/${user}/${stamp}.tar.gz"
  mkdir -p "${BACKUP_DIR}/${user}"

  # Дампы баз клиента (namespace user_*) — рядом с файлами, в тот же архив.
  mkdir -p "${workdir}/databases"
  if command -v mysql >/dev/null 2>&1; then
    local dbs
    dbs=$(mysql -N -B -e "SHOW DATABASES LIKE '${user}\\_%'" 2>/dev/null || true)
    for db in $dbs; do
      # --default-character-set обязателен: иначе клиент возьмёт свою кодировку
      # по умолчанию и кириллица в дампе окажется битой.
      mysqldump --default-character-set=utf8mb4 --single-transaction --quick --routines \
        "$db" > "${workdir}/databases/${db}.sql" 2>/dev/null || {
          echo "[backup] $user: не удалось сдампить базу $db" >&2
        }
    done
  fi

  local ok=1
  if tar czf "$archive" \
      --exclude='tmp' \
      -C "$(dirname "$home")" "$(basename "$home")" \
      -C "$workdir" databases 2>/tmp/backup-${user}-${stamp}.err; then
    ok=0
  else
    ok=1
    cat /tmp/backup-${user}-${stamp}.err >&2 || true
  fi
  rm -rf "$workdir" /tmp/backup-${user}-${stamp}.err

  if [[ $ok -ne 0 || ! -f "$archive" ]]; then
    "$PHP_BIN" "$RECORDER" result --backup-id="$backup_id" --status=failed --local="$archive"
    echo "[backup] $user: ОШИБКА" >&2
    return 1
  fi

  local checksum size remote=""
  checksum=$(sha256sum "$archive" | awk '{print $1}')
  size=$(stat -c%s "$archive" 2>/dev/null || stat -f%z "$archive")

  if [[ -n "${BACKUP_PROVIDER:-}" ]] && command -v rclone >/dev/null 2>&1; then
    remote="${BACKUP_PROVIDER}:${BACKUP_BUCKET:-hosting-backups}/${user}/${stamp}.tar.gz"
    rclone copy "$archive" "$(dirname "$remote" | sed 's#:#:/#')" --quiet || {
      echo "[backup] $user: не удалось выгрузить в удалённое хранилище (архив остался локально)" >&2
      remote=""
    }
  fi

  "$PHP_BIN" "$RECORDER" result --backup-id="$backup_id" --status=success \
    --local="$archive" --checksum="$checksum" --size="$size" --remote="$remote"

  echo "[backup] $user: OK ($archive, $(numfmt --to=iec "$size" 2>/dev/null || echo "${size}B"))"

  rotate_backups "${BACKUP_DIR}/${user}"
}

# Ротация: 7 daily (по имени файла), еженедельно/ежемесячно копируем в подпапки и чистим их отдельно.
rotate_backups() {
  local dir="$1"
  mkdir -p "$dir/weekly" "$dir/monthly"

  # daily — всё, что лежит прямо в $dir (не считая weekly/monthly), оставляем последние 7
  find "$dir" -maxdepth 1 -name '*.tar.gz' -printf '%T@ %p\n' 2>/dev/null \
    | sort -rn | awk 'NR>7{print $2}' | xargs -r rm -f

  local latest
  latest=$(find "$dir" -maxdepth 1 -name '*.tar.gz' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | awk '{print $2}')
  if [[ -n "$latest" ]]; then
    if [[ "$(date -u +%u)" == "7" ]]; then # воскресенье
      cp "$latest" "$dir/weekly/$(basename "$latest")"
    fi
    if [[ "$(date -u +%d)" == "01" ]]; then
      cp "$latest" "$dir/monthly/$(basename "$latest")"
    fi
  fi

  find "$dir/weekly" -maxdepth 1 -name '*.tar.gz' -printf '%T@ %p\n' 2>/dev/null \
    | sort -rn | awk 'NR>4{print $2}' | xargs -r rm -f
  find "$dir/monthly" -maxdepth 1 -name '*.tar.gz' -printf '%T@ %p\n' 2>/dev/null \
    | sort -rn | awk 'NR>3{print $2}' | xargs -r rm -f
}

mkdir -p "$BACKUP_DIR"

if [[ "$MODE" == "one" ]]; then
  backup_one_user "$TARGET_USER" "$BACKUP_ID"
else
  status=0
  for home in "${HOSTING_USERS_ROOT}"/client*; do
    [[ -d "$home" ]] || continue
    backup_one_user "$(basename "$home")" "" || status=1
  done
  exit $status
fi
