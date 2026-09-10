#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  ZVER TAJ — перенос базы со старого хостинга
#
#  Запуск:  sudo bash import-db.sh /root/zver_dump.sql
#
#  Что делает:
#    1. читает доступы из /var/www/zver/config.php
#    2. делает резервную копию текущей базы
#    3. импортирует дамп
#    4. запускает ?setup=1 — дописывает недостающие колонки v13.1
#    5. показывает, сколько строк получилось
#
#  Если что-то пошло не так — откат одной командой, её печатает сам скрипт.
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

DUMP="${1:-}"
DIR="${DIR:-/var/www/zver}"
CFG="$DIR/config.php"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="/root/zver-backup-${STAMP}.sql"

red()  { echo -e "\033[31m$*\033[0m"; }
grn()  { echo -e "\033[32m  ✔ $*\033[0m"; }
ylw()  { echo -e "\033[33m$*\033[0m"; }
info() { echo -e "\033[36m▸ $*\033[0m"; }
die()  { red "✘ $*"; exit 1; }

echo
echo -e "\033[1;36m═══ Перенос базы ZVER TAJ ═══\033[0m"
echo

[ "$(id -u)" -eq 0 ] || die "Нужен root: sudo bash import-db.sh дамп.sql"
[ -n "$DUMP" ]       || die "Укажите файл дампа: sudo bash import-db.sh /root/zver_dump.sql"
[ -f "$DUMP" ]       || die "Файл не найден: $DUMP"
[ -f "$CFG" ]        || die "Нет $CFG — сначала запустите install.sh"

# ---------- доступы ----------
cfg() { php -r '$c=@require $argv[1]; echo isset($c[$argv[2]])&&!is_array($c[$argv[2]])?(string)$c[$argv[2]]:"";' "$CFG" "$1"; }
DB_NAME="$(cfg db_name)"; DB_USER="$(cfg db_user)"
DB_PASS="$(cfg db_pass)"; SECRET="$(cfg secret)"
[ -n "$DB_NAME" ] || die "Не смог прочитать доступы к базе из config.php"
info "База: $DB_NAME"

MY=(mysql --default-character-set=utf8mb4 -u "$DB_USER" -p"$DB_PASS" "$DB_NAME")
MYD=(mysqldump --default-character-set=utf8mb4 --single-transaction --no-tablespaces -u "$DB_USER" -p"$DB_PASS" "$DB_NAME")

"${MY[@]}" -e "SELECT 1" >/dev/null 2>&1 || die "Не подключаюсь к базе — проверьте config.php"
grn "подключение к базе работает"

# ---------- проверка дампа ----------
info "Проверяю дамп…"
# phpMyAdmin часто отдаёт архив — распакуем сами, оригинал не трогаем
TMPSQL=""
case "$DUMP" in
    *.gz)
        command -v gunzip >/dev/null || die "нет gunzip: apt-get install -y gzip"
        TMPSQL="$(mktemp /tmp/zver-dump-XXXX.sql)"
        gunzip -c "$DUMP" > "$TMPSQL" || die "не удалось распаковать $DUMP"
        info "Распаковал архив"
        DUMP="$TMPSQL" ;;
    *.zip)
        command -v unzip >/dev/null || { apt-get install -y -qq unzip >/dev/null 2>&1 || true; }
        command -v unzip >/dev/null || die "нет unzip: apt-get install -y unzip"
        TMPD="$(mktemp -d)"
        unzip -qo "$DUMP" -d "$TMPD" || die "не удалось распаковать $DUMP"
        TMPSQL="$(find "$TMPD" -name '*.sql' | head -1)"
        [ -n "$TMPSQL" ] || die "в архиве нет .sql файла"
        info "Распаковал архив"
        DUMP="$TMPSQL" ;;
esac
trap '[ -n "${TMPSQL:-}" ] && rm -f "$TMPSQL"; [ -n "${TMPD:-}" ] && rm -rf "$TMPD"' EXIT

SIZE="$(du -h "$DUMP" | cut -f1)"
head -c 4000 "$DUMP" | grep -qiE "CREATE TABLE|INSERT INTO" \
    || die "Не похоже на SQL-дамп — внутри нет ни CREATE TABLE, ни INSERT"

