#!/usr/bin/env bash
# Установка «Бозор» на чистый VPS (Ubuntu/Debian).
# Запуск из папки проекта:  sudo bash install.sh
set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✓${NC} $*"; }
warn() { echo -e "${YELLOW}!${NC} $*"; }
err()  { echo -e "${RED}✗${NC} $*" >&2; }

[ "$(id -u)" -eq 0 ] || { err "Нужны права root. Запустите: sudo bash install.sh (или войдите как root)"; exit 1; }
[ -f docker-compose.yml ] || { err "Запускайте из папки проекта (где docker-compose.yml)"; exit 1; }

# ─────────────── 0. Базовые утилиты ───────────────
# На минимальном Debian может не быть curl и openssl
MISSING=""
for tool in curl openssl ca-certificates; do
  case "$tool" in
    ca-certificates) [ -d /etc/ssl/certs ] || MISSING="$MISSING $tool" ;;
    *) command -v "$tool" >/dev/null 2>&1 || MISSING="$MISSING $tool" ;;
  esac
done
if [ -n "$MISSING" ]; then
  echo "Доустанавливаю:$MISSING"
  apt-get update -qq && apt-get install -y -qq $MISSING >/dev/null
  ok "Утилиты установлены"
fi

# Генератор секретов: openssl, а если его нет — /dev/urandom
rand_hex() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$1"
  else
    head -c "$1" /dev/urandom | od -An -tx1 | tr -d ' \n'
  fi
}

echo
echo "══════════════════════════════════════════════"
echo "   Бозор — установка на сервер"
echo "══════════════════════════════════════════════"
echo

# ─────────────── 1. Docker ───────────────
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  ok "Docker уже установлен"
else
  echo "Устанавливаю Docker…"
  curl -fsSL https://get.docker.com | sh >/dev/null 2>&1
  ok "Docker установлен"
fi

# ─────────────── 2. Настройки ───────────────
if [ -f .env ]; then
  warn ".env уже существует — оставляю как есть."
  warn "Чтобы задать заново: rm .env && sudo bash install.sh"
