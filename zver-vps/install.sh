#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  ZVER TAJ — установка на чистый VPS одной командой
#  Ubuntu 22.04 / 24.04 · Debian 11 / 12
#
#  Запуск:
#    sudo bash install.sh
#
#  Всё спросит сам. Можно и без вопросов — через переменные:
#    sudo DOMAIN=my.duckdns.org BOT_TOKEN=... bash install.sh
# ═══════════════════════════════════════════════════════════════

set -euo pipefail

# ---------- настройки по умолчанию ----------
REPO="${REPO:-alijon26062006-bit/AlijonMahmadjonov}"
BRANCH="${BRANCH:-claude/zver-taj-server-deploy-gom4he}"
RAW="${RAW:-https://raw.githubusercontent.com/${REPO}/refs/heads/${BRANCH}/zver-vps}"
DIR="${DIR:-/var/www/zver}"
DB_NAME="${DB_NAME:-zver}"
DB_USER="${DB_USER:-zver}"

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd || echo /tmp)"
WORK=""

# ---------- вывод ----------
red()  { echo -e "\033[31m$*\033[0m"; }
grn()  { echo -e "\033[32m  ✔ $*\033[0m"; }
ylw()  { echo -e "\033[33m$*\033[0m"; }
info() { echo -e "\033[36m▸ $*\033[0m"; }
die()  { red "✘ $*"; exit 1; }

cleanup() { [ -n "$WORK" ] && rm -rf "$WORK" || true; }
trap cleanup EXIT

echo
echo -e "\033[1;36m═══ ZVER TAJ — установка ═══\033[0m"
echo

# ---------- 0. проверки ----------
[ "$(id -u)" -eq 0 ] || die "Нужен root. Запустите: sudo bash install.sh"

[ -r /etc/os-release ] || die "Не могу определить ОС"
. /etc/os-release
info "ОС: ${PRETTY_NAME:-$ID $VERSION_ID}"
case "$ID" in
    ubuntu|debian) ;;
    *) die "Поддерживаются Ubuntu и Debian. У вас: $ID" ;;
esac

INTERACTIVE=0
[ -t 0 ] && INTERACTIVE=1

ask() {                       # ask ПЕРЕМЕННАЯ "Вопрос" [обязательно]
    local var="$1" prompt="$2" required="${3:-0}" cur ans
    cur="${!var:-}"
    [ -n "$cur" ] && return 0
    if [ "$INTERACTIVE" -eq 0 ]; then
        [ "$required" -eq 1 ] && die "Нет значения $var (неинтерактивный режим)"
        return 0
    fi
    while :; do
        read -r -p "  $prompt: " ans || ans=""
        if [ -n "$ans" ]; then printf -v "$var" '%s' "$ans"; return 0; fi
        [ "$required" -eq 0 ] && return 0
        red "  Это поле обязательно."
    done
}

# ---------- 1. исходники ----------
info "Ищу файлы проекта…"
if [ -f "$SRC/zbot.php" ] && [ -f "$SRC/zapp.php" ]; then
    CODE="$SRC"
    grn "файлы рядом со скриптом: $SRC"
else
    command -v curl >/dev/null || { apt-get update -qq; apt-get install -y -qq curl; }
    WORK="$(mktemp -d)"
    CODE="$WORK"

    # Для публичного файла лишний заголовок Authorization заставляет GitHub
    # ответить 404, поэтому сначала пробуем без него, а токен подключаем
    # только если без него не вышло.
    fetch() {                       # fetch <файл> <куда>
        curl -fsSL "${RAW}/$1" -o "$2" 2>/dev/null && return 0
        if [ -n "${GH_TOKEN:-}" ]; then
            curl -fsSL -H "Authorization: Bearer ${GH_TOKEN}" \
                 "${RAW}/$1" -o "$2" 2>/dev/null && return 0
        fi
        return 1
    }

    info "Скачиваю код бота…"
    ok=1
    for f in zbot.php zapp.php config.example.php; do
        if ! fetch "$f" "$WORK/${f}"; then
            [ "$f" = "config.example.php" ] && continue
            ok=0; break
        fi
    done

    if [ "$ok" -eq 0 ]; then
        red "Не удалось скачать файлы проекта."
        red "Проверьте ссылку: ${RAW}/zbot.php"
        red "Если репозиторий приватный — передайте токен:"
        red "  sudo GH_TOKEN=ваш_токен bash install.sh"
        exit 1
    fi

    php -l "$WORK/zbot.php" >/dev/null 2>&1 || \
        head -c 200 "$WORK/zbot.php" | grep -q '<?php' || \
        die "Скачанный zbot.php повреждён (получена не та страница)"

    grn "код скачан ($(wc -c < "$WORK/zbot.php") байт)"
