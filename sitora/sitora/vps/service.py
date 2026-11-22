"""Заказ серверов и действия с ними. Каждое действие проверяет, что сервер принадлежит клиенту.

Заказ: сначала списываем деньги с баланса Sitora, потом создаём сервер у Hetzner.
Любая ошибка Hetzner — деньги сразу возвращаются на баланс.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import secrets
import string

from .. import db, shop
from ..money import fmt
from . import catalog, cloudinit, sshkey
from .hetzner import HetznerError
from .store import Vps, approved, audit, now

log = logging.getLogger(__name__)

PERIOD = 30 * 86400
STATUS_TTL = 10
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
LIVE_STATES = ("creating", "active", "suspended")
ACTIONS = ("poweron", "shutdown", "poweroff", "reboot")


class VpsError(Exception):
    pass


def sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def root_password_problem(password: str) -> str | None:
    if not 12 <= len(password) <= 72:
        return "Root-пароль — от 12 до 72 символов. / Парол — аз 12 то 72 аломат."
    if any(ch in password for ch in ":\n\r\t\x00") or not password.isprintable():
        return "В root-пароле нельзя двоеточие и служебные символы."
    if not (re.search(r"[a-z]", password) and re.search(r"[A-Z]", password) and re.search(r"\d", password)):
        return "Root-пароль: нужны строчные и заглавные буквы и цифры."
    return None


def generate_password(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "-_.!@#%+="
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if root_password_problem(pw) is None:
            return pw


def own_server(conn, config, user_id: int, sid: int):
    """Сервер этого клиента (админ видит любой). Чужой — как будто его нет."""
    row = conn.execute("SELECT * FROM vps_servers WHERE id = ?", (sid,)).fetchone()
    if row is None or (row["user_id"] != user_id and not shop.is_admin(conn, config, user_id)):
        raise VpsError("Сервер не найден. / Сервер ёфт нашуд.")
    return row


def _ip(server: dict) -> tuple[str, str]:
    net = server.get("public_net") or {}
    return (net.get("ipv4") or {}).get("ip") or "", (net.get("ipv6") or {}).get("ip") or ""


def _password(password: str | None) -> tuple[str, str | None]:
    if password:
        problem = root_password_problem(password)
        if problem:
            raise VpsError(problem)
        return password, None
    pw = generate_password()
    return pw, pw


# ── заказ ──

async def order(v: Vps, user_id: int, *, location: str, server_type: str, image: str, name: str,
                password: str | None) -> tuple[int, str | None]:
    name = (name or "").strip().lower()
    if not NAME_RE.match(name):
        raise VpsError("Имя сервера: латиница, цифры и дефис, до 40 символов.")
    password, generated = _password(password)
    conn = v.conn()
    try:
        if not v.enabled(conn):
            raise VpsError("Раздел VPS сейчас недоступен.")
        if not approved(conn, v.config, user_id):
            n = conn.execute("SELECT COUNT(*) FROM vps_servers WHERE user_id = ? AND state IN (?,?,?)",
                             (user_id, *LIVE_STATES)).fetchone()[0]
            if n >= 1:
                raise VpsError("Новым клиентам доступен 1 сервер, пока администратор не подтвердит аккаунт. / "
                               "То тасдиқи маъмур — 1 сервер.")
        h = v.hz()
        try:
            plan, _ = await catalog.find_offer(conn, h, location, server_type, image, v.http_transport)
        except ValueError as exc:
            raise VpsError(str(exc)) from None
        token = secrets.token_urlsafe(32)
        t = now()
        with db.tx(conn):
            cur = conn.execute(
                "INSERT INTO vps_servers (user_id, name, location, server_type, image, cores, memory, disk, price, "
                "price_usd, cost_hourly_e6, cost_monthly, agent_hash, paid_until, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (user_id, name, location, server_type, image, plan["cores"], plan["memory"], plan["disk"],
                 plan["price"], plan["price_usd"], plan["cost_hourly_e6"], plan["cost_monthly"], sha(token),
                 t + PERIOD, t))
            sid = cur.lastrowid
            try:
                shop.move(conn, user_id, -plan["price"], "vps", f"vps:{sid}")
            except shop.ShopError:
                raise VpsError(f"Не хватает денег: нужно {fmt(plan['price'])} с. Пополните баланс. / "
                               f"Маблағ намерасад: {fmt(plan['price'])} с.") from None
            audit(conn, user_id, "order", f"vps:{sid}", f"{server_type} {location} {image}")

        try:
            key = sshkey.ensure_key(v.key_path)
            key_name = await sshkey.ensure_registered(h, key)
            resp = await h.post("/servers", {
                "name": f"{name}-{sid}", "server_type": server_type, "image": image, "location": location,
                "start_after_create": True, "ssh_keys": [key_name],
                "user_data": cloudinit.build(v.agent_url, token),
                "labels": {"panel": "sitora", "order": str(sid), "client": str(user_id)},
                "public_net": {"enable_ipv4": True, "enable_ipv6": True},
            })
        except Exception as exc:  # любая ошибка — деньги назад сразу
            text = exc.text if isinstance(exc, HetznerError) else "внутренняя ошибка"
            with db.tx(conn):
                shop.move(conn, user_id, plan["price"], "vps_refund", f"vps:{sid}")
                conn.execute("UPDATE vps_servers SET state = 'failed', last_error = ? WHERE id = ?", (text, sid))
                audit(conn, user_id, "order_failed", f"vps:{sid}", text)
            if not isinstance(exc, HetznerError):
                log.exception("VPS: заказ %s упал", sid)
            v.spawn(v.tell_admins(f"⚠️ VPS #{sid} не создан у Hetzner: {text}. Деньги клиенту возвращены."))
            raise VpsError(f"Сервер не создан: {text} Деньги вернулись на баланс. / Пул ба баланс баргашт.") from None

        server = resp.get("server") or {}
        v4, v6 = _ip(server)
        conn.execute("UPDATE vps_servers SET hetzner_id = ?, status = ?, ipv4 = ?, ipv6 = ?, state = 'active' WHERE id = ?",
                     (server.get("id"), server.get("status", "initializing"), v4, v6, sid))
        h.forget("servers")
    finally:
        conn.close()
    v.spawn(finish_password(v, sid, password))
    v.spawn(v.tell_admins(f"🖥 Новый VPS #{sid}: {server_type} · {location} · {image}\n"
                          f"Клиент ID {user_id} · {fmt(plan['price'])} с./30 дней"))
    return sid, generated


# ── root-пароль ──

async def _wait_running(v: Vps, sid: int, timeout: float = 600) -> str:
    h = v.hz()
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        conn = v.conn()
        hid = conn.execute("SELECT hetzner_id FROM vps_servers WHERE id = ?", (sid,)).fetchone()[0]
        conn.close()
        data = (await h.get(f"/servers/{hid}")).get("server") or {}
        v4, v6 = _ip(data)
        conn = v.conn()
        conn.execute("UPDATE vps_servers SET status = ?, ipv4 = ?, ipv6 = ? WHERE id = ?",
                     (data.get("status", ""), v4, v6, sid))
        conn.close()
        if data.get("status") == "running" and v4:
            return v4
        await asyncio.sleep(0 if v.fast else 5)
    raise TimeoutError("сервер так и не запустился")


async def finish_password(v: Vps, sid: int, password: str) -> None:
    """Поставить root-пароль по SSH ключом панели; ключ удалён — через reset_password. Пароль не хранится."""
    conn = v.conn()
    conn.execute("UPDATE vps_servers SET password_state = 'pending' WHERE id = ?", (sid,))
    conn.close()
    state, error = "set", ""
    try:
        ip = await _wait_running(v, sid)
        setter = v.ssh or sshkey.set_root_password
        key = sshkey.ensure_key(v.key_path)
        try:
            await asyncio.to_thread(setter, ip, password, key=key)
        except sshkey.SSHFailed as exc:
            if "ключ не подошёл" not in str(exc):
                raise
            conn = v.conn()
            hid = conn.execute("SELECT hetzner_id FROM vps_servers WHERE id = ?", (sid,)).fetchone()[0]
            conn.close()
            temp = (await v.hz().post(f"/servers/{hid}/actions/reset_password")).get("root_password") or ""
            await asyncio.to_thread(setter, ip, password, key=None, login_password=temp)
    except Exception as exc:  # noqa: BLE001
        state = "failed"
        error = exc.text if isinstance(exc, HetznerError) else str(exc)[:200]
        log.warning("VPS %s: пароль не поставлен: %s", sid, error)
    conn = v.conn()
    conn.execute("UPDATE vps_servers SET password_state = ?, last_error = ? WHERE id = ?", (state, error, sid))
    conn.close()


async def set_password(v: Vps, user_id: int, sid: int, password: str | None) -> str | None:
    password, generated = _password(password)
    conn = v.conn()
    try:
        if own_server(conn, v.config, user_id, sid)["state"] != "active":
            raise VpsError("Сервер сейчас недоступен.")
        audit(conn, user_id, "root_password", f"vps:{sid}")
    finally:
        conn.close()
    v.spawn(finish_password(v, sid, password))
    return generated


# ── действия ──

def _confirm(row, confirm: str) -> None:
    """Опасное действие: клиент вписывает имя сервера — случайным нажатием его не удалить."""
    if (confirm or "").strip().lower() != row["name"]:
        raise VpsError("Для подтверждения впишите имя сервера. / Барои тасдиқ номи серверро нависед.")


async def action(v: Vps, user_id: int, sid: int, act: str) -> None:
    if act not in ACTIONS:
        raise VpsError("Неизвестное действие.")
    conn = v.conn()
    try:
        row = own_server(conn, v.config, user_id, sid)
        is_admin = shop.is_admin(conn, v.config, user_id)
        if row["state"] == "suspended" and act == "poweron" and not is_admin:
            raise VpsError("Сервер выключен за неуплату — пополните баланс, и он включится сам.")
        if row["state"] not in ("active", "suspended") or not row["hetzner_id"]:
            raise VpsError("Сервер сейчас недоступен.")
        try:
            await v.hz().post(f"/servers/{row['hetzner_id']}/actions/{act}")
        except HetznerError as exc:
            raise VpsError(exc.text) from None
        v.hz().forget("servers")
        audit(conn, user_id, act, f"vps:{sid}")
    finally:
        conn.close()


async def rebuild(v: Vps, user_id: int, sid: int, image: str, password: str | None, confirm: str) -> str | None:
    password, generated = _password(password)
    conn = v.conn()
    try:
        row = own_server(conn, v.config, user_id, sid)
        _confirm(row, confirm)
        if row["state"] != "active" or not row["hetzner_id"]:
            raise VpsError("Сервер сейчас недоступен.")
        token = secrets.token_urlsafe(32)
        try:
            await v.hz().post(f"/servers/{row['hetzner_id']}/actions/rebuild",
                              {"image": image, "user_data": cloudinit.build(v.agent_url, token)})
        except HetznerError as exc:
            raise VpsError(exc.text) from None
        conn.execute("UPDATE vps_servers SET image = ?, agent_hash = ?, status = 'rebuilding' WHERE id = ?",
                     (image, sha(token), sid))
        audit(conn, user_id, "rebuild", f"vps:{sid}", image)
        v.hz().forget("servers")
    finally:
        conn.close()
    v.spawn(finish_password(v, sid, password))
    return generated


async def delete(v: Vps, user_id: int | None, sid: int, confirm: str | None = None, *, reason: str = "client") -> None:
    """Удалить у Hetzner — оплата там сразу останавливается. Оплаченный период не возвращается."""
    conn = v.conn()
    try:
        if user_id is None:
            row = conn.execute("SELECT * FROM vps_servers WHERE id = ?", (sid,)).fetchone()
        else:
            row = own_server(conn, v.config, user_id, sid)
            if confirm is not None:
                _confirm(row, confirm)
        if row["state"] == "deleted":
            return
        if row["hetzner_id"]:
            try:
                await v.hz().delete(f"/servers/{row['hetzner_id']}")
            except HetznerError as exc:
                if exc.code != "not_found":
                    raise VpsError(exc.text) from None
        conn.execute("UPDATE vps_servers SET state = 'deleted', status = 'deleted', deleted_at = ? WHERE id = ?",
                     (now(), sid))
        audit(conn, user_id, "delete", f"vps:{sid}", reason)
        v.hz().forget("servers")
    finally:
        conn.close()


# ── статусы, трафик, метрики Hetzner ──

async def sync_statuses(v: Vps, rows) -> None:
    rows = [r for r in rows if r["hetzner_id"] and r["state"] != "deleted"]
    if not rows:
        return
    h = v.hz()
    try:
        items = await h.cached("servers", STATUS_TTL,
                               lambda: h.list("/servers", "servers", {"label_selector": "panel=sitora"}))
    except HetznerError as exc:
        log.info("VPS: статусы не обновлены: %s", exc.code)
        return
    live = {s["id"]: s for s in items}
    conn = v.conn()
    for row in rows:
        s = live.get(row["hetzner_id"])
        if s:
            v4, v6 = _ip(s)
            conn.execute("UPDATE vps_servers SET status = ?, ipv4 = ?, ipv6 = ? WHERE id = ?",
                         (s.get("status", ""), v4 or row["ipv4"], v6 or row["ipv6"], row["id"]))
    conn.close()


async def traffic(v: Vps, row) -> dict:
    if not row["hetzner_id"]:
        return {}
    h = v.hz()
    data = await h.cached(f"servers:{row['hetzner_id']}", 60, lambda: h.get(f"/servers/{row['hetzner_id']}"))
    s = data.get("server") or {}
    return {"outgoing": s.get("outgoing_traffic") or 0, "ingoing": s.get("ingoing_traffic") or 0,
            "included": s.get("included_traffic") or 0}


async def hetzner_cpu(v: Vps, row) -> list[list[float]]:
    """CPU из метрик Hetzner (раз в минуту), пока агент не подключился. 100 = одно ядро → делим на vCPU."""
    import datetime as dt
    if not row["hetzner_id"]:
        return []
    end = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    start = end - dt.timedelta(hours=1)
    h = v.hz()
    data = await h.cached(f"servers:{row['hetzner_id']}:cpu", 60, lambda: h.get(
        f"/servers/{row['hetzner_id']}/metrics",
        {"type": "cpu", "start": start.isoformat(), "end": end.isoformat(), "step": 60}))
    series = (((data.get("metrics") or {}).get("time_series") or {}).get("cpu") or {}).get("values") or []
    cores = max(int(row["cores"] or 1), 1)
    return [[float(t), round(float(val) / cores, 1)] for t, val in series]
