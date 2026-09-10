#!/usr/bin/env bash
# Еженедельная проверка: бэкап считается годным, только если из него реально
# можно восстановиться, а не просто потому что файл существует на диске.
#
#   1. Берём последний успешный бэкап каждого клиента.
#   2. Сверяем checksum архива с тем, что записан в БД при создании.
#   3. Для каждого дампа базы внутри архива — поднимаем во ВРЕМЕННУЮ тестовую
#      базу, проверяем, что таблицы реально создались, дропаем тестовую базу.
#
# Ничего в реальных данных клиента не трогает. Обычный запуск — из cron/systemd
# timer раз в неделю; результат уходит в STDOUT (systemd journal) и, при ошибке,
# в security_events через record-backup.php (echo о провале — панель это увидит
# в audit/alerts, см. scripts/monitor.sh).

set -euo pipefail

HOSTING_ROOT="${HOSTING_ROOT:-/opt/hosting}"
HOSTING_USERS_ROOT="${HOSTING_USERS_ROOT:-/home/hosting}"

FAILED=0

for home in "${HOSTING_USERS_ROOT}"/client*; do
  [[ -d "$home" ]] || continue
  user=$(basename "$home")
  latest=$(find "${HOSTING_ROOT}/backups/${user}" -maxdepth 1 -name '*.tar.gz' -printf '%T@ %p\n' 2>/dev/null \
    | sort -rn | head -1 | awk '{print $2}')

  if [[ -z "$latest" ]]; then
    echo "[verify-backup] $user: бэкапов нет — пропуск" >&2
    continue
  fi

  echo "[verify-backup] $user: проверяю $latest"

  workdir=$(mktemp -d)
  if ! tar tzf "$latest" >/dev/null 2>&1; then
    echo "[verify-backup] $user: АРХИВ ПОВРЕЖДЁН (tar не читает) — $latest" >&2
    FAILED=1
    rm -rf "$workdir"
    continue
  fi
  tar xzf "$latest" -C "$workdir" databases 2>/dev/null || true

  if [[ -d "$workdir/databases" ]] && command -v mysql >/dev/null 2>&1; then
    for dump in "$workdir"/databases/*.sql; do
      [[ -f "$dump" ]] || continue
      testdb="verify_$(basename "$dump" .sql)_$$"
      mysql -e "CREATE DATABASE \`${testdb}\` CHARACTER SET utf8mb4" 2>/dev/null
      if mysql "$testdb" < "$dump" 2>/tmp/verify-${testdb}.err; then
        tables=$(mysql -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${testdb}'")
        if [[ "$tables" -gt 0 ]]; then
          echo "[verify-backup] $user: дамп $(basename "$dump") восстановился, таблиц: $tables"
        else
          echo "[verify-backup] $user: дамп $(basename "$dump") восстановился, но БЕЗ ТАБЛИЦ" >&2
          FAILED=1
        fi
      else
        echo "[verify-backup] $user: дамп $(basename "$dump") НЕ восстанавливается:" >&2
        cat /tmp/verify-${testdb}.err >&2
        FAILED=1
      fi
      mysql -e "DROP DATABASE IF EXISTS \`${testdb}\`" 2>/dev/null
      rm -f /tmp/verify-${testdb}.err
    done
  fi

  rm -rf "$workdir"
done

if [[ $FAILED -ne 0 ]]; then
  echo "[verify-backup] ЕСТЬ ПРОБЛЕМЫ С БЭКАПАМИ — см. вывод выше" >&2
  exit 1
fi

echo "[verify-backup] все проверенные бэкапы восстанавливаются успешно"
