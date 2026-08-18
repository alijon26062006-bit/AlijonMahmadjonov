#!/usr/bin/env bash
# Установка Stambul Shop на чистый сервер.
#
#   bash install.sh
#
# Работает и на Debian/Ubuntu (apt), и на RHEL-семействе — AlmaLinux, Rocky,
# CentOS (dnf). Ставит Docker, спрашивает данные Telegram и домен, поднимает
# магазин, настраивает nginx и выпускает сертификат.
#
# Повторный запуск безопасен: уже сделанное пропускается, введённые значения
# предлагаются как есть.
set -euo pipefail

cd "$(dirname "$0")"
ENV_FILE=".env"
GREEN=$'\033[32m'; RED=$'\033[31m'; DIM=$'\033[2m'; OFF=$'\033[0m'

say()  { echo "${GREEN}▸${OFF} $*"; }
warn() { echo "${RED}!${OFF} $*"; }
die()  { warn "$*"; exit 1; }

[ "$(id -u)" = "0" ] || die "Запустите от root: bash install.sh"

# ─────────────────────── Какой это дистрибутив ───────────────────────

if command -v apt-get >/dev/null; then
    FAMILY=debian
    PKG_INSTALL() { DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$@" >/dev/null; }
    PKG_REFRESH() { DEBIAN_FRONTEND=noninteractive apt-get update -qq; }
    NGINX_CONF_DIR=/etc/nginx/sites-enabled
elif command -v dnf >/dev/null || command -v yum >/dev/null; then
    FAMILY=rhel
    DNF=$(command -v dnf || command -v yum)
    PKG_INSTALL() { "$DNF" install -y -q "$@" >/dev/null; }
    PKG_REFRESH() { :; }
    # у RHEL нет sites-available: nginx сам подключает /etc/nginx/conf.d/*.conf
    NGINX_CONF_DIR=/etc/nginx/conf.d
else
    die "Не понял, какой это дистрибутив: нет ни apt-get, ни dnf"
fi
say "Система: $FAMILY"

# ─────────────────────────── Пакеты ───────────────────────────

say "Проверяю системные пакеты"
NEED=()
command -v curl >/dev/null    || NEED+=(curl)
command -v openssl >/dev/null || NEED+=(openssl)
command -v dig >/dev/null     || NEED+=("$([ "$FAMILY" = debian ] && echo dnsutils || echo bind-utils)")
command -v ss >/dev/null      || NEED+=("$([ "$FAMILY" = debian ] && echo iproute2 || echo iproute)")
if [ ${#NEED[@]} -gt 0 ]; then
    PKG_REFRESH
    PKG_INSTALL "${NEED[@]}" ca-certificates
fi

if ! command -v docker >/dev/null; then
    say "Ставлю Docker (пара минут). Вывод показываю: молчаливый выход отсюда"
    say "выглядит как «скрипт просто закончился», и причину потом не найти."
    curl -fsSL https://get.docker.com -o /tmp/get-docker.sh \
        || die "Не скачался установщик Docker. Проверьте сеть: curl -I https://get.docker.com"
    sh /tmp/get-docker.sh || warn "Установщик завершился с ошибкой — пробую через пакеты"

    if ! command -v docker >/dev/null && [ "$FAMILY" = rhel ]; then
        say "Ставлю Docker из репозитория Docker CE"
        PKG_INSTALL dnf-plugins-core || true
        "$DNF" config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo 2>/dev/null \
            || "$DNF" config-manager addrepo --from-repofile=https://download.docker.com/linux/centos/docker-ce.repo 2>/dev/null \
            || true
        PKG_INSTALL docker-ce docker-ce-cli containerd.io docker-compose-plugin || true
    fi
    command -v docker >/dev/null \
        || die "Docker поставить не удалось. Покажите вывод выше — разберёмся."
fi

systemctl enable docker >/dev/null 2>&1 || true
systemctl is-active docker >/dev/null 2>&1 || systemctl start docker \
    || die "Docker установлен, но не запускается: systemctl status docker"

if ! docker compose version >/dev/null 2>&1; then
    say "Доставляю плагин docker compose"
    PKG_INSTALL docker-compose-plugin || true
fi
docker compose version >/dev/null 2>&1 || die "Нет «docker compose». Поставьте плагин вручную."

# Сборка витрины требует памяти. На машине с 1 ГБ npm падает без объяснений —
# добавляем файл подкачки заранее, это дешевле, чем потом искать причину.
RAM_MB=$(free -m 2>/dev/null | awk '/^Mem:/{print $2}' || echo 2048)
SWAP_MB=$(free -m 2>/dev/null | awk '/^Swap:/{print $2}' || echo 0)
if [ "${RAM_MB:-2048}" -lt 1800 ] && [ "${SWAP_MB:-0}" -lt 512 ] && [ ! -f /swapfile ]; then
    say "Мало памяти (${RAM_MB} МБ) — добавляю файл подкачки на 2 ГБ"
    fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
    chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# ─────────────────────────── Настройки ───────────────────────────

[ -f "$ENV_FILE" ] || cp .env.example "$ENV_FILE"

get() { grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2- || true; }
set_env() {
    local key="$1" value="$2"
    if grep -qE "^$key=" "$ENV_FILE"; then
        value="${value//|/\\|}"
        sed -i "s|^$key=.*|$key=$value|" "$ENV_FILE"
    else
        echo "$key=$value" >> "$ENV_FILE"
    fi
}
ask() {                       # ask ПЕРЕМЕННАЯ "Вопрос" [обязательно]
    local key="$1" prompt="$2" required="${3:-}" current answer
    current="$(get "$key")"
    while true; do
        if [ -n "$current" ]; then
            read -rp "$prompt [${DIM}$current${OFF}]: " answer
            answer="${answer:-$current}"
        else
            read -rp "$prompt: " answer
        fi
        [ -z "$answer" ] && [ -n "$required" ] && { warn "Без этого не обойтись"; continue; }
        set_env "$key" "$answer"
        echo "$answer"
        return
    done
}

rand_hex() { openssl rand -hex "$1" 2>/dev/null || head -c "$1" /dev/urandom | od -An -tx1 | tr -d ' \n'; }

echo
say "Настройка магазина. В квадратных скобках — текущее значение, Enter оставит его."
echo

BOT_TOKEN="$(ask BOT_TOKEN 'Токен бота от @BotFather' yes)"
[[ "$BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]] || die "Токен выглядит неправильно: должен быть вида 123456:AA..."

BOT_USERNAME="$(ask BOT_USERNAME 'Имя бота без @' yes)"
BOT_USERNAME="${BOT_USERNAME#@}"
set_env BOT_USERNAME "$BOT_USERNAME"

ADMIN_IDS="$(ask ADMIN_IDS 'Ваш Telegram-id (узнать: @userinfobot)' yes)"
[[ "$ADMIN_IDS" =~ ^[0-9,[:space:]]+$ ]] || die "Тут нужны только цифры (можно несколько через запятую)"

STORAGE_CHAT_ID="$(ask STORAGE_CHAT_ID 'ID приватной группы для фото товаров (0 — настрою позже)')"
[[ "${STORAGE_CHAT_ID:-0}" =~ ^-?[0-9]+$ ]] || die "ID группы — это число, часто со знаком минус"
[ "${STORAGE_CHAT_ID:-0}" = "0" ] && warn "Без группы-хранилища фотографии товаров загружать не получится"

DOMAIN="$(ask DOMAIN 'Домен магазина, например shop.example.com' yes)"
DOMAIN="${DOMAIN#http://}"; DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN%%/*}"
[[ "$DOMAIN" =~ ^[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?\.[a-zA-Z]{2,}$ ]] \
    || die "«$DOMAIN» не похоже на домен"
set_env DOMAIN "$DOMAIN"
set_env SITE_URL "https://$DOMAIN"
set_env CORS_ORIGINS "https://$DOMAIN"
set_env API_PUBLIC_URL ""

echo
say "Оплата. Можно пропустить и заполнить позже в .env"
ask KASPI_PHONE 'Номер Kaspi для переводов' >/dev/null
ask KASPI_NAME  'Имя получателя, как в переводе' >/dev/null
ask PICKUP_ADDRESS 'Адрес самовывоза (пусто — самовывоза нет)' >/dev/null

[ -n "$(get JWT_SECRET)" ] || set_env JWT_SECRET "$(rand_hex 32)"
case "$(get POSTGRES_PASSWORD)" in
    ""|"поменяйте-пароль") set_env POSTGRES_PASSWORD "$(rand_hex 16)" ;;
esac

free_port() {
    local start="$1" p
    for p in $(seq "$start" $((start + 60))); do
        ss -ltn 2>/dev/null | grep -q ":$p " || { echo "$p"; return; }
    done
    echo "$start"
}
[ -n "$(get API_PORT)" ]     || set_env API_PORT "$(free_port 8010)"
[ -n "$(get WEB_PORT)" ] || set_env WEB_PORT "$(free_port 8100)"
API_PORT="$(get API_PORT)"; WEB_PORT="$(get WEB_PORT)"

# ─────────────────────────── Проверка домена ───────────────────────────

echo
say "Проверяю, что домен ведёт сюда"
SERVER_IP="$(curl -s --max-time 10 ifconfig.me || true)"
DOMAIN_IP="$(dig +short "$DOMAIN" A | tail -1 || true)"
SKIP_TLS=0
if [ -z "$DOMAIN_IP" ]; then
    warn "Домен $DOMAIN пока не резолвится — сертификат отложим"
    SKIP_TLS=1
elif [ -n "$SERVER_IP" ] && [ "$SERVER_IP" != "$DOMAIN_IP" ]; then
    warn "Домен $DOMAIN указывает на $DOMAIN_IP, а сервер — $SERVER_IP."
    warn "Сертификат не выпустится, пока A-запись не будет указывать сюда."
    read -rp "Продолжить без HTTPS и выпустить сертификат позже? [y/N]: " go
    [[ "${go,,}" == y* ]] || die "Поправьте A-запись домена и запустите снова"
    SKIP_TLS=1
else
    say "Домен указывает на этот сервер ($SERVER_IP)"
fi

# ─────────────────────────── Запуск ───────────────────────────

echo
say "Собираю и запускаю магазин (первый раз это несколько минут)"
docker compose run --rm migrate
docker compose up -d --build

say "Жду, пока поднимется API"
for _ in $(seq 1 40); do
    curl -sf "http://127.0.0.1:$API_PORT/health" >/dev/null && break
    sleep 2
done
curl -sf "http://127.0.0.1:$API_PORT/health" >/dev/null \
    || die "API не отвечает. Посмотрите: docker compose logs --tail=40 api"
say "API отвечает"

# ─────────────────────────── nginx ───────────────────────────

command -v nginx >/dev/null || { say "Ставлю nginx"; PKG_INSTALL nginx; }

cat > "$NGINX_CONF_DIR/stambul-shop.conf" <<NGINX
server {
    listen 80;
    server_name $DOMAIN;
    client_max_body_size 12m;

    location / {
        proxy_pass http://127.0.0.1:$WEB_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }
}
NGINX

if [ "$FAMILY" = debian ]; then
    rm -f /etc/nginx/sites-enabled/default
else
    # у RHEL в nginx.conf лежит свой server на 80 — он перехватит запросы
    if grep -q "server_name  _;" /etc/nginx/nginx.conf 2>/dev/null; then
        sed -i 's|^\( *\)server_name  _;|\1server_name  _;\n\1return 444;|' \
            /etc/nginx/nginx.conf 2>/dev/null || true
    fi
fi

# SELinux запрещает nginx ходить по сети — из-за этого 502 на пустом месте
if command -v getenforce >/dev/null && [ "$(getenforce)" != "Disabled" ]; then
    say "Разрешаю nginx подключаться к контейнерам (SELinux)"
    setsebool -P httpd_can_network_connect 1 2>/dev/null || true
fi

nginx -t >/dev/null 2>&1 || { nginx -t; die "nginx не принял настройки"; }
systemctl enable nginx >/dev/null 2>&1 || true
systemctl reload nginx 2>/dev/null || systemctl restart nginx
say "nginx настроен на $DOMAIN"

# Порты наружу
if command -v firewall-cmd >/dev/null && systemctl is-active firewalld >/dev/null 2>&1; then
    say "Открываю порты 80 и 443 в firewalld"
    firewall-cmd --permanent --add-service=http >/dev/null 2>&1 || true
    firewall-cmd --permanent --add-service=https >/dev/null 2>&1 || true
    firewall-cmd --reload >/dev/null 2>&1 || true
elif command -v ufw >/dev/null && ufw status 2>/dev/null | grep -q "Status: active"; then
    say "Открываю порты 80 и 443 в ufw"
    ufw allow 80/tcp >/dev/null 2>&1 || true
    ufw allow 443/tcp >/dev/null 2>&1 || true
fi

# ─────────────────────────── HTTPS ───────────────────────────

if [ "$SKIP_TLS" = "0" ]; then
    if ! command -v certbot >/dev/null; then
        say "Ставлю certbot"
        if [ "$FAMILY" = debian ]; then
            PKG_INSTALL certbot python3-certbot-nginx
        else
            PKG_INSTALL epel-release || true
            PKG_INSTALL certbot python3-certbot-nginx || true
        fi
    fi
    if command -v certbot >/dev/null; then
        say "Выпускаю сертификат"
        if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
                   --register-unsafely-without-email --redirect >/dev/null 2>&1; then
            say "HTTPS работает"
        else
            warn "Сертификат не выпустился. Повторить вручную: certbot --nginx -d $DOMAIN"
        fi
    else
        warn "Не удалось поставить certbot. Магазин работает по http://$DOMAIN"
        warn "Без HTTPS браузеры ругаются на сайт — сертификат нужен."
    fi
fi

# ─────────────────────────── Итог ───────────────────────────

echo
say "Готово. Магазин: https://$DOMAIN"
echo
echo "Магазин — обычный сайт: открывается по ссылке, ничего ставить не нужно."
echo "Бот при нём служебный: присылает коды входа и сообщения о заказах."
echo
echo "Напишите боту /start, затем /id — должно быть «владелец магазина»."
echo "Товары добавляются на сайте: профиль → Управление."
echo
echo "Что стоит дозаполнить в .env:"
echo "  STORAGE_CHAT_ID   приватная группа для фотографий товаров"
echo "  KASPI_PHONE       реквизиты, которые увидит покупатель"
echo "  SMTP_HOST и т.д.  письма о заказах"
echo "  GOOGLE_CLIENT_ID  вход через Google"
echo "После правки: docker compose up -d --force-recreate api bot worker"
echo
echo "Полезное:"
echo "  docker compose ps                 состояние"
echo "  docker compose logs --tail=40 bot логи бота"
echo "  docker compose up -d --build      обновиться после git pull"
