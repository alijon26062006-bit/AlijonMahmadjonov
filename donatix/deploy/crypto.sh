#!/usr/bin/env bash
# Ключи автоплатежей криптой (Binance Pay; TronGrid — необязательно). Секрет вводится скрыто.
#
#   curl -fsSL https://raw.githubusercontent.com/alijon26062006-bit/AlijonMahmadjonov/claude/website-api-sales-96wxcs/donatix/deploy/crypto.sh | sudo bash
set -euo pipefail
APP_DIR="/home/donatix/app"; ENV_FILE="$APP_DIR/donatix/.env"; BRANCH="${DONATIX_BRANCH:-claude/website-api-sales-96wxcs}"
die() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }
[ "$(id -u)" = 0 ] || die "Запустите через sudo."
[ -f "$ENV_FILE" ] || die "Donatix не найден."

BKEY="${BINANCE_PAY_KEY:-}"; BSECRET="${BINANCE_PAY_SECRET:-}"; TKEY="${TRONGRID_KEY:-}"
if [ -z "$BKEY" ]; then printf 'Binance Pay API Key (пусто — пропустить): '; read -r BKEY < /dev/tty; fi
if [ -n "$BKEY" ] && [ -z "$BSECRET" ]; then printf 'Binance Pay Secret Key (скрыто): '; read -rs BSECRET < /dev/tty; echo; fi
if [ -z "$TKEY" ]; then printf 'TronGrid API key (необязательно, Enter — пропустить): '; read -r TKEY < /dev/tty; fi

sudo -u donatix git -C "$APP_DIR" pull -q --ff-only origin "$BRANCH" || true
cp "$ENV_FILE" "$ENV_FILE.bak.$(date +%s)"
BKEY="$BKEY" BSECRET="$BSECRET" TKEY="$TKEY" python3 - "$ENV_FILE" <<'PY'
import os, re, sys
path = sys.argv[1]; s = open(path, encoding="utf-8").read()
for key, env in (("DONATIX_BINANCE_PAY_KEY", "BKEY"), ("DONATIX_BINANCE_PAY_SECRET", "BSECRET"), ("DONATIX_TRONGRID_KEY", "TKEY")):
    value = os.environ[env].strip()
    if not value:
        continue
    line = f"{key}={value}"
    s = re.sub(rf"^{key}=.*$", lambda m: line, s, flags=re.M) if re.search(rf"^{key}=", s, re.M) else s.rstrip("\n") + "\n" + line + "\n"
open(path, "w", encoding="utf-8").write(s)
PY
chown donatix:donatix "$ENV_FILE"; chmod 600 "$ENV_FILE"
systemctl restart donatix
printf '\033[1;32m✔ Ключи записаны, сайт перезапущен.\033[0m\n'
echo "Дальше: админка → Реквизиты → у способа выберите «Автозачисление» и сохраните."