fi

# ---------- 2. домен ----------
echo
info "Домен (Telegram работает только по HTTPS)"

if [ -z "${DOMAIN:-}" ] && [ -z "${DUCKDNS_NAME:-}" ] && [ "$INTERACTIVE" -eq 1 ]; then
    echo "  Есть свой домен — введите его."
    echo "  Нет — оставьте пусто, сделаем бесплатный через DuckDNS."
    ask DOMAIN "Ваш домен (Enter = DuckDNS)"
fi

if [ -z "${DOMAIN:-}" ]; then
    ask DUCKDNS_NAME  "Имя поддомена DuckDNS (например zvertaj)" 1
    ask DUCKDNS_TOKEN "Токен с duckdns.org" 1
    DUCKDNS_NAME="${DUCKDNS_NAME%%.duckdns.org}"
    DOMAIN="${DUCKDNS_NAME}.duckdns.org"
fi

if [ -n "${DUCKDNS_NAME:-}" ] && [ -n "${DUCKDNS_TOKEN:-}" ]; then
    info "Привязываю $DOMAIN к этому серверу…"
    DUCK_ANS="$(curl -s "https://www.duckdns.org/update?domains=${DUCKDNS_NAME}&token=${DUCKDNS_TOKEN}&ip=" || echo FAIL)"
    if [ "$DUCK_ANS" = "OK" ]; then
        grn "DuckDNS обновлён"
    else
        red "DuckDNS ответил: $DUCK_ANS"
        die "Проверьте имя поддомена и токен"
    fi
fi

info "Домен: $DOMAIN"

# ---------- 3. пакеты ----------
echo
info "Устанавливаю пакеты (несколько минут)…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq nginx mariadb-server certbot python3-certbot-nginx \
        curl tar cron ca-certificates dnsutils openssl unzip >/dev/null
grn "nginx, MariaDB, certbot"

# PHP: берём самый свежий из репозитория, при нужде подключаем sury/ondrej
PHPV="$(apt-cache search --names-only '^php[0-9.]+-fpm$' 2>/dev/null \
        | grep -oP 'php\K[0-9.]+' | sort -V | tail -1 || true)"

need_repo=1
if [ -n "$PHPV" ]; then
    major="${PHPV%%.*}"; minor="${PHPV#*.}"
    if [ "$major" -gt 8 ] || { [ "$major" -eq 8 ] && [ "$minor" -ge 0 ]; }; then
        need_repo=0
    fi
fi

if [ "$need_repo" -eq 1 ]; then
    info "В системе нет PHP 8+, подключаю сторонний репозиторий…"
    apt-get install -y -qq lsb-release apt-transport-https gnupg >/dev/null
    if [ "$ID" = "ubuntu" ]; then
        apt-get install -y -qq software-properties-common >/dev/null
        add-apt-repository -y ppa:ondrej/php >/dev/null 2>&1
    else
        curl -fsSL https://packages.sury.org/php/apt.gpg \
            -o /usr/share/keyrings/sury-php.gpg
        echo "deb [signed-by=/usr/share/keyrings/sury-php.gpg] https://packages.sury.org/php/ $(lsb_release -sc) main" \
            > /etc/apt/sources.list.d/sury-php.list
    fi
    apt-get update -qq
    PHPV="$(apt-cache search --names-only '^php[0-9.]+-fpm$' \
            | grep -oP 'php\K[0-9.]+' | sort -V | tail -1)"
fi

[ -n "$PHPV" ] || die "PHP-FPM не найден"
apt-get install -y -qq "php${PHPV}-fpm" "php${PHPV}-mysql" "php${PHPV}-curl" \
        "php${PHPV}-mbstring" "php${PHPV}-gd" "php${PHPV}-xml" \
        "php${PHPV}-zip" "php${PHPV}-bcmath" >/dev/null
