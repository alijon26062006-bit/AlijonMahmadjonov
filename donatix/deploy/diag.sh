#!/usr/bin/env bash
# Проверка: уведомления покупателям и график D-коина. Ничего не меняет — только показывает.
#   sudo bash /home/donatix/app/donatix/deploy/diag.sh
APP=/home/donatix/app
cd "$APP" || exit 1
echo "== Версия: $(sudo -u donatix git log --oneline -1)"
echo "== Ошибки за 3 часа (уведомления, бот):"
journalctl -u donatix --since "3 hours ago" --no-pager 2>/dev/null \
  | grep -iE "уведомл|бот-магазин|buyer|tgnotify|Traceback|Error" | tail -15
echo "== База:"
sudo -u donatix "$APP/.venv/bin/python" - <<'PY'
import os, sqlite3
db = os.environ.get("DONATIX_DB") or "/home/donatix/app/donatix/data/donatix.db"
for line in open("/home/donatix/app/donatix/.env", encoding="utf-8"):
    if line.startswith("DONATIX_DB="):
        db = line.split("=", 1)[1].strip().strip('"')
c = sqlite3.connect(db)
def q(sql, *a):
    try:
        return c.execute(sql, a).fetchall()
    except Exception as e:
        return [("нет:", str(e))]
env = open("/home/donatix/app/donatix/.env", encoding="utf-8").read()
print("бот-магазин токен:", "есть" if "DONATIX_SHOP_BOT_TOKEN=" in env and "DONATIX_SHOP_BOT_TOKEN=\n" not in env else "НЕТ")
print("уведомления с:", q("SELECT value FROM settings WHERE key = 'buyer_notify.since'"))
print("отправлено за сутки:", q("SELECT kind, COUNT(*), MAX(at) FROM buyer_notified WHERE at >= datetime('now','-1 day') GROUP BY kind"))
print("ждут в боте:", q("SELECT kind, COUNT(*) FROM shop_watch GROUP BY kind"))
print("ждут в мини-прил.:", q("SELECT kind, COUNT(*) FROM tgapp_watch GROUP BY kind"))
print("последние заказы (id, статус, источник, с Telegram, сообщили):")
for r in q("SELECT o.id, o.status, o.source, EXISTS(SELECT 1 FROM shop_users s WHERE s.user_id = o.user_id), "
           "EXISTS(SELECT 1 FROM buyer_notified b WHERE b.kind='order' AND b.obj_id=o.id) "
           "FROM orders o ORDER BY o.id DESC LIMIT 6"):
    print("  ", r)
print("последние пополнения (id, статус, с Telegram, сообщили):")
for r in q("SELECT p.id, p.status, EXISTS(SELECT 1 FROM shop_users s WHERE s.user_id = p.user_id), "
           "EXISTS(SELECT 1 FROM buyer_notified b WHERE b.kind='pay' AND b.obj_id=p.id) "
           "FROM payments p ORDER BY p.id DESC LIMIT 6"):
    print("  ", r)
print("D-коин настройки (за $1, % в копилку):", q("SELECT key, value FROM settings WHERE key IN ('dcoin.per_usd', 'dcoin.pool_pct')"))
print("D-коин последние точки (время, копилка $, монеты, запас, цена $, причина):")
for r in q("SELECT ts, pool/10000.0, supply/100, reserve/100, price, reason FROM dcoin_points ORDER BY id DESC LIMIT 8"):
    print("  ", r)
PY
