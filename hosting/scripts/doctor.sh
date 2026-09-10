#!/usr/bin/env bash
# Полная диагностика хостинга одной командой:
#
#   sudo bash hosting/scripts/doctor.sh
#
# Проверяет всё, от чего зависит работа клиентов: службы, конфиги, базу, очередь
# заданий (включая живой ping до воркера), DNS, HTTP-ответы панели, сертификаты,
# место на диске и права на файлах с секретами.
#
# Для каждой найденной проблемы печатает не только «не работает», но и причину
# (кусок journal / вывод nginx -t) и команду, которой это чинят.
#
# Код возврата: 0 — проблем нет, 1 — есть хотя бы одна [ПРОБЛЕМА].

set -uo pipefail   # намеренно без -e: доктор обязан дойти до конца, а не падать на первой ошибке

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOSTING_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${HOSTING_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"

FAILS=0
WARNS=0

ok()   { echo -e "  \033[1;32m[OK]\033[0m       $*"; }
bad()  { echo -e "  \033[1;31m[ПРОБЛЕМА]\033[0m $*"; FAILS=$((FAILS+1)); }
warn() { echo -e "  \033[1;33m[ВНИМАНИЕ]\033[0m $*"; WARNS=$((WARNS+1)); }
hint() { echo -e "             → $*"; }
head2() { echo; echo -e "\033[1m── $* ──────────────────────────\033[0m"; }

[[ $EUID -eq 0 ]] || { echo "Запустите от root: sudo bash hosting/scripts/doctor.sh" >&2; exit 1; }

# ── .env ───────────────────────────────────────────────────────────────────
head2 "Конфигурация"

if [[ ! -f "$ENV_FILE" ]]; then
  bad "нет ${ENV_FILE}"
  hint "sudo bash ${HOSTING_DIR}/install.sh"
  echo; echo "Дальше проверять нечего — без .env не работает ничего."
  exit 1
fi
ok ".env на месте: ${ENV_FILE}"

set -a
# shellcheck disable=SC1090
. "$ENV_FILE" 2>/dev/null
set +a

PERM=$(stat -c '%a' "$ENV_FILE")
if [[ "$PERM" == "640" || "$PERM" == "600" ]]; then
  ok "права на .env: ${PERM} (секреты не читает кто попало)"
else
  bad ".env с правами ${PERM} — в нём пароль от базы и SESSION_SECRET"
  hint "chown root:hosting-panel ${ENV_FILE} && chmod 0640 ${ENV_FILE}"
fi

# Права «не слишком широкие» — половина дела. Вторая половина: панель обязана
# свой конфиг ПРОЧИТАТЬ. При root:root 0640 она молча получает пустой пароль
# от базы и не поднимается, а по одним битам режима это незаметно.
if id -u hosting-panel >/dev/null 2>&1; then
  if su -s /bin/sh hosting-panel -c "test -r '${ENV_FILE}'" 2>/dev/null; then
    ok "панель (hosting-panel) читает свой .env"
  else
    bad "пользователь hosting-panel НЕ может прочитать ${ENV_FILE}"
    hint "панель из-за этого не видит пароль от базы: chown root:hosting-panel ${ENV_FILE} && chmod 0640 ${ENV_FILE}"
  fi
else
  bad "нет системного пользователя hosting-panel — панель и бот не запустятся"
  hint "sudo bash ${HOSTING_DIR}/install.sh"
fi

if [[ -f /etc/hosting/worker.env ]]; then
  WPERM=$(stat -c '%a' /etc/hosting/worker.env)
  if [[ "$WPERM" == "600" ]]; then
    ok "права на /etc/hosting/worker.env: 600"
  else
    bad "/etc/hosting/worker.env с правами ${WPERM} — там пароль root от MariaDB"
    hint "chmod 0600 /etc/hosting/worker.env"
  fi
else
  bad "нет /etc/hosting/worker.env — воркер не сможет управлять базами клиентов"
  hint "sudo bash ${HOSTING_DIR}/install.sh"
fi

check_env_filled() {
  local key="$1" why="$2" value="${!1:-}"
  if [[ -n "$value" ]]; then
    ok "${key} заполнен"
  else
    bad "${key} пустой — ${why}"
    hint "sudo bash ${HOSTING_DIR}/setup.sh"
  fi
}
# HOSTING_ROOT обязан указывать на этот репозиторий: по нему systemd-юниты,
# nginx-шаблоны и скрипты находят свои файлы. Если это пустой каталог, воркер
# падает с 203/EXEC и служба вечно висит в activating, а причина совсем не там,
# где её ищут.
HR="${HOSTING_ROOT:-/opt/hosting}"
if [[ "$(readlink -f "$HR" 2>/dev/null)" == "$(readlink -f "$REPO_ROOT")" ]]; then
  ok "${HR} указывает на репозиторий (${REPO_ROOT})"
else
  bad "${HR} указывает на '$(readlink -f "$HR" 2>/dev/null || echo "ничего")', а репозиторий лежит в ${REPO_ROOT}"
  hint "из-за этого systemd-юниты ссылаются на несуществующие файлы: sudo bash ${HOSTING_DIR}/install.sh"
fi

WORKER_BIN="${HR}/hosting/worker/bin/hosting-worker.php"
if [[ -f "$WORKER_BIN" ]]; then
  ok "воркер на месте: ${WORKER_BIN}"
else
  bad "нет файла ${WORKER_BIN}, а именно его запускает systemd"
  hint "sudo bash ${HOSTING_DIR}/install.sh"
fi

check_env_filled HOSTING_ROOT_DOMAIN "без домена не строятся адреса сайтов клиентов"
check_env_filled DB_PASSWORD         "панель не подключится к своей базе"
check_env_filled SESSION_SECRET      "сессии можно будет подделать"

if [[ -n "${TELEGRAM_BOT_TOKEN:-}" ]]; then
  ok "TELEGRAM_BOT_TOKEN заполнен"
  if [[ -n "${TELEGRAM_BOT_USERNAME:-}" ]]; then
    ok "TELEGRAM_BOT_USERNAME=${TELEGRAM_BOT_USERNAME} (кнопка входа на главной работает)"
  else
    bad "TELEGRAM_BOT_USERNAME пустой — кнопка «Войти через Telegram» на главной не отрисуется"
    hint "sudo bash ${HOSTING_DIR}/setup.sh — он узнает имя бота по токену сам"
  fi
  BOT_JSON=$(curl -s -m 10 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe" 2>/dev/null)
  if grep -q '"ok":true' <<<"$BOT_JSON"; then
    ok "Telegram принимает токен бота"

    # Кнопка меню — это и есть вход в Mini App. Если она не настроена, клиент,
    # открывший бота, никуда попасть не сможет.
    MENU=$(curl -s -m 10 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getChatMenuButton" 2>/dev/null)
    if grep -q '"type":"web_app"' <<<"$MENU"; then
      ok "кнопка Mini App у бота настроена"
    else
      bad "у бота не настроена кнопка Mini App — из Telegram в панель не попасть"
      hint "sudo bash ${HOSTING_DIR}/setup.sh (настроит сам, нужен выпущенный сертификат)"
    fi
  else
    bad "Telegram отклонил токен бота: ${BOT_JSON:-нет ответа}"
    hint "возьмите свежий токен у @BotFather и перезапустите setup.sh"
  fi
else
  warn "TELEGRAM_BOT_TOKEN пустой — вход через Telegram и Mini App выключены"
fi

# ── службы ─────────────────────────────────────────────────────────────────
head2 "Службы"

PHP_VERSION="${PHP_VERSIONS%%,*}"
PHP_VERSION="${PHP_VERSION:-8.3}"

for svc in nginx "php${PHP_VERSION}-fpm" mariadb hosting-worker hosting-bot fail2ban; do
  state=$(systemctl is-active "$svc" 2>/dev/null) || true
  [[ -n "$state" ]] || state="неизвестно"

  if [[ "$state" == "active" ]]; then
    ok "${svc}: active"
    continue
  fi

  bad "${svc}: ${state}"
  # activating означает перезапуск по кругу: сам по себе он ничего не объясняет,
  # причина всегда в journal — печатаем её сразу, чтобы не гонять человека за ней.
  if [[ "$state" == "activating" ]]; then
    hint "служба перезапускается по кругу — ниже последние строки её журнала:"
  fi
  journalctl -u "$svc" -n 12 --no-pager 2>&1 | sed 's/^/             /'
done

# ── конфиги ────────────────────────────────────────────────────────────────
head2 "Конфигурация служб"

if ! command -v nginx >/dev/null 2>&1; then
  bad "nginx не установлен"
  hint "sudo bash ${HOSTING_DIR}/install.sh"
elif NGX=$(nginx -t 2>&1); then
  ok "nginx -t проходит"
else
  bad "nginx -t не проходит:"
  sed 's/^/             /' <<<"$NGX"
fi

if command -v "php-fpm${PHP_VERSION}" >/dev/null 2>&1; then
  if FPM=$("php-fpm${PHP_VERSION}" -t 2>&1); then
    ok "php-fpm${PHP_VERSION} -t проходит"
  else
    bad "php-fpm${PHP_VERSION} -t не проходит:"
    sed 's/^/             /' <<<"$FPM"
  fi
fi

POOLS=$(find "${FPM_POOL_DIR:-/etc/php/${PHP_VERSION}/fpm/pool.d}" -name '*.conf' 2>/dev/null | wc -l)
ok "пулов php-fpm: ${POOLS} (панель + по одному на клиента)"

SITES=$(find "${NGINX_ENABLED_DIR:-/etc/nginx/sites-enabled}" -type l -o -type f 2>/dev/null | wc -l)
ok "включённых сайтов nginx: ${SITES}"

if [[ -f /etc/sudoers.d/hosting-admin ]]; then
  if visudo -cf /etc/sudoers.d/hosting-admin >/dev/null 2>&1; then
    ok "sudoers панели валиден"
  else
    bad "sudoers панели невалиден — sudo может сломаться целиком:"
    visudo -cf /etc/sudoers.d/hosting-admin 2>&1 | sed 's/^/             /'
  fi
fi

# ── PHP ────────────────────────────────────────────────────────────────────
head2 "PHP"

ok "версия CLI: $(php -r 'echo PHP_VERSION;' 2>/dev/null || echo '?')"
for ext in pdo_mysql zip mbstring json; do
  if php -m 2>/dev/null | grep -qix "$ext"; then
    ok "расширение ${ext}"
  else
    bad "нет расширения PHP ${ext} — без него панель не работает"
    hint "apt install php${PHP_VERSION}-${ext}"
  fi
done
for ext in curl gd simplexml opcache; do
  php -m 2>/dev/null | grep -qix "$ext" || warn "нет расширения ${ext} — часть CMS клиентов может не завестись"
done

# ── база и очередь ─────────────────────────────────────────────────────────
head2 "База данных и очередь заданий"

PROBE=""
systemctl is-active hosting-worker >/dev/null 2>&1 && PROBE="--probe"
while IFS='|' read -r status text; do
  [[ -n "$status" ]] || continue
  case "$status" in
    OK)   ok   "$text" ;;
    WARN) warn "$text" ;;
    FAIL) bad  "$text" ;;
    *)    echo "             ${status}${text}" ;;
  esac
