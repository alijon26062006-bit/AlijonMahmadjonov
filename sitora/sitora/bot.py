"""Бот: /start с картинкой и кнопкой мини-приложения, подарок по ссылке, чеки и команды админа.

Админ — Telegram ID из SITORA_ADMIN_IDS. Команды админа (/help в боте):
  /admin                 — кнопка админ-панели (всё главное — там)
  /stats                 — сводка текстом
  /rate 11.2             — курс сомони за 1 USD
  /markup 10             — наценка, %
  /giftstar 0.25         — цена 1 звезды подарка в сомони (пусто — как у Stars)
  /card add alif 4444 5555 6666 7777 · Али В.   — карта для оплаты (alif | dc | card)
  /cards                 — список карт · /card off 3 — выключить карту № 3
  /give 123456789 50     — изменить баланс клиента (сомони; минус — списать)
  /find 15               — заказ № 15 · /find t15 — пополнение № 15
  /fundgifts 500         — счёт на 500 ⭐ — пополнить баланс бота для подарков
"""
from __future__ import annotations

import json
import logging
import threading
from decimal import Decimal, InvalidOperation
from pathlib import Path

from . import db, shop
from .botui import Ui
from .config import ROOT, Config
from .money import fmt, to_diram
from .supplier import Supplier
from .tg import Bot, TgError

log = logging.getLogger(__name__)
START_IMG = ROOT / "static" / "start.png"

WELCOME = ("<b>{name}</b> — Stars, Premium ва тӯҳфаҳои Telegram\n"
           "Ситораҳо ва Premium-ро дар як дақиқа харед: бастаро интихоб кунед, @username нависед ва пардохт кунед.\n\n"
           "Звёзды, Premium и подарки Telegram за минуту: откройте магазин, выберите пакет, "
           "укажите @username и оплатите.\n\n👇 <b>Магазинро кушоед · Откройте магазин</b>")


