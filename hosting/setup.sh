#!/usr/bin/env bash
# Мастер настройки AlijonHost: спрашивает всё, что нужно, сам заполняет .env,
# заводит администратора, при желании выпускает SSL и проверяет, что панель
# реально отвечает.
#
#   sudo bash hosting/setup.sh
#
# Запускать ПОСЛЕ install.sh. Можно запускать повторно — все ответы
# подставляются из текущего .env как значения по умолчанию, так что достаточно
# жать Enter на том, что менять не нужно.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"

log()  { echo -e "\033[1;32m==>\033[0m $*"; }
warn() { echo -e "\033[1;33m!!\033[0m $*" >&2; }
die()  { echo -e "\033[1;31mОШИБКА:\033[0m $*" >&2; exit 1; }
head2() { echo; echo -e "\033[1m── $* ─────────────────────────────\033[0m"; }

[[ $EUID -eq 0 ]] || die "Запустите от root: sudo bash hosting/setup.sh"
[[ -f "$ENV_FILE" ]] || die "Нет ${ENV_FILE} — сначала выполните: sudo bash hosting/install.sh"

# read -p печатает приглашение в stderr, поэтому подстановка $(ask ...) забирает
# только сам ответ и приглашение не попадает в переменную.
ask() {
  local prompt="$1" default="${2:-}" answer
  if [[ -n "$default" ]]; then
    read -rp "$prompt [$default]: " answer
    echo "${answer:-$default}"
  else
    read -rp "$prompt: " answer
    echo "$answer"
  fi
}

ask_secret() {
  local prompt="$1" answer
  read -rsp "$prompt: " answer
  echo >&2
  echo "$answer"
}

ask_yes_no() {
  local prompt="$1" default="${2:-y}" answer
  read -rp "$prompt [$([[ $default == y ]] && echo "Y/n" || echo "y/N")]: " answer
  answer="${answer:-$default}"
  [[ "${answer,,}" == y* ]]
}

current_env() {
  grep -E "^${1}=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- || true
}