else
  echo
  echo "── Данные из Telegram ────────────────────────"
  echo "Если чего-то нет — см. раздел «Настройка Telegram» в README."
  echo

  read -rp "Токен бота (от @BotFather): " BOT_TOKEN
  [[ "$BOT_TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]+$ ]] || { err "Токен выглядит неверно"; exit 1; }

  read -rp "Имя бота без @ (например bozor_bot): " BOT_USERNAME
  BOT_USERNAME="${BOT_USERNAME#@}"

  # Числовой ID: только цифры, возможен минус. Имя канала здесь не подойдёт.
  ask_id() {
    local prompt="$1" allow_empty="$2" value
    while true; do
      read -rp "$prompt" value
      value="${value// /}"
      if [ -z "$value" ] && [ "$allow_empty" = "yes" ]; then echo ""; return; fi
      if [[ "$value" =~ ^-?[0-9]+$ ]]; then echo "$value"; return; fi
      err "Нужен числовой ID (например -1001234567890), а не имя."
      err "Перешлите сообщение оттуда боту @userinfobot — он покажет ID."
    done
  }

  CHANNEL_ID=$(ask_id "ID канала публикаций (-100…): " no)
  read -rp "Имя канала без @ (для ссылок, можно пусто): " CHANNEL_USERNAME
  CHANNEL_USERNAME="${CHANNEL_USERNAME#@}"
  ADMIN_CHAT_ID=$(ask_id "ID группы модерации (-100…): " no)
  STORAGE_CHAT_ID=$(ask_id "ID группы-хранилища фото (-100…, можно пусто): " yes)
  ADMIN_IDS=$(ask_id "Ваш Telegram ID (админ): " no)

  echo
  echo "── Адрес сайта ───────────────────────────────"
  echo "Нужен полный домен с точкой, например bozor.duckdns.org"
  echo "(бесплатный поддомен — на duckdns.org, укажите там IP этого сервера)."
  echo "Оставьте пустым, если пока запускаете только бота."
  while true; do
    read -rp "Домен для Mini App: " DOMAIN
    DOMAIN="${DOMAIN// /}"
    DOMAIN="${DOMAIN#http://}"; DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN%%/*}"
    [ -z "$DOMAIN" ] && break
    if [[ "$DOMAIN" =~ ^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then break; fi
    err "Это не похоже на домен. Нужен вид bozor.duckdns.org — или оставьте пустым."
  done

  # Свободный порт для локальной публикации miniapp
  MINIAPP_PORT=8080
  while ss -ltn 2>/dev/null | grep -q ":$MINIAPP_PORT " || \
        netstat -ltn 2>/dev/null | grep -q ":$MINIAPP_PORT "; do
    MINIAPP_PORT=$((MINIAPP_PORT + 1))
  done
  [ "$MINIAPP_PORT" != "8080" ] && warn "Порт 8080 занят — использую $MINIAPP_PORT"

  API_PORT=8000
  while ss -ltn 2>/dev/null | grep -q ":$API_PORT " || \
        netstat -ltn 2>/dev/null | grep -q ":$API_PORT "; do
    API_PORT=$((API_PORT + 1))
  done
  [ "$API_PORT" != "8000" ] && warn "Порт 8000 занят — использую $API_PORT"

  if [ -n "$DOMAIN" ]; then
    WEBAPP_URL="https://$DOMAIN"
    CORS_ORIGINS="https://$DOMAIN"
  else
    WEBAPP_URL="http://localhost:8080"
    CORS_ORIGINS="http://localhost:8080"
  fi

  # Секреты генерируются сами — руками их придумывать не нужно
  JWT_SECRET=$(rand_hex 32)
  POSTGRES_PASSWORD=$(rand_hex 16)

  cat > .env <<EOF
ENV=prod

BOT_TOKEN=$BOT_TOKEN
BOT_USERNAME=$BOT_USERNAME
MINIAPP_SHORT_NAME=app

CHANNEL_ID=$CHANNEL_ID
CHANNEL_USERNAME=$CHANNEL_USERNAME
ADMIN_CHAT_ID=$ADMIN_CHAT_ID
STORAGE_CHAT_ID=${STORAGE_CHAT_ID:-0}
ADMIN_IDS=$ADMIN_IDS

DOMAIN=$DOMAIN
WEBAPP_URL=$WEBAPP_URL
API_PUBLIC_URL=
CORS_ORIGINS=$CORS_ORIGINS

JWT_SECRET=$JWT_SECRET

POSTGRES_USER=bozor
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_DB=bozor

API_PORT=$API_PORT
MINIAPP_PORT=$MINIAPP_PORT

TJS_PER_USD=10.9
DAILY_LISTING_LIMIT=3
ACTIVE_LISTING_LIMIT=10
LISTING_TTL_DAYS=30
EOF
  chmod 600 .env
  ok ".env создан (пароли сгенерированы автоматически)"
fi

DOMAIN=$(grep -E '^DOMAIN=' .env | cut -d= -f2- || true)

# ─────────────── 3. Запуск ───────────────
echo
echo "── Сборка и запуск ───────────────────────────"
if [ -n "$DOMAIN" ]; then
  echo "Режим: бот + сайт на https://$DOMAIN"
  echo "Убедитесь, что A-запись домена указывает на этот сервер,"
  echo "а порты 80 и 443 открыты — иначе сертификат не выпустится."
  docker compose -f docker-compose.yml -f docker-compose.https.yml up -d --build
else
  echo "Режим: только бот (домен не задан)"
  docker compose up -d --build db redis migrate bot worker
fi

# ─────────────── 4. Проверка ───────────────
echo
echo "── Проверка ──────────────────────────────────"
sleep 12
docker compose ps --format 'table {{.Service}}\t{{.Status}}' 2>/dev/null || docker compose ps

echo
if docker compose logs bot 2>/dev/null | grep -q "Бот запущен"; then
  ok "Бот запущен и слушает Telegram"
else
  warn "Бот ещё стартует. Логи:  docker compose logs -f bot"
fi

if [ -n "$DOMAIN" ]; then
  echo
  echo "Сертификат выпускается 10–60 секунд. Затем проверьте:"
  echo "  curl -I https://$DOMAIN"
  echo
  echo "И укажите в @BotFather:"
  echo "  /newapp        → URL: https://$DOMAIN  → short name: app"
  echo "  /setmenubutton → URL: https://$DOMAIN"
fi

echo
ok "Готово. Напишите боту /start в Telegram."
echo
echo "Полезное:"
echo "  docker compose logs -f bot     — логи бота"
echo "  docker compose ps              — состояние"
echo "  docker compose restart bot     — перезапуск"
echo "  docker compose down            — остановить всё"
echo
