#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  ZVER TAJ (PHP) — полное удаление с сервера
#
#  Запуск:  bash uninstall.sh
#
#  Убирает: папку /var/www/zver, конфиг nginx, базу zver и её
#  пользователя, задания cron, SSL-сертификат, вебхук Telegram.
#
#  Базу перед удалением сохраняет в /root/zver-backup-ДАТА.sql.gz
#  Снести всё вместе с nginx, PHP, MariaDB и копией базы:
#      PURGE=1 bash uninstall.sh
# ═══════════════════════════════════════════════════════════════

set -uo pipefail          # без -e: удаление должно доводиться до конца

DIR="${DIR:-/var/www/zver}"
DB_NAME="${DB_NAME:-zver}"
DB_USER="${DB_USER:-zver}"
SITE="${SITE:-/etc/nginx/sites-available/zver}"
PURGE="${PURGE:-0}"

red()  { echo -e "\033[31m$*\033[0m"; }
grn()  { echo -e "\033[32m  ✔ $*\033[0m"; }
ylw()  { echo -e "\033[33m$*\033[0m"; }
info() { echo -e "\033[36m▸ $*\033[0m"; }
skip() { echo -e "\033[90m  · $*\033[0m"; }

echo
echo -e "\033[1;31m═══ УДАЛЕНИЕ ZVER TAJ (PHP) ═══\033[0m"
echo

[ "$(id -u)" -eq 0 ] || { red "✘ Нужен root: sudo bash uninstall.sh"; exit 1; }

BACKUP=""
DOMAIN=""
BOT_TOKEN=""

# ---------- 0. что знаем о проекте ----------
if [ -f "$DIR/config.php" ] && command -v php >/dev/null 2>&1; then
    BOT_TOKEN="$(php -r '$c=@require $argv[1]; echo is_array($c)?(string)($c["bot_token"]??""):"";' \
                 "$DIR/config.php" 2>/dev/null || true)"
fi
[ -f "$SITE" ] && DOMAIN="$(grep -m1 -oP 'server_name\s+\K[^;]+' "$SITE" 2>/dev/null | awk '{print $1}')"
[ -n "$DOMAIN" ] && info "Домен проекта: $DOMAIN"

# ---------- 1. копия базы ----------
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
            ylw "  Копию снять не удалось — база всё равно будет удалена"
        fi
    else
        skip "базы ${DB_NAME} нет, копировать нечего"
    fi
fi

# ---------- 2. вебхук Telegram ----------
info "Отключаю вебхук Telegram…"
if [ -n "$BOT_TOKEN" ]; then
    ANS="$(curl -s --max-time 20 \
        "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook?drop_pending_updates=true" || echo '')"
    case "$ANS" in
        *'"ok":true'*) grn "вебхук снят — Telegram больше не стучится на сервер" ;;
        *)             ylw "  не удалось снять вебхук (это не мешает удалению)" ;;
    esac
else
    skip "токен не найден, вебхук пропускаю"
fi

# ---------- 3. cron ----------
info "Убираю задания cron…"
TMPC="$(mktemp)"
crontab -l 2>/dev/null > "$TMPC" || true
BEFORE="$(wc -l < "$TMPC")"
grep -v 'zbot.php' "$TMPC" | grep -v 'duckdns.org/update' > "${TMPC}.new" 2>/dev/null || true
AFTER="$(wc -l < "${TMPC}.new")"
if [ "$BEFORE" != "$AFTER" ]; then
    crontab "${TMPC}.new" && grn "удалено заданий: $((BEFORE - AFTER))"
else
    skip "заданий проекта в cron не было"
fi
rm -f "$TMPC" "${TMPC}.new"

# ---------- 4. nginx ----------
info "Убираю конфиг nginx…"
if [ -f "$SITE" ] || [ -L /etc/nginx/sites-enabled/zver ]; then
    rm -f /etc/nginx/sites-enabled/zver "$SITE" "${SITE}.zver-backup"
    if nginx -t >/dev/null 2>&1; then
        systemctl reload nginx >/dev/null 2>&1
        grn "конфиг удалён, nginx перезагружен"
    else
        ylw "  конфиг удалён, но nginx ругается на остальное:"
        nginx -t 2>&1 | sed 's/^/    /'
    fi
else
    skip "конфига nginx не было"
fi

# ---------- 5. сертификат ----------
info "Убираю SSL-сертификат…"
if [ -n "$DOMAIN" ] && command -v certbot >/dev/null 2>&1; then
    if certbot delete --cert-name "$DOMAIN" --non-interactive >/dev/null 2>&1; then
        grn "сертификат для $DOMAIN удалён"
    else
        skip "сертификата для $DOMAIN не нашлось"
    fi
else
    skip "certbot или домен не определены"
fi

# ---------- 6. база ----------
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

# ---------- 7. файлы ----------
info "Удаляю файлы…"
if [ -d "$DIR" ]; then
    rm -rf "$DIR"
    grn "папка $DIR удалена"
else
    skip "папки $DIR не было"
fi

for f in /root/in.sh /root/ip.sh /root/i.sh /root/imp.sh /root/fs.sh /root/un.sh \
         ./in.sh ./ip.sh ./i.sh ./imp.sh ./fs.sh; do
    [ -f "$f" ] && { rm -f "$f"; grn "удалён $f"; }
done

# ---------- 8. полная зачистка ----------
if [ "$PURGE" = "1" ]; then
    echo
    info "Полная зачистка: сношу nginx, PHP, MariaDB, certbot…"
    export DEBIAN_FRONTEND=noninteractive
    apt-get purge -y -qq 'php*' nginx nginx-common nginx-core \
            mariadb-server mariadb-client mariadb-common \
            certbot python3-certbot-nginx >/dev/null 2>&1
    apt-get autoremove -y -qq >/dev/null 2>&1
    rm -rf /var/lib/mysql /etc/mysql /etc/nginx /etc/php /etc/letsencrypt /var/www
    rm -f /root/zver-backup-*.sql.gz /root/zver-backup-*.sql
    grn "всё снесено, копии стёрты"
fi

# ---------- что осталось ----------
echo
echo -e "\033[1;32m═══ УДАЛЕНО ═══\033[0m"
echo
LEFT=0
[ -d "$DIR" ]                      && { red "  осталась папка $DIR"; LEFT=1; }
[ -f "$SITE" ]                     && { red "  остался конфиг nginx"; LEFT=1; }
[ -L /etc/nginx/sites-enabled/zver ] && { red "  осталась ссылка в sites-enabled"; LEFT=1; }
mysql -e "USE \`${DB_NAME}\`" >/dev/null 2>&1 && { red "  осталась база ${DB_NAME}"; LEFT=1; }
crontab -l 2>/dev/null | grep -q 'zbot.php' && { red "  осталось задание cron"; LEFT=1; }
[ "$LEFT" -eq 0 ] && echo "  Следов проекта на сервере не осталось."
echo

if [ -n "$BACKUP" ]; then
    ylw "  Копия базы: $BACKUP"
    echo "  Вернуть данные потом:  zcat $BACKUP | mysql ИМЯ_БАЗЫ"
    echo "  Если не нужна:         rm -f $BACKUP"
    echo
fi

if [ "$PURGE" != "1" ]; then
    skip "nginx, PHP и MariaDB оставлены — их могут использовать другие сайты."
    skip "Снести и их:  PURGE=1 bash uninstall.sh"
    echo
fi