set_env() {
  local key="$1" value="$2" escaped
  # Экранируем то, что sed трактует особо, — иначе токен со слэшем всё сломает.
  escaped=$(printf '%s' "$value" | sed -e 's/[\\&|]/\\&/g')
  if grep -qE "^${key}=" "$ENV_FILE"; then
    sed -i "s|^${key}=.*|${key}=${escaped}|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

echo
echo -e "\033[1mНастройка хостинга AlijonHost\033[0m"
echo "Отвечайте на вопросы; чтобы оставить значение в скобках — просто Enter."

# ── 1. домен и IP ─────────────────────────────────────────────────────────
head2 "Домен и адрес сервера"

DOMAIN=$(ask "Основной домен хостинга" "$(current_env HOSTING_ROOT_DOMAIN)")
[[ -n "$DOMAIN" ]] || die "Домен обязателен"

DETECTED_IP=$(curl -4 -s -m 10 ifconfig.me || true)
SERVER_IP=$(ask "Публичный IP сервера" "${DETECTED_IP:-$(current_env HOSTING_SERVER_IP)}")
[[ -n "$SERVER_IP" ]] || die "IP обязателен — по нему проверяются домены клиентов"

set_env HOSTING_ROOT_DOMAIN "$DOMAIN"
set_env HOSTING_SERVER_IP "$SERVER_IP"
set_env APP_URL "https://panel.${DOMAIN}"

# Проверяем DNS сразу: без wildcard сайты клиентов работать не будут, и лучше
# узнать об этом здесь, чем после первой жалобы клиента.
log "Проверяю DNS…"
RESOLVED_ROOT=$(getent hosts "$DOMAIN" 2>/dev/null | awk '{print $1}' | head -1 || true)
RESOLVED_WILD=$(getent hosts "proverka-$$.${DOMAIN}" 2>/dev/null | awk '{print $1}' | head -1 || true)

if [[ "$RESOLVED_ROOT" == "$SERVER_IP" ]]; then
  log "A-запись ${DOMAIN} → ${SERVER_IP}: верно"
else
  warn "${DOMAIN} резолвится в '${RESOLVED_ROOT:-ничего}', а не в ${SERVER_IP} — панель по домену не откроется"
fi

if [[ "$RESOLVED_WILD" == "$SERVER_IP" ]]; then
  log "Wildcard *.${DOMAIN} работает: сайты клиентов будут открываться"
else
  warn "*.${DOMAIN} не резолвится в ${SERVER_IP} — добавьте A-запись с именем * у регистратора,"
  warn "иначе поддомены клиентов (shop.${DOMAIN}) работать не будут"
fi

# ── 2. Telegram ────────────────────────────────────────────────────────────
head2 "Telegram"
echo "Токен нужен для входа клиентов через Mini App и для алертов мониторинга."
echo "Получить: @BotFather → /newbot. Можно пропустить (Enter) и добавить позже."

TG_TOKEN=$(ask "Токен бота" "$(current_env TELEGRAM_BOT_TOKEN)")
if [[ -n "$TG_TOKEN" ]]; then
  set_env TELEGRAM_BOT_TOKEN "$TG_TOKEN"
  # Проверяем токен у самого Telegram — опечатку лучше поймать сейчас.
  BOT_NAME=$(curl -s -m 10 "https://api.telegram.org/bot${TG_TOKEN}/getMe" \
    | grep -oE '"username":"[^"]+"' | head -1 | cut -d'"' -f4 || true)
  if [[ -n "$BOT_NAME" ]]; then
    log "Токен рабочий, бот: @${BOT_NAME}"
    # Имя бота нужно кнопке «Войти через Telegram» на публичной главной —
    # виджет Telegram принимает username, а не токен.
    set_env TELEGRAM_BOT_USERNAME "$BOT_NAME"
    log "Кнопку Mini App настрою сам чуть ниже, после выпуска сертификата"
  else
    warn "Telegram не принял этот токен — вход через Mini App работать не будет"
  fi

  TG_CHAT=$(ask "Ваш Telegram ID для алертов мониторинга (узнать: @userinfobot)" "$(current_env TELEGRAM_ADMIN_CHAT_ID)")
  [[ -n "$TG_CHAT" ]] && set_env TELEGRAM_ADMIN_CHAT_ID "$TG_CHAT"
else
  warn "Без токена вход через Telegram и алерты в Telegram работать не будут"
fi

# ── 3. почта для сертификатов ──────────────────────────────────────────────
head2 "Почта"
ACME_EMAIL=$(ask "E-mail для Let's Encrypt (туда придёт письмо, если сертификат перестанет продлеваться)" "$(current_env ACME_EMAIL)")
[[ -n "$ACME_EMAIL" ]] && set_env ACME_EMAIL "$ACME_EMAIL"

# ── 4. администратор ───────────────────────────────────────────────────────
head2 "Администратор панели"

ADMIN_EMAIL=$(ask "Ваш e-mail для входа в панель")
[[ -n "$ADMIN_EMAIL" ]] || die "E-mail администратора обязателен"

while true; do
  ADMIN_PASS=$(ask_secret "Пароль (минимум 8 символов)")
  ADMIN_PASS2=$(ask_secret "Пароль ещё раз")
  [[ "$ADMIN_PASS" == "$ADMIN_PASS2" ]] || { warn "Пароли не совпали, попробуйте снова"; continue; }
  [[ ${#ADMIN_PASS} -ge 8 ]] || { warn "Слишком короткий пароль"; continue; }
  break
done

if printf '%s' "$ADMIN_PASS" | php "${SCRIPT_DIR}/panel/bin/create-admin.php" "$ADMIN_EMAIL" pro; then
  log "Администратор готов"
else
  die "Не удалось создать администратора — смотрите ошибку выше"
fi

# ── 5. перезапуск с новыми настройками ────────────────────────────────────
head2 "Применяю настройки"
# Воркер читает .env один раз при старте (EnvironmentFile), поэтому его нужно
# перезапустить, чтобы он увидел новый домен и токен.
systemctl restart hosting-worker 2>/dev/null || warn "hosting-worker не перезапустился"
systemctl reload nginx 2>/dev/null || true
log "Сервисы перезапущены"

# ── 6. SSL ─────────────────────────────────────────────────────────────────
head2 "SSL-сертификат"

WILDCARD_CERT="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
if [[ -f "$WILDCARD_CERT" ]]; then
  log "Сертификат для ${DOMAIN} уже есть"
elif ask_yes_no "Выпустить wildcard-сертификат сейчас? (нужно будет добавить TXT-запись у регистратора)"; then
  echo
  echo "Certbot сейчас покажет TXT-запись. Добавьте её у регистратора домена,"
  echo "подождите минуту и нажмите Enter в certbot."
  echo
  certbot certonly --manual --preferred-challenges dns \
    -d "$DOMAIN" -d "*.${DOMAIN}" \
    ${ACME_EMAIL:+--email "$ACME_EMAIL"} ${ACME_EMAIL:+--agree-tos} \
    ${ACME_EMAIL:+--no-eff-email} || warn "Certbot не завершил выпуск — можно повторить позже"

  if [[ -f "$WILDCARD_CERT" ]]; then
    log "Сертификат выпущен — HTTPS заработает для панели и всех поддоменов"
    # Существующие сайты нужно перегенерировать: теперь у них может быть HTTPS.
    systemctl restart hosting-worker 2>/dev/null || true
  fi
else
  echo "Позже выпустите так:"
  echo "  certbot certonly --manual --preferred-challenges dns -d ${DOMAIN} -d '*.${DOMAIN}'"
fi

# ── 6b. настройка самого бота через Bot API ────────────────────────────────
# Всё, что Telegram позволяет настроить программно, настраиваем здесь, а не
# просим человека кликать в @BotFather. Единственное исключение — /setdomain
# для кнопки входа на сайте: метода Bot API для него нет.
if [[ -n "${TG_TOKEN:-}" && -n "${BOT_NAME:-}" ]]; then
  head2 "Настраиваю бота @${BOT_NAME}"

  tg_api() {
    local method="$1"; shift
    curl -s -m 15 "https://api.telegram.org/bot${TG_TOKEN}/${method}" "$@" 2>/dev/null
  }

  MINIAPP_URL="https://panel.${DOMAIN}/telegram"

  if [[ -f "$WILDCARD_CERT" ]]; then
    # Telegram принимает в web_app только https и только домен с валидным
    # сертификатом — до его выпуска этот вызов гарантированно провалится.
    RESP=$(tg_api setChatMenuButton --data-urlencode \
      "menu_button={\"type\":\"web_app\",\"text\":\"Мой хостинг\",\"web_app\":{\"url\":\"${MINIAPP_URL}\"}}")
    if grep -q '"ok":true' <<<"$RESP"; then
      log "Кнопка Mini App настроена: клиент открывает бота и сразу попадает в панель"
    else
      warn "Не удалось настроить кнопку Mini App: ${RESP}"
      warn "Сделайте вручную: @BotFather → /setmenubutton → @${BOT_NAME} → ${MINIAPP_URL}"
    fi
  else
    warn "Кнопку Mini App пока не настроить — Telegram требует https, а сертификата ещё нет."
    warn "Выпустите сертификат и запустите setup.sh ещё раз."
  fi

  RESP=$(tg_api setMyCommands --data-urlencode \
    'commands=[{"command":"start","description":"Открыть панель хостинга"}]')
  grep -q '"ok":true' <<<"$RESP" && log "Команды бота обновлены" || true

  tg_api setMyShortDescription --data-urlencode \
    "short_description=Хостинг для PHP-сайтов на ${DOMAIN}. Вход без регистрации." >/dev/null

  echo
  echo "  Осталось ровно одно действие в @BotFather (метода Bot API для него нет):"
  echo "     /setdomain → @${BOT_NAME} → ${DOMAIN}"
  echo
  echo "  Оно включает виджет «Войти через Telegram» прямо на главной странице."
  echo "  Пока это не сделано, Telegram рисует на месте виджета белую плашку"
  echo "  «Bot domain invalid» — поэтому виджет по умолчанию выключен, а вход"
  echo "  идёт по кнопке-ссылке на бота, которая работает всегда."
  echo
  if ask_yes_no "Вы уже сделали /setdomain для @${BOT_NAME}? Включить виджет на главной?" n; then
    set_env TELEGRAM_LOGIN_WIDGET true
    log "Виджет входа включён"
  else
    set_env TELEGRAM_LOGIN_WIDGET false
    echo "  Хорошо — сделаете /setdomain, запустите setup.sh ещё раз и ответьте «y»."
  fi
  echo
fi

# ── 7. проверка ────────────────────────────────────────────────────────────
head2 "Проверка"

ALL_OK=1
for svc in nginx mariadb hosting-worker; do
  # is-active печатает состояние и при этом выходит с ненулевым кодом на всём,
  # кроме active. Поэтому значение и код возврата берём раздельно — иначе
  # в переменную попадали бы обе строки сразу.
  state=$(systemctl is-active "$svc" 2>/dev/null) || true
  [[ -n "$state" ]] || state="не запущен"

  if [[ "$state" == "active" ]]; then
    echo "  ✓ ${svc}"
  else
    echo "  ✗ ${svc}: ${state}"
    # "activating" значит перезапуск по кругу — причина всегда в журнале.
    journalctl -u "$svc" -n 10 --no-pager 2>&1 | sed 's/^/      /'
    ALL_OK=0
  fi
done

HEALTH=$(curl -s -m 10 -H "Host: panel.${DOMAIN}" http://127.0.0.1/health || true)
if grep -q '"status":"ok"' <<<"$HEALTH"; then
  echo "  ✓ панель отвечает и видит свою базу данных"
else
  echo "  ✗ health-check: ${HEALTH:-нет ответа}"
  ALL_OK=0
fi

LOGIN_CODE=$(curl -s -o /dev/null -w '%{http_code}' -m 10 -H "Host: panel.${DOMAIN}" http://127.0.0.1/login || true)
if [[ "$LOGIN_CODE" == "200" ]]; then
  echo "  ✓ страница входа открывается"
else
  echo "  ✗ страница входа отдала код ${LOGIN_CODE}"
  ALL_OK=0
fi

echo
if [[ $ALL_OK -eq 1 ]]; then
  PROTO="http"; [[ -f "$WILDCARD_CERT" ]] && PROTO="https"
  log "Готово. Панель: ${PROTO}://panel.${DOMAIN}"
  echo "   Вход: ${ADMIN_EMAIL}"
  echo
  echo "Что дальше:"
  echo "  • Зайдите в панель и создайте первый сайт — проверьте, что он открывается"
  echo "  • Клиентам давайте адрес ${PROTO}://panel.${DOMAIN}/register"
  [[ -n "${BOT_NAME:-}" ]] && echo "  • В @BotFather: /setmenubutton → ${PROTO}://panel.${DOMAIN}/telegram"
else
  warn "Часть проверок не прошла — смотрите отметки ✗ выше"
  echo "Полная диагностика с причинами и командами для починки:"
  echo "    sudo bash ${SCRIPT_DIR}/scripts/doctor.sh"
fi

echo
echo "Проверить весь хостинг целиком в любой момент: sudo bash ${SCRIPT_DIR}/scripts/doctor.sh"
