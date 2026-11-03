#!/usr/bin/env bash
# SmartPay — оплата из любого банка Таджикистана, баланс пополняется сам. Ключи вводятся скрыто и пишутся
# только в .env сервера. В конце — проверка ключа (GET /health) и адрес webhook для кабинета SmartPay.
#
#   curl -fsSL https://raw.githubusercontent.com/alijon26062006-bit/AlijonMahmadjonov/claude/website-api-sales-96wxcs/donatix/deploy/smartpay.sh | sudo bash
set -euo pipefail
APP_DIR="/home/donatix/app"; ENV_FILE="$APP_DIR/donatix/.env"; BRANCH="${DONATIX_BRANCH:-claude/website-api-sales-96wxcs}"
die() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }
[ "$(id -u)" = 0 ] || die "Запустите через sudo."
[ -f "$ENV_FILE" ] || die "Donatix не найден."

MODE="${SMARTPAY_MODE:-production}"; KEY="${SMARTPAY_KEY:-}"; HTOKEN="${SMARTPAY_HOOK_TOKEN:-}"; HSECRET="${SMARTPAY_HOOK_SECRET:-}"
printf '\n\033[1mПодключаю SmartPay (оплата из любого банка). Ввод скрытый — символы не видны, это нормально.\033[0m\n'
if [ -z "$KEY" ]; then
  printf '\nШаг 1 из 2 — API Key (кабинет SmartPay → Танзимот → API Keys): '; read -rs KEY < /dev/tty; echo
fi
if [ -z "$HTOKEN" ] || [ -z "$HSECRET" ]; then
  printf '\nШаг 2 из 2 — Webhook (Танзимот → Webhooks, адрес https://donatix.tj/pay/smartpay/webhook)\n'
  [ -n "$HTOKEN" ] || { printf '  X-Api-Token (из поля Headers, без кавычек): '; read -rs HTOKEN < /dev/tty; echo; }
  [ -n "$HSECRET" ] || { printf '  Секрет подписи HMAC (показывался один раз): '; read -rs HSECRET < /dev/tty; echo; }
fi
HTOKEN=$(printf '%s' "$HTOKEN" | tr -d '" '); KEY=$(printf '%s' "$KEY" | tr -d '" '); HSECRET=$(printf '%s' "$HSECRET" | tr -d '" ')
[ -n "$KEY" ] || die "API Key пустой — ничего не записано."
[ -n "$HTOKEN" ] && [ -n "$HSECRET" ] || die "Без токена и секрета webhook оплата не зачислится — ничего не записано."

sudo -u donatix git -C "$APP_DIR" pull -q --ff-only origin "$BRANCH" || true

# Ключ проверяем ДО записи: сначала в выбранном режиме, потом в другом (тестовый ключ к боевому адресу не подходит)
check() {   # $1 — режим; печатает UUID мерчанта или причину
  (cd "$APP_DIR" && DONATIX_SMARTPAY_KEY="$KEY" DONATIX_SMARTPAY_MODE="$1" \
    sudo --preserve-env=DONATIX_SMARTPAY_KEY,DONATIX_SMARTPAY_MODE -u donatix .venv/bin/python -c '
import logging; logging.disable(logging.CRITICAL)
from donatix.config import Config; from donatix import smartpay
try: print("OK", smartpay.health(Config.from_env()))
except Exception as e: print("ERR", e)' 2>/dev/null)
}
printf '\nПроверяю ключ в SmartPay… '
OTHER=$([ "$MODE" = sandbox ] && echo production || echo sandbox)
RES=$(check "$MODE")
if [ "${RES%% *}" != OK ]; then
  RES2=$(check "$OTHER")
  if [ "${RES2%% *}" = OK ]; then
    printf '\n  ключ от режима «%s», а не «%s» — использую «%s».\n' "$OTHER" "$MODE" "$OTHER"; MODE="$OTHER"; RES="$RES2"
  else
    die "Ключ не принят SmartPay ни в боевом, ни в тестовом режиме (Invalid API key). Скопируйте API Key заново (Танзимот → API Keys — именно API Key, не токен webhook) и запустите ещё раз. Ничего не записано."
  fi
fi
printf '\033[1;32m✔ ключ работает (%s), мерчант %s\033[0m\n' "$MODE" "${RES#OK }"

cp "$ENV_FILE" "$ENV_FILE.bak.$(date +%s)"
MODE="$MODE" KEY="$KEY" HTOKEN="$HTOKEN" HSECRET="$HSECRET" python3 - "$ENV_FILE" <<'PY'
import os, re, sys
path = sys.argv[1]; s = open(path, encoding="utf-8").read()
for key, env in (("DONATIX_SMARTPAY_MODE", "MODE"), ("DONATIX_SMARTPAY_KEY", "KEY"),
                 ("DONATIX_SMARTPAY_HOOK_TOKEN", "HTOKEN"), ("DONATIX_SMARTPAY_HOOK_SECRET", "HSECRET")):
    line = f"{key}={os.environ[env].strip()}"
    s = re.sub(rf"^{key}=.*$", lambda m: line, s, flags=re.M) if re.search(rf"^{key}=", s, re.M) else s.rstrip("\n") + "\n" + line + "\n"
open(path, "w", encoding="utf-8").write(s)
PY
chown donatix:donatix "$ENV_FILE"; chmod 600 "$ENV_FILE"
systemctl restart donatix

DOMAIN=$(grep -E '^DONATIX_BASE_URL=' "$ENV_FILE" | cut -d= -f2- | sed 's#/*$##'); DOMAIN="${DOMAIN:-https://donatix.tj}"
printf '\n\033[1;32m✔ SmartPay подключён (%s), сайт перезапущен.\033[0m\n' "$MODE"
echo "Дальше:"
echo "  1) Кабинет SmartPay → Танзимот → Webhooks → Target URL:  $DOMAIN/pay/smartpay/webhook"
echo "  2) Cloudflare → Security → WAF → правило Skip для пути /pay/smartpay/webhook (иначе webhook не дойдёт)"
echo "  3) Админка Donatix → Реквизиты и пополнение → способ «SmartPay» → Автозачисление: «SmartPay» → Сохранить"