class Handler:
    def __init__(self, config: Config, bot: Bot, supplier: Supplier | None = None):
        self.config, self.bot, self.supplier = config, bot, supplier
        self.conn = db.connect(config.db_path)
        self.username = ""
        self.ui = Ui(config, bot, self.conn, supplier)
        config.support = db.get_setting(self.conn, "support") or config.support   # поддержку можно сменить в панели

    # ── запуск ──
    def setup(self) -> None:
        me = self.bot.safe("getMe") or {}
        self.username = me.get("username", "")
        db.set_setting(self.conn, "bot_username", self.username)
        app = self.config.base_url + "/app"
        self.bot.safe("setChatMenuButton", menu_button={"type": "web_app", "text": "Магазин",
                                                          "web_app": {"url": app}})
        self.bot.safe("setMyCommands", commands=[{"command": "start", "description": "Меню · Мағоза"},
                                                 {"command": "orders", "description": "Мои заказы · Фармоишҳо"},
                                                 {"command": "topup", "description": "Пополнить · Пур кардан"},
                                                 {"command": "help", "description": "Помощь · Ёрӣ"}])

    def open_button(self, text: str = "Открыть магазин · Магазинро кушоед") -> list:
        return [[{"text": text, "web_app": {"url": self.config.base_url + "/app"}}]]

    def admin_button(self) -> list:
        return [[{"text": "⚙️ Админ-панель", "web_app": {"url": self.config.base_url + "/app#admin"}}]]

    # ── входящие ──
    def handle(self, upd: dict) -> None:
        if "callback_query" in upd:
            return self.on_button(upd["callback_query"])
        if "pre_checkout_query" in upd:
            q = upd["pre_checkout_query"]
            self.bot.safe("answerPreCheckoutQuery", pre_checkout_query_id=q["id"], ok=True)
            return
        msg = upd.get("message") or {}
        user = msg.get("from") or {}
        if not user.get("id") or (msg.get("chat") or {}).get("type") != "private":
            return
        shop.touch_user(self.conn, user)
        if msg.get("successful_payment"):
            sp = msg["successful_payment"]
            self.bot.send(user["id"], f"⭐ Баланс бота пополнен на {sp.get('total_amount')} Stars — подарки можно отправлять.")
            return
        uid = user["id"]
        state, data = self.ui.state(uid)
        if msg.get("photo") or msg.get("document"):
            return self.on_file(uid, msg, state)
        text = (msg.get("text") or "").strip()
        cmd, _, arg = text.partition(" ")
        cmd = cmd.split("@")[0].lower()
        if cmd == "/start":
            self.ui.set_state(uid)
            return self.start(user, arg.strip())
        admin = shop.is_admin(self.conn, self.config, uid)
        if not cmd.startswith("/") and state:
            if admin and self.ui.admin_text(uid, text, state, data):
                return
            if self.ui.client_text(uid, text, state, data):
                return
        if cmd.startswith("/"):
            self.ui.set_state(uid)
        if admin and cmd in ("/panel", "/admin"):
            return self.ui.a_home(uid, None)
        if admin and cmd.startswith("/") and cmd not in ("/help", "/orders", "/topup", "/menu"):
            return self.admin(uid, cmd, arg.strip())
        if cmd == "/orders":
            return self.ui.orders(uid, None)
        if cmd == "/topup":
            return self.ui.client(uid, 0, "c:top")
        if cmd == "/help":
            return self.ui.client(uid, 0, "c:help")
        self.ui.home(uid)

    def on_file(self, uid: int, msg: dict, state: str) -> None:
        """Фото или PDF чека прямо в чат бота."""
        if state != "receipt":
            t = self.ui.t(uid)
            return self.bot.send(uid, "Чтобы пополнить баланс, нажмите «Пополнить» — потом пришлите чек.",
                                 [[{"text": t["topup"], "callback_data": "c:top"}]])
        if msg.get("photo"):
            file_id = msg["photo"][-1]["file_id"]
        else:
            file_id = msg["document"]["file_id"]
        try:
            data = self.bot.download(file_id, limit=10 * 1024 * 1024)
        except TgError:
            return self.bot.send(uid, "Не удалось получить файл — пришлите чек ещё раз (фото или PDF до 10 МБ).")
        ext = sniff(data)
        if not ext:
            return self.bot.send(uid, "Чек — фото (JPG, PNG, WEBP) или PDF.")
        self.ui.receipt(uid, data, ext)

    def start(self, user: dict, payload: str) -> None:
        got = []
        if payload.startswith("g_"):
            res, o = shop.claim_gift(self.conn, payload[2:], user)
            if res == "ok":
                got.append(o)
            elif res == "notyours":
                self.bot.send(user["id"], "🔒 Этот подарок предназначен другому человеку — открыть его может только получатель.\n"
                                          "Ин тӯҳфа барои шахси дигар аст — онро танҳо гиранда кушода метавонад.")
            elif res == "buyer":
                self.bot.send(user["id"], f"Это ссылка на ваш подарок для @{o['recipient']}. Отправьте её получателю — "
                                          "сработает только у него.\nИн пайвандро ба гиранда фиристед.")
            elif res == "gone":
                self.bot.send(user["id"], "Эта ссылка уже использована или устарела.")
        for o in got + shop.claim_waiting(self.conn, user):   # подарки на его @username (со ссылкой и без)
            self.bot.send(user["id"], "🎁 Вам подарок! Он придёт через несколько секунд.\nБа шумо тӯҳфа! Пас аз чанд сония мерасад.")
            self.bot.safe("sendMessage", chat_id=o["user_id"], text=f"🎁 @{o['recipient']} зашёл в бота — подарок № {o['id']} отправляется.")
        caption = WELCOME.format(name=self.config.name)
        t = self.ui.t(user["id"])
        markup = {"inline_keyboard": [[{"text": t["stars"], "callback_data": "c:stars"}, {"text": t["premium"], "callback_data": "c:prem"}],
                                      [{"text": t["gifts"], "callback_data": "c:gifts"}, {"text": t["topup"], "callback_data": "c:top"}],
                                      [{"text": t["menu"], "callback_data": "c:home"}]] + self.open_button()
                  + ([[{"text": "⚙️ Админ-панель", "callback_data": "a:home"}]] if shop.is_admin(self.conn, self.config, user["id"]) else [])}
        file_id = db.get_setting(self.conn, "start_photo")
        try:
            if file_id:
                self.bot.call("sendPhoto", chat_id=user["id"], photo=file_id, caption=caption, parse_mode="HTML", reply_markup=markup)
                return
            if START_IMG.exists():
                res = self.bot.call("sendPhoto", files={"photo": ("start.png", START_IMG.read_bytes(), "image/png")},
                                    chat_id=user["id"], caption=caption, parse_mode="HTML", reply_markup=markup)
                photos = (res or {}).get("photo") or []
                if photos:
                    db.set_setting(self.conn, "start_photo", photos[-1]["file_id"])
                return
        except TgError as exc:
            log.warning("start photo: %s", exc)
            db.set_setting(self.conn, "start_photo", "")
        self.bot.send(user["id"], caption, self.open_button())

    # ── кнопки «Зачислить / Отклонить» ──
    def on_button(self, cq: dict) -> None:
        who = cq.get("from") or {}
        data = cq.get("data") or ""
        mid = ((cq.get("message") or {}).get("message_id")) or None
        if data.startswith("c:") and who.get("id"):
            self.bot.safe("answerCallbackQuery", callback_query_id=cq["id"])
            shop.touch_user(self.conn, who)
            return self.ui.client(who["id"], mid, data)
        if data.startswith("a:") and shop.is_admin(self.conn, self.config, who.get("id")):
            self.bot.safe("answerCallbackQuery", callback_query_id=cq["id"])
            return self.ui.admin(who["id"], mid, data)
        if not shop.is_admin(self.conn, self.config, who.get("id")) or not data.startswith("tp:"):
            self.bot.safe("answerCallbackQuery", callback_query_id=cq["id"], text="Нет доступа")
            return
        _, act, tid = data.split(":")
        t = finish_topup(self.config, self.bot, self.conn, int(tid), act == "ok", who.get("first_name") or str(who["id"]))
        self.bot.safe("answerCallbackQuery", callback_query_id=cq["id"], text="Готово" if t else "Уже решено")

    # ── админ ──
    def admin(self, chat: int, cmd: str, arg: str) -> None:
        c = self.conn
        say = lambda t: self.bot.send(chat, t)   # noqa: E731
        try:
            if cmd in ("/help", "/stats"):
                users = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                today = c.execute("SELECT COUNT(*), COALESCE(SUM(price),0) FROM orders WHERE created_at >= date('now') "
                                  "AND status NOT IN ('failed')").fetchone()
                waiting = c.execute("SELECT COUNT(*) FROM topups WHERE status = 'pending'").fetchone()[0]
                stuck = c.execute("SELECT COUNT(*) FROM orders WHERE status = 'attention'").fetchone()[0]
                sup = ""
                if self.supplier:
                    try:
                        sup = f"\nБаланс у поставщика: ${self.supplier.balance()}"
                    except Exception as exc:  # noqa: BLE001
                        sup = f"\nБаланс у поставщика: нет связи ({str(exc)[:60]})"
                stars = (self.bot.safe("getMyStarBalance") or {}).get("amount", "—")
                say(f"<b>{self.config.name} · админ</b>\nКлиентов: {users}\nЗаказов сегодня: {today[0]} на {fmt(today[1])} с.\n"
                    f"Чеков ждут: {waiting} · Зависших заказов: {stuck}{sup}\nStars у бота (подарки): {stars}\n"
                    f"Курс: {shop.rate(c)} · Наценка: {shop.markup(c)}%\n\n" + __doc__.split("Команды админа (/help в боте):")[1])
            elif cmd == "/rate":
                v = Decimal(arg.replace(",", "."))
                if not Decimal(5) <= v <= Decimal(30):
                    raise ValueError
                db.set_setting(c, "rate", str(v)); say(f"Курс: 1 USD = {v} сомони")
            elif cmd == "/markup":
                v = Decimal(arg.replace(",", "."))
                if not Decimal(0) <= v <= Decimal(100):
                    raise ValueError
                db.set_setting(c, "markup", str(v)); say(f"Наценка: {v}%")
            elif cmd == "/giftstar":
                if not arg:
                    db.set_setting(c, "gift_star_diram", ""); say("Цена звезды подарка — как у Stars.")
                else:
                    d = to_diram(arg); db.set_setting(c, "gift_star_diram", str(d)); say(f"1 звезда подарка = {fmt(d)} с.")
            elif cmd == "/card":
                sub, _, rest = arg.partition(" ")
                if sub == "add":
                    method, _, details = rest.partition(" ")
                    if method not in shop.METHODS or len(details.strip()) < 6:
                        raise ValueError
                    c.execute("INSERT INTO cards (method, details, created_at) VALUES (?, ?, ?)", (method, details.strip(), db.now()))
                    say("Карта добавлена.")
                elif sub == "off":
                    c.execute("UPDATE cards SET active = 0 WHERE id = ?", (int(rest),)); say("Карта выключена.")
                else:
                    raise ValueError
            elif cmd == "/cards":
                rows = c.execute("SELECT * FROM cards WHERE active = 1 ORDER BY method, id").fetchall()
                say("\n".join(f"№ {r['id']} · {shop.METHODS[r['method']]} · {r['details']}" for r in rows) or "Карт нет. /card add alif …")
            elif cmd == "/give":
                who, _, amount = arg.partition(" ")
                uid = int(who) if who.isdigit() else (c.execute("SELECT id FROM users WHERE lower(username)=lower(?)",
                                                              (who.lstrip("@"),)).fetchone() or [0])[0]
                with db.tx(c):
                    after = shop.move(c, uid, to_diram(amount), "Изменено администратором", "admin")
                say(f"Готово. Баланс клиента: {fmt(after)} с.")
            elif cmd == "/find":
                if arg.lower().startswith("t"):
                    t = c.execute("SELECT * FROM topups WHERE id = ?", (int(arg[1:]),)).fetchone()
                    say(f"Пополнение № {t['id']}: {fmt(t['amount'])} с. · {t['status']} · клиент {t['user_id']} · {t['created_at']}"
                        if t else "Не найдено.")
                else:
                    o = c.execute("SELECT * FROM orders WHERE id = ?", (int(arg),)).fetchone()
                    say(f"Заказ № {o['id']}: {o['title']} → @{o['recipient']} · {fmt(o['price'])} с. · {o['status']} · "
                        f"поставщик {o['supplier_order_id'] or '—'}\n{o['error']}" if o else "Не найдено.")
            elif cmd == "/fundgifts":
                n = int(arg)
                self.bot.call("sendInvoice", chat_id=chat, title="Баланс бота для подарков", description=f"{n} Stars",
                              payload=f"fund:{n}", currency="XTR", prices=[{"label": "Stars", "amount": n}])
            else:
                say("Неизвестная команда. /help")
        except (ValueError, InvalidOperation, TypeError, IndexError):
            say("Не понял. Примеры — в /help")
        except shop.ShopError as exc:
            say(str(exc))
        except TgError as exc:
            say(f"Telegram: {exc}")


