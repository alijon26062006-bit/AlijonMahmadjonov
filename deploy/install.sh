#!/usr/bin/env bash
# Установка математической дуэли на сервер одной командой.
#
#   curl -fsSL -o install-duel.sh https://raw.githubusercontent.com/alijon26062006-bit/AlijonMahmadjonov/main/deploy/install.sh
#   sudo bash install-duel.sh
#
# Именно так, в два шага: `sudo bash <(curl …)` не работает — sudo закрывает
# лишние дескрипторы, и подставленный файл исчезает прямо из-под bash.
#
# Ставит зависимости, спрашивает токен бота и домен, выпускает сертификат,
# заводит службу и запускает. Повторный запуск обновляет уже установленное.
#
# Можно и без вопросов, если задать всё заранее:
#   sudo DUEL_BOT_TOKEN=... DUEL_DOMAIN=duel.example.com DUEL_EMAIL=я@почта.ru \
#        bash deploy/install.sh
#
set -euo pipefail

DUEL_HOME="${DUEL_HOME:-/opt/duel}"
DUEL_USER="${DUEL_USER:-duel}"
DUEL_PORT="${DUEL_PORT:-8081}"
DUEL_REPO="${DUEL_REPO:-https://github.com/alijon26062006-bit/AlijonMahmadjonov.git}"
DUEL_BRANCH_GIVEN="${DUEL_BRANCH:-}"
DUEL_BRANCH="${DUEL_BRANCH:-main}"
# Пока код не влит в main, установщик сам находит его здесь.
DUEL_FALLBACK_BRANCH="${DUEL_FALLBACK_BRANCH:-claude/telegram-math-duel-bot-wutl1t}"

