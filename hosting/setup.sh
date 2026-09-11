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
# shellcheck source=scripts/lib/env-file.sh
. "${SCRIPT_DIR}/scripts/lib/env-file.sh"
ENV_FILE="$(hosting_env_file "$REPO_ROOT")"

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

# Проверка ответов — не формальность.
#
# Реальный случай: человек вставил в терминал сразу две команды, вторая строка
# попала в ответ на вопрос о домене, и в настройках оказалось
# HOSTING_ROOT_DOMAIN="sudo bash hosting/scripts/telegram.sh". Мастер это принял,
# и дальше сломалось всё: vhost не собрался, Telegram отверг адрес Mini App.
# Поэтому ответы проверяются здесь, а не «падают» через три шага.
is_valid_domain() {
  php -r 'require $argv[1]; exit(Hosting\Support\Domain::isValidFqdn($argv[2]) ? 0 : 1);' \
    "${REPO_ROOT}/hosting/autoload.php" "$1" 2>/dev/null
}

ask_domain() {
  local prompt="$1" default="$2" answer
  # Заведомо непригодное значение из .env не предлагаем как ответ по умолчанию.
  if [[ -n "$default" ]] && ! is_valid_domain "$default"; then
    warn "В настройках записан недопустимый домен: ${default} — введите правильный"
    default=""
  fi

  while true; do
    answer=$(ask "$prompt" "$default")
    answer="${answer,,}"
    answer="${answer#http://}"; answer="${answer#https://}"; answer="${answer%%/*}"
    if is_valid_domain "$answer"; then
      echo "$answer"
      return 0
    fi
    warn "«${answer}» не похоже на домен. Нужен вид diyorhost.com — без http://, без пробелов."
  done
}

ask_email() {
  local prompt="$1" default="${2:-}" answer
  while true; do
    answer=$(ask "$prompt" "$default")
    if [[ -z "$answer" ]] || [[ "$answer" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]]; then
      echo "$answer"
      return 0
    fi
    warn "«${answer}» не похоже на e-mail."
  done
}

