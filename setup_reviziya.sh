#!/usr/bin/env bash
# Установка ревизии на свой сервер одной командой:
#
#   bash setup_reviziya.sh
#
# Ставит всё нужное, спрашивает токен бота и ключ Anthropic, подбирает бесплатный
# адрес с HTTPS и запускает сервис. Повторный запуск безопасен: ключи спросит заново,
# только если их нет или они не подошли.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

ROOT="$PWD"
ENV_FILE="$ROOT/.env.reviziya"
VENV="$ROOT/.venv-reviziya"
PORT=8787
SITE_FILE=/etc/caddy/reviziya.caddy

BOLD=$'\033[1m'; DIM=$'\033[90m'; GREEN=$'\033[32m'; RED=$'\033[31m'; OFF=$'\033[0m'
say()  { printf '%s\n' "$*"; }
ok()   { printf '  %s✓%s %s\n' "$GREEN" "$OFF" "$*"; }
bad()  { printf '  %s✗%s %s\n' "$RED" "$OFF" "$*" >&2; }
hint() { printf '  %s%s%s\n' "$DIM" "$*" "$OFF"; }
step() { printf '\n%s[%s/5] %s%s\n' "$BOLD" "$1" "$2" "$OFF"; }
die()  { bad "$*"; exit 1; }

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null 2>&1 || die "Нужны права root. Запусти от root или поставь sudo."
  SUDO="sudo"
fi
[ -t 0 ] || die "Запусти в обычном терминале: скрипт спрашивает ключи."
command -v systemctl >/dev/null 2>&1 || die "На сервере нет systemd. Напиши мне, какая у тебя система."

env_get() { [ -f "$ENV_FILE" ] && grep -E "^$1=" "$ENV_FILE" | tail -1 | cut -d= -f2- || true; }
env_set() {  # ключ значение
  touch "$ENV_FILE"; chmod 600 "$ENV_FILE"
  grep -vE "^$1=" "$ENV_FILE" > "$ENV_FILE.tmp" || true
  printf '%s=%s\n' "$1" "$2" >> "$ENV_FILE.tmp"
  mv "$ENV_FILE.tmp" "$ENV_FILE"; chmod 600 "$ENV_FILE"
}
ask_secret() {  # ключ вопрос
  local value=""
  while [ -z "$value" ]; do
    read -r -s -p "  $2: " value; printf '\n'
    value="$(printf '%s' "$value" | tr -d '[:space:]')"
  done
  env_set "$1" "$value"
}

say ""
say "${BOLD}Установка ревизии${OFF}"
hint "Сканер ценников в Telegram. Это займёт несколько минут."

# ── 1. Python и библиотеки ─────────────────────────────────────────────────
step 1 "Python и библиотеки"
command -v python3 >/dev/null 2>&1 || die "Не найден python3. Установи: apt install python3"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || die "Нужен Python 3.10 или новее."
if ! python3 -c 'import venv, ensurepip' >/dev/null 2>&1; then
  command -v apt-get >/dev/null 2>&1 || die "Поставь пакет python3-venv и запусти ещё раз."
  hint "Доставляю python3-venv"
  $SUDO apt-get update -qq && $SUDO apt-get install -y -qq python3-venv >/dev/null
fi
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV" || die "Не удалось создать $VENV"
"$VENV/bin/python" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
"$VENV/bin/python" -m pip install --quiet -r reviziya_server/requirements.txt \
  || die "Не удалось поставить библиотеки. Проверь интернет и запусти ещё раз."
"$VENV/bin/python" -c 'import reviziya_server.app, reviziya_server.bot' \
  || die "Код не запускается. Пришли мне эту ошибку."
ok "Готово"