def finish_topup(config: Config, bot: Bot | None, conn, topup_id: int, ok: bool, who: str, note: str = ""):
    """Решение по чеку — из бота или из админ-панели. Один раз; итог видят все админы, клиенту — сообщение."""
    t = shop.decide_topup(conn, topup_id, ok, who, note)
    if t is None:
        return None
    order = shop.run_intent(conn, t) if ok else None
    if bot is None:
        return t
    verdict = f"✅ Зачислено {fmt(t['amount'])} с. — {who}" if ok else f"❌ Отклонено — {who}"
    for m in json.loads(t["admin_msgs"] or "[]"):   # кнопки у всех админов исчезают
        bot.safe("editMessageCaption", chat_id=m[0], message_id=m[1], caption=f"Пополнение № {t['id']}\n{verdict}")
    app = {"inline_keyboard": [[{"text": "Открыть магазин", "web_app": {"url": config.base_url + "/app"}}]]}
    if ok:
        bot.safe("sendMessage", chat_id=t["user_id"], reply_markup=app, text=(
            f"✅ Баланс пополнен на {fmt(t['amount'])} с. / Баланс пур шуд."
            + (f"\n🛒 Заказ № {order['id']} оформлен: {order['title']}" if order else "")))
    else:
        bot.safe("sendMessage", chat_id=t["user_id"], text=(
            "❌ Пополнение не подтверждено" + (f": {note}" if note else ": перевод не найден")
            + ". Если это ошибка — напишите в поддержку.\nПардохт тасдиқ нашуд."))
    return t


