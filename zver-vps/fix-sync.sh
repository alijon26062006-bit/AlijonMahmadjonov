#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  ZVER TAJ — поднять лимиты времени для синхронизации каталога
#
#  Запуск:  bash fix-sync.sh
#
#  Зачем: «⟳ СИНК КАТАЛОГ» делает по запросу к API на каждый товар.
#  При 300+ товарах это 5–10 минут. Стандартные лимиты в 120 секунд
#  обрывают её на середине, и каталог остаётся пустым.
#
#  Что меняет: время выполнения PHP, таймаут PHP-FPM и nginx,
#  и ignore_user_abort — чтобы обрыв связи не убивал работу.
# ═══════════════════════════════════════════════════════════════

set -uo pipefail

LIMIT="${LIMIT:-1800}"          # 30 минут с запасом
SITE="${SITE:-/etc/nginx/sites-available/zver}"

red()  { echo -e "\033[31m$*\033[0m"; }
grn()  { echo -e "\033[32m  ✔ $*\033[0m"; }
ylw()  { echo -e "\033[33m$*\033[0m"; }
info() { echo -e "\033[36m▸ $*\033[0m"; }
die()  { red "✘ $*"; exit 1; }

echo
echo -e "\033[1;36m═══ Лимиты для синхронизации каталога ═══\033[0m"
echo

[ "$(id -u)" -eq 0 ] || die "Нужен root: sudo bash fix-sync.sh"

# ---------- версия PHP ----------
PHPV="$(ls -1 /etc/php 2>/dev/null | grep -E '^[0-9]+\.[0-9]+$' | sort -V | tail -1)"
[ -n "$PHPV" ] || die "PHP не найден в /etc/php"
info "PHP $PHPV"

PHPINI="/etc/php/${PHPV}/fpm/php.ini"
POOL="/etc/php/${PHPV}/fpm/pool.d/www.conf"

# ---------- php.ini ----------
if [ -f "$PHPINI" ]; then
    cp -n "$PHPINI" "${PHPINI}.zver-backup" 2>/dev/null || true
    sed -i "s|^;\?\s*max_execution_time\s*=.*|max_execution_time = ${LIMIT}|" "$PHPINI"
    sed -i "s|^;\?\s*max_input_time\s*=.*|max_input_time = ${LIMIT}|"         "$PHPINI"
    sed -i "s|^;\?\s*ignore_user_abort\s*=.*|ignore_user_abort = On|"         "$PHPINI"
    sed -i "s|^;\?\s*default_socket_timeout\s*=.*|default_socket_timeout = 120|" "$PHPINI"
    grep -q '^ignore_user_abort' "$PHPINI" || echo "ignore_user_abort = On" >> "$PHPINI"
    grn "php.ini: время выполнения ${LIMIT} с, обрыв связи не прерывает работу"
else
    ylw "  $PHPINI не найден — пропускаю"
fi

# ---------- пул PHP-FPM ----------
if [ -f "$POOL" ]; then
    cp -n "$POOL" "${POOL}.zver-backup" 2>/dev/null || true
    if grep -q '^;\?\s*request_terminate_timeout' "$POOL"; then
        sed -i "s|^;\?\s*request_terminate_timeout\s*=.*|request_terminate_timeout = ${LIMIT}|" "$POOL"
    else
        echo "request_terminate_timeout = ${LIMIT}" >> "$POOL"
    fi
    grn "пул PHP-FPM: принудительное завершение через ${LIMIT} с"
else
    ylw "  $POOL не найден — пропускаю"
fi

# ---------- nginx ----------
if [ -f "$SITE" ]; then
    cp -n "$SITE" "${SITE}.zver-backup" 2>/dev/null || true
    if grep -q 'fastcgi_read_timeout' "$SITE"; then
        sed -i "s|fastcgi_read_timeout .*;|fastcgi_read_timeout ${LIMIT};|" "$SITE"
    else
        sed -i "s|fastcgi_pass |fastcgi_read_timeout ${LIMIT};\n        fastcgi_pass |" "$SITE"
    fi
    grep -q 'fastcgi_send_timeout' "$SITE" \
        || sed -i "s|fastcgi_read_timeout |fastcgi_send_timeout ${LIMIT};\n        fastcgi_read_timeout |" "$SITE"
    grn "nginx: таймаут до PHP ${LIMIT} с"
else
    ylw "  $SITE не найден — пропускаю"
fi

# ---------- применяем ----------
echo
info "Перезапускаю…"
if nginx -t >/dev/null 2>&1; then
    systemctl reload nginx && grn "nginx перезагружен"
else
    red "  Конфиг nginx не прошёл проверку, откатываю:"
    nginx -t 2>&1 | sed 's/^/    /'
    [ -f "${SITE}.zver-backup" ] && cp "${SITE}.zver-backup" "$SITE" && systemctl reload nginx
    die "изменения nginx откачены"
fi
systemctl restart "php${PHPV}-fpm" && grn "PHP-FPM перезапущен"

# ---------- что получилось ----------
echo
info "Проверяю:"
php -r 'echo "  php-cli max_execution_time = ", ini_get("max_execution_time"), "\n";' 2>/dev/null || true
grep -m1 '^max_execution_time' "$PHPINI" 2>/dev/null | sed 's/^/  fpm: /'
grep -m1 '^ignore_user_abort' "$PHPINI" 2>/dev/null | sed 's/^/  fpm: /'
grep -m1 '^request_terminate_timeout' "$POOL" 2>/dev/null | sed 's/^/  pool: /'
grep -m1 'fastcgi_read_timeout' "$SITE" 2>/dev/null | sed 's/^ *//; s/^/  nginx: /'

echo
echo -e "\033[1;32m═══ ГОТОВО ═══\033[0m"
echo
ylw "  Теперь в боте: /admin → ⟳ СИНК КАТАЛОГ"
echo "  Нажмите ОДИН раз и ждите — при 300+ товарах это 5–10 минут."
echo "  Появится полоса загрузки, она обновляется каждые 3 секунды."
echo
echo "  Проверить результат:"
echo "    /admin → ▪ БОЗИҲО   (должны появиться игры)"
echo
