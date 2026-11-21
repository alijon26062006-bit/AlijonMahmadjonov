"""Фоновая работа: цены поставщика, отправка заказов, проверка статусов, подарки, возвраты.

Правило денег: возвращаем только когда ТОЧНО известно, что заказ не выполнен. Нет связи с поставщиком —
повторяем тем же Idempotency-Key (второго заказа не будет), а админу пишем, если долго не получается.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timedelta, timezone

from . import db, shop
from .config import Config
from .money import fmt
from .supplier import Supplier, SupplierError, SupplierUnavailable
from .tg import Bot, TgError

log = logging.getLogger(__name__)
ATTENTION_AFTER = 12        # попыток без связи (~1 мин) — сказать админу
GIVE_UP_HOURS = 24          # потом заказ ждёт решения админа (возврат — только вручную)


def _ago(ts: str) -> timedelta:
    return datetime.now(timezone.utc) - datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


class Worker:
    def __init__(self, config: Config, bot: Bot | None, supplier: Supplier | None):
        self.config, self.bot, self.supplier = config, bot, supplier
        self.conn = db.connect(config.db_path)
        self._last_prices = 0.0
        self._last_gifts = 0.0
        self._last_poll = 0.0

    # ── уведомления ──
    def tell(self, user_id: int, text: str, buttons: list | None = None) -> None:
        if self.bot:
            self.bot.safe("sendMessage", chat_id=user_id, text=text, parse_mode="HTML",
                          reply_markup={"inline_keyboard": buttons} if buttons else None)

    def tell_admins(self, text: str) -> None:
        for a in shop.admin_list(self.conn, self.config):
            self.tell(a, text)

    # ── цены ──
    def refresh_prices(self) -> None:
        if not self.supplier:
            return
        try:
            s = self.supplier.stars_info()
            p = self.supplier.premium_plans()
        except (SupplierError, SupplierUnavailable) as exc:
            log.warning("цены: %s", exc)
            return
        db.set_setting(self.conn, "star_usd", str(s["price_per_star"]))
        db.set_setting(self.conn, "star_min", str(s["min"]))
        db.set_setting(self.conn, "star_max", str(s["max"]))
        db.set_setting(self.conn, "premium", json.dumps([{"months": x["months"], "price_usd": str(x["price_usd"])} for x in p]))

    def refresh_gifts(self) -> None:
        if not self.bot:
            return
        try:
            gifts = (self.bot.call("getAvailableGifts") or {}).get("gifts") or []
        except TgError as exc:
            log.warning("подарки: %s", exc)
            return
        def fmt(st: dict) -> str:
            return "tgs" if st.get("is_animated") else "webm" if st.get("is_video") else "webp"
        out = [{"id": g["id"], "stars": int(g.get("star_count") or 0), "emoji": (g.get("sticker") or {}).get("emoji", ""),
                "file": (g.get("sticker") or {}).get("file_id", ""), "fmt": fmt(g.get("sticker") or {})}
               for g in gifts if g.get("id") and g.get("star_count") and not g.get("remaining_count") == 0]
        db.set_setting(self.conn, "gifts", json.dumps(sorted(out, key=lambda g: g["stars"])[:24]))

    # ── заказы поставщику ──
    def send_new(self) -> None:
        rows = self.conn.execute("SELECT * FROM orders WHERE status IN ('new', 'attention') AND kind IN ('stars', 'premium') "
                                 "ORDER BY id LIMIT 20").fetchall()
        for o in rows:
            if o["status"] == "attention" and o["tries"] % 12:   # «зависшие» — раз в минуту
                self.conn.execute("UPDATE orders SET tries = tries + 1 WHERE id = ?", (o["id"],))
                continue
            self._send(o)

    def _send(self, o) -> None:
        if not self.supplier:
            return
        idem = f"sitora-{o['id']}"
        try:
            if o["kind"] == "stars":
                r = self.supplier.buy_stars(o["recipient"], o["qty"], idem)
            else:
                r = self.supplier.buy_premium(o["recipient"], o["months"], idem)
        except SupplierError as exc:   # отказ — заказа точно нет, деньги назад
            if shop.refund(self.conn, o["id"], str(exc)):
                self.tell(o["user_id"], f"❌ Заказ № {o['id']} не выполнен: {exc}\nДеньги ({fmt(o['price'])} с.) вернулись на баланс.")
            return
        except SupplierUnavailable as exc:
            tries = o["tries"] + 1
            status = "attention" if tries >= ATTENTION_AFTER else "new"
            self.conn.execute("UPDATE orders SET tries = ?, status = ?, error = ?, updated_at = ? WHERE id = ?",
                              (tries, status, str(exc)[:300], db.now(), o["id"]))
            if tries == ATTENTION_AFTER:
                self.tell_admins(f"⚠️ Заказ № {o['id']} ({o['title']} → @{o['recipient']}): нет связи с поставщиком. "
                                 "Повторяю тем же ключом — второго заказа не будет.")
            return
        status = {"completed": "completed", "failed": "failed"}.get(r.status, "processing")
        self.conn.execute("UPDATE orders SET supplier_order_id = ?, status = ?, error = '', updated_at = ? WHERE id = ?",
                          (r.id, "processing" if status == "failed" else status, db.now(), o["id"]))
        if status == "completed":
            self._done(o)
        elif status == "failed":
            self._fail(o, r.message or r.raw)

    def poll(self) -> None:
        if not self.supplier:
            return
        for o in self.conn.execute("SELECT * FROM orders WHERE status = 'processing' AND supplier_order_id IS NOT NULL "
                                   "ORDER BY id LIMIT 30").fetchall():
            try:
                r = self.supplier.get_order(o["supplier_order_id"])
            except (SupplierError, SupplierUnavailable) as exc:
                log.info("статус %s: %s", o["id"], exc)
                continue
            if r.status == "completed":
                self.conn.execute("UPDATE orders SET status = 'completed', updated_at = ? WHERE id = ?", (db.now(), o["id"]))
                self._done(o)
            elif r.status == "failed":
                self._fail(o, r.message or r.raw)

    def _done(self, o) -> None:
        self.tell(o["user_id"], f"✅ Заказ № {o['id']} выполнен: {o['title']} → @{o['recipient']}\n"
                                f"Фармоиш иҷро шуд.")

    def _fail(self, o, why: str) -> None:
        if shop.refund(self.conn, o["id"], why or "поставщик отказал"):
            self.tell(o["user_id"], f"❌ Заказ № {o['id']} не выполнен. Деньги ({fmt(o['price'])} с.) вернулись на баланс.\n"
                                    "Маблағ ба баланс баргашт.")

    # ── подарки ──
    def send_gifts(self) -> None:
        if not self.bot:
            return
        for o in self.conn.execute("SELECT * FROM orders WHERE kind = 'gift' AND status = 'paid' ORDER BY id LIMIT 10").fetchall():
            took = self.conn.execute("UPDATE orders SET status = 'sending', updated_at = ? WHERE id = ? AND status = 'paid'",
                                     (db.now(), o["id"])).rowcount
            if not took:
                continue
            try:
                self.bot.call("sendGift", user_id=o["recipient_id"], gift_id=o["gift_id"], text=o["gift_text"] or None)
            except TgError as exc:
                if 400 <= exc.code < 500:   # Telegram отказал — подарка нет, деньги назад
                    if shop.refund(self.conn, o["id"], str(exc)):
                        self.tell(o["user_id"], f"❌ Подарок № {o['id']} не отправлен. Деньги вернулись на баланс.")
                    self.tell_admins(f"⚠️ Подарок № {o['id']} не ушёл: {exc}. Проверьте баланс Stars бота (/fundgifts).")
                else:   # сеть: дошло ли — неизвестно; вслепую не повторяем
                    self.conn.execute("UPDATE orders SET status = 'attention', error = ?, updated_at = ? WHERE id = ?",
                                      (str(exc)[:300], db.now(), o["id"]))
                    self.tell_admins(f"⚠️ Подарок № {o['id']}: нет ответа от Telegram — проверьте вручную.")
                continue
            self.conn.execute("UPDATE orders SET status = 'sent', updated_at = ? WHERE id = ?", (db.now(), o["id"]))
            self.tell(o["user_id"], f"🎁 Подарок № {o['id']} отправлен. / Тӯҳфа фиристода шуд.")

    def expire_gifts(self) -> None:
        for o in self.conn.execute("SELECT * FROM orders WHERE status = 'awaiting_recipient'").fetchall():
            if _ago(o["created_at"]) > timedelta(hours=shop.GIFT_RECIPIENT_HOURS):
                if shop.refund(self.conn, o["id"], "получатель не открыл ссылку"):
                    self.tell(o["user_id"], f"⌛ Подарок № {o['id']}: получатель не открыл ссылку за "
                                            f"{shop.GIFT_RECIPIENT_HOURS} ч. Деньги вернулись на баланс.")

    def tick(self) -> None:
        now = time.time()
        if now - self._last_prices > 600:
            self._last_prices = now
            self.refresh_prices()
        if now - self._last_gifts > 6 * 3600:
            self._last_gifts = now
            self.refresh_gifts()
        self.send_new()
        self.send_gifts()
        if now - self._last_poll > 20:
            self._last_poll = now
            self.poll()
            self.expire_gifts()

    def run(self, stop: threading.Event) -> None:
        while not stop.is_set():
            try:
                self.tick()
            except Exception:  # noqa: BLE001 — воркер не должен падать
                log.exception("воркер")
            stop.wait(5)
