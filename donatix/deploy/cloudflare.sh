#!/usr/bin/env bash
# Cloudflare из терминала: убрать проверку «я не робот» (защита от DDoS остаётся) или включить её на время атаки.
#
#   sudo bash /home/donatix/app/donatix/deploy/cloudflare.sh status   — что сейчас включено
#   sudo bash /home/donatix/app/donatix/deploy/cloudflare.sh off      — убрать проверку для клиентов
#   sudo bash /home/donatix/app/donatix/deploy/cloudflare.sh attack   — идёт атака: включить «Под атакой»
#   sudo bash /home/donatix/app/donatix/deploy/cloudflare.sh calm     — атака закончилась: снова без проверки
#
# Нужен API-токен Cloudflare (создаётся один раз, см. ниже). Токен вводится скрытно и НИКУДА не сохраняется,
# если не ответить «да» на вопрос о сохранении (тогда — в /root/.cloudflare-token, доступ только root).
# Права токена: Zone → Zone → Read; Zone → Zone Settings → Edit; Zone → Zone WAF → Edit; Zone → Bot Management → Edit.
set -euo pipefail
DOMAIN="${CF_DOMAIN:-donatix.tj}"
TOKEN_FILE=/root/.cloudflare-token
ACTION="${1:-status}"

if [ -r "$TOKEN_FILE" ]; then
  CF_TOKEN=$(cat "$TOKEN_FILE")
else
  echo "Нужен API-токен Cloudflare: dash.cloudflare.com → My Profile → API Tokens → Create Token → Custom token."
  echo "Права: Zone/Zone/Read · Zone/Zone Settings/Edit · Zone/Zone WAF/Edit · Zone/Bot Management/Edit; Zone Resources: $DOMAIN"
  read -rsp "Вставьте токен (на экране не видно) и нажмите Enter: " CF_TOKEN; echo
  read -rp "Сохранить токен на сервере, чтобы не вводить снова? (да/нет): " SAVE
  if [ "$SAVE" = "да" ] || [ "$SAVE" = "y" ]; then
    umask 077; printf '%s' "$CF_TOKEN" > "$TOKEN_FILE"; echo "  сохранён в $TOKEN_FILE (только для root)"
  fi
fi
export CF_TOKEN DOMAIN ACTION

python3 - <<'PY'
import json, os, sys, urllib.request, urllib.error

TOKEN, DOMAIN, ACTION = os.environ["CF_TOKEN"].strip(), os.environ["DOMAIN"], os.environ["ACTION"]
API = "https://api.cloudflare.com/client/v4"
CHALLENGE = {"challenge", "js_challenge", "managed_challenge"}


def call(method, path, body=None, quiet=False):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        data = json.loads(e.read() or b"{}")
        if not quiet:
            msg = "; ".join(x.get("message", "") for x in data.get("errors", [])) or str(e)
            print(f"  ⚠️  {method} {path.split('/')[-1]}: {msg}")
        return data


zones = call("GET", f"/zones?name={DOMAIN}")
if not zones.get("success") or not zones.get("result"):
    sys.exit(f"❌ Домен {DOMAIN} не найден или токен неверный/без прав «Zone Read».")
zid = zones["result"][0]["id"]


def setting(name):
    return (call("GET", f"/zones/{zid}/settings/{name}", quiet=True).get("result") or {}).get("value")


def set_level(value):
    r = call("PATCH", f"/zones/{zid}/settings/security_level", {"value": value})
    print(("  ✅" if r.get("success") else "  ❌") + f" уровень защиты → {value}")


def bots(fight):
    r = call("PUT", f"/zones/{zid}/bot_management", {"fight_mode": fight}, quiet=True)
    if r.get("success"):
        print(f"  ✅ Bot Fight Mode → {'вкл' if fight else 'выкл'}")
    else:
        print("  ⚠️  Bot Fight Mode не удалось поменять (нет права «Bot Management → Edit»?) — выключите вручную: Security → Bots")


def custom_rules(disable):
    entry = call("GET", f"/zones/{zid}/rulesets/phases/http_request_firewall_custom/entrypoint", quiet=True)
    rs = entry.get("result") or {}
    found = [r for r in rs.get("rules", []) if r.get("action") in CHALLENGE]
    for r in found:
        name = r.get("description") or r.get("expression", "")[:60]
        if not disable:
            print(f"     • {'вкл ' if r.get('enabled', True) else 'выкл'} «{name}» → {r['action']}")
            continue
        if not r.get("enabled", True):
            continue
        body = {k: r[k] for k in ("action", "expression", "description", "action_parameters") if k in r}
        body["enabled"] = False
        res = call("PATCH", f"/zones/{zid}/rulesets/{rs['id']}/rules/{r['id']}", body)
        print(("  ✅ выключено" if res.get("success") else "  ❌ не выключено") + f" правило «{name}» ({r['action']})")
    return found


def status():
    print(f"Cloudflare · {DOMAIN}")
    print(f"  уровень защиты: {setting('security_level')}   (under_attack = «Под атакой», проверка у всех)")
    bm = (call("GET", f"/zones/{zid}/bot_management", quiet=True).get("result") or {})
    print(f"  Bot Fight Mode: {'вкл' if bm.get('fight_mode') else 'выкл' if bm else 'нет доступа'}")
    print("  свои правила с проверкой «я не робот»:")
    if not custom_rules(False):
        print("     нет")
    print("  защита от DDoS: работает всегда (Cloudflare, отдельно от этих настроек)")


if ACTION == "status":
    status()
elif ACTION in ("off", "calm"):
    print("Убираю проверку «я не робот»…")
    set_level("essentially_off")
    bots(False)
    custom_rules(True)
    print("Готово. Защита от DDoS остаётся включённой. Проверьте сайт с телефона на мобильном интернете.")
elif ACTION == "attack":
    set_level("under_attack")
    print("⚠️  Включён «Под атакой»: всем показывается проверка. Когда атака закончится: … cloudflare.sh calm")
else:
    sys.exit("Команды: status | off | attack | calm")
PY