grn "PHP $PHPV + расширения"

systemctl enable --now mariadb  >/dev/null 2>&1 || true
systemctl enable --now nginx    >/dev/null 2>&1 || true
systemctl enable --now cron     >/dev/null 2>&1 || true

# ---------- 4. секреты / config.php ----------
echo
OLDCFG=""
for c in "$DIR/config.php" "$CODE/config.php" "$SRC/config.php" /root/config.php; do
    [ -f "$c" ] && { OLDCFG="$c"; break; }
done

getcfg() {  # getcfg файл ключ
    php -r '$c=@require $argv[1]; echo is_array($c)&&isset($c[$argv[2]]) && !is_array($c[$argv[2]]) ? (string)$c[$argv[2]] : "";' \
        "$1" "$2" 2>/dev/null || true
}

if [ -n "$OLDCFG" ]; then
    info "Нашёл готовый config.php — беру секреты из него"
    BOT_TOKEN="${BOT_TOKEN:-$(getcfg "$OLDCFG" bot_token)}"
    SECRET="${SECRET:-$(getcfg   "$OLDCFG" secret)}"
    FZ_KEY="${FZ_KEY:-$(getcfg   "$OLDCFG" fz_key)}"
    FZ_HOOK="${FZ_HOOK:-$(getcfg "$OLDCFG" fz_hook)}"
    GS_KEY="${GS_KEY:-$(getcfg   "$OLDCFG" gs_key)}"
    FT_ID="${FT_ID:-$(getcfg     "$OLDCFG" ft_id)}"
    FT_KEY="${FT_KEY:-$(getcfg   "$OLDCFG" ft_key)}"
    DB_PASS="${DB_PASS:-$(getcfg "$OLDCFG" db_pass)}"
    ADMINS_PHP="$(php -r '$c=@require $argv[1]; $a=is_array($c)&&!empty($c["admins"])?$c["admins"]:[]; echo implode(",", array_map("intval",(array)$a));' "$OLDCFG" 2>/dev/null || true)"
    grn "секреты загружены"
else
    info "config.php не найден — заполним сейчас"
    echo
    ylw "  Токен бота берётся у @BotFather, ID админа — у @userinfobot"
    echo
    ask BOT_TOKEN "Токен бота (123456:AAE...)" 1
    ask ADMINS    "Ваш Telegram ID (через запятую, если несколько)" 1
    ask FZ_KEY    "Ключ FazerCards fc_... (Enter — пропустить)"
    ask FZ_HOOK   "Webhook-секрет FazerCards whsec_... (Enter — пропустить)"
    ask GS_KEY    "Ключ gameskinbo для ников (Enter — пропустить)"
    ADMINS_PHP="$(echo "${ADMINS:-}" | tr -cd '0-9,' )"
fi

[ -n "${BOT_TOKEN:-}" ]   || die "Без токена бота установка бессмысленна"
[ -n "${ADMINS_PHP:-}" ]  || die "Нужен хотя бы один Telegram ID администратора"

# то, чего нет — генерируем
[ -n "${SECRET:-}" ]  || SECRET="$(openssl rand -hex 12)"
[ -n "${DB_PASS:-}" ] || DB_PASS="$(openssl rand -hex 20)"

# ---------- 5. база ----------
echo
info "Настраиваю базу данных…"
mysql -e "CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -e "CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';"
mysql -e "ALTER USER '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';"
mysql -e "GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost'; FLUSH PRIVILEGES;"
grn "база «${DB_NAME}» и пользователь «${DB_USER}» готовы"

# ---------- 6. файлы ----------
info "Копирую файлы в $DIR…"
mkdir -p "$DIR"
cp "$CODE/zbot.php" "$CODE/zapp.php" "$DIR/"

ADMINS_ARR="[$ADMINS_PHP]"
esc() { printf '%s' "${1:-}" | sed "s/\\\\/\\\\\\\\/g; s/'/\\\\'/g"; }

