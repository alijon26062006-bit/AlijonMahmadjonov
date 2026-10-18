#!/usr/bin/env bash
# Вся защита Donatix одной командой: флуд/DDoS, перебор паролей, автоблок атакующих, сторож и ночная
# копия базы в Telegram, закрытые файлы, настоящий IP за Cloudflare. В конце — отчёт, что работает.
# Безопасно запускать повторно: каждый шаг сам проверяет, сделан ли он. Упал один шаг — идут остальные.
#
#   sudo bash /home/donatix/app/donatix/deploy/shield.sh
set -uo pipefail
D=/home/donatix/app/donatix/deploy
[ "$(id -u)" = 0 ] || { echo "Запустите через sudo"; exit 1; }
ok() { printf '  \033[1;32m✔\033[0m %s\n' "$*"; }
no() { printf '  \033[1;31m✖\033[0m %s\n' "$*"; }

step() {
  printf '\n\033[1;34m▶ %s\033[0m\n' "$1"
  if bash "$D/$2" >/tmp/donatix-shield.log 2>&1; then ok "готово"; else no "не вышло — подробности: tail -30 /tmp/donatix-shield.log"; cp /tmp/donatix-shield.log "/tmp/donatix-shield-$2.log"; fi
}

step "Защита от флуда и перебора паролей (nginx + fail2ban)" protect.sh
step "Автоблокировка атакующих навсегда + сообщение в админ-бот" autoban.sh
step "Сторож сайта и ночная копия базы в Telegram" guard.sh
step "Закрытые файлы и службы (если сайт взломают — система цела)" harden.sh
step "Настоящий IP посетителей за Cloudflare" cloudflare.sh

printf '\n\033[1;34m▶ Отчёт\033[0m\n'
systemctl is-active -q donatix && ok "сайт работает" || no "сайт не отвечает: journalctl -u donatix -n 40"
systemctl is-active -q fail2ban && ok "fail2ban включён (блокирует флуд и перебор)" || no "fail2ban не работает"
n=$(fail2ban-client status 2>/dev/null | grep -o "Jail list:.*" | tr ',' '\n' | grep -c . || true)
[ "${n:-0}" -gt 0 ] && ok "правил блокировки: $n" || no "правил блокировки нет"
swapon --show | grep -q . && ok "swap есть ($(free -h | awk '/Swap/{print $2}'))" || no "swap нет — сервер может упасть при нехватке памяти"
grep -q donatix-backup /etc/cron.d/donatix-guard 2>/dev/null && ok "ночная копия базы в Telegram настроена (03:40)" \
  || no "ночная копия базы не настроена"
if ufw status 2>/dev/null | grep -q "Status: active"; then ok "файрвол ufw включён"; else no "файрвол ufw выключен (не страшно, если открыты только 22/80/443)"; fi
grep -q "^PasswordAuthentication no" /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null \
  && ok "вход на сервер по SSH только по ключу" || no "вход по SSH по паролю ещё разрешён (см. ниже)"
DOMAIN=$(grep -oE "^DONATIX_BASE_URL=.*" /home/donatix/app/donatix/.env 2>/dev/null | sed -E 's#.*//([^/]+).*#\1#')
if [ -n "$DOMAIN" ] && curl -sI "https://$DOMAIN" --max-time 8 | grep -qi "^cf-ray"; then
  ok "$DOMAIN работает через Cloudflare — IP сервера скрыт"
else
  no "${DOMAIN:-домен} НЕ через Cloudflare — IP сервера виден всем, его можно атаковать напрямую"
fi
echo
echo "Пришлите этот отчёт — скажу, что осталось."
