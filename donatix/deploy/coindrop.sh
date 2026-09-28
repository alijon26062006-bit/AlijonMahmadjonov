#!/usr/bin/env bash
# Второй поставщик CoinDrop (Standoff 2 и другие игры по ID). Ключ вводится скрыто и пишется только в .env.
# Игры по желанию можно ограничить списком: COINDROP_GAMES="standoff-2,pubg-mobile"
#
#   curl -fsSL https://raw.githubusercontent.com/alijon26062006-bit/AlijonMahmadjonov/claude/website-api-sales-96wxcs/donatix/deploy/coindrop.sh | sudo bash
set -euo pipefail
APP_DIR="/home/donatix/app"; ENV_FILE="$APP_DIR/donatix/.env"; BRANCH="${DONATIX_BRANCH:-claude/website-api-sales-96wxcs}"
die() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }
[ "$(id -u)" = 0 ] || die "Запустите через sudo."
[ -f "$ENV_FILE" ] || die "Donatix не найден."

KEY="${COINDROP_KEY:-}"; GAMES="${COINDROP_GAMES:-}"
if [ -z "$KEY" ]; then printf 'API-ключ CoinDrop (cd_…, скрыто): '; read -rs KEY < /dev/tty; echo; fi
[[ "$KEY" == cd_* ]] || die "Ключ CoinDrop должен начинаться с cd_"

sudo -u donatix git -C "$APP_DIR" pull -q --ff-only origin "$BRANCH" || true
cp "$ENV_FILE" "$ENV_FILE.bak.$(date +%s)"
KEY="$KEY" GAMES="$GAMES" python3 - "$ENV_FILE" <<'PY'
import os, re, sys
path = sys.argv[1]; s = open(path, encoding="utf-8").read()
for key, env in (("DONATIX_COINDROP_API_KEY", "KEY"), ("DONATIX_COINDROP_GAMES", "GAMES")):
    value = os.environ[env].strip()
    if env == "GAMES" and not value and not re.search(r"^DONATIX_COINDROP_GAMES=", s, re.M):
        continue
    line = f"{key}={value}"
    s = re.sub(rf"^{key}=.*$", lambda m: line, s, flags=re.M) if re.search(rf"^{key}=", s, re.M) else s.rstrip("\n") + "\n" + line + "\n"
open(path, "w", encoding="utf-8").write(s)
PY
chown donatix:donatix "$ENV_FILE"; chmod 600 "$ENV_FILE"

# Проверка ключа до перезапуска: живой ли баланс
echo "Проверяю ключ у CoinDrop…"
HTTP=$(curl -s -o /tmp/cd.json -w '%{http_code}' -H "X-API-Key: $KEY" https://coindrop.uz/api/v1/balance || echo 000)
if [ "$HTTP" = "200" ]; then echo "✔ Ключ работает. Баланс: $(cat /tmp/cd.json)"; else
  echo "⚠ CoinDrop ответил HTTP $HTTP: $(head -c 200 /tmp/cd.json). Ключ всё равно сохранён — проверьте в профиле CoinDrop, включён ли API."; fi
rm -f /tmp/cd.json
systemctl restart donatix; sleep 4
printf '\033[1;32m✔ CoinDrop подключён.\033[0m\n'
echo "1) В админке → «Загрузка каталога» нажмите обновить — появятся игры CoinDrop (Standoff 2 и др.)."
echo "2) Баланс CoinDrop виден в админке на «Сводке» отдельной карточкой."
echo "3) Пополните баланс CoinDrop в их кабинете — иначе заказы будут возвращаться клиентам."
