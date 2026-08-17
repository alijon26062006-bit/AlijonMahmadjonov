#!/usr/bin/env bash
# Установка Stambul Shop на чистый сервер (Ubuntu/Debian).
#
#   bash install.sh
#
# Скрипт ставит Docker, спрашивает данные Telegram и домен, поднимает магазин
# и выпускает сертификат. Повторный запуск безопасен: уже сделанное
# пропускается, введённые значения предлагаются как есть.
set -euo pipefail

cd "$(dirname "$0")"
ENV_FILE=".env"
GREEN=$'\033[32m'; RED=$'\033[31m'; DIM=$'\033[2m'; OFF=$'\033[0m'

say()  { echo "${GREEN}▸${OFF} $*"; }
warn() { echo "${RED}!${OFF} $*"; }
die()  { warn "$*"; exit 1; }

[ "$(id -u)" = "0" ] || die "Запустите от root: bash install.sh"

# ─────────────────────────── Системные пакеты ───────────────────────────

say "Проверяю системные пакеты"
export DEBIAN_FRONTEND=noninteractive
MISSING=()
for cmd in curl openssl dig; do command -v "$cmd" >/dev/null || MISSING+=("$cmd"); done
if [ ${#MISSING[@]} -gt 0 ]; then
    apt-get update -qq
    apt-get install -y -qq curl openssl dnsutils ca-certificates >/dev/null
fi

if ! command -v docker >/dev/null; then
    say "Ставлю Docker (пара минут)"
    curl -fsSL https://get.docker.com | sh >/dev/null
fi
docker compose version >/dev/null 2>&1 || die "Не нашёл «docker compose». Обновите Docker."

# ─────────────────────────── Настройки ───────────────────────────

[ -f "$ENV_FILE" ] || cp .env.example "$ENV_FILE"

get() { grep -E "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2- || true; }
set_env() {
    local key="$1" value="$2"
    if grep -qE "^$key=" "$ENV_FILE"; then
        # значение может содержать / и & — разделитель |, экранируем его
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
set_env WEBAPP_URL "https://$DOMAIN"
set_env CORS_ORIGINS "https://$DOMAIN"
set_env API_PUBLIC_URL ""

echo
say "Оплата. Можно пропустить и заполнить позже в .env"
ask KASPI_PHONE 'Номер Kaspi для переводов' >/dev/null
ask KASPI_NAME  'Имя получателя, как в переводе' >/dev/null
ask PICKUP_ADDRESS 'Адрес самовывоза (пусто — самовывоза нет)' >/dev/null

# Секреты — только если их ещё нет
[ -n "$(get JWT_SECRET)" ] || set_env JWT_SECRET "$(rand_hex 32)"
case "$(get POSTGRES_PASSWORD)" in
    ""|"поменяйте-пароль") set_env POSTGRES_PASSWORD "$(rand_hex 16)" ;;
esac

# Свободные порты: на сервере может стоять что-то ещё
free_port() {
    local start="$1" p
    for p in $(seq "$start" $((start + 60))); do
        ss -ltn 2>/dev/null | grep -q ":$p " || { echo "$p"; return; }
    done
    echo "$start"
}
[ -n "$(get API_PORT)" ]     || set_env API_PORT "$(free_port 8010)"
[ -n "$(get MINIAPP_PORT)" ] || set_env MINIAPP_PORT "$(free_port 8100)"
API_PORT="$(get API_PORT)"; MINIAPP_PORT="$(get MINIAPP_PORT)"

# ─────────────────────────── Проверка домена ───────────────────────────

echo
say "Проверяю, что домен ведёт сюда"
SERVER_IP="$(curl -s --max-time 10 ifconfig.me || true)"
DOMAIN_IP="$(dig +short "$DOMAIN" A | tail -1 || true)"
if [ -n "$SERVER_IP" ] && [ -n "$DOMAIN_IP" ] && [ "$SERVER_IP" != "$DOMAIN_IP" ]; then
    warn "Домен $DOMAIN сейчас указывает на $DOMAIN_IP, а сервер — $SERVER_IP."
    warn "Сертификат не выпустится, пока A-запись не будет указывать сюда."
    read -rp "Продолжить без HTTPS и выпустить сертификат позже? [y/N]: " go
    [[ "${go,,}" == y* ]] || die "Поправьте A-запись домена и запустите снова"
    SKIP_TLS=1
elif [ -z "$DOMAIN_IP" ]; then
    warn "Домен $DOMAIN пока не резолвится — сертификат отложим"
    SKIP_TLS=1
else
    say "Домен указывает на этот сервер ($SERVER_IP)"
    SKIP_TLS=0
fi

# ─────────────────────────── Запуск ───────────────────────────

echo
say "Собираю и запускаю магазин (первый раз это несколько минут)"
docker compose run --rm migrate
docker compose up -d --build

say "Жду, пока поднимется API"
for _ in $(seq 1 30); do
    curl -sf "http://127.0.0.1:$API_PORT/health" >/dev/null && break
    sleep 2
done
curl -sf "http://127.0.0.1:$API_PORT/health" >/dev/null \
    || die "API не отвечает. Посмотрите: docker compose logs --tail=40 api"
say "API отвечает"

# ─────────────────────────── nginx и HTTPS ───────────────────────────

command -v nginx >/dev/null || { say "Ставлю nginx"; apt-get install -y -qq nginx >/dev/null; }

SITE="/etc/nginx/sites-available/stambul-shop"
cat > "$SITE" <<NGINX
server {
    listen 80;
    server_name $DOMAIN;
    client_max_body_size 12m;

    location / {
        proxy_pass http://127.0.0.1:$MINIAPP_PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
    }
}
NGINX
ln -sfn "$SITE" /etc/nginx/sites-enabled/stambul-shop
rm -f /etc/nginx/sites-enabled/default
nginx -t >/dev/null 2>&1 || die "nginx не принял настройки: nginx -t"
systemctl reload nginx 2>/dev/null || systemctl start nginx
say "nginx настроен на $DOMAIN"

if [ "${SKIP_TLS:-0}" = "0" ]; then
    command -v certbot >/dev/null || { say "Ставлю certbot"; apt-get install -y -qq certbot python3-certbot-nginx >/dev/null; }
    say "Выпускаю сертификат"
    if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
               --register-unsafely-without-email --redirect >/dev/null 2>&1; then
        say "HTTPS работает"
    else
        warn "Сертификат не выпустился. Повторить вручную: certbot --nginx -d $DOMAIN"
    fi
fi

# ─────────────────────────── Итог ───────────────────────────

echo
say "Готово. Магазин: https://$DOMAIN"
echo
echo "Осталось два шага в Telegram:"
echo "  1. @BotFather → /newapp → выбрать @$BOT_USERNAME"
echo "     URL: https://$DOMAIN"
echo "     short name: $(get MINIAPP_SHORT_NAME)"
echo "  2. @BotFather → /setmenubutton → тот же адрес"
echo
echo "Потом напишите боту /start, затем /id — должно быть «владелец магазина»."
echo "Товары добавляются в панели: нижняя навигация → Товары."
echo
echo "Полезное:"
echo "  docker compose ps                 состояние"
echo "  docker compose logs --tail=40 bot логи бота"
echo "  docker compose up -d --build      обновиться после git pull"
