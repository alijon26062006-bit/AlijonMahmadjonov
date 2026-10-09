#!/usr/bin/env bash
# Укрепление сервера Donatix (только этот проект, другие не трогает). Безопасно запускать повторно.
#
# 1. База, чеки, файлы тикетов, сессия банковского бота, копии базы и .env — читать может только donatix
#    (раньше файлы создавались «читать всем» — их видели другие пользователи сервера и проекты).
# 2. Службы donatix и donatix-bankbot: новые файлы сразу закрытые (UMask 077), без повышения прав,
#    системные папки только для чтения, свой /tmp. Если сайт когда-нибудь взломают — он не тронет систему.
#
#   sudo bash /home/donatix/app/donatix/deploy/harden.sh
set -uo pipefail
APP_USER=donatix
HOME_DIR=/home/$APP_USER
APP_DIR=$HOME_DIR/app
DATA_DIR=$APP_DIR/donatix/data
ENV_FILE=$APP_DIR/donatix/.env
say() { printf '\n\033[1;32m== %s\033[0m\n' "$*"; }
ok() { echo "  ✓ $*"; }
die() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }
[ "$(id -u)" = 0 ] || die "Запустите через sudo"
[ -d "$APP_DIR" ] || die "Нет $APP_DIR — это не сервер Donatix"

say "1/3 Права на данные"
chmod 750 "$HOME_DIR"
[ -f "$ENV_FILE" ] && chown "$APP_USER": "$ENV_FILE" && chmod 600 "$ENV_FILE" && ok ".env — только donatix"
for f in "$ENV_FILE".bak*; do [ -f "$f" ] && chmod 600 "$f"; done
if [ -d "$DATA_DIR" ]; then
  # -P: по ссылкам не ходим (подложенная ссылка не сменит права системного файла)
  find -P "$DATA_DIR" -xdev \( -type d -exec chmod 700 {} + \) -o \( -type f -exec chmod 600 {} + \)
  ok "data/ (база, чеки, тикеты, картинки, сессия банк-бота) — только donatix"
fi
if [ -d "$HOME_DIR/backup" ]; then
  find -P "$HOME_DIR/backup" -xdev \( -type d -exec chmod 700 {} + \) -o \( -type f -exec chmod 600 {} + \)
  ok "копии базы — только donatix"
fi

say "2/3 Ограничения для служб"
for unit in donatix donatix-bankbot; do
  systemctl cat "$unit" >/dev/null 2>&1 || continue
  mkdir -p "/etc/systemd/system/$unit.service.d"
  cat > "/etc/systemd/system/$unit.service.d/hardening.conf" <<'UNIT'
[Service]
UMask=0077
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
RestrictRealtime=yes
LockPersonality=yes
UNIT
  ok "$unit"
done
systemctl daemon-reload

say "3/3 Перезапуск"
for unit in donatix donatix-bankbot; do
  systemctl is-enabled "$unit" >/dev/null 2>&1 || continue
  systemctl restart "$unit"
done
sleep 4
state=$(systemctl is-active donatix)
code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/ || true)
echo "  сайт: $state, ответ $code"
if [ "$state" != "active" ] || [ "$code" != "200" ]; then
  echo "  ✖ что-то не так — откатываю ограничения служб (права на файлы остаются)"
  rm -f /etc/systemd/system/donatix.service.d/hardening.conf /etc/systemd/system/donatix-bankbot.service.d/hardening.conf
  systemctl daemon-reload; systemctl restart donatix
  systemctl is-enabled donatix-bankbot >/dev/null 2>&1 && systemctl restart donatix-bankbot
  echo "  пришлите вывод: journalctl -u donatix -n 40 --no-pager"
  exit 1
fi
echo "Готово: данные закрыты, службы ограничены, сайт работает."
