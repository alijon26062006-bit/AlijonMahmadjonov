#!/usr/bin/env bash
# Письма с кодом подтверждения почты через Resend (resend.com): бесплатно 3000 в месяц.
#
#   sudo bash /home/donatix/app/donatix/deploy/resend.sh 're_ВАШ_КЛЮЧ' 'ваша@почта для пробного письма'
#
# Перед этим в Resend: Domains → donatix.tj → статус Verified; API Keys → ключ с правом «Sending access».
# Скрипт отправляет пробное письмо с кодом и только если Resend его принял — пишет ключ в donatix/.env
# (в репозиторий ключ не попадает). Отправитель по умолчанию: Donatix <noreply@donatix.tj>,
# свой — третьим аргументом: 'Donatix <info@donatix.tj>'.
set -euo pipefail
APP_DIR="/home/donatix/app"; ENV_FILE="$APP_DIR/donatix/.env"; BRANCH="${DONATIX_BRANCH:-claude/website-api-sales-96wxcs}"
die() { printf '\n\033[1;31m✖ %s\033[0m\n' "$*"; exit 1; }
ok() { printf '\033[1;32m✔ %s\033[0m\n' "$*"; }
[ "$(id -u)" = 0 ] || die "Запустите через sudo."
[ -f "$ENV_FILE" ] || die "Donatix не найден ($ENV_FILE)."

KEY="${1:-}"; TO="${2:-}"; FROM="${3:-Donatix <noreply@donatix.tj>}"
[[ "$KEY" =~ ^re_[A-Za-z0-9_]{20,}$ ]] || die "Первый — ключ Resend (начинается с re_)."
[[ "$TO" == *@*.* ]] || die "Второй — ваша почта: на неё придёт пробное письмо."

RES=$(KEY="$KEY" TO="$TO" FROM="$FROM" python3 - <<'PY'
import json, os, urllib.error, urllib.request
body = json.dumps({"from": os.environ["FROM"], "to": [os.environ["TO"]],
                   "subject": "123456 — проверка Donatix",
                   "text": "Пробное письмо: сайт теперь отправляет коды подтверждения почты. Код для примера: 123456",
                   "html": "<p>Пробное письмо: сайт теперь отправляет коды подтверждения почты.</p>"
                           "<p style='font-size:28px;font-weight:800;letter-spacing:6px'>123456</p>"}).encode()
req = urllib.request.Request("https://api.resend.com/emails", data=body, method="POST", headers={
    "Authorization": f"Bearer {os.environ['KEY']}", "Content-Type": "application/json", "User-Agent": "donatix-setup"})
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        print("OK " + json.load(r).get("id", ""))
except urllib.error.HTTPError as e:
    print(f"ERR {e.code} {e.read().decode(errors='replace')[:300]}")
except Exception as e:  # noqa: BLE001
    print(f"ERR сеть: {e}")
PY
)
case "$RES" in
  OK*) ok "Resend принял пробное письмо — проверьте ящик $TO" ;;
  *"403"*|*"domain"*|*"verify"*) die "Resend отказал: $RES
  Скорее всего домен ещё не подтверждён: Resend → Domains → donatix.tj должен быть Verified.
  Или адрес отправителя не на подтверждённом домене (нужен @donatix.tj)." ;;
  *"401"*) die "Ключ не подошёл (401) — скопируйте его заново или создайте новый в Resend → API Keys." ;;
  *) die "Письмо не ушло: $RES" ;;
esac

sudo -u donatix git -C "$APP_DIR" pull -q --ff-only origin "$BRANCH" || true
cp "$ENV_FILE" "$ENV_FILE.bak.$(date +%s)"
KEY="$KEY" FROM="$FROM" python3 - "$ENV_FILE" <<'PY'
import os, re, sys
path = sys.argv[1]; s = open(path, encoding="utf-8").read()
for key, val in (("DONATIX_RESEND_KEY", os.environ["KEY"]), ("DONATIX_MAIL_FROM", os.environ["FROM"])):
    line = f"{key}={val}"
    s = re.sub(rf"^{key}=.*$", lambda m: line, s, flags=re.M) if re.search(rf"^{key}=", s, re.M) else s.rstrip("\n") + "\n" + line + "\n"
open(path, "w", encoding="utf-8").write(s)
PY
chown donatix:donatix "$ENV_FILE"; chmod 600 "$ENV_FILE"
ok "Ключ записан в .env"
systemctl restart donatix
sleep 4
[ "$(systemctl is-active donatix)" = "active" ] || die "Сайт не запустился: journalctl -u donatix -n 40 --no-pager"
ok "Готово. Теперь каждый новый клиент получает на почту код из 6 цифр и вводит его на сайте."
