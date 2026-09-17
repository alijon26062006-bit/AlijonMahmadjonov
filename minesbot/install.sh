#!/usr/bin/env bash
#
# Установка мина-бота ОДНОЙ командой.
#
#   curl -fsSL https://raw.githubusercontent.com/alijon26062006-bit/AlijonMahmadjonov/claude/telegram-bot-game-24dkzl/minesbot/install.sh | bash
#
# Скрипт сам: поставит python/venv, скачает код, спросит токен @BotFather,
# проверит токен у Telegram, сделает systemd-сервис и запустит бота.
#
set -euo pipefail

REPO="${MINES_REPO:-https://github.com/alijon26062006-bit/AlijonMahmadjonov}"
BRANCH="${MINES_BRANCH:-claude/telegram-bot-game-24dkzl}"
DIR="${MINES_DIR:-$HOME/mines-bot}"
SERVICE="${MINES_SERVICE:-minesbot}"
# Отдельное окружение и отдельный файл ключей: в репозитории есть второй бот.
VENV=".venv-mines"
ENV_FILE=".env.mines"

BOLD=$'\033[1m'; DIM=$'\033[90m'; GREEN=$'\033[32m'; RED=$'\033[31m'; YEL=$'\033[33m'; OFF=$'\033[0m'
say()  { printf '%s\n' "$*"; }
ok()   { printf '  %s✓%s %s\n' "$GREEN" "$OFF" "$*"; }
bad()  { printf '  %s✗%s %s\n' "$RED" "$OFF" "$*" >&2; }
warn() { printf '  %s!%s %s\n' "$YEL" "$OFF" "$*"; }
hint() { printf '  %s%s%s\n' "$DIM" "$*" "$OFF"; }
step() { printf '\n%s[%s/5] %s%s\n' "$BOLD" "$1" "$2" "$OFF"; }
die()  { bad "$*"; exit 1; }

# Вопросы читаем из терминала, а не из stdin: иначе при `curl | bash`
# скрипт «съел бы» сам себя вместо ответа пользователя.
if [ -r /dev/tty ]; then TTY=/dev/tty; else TTY=/dev/stdin; fi
ask() { # ask ПЕРЕМЕННАЯ "вопрос"
  local __var="$1" __prompt="$2" __value=""
  printf '%s' "$__prompt" > /dev/tty 2>/dev/null || printf '%s' "$__prompt"
  IFS= read -r __value < "$TTY" || die "Не могу прочитать ответ. Запусти скрипт в обычном терминале."
  printf -v "$__var" '%s' "$__value"
}

SUDO=""
if [ "$(id -u)" -ne 0 ]; then command -v sudo >/dev/null 2>&1 && SUDO="sudo"; fi

say ""
say "${BOLD}💣 Установка мина-бота${OFF}"
hint "Займёт пару минут. Нужен только токен от @BotFather."

# ── 1. Системные пакеты ────────────────────────────────────────────────────
step 1 "Система"
command -v python3 >/dev/null 2>&1 || {
  hint "Ставлю python3…"
  if command -v apt-get >/dev/null 2>&1; then $SUDO apt-get update -qq && $SUDO apt-get install -y -qq python3 >/dev/null
  elif command -v dnf >/dev/null 2>&1; then $SUDO dnf install -y -q python3 >/dev/null
  else die "Не нашёл python3 и не знаю твой пакетный менеджер. Поставь python3 вручную."; fi
}
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' \
  || die "Нужен Python 3.9 или новее."
ok "Python $(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')"

