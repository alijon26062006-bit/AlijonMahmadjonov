#!/usr/bin/env bash
# Виртуальные номера (5sim.net) на сайте: одна команда — токен в .env, обновление, перезапуск, проверка.
#
#   sudo bash /home/donatix/app/donatix/deploy/fivesim.sh 'ТОКЕН_5SIM' [наценка_%]
#
# Токен — «API key for 5SIM protocol» (длинный, начинается с eyJ) из кабинета 5sim → API. Пишется только
# в donatix/.env (не в репозиторий). Наценка по умолчанию 25 %. Повторный запуск с новым токеном — заменит старый.
set -euo pipefail
APP_DIR="/home/donatix/app"; ENV_FILE="$APP_DIR/donatix/.env"; BRANCH="${DONATIX_BRANCH:-claude/website-api-sales-96wxcs}"
die() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }
ok() { printf '\033[1;32m✔ %s\033[0m\n' "$*"; }
[ "$(id -u)" = 0 ] || die "Запустите через sudo."
[ -f "$ENV_FILE" ] || die "Donatix не найден ($ENV_FILE)."

TOKEN="${1:-${FIVESIM_TOKEN:-}}"; MARKUP="${2:-25}"
[[ "$TOKEN" =~ ^eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$ ]] || \
  die "Нужен токен 5sim, который начинается с eyJ (кабинет 5sim → API → «API key for 5SIM protocol»)."
[[ "$MARKUP" =~ ^[0-9]{1,3}(\.[0-9]+)?$ ]] || die "Наценка — число процентов, например 25."

code=$(curl -s -m 20 -o /dev/null -w '%{http_code}' -H "Authorization: Bearer $TOKEN" -H "Accept: application/json" \
       https://5sim.net/v1/user/profile || true)
[ "$code" = "200" ] || die "5sim не принял токен (ответ $code). Проверьте, что скопировали его целиком."
ok "Токен 5sim рабочий"

sudo -u donatix git -C "$APP_DIR" pull -q --ff-only origin "$BRANCH" || true
ok "Код сайта обновлён"

cp "$ENV_FILE" "$ENV_FILE.bak.$(date +%s)"
TOKEN="$TOKEN" MARKUP="$MARKUP" python3 - "$ENV_FILE" <<'PY'
import os, re, sys
path = sys.argv[1]; s = open(path, encoding="utf-8").read()
for key, env in (("DONATIX_FIVESIM_TOKEN", "TOKEN"), ("DONATIX_FIVESIM_MARKUP", "MARKUP")):
    line = f"{key}={os.environ[env].strip()}"
    s = re.sub(rf"^{key}=.*$", lambda m: line, s, flags=re.M) if re.search(rf"^{key}=", s, re.M) else s.rstrip("\n") + "\n" + line + "\n"
open(path, "w", encoding="utf-8").write(s)
PY
chown donatix:donatix "$ENV_FILE"; chmod 600 "$ENV_FILE"
ok "Токен записан в .env, наценка $MARKUP %"

systemctl restart donatix
sleep 4
state=$(systemctl is-active donatix)
page=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/ || true)
echo "  сайт: $state, главная $page"
[ "$state" = "active" ] || die "Сайт не запустился: journalctl -u donatix -n 40 --no-pager"
ok "Готово: на главной — «Виртуальные номера», страница: /panel/numbers"
echo "  Баланс 5sim пополните в кабинете 5sim — без него номера не купятся (клиенту деньги вернутся сами)."