ask_secret_optional() {
  local prompt="$1" answer
  read -rsp "$prompt (Enter — пропустить): " answer
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

DOMAIN=$(ask_domain "Основной домен хостинга" "$(current_env HOSTING_ROOT_DOMAIN)")
[[ -n "$DOMAIN" ]] || die "Домен обязателен"

DETECTED_IP=$(curl -4 -s -m 10 ifconfig.me || true)
SERVER_IP=$(ask "Публичный IP сервера" "${DETECTED_IP:-$(current_env HOSTING_SERVER_IP)}")
[[ -n "$SERVER_IP" ]] || die "IP обязателен — по нему проверяются домены клиентов"

set_env HOSTING_ROOT_DOMAIN "$DOMAIN"
set_env HOSTING_SERVER_IP "$SERVER_IP"
set_env APP_URL "https://panel.${DOMAIN}"

# Название хостинга берём из домена: diyorhost.com → DiyorHost. Домен — то
# единственное, что владелец точно уже выбрал и купил, а имя из примера
# (AlijonHost) иначе так и остаётся на витрине у всех.
SUGGESTED_NAME=$(php -r 'require $argv[1]; echo Hosting\Support\Brand::fromDomain($argv[2]);' \
  "${REPO_ROOT}/hosting/autoload.php" "$DOMAIN" 2>/dev/null || true)
PANEL_NAME_CURRENT=$(current_env PANEL_NAME)
PANEL_NAME_NEW=$(ask "Название хостинга (видно на сайте и в панели)" "${SUGGESTED_NAME:-$PANEL_NAME_CURRENT}")
[[ -n "$PANEL_NAME_NEW" ]] && set_env PANEL_NAME "$PANEL_NAME_NEW"

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
echo "Токен нужен для входа клиентов через бота и Mini App."
echo "Взять: @BotFather → /mybots → ваш бот → API Token. Можно пропустить (Enter)."
echo
echo "Важно: это должен быть токен ОТДЕЛЬНОГО бота для хостинга."
echo "Если дать сюда токен бота, который уже где-то работает, два процесса начнут"
echo "тянуть его сообщения по очереди, и на /start ответ будет приходить через раз."

TG_TOKEN=$(ask_secret_optional "Токен бота хостинга")
BOT_NAME=""
if [[ -n "$TG_TOKEN" ]]; then
  # Всё, что можно узнать у Telegram, узнаёт telegram.sh: имя бота, кнопку
  # Mini App, команды. Здесь только сохраняем токен, чтобы не дублировать логику.
  set_env TELEGRAM_BOT_TOKEN "$TG_TOKEN"
  BOT_NAME=$(curl -s -m 15 "https://api.telegram.org/bot${TG_TOKEN}/getMe" \
    | grep -oE '"username":"[^"]+"' | head -1 | cut -d'"' -f4 || true)
  if [[ -n "$BOT_NAME" ]]; then
    set_env TELEGRAM_BOT_USERNAME "$BOT_NAME"
    log "Токен рабочий, бот: @${BOT_NAME}"
  else
    warn "Telegram не принял этот токен — вход через Telegram работать не будет"
  fi

  TG_CHAT=$(ask "Ваш Telegram ID для алертов мониторинга (узнать: @userinfobot)" "$(current_env TELEGRAM_ADMIN_CHAT_ID)")
  [[ -n "$TG_CHAT" ]] && set_env TELEGRAM_ADMIN_CHAT_ID "$TG_CHAT"
else
  warn "Без токена вход через Telegram и алерты работать не будут"
  echo "Задать позже: sudo bash ${SCRIPT_DIR}/scripts/telegram.sh"
fi

# ── 3. почта для сертификатов ──────────────────────────────────────────────
head2 "Почта"
ACME_EMAIL=$(ask_email "E-mail для Let's Encrypt (туда придёт письмо, если сертификат перестанет продлеваться)" "$(current_env ACME_EMAIL)")
[[ -n "$ACME_EMAIL" ]] && set_env ACME_EMAIL "$ACME_EMAIL"

# ── 4. администратор ───────────────────────────────────────────────────────
head2 "Администратор панели"

ADMIN_EMAIL=$(ask_email "Ваш e-mail для входа в панель")
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

# Сертификат — не украшение: Telegram и Mini App, и кнопку входа на сайте
# принимает ТОЛЬКО по HTTPS. Поэтому сначала выпускаем обычный сертификат для
# самой панели по HTTP-01: он не требует ни одной ручной записи в DNS —
# домен уже указывает сюда, порт 80 открыт, certbot кладёт файл проверки
# в /var/www/html. Wildcard для поддоменов клиентов — отдельный шаг ниже,
# он требует TXT-записи и не должен блокировать запуск Telegram.

cert_dir_for() {
  for c in "$DOMAIN" "panel.${DOMAIN}"; do
    [[ -f "/etc/letsencrypt/live/${c}/fullchain.pem" ]] && { echo "$c"; return 0; }
  done
  return 1
}

if CERT_NAME=$(cert_dir_for); then
  log "Сертификат уже есть (${CERT_NAME})"
else
  log "Выпускаю сертификат для ${DOMAIN}, panel.${DOMAIN} и www.${DOMAIN}…"
  mkdir -p /var/www/html

  # db.<домен> — адрес phpMyAdmin, он тоже должен открываться по https:
  # клиент вводит там пароль от своей базы.
  CERT_ARGS=(--webroot -w /var/www/html --non-interactive --agree-tos
             -d "$DOMAIN" -d "panel.${DOMAIN}" -d "www.${DOMAIN}" -d "db.${DOMAIN}")
  if [[ -n "${ACME_EMAIL:-}" ]]; then
    CERT_ARGS+=(--email "$ACME_EMAIL" --no-eff-email)
  else
    CERT_ARGS+=(--register-unsafely-without-email)
  fi

  if certbot certonly "${CERT_ARGS[@]}"; then
    log "Сертификат выпущен"
  else
    warn "Certbot не выпустил сертификат."
    warn "Чаще всего причина одна из двух: A-запись ещё не разошлась, либо порт 80 закрыт снаружи."
    warn "Проверить снаружи: curl -I http://${DOMAIN}/.well-known/acme-challenge/test"
    warn "Панель останется на http, вход через Telegram работать не будет."
  fi
fi

# Перекладываем vhost панели на HTTPS, если сертификат появился.
bash "${SCRIPT_DIR}/scripts/apply-panel-vhost.sh" || warn "Не удалось применить vhost панели"

if CERT_NAME=$(cert_dir_for); then
  # APP_URL уходит в data-auth-url виджета Telegram и в ссылки писем: по http
  # Telegram его не примет.
  set_env APP_URL "https://panel.${DOMAIN}"
  APP_SCHEME="https"
  # Сайтам клиентов конфиги перегенерирует воркер — теперь у них тоже может быть HTTPS.
  systemctl restart hosting-worker 2>/dev/null || true
else
  APP_SCHEME="http"
fi

# Wildcard нужен ТОЛЬКО поддоменам клиентов (shop.домен). Панель и Telegram
# работают и без него, поэтому это отдельный необязательный шаг.
WILDCARD_CERT="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
if [[ "${APP_SCHEME}" == "https" ]] \
   && ! openssl x509 -noout -text -in "$WILDCARD_CERT" 2>/dev/null | grep -q "DNS:\*\.${DOMAIN}" \
   && ask_yes_no "Выпустить ещё и wildcard (*.${DOMAIN}) для сайтов клиентов? Понадобится TXT-запись" n; then
  echo
  echo "Certbot покажет TXT-запись. Добавьте её у регистратора, подождите минуту и нажмите Enter."
  echo
  certbot certonly --manual --preferred-challenges dns --cert-name "wildcard-${DOMAIN}" \
    -d "$DOMAIN" -d "*.${DOMAIN}" \
    ${ACME_EMAIL:+--email "$ACME_EMAIL"} ${ACME_EMAIL:+--agree-tos} \
    ${ACME_EMAIL:+--no-eff-email} || warn "Certbot не завершил выпуск wildcard — можно повторить позже"
  systemctl restart hosting-worker 2>/dev/null || true
fi

# ── 6b. настройка бота ─────────────────────────────────────────────────────
# Кнопку Mini App можно настроить только после выпуска сертификата (Telegram
# принимает в web_app исключительно https), поэтому это здесь, а не выше.
if [[ -n "${TG_TOKEN:-}" ]]; then
  head2 "Настраиваю бота"
  bash "${SCRIPT_DIR}/scripts/telegram.sh" "$TG_TOKEN" || warn "Не удалось настроить бота — запустите отдельно: sudo bash ${SCRIPT_DIR}/scripts/telegram.sh"

  if [[ -n "${BOT_NAME:-}" ]]; then
    if ask_yes_no "Вы уже сделали /setdomain для @${BOT_NAME} в @BotFather? Включить виджет входа на сайте?" n; then
      set_env TELEGRAM_LOGIN_WIDGET true
      log "Виджет входа на сайте включён"
    else
      set_env TELEGRAM_LOGIN_WIDGET false
    fi
  fi
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

# После перехода на HTTPS порт 80 отдаёт редирект всему, кроме проверки ACME,
# поэтому проверяем по той же схеме, на которой панель реально работает.
# --resolve вместо заголовка Host: он подставляет имя и в SNI тоже, иначе
# TLS-рукопожатие пойдёт не с тем сертификатом.
panel_curl() {
  local path="$1"; shift
  if [[ "${APP_SCHEME}" == "https" ]]; then
    curl -s -m 10 --resolve "panel.${DOMAIN}:443:127.0.0.1" "https://panel.${DOMAIN}${path}" "$@"
  else
    curl -s -m 10 -H "Host: panel.${DOMAIN}" "http://127.0.0.1${path}" "$@"
  fi
}

HEALTH=$(panel_curl /health || true)
if grep -q '"status":"ok"' <<<"$HEALTH"; then
  echo "  ✓ панель отвечает и видит свою базу данных"
else
  echo "  ✗ health-check: ${HEALTH:-нет ответа}"
  ALL_OK=0
fi

LOGIN_CODE=$(panel_curl /login -o /dev/null -w '%{http_code}' || true)
if [[ "$LOGIN_CODE" == "200" ]]; then
  echo "  ✓ страница входа открывается"
else
  echo "  ✗ страница входа отдала код ${LOGIN_CODE}"
  ALL_OK=0
fi

echo
if [[ $ALL_OK -eq 1 ]]; then
  PROTO="${APP_SCHEME}"
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
