#!/usr/bin/env bash
# Проверка защиты сервера по пунктам: что закрыто, что открыто. Ничего не меняет — только смотрит.
#   sudo bash /home/donatix/app/donatix/deploy/audit.sh
set -uo pipefail
[ "$(id -u)" = 0 ] || { echo "Запустите через sudo"; exit 1; }
ENV=/home/donatix/app/donatix/.env
GOOD=0; BAD=0
ok() { GOOD=$((GOOD+1)); printf '  \033[1;32m✔\033[0m %s\n' "$*"; }
no() { BAD=$((BAD+1)); printf '  \033[1;31m✖\033[0m %s\n' "$*"; }
head_() { printf '\n\033[1;34m▶ %s\033[0m\n' "$1"; }

DOMAIN=$(grep -oE "^DONATIX_BASE_URL=.*" "$ENV" 2>/dev/null | sed -E 's#.*//([^/]+).*#\1#')
MYIP=$(curl -s -m 8 https://api.ipify.org || hostname -I | awk '{print $1}')

head_ "1. Заход мимо Cloudflare (прямой удар по IP сервера)"
code=$(curl -sk -m 8 -o /dev/null -w "%{http_code}" --resolve "$DOMAIN:443:$MYIP" "https://$DOMAIN/" 2>/dev/null)
if [ "$code" = "000" ] || [ "$code" = "444" ]; then ok "прямой заход на $MYIP отбит (код $code)"
else no "прямой заход на $MYIP ПРОШЁЛ (код $code) — включите: cloudflare.sh с LOCK=1 и смените IP"; fi
curl -sI -m 8 "https://$DOMAIN/" | grep -qi "^cf-ray" && ok "$DOMAIN идёт через Cloudflare" || no "$DOMAIN идёт НЕ через Cloudflare"

head_ "2. Открытые порты (что видно из интернета)"
ss -tlnH 2>/dev/null | awk '{print $4}' | while read -r a; do
  port=${a##*:}; host=${a%:*}
  case "$host" in 127.*|"[::1]"|::1) continue ;; esac
  echo "$port"
done | sort -un | tr '\n' ' ' > /tmp/donatix-audit-ports
PORTS=$(cat /tmp/donatix-audit-ports)
echo "  слушают снаружи: ${PORTS:-ничего}"
for p in $PORTS; do
  case "$p" in 22|80|443) ;; *) no "порт $p открыт всем — если это не ваш проект, закройте: ufw deny $p" ;; esac
done
echo " $PORTS " | grep -qE " (8000|5432|3306|6379|27017) " && no "служба базы или приложения слушает наружу" || ok "база и приложение снаружи закрыты"
ufw status 2>/dev/null | grep -q "Status: active" && ok "файрвол ufw включён" || no "файрвол ufw выключен"

head_ "3. Защита от флуда на сервере"
[ -f /etc/nginx/conf.d/donatix-limits.conf ] && ok "лимиты запросов nginx есть" || no "лимитов nginx нет (protect.sh)"
[ -f /etc/nginx/conf.d/donatix-cf-only.conf ] && ok "nginx пускает только Cloudflare" || no "nginx пускает не только Cloudflare"
[ "$(sysctl -n net.ipv4.tcp_syncookies 2>/dev/null)" = "1" ] && ok "защита от SYN-флуда (syncookies) включена" || no "syncookies выключены"
systemctl is-active -q fail2ban && ok "fail2ban работает" || no "fail2ban не работает"

head_ "4. Вход на сервер"
grep -rqE "^PasswordAuthentication no" /etc/ssh/sshd_config /etc/ssh/sshd_config.d/ 2>/dev/null \
  && ok "SSH только по ключу" || no "SSH по паролю разрешён — его можно перебирать"
grep -rqE "^PermitRootLogin (no|prohibit-password|without-password)" /etc/ssh/sshd_config /etc/ssh/sshd_config.d/ 2>/dev/null \
  && ok "root по паролю не пускают" || no "root можно зайти по паролю"

head_ "5. Секреты и файлы"
perm=$(stat -c %a "$ENV" 2>/dev/null)
[ -n "$perm" ] && { [ "${perm: -1}" = "0" ] && ok ".env закрыт от посторонних ($perm)" || no ".env читают все ($perm): chmod 600 $ENV"; }
curl -s -m 8 -o /dev/null -w "%{http_code}" "http://127.0.0.1:8000/.env" | grep -q 200 && no ".env отдаётся через сайт!" || ok ".env через сайт не отдаётся"
curl -s -m 8 -o /dev/null -w "%{http_code}" "http://127.0.0.1:8000/data/donatix.db" | grep -q 200 && no "база отдаётся через сайт!" || ok "база через сайт не отдаётся"

head_ "6. Заголовки сайта"
H=$(curl -sI -m 8 "http://127.0.0.1:8000/" || true)
echo "$H" | grep -qi "x-frame-options\|frame-ancestors" && ok "защита от встраивания (clickjacking)" || no "нет X-Frame-Options"
echo "$H" | grep -qi "x-content-type-options" && ok "X-Content-Type-Options есть" || no "нет X-Content-Type-Options"
echo "$H" | grep -qi "^server:.*[0-9]\." && no "сервер показывает версию ПО" || ok "версия ПО не светится"

head_ "7. Обновления и резервные копии"
[ -f /var/run/reboot-required ] && no "нужна перезагрузка сервера (обновление ядра): sudo reboot ночью" || ok "перезагрузка не нужна"
n=$(apt list --upgradable 2>/dev/null | grep -c security || true)
[ "${n:-0}" -gt 0 ] && no "есть обновления безопасности: $n (apt update && apt upgrade)" || ok "обновлений безопасности нет"
grep -q donatix-backup /etc/cron.d/donatix-guard 2>/dev/null && ok "ночная копия базы настроена" || no "ночной копии базы нет (guard.sh)"
swapon --show | grep -q . && ok "swap есть" || no "swap нет"

head_ "Итог"
echo "  хорошо: $GOOD   замечаний: $BAD"
[ "$BAD" = 0 ] && echo "  Замечаний нет." || echo "  Пришлите этот вывод — скажу, что исправить в первую очередь."
