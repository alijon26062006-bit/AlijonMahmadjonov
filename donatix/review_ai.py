"""ИИ (ChatGPT) отвечает на отзывы — только по фактам из базы.

Что делает с каждым новым (или исправленным) отзывом без ответа:
1. Собирает факты: заказ отзыва и заказы, номера которых покупатель упомянул в тексте (только его собственные) —
   номер, дата, товар, ID игрока, ник (если проверяли), статус, когда выполнен или почему возвращены деньги.
2. Спрашивает ChatGPT, что это за отзыв:
   • «reply» — жалоба или вопрос про заказ (не пришло, долго, не тот ID) → ответ на языке покупателя
     ТОЛЬКО по фактам: номер заказа, дата, ID, ник, статус. Ответ сразу виден под отзывом.
   • «hide» — спам, реклама, ссылки, оскорбления, мат, бессмыслица, текст не про магазин → отзыв скрыт
     (админ видит его в «Отзывы → Все» с пометкой и может вернуть).
   • «skip» — всё остальное (похвала, пожелания, цены, мнение о сервисе) → отвечает админ сам.
   Честный плохой отзыв о заказе НЕ скрывается никогда — на него ИИ отвечает фактами.
3. Админу приходит уведомление, что сделал ИИ.

Ключ — тот же DONATIX_OPENAI_API_KEY. Выключить: DONATIX_REVIEW_AI=0.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
import time
from typing import Any

import httpx

from . import db
from .config import Config

log = logging.getLogger(__name__)

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
TIMEOUT = 30
STATUS_RU = {"completed": "выполнен", "processing": "в обработке", "attention": "в обработке",
             "failed": "не выполнен, деньги возвращены на баланс"}

PROMPT = """Ты — служба поддержки магазина игрового доната {site} ({url}). Тебе дают отзыв покупателя и ФАКТЫ из базы.
Верни ТОЛЬКО JSON: {{"action": "reply" | "hide" | "skip", "reason": "коротко по-русски, почему", "reply": "текст ответа"}}

action:
• "reply" — отзыв про конкретный заказ: не пришло / долго / пришло не на тот аккаунт / вернули деньги / вопрос о статусе.
  Ответь покупателю на ЕГО языке (таджикский, русский, английский — как написан отзыв), вежливо, 2–4 предложения.
  Используй ТОЛЬКО факты ниже: номер заказа, дату, товар, ID игрока, ник (если есть), статус. Ничего не придумывай.
  Если заказ выполнен — скажи, что он выполнен такого-то числа на такой-то ID (и ник), и попроси проверить, что это его
  аккаунт; если ID не тот — заказ ушёл туда, куда он сам указал. Если в обработке — что заказ выполняется.
  Если не выполнен — что деньги вернулись на баланс. В конце предложи написать в поддержку: {support}
  Не обещай возврат денег и не признавай вину, если факты этого не говорят.
• "hide" — ТОЛЬКО если это спам, реклама, ссылки на другие сайты, оскорбления, мат, бессмысленный набор букв
  или текст вообще не про покупку в магазине. Честный негативный отзыв о заказе или сервисе — НЕ hide, а reply/skip.
