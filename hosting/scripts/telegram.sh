#!/usr/bin/env bash
# Настройка Telegram-бота хостинга по одному токену:
#
#   sudo bash hosting/scripts/telegram.sh 123456:AAE...      — задать токен
#   sudo bash hosting/scripts/telegram.sh                    — спросит токен
#   sudo bash hosting/scripts/telegram.sh --show             — показать текущий
#
# Скрипт сам спрашивает у Telegram, чей это токен (getMe), записывает имя бота,
# настраивает кнопку Mini App, команды и описание, перезапускает службу бота
# и проверяет, что бот действительно отвечает.
#
# Имя бота никогда не вводится руками: раньше в настройках оставалось имя от
# прошлого токена, кнопка входа вела к чужому боту, и понять это было нельзя —
# токен-то валидный.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOSTING_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${HOSTING_DIR}/.." && pwd)"

# shellcheck source=lib/env-file.sh
. "${SCRIPT_DIR}/lib/env-file.sh"
ENV_FILE="$(hosting_env_file "$REPO_ROOT")"

log()  { echo -e "\033[1;32m==>\033[0m $*"; }
warn() { echo -e "\033[1;33m!!\033[0m $*" >&2; }
die()  { echo -e "\033[1;31mОШИБКА:\033[0m $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Запустите от root: sudo bash hosting/scripts/telegram.sh"
[[ -f "$ENV_FILE" ]] || die "Нет ${ENV_FILE} — сначала выполните: sudo bash ${HOSTING_DIR}/install.sh"

env_value() { grep -E "^${1}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2-; }
set_env() {
  local key="$1" value="$2" escaped
  escaped=$(printf '%s' "$value" | sed -e 's/[\\&|]/\\&/g')
  if grep -qE "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${escaped}|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

# Адрес API вынесен в переменную по той же причине, что и в самом боте:
# тесты подставляют локальную заглушку вместо Telegram.
TELEGRAM_API_BASE="${TELEGRAM_API_BASE:-https://api.telegram.org}"

tg() {
  local token="$1" method="$2"; shift 2
  curl -s --noproxy '*' -m 20 "${TELEGRAM_API_BASE%/}/bot${token}/${method}" "$@" 2>/dev/null
}

if [[ "${1:-}" == "--show" ]]; then
  TOKEN=$(env_value TELEGRAM_BOT_TOKEN)
  [[ -n "$TOKEN" ]] || die "Токен не задан в ${ENV_FILE}"
  RESP=$(tg "$TOKEN" getMe)
  echo "Файл настроек: ${ENV_FILE}"
  echo "Имя бота в настройках: @$(env_value TELEGRAM_BOT_USERNAME)"
  echo "Telegram отвечает: ${RESP}"
  exit 0
fi

TOKEN="${1:-}"
if [[ -z "$TOKEN" ]]; then
  echo "Токен бота от @BotFather (/mybots → выбрать бота → API Token):"
  read -rsp "  Токен: " TOKEN
  echo
fi
TOKEN="${TOKEN//[[:space:]]/}"
[[ -n "$TOKEN" ]] || die "Токен пустой"

# Формат токена проверяем до сети: <цифры>:<буквы-цифры>. Опечатку так видно сразу.
[[ "$TOKEN" =~ ^[0-9]{5,}:[A-Za-z0-9_-]{30,}$ ]] \
  || die "Это не похоже на токен бота. Он выглядит так: 123456789:AAE...
     Возьмите его в @BotFather → /mybots → ваш бот → API Token."

log "Спрашиваю у Telegram, чей это токен…"
ME=$(tg "$TOKEN" getMe)
grep -q '"ok":true' <<<"$ME" || die "Telegram не принял токен. Ответ: ${ME:-нет ответа}"

BOT_USERNAME=$(grep -oE '"username":"[^"]+"' <<<"$ME" | head -1 | cut -d'"' -f4)
BOT_TITLE=$(grep -oE '"first_name":"[^"]+"' <<<"$ME" | head -1 | cut -d'"' -f4)
[[ -n "$BOT_USERNAME" ]] || die "Telegram не вернул имя бота: ${ME}"

OLD_USERNAME=$(env_value TELEGRAM_BOT_USERNAME)
if [[ -n "$OLD_USERNAME" && "$OLD_USERNAME" != "$BOT_USERNAME" ]]; then
  warn "Бот меняется: был @${OLD_USERNAME}, стал @${BOT_USERNAME}"
fi

log "Это бот @${BOT_USERNAME} (${BOT_TITLE:-без названия})"
set_env TELEGRAM_BOT_TOKEN "$TOKEN"
set_env TELEGRAM_BOT_USERNAME "$BOT_USERNAME"
chown root:hosting-panel "$ENV_FILE" 2>/dev/null || true
chmod 0640 "$ENV_FILE"

DOMAIN=$(env_value HOSTING_ROOT_DOMAIN)
APP_URL=$(env_value APP_URL)
[[ -n "$APP_URL" ]] || APP_URL="https://panel.${DOMAIN}"

# ── кнопка Mini App ─────────────────────────────────────────────────────────
if [[ "$APP_URL" == https://* ]]; then
  RESP=$(tg "$TOKEN" setChatMenuButton --data-urlencode \
    "menu_button={\"type\":\"web_app\",\"text\":\"Мой хостинг\",\"web_app\":{\"url\":\"${APP_URL}/telegram\"}}")
  if grep -q '"ok":true' <<<"$RESP"; then
    log "Кнопка Mini App настроена: ${APP_URL}/telegram"
  else
    warn "Кнопка Mini App не настроилась: ${RESP}"
    warn "Telegram принимает только https с действующим сертификатом."
  fi
else
  warn "APP_URL = ${APP_URL} (не https) — кнопку Mini App Telegram не примет."
  warn "Сначала выпустите сертификат: sudo bash ${HOSTING_DIR}/setup.sh"
fi

tg "$TOKEN" setMyCommands --data-urlencode \
  'commands=[{"command":"start","description":"Открыть панель хостинга"}]' >/dev/null
tg "$TOKEN" setMyShortDescription --data-urlencode \
  "short_description=Хостинг для PHP-сайтов${DOMAIN:+ на ${DOMAIN}}. Вход без регистрации." >/dev/null
log "Команды и описание бота обновлены"

# ── перезапуск службы ───────────────────────────────────────────────────────
# Бот читает токен один раз при старте, поэтому без перезапуска он продолжит
# работать со старым — самая незаметная причина «поменял токен, ничего не изменилось».
if systemctl restart hosting-bot 2>/dev/null; then
  log "Служба бота перезапущена"
else
  warn "Не удалось перезапустить hosting-bot — проверьте: systemctl status hosting-bot"
fi

# ── проверка, что бот действительно забирает сообщения ──────────────────────
# getUpdates с чужой стороны вернёт 409, если тот же токен опрашивает кто-то ещё,
# — ровно тот случай, когда бот «то отвечает, то нет».
sleep 3
CONFLICT=$(tg "$TOKEN" getUpdates -d 'timeout=0&limit=1')
if grep -q '"error_code":409' <<<"$CONFLICT"; then
  log "Токен опрашивает наш бот — это правильно (Telegram отдаёт 409 второму читателю)"
elif grep -q '"ok":true' <<<"$CONFLICT"; then
  warn "Никто не опрашивает бота: служба hosting-bot, похоже, не работает."
  warn "Проверьте: journalctl -u hosting-bot -n 30"
fi

echo
log "Готово. Бот: https://t.me/${BOT_USERNAME}"
echo "   Откройте бота и нажмите «Старт» — придёт кнопка «Открыть панель»."
echo
echo "Осталось одно действие в @BotFather (метода Bot API для него нет):"
echo "   /setdomain → @${BOT_USERNAME} → ${DOMAIN}"
echo "   Оно включает кнопку «Войти через Telegram» на самом сайте."
echo "   Вход через бота работает и без этого."
