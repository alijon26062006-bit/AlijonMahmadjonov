#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  ZVER TAJ — полное удаление с сервера
#
#  Запуск:  bash uninstall.sh
#
#  Что убирает: сервис zverbot, папку /opt/zverbot, системного
#  пользователя, базу zver и её пользователя, временные файлы.
#
#  Базу перед удалением сохраняет в /root/zver-backup-ДАТА.sql.gz
#  Чтобы снести и бэкап, и саму MariaDB:  PURGE=1 bash uninstall.sh
# ═══════════════════════════════════════════════════════════════

set -uo pipefail          # без -e: удаление должно доводиться до конца

DIR="${DIR:-/opt/zverbot}"
SVC="${SVC:-zverbot}"
RUN_USER="${RUN_USER:-zverbot}"
DB_NAME="${DB_NAME:-zver}"
DB_USER="${DB_USER:-zver}"
PURGE="${PURGE:-0}"

red()  { echo -e "\033[31m$*\033[0m"; }
grn()  { echo -e "\033[32m  ✔ $*\033[0m"; }
ylw()  { echo -e "\033[33m$*\033[0m"; }
info() { echo -e "\033[36m▸ $*\033[0m"; }
skip() { echo -e "\033[90m  · $*\033[0m"; }

echo
echo -e "\033[1;31m═══ УДАЛЕНИЕ ZVER TAJ ═══\033[0m"
echo

[ "$(id -u)" -eq 0 ] || { red "✘ Нужен root: sudo bash uninstall.sh"; exit 1; }

BACKUP=""

# ---------- 1. бэкап базы ----------
if [ "$PURGE" != "1" ] && command -v mysqldump >/dev/null 2>&1; then
    if mysql -e "USE \`${DB_NAME}\`" >/dev/null 2>&1; then
        info "Сохраняю базу перед удалением…"
        BACKUP="/root/zver-backup-$(date +%Y%m%d-%H%M%S).sql"
        if mysqldump --default-character-set=utf8mb4 --single-transaction \
                     --no-tablespaces "${DB_NAME}" > "$BACKUP" 2>/dev/null; then
            gzip -f "$BACKUP" && BACKUP="${BACKUP}.gz"
            grn "копия: $BACKUP ($(du -h "$BACKUP" | cut -f1))"
        else
            rm -f "$BACKUP"; BACKUP=""
            ylw "  Снять копию не удалось — база всё равно будет удалена"
        fi
    else
        skip "базы ${DB_NAME} нет, копировать нечего"
    fi
fi

# ---------- 2. сервис ----------
info "Останавливаю сервис…"
UNIT="/etc/systemd/system/${SVC}.service"
# Ориентируемся на файл юнита, а не на вывод systemctl: если systemctl
# недоступен, файл всё равно надо убрать, иначе он останется на диске.
if [ -f "$UNIT" ] || systemctl list-unit-files 2>/dev/null | grep -q "^${SVC}.service"; then
    systemctl stop "$SVC"    >/dev/null 2>&1
    systemctl disable "$SVC" >/dev/null 2>&1
    rm -f "$UNIT"
    systemctl daemon-reload  >/dev/null 2>&1
    systemctl reset-failed   >/dev/null 2>&1
    grn "сервис ${SVC} остановлен, юнит удалён"
else
    skip "сервиса ${SVC} не было"
fi

# на всякий случай добиваем процессы, если остались
pkill -f "${DIR}/bot.py" >/dev/null 2>&1 && grn "оставшиеся процессы бота завершены" || true

# ---------- 3. база ----------
info "Удаляю базу данных…"
if command -v mysql >/dev/null 2>&1 && mysql -e "SELECT 1" >/dev/null 2>&1; then
    mysql -e "DROP DATABASE IF EXISTS \`${DB_NAME}\`;" 2>/dev/null
    for H in 'localhost' '127.0.0.1' '%'; do
        mysql -e "DROP USER IF EXISTS '${DB_USER}'@'$H';" 2>/dev/null
    done
    mysql -e "FLUSH PRIVILEGES;" 2>/dev/null
    grn "база ${DB_NAME} и пользователь ${DB_USER} удалены"
else
    skip "MariaDB недоступна, базу пропускаю"
fi

# ---------- 4. файлы ----------
info "Удаляю файлы…"
if [ -d "$DIR" ]; then
    rm -rf "$DIR"
    grn "папка $DIR удалена"
else
    skip "папки $DIR не было"
fi

for f in /root/ip.sh /root/i.sh /root/imp.sh ./ip.sh ./i.sh; do
    [ -f "$f" ] && { rm -f "$f"; grn "удалён $f"; }
done

# ---------- 5. пользователь ----------
info "Удаляю системного пользователя…"
if id -u "$RUN_USER" >/dev/null 2>&1; then
    userdel "$RUN_USER" >/dev/null 2>&1 && grn "пользователь $RUN_USER удалён" \
        || ylw "  не удалось удалить $RUN_USER"
else
    skip "пользователя $RUN_USER не было"
fi

# ---------- 6. полная зачистка ----------
if [ "$PURGE" = "1" ]; then
    info "Полная зачистка: сношу MariaDB и старые копии…"
    export DEBIAN_FRONTEND=noninteractive
    apt-get purge -y -qq mariadb-server mariadb-client mariadb-common >/dev/null 2>&1
    apt-get autoremove -y -qq >/dev/null 2>&1
    rm -rf /var/lib/mysql /etc/mysql
    rm -f /root/zver-backup-*.sql.gz /root/zver-backup-*.sql
    grn "MariaDB удалена, копии стёрты"
fi

# ---------- что осталось ----------
echo
echo -e "\033[1;32m═══ УДАЛЕНО ═══\033[0m"
echo
LEFT=0
[ -d "$DIR" ]                               && { red "  осталась папка $DIR"; LEFT=1; }
[ -f "/etc/systemd/system/${SVC}.service" ] && { red "  остался юнит ${SVC}"; LEFT=1; }
id -u "$RUN_USER" >/dev/null 2>&1           && { red "  остался пользователь ${RUN_USER}"; LEFT=1; }
mysql -e "USE \`${DB_NAME}\`" >/dev/null 2>&1 && { red "  осталась база ${DB_NAME}"; LEFT=1; }
[ "$LEFT" -eq 0 ] && echo "  Следов проекта на сервере не осталось."
echo

if [ -n "$BACKUP" ]; then
    ylw "  Копия базы сохранена: $BACKUP"
    echo "  Вернуть данные потом:"
    echo "    zcat $BACKUP | mysql ИМЯ_БАЗЫ"
    echo
    echo "  Если копия не нужна:  rm -f $BACKUP"
    echo
fi

if [ "$PURGE" != "1" ]; then
    skip "MariaDB и Python оставлены — их могут использовать другие проекты."
    skip "Снести и их:  PURGE=1 bash uninstall.sh"
    echo
fi
