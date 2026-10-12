#!/usr/bin/env bash
# Автоплатёж Bybit (перевод по UID и пополнение USDT на ваш адрес Bybit): ключ «только чтение» в .env.
#
#   sudo bash /home/donatix/app/donatix/deploy/bybit.sh 'API_KEY' 'API_SECRET'
#
# Ключ создаётся в Bybit → API → «Создать новый ключ» → «Системный» → «Только для чтения» + IP сервера.
# Скрипт проверяет у самого Bybit, что ключ рабочий и ТОЛЬКО ДЛЯ ЧТЕНИЯ: ключ с правом торговли
# или вывода не ставит. Ключи пишутся только в donatix/.env (не в репозиторий).
set -euo pipefail
APP_DIR="/home/donatix/app"; ENV_FILE="$APP_DIR/donatix/.env"; BRANCH="${DONATIX_BRANCH:-claude/website-api-sales-96wxcs}"
die() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }
ok() { printf '\033[1;32m✔ %s\033[0m\n' "$*"; }
[ "$(id -u)" = 0 ] || die "Запустите через sudo."
[ -f "$ENV_FILE" ] || die "Donatix не найден ($ENV_FILE)."

KEY="${1:-}"; SECRET="${2:-}"
[[ "$KEY" =~ ^[A-Za-z0-9]{10,64}$ ]] || die "Первый — API Key из Bybit (буквы и цифры)."
[[ "$SECRET" =~ ^[A-Za-z0-9]{10,128}$ ]] || die "Второй — API Secret из Bybit (буквы и цифры)."

# Спросить у Bybit сведения о самом ключе: работает ли и какие у него права
INFO=$(KEY="$KEY" SECRET="$SECRET" python3 - <<'PY'
import hashlib, hmac, json, os, socket, time, urllib.request
_orig = socket.getaddrinfo   # только IPv4: ключ привязан к IPv4 сервера
socket.getaddrinfo = lambda host, *a, **k: [x for x in _orig(host, *a, **k) if x[0] == socket.AF_INET]
key, secret = os.environ["KEY"], os.environ["SECRET"]
ts, window = str(int(time.time() * 1000)), "10000"
sign = hmac.new(secret.encode(), f"{ts}{key}{window}".encode(), hashlib.sha256).hexdigest()
req = urllib.request.Request("https://api.bybit.com/v5/user/query-api", headers={
    "X-BAPI-API-KEY": key, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": window, "X-BAPI-SIGN": sign})
try:
    data = json.load(urllib.request.urlopen(req, timeout=20))
except Exception as exc:  # noqa: BLE001
    print(json.dumps({"err": f"Bybit не ответил: {exc}"})); raise SystemExit
if data.get("retCode") != 0:
    print(json.dumps({"err": data.get("retMsg") or str(data)})); raise SystemExit
r = data.get("result") or {}
print(json.dumps({"readOnly": r.get("readOnly"), "perms": r.get("permissions") or {}, "ips": r.get("ips") or []}))
PY
)
ERR=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("err",""))' "$INFO")
[ -z "$ERR" ] || die "Bybit не принял ключ: $ERR
  Частые причины: скопировали не целиком; IP сервера не в списке доверенных (нужен $(curl -4 -s -m 5 ifconfig.me || echo '?'))."
RO=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("readOnly"))' "$INFO")
[ "$RO" = "1" ] || die "У ключа есть права НЕ только на чтение (торговля/переводы/вывод). Такой ключ опасно держать на сервере.
  Удалите его в Bybit и создайте новый: «Разрешения API» → «Только для чтения»."
ok "Ключ Bybit рабочий и только для чтения"
IPS=$(python3 -c 'import json,sys; print(",".join(json.loads(sys.argv[1]).get("ips") or []))' "$INFO")
[ -n "$IPS" ] && [ "$IPS" != "*" ] && ok "Ключ привязан к IP: $IPS" || echo "  ⚠️ Ключ без привязки к IP — Bybit отключит его через 3 месяца. Лучше привязать к IP сервера."

sudo -u donatix git -C "$APP_DIR" pull -q --ff-only origin "$BRANCH" || true
cp "$ENV_FILE" "$ENV_FILE.bak.$(date +%s)"
KEY="$KEY" SECRET="$SECRET" python3 - "$ENV_FILE" <<'PY'
import os, re, sys
path = sys.argv[1]; s = open(path, encoding="utf-8").read()
for key, env in (("DONATIX_BYBIT_KEY", "KEY"), ("DONATIX_BYBIT_SECRET", "SECRET")):
    line = f"{key}={os.environ[env].strip()}"
    s = re.sub(rf"^{key}=.*$", lambda m: line, s, flags=re.M) if re.search(rf"^{key}=", s, re.M) else s.rstrip("\n") + "\n" + line + "\n"
open(path, "w", encoding="utf-8").write(s)
PY
chown donatix:donatix "$ENV_FILE"; chmod 600 "$ENV_FILE"
ok "Ключ записан в .env"

systemctl restart donatix
sleep 4
[ "$(systemctl is-active donatix)" = "active" ] || die "Сайт не запустился: journalctl -u donatix -n 40 --no-pager"
ok "Готово. Теперь: Админка → «Реквизиты» → способ USDT → Автозачисление «Bybit» → в реквизиты ваш UID Bybit."