def sniff(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:5] == b"%PDF-":
        return "pdf"
    return None


def submit_receipt(config: Config, bot: Bot | None, conn, user_id: int, tid: int, data: bytes, ext: str) -> str:
    """Чек от клиента (из бота или мини-приложения): проверить, сохранить, отправить админам. Ошибка — ShopError."""
    import hashlib
    import secrets
    from . import receipt
    t = conn.execute("SELECT * FROM topups WHERE id = ? AND user_id = ?", (tid, user_id)).fetchone()
    if t is None or t["status"] != "waiting":
        raise shop.ShopError("Заявка не найдена или уже на проверке.")
    digest = hashlib.sha256(data).hexdigest()
    if conn.execute("SELECT 1 FROM topups WHERE receipt_hash = ? AND status IN ('pending','paid')", (digest,)).fetchone():
        raise shop.ShopError("Этот чек уже присылали. / Ин чек аллакай фиристода шудааст.")
    ours = "\n".join(r["details"] for r in shop.cards(conn))   # все наши карты: клиент мог перевести на другую нашу
    seen = receipt.read(config.openai_key, config.receipt_model, data, ext, ours)
    bad = receipt.refuse(seen, ours)
    if bad:
        raise shop.ShopError(bad)
    folder = Path(config.receipts_dir)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{tid}-{secrets.token_hex(6)}.{ext}"
    (folder / name).write_bytes(data)
    note = f"получатель «{seen['recipient']}», сумма {seen.get('amount')} {seen.get('currency')}" if seen else ""
    done = conn.execute("UPDATE topups SET status = 'pending', receipt_file = ?, receipt_hash = ?, ai_note = ? "
                        "WHERE id = ? AND status = 'waiting'", (name, digest, note, tid)).rowcount
    if not done:
        raise shop.ShopError("Заявка уже на проверке.")
    if bot is not None:
        threading.Thread(target=notify_receipt, args=(config, bot, db.connect(config.db_path), tid, data, ext),
                         daemon=True).start()
    return (f"Чек получен — проверим и пополним баланс на {fmt(t['amount'])} с. "
            "/ Чек гирифта шуд — санҷида баланс пур мекунем.")