NEED=()
python3 -c 'import venv, ensurepip' >/dev/null 2>&1 || NEED+=("python3-venv")
command -v git  >/dev/null 2>&1 || NEED+=("git")
command -v curl >/dev/null 2>&1 || NEED+=("curl")
if [ ${#NEED[@]} -gt 0 ]; then
  hint "Доставляю: ${NEED[*]}"
  if command -v apt-get >/dev/null 2>&1; then
    $SUDO apt-get update -qq && $SUDO apt-get install -y -qq "${NEED[@]}" >/dev/null
  elif command -v dnf >/dev/null 2>&1; then
    $SUDO dnf install -y -q git curl python3-venv >/dev/null || true
  else die "Поставь вручную: ${NEED[*]}"; fi
fi
ok "Пакеты на месте"

# ── 2. Код ─────────────────────────────────────────────────────────────────
step 2 "Код бота"
# Если скрипт запущен из уже склонированного репозитория — используем его.
SELF_DIR=""
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi
if [ -n "$SELF_DIR" ] && [ -f "$SELF_DIR/minesbot/main.py" ]; then
  DIR="$SELF_DIR"
  ok "Код уже здесь: $DIR"
elif [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch --quiet origin "$BRANCH"
  git -C "$DIR" checkout --quiet -B "$BRANCH" "origin/$BRANCH"
  ok "Код обновлён: $DIR"
else
  git clone --quiet --depth 1 --branch "$BRANCH" "$REPO" "$DIR" \
    || die "Не смог скачать код. Проверь интернет."
  ok "Код скачан: $DIR"
fi
cd "$DIR"

# ── 3. Зависимости ─────────────────────────────────────────────────────────
step 3 "Зависимости"
[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV" || die "Не создалось .venv (поставь python3-venv)."
"$VENV/bin/python" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
"$VENV/bin/python" -m pip install --quiet -r minesbot/requirements.txt \
  || die "Не поставились библиотеки. Проверь интернет и повтори."
"$VENV/bin/python" -c 'import minesbot.main' >/dev/null 2>&1 \
  || die "Код не импортируется — установка сломана."
ok "Всё поставлено и проверено"

# ── 4. Токен ───────────────────────────────────────────────────────────────
step 4 "Токен бота"

TOKEN="${TELEGRAM_BOT_TOKEN:-}"
# Токен уже сохранён от прошлой установки?
if [ -z "$TOKEN" ] && [ -f "$ENV_FILE" ]; then
  TOKEN="$(grep -E '^TELEGRAM_BOT_TOKEN=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)"
  [ -n "$TOKEN" ] && hint "Нашёл сохранённый токен в $ENV_FILE"
fi

check_token() { # печатает @username, если токен рабочий
  curl -fsS --max-time 15 "https://api.telegram.org/bot$1/getMe" 2>/dev/null \
    | "$VENV/bin/python" -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(1)
if not data.get("ok"):
    sys.exit(1)
print("@" + data["result"]["username"])
'
}

while :; do
  if [ -z "$TOKEN" ]; then
    say ""
    hint "Открой @BotFather в Телеграме → /newbot → скопируй токен."
    hint "Он выглядит так: 123456789:AAE_hs1k…"
    ask TOKEN "  ${BOLD}Токен бота:${OFF} "
    TOKEN="$(printf '%s' "$TOKEN" | tr -d ' \r\t')"
  fi
  if ! printf '%s' "$TOKEN" | grep -qE '^[0-9]+:[A-Za-z0-9_-]{30,}$'; then
    bad "Это не похоже на токен. Скопируй его целиком, вместе с цифрами до двоеточия."
    TOKEN=""; continue
  fi
  if [ "${MINES_SKIP_TOKEN_CHECK:-0}" = "1" ]; then
    warn "Проверку токена у Telegram пропустил (MINES_SKIP_TOKEN_CHECK=1)."
    break
  fi
  if USERNAME="$(check_token "$TOKEN")"; then
    ok "Токен рабочий: $USERNAME"
    break
  fi
  bad "Telegram не принял этот токен (или нет интернета)."
  ask AGAIN "  Ввести другой токен? [Д/н] "
  case "${AGAIN:-д}" in
    [нnNН]*) warn "Оставляю как есть — бот может не запуститься."; break ;;
    *) TOKEN="" ;;
  esac
done

ADMIN_ID="${ADMIN_IDS:-}"
if [ -z "$ADMIN_ID" ]; then
  hint "Свой telegram id (узнать у @userinfobot). Можно пропустить — просто Enter."
  ask ADMIN_ID "  ${BOLD}Твой id:${OFF} "
  ADMIN_ID="$(printf '%s' "$ADMIN_ID" | tr -cd '0-9,')"
fi

umask 077
cat > "$ENV_FILE" <<ENV
# Создано установщиком $(date '+%Y-%m-%d %H:%M'). Файл секретный: никому не показывай.
TELEGRAM_BOT_TOKEN=$TOKEN
ADMIN_IDS=$ADMIN_ID
DATA_DIR=data
START_BALANCE=1000
BONUS_AMOUNT=500
BONUS_HOURS=12
MIN_BET=10
MAX_BET=100000
MINES_COUNT=3
HOUSE_EDGE=0.03
LOG_LEVEL=INFO
ENV
chmod 600 "$ENV_FILE"
ok "Настройки сохранены в $DIR/$ENV_FILE"

# ── 5. Запуск ──────────────────────────────────────────────────────────────
step 5 "Запуск"

install_systemd() {
  # systemd есть только если система реально загружена через него:
  # в контейнерах systemctl бывает установлен, но не работает.
  [ -d /run/systemd/system ] || return 1
  command -v systemctl >/dev/null 2>&1 || return 1
  [ "$(id -u)" -eq 0 ] || [ -n "$SUDO" ] || return 1

  $SUDO tee "/etc/systemd/system/$SERVICE.service" >/dev/null <<UNITFILE
[Unit]
Description=Mines Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(id -un)
WorkingDirectory=$DIR
ExecStart=$DIR/$VENV/bin/python -m minesbot
Restart=always
RestartSec=5
# Бот не должен лезть никуда, кроме своей папки.
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNITFILE
  $SUDO systemctl daemon-reload || return 1
  $SUDO systemctl enable "$SERVICE" >/dev/null 2>&1 || true
  $SUDO systemctl restart "$SERVICE" || return 1
  sleep 3
  $SUDO systemctl is-active --quiet "$SERVICE" || {
    bad "Сервис не поднялся. Последние строки лога:"
    $SUDO journalctl -u "$SERVICE" -n 30 --no-pager || true
    return 2
  }
  return 0
}

set +e
install_systemd
SYSTEMD=$?
set -e

if [ "$SYSTEMD" -eq 0 ]; then
  ok "Бот работает и сам поднимется после перезагрузки сервера"
  say ""
  say "${BOLD}Что дальше${OFF}"
  hint "логи:       sudo journalctl -u $SERVICE -f"
  hint "остановить: sudo systemctl stop $SERVICE"
  hint "запустить:  sudo systemctl start $SERVICE"
  hint "обновить:   bash $DIR/minesbot/install.sh"
elif [ "$SYSTEMD" -eq 2 ]; then
  exit 1
else
  warn "systemd недоступен — запускаю в фоне (nohup)."
  pkill -f "$DIR/$VENV/bin/python -m minesbot" 2>/dev/null || true
  nohup "$DIR/$VENV/bin/python" -m minesbot >> "$DIR/bot.log" 2>&1 &
  PID=$!
  sleep 3
  if kill -0 "$PID" 2>/dev/null; then
    ok "Бот работает (pid $PID)"
  else
    bad "Не запустился. Лог: $DIR/bot.log"
    tail -n 20 "$DIR/bot.log" || true
    exit 1
  fi
  say ""
  say "${BOLD}Что дальше${OFF}"
  hint "логи:       tail -f $DIR/bot.log"
  hint "остановить: kill $PID"
  hint "обновить:   bash $DIR/minesbot/install.sh"
fi

say ""
say "${GREEN}${BOLD}Готово.${OFF} Открой бота в Телеграме и напиши /start"
say ""
