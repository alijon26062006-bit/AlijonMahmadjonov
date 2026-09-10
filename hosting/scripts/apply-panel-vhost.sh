#!/usr/bin/env bash
# Собирает vhost панели и включает его, выбирая HTTP- или HTTPS-версию по тому,
# существует ли сертификат. Один и тот же код нужен и install.sh (первая
# установка), и setup.sh (сразу после выпуска сертификата), поэтому он живёт
# здесь, а не копией в каждом из них.
#
#   apply-panel-vhost.sh            — определить всё из .env
#
# Ничего не ломает при провале: nginx -t проверяется до подмены живого конфига,
# и при ошибке возвращается прежний файл.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOSTING_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${HOSTING_DIR}/.." && pwd)"

# shellcheck source=lib/env-file.sh
. "${SCRIPT_DIR}/lib/env-file.sh"
ENV_FILE="$(hosting_env_file "$REPO_ROOT")"

set -a
# shellcheck disable=SC1090
[[ -f "$ENV_FILE" ]] && . "$ENV_FILE"
set +a

DOMAIN="${HOSTING_ROOT_DOMAIN:-}"
if [[ -z "$DOMAIN" ]]; then
  echo "[vhost] HOSTING_ROOT_DOMAIN не задан в ${ENV_FILE}" >&2
  echo "[vhost] задайте его мастером: sudo bash ${HOSTING_DIR}/setup.sh" >&2
  exit 1
fi
# Значение может быть не просто пустым, а мусорным — например, если в ответ на
# вопрос о домене случайно попала вставленная команда. Собирать из такого vhost
# нельзя: nginx примет что угодно как server_name, и поломка всплывёт позже.
if ! php -r 'require $argv[1]; exit(Hosting\Support\Domain::isValidFqdn($argv[2]) ? 0 : 1);' \
     "${HOSTING_DIR}/autoload.php" "$DOMAIN" 2>/dev/null; then
  echo "[vhost] HOSTING_ROOT_DOMAIN в ${ENV_FILE} — не домен: «${DOMAIN}»" >&2
  echo "[vhost] исправьте: sudo bash ${HOSTING_DIR}/setup.sh (он спросит домен заново)" >&2
  exit 1
fi

PANEL_DOMAIN="panel.${DOMAIN} ${DOMAIN} www.${DOMAIN}"
PANEL_ROOT="${HOSTING_ROOT:-/opt/hosting}/hosting/panel/public"
AVAILABLE="${NGINX_AVAILABLE_DIR:-/etc/nginx/sites-available}/panel.conf"
ENABLED="${NGINX_ENABLED_DIR:-/etc/nginx/sites-enabled}/panel.conf"

# Сертификат ищем и по имени домена, и по имени panel.<домен>: certbot называет
# каталог по ПЕРВОМУ домену в запросе, а он зависит от того, как выпускали.
CERT_DOMAIN=""
for candidate in "$DOMAIN" "panel.${DOMAIN}"; do
  if [[ -f "/etc/letsencrypt/live/${candidate}/fullchain.pem" ]]; then
    CERT_DOMAIN="$candidate"
    break
  fi
done

if [[ -n "$CERT_DOMAIN" ]]; then
  TEMPLATE="${HOSTING_DIR}/templates/nginx-panel-ssl.conf.tpl"
  echo "[vhost] сертификат ${CERT_DOMAIN} найден — собираю vhost с HTTPS"
else
  TEMPLATE="${HOSTING_DIR}/templates/nginx-panel.conf.tpl"
  echo "[vhost] сертификата нет — пока только HTTP"
fi

TMP="${AVAILABLE}.new"
sed \
  -e "s#{{PANEL_NAME}}#${PANEL_NAME:-AlijonHost}#g" \
  -e "s#{{PANEL_DOMAIN}}#${PANEL_DOMAIN}#g" \
  -e "s#{{PANEL_ROOT}}#${PANEL_ROOT}#g" \
  -e "s#{{LOG_DIR}}#${LOG_DIR:-/var/log/hosting}#g" \
  -e "s#{{UPLOAD_MAX_MB}}#${UPLOAD_MAX_MB:-64}#g" \
  -e "s#{{CERT_DOMAIN}}#${CERT_DOMAIN}#g" \
  "$TEMPLATE" > "$TMP"

# На машине без IPv6 строка listen [::] роняет проверку ВСЕГО конфига nginx,
# а не только этого сайта (см. install.sh).
[[ -e /proc/net/if_inet6 ]] || sed -i -E '/^[[:space:]]*listen[[:space:]]+\[::\]/d' "$TMP"

# Отдельная директива «http2 on;» появилась только в nginx 1.25.1. На более
# старых сборках (Ubuntu 24.04 — 1.24) это «unknown directive», и падает
# проверка всего конфига. Там нужен старый синтаксис — флаг в самой listen.
NGINX_VER=$(nginx -v 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
if [[ -n "$NGINX_VER" ]] \
   && [[ "$(printf '%s\n' "1.25.1" "$NGINX_VER" | sort -V | head -1)" != "1.25.1" ]]; then
  sed -i -E '/^[[:space:]]*http2 on;/d' "$TMP"
  sed -i -E 's#^([[:space:]]*listen[[:space:]]+.*)443 ssl;#\1443 ssl http2;#' "$TMP"
  echo "[vhost] nginx ${NGINX_VER}: использую старый синтаксис http2 в listen"
fi

BACKUP=""
if [[ -f "$AVAILABLE" ]]; then
  BACKUP="${AVAILABLE}.bak"
  cp "$AVAILABLE" "$BACKUP"
fi

mv "$TMP" "$AVAILABLE"
ln -sfn "$AVAILABLE" "$ENABLED"

if NGX=$(nginx -t 2>&1); then
  # restart, а не reload: nginx должен войти в группу hosting-web, иначе не
  # увидит файлы сайтов клиентов (reload членство в группах не перечитывает).
  systemctl restart nginx 2>/dev/null || nginx -s reload 2>/dev/null || true
  rm -f "$BACKUP"
  echo "[vhost] применён${CERT_DOMAIN:+ (HTTPS)}"
else
  echo "[vhost] nginx -t не прошёл — возвращаю прежний конфиг:" >&2
  echo "$NGX" >&2
  if [[ -n "$BACKUP" ]]; then
    mv "$BACKUP" "$AVAILABLE"
  else
    rm -f "$AVAILABLE" "$ENABLED"
  fi
  nginx -t >/dev/null 2>&1 && { systemctl reload nginx 2>/dev/null || nginx -s reload 2>/dev/null || true; }
  exit 1
fi