• "skip" — всё остальное: похвала, пожелания, цены, скидки, общее мнение, вопрос не про заказ. На это ответит админ.
reply пустой, если action не "reply"."""


def enabled(config: Config) -> bool:
    return bool(config.openai_api_key) and config.review_ai


def _nick(conn: sqlite3.Connection, uid: str) -> str:
    if not uid:
        return ""
    try:
        r = conn.execute("SELECT player_name FROM player_names WHERE uid = ? AND player_name IS NOT NULL "
                         "ORDER BY checked_at DESC LIMIT 1", (uid,)).fetchone()
    except sqlite3.Error:
        return ""
    return (r[0] or "")[:40] if r else ""


def _order_facts(conn: sqlite3.Connection, o: sqlite3.Row) -> dict[str, Any]:
    fields = json.loads(o["fields_json"] or "{}")
    uid = str(next((v for k, v in fields.items() if "id" in k.lower() or k in ("uid", "login")), "") or "")
    delivery = json.loads(o["delivery_json"] or "{}") if o["delivery_json"] else {}
    nick = ""
    if isinstance(delivery, dict):
        nick = str(next((delivery[k] for k in ("player_name", "nickname", "account_name", "username")
                         if delivery.get(k)), "") or "")
    return {"номер": o["public_id"], "товар": o["product_name"], "создан": o["created_at"][:16].replace("T", " "),
            "выполнен": (o["completed_at"] or "")[:16].replace("T", " "), "статус": STATUS_RU.get(o["status"], o["status"]),
            "данные_для_пополнения": fields, "ник": nick or _nick(conn, uid),
            "причина_отказа": (o["error"] or "")[:150] if o["status"] == "failed" else ""}


def facts(conn: sqlite3.Connection, r: sqlite3.Row) -> dict[str, Any]:
    out: dict[str, Any] = {"заказы": []}
    seen = set()
    if r["order_id"]:
        o = conn.execute("SELECT * FROM orders WHERE id = ?", (r["order_id"],)).fetchone()
        if o is not None:
            out["заказы"].append(_order_facts(conn, o))
            seen.add(o["id"])
    # Номера заказов из текста («#21433», «dx-21433», «заказ 21433») — только свои заказы покупателя
    for num in re.findall(r"(?:dx-?|#|№|заказ\w*\s*|фармоиш\w*\s*#?)(\d{1,9})", r["text"], flags=re.I)[:5]:
        o = conn.execute("SELECT * FROM orders WHERE user_id = ? AND (public_id = ? OR id = ?)",
                         (r["user_id"], f"dx-{num}", int(num))).fetchone()
        if o is not None and o["id"] not in seen:
            out["заказы"].append(_order_facts(conn, o))
            seen.add(o["id"])
    stat = conn.execute("SELECT COUNT(*), SUM(status = 'completed') FROM orders WHERE user_id = ?",
                        (r["user_id"],)).fetchone()
    out["покупатель"] = {"всего_заказов": stat[0], "выполнено": stat[1] or 0}
    return out


def ask(config: Config, review: sqlite3.Row, data: dict[str, Any],
        transport: httpx.BaseTransport | None = None) -> dict[str, Any] | None:
    system = PROMPT.format(site=config.site_name, url=config.base_url, support=f"{config.base_url}/panel/support")
    user = json.dumps({"оценка": review["rating"], "отзыв": review["text"], "факты": data}, ensure_ascii=False)
    body = {"model": config.support_model, "temperature": 0.2, "max_tokens": 500,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    try:
        with httpx.Client(timeout=TIMEOUT, transport=transport) as client:
            resp = client.post(OPENAI_URL, json=body, headers={"Authorization": f"Bearer {config.openai_api_key}"})
        if resp.status_code != 200:
            log.warning("отзывы ИИ: OpenAI %s %s", resp.status_code, resp.text[:200])
            return None
        raw = json.loads(resp.json()["choices"][0]["message"]["content"])
    except Exception:  # noqa: BLE001 — ИИ не должен мешать сайту; отзыв останется админу
        log.exception("отзывы ИИ: нет ответа")
        return None
    action = str(raw.get("action") or "").lower()
    if action not in ("reply", "hide", "skip"):
        action = "skip"
    reply = re.sub(r"[ \t]+", " ", str(raw.get("reply") or "")).strip()[:1200]
    if action == "reply" and len(reply) < 10:
        action = "skip"
    return {"action": action, "reason": str(raw.get("reason") or "")[:200], "reply": reply}


def process(conn: sqlite3.Connection, config: Config, rid: int,
            transport: httpx.BaseTransport | None = None) -> str:
    """Обработать один отзыв. Вернёт, что сделано: reply / hide / skip / error."""
    from . import reviews
    from .notify import notify
    r = conn.execute("SELECT * FROM reviews WHERE id = ?", (rid,)).fetchone()
    if r is None or r["reply_text"] or r["ai_state"] != "pending":
        return "skip"
    got = ask(config, r, facts(conn, r), transport)
    if got is None:
        conn.execute("UPDATE reviews SET ai_state = 'error', updated_at = ? WHERE id = ?", (db.now(), rid))
        return "error"
    # Пока ChatGPT думал, покупатель мог исправить отзыв или админ — ответить: тогда ничего не трогаем
    now = conn.execute("SELECT text, reply_text, ai_state FROM reviews WHERE id = ?", (rid,)).fetchone()
    if now is None or now["text"] != r["text"] or now["reply_text"] or now["ai_state"] != "pending":
        return "skip"
    admins = [a["id"] for a in conn.execute("SELECT id FROM users WHERE role = 'admin'")]
    act, note = got["action"], got["reason"]
    if act == "reply":
        reviews.reply(conn, config, None, rid, got["reply"])
        msg = f"ИИ ответил на отзыв {'★' * r['rating']}: {got['reply'][:120]}"
    elif act == "hide":
        reviews.set_hidden(conn, rid, True)
        msg = f"ИИ скрыл отзыв ({note or 'спам'}): «{r['text'][:80]}». Вернуть — Отзывы → Все → «Показать»."
    else:
        msg = ""
    conn.execute("UPDATE reviews SET ai_state = ?, ai_note = ?, updated_at = ? WHERE id = ?",
                 (act, note, db.now(), rid))
    for a in admins if msg else []:
        notify(conn, None, a, msg, f"/admin/reviews?show=all#r{rid}")
    return act


def run_pending(conn: sqlite3.Connection, config: Config, limit: int = 3) -> None:
    if not enabled(config):
        return
    for r in conn.execute("SELECT id FROM reviews WHERE ai_state = 'pending' AND reply_text IS NULL "
                          "ORDER BY id LIMIT ?", (limit,)).fetchall():
        process(conn, config, r["id"])


_lock = threading.Lock()
_last = {"at": 0.0}


def maybe_run(conn: sqlite3.Connection, config: Config) -> None:
    with _lock:
        if time.monotonic() - _last["at"] < 10:
            return
        _last["at"] = time.monotonic()
    run_pending(conn, config)
