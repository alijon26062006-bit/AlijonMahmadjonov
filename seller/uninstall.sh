#!/usr/bin/env bash
# Полное удаление того, что поставил deploy.sh: файлы сайта, настройки nginx, HTTPS-сертификат.
#
#   curl -fsSL https://raw.githubusercontent.com/alijon26062006-bit/AlijonMahmadjonov/seller-app/seller/uninstall.sh | sudo bash
#
# С флагом --all удаляются ещё и сами программы nginx и certbot (если на сервере больше ничего на них не работает):
#
#   curl -fsSL https://raw.githubusercontent.com/alijon26062006-bit/AlijonMahmadjonov/seller-app/seller/uninstall.sh | sudo bash -s -- --all
#
# Магазины, товары и заказы хранятся не на сервере, а в базе Supabase, — их этот скрипт не трогает.
set -euo pipefail

ALL=0; [ "${1:-}" = "--all" ] && ALL=1
APP_DIR="/opt/seller-panel"
CONF=/etc/nginx/sites-available/seller-panel

log()  { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
note() { printf '    %s\n' "$*"; }
die()  { printf '\n\033[1;31mОшибка: %s\033[0m\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "запустите с sudo"

# домен берём из настроек nginx, которые записал deploy.sh
DOMAIN=""
[ -f "$CONF" ] && DOMAIN=$(awk '/server_name/ { gsub(/;/, "", $2); print $2; exit }' "$CONF")
[ "$DOMAIN" = "_" ] && DOMAIN=""

log "Будет удалено"
note "файлы сайта:        $APP_DIR"
note "настройки nginx:    $CONF"
[ -n "$DOMAIN" ] && note "HTTPS-сертификат:   $DOMAIN"
[ "$ALL" -eq 1 ] && note "программы:          nginx, certbot"
note "Передумали — нажмите Ctrl+C в течение 10 секунд"
sleep 10

log "Удаляю файлы сайта"
rm -rf "$APP_DIR" "$APP_DIR.new" "$APP_DIR.old"

log "Удаляю настройки nginx"
rm -f /etc/nginx/sites-enabled/seller-panel "$CONF"

if [ -n "$DOMAIN" ] && command -v certbot >/dev/null && [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
  log "Удаляю HTTPS-сертификат $DOMAIN"
  certbot delete --cert-name "$DOMAIN" --non-interactive -q || note "не получилось удалить сертификат — можно оставить, он просто истечёт"
fi

if [ "$ALL" -eq 1 ]; then
  log "Удаляю nginx и certbot"
  if command -v ufw >/dev/null && ufw status | grep -q "Status: active"; then ufw delete allow 'Nginx Full' >/dev/null 2>&1 || true; fi
  [ -d /run/systemd/system ] && systemctl stop nginx 2>/dev/null || nginx -s stop 2>/dev/null || true
  export DEBIAN_FRONTEND=noninteractive
  apt-get -o DPkg::Lock::Timeout=600 purge -y -qq 'nginx*' certbot python3-certbot-nginx >/dev/null 2>&1 || true
  apt-get -o DPkg::Lock::Timeout=600 autoremove -y -qq >/dev/null 2>&1 || true
  rm -rf /etc/letsencrypt/renewal/"$DOMAIN".conf
elif command -v nginx >/dev/null; then
  # nginx остаётся: возвращаем стандартную страницу, чтобы он запускался без нашего сайта
  [ -f /etc/nginx/sites-available/default ] && ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default
  if nginx -t -q 2>/dev/null; then
    if [ -d /run/systemd/system ]; then systemctl reload nginx 2>/dev/null || true; else nginx -s reload 2>/dev/null || true; fi
  else
    note "nginx сообщает об ошибке в других настройках — проверьте: sudo nginx -t"
  fi
fi

log "Готово: сайт удалён с сервера"
[ "$ALL" -eq 1 ] || note "nginx и certbot оставлены. Удалить и их: добавьте --all"
note "Данные магазинов в базе Supabase не тронуты"