TBL="$(grep -oiE "CREATE TABLE [\`\"']?z_[a-z_]+" "$DUMP" | grep -oE "z_[a-z_]+" | sort -u | tr '\n' ' ' || true)"
echo "  размер: $SIZE"
echo "  таблицы в дампе: ${TBL:-не найдены}"
[ -n "$TBL" ] || ylw "  ⚠ Таблиц z_* не видно. Точно дамп от ZVER TAJ?"

if grep -qiE "^\s*(DROP DATABASE|CREATE DATABASE)" "$DUMP"; then
    ylw "  ⚠ В дампе есть CREATE/DROP DATABASE — импортирую только в $DB_NAME"
fi

# ---------- было ----------
count() { "${MY[@]}" -N -B -e "SELECT COUNT(*) FROM $1" 2>/dev/null || echo "—"; }
echo
info "Сейчас в базе:"
for t in z_users z_orders z_topups z_tx; do
    printf "  %-12s %s\n" "$t" "$(count $t)"
done

# ---------- бэкап ----------
echo
info "Делаю резервную копию…"
"${MYD[@]}" > "$BACKUP" 2>/dev/null || die "Не удалось сделать бэкап — импорт отменён"
gzip -f "$BACKUP"; BACKUP="${BACKUP}.gz"
grn "копия: $BACKUP ($(du -h "$BACKUP" | cut -f1))"

# ---------- импорт ----------
echo

# Установщик уже создал пустые таблицы. Если дамп сам их создаёт, но без
# DROP TABLE, импорт упал бы на «таблица уже существует». Поэтому пустые
# таблицы, которые есть в дампе, убираем заранее — данные из дампа их
# полностью заменят. Копия базы уже снята выше.
if grep -qiE "CREATE TABLE.*z_" "$DUMP" && ! grep -qiE "DROP TABLE.*z_" "$DUMP"; then
    info "Дамп создаёт таблицы сам — освобождаю место…"
    DROPPED=0
    for t in $(grep -oiE "CREATE TABLE (IF NOT EXISTS )?[\`\"']?z_[a-z_]+" "$DUMP" \
               | grep -oE "z_[a-z_]+" | sort -u); do
        rows="$("${MY[@]}" -N -B -e "SELECT COUNT(*) FROM \`$t\`" 2>/dev/null || echo 0)"
        if [ "${rows:-0}" -gt 0 ]; then
            ylw "  ⚠ в таблице $t уже есть $rows строк — она будет заменена данными из дампа"
        fi
        "${MY[@]}" -e "SET FOREIGN_KEY_CHECKS=0; DROP TABLE IF EXISTS \`$t\`;" 2>/dev/null \
            && DROPPED=$((DROPPED+1))
    done
    grn "освобождено таблиц: $DROPPED"
fi

info "Импортирую дамп…"
if "${MY[@]}" < "$DUMP" 2>/tmp/imp.err; then
    grn "дамп залит"
else
    red "Ошибка импорта:"
    tail -5 /tmp/imp.err | sed 's/^/    /'
    echo
    ylw "База не тронута безвозвратно — откат:"
    echo "  zcat $BACKUP | mysql -u $DB_USER -p'ПАРОЛЬ_ИЗ_CONFIG' $DB_NAME"
    exit 1
fi
[ -s /tmp/imp.err ] && { ylw "  предупреждения:"; head -3 /tmp/imp.err | sed 's/^/    /'; }
rm -f /tmp/imp.err

# ---------- миграция структуры ----------
echo
info "Дописываю колонки версии 13.1…"
DOMAIN="$(grep -m1 -oP 'server_name\s+\K[^;]+' /etc/nginx/sites-available/zver 2>/dev/null | awk '{print $1}' || true)"
if [ -n "$DOMAIN" ] && [ -n "$SECRET" ]; then
    curl -sS --max-time 90 "https://${DOMAIN}/zbot.php?setup=1&secret=${SECRET}" \
        | sed 's/<[^>]*>//g' | grep -v '^\s*$' | head -20 | sed 's/^/    /' || \
        ylw "  не достучался до сайта — откройте вручную:
    https://${DOMAIN}/zbot.php?setup=1&secret=${SECRET}"
else
    ylw "  домен не определился — откройте вручную:
    https://ВАШ_ДОМЕН/zbot.php?setup=1&secret=СЕКРЕТ"
fi

# ---------- стало ----------
echo
info "Стало в базе:"
for t in z_users z_orders z_topups z_tx; do
    printf "  %-12s %s\n" "$t" "$(count $t)"
done

echo
info "Проверка сумм:"
"${MY[@]}" -e "
SELECT COUNT(*) AS 'пользователей', ROUND(SUM(balance),2) AS 'общий баланс' FROM z_users;
" 2>/dev/null | sed 's/^/  /' || ylw "  не смог посчитать (нет колонки balance?)"

echo
echo -e "\033[1;32m═══ Перенос завершён ═══\033[0m"
echo
echo "  Резервная копия старого состояния: $BACKUP"
echo "  Откат, если что-то не так:"
echo "    zcat $BACKUP | mysql -u $DB_USER -p'ПАРОЛЬ_ИЗ_CONFIG' $DB_NAME"
echo
[ -n "$DOMAIN" ] && echo "  Диагностика: https://${DOMAIN}/zbot.php?diag=1&secret=${SECRET}"
echo
ylw "  Проверьте в боте: баланс любого пользователя и список заказов."
echo
