"""Фоновая работа: доводит заказы, обновляет каталог, следит за балансом у поставщика."""

from __future__ import annotations

import logging
import threading
import time
from decimal import Decimal

import httpx

from . import catalog, db, orders, webhooks
from .config import Config
from .money import to_decimal
from .suppliers import Supplier

log = logging.getLogger(__name__)


def notify_admin(config: Config, text: str, buttons: list | None = None, *, html: bool = False) -> None:
    """Сообщение админу в Telegram, если настроено (с кнопками — ответ прямо из чата). Иначе — только в лог."""
    log.warning("ADMIN: %s", text)
    if not (config.alert_telegram_token and config.alert_telegram_chat_id):
        return
    from .tgbot import keyboard
    payload = {"chat_id": config.alert_telegram_chat_id, "text": text if html else f"{config.site_name}: {text}",
               "disable_web_page_preview": True}
    if html:
        payload["parse_mode"] = "HTML"
    if buttons:
        payload["reply_markup"] = keyboard(buttons)
    try:
        httpx.post(f"https://api.telegram.org/bot{config.alert_telegram_token}/sendMessage", json=payload, timeout=10)
    except httpx.HTTPError as exc:
        log.warning("не удалось отправить уведомление: %s", exc)


def notify_event(conn, config: Config, event: tuple[str, list]) -> None:
    text, buttons = event
    notify_admin(config, text, buttons, html=True)


def notify_admin_file(config: Config, caption: str, buttons: list | None, path, *, photo: bool) -> None:
    """Файл админу (чек об оплате) с подписью и кнопками. Без Telegram — только в лог."""
    log.warning("ADMIN (файл %s): %s", path, caption)
    if not (config.alert_telegram_token and config.alert_telegram_chat_id):
        return
    import json as _json

    from .tgbot import keyboard
    method, field = ("sendPhoto", "photo") if photo else ("sendDocument", "document")
    data = {"chat_id": config.alert_telegram_chat_id, "caption": caption[:1000], "parse_mode": "HTML"}
    if buttons:
        data["reply_markup"] = _json.dumps(keyboard(buttons), ensure_ascii=False)
    try:
        with open(path, "rb") as fh:
            httpx.post(f"https://api.telegram.org/bot{config.alert_telegram_token}/{method}",
                       data=data, files={field: (path.name, fh)}, timeout=30)
    except (httpx.HTTPError, OSError) as exc:
        log.warning("не удалось отправить чек админу: %s", exc)


def check_supplier_balance(conn, config: Config, supplier: Supplier) -> Decimal | None:
    try:
        balance = supplier.balance()
    except Exception as exc:  # noqa: BLE001 — причину покажем в админке, а не только в журнале
        log.warning("баланс поставщика: %s", exc)
        db.set_setting(conn, "supplier_balance_error", f"{type(exc).__name__}: {exc}"[:300])
        return None
    db.set_setting(conn, "supplier_balance_error", "")
    db.set_setting(conn, "supplier_balance", str(balance))
    db.set_setting(conn, "supplier_balance_at", db.now())
    was_low = db.get_setting(conn, "supplier_balance_low") == "1"
    is_low = balance < config.supplier_low_balance
    if is_low and not was_low:
        notify_admin(config, f"баланс у поставщика ${balance} — пополните, иначе заказы начнут падать.")
    db.set_setting(conn, "supplier_balance_low", "1" if is_low else "0")
    return balance


def attention_alert(conn, config: Config) -> None:
    """Каждый новый проблемный заказ — отдельным сообщением с кнопками."""
    from .tgbot import order_event
    last = int(db.get_setting(conn, "attention_alerted_id", "0") or 0)
    rows = conn.execute("SELECT id FROM orders WHERE status = 'attention' AND id > ? ORDER BY id LIMIT 20",
                        (last,)).fetchall()
    for r in rows:
        notify_event(conn, config, order_event(conn, r["id"]))
        last = r["id"]
    db.set_setting(conn, "attention_alerted_id", str(last))


class Worker:
    def __init__(self, config: Config, supplier: Supplier):
        self.config = config
        self.supplier = supplier
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="donatix-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        last_sync = last_balance = last_watch = 0.0
        conn = db.connect(self.config.db_path)
        try:
            while not self._stop.is_set():
                now = time.monotonic()
                try:
                    # Баланс поставщика — первым делом: раньше он ждал, пока загрузится весь каталог
                    if now - last_balance >= 300 or last_balance == 0:
                        check_supplier_balance(conn, self.config, self.supplier)
                        attention_alert(conn, self.config)
                        last_balance = now
                except Exception:
                    log.exception("баланс поставщика")
                    last_balance = now
                if now - last_sync >= self.config.catalog_sync_minutes * 60 or last_sync == 0:
                    # Каталог грузится в своём потоке: сотни запросов не должны держать заказы и баланс
                    self._start_sync()
                    last_sync = now
                if now - last_watch >= 3600 or last_watch == 0:
                    try:
                        from . import bot_watch
                        bot_watch.check(conn, self.config)  # боты без продаж: предупредить / отключить
                    except Exception:
                        log.exception("проверка ботов")
                    last_watch = now
                try:
                    from . import cryptopay
                    cryptopay.check_all(conn, self.config, min_interval=60)  # автоплатежи TRC20 / Binance
                except Exception:
                    log.exception("автоплатежи")
                try:
                    from . import rates
                    rates.refresh(conn, self.config, rates.WORKER_SECONDS)
                except Exception:
                    log.exception("курс")
                try:
                    orders.process_pending(conn, self.supplier)
                    webhooks.deliver_pending(conn)
                except Exception:
                    log.exception("воркер")
                self._stop.wait(self.config.order_poll_seconds)
        finally:
            conn.close()

    def _start_sync(self) -> None:
        def run() -> None:
            # Если каталог сейчас грузит админка — пропускаем, возьмём в следующий раз
            if not catalog.SYNC_LOCK.acquire(blocking=False):
                return
            c = db.connect(self.config.db_path)
            try:
                catalog.sync_catalog(c, self.supplier)
            except Exception:
                log.exception("обновление каталога")
            finally:
                c.close()
                catalog.SYNC_LOCK.release()
        threading.Thread(target=run, name="donatix-catalog-sync", daemon=True).start()


def supplier_balance_cached(conn) -> Decimal | None:
    value = db.get_setting(conn, "supplier_balance")
    return to_decimal(value) if value else None