done < <(php "${HOSTING_DIR}/scripts/doctor-db.php" $PROBE 2>&1 | grep -E '^(OK|WARN|FAIL)\|' || true)

# ── сеть и DNS ─────────────────────────────────────────────────────────────
head2 "Сеть и DNS"

for port in 80 443; do
  if ss -ltn 2>/dev/null | grep -q ":${port} "; then
    ok "порт ${port} слушается"
  else
    bad "порт ${port} никто не слушает — сайты клиентов недоступны снаружи"
  fi
done

SERVER_IP="${HOSTING_SERVER_IP:-}"
[[ -n "$SERVER_IP" ]] || SERVER_IP=$(curl -s -m 10 https://api.ipify.org 2>/dev/null)

if [[ -z "$SERVER_IP" ]]; then
  warn "не удалось определить внешний IP сервера — проверку DNS пропускаю"
  hint "впишите HOSTING_SERVER_IP в ${ENV_FILE}"
elif [[ -n "${HOSTING_ROOT_DOMAIN:-}" ]]; then
  for name in "${HOSTING_ROOT_DOMAIN}" "panel.${HOSTING_ROOT_DOMAIN}" "proverka-dns.${HOSTING_ROOT_DOMAIN}"; do
    resolved=$(getent ahostsv4 "$name" 2>/dev/null | awk 'NR==1{print $1}')
    if [[ -z "$resolved" ]]; then
      bad "${name} не резолвится"
      hint "добавьте A-запись ${name} -> ${SERVER_IP} (для поддоменов клиентов нужен именно wildcard: A *.${HOSTING_ROOT_DOMAIN})"
    elif [[ "$resolved" == "$SERVER_IP" ]]; then
      ok "${name} -> ${resolved}"
    else
      warn "${name} -> ${resolved}, а сервер ${SERVER_IP} (Cloudflare-проксирование выглядит так же — это нормально)"
    fi
  done
fi

# ── ответы панели ──────────────────────────────────────────────────────────
head2 "Панель отвечает"

if [[ -n "${HOSTING_ROOT_DOMAIN:-}" ]]; then
  HEALTH=$(curl -s -m 10 -H "Host: panel.${HOSTING_ROOT_DOMAIN}" http://127.0.0.1/health 2>/dev/null)
  if grep -q '"status":"ok"' <<<"$HEALTH"; then
    ok "/health: панель видит свою базу"
  else
    bad "/health вернул: ${HEALTH:-нет ответа}"
    hint "tail -30 ${LOG_DIR:-/var/log/hosting}/panel-error.log"
  fi

  for path in / /login /register; do
    code=$(curl -s -o /dev/null -w '%{http_code}' -m 10 -H "Host: ${HOSTING_ROOT_DOMAIN}" "http://127.0.0.1${path}" 2>/dev/null)
    if [[ "$code" == "200" ]]; then
      ok "страница ${path} отдаёт 200"
    else
      bad "страница ${path} отдала ${code}"
      hint "tail -30 ${LOG_DIR:-/var/log/hosting}/panel-error.log"
    fi
  done
fi

# ── SSL ────────────────────────────────────────────────────────────────────
head2 "Сертификаты"

CERT="/etc/letsencrypt/live/${HOSTING_ROOT_DOMAIN:-none}/fullchain.pem"
if [[ -f "$CERT" ]]; then
  END=$(openssl x509 -enddate -noout -in "$CERT" 2>/dev/null | cut -d= -f2)
  LEFT=$(( ( $(date -d "$END" +%s) - $(date +%s) ) / 86400 ))
  if [[ $LEFT -gt 14 ]]; then
    ok "сертификат действует ещё ${LEFT} дн."
  else
    bad "сертификат истекает через ${LEFT} дн. — сайты начнут ругаться в браузере"
    hint "certbot renew"
  fi
  if openssl x509 -noout -text -in "$CERT" 2>/dev/null | grep -q "DNS:\*\.${HOSTING_ROOT_DOMAIN}"; then
    ok "сертификат wildcard — поддомены клиентов покрыты"
  else
    warn "сертификат без wildcard — https на поддоменах клиентов работать не будет"
  fi
else
  warn "нет сертификата для ${HOSTING_ROOT_DOMAIN:-домена} — панель работает только по http"
  hint "sudo bash ${HOSTING_DIR}/setup.sh"
fi

# ── ресурсы ────────────────────────────────────────────────────────────────
head2 "Ресурсы сервера"

USED=$(df --output=pcent / 2>/dev/null | tail -1 | tr -dc '0-9')
if [[ -n "$USED" && "$USED" -lt 85 ]]; then
  ok "диск занят на ${USED}%"
else
  bad "диск занят на ${USED}% — при 100% перестанут работать и база, и загрузка файлов"
  hint "du -sh ${HOSTING_USERS_ROOT:-/home/hosting}/* ${HOSTING_ROOT:-/opt/hosting}/backups 2>/dev/null | sort -h | tail"
fi

INODES=$(df -i --output=pcent / 2>/dev/null | tail -1 | tr -dc '0-9')
if [[ -z "$INODES" ]]; then
  : # некоторые ФС (overlay в контейнере) не отдают счётчик inode — это не проблема
elif [[ "$INODES" -lt 85 ]]; then
  ok "inode занято на ${INODES}%"
else
  bad "inode занято на ${INODES}% — файлы перестанут создаваться раньше, чем кончится место"
fi

MEM_FREE=$(free -m 2>/dev/null | awk '/^Mem:/{print $7}')
if [[ -n "$MEM_FREE" && "$MEM_FREE" -gt 300 ]]; then
  ok "свободной памяти: ${MEM_FREE} МБ"
else
  warn "свободной памяти всего ${MEM_FREE:-?} МБ — MariaDB может быть убита OOM"
fi

CLIENTS=$(find "${HOSTING_USERS_ROOT:-/home/hosting}" -maxdepth 1 -name 'client*' -type d 2>/dev/null | wc -l)
ok "домашних каталогов клиентов: ${CLIENTS}"

# ── итог ───────────────────────────────────────────────────────────────────
echo
if [[ $FAILS -eq 0 && $WARNS -eq 0 ]]; then
  echo -e "\033[1;32m✓ Проблем не найдено — хостинг готов принимать клиентов.\033[0m"
elif [[ $FAILS -eq 0 ]]; then
  echo -e "\033[1;33m✓ Критических проблем нет. Замечаний: ${WARNS} (см. [ВНИМАНИЕ] выше).\033[0m"
else
  echo -e "\033[1;31m✗ Проблем: ${FAILS}, замечаний: ${WARNS}. Чинить нужно то, что помечено [ПРОБЛЕМА].\033[0m"
  exit 1
fi
