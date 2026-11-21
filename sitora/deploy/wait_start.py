"""Ждёт, пока владелец нажмёт /start в боте, и печатает его Telegram ID (только stdlib).

Токен берётся из переменной окружения TG_TOKEN (не из аргументов — их видно в списке процессов).
В stdout — только ID; подсказки — в stderr.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

TOKEN = os.environ.get("TG_TOKEN", "")
API = os.environ.get("TG_API", "https://api.telegram.org") + f"/bot{TOKEN}/"


def call(method, wait=15, **params):
    req = urllib.request.Request(API + method, data=json.dumps(params).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=wait) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return json.load(e)
        except Exception:  # noqa: BLE001
            return {"ok": False, "description": f"HTTP {e.code}"}


def say(*a):
    print(*a, file=sys.stderr, flush=True)


def main():
    me = call("getMe")
    if not me.get("ok"):
        say("❌ Токен не подходит:", me.get("description", "нет ответа от Telegram"))
        sys.exit(2)
    user = me["result"]["username"]
    call("deleteWebhook")
    # старые сообщения пропускаем — ждём только новое нажатие
    old = call("getUpdates", offset=-1).get("result") or []
    offset = old[-1]["update_id"] + 1 if old else 0
    say(f"\n✅ Бот найден: @{user}")
    say(f"👉 Откройте в Telegram  https://t.me/{user}  и нажмите «СТАРТ» (или отправьте /start).")
    say("   Жду… (до 15 минут)")
    end = time.time() + 15 * 60
    while time.time() < end:
        r = call("getUpdates", wait=60, offset=offset, timeout=50, allowed_updates=["message"])
        for u in r.get("result") or []:
            offset = u["update_id"] + 1
            m = u.get("message") or {}
            if (m.get("chat") or {}).get("type") == "private" and (m.get("text") or "").startswith("/start"):
                uid = m["from"]["id"]
                call("getUpdates", offset=offset)  # отметить прочитанным
                call("sendMessage", chat_id=uid,
                     text="✅ Вы — администратор. Через минуту бот заработает: нажмите /start ещё раз, потом /admin.")
                say(f"✅ Ваш ID: {uid} — записан как администратор.")
                print(uid)
                return
        if not r.get("ok"):
            time.sleep(3)
    say("❌ Не дождался /start. Запустите установку ещё раз.")
    sys.exit(3)


if __name__ == "__main__":
    main()
