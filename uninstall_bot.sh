#!/usr/bin/env bash
# Полностью убрать бота со СТАРОГО сервера после переезда: службы, процессы,
# папки с кодом, базу, .env с токеном и ключами, архивы, команду bot.
#
#   bash uninstall_bot.sh НОВЫЙ_IP          — спросит подтверждение
#   UNINSTALL_DRY=1 bash uninstall_bot.sh IP — только показать, ничего не удалять
#
# НОВЫЙ_IP обязателен: на сервере с этим адресом команда откажется работать,
# чтобы случайно не стереть рабочий бот.
set -uo pipefail

NEW_IP="${1:-}"
DRY="${UNINSTALL_DRY:-0}"
REPO_HINT="AlijonMahmadjonov"

ok()   { printf '\033[1;32m✅ %s\033[0m\n' "$*"; }
bad()  { printf '\033[1;31m❌ %s\033[0m\n' "$*" >&2; }
say()  { printf '\033[1;36m%s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m⚠️  %s\033[0m\n' "$*"; }
run()  { if [ "$DRY" = "1" ]; then echo "   [проверка] $*"; else "$@"; fi; }

if [ -z "$NEW_IP" ]; then
  bad "Укажите IP НОВОГО сервера:  bash uninstall_bot.sh 89.207.254.178"
  exit 1
fi
if [ "$(id -u)" -ne 0 ] && [ "$DRY" != "1" ]; then
  bad "Нужны права root."
  exit 1
fi

# ── 1. Это точно НЕ новый сервер? ─────────────────────────────────────
MY_IPS="$(hostname -I 2>/dev/null) $(curl -s -m 10 ipinfo.io/ip 2>/dev/null)"
for ip in $MY_IPS; do
  if [ "$ip" = "$NEW_IP" ]; then
    bad "Это НОВЫЙ сервер ($NEW_IP) — здесь работает ваш магазин. Ничего не удаляю."
    echo "   Запускайте эту команду на СТАРОМ сервере."
    exit 1
  fi
done
say "Сервер: $(hostname) ($(echo $MY_IPS | tr ' ' '\n' | grep -v '^$' | sort -u | tr '\n' ' '))"

# ── 2. Что нашлось ────────────────────────────────────────────────────
DIRS=()
add_dir() {
  local d
  d="$(readlink -f "$1" 2>/dev/null)" || return 0
  [ -n "$d" ] && [ -f "$d/shop/main.py" ] || return 0
  [ "$d" = "/" ] && return 0
  for x in "${DIRS[@]:-}"; do [ "$x" = "$d" ] && return 0; done
  DIRS+=("$d")
}
if [ -f /usr/local/bin/bot ]; then
  add_dir "$(grep -m1 '^ROOT=' /usr/local/bin/bot | cut -d'"' -f2)"
fi
while IFS= read -r f; do
  add_dir "$(dirname "$(dirname "$f")")"
done < <(find /root /home /opt /srv /var/www -maxdepth 5 -path '*/shop/main.py' \
           -not -path '*/.venv/*' -not -path '*/site-packages/*' 2>/dev/null)

UNITS=()
for f in /etc/systemd/system/*.service /lib/systemd/system/*.service; do
  [ -f "$f" ] || continue
  if grep -qE 'shop\.main|nickapi\.server' "$f" 2>/dev/null; then
    UNITS+=("$(basename "$f")")
  fi
done

PIDS="$(pgrep -f 'shop\.main|nickapi\.server' 2>/dev/null | tr '\n' ' ')"
ARCHIVES="$(ls -1 /root/almaz-backup-*.tar.gz /home/*/almaz-backup-*.tar.gz 2>/dev/null)"

if [ "${#DIRS[@]}" -eq 0 ] && [ "${#UNITS[@]}" -eq 0 ] && [ -z "$PIDS" ] \
   && [ -z "$ARCHIVES" ] && [ ! -f /usr/local/bin/bot ]; then
  ok "От бота на этом сервере ничего не осталось."
  exit 0
fi

echo
say "Будет УДАЛЕНО безвозвратно:"
for d in "${DIRS[@]:-}"; do
  [ -n "$d" ] || continue
  if git -C "$d" remote get-url origin 2>/dev/null | grep -q "$REPO_HINT"; then
    echo "   📁 папка целиком: $d"
  else
    echo "   📁 из $d: .env, data/ (база), .venv  — остальные файлы папки не трогаю"
  fi
done
for u in "${UNITS[@]:-}"; do [ -n "$u" ] && echo "   ⚙️  служба: $u"; done
[ -n "$PIDS" ] && echo "   ⏹  запущенные процессы бота: $PIDS"
for a in $ARCHIVES; do echo "   🗜  архив: $a"; done
[ -f /usr/local/bin/bot ] && echo "   🔧 команда: /usr/local/bin/bot"
echo
warn "Перед этим убедитесь, что бот работает на НОВОМ сервере ($NEW_IP)."

if [ "$DRY" != "1" ]; then
  printf 'Удалить всё это? Напишите  да  и нажмите Enter: '
  read -r ANSWER
  if [ "$ANSWER" != "да" ] && [ "$ANSWER" != "Да" ] && [ "$ANSWER" != "ДА" ]; then
    warn "Отменено. Ничего не удалено."
    exit 1
  fi
fi

# ── 3. Удаление ───────────────────────────────────────────────────────
echo
for u in "${UNITS[@]:-}"; do
  [ -n "$u" ] || continue
  run systemctl stop "$u" >/dev/null 2>&1
  run systemctl disable "$u" >/dev/null 2>&1
  for f in "/etc/systemd/system/$u" "/lib/systemd/system/$u"; do
    [ -f "$f" ] && run rm -f "$f"
  done
  ok "служба $u удалена"
done
[ "${#UNITS[@]}" -gt 0 ] && run systemctl daemon-reload >/dev/null 2>&1

if [ -n "$PIDS" ]; then
  run kill $PIDS 2>/dev/null
  [ "$DRY" = "1" ] || sleep 3
  LEFT="$(pgrep -f 'shop\.main|nickapi\.server' 2>/dev/null | tr '\n' ' ')"
  [ -n "$LEFT" ] && run kill -9 $LEFT 2>/dev/null
  ok "процессы бота остановлены"
fi

for d in "${DIRS[@]:-}"; do
  [ -n "$d" ] || continue
  if git -C "$d" remote get-url origin 2>/dev/null | grep -q "$REPO_HINT"; then
    run rm -rf "$d"
    ok "папка $d удалена"
  else
    run rm -rf "$d/.env" "$d/data" "$d/.venv"
    ok "из $d удалены .env, база и окружение"
  fi
done

for a in $ARCHIVES; do run rm -f "$a"; done
[ -n "$ARCHIVES" ] && ok "архивы удалены"
run rm -f /usr/local/bin/bot /run/lock/almaz-shop-*.lock /tmp/almaz-shop-*.lock
ok "команда bot удалена"

# ── 4. Проверка ───────────────────────────────────────────────────────
if [ "$DRY" = "1" ]; then
  echo
  warn "Это была проверка — ничего не удалено."
  exit 0
fi
echo
REST="$(find / -xdev \( -name 'shop.sqlite3*' -o -name 'almaz-backup-*.tar.gz' \) 2>/dev/null)"
if [ -n "$REST" ]; then
  warn "Ещё нашлось (удалите вручную, если это от бота):"
  echo "$REST" | sed 's/^/     /'
else
  ok "ГОТОВО. От бота и его базы на этом сервере ничего не осталось."
fi
echo "   Журнал systemd ещё хранит старые записи бота; он очистится сам со временем."
