"""Магазин и админ-панель прямо в чате бота (кнопки под сообщением).

Нажатие кнопки меняет то же сообщение — чат не засоряется. Когда нужен ввод (сумма, @username, цена),
бот запоминает шаг в chat_state и ждёт ответ текстом. Кнопки клиента — «c:…», админа — «a:…».
Каждое действие админа проверяет права заново.
"""
from __future__ import annotations

import html
import json
import logging
import threading
import time
from decimal import Decimal, InvalidOperation

from . import db, shop
from .config import Config
from .money import fmt, to_diram
from .tg import Bot, TgError

log = logging.getLogger(__name__)
esc = html.escape
PAGE = 8

TX = {
    "ru": {"hello": "<b>{name}</b> — Stars, Premium и подарки Telegram\n\n💰 Баланс: <b>{bal} с.</b>\nВыберите, что купить 👇",
           "stars": "⭐ Stars", "premium": "💎 Premium", "gifts": "🎁 Подарки", "topup": "💳 Пополнить", "orders": "🧾 Мои заказы",
           "lang": "🌐 Тоҷикӣ", "help": "❓ Помощь", "app": "📱 Мини-приложение", "back": "← Назад", "menu": "🏠 Меню",
           "starsT": "⭐ <b>Telegram Stars</b>\nВыберите пакет или своё количество ({lo}–{hi}).",
           "own": "✍️ Своё количество", "askQty": "Напишите количество звёзд числом ({lo}–{hi}):",
           "premT": "💎 <b>Telegram Premium</b>\nВыберите срок:", "mon": "мес.",
           "giftT": "🎁 <b>Подарки Telegram</b>\nВыберите подарок — получатель увидит его в профиле.",
           "who": "{title} — <b>{price} с.</b>\n\nКому отправить? Напишите @username или нажмите «Себе».",
           "whoGift": "{title} — <b>{price} с.</b>\n\nКому подарить? Напишите @username или нажмите «Себе».",
           "self": "👤 Себе", "noUser": "У вас нет @username в Telegram — напишите @username получателя.",
           "check": "Проверьте заказ:\n{title} → <b>{to}</b>\nЦена: <b>{price} с.</b> · на балансе {bal} с.",
           "pay": "✅ Оплатить с баланса", "cancel": "✖ Отмена",
           "lack": "Не хватает <b>{need} с.</b> — пополните баланс, и заказ оформится сам после проверки чека.",
           "topNeed": "💳 Пополнить на {need} с.",
           "paid": "✅ <b>Заказ № {id} оплачен</b>\n{title} → {to}\nСтатус: ⏳ выполняется (обычно 1–5 мин)\nОстаток: {bal} с.",
           "giftLink": "🎁 <b>Подарок № {id} оплачен</b>\n@{to} ещё не открывал бота. Отправьте ему ссылку — подарок придёт, когда он нажмёт Start:\n{link}",
           "ordersT": "🧾 <b>Мои заказы</b>", "noOrders": "Заказов пока нет.",
           "st_work": "⏳ в работе", "st_wait": "⌛ ждёт получателя", "st_done": "✅ выполнен", "st_fail": "↩️ возврат",
           "topT": "💳 <b>Пополнение баланса</b>\nШаг 1 из 3 — напишите сумму в сомони (минимум {min} с.):",
           "topBank": "Шаг 2 из 3 — сумма <b>{sum} с.</b>\nВыберите банк:",
           "topReq": "Шаг 3 из 3 — переведите <b>{sum} с.</b>\n{method}:\n<code>{details}</code>\n\n📸 Затем пришлите сюда <b>фото чека</b> (или PDF).",
           "noMethods": "Способов оплаты пока нет — напишите в поддержку.", "lowSum": "Минимальная сумма — {min} с. Напишите другую сумму:",
           "badNum": "Напишите число, например 50", "badUser": "Напишите @username, например @ali_dev",
           "helpT": "❓ <b>Помощь</b>\n• Покупка: пакет → @username → оплата с баланса.\n• Пополнение: сумма → банк → перевод → фото чека.\n• Обычно заказ выполняется за 1–5 минут.",
           "support": "✉️ Поддержка", "sendCheck": "Пришлите фото чека к заявке № {id} — или нажмите «Отмена».",
           "paused": "⏸ Магазин на короткой паузе — попробуйте чуть позже.", "banned": "Доступ закрыт."},
    "tj": {"hello": "<b>{name}</b> — Stars, Premium ва тӯҳфаҳои Telegram\n\n💰 Баланс: <b>{bal} с.</b>\nЧӣ мехаред? 👇",
           "stars": "⭐ Stars", "premium": "💎 Premium", "gifts": "🎁 Тӯҳфаҳо", "topup": "💳 Пур кардан", "orders": "🧾 Фармоишҳо",
           "lang": "🌐 Русский", "help": "❓ Ёрӣ", "app": "📱 Мини-барнома", "back": "← Бозгашт", "menu": "🏠 Меню",
           "starsT": "⭐ <b>Telegram Stars</b>\nБаста ё миқдори худро интихоб кунед ({lo}–{hi}).",
           "own": "✍️ Миқдори дилхоҳ", "askQty": "Миқдори ситораҳоро бо рақам нависед ({lo}–{hi}):",
           "premT": "💎 <b>Telegram Premium</b>\nМуҳлатро интихоб кунед:", "mon": "моҳ",
           "giftT": "🎁 <b>Тӯҳфаҳои Telegram</b>\nТӯҳфаро интихоб кунед.",
           "who": "{title} — <b>{price} с.</b>\n\nБа кӣ? @username нависед ё «Ба худ»-ро пахш кунед.",
           "whoGift": "{title} — <b>{price} с.</b>\n\nБа кӣ тӯҳфа медиҳед? @username нависед ё «Ба худ».",
           "self": "👤 Ба худ", "noUser": "Шумо @username надоред — @username-и гирандаро нависед.",
           "check": "Фармоишро санҷед:\n{title} → <b>{to}</b>\nНарх: <b>{price} с.</b> · дар баланс {bal} с.",
           "pay": "✅ Аз баланс пардохт", "cancel": "✖ Бекор",
           "lack": "<b>{need} с.</b> намерасад — балансро пур кунед, фармоиш баъди санҷиши чек худ ба худ сохта мешавад.",
           "topNeed": "💳 Пур кардан ба {need} с.",
           "paid": "✅ <b>Фармоиши № {id} пардохт шуд</b>\n{title} → {to}\nҲолат: ⏳ дар иҷро (1–5 дақ.)\nБақия: {bal} с.",
           "giftLink": "🎁 <b>Тӯҳфаи № {id} пардохт шуд</b>\n@{to} ҳоло ботро накушодааст. Ин пайвандро ба ӯ фиристед:\n{link}",
           "ordersT": "🧾 <b>Фармоишҳои ман</b>", "noOrders": "Ҳоло фармоиш нест.",
           "st_work": "⏳ дар кор", "st_wait": "⌛ интизори гиранда", "st_done": "✅ иҷро шуд", "st_fail": "↩️ баргардонида шуд",
           "topT": "💳 <b>Пур кардани баланс</b>\nҚадами 1 аз 3 — маблағро бо сомонӣ нависед (ҳадди ақал {min} с.):",
           "topBank": "Қадами 2 аз 3 — маблағ <b>{sum} с.</b>\nБонкро интихоб кунед:",
           "topReq": "Қадами 3 аз 3 — <b>{sum} с.</b> интиқол диҳед\n{method}:\n<code>{details}</code>\n\n📸 Баъд <b>сурати чек</b>-ро ин ҷо фиристед.",
           "noMethods": "Ҳоло усули пардохт нест.", "lowSum": "Ҳадди ақал — {min} с. Маблағи дигар нависед:",
           "badNum": "Рақам нависед, масалан 50", "badUser": "@username нависед, масалан @ali_dev",
           "helpT": "❓ <b>Ёрӣ</b>\n• Харид: баста → @username → пардохт аз баланс.\n• Пуркунӣ: маблағ → бонк → интиқол → сурати чек.\n• Одатан 1–5 дақиқа.",
           "support": "✉️ Дастгирӣ", "sendCheck": "Сурати чекро барои дархости № {id} фиристед — ё «Бекор».",
           "paused": "⏸ Мағоза муваққатан таваққуф кардааст.", "banned": "Дастрасӣ баста аст."},
}
KIND_STATUS = {"new": "work", "processing": "work", "attention": "work", "paid": "work", "sending": "work",
               "awaiting_recipient": "wait", "completed": "done", "sent": "done", "failed": "fail"}