# ── 2. Ключи ───────────────────────────────────────────────────────────────
step 2 "Ключи"
hint "Токен бота: в Telegram открой @BotFather, отправь /newbot и скопируй токен."
hint "Ключ Anthropic: console.anthropic.com → API keys. При вводе символы не видны, это нормально."
[ -n "$(env_get REVIZIYA_URL)" ] || env_set REVIZIYA_URL "https://example.invalid"   # настоящий адрес выберем на шаге 3
[ -n "$(env_get REVIZIYA_PORT)" ] || env_set REVIZIYA_PORT "$PORT"
[ -n "$(env_get REVIZIYA_BOT_TOKEN)" ] || ask_secret REVIZIYA_BOT_TOKEN "Токен бота"
[ -n "$(env_get ANTHROPIC_API_KEY)" ] || ask_secret ANTHROPIC_API_KEY "Ключ Anthropic"

BOT_NAME=""
while true; do
  set +e; CHECK="$("$VENV/bin/python" -m reviziya_server.check 2>&1)"; CODE=$?; set -e
  BOT_NAME="$(printf '%s\n' "$CHECK" | awk '$1=="BOT" && $2=="ok" {print $3}')"
  case "$CODE" in
    0) ok "Бот @$BOT_NAME и ключ Anthropic работают"; break ;;
    1) bad "Токен бота не подошёл."; ask_secret REVIZIYA_BOT_TOKEN "Токен бота" ;;
    2) bad "Ключ Anthropic не подошёл."; ask_secret ANTHROPIC_API_KEY "Ключ Anthropic" ;;
    3) bad "Не подошли оба ключа."
       ask_secret REVIZIYA_BOT_TOKEN "Токен бота"; ask_secret ANTHROPIC_API_KEY "Ключ Anthropic" ;;
    *) bad "Не удалось проверить ключи: нет связи с Telegram или Anthropic."
       printf '%s\n' "$CHECK" | sed 's/^/    /'
       hint "Ключи сохранены. Продолжаю, но если сканер не заработает, причина здесь."
       break ;;
  esac
done