def notify_receipt(config: Config, bot: Bot, conn, topup_id: int, data: bytes, ext: str) -> None:
    """Чек — всем админам, с кнопками. ID сообщений запоминаем, чтобы показать итог у всех."""
    t = conn.execute("SELECT t.*, u.username, u.first_name FROM topups t JOIN users u ON u.id = t.user_id WHERE t.id = ?",
                     (topup_id,)).fetchone()
    card = conn.execute("SELECT details FROM cards WHERE id = ?", (t["card_id"],)).fetchone()
    cap = (f"🧾 Пополнение № {t['id']} · {fmt(t['amount'])} с.\n{shop.METHODS.get(t['method'])}: {card['details'] if card else '—'}\n"
           f"Клиент: {t['first_name']} @{t['username'] or '—'} ({t['user_id']})" + (f"\nИИ: {t['ai_note']}" if t["ai_note"] else ""))
    kb = {"inline_keyboard": [[{"text": "✅ Зачислить", "callback_data": f"tp:ok:{t['id']}"},
                               {"text": "❌ Отклонить", "callback_data": f"tp:no:{t['id']}"}]]}
    sent = []
    for a in shop.admin_list(conn, config):
        try:
            method, field = ("sendDocument", "document") if ext == "pdf" else ("sendPhoto", "photo")
            m = bot.call(method, files={field: (f"check.{ext}", data)}, chat_id=a, caption=cap[:1000], reply_markup=kb)
            sent.append([a, m["message_id"]])
        except TgError as exc:
            log.warning("чек админу %s: %s", a, exc)
    conn.execute("UPDATE topups SET admin_msgs = ? WHERE id = ?", (json.dumps(sent), topup_id))


def poll(config: Config, handler: Handler, stop: threading.Event) -> None:
    offset = 0
    handler.setup()
    while not stop.is_set():
        try:
            ups = handler.bot.call("getUpdates", offset=offset, timeout=30,
                                   allowed_updates=["message", "callback_query", "pre_checkout_query"]) or []
        except TgError as exc:
            log.warning("getUpdates: %s", exc)
            stop.wait(3)
            continue
        for u in ups:
            offset = u["update_id"] + 1
            try:
                handler.handle(u)
            except Exception:  # noqa: BLE001
                log.exception("обработка %s", u.get("update_id"))
