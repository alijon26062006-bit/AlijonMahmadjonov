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

MODE="${SMARTPAY_MODE:-}"; KEY="${SMARTPAY_KEY:-}"; HTOKEN="${SMARTPAY_HOOK_TOKEN:-}"; HSECRET="${SMARTPAY_HOOK_SECRET:-}"
if [ -z "$MODE" ]; then
  printf 'Режим: 1 — боевой (production), 2 — тест (sandbox) [1]: '; read -r ans < /dev/tty
  [ "$ans" = "2" ] && MODE="sandbox" || MODE="production"
fi
if [ -z "$KEY" ]; then printf 'SmartPay API Key (Танзимот → API Keys), скрыто: '; read -rs KEY < /dev/tty; echo; fi
if [ -z "$HTOKEN" ]; then printf 'Webhook X-Api-Token (64 символа, Танзимот → Webhooks), скрыто: '; read -rs HTOKEN < /dev/tty; echo; fi
if [ -z "$HSECRET" ]; then printf 'Webhook секрет подписи (HMAC, показывался один раз), скрыто: '; read -rs HSECRET < /dev/tty; echo; fi
[ -n "$KEY" ] || die "API Key пустой — ничего не записано."
[ -n "$HTOKEN" ] && [ -n "$HSECRET" ] || die "Без токена и секрета webhook оплата не зачислится — ничего не записано."

sudo -u donatix git -C "$APP_DIR" pull -q --ff-only origin "$BRANCH" || true
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

printf '\nПроверяю ключ в SmartPay… '
if (cd "$APP_DIR" && sudo -u donatix .venv/bin/python -c \
    'from donatix.config import Config; from donatix import smartpay; print("✔ ключ работает, мерчант", smartpay.health(Config.from_env()))'); then :
else printf '\033[1;31m✖ Ключ не принят — проверьте режим (тест/боевой) и ключ, запустите ещё раз.\033[0m\n'; fi

DOMAIN=$(grep -E '^DONATIX_BASE_URL=' "$ENV_FILE" | cut -d= -f2- | sed 's#/*$##'); DOMAIN="${DOMAIN:-https://donatix.tj}"
printf '\n\033[1;32m✔ SmartPay подключён (%s), сайт перезапущен.\033[0m\n' "$MODE"
echo "Дальше:"
echo "  1) Кабинет SmartPay → Танзимот → Webhooks → Target URL:  $DOMAIN/pay/smartpay/webhook"
echo "  2) Cloudflare → Security → WAF → правило Skip для пути /pay/smartpay/webhook (иначе webhook не дойдёт)"
echo "  3) Админка Donatix → Реквизиты и пополнение → способ «SmartPay» → Автозачисление: «SmartPay» → Сохранить"