cat > "$DIR/config.php" <<PHPCFG
<?php
/* ZVER TAJ — рабочий конфиг. В git не класть! */
return [
    'bot_token' => '$(esc "$BOT_TOKEN")',
    'admins'    => ${ADMINS_ARR},

    'db_host'   => 'localhost',
    'db_name'   => '$(esc "$DB_NAME")',
    'db_user'   => '$(esc "$DB_USER")',
    'db_pass'   => '$(esc "$DB_PASS")',

    'secret'    => '$(esc "$SECRET")',

    'fz_key'    => '$(esc "${FZ_KEY:-}")',
    'fz_hook'   => '$(esc "${FZ_HOOK:-}")',
    'fz_base'   => 'https://api.fzr.cards/api/v2',

    'gs_key'    => '$(esc "${GS_KEY:-}")',

    'ft_id'     => '$(esc "${FT_ID:-}")',
    'ft_key'    => '$(esc "${FT_KEY:-}")',
    'ft_base'   => 'https://api.flashtopup.com/api/reseller/v2',
    'ft_path'   => '/api/reseller/v2',

    'debug'     => false,
];
PHPCFG

php -l "$DIR/config.php" >/dev/null || die "config.php получился битым"

chown -R www-data:www-data "$DIR"
chmod 755 "$DIR"
chmod 644 "$DIR/zbot.php" "$DIR/zapp.php"
chmod 640 "$DIR/config.php"
grn "файлы на месте, config.php закрыт (640)"

# ---------- 7. nginx ----------
info "Настраиваю nginx…"
cat > /etc/nginx/sites-available/zver <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};
    root ${DIR};
    index zapp.php;

    client_max_body_size 12M;

    location = /config.php            { deny all; return 404; }
    location ~ /\.                    { deny all; return 404; }
    location ~ \.(log|sh|md|sql|zip)\$ { deny all; return 404; }

    location / { try_files \$uri \$uri/ =404; }

    location ~ \.php\$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/run/php/php${PHPV}-fpm.sock;
        fastcgi_send_timeout 1800;
        fastcgi_read_timeout 1800;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/zver /etc/nginx/sites-enabled/zver
rm -f /etc/nginx/sites-enabled/default
nginx -t >/dev/null 2>&1 || { nginx -t; die "Ошибка в конфиге nginx"; }
systemctl reload nginx
grn "nginx настроен"

# ---------- 8. PHP тюнинг ----------
PHPINI="/etc/php/${PHPV}/fpm/php.ini"
if [ -f "$PHPINI" ]; then
    sed -i 's|^;\?opcache.enable=.*|opcache.enable=1|'                           "$PHPINI"
    sed -i 's|^;\?opcache.memory_consumption=.*|opcache.memory_consumption=128|' "$PHPINI"
    # Синхронизация каталога делает по запросу к API на каждый товар:
    # при 300+ товарах это 5–10 минут, стандартных 120 секунд не хватает.
    sed -i 's|^;\?max_execution_time =.*|max_execution_time = 1800|'             "$PHPINI"
    sed -i 's|^;\?ignore_user_abort =.*|ignore_user_abort = On|'                 "$PHPINI"
    sed -i 's|^;\?upload_max_filesize =.*|upload_max_filesize = 12M|'            "$PHPINI"
    sed -i 's|^;\?post_max_size =.*|post_max_size = 12M|'                        "$PHPINI"
fi
systemctl restart "php${PHPV}-fpm"
grn "PHP настроен, OPcache включён"

# ---------- 9. фаервол ----------
if command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then
    ufw allow 80/tcp  >/dev/null 2>&1 || true
    ufw allow 443/tcp >/dev/null 2>&1 || true
    grn "порты 80 и 443 открыты в ufw"
fi

# ---------- 10. проверка DNS ----------
echo
info "Проверяю, что домен смотрит на этот сервер…"
MYIP="$(curl -s --max-time 10 https://api.ipify.org || curl -s --max-time 10 https://ifconfig.me || echo '')"
DNSIP="$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk 'NR==1{print $1}' || echo '')"
echo "  IP сервера: ${MYIP:-неизвестно}"
echo "  Домен ведёт на: ${DNSIP:-не резолвится}"
DNS_OK=0
if [ -n "$MYIP" ] && [ "$MYIP" = "$DNSIP" ]; then
    DNS_OK=1; grn "домен настроен верно"
else
    ylw "  ⚠ Домен пока не указывает на этот сервер — сертификат может не выдаться"
fi

