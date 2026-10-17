"""Бот мини-приложения Stars / Premium / Подарки (DONATIX_GIFT_BOT_TOKEN).

Что умеет:
  /start              — кнопка «Открыть магазин» (мини-приложение /tg) и кнопка меню бота;
  /start g_<token>    — получатель подарка от друга: запоминаем его ID, подарок уходит;
  /topup 500          — только админу: счёт на 500 ⭐ (Telegram Stars, XTR) — так пополняется баланс бота;
  pre_checkout_query  — подтверждаем за 10 секунд (только счета /topup);
  successful_payment  — «баланс бота пополнен».
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from . import db, tggifts
from .config import Config

log = logging.getLogger("donatix.giftbot")
POLL_SECONDS = 25
TOPUP_MAX = 10_000


def admin_ids(config: Config) -> set[str]:
    raw = ",".join(str(x) for x in (config.alert_telegram_chat_id, config.support_admin_id, config.shop_admin_ids))
    return {x.strip() for x in raw.split(",") if x.strip().lstrip("-").isdigit()}


def app_url(config: Config) -> str:
    return f"{config.base_url.rstrip('/')}/tg"


T = {
    "ru": {"hello": "👋 Привет, {name}!\n\n⭐ Telegram Stars, 💎 Premium и 🎁 подарки — оплата в сомони, выдача сразу.\n"
                    "Нажмите кнопку ниже 👇",
           "open": "🛍 Открыть магазин",
           "claimed": "🎁 {name}, вам подарок ⭐{stars}! Отправляем — придёт через несколько секунд.",
           "claim_old": "Этот подарок уже получен или ссылка устарела.",
           "foot": "Donatix — независимый сервис, не связан с Telegram."},
    "tj": {"hello": "👋 Салом, {name}!\n\n⭐ Telegram Stars, 💎 Premium ва 🎁 тӯҳфаҳо — пардохт бо сомонӣ, фавран.\n"
                    "Тугмаи поёнро пахш кунед 👇",
           "open": "🛍 Кушодани мағоза",
           "claimed": "🎁 {name}, ба шумо тӯҳфа ⭐{stars}! Фиристода мешавад — дар чанд сония мерасад.",
           "claim_old": "Ин тӯҳфа аллакай гирифта шудааст ё пайванд кӯҳна шудааст.",
           "foot": "Donatix — хизматрасонии мустақил, бо Telegram алоқаманд нест."},
}


def lang_of(tg: dict[str, Any]) -> str:
    return "ru" if (tg.get("language_code") or "").startswith("ru") else "tj"


class GiftBot:
    def __init__(self, config: Config):
        self.config = config
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="donatix-giftbot", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def api(self, method: str, **payload: Any) -> Any:
        return tggifts.call(self.config, method, timeout=POLL_SECONDS + 10, **payload)

    def _setup(self) -> None:
        try:
            self.api("deleteWebhook", drop_pending_updates=False)
            me = self.api("getMe") or {}
            conn = db.connect(self.config.db_path)
            try:
                if me.get("username"):
                    db.set_setting(conn, "gifts.bot_username", me["username"])
            finally:
                conn.close()
            # Кнопка меню бота сразу открывает мини-приложение
            self.api("setChatMenuButton", menu_button={"type": "web_app", "text": "Donatix",
                                                       "web_app": {"url": app_url(self.config)}})
            self.api("setMyCommands", commands=[{"command": "start", "description": "Мағоза / Магазин"}])
            log.info("бот мини-приложения запущен: @%s", me.get("username"))
        except Exception as exc:  # noqa: BLE001
            log.warning("бот мини-приложения: %s", exc)

    def _run(self) -> None:
        self._setup()
        conn = db.connect(self.config.db_path)
        tggifts.ensure(conn)
        offset = int(db.get_setting(conn, "gifts.tg_offset", "0") or 0)
        try:
            while not self._stop.is_set():
                try:
                    updates = self.api("getUpdates", offset=offset, timeout=POLL_SECONDS,
                                       allowed_updates=["message", "pre_checkout_query"]) or []
                except Exception as exc:  # noqa: BLE001
                    log.warning("бот мини-приложения: %s", exc)
                    self._stop.wait(10)
                    continue
                for upd in updates:
                    offset = max(offset, int(upd["update_id"]) + 1)
                    try:
                        self.handle(conn, upd)
                    except Exception:  # noqa: BLE001
                        log.exception("бот мини-приложения: обработка %s", upd.get("update_id"))
                if updates:
                    db.set_setting(conn, "gifts.tg_offset", str(offset))
        finally:
            conn.close()

    # ── входящие ──
    def handle(self, conn, upd: dict[str, Any]) -> None:
        if "pre_checkout_query" in upd:
            q = upd["pre_checkout_query"]
            ok = self._topup_payload(q.get("invoice_payload")) is not None and str(q["from"]["id"]) in admin_ids(self.config)
            self.api("answerPreCheckoutQuery", pre_checkout_query_id=q["id"], ok=ok,
                     error_message=None if ok else "Счёт устарел.")
            return
        msg = upd.get("message") or {}
        chat = msg.get("chat") or {}
        if chat.get("type") != "private":
            return
        tg = msg.get("from") or {}
        tggifts.remember_user(conn, tg)
        lang = lang_of(tg)
        if msg.get("successful_payment"):
            sp = msg["successful_payment"]
            n = self._topup_payload(sp.get("invoice_payload"))
            if n is not None:
                bal = tggifts.star_balance(self.config)
                self.api("sendMessage", chat_id=chat["id"],
                         text=f"✅ Баланс бота пополнен на ⭐{sp.get('total_amount', n)}."
                              + (f" Сейчас на боте ⭐{bal}." if bal is not None else ""))
            return
        text = (msg.get("text") or "").strip()
        if text.startswith("/topup"):
            self.topup(chat["id"], tg, text)
            return
        start = text.split(maxsplit=1)[1] if text.startswith("/start ") else ""
        if start.startswith("g_"):
            o = tggifts.claim_link(conn, start[2:], tg)
            if o and o.get("claimed"):
                self.api("sendMessage", chat_id=chat["id"],
                         text=T[lang]["claimed"].format(name=tg.get("first_name") or "", stars=o["star_count"]))
            elif o:
                self.api("sendMessage", chat_id=chat["id"], text=T[lang]["claim_old"])
        self.welcome(chat["id"], tg, lang)

    def welcome(self, chat_id: int, tg: dict[str, Any], lang: str) -> None:
        self.api("sendMessage", chat_id=chat_id, parse_mode="HTML", disable_web_page_preview=True,
                 text=T[lang]["hello"].format(name=(tg.get("first_name") or "").replace("<", "")) +
                 f"\n\n<i>{T[lang]['foot']}</i>",
                 reply_markup={"inline_keyboard": [[{"text": T[lang]["open"],
                                                     "web_app": {"url": app_url(self.config)}}]]})

    def topup(self, chat_id: int, tg: dict[str, Any], text: str) -> None:
        if str(tg.get("id")) not in admin_ids(self.config):
            return
        parts = text.split()
        try:
            n = int(parts[1]) if len(parts) > 1 else 0
        except ValueError:
            n = 0
        if not 1 <= n <= TOPUP_MAX:
            bal = tggifts.star_balance(self.config)
            self.api("sendMessage", chat_id=chat_id,
                     text=f"Баланс бота: ⭐{bal if bal is not None else '?'}.\nПополнить: /topup 500 (от 1 до {TOPUP_MAX}).")
            return
        self.api("sendInvoice", chat_id=chat_id, title=f"Пополнение бота на {n} ⭐",
                 description="Stars для отправки подарков покупателям Donatix.",
                 payload=tggifts.payload_topup(n), provider_token="", currency="XTR",
                 prices=[{"label": f"{n} Stars", "amount": n}])

    @staticmethod
    def _topup_payload(raw: Any) -> int | None:
        try:
            data = json.loads(raw or "")
        except ValueError:
            return None
        return int(data["n"]) if isinstance(data, dict) and data.get("t") == "topup" else None
