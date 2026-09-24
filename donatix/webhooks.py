"""Уведомления клиентам о смене статуса заказа (POST на их адрес с подписью)."""

from __future__ import annotations

import json
import logging
import sqlite3
import time

import httpx

from .orders import public_view
from .security import sign_webhook

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 5


def build(order: sqlite3.Row) -> bytes:
    body = {"event": "order.updated", "order": public_view(order)}
    return json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()


def deliver_pending(conn: sqlite3.Connection, client: httpx.Client | None = None, limit: int = 20) -> int:
    rows = conn.execute(
        "SELECT o.*, u.webhook_url, u.webhook_secret FROM orders o JOIN users u ON u.id = o.user_id "
        "WHERE o.webhook_state = 'pending' ORDER BY o.updated_at LIMIT ?",
        (limit,),
    ).fetchall()
    own = client is None
    client = client or httpx.Client(timeout=10)
    sent = 0
    try:
        for row in rows:
            if not row["webhook_url"]:
                conn.execute("UPDATE orders SET webhook_state = 'none' WHERE id = ?", (row["id"],))
                continue
            body = build(row)
            ts = str(int(time.time()))
            headers = {
                "Content-Type": "application/json",
                "X-Donatix-Timestamp": ts,
                "X-Donatix-Signature": sign_webhook(row["webhook_secret"] or "", ts, body),
            }
            ok = False
            try:
                resp = client.post(row["webhook_url"], content=body, headers=headers)
                ok = 200 <= resp.status_code < 300
            except httpx.HTTPError as exc:
                log.info("webhook %s: %s", row["public_id"], exc)
            attempts = row["webhook_attempts"] + 1
            state = "sent" if ok else ("failed" if attempts >= MAX_ATTEMPTS else "pending")
            conn.execute(
                "UPDATE orders SET webhook_state = ?, webhook_attempts = ? WHERE id = ?",
                (state, attempts, row["id"]),
            )
            sent += ok
    finally:
        if own:
            client.close()
    return sent
