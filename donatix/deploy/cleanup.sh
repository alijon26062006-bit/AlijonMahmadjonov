#!/usr/bin/env bash
# Уборка мусора ТОЛЬКО проекта Donatix (/home/donatix). Другие проекты на сервере не трогает.
#
# НЕ удаляет: базу, чеки (data/receipts), файлы тикетов, видео, .env, аккаунты и балансы людей.
# Сначала делает свежую копию базы в /home/donatix/backup — даже если что-то пойдёт не так, данные целы.
#
# Удаляет: кэш Python (__pycache__, *.pyc), кэш pip пользователя donatix, старые копии .env.bak (оставляет 3),
# копии базы старше 14 дней (оставляет минимум 3 последние), временные файлы, мусор git (git gc).
# Служебные строки в базе (истёкшие коды входа, старый кэш ников) — убирает сайт сам каждую ночь в 4:00.
#
#   sudo bash /home/donatix/app/donatix/deploy/cleanup.sh            # обычная уборка, сайт работает
#   sudo bash /home/donatix/app/donatix/deploy/cleanup.sh --vacuum   # + сжать базу (сайт остановится ~10–30 с)
set -uo pipefail
APP_USER="donatix"
HOME_DIR="/home/$APP_USER"
APP_DIR="$HOME_DIR/app"
DATA_DIR="$APP_DIR/donatix/data"
DB="$DATA_DIR/donatix.db"
BACKUP_DIR="$HOME_DIR/backup"
ENV_FILE="$APP_DIR/donatix/.env"
VACUUM=0; [ "${1:-}" = "--vacuum" ] && VACUUM=1

ok() { echo "  ✓ $*"; }
size() { du -sh "$1" 2>/dev/null | cut -f1; }

[ -d "$APP_DIR" ] || { echo "Нет $APP_DIR — это не сервер Donatix"; exit 1; }
[ -f "$DB" ] || { echo "Нет базы $DB — остановлено, ничего не удалено"; exit 1; }

echo "== До уборки"
echo "  диск: $(df -h / | awk 'NR==2{print $3" занято из "$2", свободно "$4}')"
echo "  проект: $(size "$HOME_DIR")   база: $(size "$DB") (+WAL $(size "$DB-wal"))   чеки: $(size "$DATA_DIR/receipts")"

echo "== 1. Копия базы (до любых изменений)"
mkdir -p "$BACKUP_DIR"; chown "$APP_USER": "$BACKUP_DIR"
COPY="$BACKUP_DIR/donatix-$(date +%F-%H%M).db"
if sudo -u "$APP_USER" sqlite3 "$DB" ".backup '$COPY'" && [ -s "$COPY" ] \
        && [ "$(sqlite3 "$COPY" 'PRAGMA quick_check' 2>/dev/null)" = "ok" ]; then
    ok "копия: $COPY ($(size "$COPY"))"
else
    echo "  ✗ копия базы не получилась — дальше не иду, ничего не удалено"; rm -f "$COPY"; exit 1
fi
# копии старше 14 дней — удалить, но 3 самые свежие оставить всегда
ls -1t "$BACKUP_DIR"/donatix-*.db 2>/dev/null | tail -n +4 | while read -r f; do
    [ -n "$(find "$f" -mtime +14 2>/dev/null)" ] && rm -f "$f"
done
ok "копий базы: $(ls -1 "$BACKUP_DIR"/donatix-*.db 2>/dev/null | wc -l) ($(size "$BACKUP_DIR"))"

echo "== 2. Кэш Python и pip"
find "$APP_DIR" -name "__pycache__" -type d -prune -exec rm -rf {} + 2>/dev/null
find "$APP_DIR" -name "*.py[co]" -type f -delete 2>/dev/null
rm -rf "$APP_DIR"/.pytest_cache "$APP_DIR"/donatix/.pytest_cache "$APP_DIR"/donatix/.ruff_cache 2>/dev/null
rm -rf "$HOME_DIR/.cache/pip" 2>/dev/null
ok "убрано (Python сам создаст нужный кэш заново)"

echo "== 3. Старые копии .env (там ключи — лишние копии лучше не держать)"
ls -1t "$ENV_FILE".bak* 2>/dev/null | tail -n +4 | xargs -r rm -f
ok "оставлено: $(ls -1 "$ENV_FILE".bak* 2>/dev/null | wc -l)"

echo "== 4. Временные файлы проекта"
find "$DATA_DIR" -maxdepth 2 -type f \( -name "*.tmp" -o -name "*.part" \) -mmin +60 -delete 2>/dev/null
find /tmp -maxdepth 1 -user "$APP_USER" -mtime +2 -exec rm -rf {} + 2>/dev/null
ok "готово"

echo "== 5. Git"
sudo -u "$APP_USER" git -C "$APP_DIR" gc --prune=now -q 2>/dev/null && ok "git gc" || echo "  - git gc пропущен"

if [ "$VACUUM" = 1 ]; then
    echo "== 6. Сжатие базы (сайт и автоплатежи на паузе)"
    systemctl stop donatix donatix-bankbot 2>/dev/null
    if sudo -u "$APP_USER" sqlite3 "$DB" "PRAGMA wal_checkpoint(TRUNCATE); VACUUM; PRAGMA optimize;"; then
        ok "база сжата: $(size "$DB")"
    else
        echo "  ✗ VACUUM не прошёл — база не изменена, копия в $COPY"
    fi
    systemctl start donatix 2>/dev/null
    systemctl is-enabled donatix-bankbot >/dev/null 2>&1 && systemctl start donatix-bankbot
    sleep 3; ok "сайт: $(systemctl is-active donatix)"
else
    sudo -u "$APP_USER" sqlite3 "$DB" "PRAGMA wal_checkpoint(PASSIVE);" >/dev/null 2>&1
fi

echo "== После уборки"
echo "  диск: $(df -h / | awk 'NR==2{print $3" занято из "$2", свободно "$4}')"
echo "  проект: $(size "$HOME_DIR")   база: $(size "$DB")   чеки: $(size "$DATA_DIR/receipts") — на месте"
echo "  Чеки, тикеты, аккаунты и балансы не тронуты."