BOLD=$'\033[1m'; DIM=$'\033[90m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; OFF=$'\033[0m'

say()  { printf '%s\n' "$*"; }
ok()   { printf '  %s✓%s %s\n' "$GREEN" "$OFF" "$*"; }
warn() { printf '  %s!%s %s\n' "$YELLOW" "$OFF" "$*"; }
bad()  { printf '  %s✗%s %s\n' "$RED" "$OFF" "$*" >&2; }
hint() { printf '  %s%s%s\n' "$DIM" "$*" "$OFF"; }
step() { printf '\n%s[%s/7] %s%s\n' "$BOLD" "$1" "$2" "$OFF"; }
die()  { bad "$*"; exit 1; }

# ── проверки значений ───────────────────────────────────────────────────────

valid_token() {
  [[ "${1:-}" =~ ^[0-9]{5,}:[A-Za-z0-9_-]{20,}$ ]]
}

looks_like_ip() {
  [[ "${1:-}" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || [[ "${1:-}" =~ ^[0-9A-Fa-f]*:[0-9A-Fa-f:]*$ ]]
}

valid_domain() {
  local d="${1:-}"
  [ ${#d} -le 253 ] || return 1
  # Последняя часть домена никогда не бывает числом. Так отсеиваются IP-адреса:
  # сертификат на голый IP не выдают, а без него Telegram игру не откроет.
  [[ ! "$d" =~ \.[0-9]+$ ]] || return 1
  [[ "$d" =~ ^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)+$ ]]
}

valid_email() {
  [[ "${1:-}" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]]
}

# git отказывается трогать репозиторий, который принадлежит не ему: с версии
# 2.35 это защита от подмены кода. Папка игры принадлежит своему пользователю,
# поэтому каждый вызов git помечаем как доверенный явно.
git_duel() {
  git -C "$DUEL_HOME" -c "safe.directory=$DUEL_HOME" "$@"
}

# ── что пишем в файлы ───────────────────────────────────────────────────────

render_env() {  # render_env <токен> <домен>
  cat <<ENV
# Настройки математической дуэли. Создано установщиком $(date '+%d.%m.%Y %H:%M').
# Токен — это ключ от бота: кто его знает, тот управляет ботом. Не показывай никому.
DUEL_BOT_TOKEN=$1
DUEL_PUBLIC_URL=https://$2
DUEL_HOST=127.0.0.1
DUEL_PORT=${DUEL_PORT}
DUEL_DATA_DIR=${DUEL_HOME}/data
DUEL_DEV_MODE=0
LOG_LEVEL=INFO
ENV
}

# Пока сертификата нет, поднимаем сайт по http. Дальше certbot сам допишет сюда
# https и переадресацию — поэтому здесь только то, что от него не зависит.
render_nginx() {  # render_nginx <домен>
  cat <<NGINX
# Математическая дуэль. Создано установщиком, правится через deploy/install.sh.
server {
    listen 80;
    listen [::]:80;
    server_name $1;

    # Матч живёт на одном соединении: обрывать его по таймауту нельзя.
    location /ws {
        proxy_pass http://127.0.0.1:${DUEL_PORT};
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
        proxy_buffering off;
    }

    location / {
        proxy_pass http://127.0.0.1:${DUEL_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX
}

# Дальше — сама установка. При запуске через `source` ничего не выполняется:
# так установщик можно проверять тестами.
if [ "${BASH_SOURCE[0]}" != "${0}" ]; then
  return 0 2>/dev/null || true
fi

# ── 1. Можно ли вообще ставить ──────────────────────────────────────────────
say ""
say "${BOLD}Математическая дуэль — установка на сервер${OFF}"
hint "Поставлю всё нужное, выпущу сертификат и запущу. Три-пять минут."

step 1 "Проверяю сервер"

[ "$(id -u)" -eq 0 ] || die "Запусти с правами администратора: sudo bash $0"
[ "$(uname -s)" = "Linux" ] || die "Установщик рассчитан на Linux-сервер."
command -v systemctl >/dev/null 2>&1 || die "Нет systemd — не смогу сделать службу, которая переживёт перезагрузку."
ok "Linux с systemd, права есть"

APT=""
command -v apt-get >/dev/null 2>&1 && APT=1
[ -n "$APT" ] || warn "Пакетный менеджер не apt — недостающее придётся доставить руками."

# ── 2. Токен, домен, почта ──────────────────────────────────────────────────
step 2 "Токен бота и домен"

ENV_FILE="${DUEL_HOME}/.env"
read_env() { [ -f "$ENV_FILE" ] && sed -n "s/^$1=//p" "$ENV_FILE" | head -n1 || true; }

TOKEN="${DUEL_BOT_TOKEN:-$(read_env DUEL_BOT_TOKEN)}"
DOMAIN="${DUEL_DOMAIN:-$(read_env DUEL_PUBLIC_URL | sed 's#^https\?://##; s#/$##')}"
EMAIL="${DUEL_EMAIL:-}"

INTERACTIVE=""
[ -t 0 ] && INTERACTIVE=1
[ -r /dev/tty ] && INTERACTIVE=1

prompt() {  # prompt <вопрос> — читает ответ с клавиатуры, а не из потока
  local answer=""
  if [ -r /dev/tty ]; then read -r -p "  $1" answer < /dev/tty; else read -r -p "  $1" answer; fi
  printf '%s' "$answer"
}

while ! valid_token "$TOKEN"; do
  [ -n "$INTERACTIVE" ] || die "Не задан DUEL_BOT_TOKEN. Получи токен у @BotFather (/newbot)."
  [ -z "$TOKEN" ] || bad "Это не похоже на токен. Он выглядит так: 123456789:AAE...-xyz"
  hint "Токен даёт @BotFather в Telegram по команде /newbot"
  TOKEN="$(prompt 'Токен бота: ')"
done

# Спросим у Телеграма, чей это токен: заодно узнаем имя бота для ссылки.
BOT_USERNAME=""
MAIN_APP=""
if command -v curl >/dev/null 2>&1; then
  ME="$(curl -fsS --max-time 15 "https://api.telegram.org/bot${TOKEN}/getMe" 2>/dev/null || true)"
  case "$ME" in
    *'"ok":true'*) BOT_USERNAME="$(printf '%s' "$ME" | sed -n 's/.*"username":"\([^"]*\)".*/\1/p')" ;;
    *) die "Телеграм не признал этот токен. Проверь его у @BotFather." ;;
  esac
  # Есть ли главное мини-приложение: от этого зависит, откроется ли игра у
  # друга с одного касания по ссылке или ему придётся жать «Начать».
  case "$ME" in
    *'"has_main_web_app":true'*) MAIN_APP=1 ;;
  esac
fi
ok "Бот @${BOT_USERNAME:-?} на связи"

while ! valid_domain "$DOMAIN"; do
  [ -n "$INTERACTIVE" ] || die "Не задан DUEL_DOMAIN. Нужен домен, который смотрит на этот сервер."
  if looks_like_ip "$DOMAIN"; then
    bad "Это IP-адрес, а нужен домен."
    hint "Сертификат на голый IP не выдают, а без https Telegram игру не откроет."
    hint "Нет своего домена — бесплатный за две минуты на duckdns.org:"
    hint "заведи там имя, укажи адрес ${DOMAIN}, и введи сюда имя.duckdns.org"
  elif [ -n "$DOMAIN" ]; then
    bad "Это не похоже на домен. Пример: duel.example.com"
    hint "Telegram открывает игру только по https, поэтому домен обязателен"
  else
    hint "Telegram открывает игру только по https, поэтому домен обязателен"
  fi
  DOMAIN="$(prompt 'Домен: ')"
done
ok "Домен ${DOMAIN}"

# Если домен смотрит не сюда, сертификат не выпустится — лучше узнать сразу.
MY_IP="$(curl -fsS --max-time 8 https://api.ipify.org 2>/dev/null || true)"
DNS_IP="$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk 'NR==1{print $1}' || true)"
if [ -n "$MY_IP" ] && [ -n "$DNS_IP" ] && [ "$MY_IP" != "$DNS_IP" ]; then
  warn "Домен ${DOMAIN} ведёт на ${DNS_IP}, а этот сервер — ${MY_IP}."
  hint "Пока это не исправить в настройках домена, сертификат не выпустится."
  if [ -n "$INTERACTIVE" ]; then
    [ "$(prompt 'Всё равно продолжить? (да/нет): ')" = "да" ] || die "Остановился. Поправь A-запись домена и запусти снова."
  fi
elif [ -n "$DNS_IP" ]; then
  ok "Домен ведёт на этот сервер"
fi

if [ -z "$EMAIL" ] && [ -n "$INTERACTIVE" ] \
   && [ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
  hint "На почту придёт письмо, если сертификат вдруг перестанет обновляться"
  EMAIL="$(prompt 'Почта (можно пропустить, Enter): ')"
fi
[ -z "$EMAIL" ] || valid_email "$EMAIL" || die "Почта записана неверно: $EMAIL"

# ── 3. Системные пакеты ─────────────────────────────────────────────────────
step 3 "Системные пакеты"

if [ -n "$APT" ]; then
  NEED=()
  command -v git >/dev/null 2>&1 || NEED+=(git)
  command -v curl >/dev/null 2>&1 || NEED+=(curl)
  command -v nginx >/dev/null 2>&1 || NEED+=(nginx)
  command -v certbot >/dev/null 2>&1 || NEED+=(certbot python3-certbot-nginx)
  python3 -c 'import venv, ensurepip' >/dev/null 2>&1 || NEED+=(python3-venv)
  command -v python3 >/dev/null 2>&1 || NEED+=(python3)
  if [ ${#NEED[@]} -gt 0 ]; then
    hint "Доставляю: ${NEED[*]}"
    DEBIAN_FRONTEND=noninteractive apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${NEED[@]}" >/dev/null
  fi
fi

for tool in python3 git curl nginx certbot; do
  command -v "$tool" >/dev/null 2>&1 || die "Не хватает программы: $tool. Поставь её и запусти снова."
done
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || die "Нужен Python 3.10 или новее."
ok "Всё нужное на месте"

# ── 4. Код и окружение ──────────────────────────────────────────────────────
step 4 "Код игры"

getent group "$DUEL_USER" >/dev/null 2>&1 || groupadd --system "$DUEL_USER"
id -u "$DUEL_USER" >/dev/null 2>&1 \
  || useradd --system --gid "$DUEL_USER" --home-dir "$DUEL_HOME" \
             --shell /usr/sbin/nologin "$DUEL_USER"

SRC_DIR="$(cd "$(dirname "$(readlink -f "$0")")/.." 2>/dev/null && pwd || true)"

if [ -d "${DUEL_HOME}/.git" ]; then
  git config --global --add safe.directory "$DUEL_HOME" >/dev/null 2>&1 || true

  # Ветку не задали — остаёмся на той, с которой ставили в прошлый раз.
  if [ -z "$DUEL_BRANCH_GIVEN" ]; then
    HERE="$(git_duel rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"
    [ -z "$HERE" ] || [ "$HERE" = "HEAD" ] || DUEL_BRANCH="$HERE"
  fi

  BRANCHES=("$DUEL_BRANCH")
  [ "$DUEL_BRANCH" = "$DUEL_FALLBACK_BRANCH" ] || [ -n "$DUEL_BRANCH_GIVEN" ] \
    || BRANCHES+=("$DUEL_FALLBACK_BRANCH")
  FOUND=""
  for BRANCH in "${BRANCHES[@]}"; do
    # Скачано было одной веткой, поэтому спрашиваем нужную ссылку прямо.
    git_duel fetch --quiet --depth 1 origin \
      "+refs/heads/${BRANCH}:refs/remotes/origin/${BRANCH}" 2>/dev/null || continue
    git_duel checkout --quiet -B "$BRANCH" "origin/${BRANCH}" 2>/dev/null || continue
    git_duel reset --hard --quiet "origin/${BRANCH}" 2>/dev/null || continue
    if [ -f "${DUEL_HOME}/duel/main.py" ]; then FOUND="$BRANCH"; break; fi
    hint "В ветке ${BRANCH} игры нет, смотрю дальше…"
  done
  [ -n "$FOUND" ] \
    || die "Не удалось обновить код в ${DUEL_HOME}. Что сказал git — видно выше."
  DUEL_BRANCH="$FOUND"
  ok "Код обновлён из ветки ${DUEL_BRANCH}"
elif [ -n "$SRC_DIR" ] && [ -f "${SRC_DIR}/duel/main.py" ] && [ "$SRC_DIR" != "$DUEL_HOME" ]; then
  mkdir -p "$DUEL_HOME"
  tar -C "$SRC_DIR" --exclude=.venv --exclude=data -cf - . | tar -C "$DUEL_HOME" -xf -
  ok "Код скопирован из ${SRC_DIR}"
elif [ ! -f "${DUEL_HOME}/duel/main.py" ]; then
  # Ветки пробуем по очереди: игра могла быть ещё не влита в main.
  BRANCHES=("$DUEL_BRANCH")
  [ "$DUEL_BRANCH" = "$DUEL_FALLBACK_BRANCH" ] || [ -n "$DUEL_BRANCH_GIVEN" ] \
    || BRANCHES+=("$DUEL_FALLBACK_BRANCH")
  FOUND=""
  for BRANCH in "${BRANCHES[@]}"; do
    rm -rf "${DUEL_HOME}.tmp"
    if git clone --quiet --depth 1 --branch "$BRANCH" "$DUEL_REPO" "${DUEL_HOME}.tmp" 2>/dev/null \
       && [ -f "${DUEL_HOME}.tmp/duel/main.py" ]; then
      FOUND="$BRANCH"
      break
    fi
    hint "В ветке ${BRANCH} игры нет, смотрю дальше…"
  done
  [ -n "$FOUND" ] || die "Не нашёл код игры ни в одной ветке. Задай нужную: DUEL_BRANCH=имя-ветки"
  DUEL_BRANCH="$FOUND"
  mkdir -p "$DUEL_HOME"
  tar -C "${DUEL_HOME}.tmp" -cf - . | tar -C "$DUEL_HOME" -xf -
  rm -rf "${DUEL_HOME}.tmp"
  ok "Код скачан из ветки ${DUEL_BRANCH}"
else
  ok "Код уже на месте"
fi

[ -f "${DUEL_HOME}/duel/main.py" ] \
  || die "В ${DUEL_HOME} нет игры. Если код в другой ветке, задай её: DUEL_BRANCH=имя-ветки"

mkdir -p "${DUEL_HOME}/data"

if [ ! -x "${DUEL_HOME}/.venv/bin/python" ]; then
  python3 -m venv "${DUEL_HOME}/.venv" || die "Не удалось создать окружение. Поставь python3-venv."
fi
hint "Ставлю библиотеки, это самая долгая часть…"
"${DUEL_HOME}/.venv/bin/python" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
"${DUEL_HOME}/.venv/bin/python" -m pip install --quiet -r "${DUEL_HOME}/requirements-duel.txt" \
  || die "Не удалось поставить библиотеки. Проверь интернет и запусти снова."
ok "Библиотеки готовы"

# ── 5. Настройки ────────────────────────────────────────────────────────────
step 5 "Настройки"

render_env "$TOKEN" "$DOMAIN" > "$ENV_FILE"

# Код принадлежит root и доступен игре только на чтение: так служба не сможет
# переписать сама себя, а git в этой папке работает без лишних разрешений.
chown -R root:root "$DUEL_HOME"
chmod -R a+rX "$DUEL_HOME"
# Своё игре отдаём: база и настройки с токеном.
chown -R "${DUEL_USER}:${DUEL_USER}" "${DUEL_HOME}/data"
chown "${DUEL_USER}:${DUEL_USER}" "$ENV_FILE"
chmod 600 "$ENV_FILE"
ok "Токен записан в ${ENV_FILE} и закрыт от посторонних"

# Игра должна импортироваться и настройки читаться — проверим до запуска службы.
# Путь к игре задаём явно: установщик мог быть запущен из любой папки.
CHECK_PY="$(mktemp)"
cat > "$CHECK_PY" <<'CHECK'
from duel.config import load_config
from duel import main  # noqa: F401

config = load_config()
assert config.public_url.startswith("https://"), config.public_url
print("  настройки читаются:", config.public_url)
CHECK
chmod 644 "$CHECK_PY"
if ! sudo -u "$DUEL_USER" env HOME="$DUEL_HOME" PYTHONPATH="$DUEL_HOME" \
     "${DUEL_HOME}/.venv/bin/python" "$CHECK_PY"; then
  rm -f "$CHECK_PY"
  die "Игра не собирается. Покажи вывод выше — по нему видно, что не так."
fi
rm -f "$CHECK_PY"
ok "Игра собирается, настройки читаются"

# ── 6. Домен и сертификат ───────────────────────────────────────────────────
step 6 "Домен и сертификат"

if [ -d /etc/nginx/sites-available ] && [ -d /etc/nginx/sites-enabled ]; then
  NGINX_CONF=/etc/nginx/sites-available/duel
  render_nginx "$DOMAIN" > "$NGINX_CONF"
  ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/duel
else
  NGINX_CONF=/etc/nginx/conf.d/duel.conf
  render_nginx "$DOMAIN" > "$NGINX_CONF"
fi
nginx -t >/dev/null 2>&1 || { nginx -t; die "nginx не принял настройки."; }
systemctl enable --now nginx >/dev/null 2>&1 || true
systemctl reload nginx
ok "nginx настроен на ${DOMAIN}"

if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "^Status: active"; then
  ufw allow 'Nginx Full' >/dev/null 2>&1 || true
  ok "Порты 80 и 443 открыты в файрволе"
fi

if [ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
  ok "Сертификат уже есть"
else
  hint "Выпускаю бесплатный сертификат Let's Encrypt…"
  CERTBOT_MAIL=(--register-unsafely-without-email)
  [ -z "$EMAIL" ] || CERTBOT_MAIL=(-m "$EMAIL")
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --redirect \
    "${CERTBOT_MAIL[@]}" >/dev/null 2>&1 \
    || die "Сертификат не выпустился. Чаще всего домен ещё не ведёт на этот сервер или порт 80 закрыт. Подробности: certbot --nginx -d ${DOMAIN}"
  ok "Сертификат выпущен, http переведён на https"
fi

# ── 7. Служба ───────────────────────────────────────────────────────────────
step 7 "Запуск"

sed -e "s#/opt/duel#${DUEL_HOME}#g" -e "s#^User=duel#User=${DUEL_USER}#" \
    -e "s#^Group=duel#Group=${DUEL_USER}#" \
    "${DUEL_HOME}/deploy/duel.service" > /etc/systemd/system/duel.service

install -m 755 "${DUEL_HOME}/deploy/duel" /usr/local/bin/duel

systemctl daemon-reload
systemctl enable duel >/dev/null 2>&1
systemctl restart duel

for _ in $(seq 1 30); do
  curl -fsS --max-time 3 "http://127.0.0.1:${DUEL_PORT}/health" >/dev/null 2>&1 && break
  sleep 1
done

HEALTH="$(curl -fsS --max-time 5 "http://127.0.0.1:${DUEL_PORT}/health" 2>/dev/null || true)"
[ -n "$HEALTH" ] || { journalctl -u duel -n 30 --no-pager; die "Служба не отвечает. Журнал выше."; }
ok "Служба работает: ${HEALTH}"

PUBLIC="$(curl -fsS --max-time 10 "https://${DOMAIN}/health" 2>/dev/null || true)"
if [ -n "$PUBLIC" ]; then
  ok "Снаружи тоже отвечает: https://${DOMAIN}"
else
  warn "Изнутри работает, а снаружи https://${DOMAIN}/health не отвечает."
  hint "Проверь, открыты ли порты 80 и 443 у хостера."
fi

say ""
say "${GREEN}${BOLD}Готово.${OFF}"
say ""
if [ -n "$BOT_USERNAME" ]; then
  say "  Открой бота:  ${BOLD}https://t.me/${BOT_USERNAME}${OFF}  и нажми «⚔️ Играть»"
else
  say "  Открой своего бота в Telegram и нажми «⚔️ Играть»"
fi
say ""
say "  ${DIM}duel          — что сейчас происходит${OFF}"
say "  ${DIM}duel logs     — журнал вживую${OFF}"
say "  ${DIM}duel restart  — перезапустить${OFF}"
say "  ${DIM}duel update   — забрать свежий код и перезапустить${OFF}"
say ""
say "  ${DIM}Игра сама поднимется после перезагрузки сервера.${OFF}"
say ""

if [ -z "$MAIN_APP" ]; then
  warn "Осталось одно ручное действие — на него уйдёт полминуты."
  say ""
  say "  Сейчас ссылка-приглашение открывает у друга переписку с ботом, и ему"
  say "  придётся нажать лишний раз. Чтобы игра открывалась сразу:"
  say ""
  say "  ${BOLD}@BotFather${OFF} → /mybots → @${BOT_USERNAME} → Bot Settings →"
  say "  Configure Mini App → Enable Mini App → ${BOLD}https://${DOMAIN}/${OFF}"
  say ""
  say "  ${DIM}После этого перезапусти: duel restart${OFF}"
  say ""
fi
