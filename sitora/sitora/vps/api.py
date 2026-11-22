"""HTTP и WebSocket раздела VPS. Вход — подпись Telegram (initData), как во всём Sitora."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect

from .. import db, shop
from ..tg import check_init_data
from . import billing, catalog, live, service
from .hetzner import Hetzner, HetznerError
from .store import Vps, audit, now

log = logging.getLogger(__name__)


def view(row) -> dict:
    return {
        "id": row["id"], "name": row["name"], "location": row["location"], "server_type": row["server_type"],
        "image": row["image"], "cores": row["cores"], "memory": row["memory"], "disk": row["disk"],
        "price": row["price"], "status": row["status"], "state": row["state"], "ipv4": row["ipv4"],
        "ipv6": row["ipv6"], "paid_until": row["paid_until"], "password_state": row["password_state"],
        "error": row["last_error"] if row["state"] == "failed" or row["password_state"] == "failed" else "",
        "created_at": row["created_at"], "live": live.hub.online(row["id"]),
    }


def _fail(exc: Exception):
    if isinstance(exc, service.VpsError):
        raise HTTPException(400, str(exc))
    if isinstance(exc, HetznerError):
        raise HTTPException(502, exc.text)
    if isinstance(exc, RuntimeError):
        raise HTTPException(503, str(exc))
    raise exc


def month_start() -> int:
    t = datetime.now(timezone.utc)
    return int(t.replace(day=1, hour=0, minute=0, second=0, microsecond=0).timestamp())


def hetzner_cost(conn, since: int, until: int) -> int:
    """Расход у Hetzner, центы USD: почасово, начатый час — целый, не больше месячного потолка."""
    total = 0
    for s in conn.execute("SELECT created_at, deleted_at, cost_hourly_e6, cost_monthly FROM vps_servers "
                          "WHERE hetzner_id IS NOT NULL AND created_at <= ? AND (deleted_at IS NULL OR deleted_at > ?)",
                          (until, since)).fetchall():
        start, end = max(s["created_at"], since), min(s["deleted_at"] or until, until)
        hours = max(1, -(-(end - start) // 3600))   # начатый час Hetzner считает целым
        total += min(-(-hours * s["cost_hourly_e6"] // 10_000), s["cost_monthly"] or 10 ** 12)
    return total


def router(v: Vps, user, admin) -> APIRouter:
    r = APIRouter()

    # ── клиент ──

    @r.get("/api/vps/catalog")
    async def get_catalog(u=Depends(user)):
        conn = v.conn()
        try:
            if not v.enabled(conn):
                raise HTTPException(404, "Раздел VPS выключен.")
            return await catalog.build(conn, v.hz(), v.http_transport)
        except Exception as exc:  # noqa: BLE001
            _fail(exc)
        finally:
            conn.close()

    @r.get("/api/vps/servers")
    async def my_servers(u=Depends(user)):
        conn = v.conn()
        rows = conn.execute("SELECT * FROM vps_servers WHERE user_id = ? AND state != 'deleted' ORDER BY id DESC",
                            (u["id"],)).fetchall()
        enabled = v.enabled(conn)
        conn.close()
        await service.sync_statuses(v, rows)
        conn = v.conn()
        rows = conn.execute("SELECT * FROM vps_servers WHERE user_id = ? AND state != 'deleted' ORDER BY id DESC",
                            (u["id"],)).fetchall()
        conn.close()
        return {"ok": True, "enabled": enabled, "items": [view(x) for x in rows]}

    @r.post("/api/vps/servers")
    async def create(request: Request, u=Depends(user)):
        b = await request.json()
        try:
            sid, pw = await service.order(v, u["id"], location=str(b.get("location", "")),
                                          server_type=str(b.get("server_type", "")), image=str(b.get("image", "")),
                                          name=str(b.get("name", "")), password=str(b.get("password") or "") or None)
        except Exception as exc:  # noqa: BLE001
            _fail(exc)
        conn = v.conn()
        bal = conn.execute("SELECT balance FROM users WHERE id = ?", (u["id"],)).fetchone()[0]
        conn.close()
        return {"ok": True, "id": sid, "password": pw, "balance": bal}

    @r.get("/api/vps/servers/{sid}")
    async def card(sid: int, u=Depends(user)):
        conn = v.conn()
        try:
            row = service.own_server(conn, v.config, u["id"], sid)
        except service.VpsError as exc:
            raise HTTPException(404, str(exc)) from None
        finally:
            conn.close()
        await service.sync_statuses(v, [row])
        conn = v.conn()
        row = conn.execute("SELECT * FROM vps_servers WHERE id = ?", (sid,)).fetchone()
        conn.close()
        out = view(row)
        try:
            out["traffic"] = await service.traffic(v, row) if row["state"] != "deleted" else {}
        except HetznerError:
            out["traffic"] = {}
        out["latest"] = live.hub.latest.get(sid)
        out["ok"] = True
        return out

    @r.post("/api/vps/servers/{sid}/action")
    async def act(sid: int, request: Request, u=Depends(user)):
        b = await request.json()
        try:
            await service.action(v, u["id"], sid, str(b.get("action", "")))
        except Exception as exc:  # noqa: BLE001
            _fail(exc)
        return {"ok": True}

    @r.post("/api/vps/servers/{sid}/password")
    async def password(sid: int, request: Request, u=Depends(user)):
        b = await request.json()
        try:
            pw = await service.set_password(v, u["id"], sid, str(b.get("password") or "") or None)
        except Exception as exc:  # noqa: BLE001
            _fail(exc)
        return {"ok": True, "password": pw}

    @r.post("/api/vps/servers/{sid}/rebuild")
    async def rebuild(sid: int, request: Request, u=Depends(user)):
        b = await request.json()
        try:
            pw = await service.rebuild(v, u["id"], sid, str(b.get("image", "")), str(b.get("password") or "") or None,
                                       str(b.get("confirm", "")))
        except Exception as exc:  # noqa: BLE001
            _fail(exc)
        return {"ok": True, "password": pw}

    @r.post("/api/vps/servers/{sid}/delete")
    async def remove(sid: int, request: Request, u=Depends(user)):
        b = await request.json()
        try:
            await service.delete(v, u["id"], sid, str(b.get("confirm", "")))
        except Exception as exc:  # noqa: BLE001
            _fail(exc)
        return {"ok": True}

    @r.get("/api/vps/servers/{sid}/history")
    async def history(sid: int, range: str = "1h", u=Depends(user)):
        conn = v.conn()
        try:
            row = service.own_server(conn, v.config, u["id"], sid)
            out = live.history(conn, sid, range)
        except service.VpsError as exc:
            raise HTTPException(404, str(exc)) from None
        finally:
            conn.close()
        if not out["points"] and range == "1h":
            try:
                out["hetzner_cpu"] = await service.hetzner_cpu(v, row)
            except HetznerError:
                out["hetzner_cpu"] = []
        out["ok"] = True
        return out

    # ── WebSocket: агент на сервере клиента ──

    @r.websocket("/agent")
    async def agent_socket(ws: WebSocket):
        auth = ws.headers.get("authorization", "")
        token = auth[7:] if auth.lower().startswith("bearer ") else ""
        conn = v.conn()
        row = conn.execute("SELECT id FROM vps_servers WHERE agent_hash = ? AND state IN ('active', 'suspended')",
                           (service.sha(token),)).fetchone() if token else None
        conn.close()
        if row is None:
            await ws.close(code=4401)
            return
        sid = row["id"]
        await ws.accept()
        previous = live.hub.agents.get(sid)
        live.hub.agents[sid] = ws
        if previous is not None:
            try:
                await previous.close()
            except Exception:  # noqa: BLE001
                pass
        try:
            while True:
                text = await ws.receive_text()
                if len(text) > 64_000:
                    continue
                try:
                    data = json.loads(text)
                except ValueError:
                    continue
                if isinstance(data, dict):
                    await live.hub.publish(v, sid, data)
        except WebSocketDisconnect:
            pass
        finally:
            if live.hub.agents.get(sid) is ws:
                del live.hub.agents[sid]
                live.hub.flush(v, sid)
                for sub in list(live.hub.subs.get(sid, ())):
                    try:
                        await sub.send_text(json.dumps({"type": "offline", "server": sid}))
                    except Exception:  # noqa: BLE001
                        pass

    # ── WebSocket: мини-приложение владельца. Первое сообщение — initData и номер сервера ──

    @r.websocket("/ws/live")
    async def live_socket(ws: WebSocket):
        await ws.accept()
        try:
            hello = json.loads(await asyncio.wait_for(ws.receive_text(), timeout=10))
            u = check_init_data(str(hello.get("init", "")), v.config.bot_token)
            sid = int(hello.get("server", 0))
            if u is None:
                raise PermissionError
            conn = v.conn()
            try:
                service.own_server(conn, v.config, int(u["id"]), sid)
            finally:
                conn.close()
        except Exception:  # noqa: BLE001 — нет подписи или чужой сервер
            await ws.close(code=4403)
            return
        live.hub.subscribe(sid, ws)
        try:
            await ws.send_text(json.dumps({"type": "hello", "server": sid, "online": live.hub.online(sid),
                                           "data": live.hub.latest.get(sid)}))
            while True:
                await asyncio.wait_for(ws.receive_text(), timeout=3600)
        except (WebSocketDisconnect, asyncio.TimeoutError):
            pass
        finally:
            live.hub.unsubscribe(sid, ws)

    # ── админ ──

    @r.get("/api/admin/vps")
    async def admin_overview(a=Depends(admin)):
        conn = v.conn()
        try:
            since, t = month_start(), now()
            since_iso = datetime.fromtimestamp(since, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            q = lambda sql, *args: conn.execute(sql, args).fetchone()[0]
            revenue = q("SELECT COALESCE(-SUM(delta), 0) FROM ledger WHERE reason IN ('vps', 'vps_renew') "
                        "AND created_at >= ?", since_iso) - q(
                "SELECT COALESCE(SUM(delta), 0) FROM ledger WHERE reason = 'vps_refund' AND created_at >= ?", since_iso)
            cost_usd = hetzner_cost(conn, since, t)
            rate = shop.rate(conn)
            rows = conn.execute("SELECT * FROM vps_servers WHERE state != 'deleted' ORDER BY id DESC LIMIT 100").fetchall()
            return {
                "ok": True, "token": bool(v.config.hetzner_token), "enabled": v.enabled(conn),
                "revenue": revenue, "cost_usd": cost_usd, "cost": catalog.to_diram(cost_usd, rate),
                "profit": revenue - catalog.to_diram(cost_usd, rate),
                "servers": [{**view(x), "user_id": x["user_id"]} for x in rows],
                "active": q("SELECT COUNT(*) FROM vps_servers WHERE state IN ('active', 'creating')"),
                "suspended": q("SELECT COUNT(*) FROM vps_servers WHERE state = 'suspended'"),
                "markup": catalog.markup(conn), "eur_usd": db.get_setting(conn, "vps_eur_usd"),
                "ratelimit": v.hz().ratelimit,
            }
        finally:
            conn.close()

    @r.post("/api/admin/vps/settings")
    async def admin_settings(request: Request, a=Depends(admin)):
        b = await request.json()
        conn = v.conn()
        try:
            if "enabled" in b:
                db.set_setting(conn, "vps_enabled", "1" if b["enabled"] else "0")
            if b.get("markup") not in (None, ""):
                if not str(b["markup"]).isdigit() or int(b["markup"]) > 300:
                    raise HTTPException(400, "Наценка — целое число процентов, например 20.")
                db.set_setting(conn, "vps_markup", str(int(b["markup"])))
            if "eur_usd" in b:
                value = str(b["eur_usd"]).strip().replace(",", ".")
                if value:
                    try:
                        if Decimal(value) <= 0:
                            raise InvalidOperation
                    except InvalidOperation:
                        raise HTTPException(400, "Курс EUR→USD — число, например 1.08. Пусто — автоматически.") from None
                db.set_setting(conn, "vps_eur_usd", value)
            audit(conn, a["id"], "vps_settings", "", json.dumps(b, ensure_ascii=False)[:200])
            v.hz().forget("catalog")
        finally:
            conn.close()
        return {"ok": True}

    @r.post("/api/admin/vps/servers/{sid}")
    async def admin_server(sid: int, request: Request, a=Depends(admin)):
        b = await request.json()
        act = str(b.get("action", ""))
        try:
            if act == "delete":
                await service.delete(v, a["id"], sid, reason="администратор")
            else:
                await service.action(v, a["id"], sid, act)
        except Exception as exc:  # noqa: BLE001
            _fail(exc)
        return {"ok": True}

    @r.post("/api/admin/vps/approve/{uid}")
    async def admin_approve(uid: int, request: Request, a=Depends(admin)):
        b = await request.json()
        conn = v.conn()
        if b.get("approved", True):
            conn.execute("INSERT OR IGNORE INTO vps_approved (user_id, at) VALUES (?, ?)", (uid, now()))
        else:
            conn.execute("DELETE FROM vps_approved WHERE user_id = ?", (uid,))
        audit(conn, a["id"], "vps_approve", f"user:{uid}", str(bool(b.get("approved", True))))
        conn.close()
        return {"ok": True}

    @r.get("/api/admin/vps/user/{uid}")
    async def admin_user(uid: int, a=Depends(admin)):
        conn = v.conn()
        rows = conn.execute("SELECT * FROM vps_servers WHERE user_id = ? ORDER BY id DESC", (uid,)).fetchall()
        ok = conn.execute("SELECT 1 FROM vps_approved WHERE user_id = ?", (uid,)).fetchone() is not None
        conn.close()
        return {"ok": True, "approved": ok, "servers": [view(x) for x in rows]}

    @r.post("/api/admin/vps/check")
    async def admin_check(a=Depends(admin)):
        """Проверить токен Hetzner из .env: есть ли права Read & Write."""
        probe = Hetzner(v.config.hetzner_token, v.config.hetzner_url, v.hetzner_transport)
        try:
            access = await probe.access()
        except HetznerError as exc:
            raise HTTPException(502, exc.text) from None
        finally:
            await probe.close()
        return {"ok": True, "access": access}

    return r


def background(v: Vps):
    return [billing.loop(v)]
