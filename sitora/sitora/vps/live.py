"""Живая аналитика: агент шлёт данные раз в секунду → браузеры владельца получают их сразу.

История — точки, усреднённые за минуту, в таблице metrics. Показываем
1 час (по минутам), 24 часа (по 5 минут), 7 дней (по 30 минут). Старше 8 дней — удаляем.
"""
from __future__ import annotations

import json
import logging
import math

from .store import now as _now

log = logging.getLogger(__name__)

RANGES = {"1h": (3600, 60), "24h": (86400, 300), "7d": (7 * 86400, 1800)}
KEEP_DAYS = 8
FIELDS = ("cpu", "ram", "disk", "rd", "wr", "rx", "tx", "load1")


def _num(value, lo=0.0, hi=1e15) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return min(max(v, lo), hi) if math.isfinite(v) else 0.0


def clean(data: dict) -> dict:
    """Агент — на чужом сервере. Берём только числа в разумных пределах."""
    out = {k: _num(data.get(k)) for k in ("ram_used", "ram_total", "swap_used", "swap_total",
                                          "disk_used", "disk_total", "disk_read", "disk_write",
                                          "net_in", "net_out", "uptime", "conns")}
    out["cpu"] = _num(data.get("cpu"), 0, 100)
    out["cores"] = [_num(c, 0, 100) for c in (data.get("cores") or [])[:256]]
    load = data.get("load") or [0, 0, 0]
    out["load"] = [_num(x, 0, 1e6) for x in list(load)[:3]] + [0.0] * (3 - len(list(load)[:3]))
    top = []
    for p in (data.get("top") or [])[:10]:
        if isinstance(p, dict):
            top.append({"pid": int(_num(p.get("pid"), 0, 1e9)), "name": str(p.get("name", ""))[:40],
                        "cpu": _num(p.get("cpu"), 0, 100 * 256), "rss": _num(p.get("rss"))})
    out["top"] = top
    return out


class Hub:
    def __init__(self):
        self.latest: dict[int, dict] = {}
        self.subs: dict[int, set] = {}
        self.agents: dict[int, object] = {}
        self._bucket: dict[int, list] = {}

    def online(self, sid: int) -> bool:
        return sid in self.agents

    def subscribe(self, sid: int, ws) -> None:
        self.subs.setdefault(sid, set()).add(ws)

    def unsubscribe(self, sid: int, ws) -> None:
        self.subs.get(sid, set()).discard(ws)

    async def publish(self, ctx, sid: int, raw: dict, t: int | None = None) -> dict:
        data = clean(raw)
        t = _now() if t is None else t
        data["t"] = t
        data["live"] = True
        self.latest[sid] = data
        self._accumulate(ctx, sid, data, t)
        text = json.dumps({"type": "sample", "server": sid, "data": data}, separators=(",", ":"))
        for ws in list(self.subs.get(sid, ())):
            try:
                await ws.send_text(text)
            except Exception:  # noqa: BLE001 — браузер закрылся
                self.unsubscribe(sid, ws)
        return data

    def _accumulate(self, ctx, sid: int, d: dict, t: int) -> None:
        minute = t - t % 60
        ram = 100 * d["ram_used"] / d["ram_total"] if d["ram_total"] else 0
        disk = 100 * d["disk_used"] / d["disk_total"] if d["disk_total"] else 0
        point = [d["cpu"], ram, disk, d["disk_read"], d["disk_write"], d["net_in"], d["net_out"], d["load"][0]]
        bucket = self._bucket.get(sid)
        if bucket and bucket[0] != minute:
            self.flush(ctx, sid)
            bucket = None
        if bucket is None:
            self._bucket[sid] = [minute, 1, point]
        else:
            bucket[1] += 1
            bucket[2] = [a + b for a, b in zip(bucket[2], point)]

    def flush(self, ctx, sid: int | None = None) -> None:
        ids = [sid] if sid is not None else list(self._bucket)
        conn = ctx.conn()
        for s in ids:
            b = self._bucket.pop(s, None)
            if not b:
                continue
            avg = [round(v / b[1], 2) for v in b[2]]
            conn.execute(f"INSERT OR REPLACE INTO vps_metrics (server_id, ts, {', '.join(FIELDS)}) "
                         f"VALUES (?, ?, {', '.join('?' * len(FIELDS))})", (s, b[0], *avg))
        conn.close()


hub = Hub()


def history(conn, sid: int, rng: str) -> dict:
    span, step = RANGES.get(rng, RANGES["1h"])
    since = _now() - span
    rows = conn.execute(
        f"SELECT (ts / {step}) * {step} AS t, " + ", ".join(f"AVG({f}) AS {f}" for f in FIELDS) +
        " FROM vps_metrics WHERE server_id = ? AND ts >= ? GROUP BY t ORDER BY t", (sid, since)).fetchall()
    return {"range": rng, "step": step, "points": [[r["t"], *[round(r[f] or 0, 2) for f in FIELDS]] for r in rows],
            "fields": list(FIELDS)}


def cleanup(conn) -> None:
    conn.execute("DELETE FROM vps_metrics WHERE ts < ?", (_now() - KEEP_DAYS * 86400,))