# ---------- 11. SSL ----------
echo
info "Получаю SSL-сертификат Let's Encrypt…"
SSL_OK=0
if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
        --register-unsafely-without-email --redirect >/dev/null 2>&1; then
    SSL_OK=1; grn "HTTPS работает, автопродление включено"
else
    red "  SSL не получен."
    [ "$DNS_OK" -eq 0 ] && red "  Причина скорее всего в DNS — домен не ведёт на $MYIP"
    red "  Когда DNS обновится, выполните: certbot --nginx -d $DOMAIN"
fi
systemctl enable --now certbot.timer >/dev/null 2>&1 || true

# ---------- 12. cron ----------
info "Настраиваю cron…"
CRON_BOT="*/5 * * * * curl -s \"https://${DOMAIN}/zbot.php?cron=1&secret=${SECRET}\" >/dev/null 2>&1"
TMPC="$(mktemp)"
crontab -l 2>/dev/null | grep -v 'zbot.php?cron' | grep -v 'duckdns.org/update' > "$TMPC" || true
echo "$CRON_BOT" >> "$TMPC"
if [ -n "${DUCKDNS_NAME:-}" ] && [ -n "${DUCKDNS_TOKEN:-}" ]; then
    echo "*/5 * * * * curl -s \"https://www.duckdns.org/update?domains=${DUCKDNS_NAME}&token=${DUCKDNS_TOKEN}&ip=\" >/dev/null 2>&1" >> "$TMPC"
fi
crontab "$TMPC"; rm -f "$TMPC"
grn "cron бота${DUCKDNS_NAME:+ и автообновление DuckDNS} каждые 5 минут"

# ---------- 13. инициализация ----------
echo
if [ "$SSL_OK" -eq 1 ]; then
    info "Создаю таблицы и подключаю webhook Telegram…"
    SETUP="$(curl -sS --max-time 90 "https://${DOMAIN}/zbot.php?setup=1&secret=${SECRET}" || echo 'ОШИБКА ЗАПРОСА')"
    echo "$SETUP" | sed 's/<[^>]*>//g' | grep -v '^\s*$' | head -30 | sed 's/^/    /'

    if [ -n "${FZ_KEY:-}" ]; then
        echo
        info "Регистрирую webhook FazerCards…"
        curl -sS --max-time 60 "https://${DOMAIN}/zbot.php?hookset=1&secret=${SECRET}" \
            | sed 's/<[^>]*>//g' | grep -v '^\s*$' | head -12 | sed 's/^/    /' || true
    fi

    echo
    info "Диагностика:"
    curl -sS --max-time 60 "https://${DOMAIN}/zbot.php?diag=1&secret=${SECRET}" \
        | sed 's/<[^>]*>//g' | grep -v '^\s*$' | head -40 | sed 's/^/    /' || true
else
    ylw "Инициализацию пропускаю — нет HTTPS. После получения сертификата откройте:"
    echo "    https://${DOMAIN}/zbot.php?setup=1&secret=${SECRET}"
fi

# ---------- итог ----------
echo
echo -e "\033[1;32m═══════════════════════════════════════════════\033[0m"
echo -e "\033[1;32m  ГОТОВО\033[0m"
echo -e "\033[1;32m═══════════════════════════════════════════════\033[0m"
echo
echo "  Сайт:        https://${DOMAIN}/zapp.php"
echo "  Диагностика: https://${DOMAIN}/zbot.php?diag=1&secret=${SECRET}"
echo "  Папка:       ${DIR}"
echo "  База:        ${DB_NAME} / ${DB_USER}  (пароль внутри config.php)"
echo
ylw "  ОСТАЛОСЬ СДЕЛАТЬ ВРУЧНУЮ (1 минута):"
echo "  @BotFather → /mybots → ваш бот → Bot Settings → Menu Button"
echo "  и вставить ссылку:"
echo "     https://${DOMAIN}/zapp.php"
echo
if [ -n "${FZ_KEY:-}" ]; then
    echo "  Webhook FazerCards подключён автоматически:"
    echo "     https://${DOMAIN}/zbot.php?hook=fz"
    echo "  Проверить: https://${DOMAIN}/zbot.php?hookset=1&secret=${SECRET}"
    echo
fi
[ "$SSL_OK" -eq 0 ] && red "  ⚠ HTTPS не настроен — бот не заработает, пока нет сертификата!"
echo