ADMIN_STATUS = {"new": "🆕 ждёт отправки", "processing": "⏳ у поставщика", "attention": "⚠️ нет связи",
                "paid": "🎁 отправляется", "sending": "🎁 отправляется", "awaiting_recipient": "⌛ ждёт получателя",
                "completed": "✅ выполнен", "sent": "✅ доставлен", "failed": "↩️ возврат"}


def b(text: str, data: str) -> dict:
    return {"text": text, "callback_data": data[:64]}


def rows(buttons: list[dict], n: int = 2) -> list[list[dict]]:
    return [buttons[i:i + n] for i in range(0, len(buttons), n)]


class Ui:
    def __init__(self, config: Config, bot: Bot, conn, supplier=None):
        self.config, self.bot, self.conn, self.supplier = config, bot, conn, supplier

    # ── общее ──
    def t(self, uid: int) -> dict:
        row = self.conn.execute("SELECT lang FROM users WHERE id = ?", (uid,)).fetchone()
        return TX["ru" if row and row["lang"] == "ru" else "tj"]

    def user(self, uid: int):
        return self.conn.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()

    def show(self, chat: int, mid: int | None, text: str, kb: list | None = None) -> None:
        """Обновить сообщение с кнопками; не получилось (фото, старое) — прислать новое."""
        markup = {"inline_keyboard": kb or []}
        if mid:
            try:
                self.bot.call("editMessageText", chat_id=chat, message_id=mid, text=text, parse_mode="HTML",
                              reply_markup=markup, disable_web_page_preview=True)
                return
            except TgError as exc:
                if "not modified" in str(exc):
                    return
        self.bot.safe("sendMessage", chat_id=chat, text=text, parse_mode="HTML", reply_markup=markup,
                      disable_web_page_preview=True)

    def state(self, uid: int) -> tuple[str, dict]:
        r = self.conn.execute("SELECT state, data FROM chat_state WHERE user_id = ?", (uid,)).fetchone()
        return (r["state"], json.loads(r["data"] or "{}")) if r else ("", {})

    def set_state(self, uid: int, state: str = "", **data) -> None:
        if not state:
            self.conn.execute("DELETE FROM chat_state WHERE user_id = ?", (uid,))
        else:
            self.conn.execute("INSERT OR REPLACE INTO chat_state (user_id, state, data) VALUES (?, ?, ?)",
                              (uid, state, json.dumps(data, ensure_ascii=False)))

    def is_admin(self, uid: int) -> bool:
        return shop.is_admin(self.conn, self.config, uid)

    def app_row(self, t: dict) -> list:
        return [[{"text": t["app"], "web_app": {"url": self.config.base_url + "/app"}}]]

    # ══════════════════ КЛИЕНТ ══════════════════

    def home(self, uid: int, mid: int | None = None) -> None:
        t, u = self.t(uid), self.user(uid)
        self.set_state(uid)
        kb = rows([b(t["stars"], "c:stars"), b(t["premium"], "c:prem"), b(t["gifts"], "c:gifts"), b(t["topup"], "c:top"),
                   b(t["orders"], "c:ord"), b(t["lang"], "c:lang")]) + [[b(t["help"], "c:help")]] + self.app_row(t)
        if self.is_admin(uid):
            kb.append([b("⚙️ Админ-панель", "a:home")])
        self.show(uid, mid, t["hello"].format(name=esc(self.config.name), bal=fmt(u["balance"] if u else 0)), kb)

    def client(self, uid: int, mid: int, data: str) -> None:
        t, c = self.t(uid), self.conn
        u = self.user(uid)
        if u is None or u["banned"]:
            return self.show(uid, mid, t["banned"])
        parts = data.split(":")
        act = parts[1]
        cat = shop.public_catalog(c)
        if act == "home":
            return self.home(uid, mid)
        if act == "lang":
            c.execute("UPDATE users SET lang = ? WHERE id = ?", ("tj" if u["lang"] == "ru" else "ru", uid))
            return self.home(uid, mid)
        if act == "help":
            kb = ([[{"text": t["support"], "url": self._support_url()}]] if self._support_url() else []) + [[b(t["back"], "c:home")]]
            return self.show(uid, mid, t["helpT"], kb)
        if act == "stars":
            s = cat["stars"]
            if not s:
                return self.show(uid, mid, "⭐ Stars — скоро / ба зудӣ", [[b(t["back"], "c:home")]])
            kb = rows([b(f"{p['qty']} ⭐ · {fmt(p['price'])} с.", f"c:sq:{p['qty']}") for p in s["packs"]])
            return self.show(uid, mid, t["starsT"].format(lo=s["min"], hi=s["max"]),
                             kb + [[b(t["own"], "c:sown")], [b(t["back"], "c:home")]])
        if act == "sown":
            s = cat["stars"] or {"min": 50, "max": 10000}
            self.set_state(uid, "qty", mid=mid)
            return self.show(uid, mid, t["askQty"].format(lo=s["min"], hi=s["max"]), [[b(t["back"], "c:stars")]])
        if act == "sq":
            return self.ask_to(uid, mid, {"kind": "stars", "qty": int(parts[2])})
        if act == "prem":
            kb = rows([b(f"{p['months']} {t['mon']} · {fmt(p['price'])} с.", f"c:pm:{p['months']}") for p in cat["premium"]], 1)
            return self.show(uid, mid, t["premT"], kb + [[b(t["back"], "c:home")]])
        if act == "pm":
            return self.ask_to(uid, mid, {"kind": "premium", "months": int(parts[2])})
        if act == "gifts":
            page = int(parts[2]) if len(parts) > 2 else 0
            g = cat["gifts"]
            chunk = g[page * PAGE:(page + 1) * PAGE]
            kb = rows([b(f"{x['emoji'] or '🎁'} ★{x['stars']} · {fmt(x['price'])} с.", f"c:g:{x['id']}") for x in chunk])
            nav = ([b("◀", f"c:gifts:{page - 1}")] if page else []) + ([b("▶", f"c:gifts:{page + 1}")] if len(g) > (page + 1) * PAGE else [])
            return self.show(uid, mid, t["giftT"], kb + ([nav] if nav else []) + [[b(t["back"], "c:home")]])
        if act == "g":
            return self.ask_to(uid, mid, {"kind": "gift", "gift_id": parts[2]})
        if act == "self":
            st, d = self.state(uid)
            item = d.get("item")
            if not item:
                return self.home(uid, mid)
            if item["kind"] == "gift":
                item["to"] = ""
            elif u["username"]:
                item["to"] = u["username"]
            else:
                return self.show(uid, mid, t["noUser"], [[b(t["back"], "c:home")]])
            return self.confirm(uid, mid, item)
        if act == "pay":
            st, d = self.state(uid)
            if st != "confirm":
                return self.home(uid, mid)
            return self.pay(uid, mid, d["item"])
        if act == "ord":
            return self.orders(uid, mid)
        if act == "top":
            self.set_state(uid, "amount", mid=mid)
            return self.show(uid, mid, t["topT"].format(min=fmt(shop.min_topup(c))), [[b(t["back"], "c:home")]])
        if act == "tneed":   # пополнить ровно на недостающее и потом купить
            st, d = self.state(uid)
            if st != "confirm":
                return self.home(uid, mid)
            q = shop.quote(c, d["item"])
            need = max(q["price"] - u["balance"], shop.min_topup(c))
            return self.banks(uid, mid, need, d["item"])
        if act == "tm":
            st, d = self.state(uid)
            if st != "bank":
                return self.home(uid, mid)
            try:
                tp = shop.create_topup(c, uid, parts[2], int(d["amount"]), d.get("intent"))
            except shop.ShopError as exc:
                return self.show(uid, mid, esc(str(exc)), [[b(t["back"], "c:home")]])
            v = shop.topup_view(c, tp)
            self.set_state(uid, "receipt", tid=tp["id"])
            return self.show(uid, mid, t["topReq"].format(sum=v["amount_text"], method=esc(v["method"]), details=esc(v["details"])),
                             [[b(t["cancel"], f"c:tcancel:{tp['id']}")]])
        if act == "tcancel":
            c.execute("UPDATE topups SET status = 'cancelled', resolved_at = ? WHERE id = ? AND user_id = ? AND status = 'waiting'",
                      (db.now(), int(parts[2]), uid))
            return self.home(uid, mid)
        return self.home(uid, mid)

    def _support_url(self) -> str:
        s = self.config.support or ""
        return "https://t.me/" + s[1:] if s.startswith("@") else s if s.startswith("http") else ""

    def ask_to(self, uid: int, mid: int, item: dict) -> None:
        t = self.t(uid)
        try:
            q = shop.quote(self.conn, item)
        except shop.ShopError as exc:
            return self.show(uid, mid, esc(str(exc)), [[b(t["back"], "c:home")]])
        self.set_state(uid, "to", mid=mid, item=item)
        key = "whoGift" if item["kind"] == "gift" else "who"
        self.show(uid, mid, t[key].format(title=esc(q["title"]), price=fmt(q["price"])),
                  [[b(t["self"], "c:self")], [b(t["back"], "c:home")]])

    def confirm(self, uid: int, mid: int | None, item: dict) -> None:
        t, u = self.t(uid), self.user(uid)
        try:
            q = shop.quote(self.conn, item)
            if item["kind"] != "gift" or item.get("to"):
                item["to"] = shop.clean_username(item.get("to") or "")
        except shop.ShopError as exc:
            return self.show(uid, mid, esc(str(exc)), [[b(t["back"], "c:home")]])
        self.set_state(uid, "confirm", item=item)
        to = "@" + item["to"] if item.get("to") else t["self"].split(" ", 1)[1]
        text = t["check"].format(title=esc(q["title"]), to=esc(to), price=fmt(q["price"]), bal=fmt(u["balance"]))
        if u["balance"] >= q["price"]:
            kb = [[b(t["pay"], "c:pay")], [b(t["cancel"], "c:home")]]
        else:
            text += "\n\n" + t["lack"].format(need=fmt(q["price"] - u["balance"]))
            kb = [[b(t["topNeed"].format(need=fmt(max(q["price"] - u["balance"], shop.min_topup(self.conn)))), "c:tneed")],
                  [b(t["cancel"], "c:home")]]
        self.show(uid, mid, text, kb)

    def pay(self, uid: int, mid: int, item: dict) -> None:
        t = self.t(uid)
        try:
            o = shop.place_order(self.conn, uid, item)
        except shop.ShopError as exc:
            return self.show(uid, mid, "❌ " + esc(str(exc)), [[b(t["topup"], "c:top")], [b(t["menu"], "c:home")]])
        self.set_state(uid)
        bal = self.user(uid)["balance"]
        if o["status"] == "awaiting_recipient":
            link = f"https://t.me/{db.get_setting(self.conn, 'bot_username')}?start=g_{o['gift_token']}"
            text = t["giftLink"].format(id=o["id"], to=esc(o["recipient"]), link=link)
        else:
            to = "@" + o["recipient"] if o["recipient"] and not (o["kind"] == "gift" and o["recipient_id"] == uid) else t["self"].split(" ", 1)[1]
            text = t["paid"].format(id=o["id"], title=esc(o["title"]), to=esc(to), bal=fmt(bal))
        self.show(uid, mid, text, [[b(t["orders"], "c:ord"), b(t["menu"], "c:home")]])

    def orders(self, uid: int, mid: int | None) -> None:
        t = self.t(uid)
        rs = self.conn.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 10", (uid,)).fetchall()
        lines = [f"№ {o['id']} · {esc(o['title'])}" + (f" → @{esc(o['recipient'])}" if o["recipient"] else "") +
                 f"\n   {fmt(o['price'])} с. · {t['st_' + KIND_STATUS.get(o['status'], 'work')]}" for o in rs]
        self.show(uid, mid, t["ordersT"] + "\n\n" + ("\n".join(lines) if lines else t["noOrders"]),
                  [[b("🔄", "c:ord"), b(t["menu"], "c:home")]])

    def banks(self, uid: int, mid: int | None, amount: int, intent: dict | None = None) -> None:
        t, ms = self.t(uid), shop.methods(self.conn)
        if not ms:
            return self.show(uid, mid, t["noMethods"], [[b(t["back"], "c:home")]])
        self.set_state(uid, "bank", amount=amount, intent=intent)
        self.show(uid, mid, t["topBank"].format(sum=fmt(amount)),
                  [[b(m["title"], f"c:tm:{m['code']}")] for m in ms] + [[b(t["cancel"], "c:home")]])

    def client_text(self, uid: int, text: str, state: str, d: dict) -> bool:
        """Ответ текстом на вопрос бота. True — обработано."""
        t, c = self.t(uid), self.conn
        if state == "qty":
            try:
                qty = int(text.replace(" ", ""))
            except ValueError:
                self.bot.send(uid, t["badNum"]); return True
            self.ask_to(uid, None, {"kind": "stars", "qty": qty}); return True
        if state == "to":
            item = d["item"]
            item["to"] = text.strip()
            try:
                shop.clean_username(item["to"])
            except shop.ShopError:
                self.bot.send(uid, t["badUser"]); return True
            self.confirm(uid, None, item); return True
        if state == "amount":
            try:
                amount = to_diram(text)
            except Exception:  # noqa: BLE001
                self.bot.send(uid, t["badNum"]); return True
            if amount < shop.min_topup(c):
                self.bot.send(uid, t["lowSum"].format(min=fmt(shop.min_topup(c)))); return True
            self.banks(uid, None, amount); return True
        if state == "receipt":
            self.bot.send(uid, t["sendCheck"].format(id=d.get("tid")), [[b(t["cancel"], f"c:tcancel:{d.get('tid')}")]]); return True
        return False

    def receipt(self, uid: int, data: bytes, ext: str) -> None:
        from .bot import submit_receipt
        st, d = self.state(uid)
        t = self.t(uid)
        try:
            msg = submit_receipt(self.config, self.bot, self.conn, uid, int(d.get("tid") or 0), data, ext)
        except shop.ShopError as exc:
            self.bot.send(uid, "❌ " + esc(str(exc)))
            return
        self.set_state(uid)
        self.bot.send(uid, "✅ " + esc(msg), [[b(t["menu"], "c:home")]])

    # ══════════════════ АДМИН ══════════════════

    def admin(self, uid: int, mid: int | None, data: str = "a:home") -> None:
        if not self.is_admin(uid):
            return
        p = data.split(":")
        act = p[1]
        c = self.conn
        h = getattr(self, "a_" + act, None)
        if h is None:
            return self.a_home(uid, mid, p)
        self.set_state(uid)   # новое нажатие отменяет незаконченный ввод
        h(uid, mid, p)

    def a_home(self, uid, mid, p=None) -> None:
        c = self.conn
        q = lambda sql, *a: c.execute(sql, a).fetchone()  # noqa: E731
        today = q("SELECT COUNT(*), COALESCE(SUM(price),0) FROM orders WHERE created_at >= date('now') AND status != 'failed'")
        week = q("SELECT COUNT(*), COALESCE(SUM(price),0) FROM orders WHERE created_at >= date('now','-6 days') AND status != 'failed'")
        users = q("SELECT COUNT(*) FROM users")[0]
        new = q("SELECT COUNT(*) FROM users WHERE created_at >= date('now')")[0]
        checks = q("SELECT COUNT(*) FROM topups WHERE status = 'pending'")[0]
        stuck = q("SELECT COUNT(*) FROM orders WHERE status = 'attention'")[0]
        sup = "—"
        if self.supplier is not None:
            try:
                sup = f"${self.supplier.balance()}"
            except Exception:  # noqa: BLE001
                sup = "нет связи"
        stars = (self.bot.safe("getMyStarBalance") or {}).get("amount", "—")
        text = (f"⚙️ <b>Панель {esc(self.config.name)}</b>" + ("  ⏸ <b>ПАУЗА</b>" if shop.paused(c) else "") + "\n\n"
                f"Сегодня: {today[0]} заказов · <b>{fmt(today[1])} с.</b>\n7 дней: {week[0]} · {fmt(week[1])} с.\n"
                f"Клиентов: {users} (+{new} сегодня)\n🧾 Чеков ждут: <b>{checks}</b> · ⚠️ зависших: {stuck}\n"
                f"Поставщик: {sup} · Stars бота: {stars} ⭐")
        kb = rows([b(f"🧾 Чеки ({checks})", "a:chk"), b("📦 Заказы", "a:ord"), b("💲 Цены", "a:pr"), b("💳 Карты", "a:cards"),
                   b("👥 Клиенты", "a:cl"), b("📢 Рассылка", "a:bc"), b("📊 Статистика", "a:st"), b("⚙️ Настройки", "a:set")]) + \
            [[b("🔄 Обновить", "a:home"), b("🏠 Магазин", "c:home")]]
        self.show(uid, mid, text, kb)

    # ── чеки ──
    def a_chk(self, uid, mid, p) -> None:
        rs = self.conn.execute("SELECT t.*, u.first_name, u.username FROM topups t JOIN users u ON u.id = t.user_id "
                               "WHERE t.status = 'pending' ORDER BY t.id LIMIT 20").fetchall()
        kb = [[b(f"№ {r['id']} · {fmt(r['amount'])} с. · {r['first_name'] or r['user_id']}", f"a:ck:{r['id']}")] for r in rs]
        self.show(uid, mid, "🧾 <b>Чеки на проверке</b>\n" + ("Нажмите, чтобы открыть чек." if rs else "Чеков нет ✅"),
                  kb + [[b("← Панель", "a:home")]])

    def a_ck(self, uid, mid, p) -> None:
        from pathlib import Path
        t = self.conn.execute("SELECT t.*, u.first_name, u.username FROM topups t JOIN users u ON u.id = t.user_id WHERE t.id = ?",
                              (int(p[2]),)).fetchone()
        if t is None or t["status"] != "pending":
            return self.a_chk(uid, mid, p)
        card = self.conn.execute("SELECT details FROM cards WHERE id = ?", (t["card_id"],)).fetchone()
        cap = (f"🧾 Пополнение № {t['id']} · {fmt(t['amount'])} с.\n{shop.METHODS.get(t['method'])}: {card['details'] if card else '—'}\n"
               f"Клиент: {t['first_name']} @{t['username'] or '—'} ({t['user_id']})" + (f"\nИИ: {t['ai_note']}" if t["ai_note"] else ""))
        kb = {"inline_keyboard": [[b("✅ Зачислить", f"tp:ok:{t['id']}"), b("❌ Отклонить", f"a:rj:{t['id']}")]]}
        path = Path(self.config.receipts_dir) / Path(t["receipt_file"] or "x").name
        try:
            if path.exists():
                method, field = ("sendDocument", "document") if path.suffix == ".pdf" else ("sendPhoto", "photo")
                self.bot.call(method, files={field: (path.name, path.read_bytes())}, chat_id=uid, caption=cap, reply_markup=kb)
                return
        except TgError as exc:
            log.warning("чек %s: %s", t["id"], exc)
        self.bot.safe("sendMessage", chat_id=uid, text=cap + "\n(файл чека не найден)", reply_markup=kb)

    def a_rj(self, uid, mid, p) -> None:
        self.set_state(uid, "reject", tid=int(p[2]))
        self.bot.send(uid, f"Причина отказа по № {p[2]} (клиент увидит). Например: <i>перевод не найден</i>",
                      [[b("Перевод не найден", f"a:rjx:{p[2]}")], [b("← Отмена", "a:chk")]])

    def a_rjx(self, uid, mid, p) -> None:
        self._reject(uid, int(p[2]), "перевод не найден")

    def _reject(self, uid, tid: int, note: str) -> None:
        from .bot import finish_topup
        who = self.user(uid)
        t = finish_topup(self.config, self.bot, self.conn, tid, False, (who["first_name"] if who else "") or str(uid), note)
        self.set_state(uid)
        self.bot.send(uid, f"❌ № {tid} отклонено." if t else "Эту заявку уже решили.", [[b("🧾 Чеки", "a:chk"), b("← Панель", "a:home")]])

    # ── заказы ──
    def a_ord(self, uid, mid, p) -> None:
        rs = self.conn.execute("SELECT * FROM orders WHERE status IN ('attention','new','processing','paid','sending','awaiting_recipient') "
                               "ORDER BY id DESC LIMIT 15").fetchall()
        last = self.conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 5").fetchall()
        kb = [[b(f"№ {o['id']} · {o['title']} · {ADMIN_STATUS.get(o['status'], o['status'])}", f"a:o:{o['id']}")] for o in rs]
        text = "📦 <b>Заказы в работе</b>" + ("" if rs else "\nВсё выполнено ✅") + "\n\nПоследние:\n" + "\n".join(
            f"№ {o['id']} · {esc(o['title'])} → @{esc(o['recipient'])} · {fmt(o['price'])} с. · {ADMIN_STATUS.get(o['status'], o['status'])}"
            for o in last)
        self.show(uid, mid, text + "\n\nНайти заказ: нажмите 🔎 и напишите номер.",
                  kb + [[b("🔎 Найти заказ", "a:ofind"), b("← Панель", "a:home")]])

    def a_ofind(self, uid, mid, p) -> None:
        self.set_state(uid, "ofind")
        self.show(uid, mid, "Напишите номер заказа:", [[b("← Заказы", "a:ord")]])

    def a_o(self, uid, mid, p) -> None:
        o = self.conn.execute("SELECT o.*, u.first_name FROM orders o JOIN users u ON u.id = o.user_id WHERE o.id = ?",
                              (int(p[2]),)).fetchone()
        if o is None:
            return self.show(uid, mid, "Заказ не найден.", [[b("← Заказы", "a:ord")]])
        text = (f"📦 <b>Заказ № {o['id']}</b>\n{esc(o['title'])} → @{esc(o['recipient'])}\nКлиент: {esc(o['first_name'])} ({o['user_id']})\n"
                f"Цена: {fmt(o['price'])} с." + (f" · закупка ${o['cost_usd']}" if o["cost_usd"] else "") +
                f"\nСтатус: {ADMIN_STATUS.get(o['status'], o['status'])}\nПоставщик: {o['supplier_order_id'] or '—'}\n"
                f"Создан: {o['created_at']}" + (f"\nОшибка: {esc(o['error'])}" if o["error"] else ""))
        kb = []
        if o["status"] == "attention":
            kb.append([b("🔁 Повторить", f"a:oa:{o['id']}:retry")])
        if o["status"] not in ("completed", "sent", "failed"):
            kb.append([b("✅ Выполнен", f"a:oa:{o['id']}:done"), b("↩️ Вернуть деньги", f"a:oa:{o['id']}:ask")])
        self.show(uid, mid, text, kb + [[b("👤 Клиент", f"a:u:{o['user_id']}"), b("← Заказы", "a:ord")]])

    def a_oa(self, uid, mid, p) -> None:
        oid, act, c = int(p[2]), p[3], self.conn
        o = c.execute("SELECT * FROM orders WHERE id = ?", (oid,)).fetchone()
        if o is None:
            return self.a_ord(uid, mid, p)
        if act == "ask":
            return self.show(uid, mid, f"Вернуть {fmt(o['price'])} с. клиенту за заказ № {oid}?\n"
                                       "Делайте это, только если у поставщика заказа точно нет.",
                             [[b("Да, вернуть", f"a:oa:{oid}:refund"), b("Нет", f"a:o:{oid}")]])
        if act == "refund":
            if shop.refund(c, oid, "отменён администратором"):
                self.bot.safe("sendMessage", chat_id=o["user_id"], text=f"↩️ Заказ № {oid} отменён, {fmt(o['price'])} с. вернулись на баланс.")
        elif act == "done":
            c.execute("UPDATE orders SET status = ?, updated_at = ? WHERE id = ? AND status NOT IN ('completed','sent','failed')",
                      ("sent" if o["kind"] == "gift" else "completed", db.now(), oid))
        elif act == "retry":
            c.execute("UPDATE orders SET status = CASE WHEN kind = 'gift' THEN 'paid' ELSE 'new' END, tries = 0, updated_at = ? "
                      "WHERE id = ? AND status = 'attention'", (db.now(), oid))
        self.a_o(uid, mid, ["a", "o", str(oid)])

    # ── цены ──
    def a_pr(self, uid, mid, p) -> None:
        c = self.conn
        fix = shop.fixed_prices(c)
        gs = db.get_setting(c, "gift_star_diram")
        text = (f"💲 <b>Цены</b>\nКурс: <b>{shop.rate(c)}</b> с. за $1 · наценка <b>{shop.markup(c)}%</b>\n"
                f"Звезда подарка: {fmt(int(gs)) + ' с.' if gs else 'как у Stars'}\n"
                f"Ручных цен: {len(fix)} · скрыто: {len(shop.hidden(c))}\n\n"
                "✏️ — своя цена · авто — по формуле (закупка × курс × наценка)")
        kb = rows([b("⭐ Пакеты Stars", "a:ps"), b("💎 Premium", "a:pp"), b("🎁 Подарки", "a:pg:0"), b("💱 Курс", "a:pset:rate"),
                   b("📈 Наценка", "a:pset:markup"), b("⭐ Звезда подарка", "a:pset:giftstar")]) + \
            [[b("↩️ Сбросить все ручные цены", "a:pclr")], [b("← Панель", "a:home")]]
        self.show(uid, mid, text, kb)

    def _mark(self, it: dict) -> str:
        return ("🙈 " if it["hidden"] else "") + ("✏️" if it["fixed"] else "авто")

    def a_ps(self, uid, mid, p) -> None:
        cat = shop.catalog(self.conn, everything=True)
        s = cat["stars"]
        if not s:
            return self.show(uid, mid, "Цены Stars ещё не пришли от поставщика (обновляются раз в 10 минут).", [[b("← Цены", "a:pr")]])
        per = db.get_setting(self.conn, "star_usd")
        kb = rows([b(f"{x['qty']} ⭐ · {fmt(x['price'])} с. {self._mark(x)}", f"a:pk:stars:{x['qty']}") for x in s["packs"]])
        self.show(uid, mid, f"⭐ <b>Пакеты Stars</b>\nЗакупка: ${per} за звезду · своё кол-во клиента — по формуле.\n"
                            "Нажмите пакет, чтобы поставить свою цену, скрыть или удалить.",
                  kb + [[b("➕ Добавить пакет", "a:padd"), b("← Цены", "a:pr")]])

    def a_pp(self, uid, mid, p) -> None:
        cat = shop.catalog(self.conn, everything=True)
        kb = [[b(f"{x['months']} мес. · {fmt(x['price'])} с. {self._mark(x)}", f"a:pk:premium:{x['months']}")] for x in cat["premium"]]
        self.show(uid, mid, "💎 <b>Premium</b>\nНажмите тариф, чтобы поставить свою цену или скрыть." if kb else
                  "Тарифы Premium ещё не пришли от поставщика.", kb + [[b("← Цены", "a:pr")]])

    def a_pg(self, uid, mid, p) -> None:
        page = int(p[2]) if len(p) > 2 else 0
        g = shop.catalog(self.conn, everything=True)["gifts"]
        chunk = g[page * PAGE:(page + 1) * PAGE]
        kb = rows([b(f"{x['emoji'] or '🎁'} ★{x['stars']} · {fmt(x['price'])} с. {self._mark(x)}", f"a:pk:gift:{x['id']}") for x in chunk])
        nav = ([b("◀", f"a:pg:{page - 1}")] if page else []) + ([b("▶", f"a:pg:{page + 1}")] if len(g) > (page + 1) * PAGE else [])
        self.show(uid, mid, f"🎁 <b>Подарки</b> ({len(g)})\nНажмите подарок, чтобы поставить свою цену или скрыть.",
                  kb + ([nav] if nav else []) + [[b("← Цены", "a:pr")]])

    def _item(self, key: str) -> dict | None:
        cat = shop.catalog(self.conn, everything=True)
        pool = (cat["stars"] or {}).get("packs", []) + cat["premium"] + cat["gifts"]
        return next((x for x in pool if x["key"] == key), None)

    def _title(self, it: dict) -> str:
        if "qty" in it:
            return f"⭐ {it['qty']} Stars"
        if "months" in it:
            return f"💎 Premium {it['months']} мес."
        return f"{it.get('emoji') or '🎁'} Подарок ★{it['stars']}"

    def _back(self, key: str) -> str:
        return {"stars": "a:ps", "premium": "a:pp", "gift": "a:pg:0"}[key.split(":")[0]]

    def a_pk(self, uid, mid, p) -> None:
        key = ":".join(p[2:])
        it = self._item(key)
        if it is None:
            return self.a_pr(uid, mid, p)
        c = self.conn
        rate = shop.rate(c)
        cost = ""
        if it.get("cost_usd"):
            cd = Decimal(it["cost_usd"])
            cost_d = int(cd * rate * 100)
            cost = f"Закупка: ${cd.quantize(Decimal('0.01'))} ≈ {fmt(cost_d)} с.\n"
            profit = f"\nПрибыль с продажи: <b>{fmt(it['price'] - cost_d)} с.</b>"
        else:
            profit = ""
        text = (f"<b>{self._title(it)}</b>\n{cost}По формуле: {fmt(it['auto'])} с. · сейчас: <b>{fmt(it['price'])} с.</b> "
                f"{'✏️' if it['fixed'] else '(авто)'}" + (" · 🙈 скрыт" if it["hidden"] else "") + profit +
                "\n\nЧтобы поставить свою цену — нажмите ✏️ и напишите сумму в сомони.")
        kb = [[b("✏️ Своя цена", f"a:pfix:{key}")],
              [b("↩️ Вернуть авто", f"a:pauto:{key}"), b("👁 Показать" if it["hidden"] else "🙈 Скрыть", f"a:phide:{key}")]]
        if key.startswith("stars:"):
            kb.append([b("🗑 Удалить пакет", f"a:pdel:{it['qty']}")])
        self.show(uid, mid, text, kb + [[b("← Назад", self._back(key))]])

    def a_pfix(self, uid, mid, p) -> None:
        key = ":".join(p[2:])
        self.set_state(uid, "price", key=key, mid=mid)
        it = self._item(key)
        self.show(uid, mid, f"Новая цена для <b>{self._title(it) if it else key}</b> в сомони (например 95 или 95,50):",
                  [[b("← Отмена", f"a:pk:{key}")]])

    def a_pauto(self, uid, mid, p) -> None:
        key = ":".join(p[2:])
        shop.set_fixed(self.conn, key, None)
        self.a_pk(uid, mid, ["a", "pk", *key.split(":")])

    def a_phide(self, uid, mid, p) -> None:
        key = ":".join(p[2:])
        shop.toggle_hidden(self.conn, key)
        self.a_pk(uid, mid, ["a", "pk", *key.split(":")])

    def a_pdel(self, uid, mid, p) -> None:
        qty = int(p[2])
        shop.set_star_packs(self.conn, [q for q in shop.star_packs(self.conn) if q != qty])
        shop.set_fixed(self.conn, f"stars:{qty}", None)
        self.a_ps(uid, mid, p)

    def a_padd(self, uid, mid, p) -> None:
        self.set_state(uid, "addpack", mid=mid)
        self.show(uid, mid, "Сколько звёзд в новом пакете? Напишите число (например 750). "
                            "Можно сразу с ценой: <code>750 140</code>", [[b("← Отмена", "a:ps")]])

    def a_pclr(self, uid, mid, p) -> None:
        if len(p) < 3:
            return self.show(uid, mid, "Сбросить ВСЕ ручные цены? Все пакеты вернутся к цене по формуле.",
                             [[b("Да, сбросить", "a:pclr:yes"), b("Нет", "a:pr")]])
        db.set_setting(self.conn, "price_fix", "{}")
        self.a_pr(uid, mid, p)

    def a_pset(self, uid, mid, p) -> None:
        what = p[2]
        c = self.conn
        ask = {"rate": f"Курс: сколько сомони за $1? Сейчас {shop.rate(c)}. Напишите, например 11,2",
               "markup": f"Наценка в %. Сейчас {shop.markup(c)}. Напишите, например 12",
               "giftstar": "Цена 1 звезды подарка в сомони, например 0,25. Напишите 0 — как у Stars.",
               "min": f"Минимальная сумма пополнения в сомони. Сейчас {fmt(shop.min_topup(c))}.",
               "support": f"Контакт поддержки (@username или ссылка). Сейчас: {self.config.support or '—'}"}[what]
        self.set_state(uid, "set", what=what, mid=mid)
        self.show(uid, mid, ask, [[b("← Отмена", "a:pr" if what in ("rate", "markup", "giftstar") else "a:set")]])

    # ── карты ──
    def a_cards(self, uid, mid, p) -> None:
        cs = shop.cards(self.conn)
        kb = [[b(f"🚫 Выкл. № {x['id']} · {shop.METHODS.get(x['method'])}", f"a:coff:{x['id']}")] for x in cs]
        text = "💳 <b>Карты для оплаты</b>\n" + ("\n".join(f"№ {x['id']} · {shop.METHODS.get(x['method'])}: <code>{esc(x['details'])}</code>"
                                                     for x in cs) or "Карт нет — клиенты не смогут пополнить баланс.")
        self.show(uid, mid, text, kb + [[b(f"➕ {v}", f"a:cadd:{k}")] for k, v in shop.METHODS.items()] + [[b("← Панель", "a:home")]])

    def a_coff(self, uid, mid, p) -> None:
        self.conn.execute("UPDATE cards SET active = 0 WHERE id = ?", (int(p[2]),))
        self.a_cards(uid, mid, p)

    def a_cadd(self, uid, mid, p) -> None:
        self.set_state(uid, "card", method=p[2], mid=mid)
        self.show(uid, mid, f"Реквизиты для «{shop.METHODS.get(p[2])}» одним сообщением, например:\n"
                            "<code>+992 90 000 00 00 · Али В.</code>", [[b("← Отмена", "a:cards")]])

    # ── клиенты ──
    def a_cl(self, uid, mid, p) -> None:
        top = self.conn.execute("SELECT u.id, u.first_name, u.username, COALESCE(SUM(o.price),0) s FROM users u "
                                "JOIN orders o ON o.user_id = u.id AND o.status != 'failed' GROUP BY u.id ORDER BY s DESC LIMIT 5").fetchall()
        self.set_state(uid, "find")
        self.show(uid, mid, "👥 <b>Клиенты</b>\nНапишите ID или @username клиента.\n\nЛучшие покупатели:\n" +
                  ("\n".join(f"{esc(r['first_name'])} @{esc(r['username'] or '—')} · {fmt(r['s'])} с." for r in top) or "—"),
                  [[b(f"👤 {r['first_name'] or r['id']}", f"a:u:{r['id']}")] for r in top] + [[b("← Панель", "a:home")]])

    def a_u(self, uid, mid, p) -> None:
        c = self.conn
        u = self.user(int(p[2]))
        if u is None:
            return self.show(uid, mid, "Клиент не найден.", [[b("← Клиенты", "a:cl")]])
        n, s = c.execute("SELECT COUNT(*), COALESCE(SUM(price),0) FROM orders WHERE user_id = ? AND status != 'failed'", (u["id"],)).fetchone()
        last = c.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY id DESC LIMIT 5", (u["id"],)).fetchall()
        text = (f"👤 <b>{esc(u['first_name'])}</b> @{esc(u['username'] or '—')}\nID: <code>{u['id']}</code> · с {u['created_at'][:10]}\n"
                f"Баланс: <b>{fmt(u['balance'])} с.</b>\nЗаказов: {n} на {fmt(s)} с." + (" · 🚫 заблокирован" if u["banned"] else "") +
                "\n\n" + "\n".join(f"№ {o['id']} · {esc(o['title'])} · {ADMIN_STATUS.get(o['status'], o['status'])}" for o in last))
        kb = [[b("➕➖ Изменить баланс", f"a:give:{u['id']}")],
              [b("✅ Разблокировать" if u["banned"] else "🚫 Заблокировать", f"a:ban:{u['id']}"),
               b("✉️ Написать", f"a:dm:{u['id']}")], [b("← Клиенты", "a:cl")]]
        self.show(uid, mid, text, kb)

    def a_give(self, uid, mid, p) -> None:
        self.set_state(uid, "give", target=int(p[2]), mid=mid)
        self.show(uid, mid, "Сумма в сомони: <code>50</code> — начислить, <code>-10</code> — списать. "
                            "Можно с комментарием для клиента: <code>50 бонус</code>", [[b("← Отмена", f"a:u:{p[2]}")]])

    def a_ban(self, uid, mid, p) -> None:
        self.conn.execute("UPDATE users SET banned = 1 - banned WHERE id = ?", (int(p[2]),))
        self.a_u(uid, mid, p)

    def a_dm(self, uid, mid, p) -> None:
        self.set_state(uid, "dm", target=int(p[2]))
        self.show(uid, mid, "Напишите сообщение клиенту — бот перешлёт его от имени магазина.", [[b("← Отмена", f"a:u:{p[2]}")]])

    # ── рассылка ──
    def a_bc(self, uid, mid, p) -> None:
        n = self.conn.execute("SELECT COUNT(*) FROM users WHERE banned = 0").fetchone()[0]
        self.set_state(uid, "bc")
        self.show(uid, mid, f"📢 <b>Рассылка</b> — {n} клиентам.\nНапишите текст сообщения. Перед отправкой покажу, как оно выглядит.",
                  [[b("← Панель", "a:home")]])

    def a_bcgo(self, uid, mid, p) -> None:
        text = db.get_setting(self.conn, "bc_draft")
        if not text:
            return self.a_home(uid, mid)
        db.set_setting(self.conn, "bc_draft", "")
        ids = [r[0] for r in self.conn.execute("SELECT id FROM users WHERE banned = 0")]
        self.show(uid, mid, f"📢 Отправляю {len(ids)} клиентам… Отчёт пришлю сюда.")

        def run():
            ok = 0
            for i in ids:
                if self.bot.safe("sendMessage", chat_id=i, text=text, parse_mode="HTML", disable_web_page_preview=True):
                    ok += 1
                time.sleep(0.05)   # не больше ~20 сообщений в секунду — лимит Telegram
            self.bot.safe("sendMessage", chat_id=uid, text=f"📢 Рассылка готова: доставлено {ok} из {len(ids)}.")
        threading.Thread(target=run, daemon=True).start()

    # ── статистика ──
    def a_st(self, uid, mid, p) -> None:
        c = self.conn
        rate = shop.rate(c)
        out = ["📊 <b>Статистика</b>"]
        for title, since in (("Сегодня", "date('now')"), ("7 дней", "date('now','-6 days')"), ("30 дней", "date('now','-29 days')")):
            rs = c.execute(f"SELECT kind, COUNT(*) n, COALESCE(SUM(price),0) s FROM orders WHERE created_at >= {since} "
                           "AND status != 'failed' GROUP BY kind").fetchall()
            cost = sum(Decimal(r[0] or 0) for r in c.execute(
                f"SELECT cost_usd FROM orders WHERE created_at >= {since} AND status != 'failed' AND cost_usd != ''"))
            total = sum(r["s"] for r in rs)
            kinds = " · ".join(f"{ {'stars': '⭐', 'premium': '💎', 'gift': '🎁'}.get(r['kind'], r['kind'])} {r['n']}" for r in rs)
            topups = c.execute(f"SELECT COALESCE(SUM(amount),0) FROM topups WHERE status = 'paid' AND resolved_at >= {since}").fetchone()[0]
            out.append(f"\n<b>{title}</b>: {fmt(total)} с. ({kinds or 'нет заказов'})\n"
                       f"Закупка ≈ {fmt(int(cost * rate * 100))} с. · прибыль ≈ <b>{fmt(total - int(cost * rate * 100))} с.</b>\n"
                       f"Пополнений: {fmt(topups)} с.")
        bal = c.execute("SELECT COALESCE(SUM(balance),0) FROM users").fetchone()[0]
        out.append(f"\nНа балансах клиентов: {fmt(bal)} с.\n<i>Закупка — без подарков (их оплачивают Stars бота).</i>")
        self.show(uid, mid, "\n".join(out), [[b("🔄", "a:st"), b("← Панель", "a:home")]])

    # ── настройки ──
    def a_set(self, uid, mid, p) -> None:
        c = self.conn
        own = int(uid) in self.config.admin_ids
        admins = shop.admin_list(c, self.config)
        text = (f"⚙️ <b>Настройки</b>\nПродажи: {'⏸ на паузе' if shop.paused(c) else '▶️ работают'}\n"
                f"Мин. пополнение: {fmt(shop.min_topup(c))} с.\nПоддержка: {esc(self.config.support or '—')}\n"
                f"Админы: {', '.join(str(a) for a in admins)}")
        kb = [[b("▶️ Возобновить продажи" if shop.paused(c) else "⏸ Пауза продаж", "a:pause")],
              [b("💵 Мин. пополнение", "a:pset:min"), b("✉️ Поддержка", "a:pset:support")]]
        if own:
            kb.append([b("➕ Добавить админа", "a:addadm")])
            kb += [[b(f"➖ Убрать {a}", f"a:deladm:{a}")] for a in admins if a not in self.config.admin_ids]
        kb.append([b("💳 Карты", "a:cards"), b("← Панель", "a:home")])
        self.show(uid, mid, text, kb)

    def a_pause(self, uid, mid, p) -> None:
        db.set_setting(self.conn, "paused", "" if shop.paused(self.conn) else "1")
        self.a_set(uid, mid, p)

    def a_addadm(self, uid, mid, p) -> None:
        if int(uid) not in self.config.admin_ids:
            return
        self.set_state(uid, "addadm", mid=mid)
        self.show(uid, mid, "Telegram ID нового админа (число). Он должен хотя бы раз нажать /start в боте.", [[b("← Отмена", "a:set")]])

    def a_deladm(self, uid, mid, p) -> None:
        if int(uid) not in self.config.admin_ids:
            return
        saved = [int(x) for x in json.loads(db.get_setting(self.conn, "admins", "[]")) if int(x) != int(p[2])]
        db.set_setting(self.conn, "admins", json.dumps(saved))
        self.a_set(uid, mid, p)

    # ── ответы админа текстом ──
    def admin_text(self, uid: int, text: str, state: str, d: dict) -> bool:
        c = self.conn
        say = lambda t, kb=None: self.bot.send(uid, t, kb)  # noqa: E731
        try:
            if state == "price":
                v = to_diram(text)
                if not 1 <= v <= 100_000_000:
                    raise ValueError
                shop.set_fixed(c, d["key"], v)
                self.set_state(uid)
                it = self._item(d["key"])
                say(f"✅ {self._title(it) if it else d['key']} = <b>{fmt(v)} с.</b>", [[b("← К товару", f"a:pk:{d['key']}"), b("💲 Цены", "a:pr")]])
            elif state == "addpack":
                parts = text.replace(",", ".").split()
                qty = int(parts[0])
                s = shop.catalog(c, everything=True)["stars"] or {"min": 50, "max": 10000}
                if not s["min"] <= qty <= s["max"]:
                    return say(f"Количество — от {s['min']} до {s['max']}.") or True
                shop.set_star_packs(c, shop.star_packs(c) + [qty])
                if len(parts) > 1:
                    shop.set_fixed(c, f"stars:{qty}", to_diram(parts[1]))
                self.set_state(uid)
                say(f"✅ Пакет {qty} ⭐ добавлен.", [[b("⭐ Пакеты", "a:ps")]])
            elif state == "set":
                what = d["what"]
                if what == "rate":
                    v = Decimal(text.replace(",", "."))
                    if not Decimal(5) <= v <= Decimal(30):
                        return say("Курс — от 5 до 30 сомони за $1.") or True
                    db.set_setting(c, "rate", str(v))
                elif what == "markup":
                    v = Decimal(text.replace(",", ".").rstrip("%"))
                    if not Decimal(0) <= v <= Decimal(100):
                        return say("Наценка — от 0 до 100%.") or True
                    db.set_setting(c, "markup", str(v))
                elif what == "giftstar":
                    v = to_diram(text)
                    db.set_setting(c, "gift_star_diram", str(v) if v > 0 else "")
                elif what == "min":
                    v = to_diram(text)
                    if not 100 <= v <= 5_000_000:
                        return say("От 1 до 50 000 сомони.") or True
                    db.set_setting(c, "min_topup", str(v))
                elif what == "support":
                    self.config.support = text.strip()[:100]
                    db.set_setting(c, "support", self.config.support)
                self.set_state(uid)
                say("✅ Сохранено.", [[b("💲 Цены", "a:pr"), b("⚙️ Настройки", "a:set"), b("← Панель", "a:home")]])
            elif state == "card":
                if len(text.strip()) < 6:
                    return say("Слишком коротко — впишите номер и имя.") or True
                c.execute("INSERT INTO cards (method, details, created_at) VALUES (?, ?, ?)", (d["method"], text.strip()[:300], db.now()))
                self.set_state(uid)
                say("✅ Карта добавлена.", [[b("💳 Карты", "a:cards")]])
            elif state == "find":
                q = text.strip().lstrip("@")
                u = c.execute("SELECT id FROM users WHERE id = ? OR lower(username) = lower(?)", (int(q) if q.isdigit() else -1, q)).fetchone()
                if u is None:
                    return say("Не нашёл. Напишите ID или @username ещё раз.") or True
                self.set_state(uid)
                self.a_u(uid, None, ["a", "u", str(u[0])])
            elif state == "ofind":
                self.set_state(uid)
                self.a_o(uid, None, ["a", "o", str(int(text.strip().lstrip("№").strip()))])
            elif state == "give":
                amount, _, note = text.strip().partition(" ")
                with db.tx(c):
                    after = shop.move(c, d["target"], to_diram(amount), note.strip()[:120] or "Изменено администратором", "admin")
                self.set_state(uid)
                if note.strip():
                    self.bot.safe("sendMessage", chat_id=d["target"], text=f"💰 Баланс изменён: {amount} с. — {note.strip()[:120]}")
                say(f"✅ Баланс клиента: {fmt(after)} с.", [[b("👤 Клиент", f"a:u:{d['target']}")]])
            elif state == "dm":
                self.bot.safe("sendMessage", chat_id=d["target"], text=f"✉️ {esc(self.config.name)}:\n{esc(text)}", parse_mode="HTML")
                self.set_state(uid)
                say("✅ Отправлено.", [[b("👤 Клиент", f"a:u:{d['target']}")]])
            elif state == "bc":
                db.set_setting(c, "bc_draft", text[:3500])
                self.set_state(uid)
                say("Так увидят клиенты:")
                self.bot.safe("sendMessage", chat_id=uid, text=text[:3500], parse_mode="HTML")
                say("Отправить всем?", [[b("📢 Отправить", "a:bcgo"), b("✖ Отмена", "a:home")]])
            elif state == "reject":
                self._reject(uid, int(d["tid"]), text.strip()[:200])
            elif state == "addadm":
                new = int(text.strip())
                saved = {int(x) for x in json.loads(db.get_setting(c, "admins", "[]"))} | {new}
                db.set_setting(c, "admins", json.dumps(sorted(saved)))
                self.set_state(uid)
                say(f"✅ {new} теперь админ.", [[b("⚙️ Настройки", "a:set")]])
            else:
                return False
        except (ValueError, InvalidOperation, TypeError, KeyError):
            say("Не понял — напишите число, например 95. Или нажмите «Отмена».")
        except shop.ShopError as exc:
            say("❌ " + esc(str(exc)))
        return True