# ── 3. Адрес ───────────────────────────────────────────────────────────────
step 3 "Адрес"
CURRENT="$(env_get REVIZIYA_URL | sed 's#^https://##')"
[ "$CURRENT" = "example.invalid" ] && CURRENT=""
IP="$(curl -4 -fsS --max-time 8 https://api.ipify.org 2>/dev/null || curl -4 -fsS --max-time 8 https://ifconfig.me 2>/dev/null || true)"
DEFAULT="$CURRENT"
if [ -z "$DEFAULT" ]; then
  [[ "$IP" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "Не смог узнать внешний IP сервера. Напиши мне его, я подскажу адрес."
  DEFAULT="reviziya.${IP//./-}.sslip.io"
fi
hint "Бесплатный адрес sslip.io сам указывает на этот сервер, регистрировать ничего не надо."
read -r -p "  Адрес [Enter = $DEFAULT]: " DOMAIN
DOMAIN="$(printf '%s' "${DOMAIN:-$DEFAULT}" | sed -E 's#^https?://##; s#/.*$##' | tr -d '[:space:]')"
[[ "$DOMAIN" =~ ^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]] || die "Адрес «$DOMAIN» не похож на домен."
env_set REVIZIYA_URL "https://$DOMAIN"
ok "https://$DOMAIN"

# ── 4. HTTPS ───────────────────────────────────────────────────────────────
step 4 "HTTPS (Caddy сам получает сертификат)"
if ! command -v caddy >/dev/null 2>&1; then
  BUSY="$($SUDO ss -ltnpH '( sport = :80 or sport = :443 )' 2>/dev/null || true)"
  if [ -n "$BUSY" ]; then
    bad "Порты 80 или 443 уже заняты другой программой:"
    printf '%s\n' "$BUSY" | sed 's/^/    /'
    die "Пришли мне эти строки, я подстрою установку под твой сервер."
  fi
  command -v apt-get >/dev/null 2>&1 || die "Поставь Caddy вручную (caddyserver.com/docs/install) и запусти ещё раз."
  hint "Ставлю Caddy"
  $SUDO apt-get update -qq
  $SUDO apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https curl gnupg >/dev/null
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | $SUDO gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    | $SUDO tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  $SUDO apt-get update -qq
  $SUDO apt-get install -y -qq caddy >/dev/null || die "Caddy не поставился. Пришли мне эту ошибку."
fi
$SUDO mkdir -p /etc/caddy
printf '%s {\n\tencode gzip\n\treverse_proxy 127.0.0.1:%s\n}\n' "$DOMAIN" "$PORT" | $SUDO tee "$SITE_FILE" >/dev/null
$SUDO touch /etc/caddy/Caddyfile
grep -qF "import $SITE_FILE" /etc/caddy/Caddyfile \
  || printf '\nimport %s\n' "$SITE_FILE" | $SUDO tee -a /etc/caddy/Caddyfile >/dev/null
$SUDO caddy validate --config /etc/caddy/Caddyfile >/dev/null 2>&1 \
  || die "Caddy не принял настройки. Пришли мне вывод: caddy validate --config /etc/caddy/Caddyfile"
$SUDO systemctl enable --now caddy >/dev/null 2>&1 || true
$SUDO systemctl reload caddy 2>/dev/null || $SUDO systemctl restart caddy || die "Caddy не запустился: journalctl -u caddy -n 30"
if command -v ufw >/dev/null 2>&1 && $SUDO ufw status 2>/dev/null | grep -q "Status: active"; then
  $SUDO ufw allow 80/tcp >/dev/null; $SUDO ufw allow 443/tcp >/dev/null
  hint "Открыл порты 80 и 443 в ufw"
fi
ok "Caddy настроен"

# ── 5. Сервис ──────────────────────────────────────────────────────────────
step 5 "Запуск"
# Сервис работает от владельца папки, поэтому ключи и библиотеки должны быть его.
RUN_USER="$(stat -c %U "$ROOT")"
mkdir -p "$ROOT/data"
$SUDO chown -R "$RUN_USER" "$VENV" "$ENV_FILE" "$ROOT/data"
$SUDO tee /etc/systemd/system/reviziya.service >/dev/null <<UNIT
[Unit]
Description=Reviziya: price tag scanner (Telegram mini app)
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=$ROOT
ExecStart=$VENV/bin/python -m reviziya_server
Restart=always
RestartSec=3
User=$RUN_USER

[Install]
WantedBy=multi-user.target
UNIT
$SUDO systemctl daemon-reload
$SUDO systemctl enable reviziya >/dev/null 2>&1
$SUDO systemctl restart reviziya

UP=""
for _ in $(seq 1 20); do
  if curl -fsS --max-time 3 "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then UP=1; break; fi
  sleep 1
done
[ -n "$UP" ] || { $SUDO journalctl -u reviziya -n 25 --no-pager || true; die "Сервис не поднялся. Пришли мне строки выше."; }
ok "Сервис работает"

hint "Жду сертификат для https://$DOMAIN (до минуты)…"
HTTPS=""
for _ in $(seq 1 30); do
  if curl -fsS --max-time 5 "https://$DOMAIN/api/health" >/dev/null 2>&1; then HTTPS=1; break; fi
  sleep 2
done

say ""
if [ -n "$HTTPS" ]; then
  say "${GREEN}${BOLD}Готово.${OFF}"
  say "  1. Открой в Telegram бота ${BOLD}@${BOT_NAME:-своего_бота}${OFF} и нажми /start."
  say "  2. Нажми «Открыть сканер». Кто откроет первым, тот становится админом, поэтому открой сам."
  say "  3. Сотрудники открывают того же бота. Тебе придёт сообщение с кнопкой «Допустить»."
else
  bad "Сервис работает, но https://$DOMAIN пока не открывается."
  hint "Проверь, что у сервера открыты порты 80 и 443 (в панели хостинга тоже)."
  hint "Потом посмотри: journalctl -u caddy -n 30 --no-pager"
fi
say ""
hint "Адрес: https://$DOMAIN"
hint "Логи: journalctl -u reviziya -f     Обновить: git pull && sudo systemctl restart reviziya"
