"""Бизнес-логика панели: заказ серверов, пароли, графики, домены, DNS и биллинг."""
from __future__ import annotations

import json
import logging
import secrets
import threading
import time

from .catalog import Catalog, cents
from .cloudinit import build_user_data
from .config import Settings
from .db import Database, now
from .providers import ProviderError, Providers
from .security import generate_root_password, root_password_problems, sha256
from .ssh import SshError, set_root_password
from .validators import ValidationError, normalize_domain, validate_record, validate_server_name

log = logging.getLogger("hosting")

MONTH = 30 * 24 * 3600
YEAR = 365 * 24 * 3600
RANGES = {"1h": (3600, 60), "24h": (86400, 900), "7d": (7 * 86400, 3 * 3600)}


class ServiceError(Exception):
    def __init__(self, message: str, status: int = 400, field: str | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.field = field


class _Cache:
    def __init__(self):
        self._d: dict = {}
        self._lock = threading.Lock()

    def get(self, key, ttl: float):
        with self._lock:
            v = self._d.get(key)
            if v and time.monotonic() - v[0] < ttl:
                return v[1]
        return None

    def put(self, key, value):
        with self._lock:
            self._d[key] = (time.monotonic(), value)

    def drop(self, key):
        with self._lock:
            self._d.pop(key, None)


class Hosting:
    def __init__(self, settings: Settings, db: Database, catalog: Catalog, providers: Providers,
                 run_async=None, demo_password_delay: float = 1.5):
        self.s = settings
        self.db = db
        self.catalog = catalog
        self.p = providers
        self.cache = _Cache()
        self.demo_password_delay = demo_password_delay
        # Тесты подменяют на синхронный вызов.
        self.run_async = run_async or (lambda fn, *a: threading.Thread(target=fn, args=a, daemon=True).start())

    # ═══════════════════════ Серверы ═══════════════════════
    def server_view(self, row: dict) -> dict:
        plan = self.catalog.plan(row["plan"]) or {"id": row["plan"], "name": row["plan"]}
        last_agent = self.db.one("SELECT ts FROM agent_metrics WHERE server_id = ? ORDER BY ts DESC LIMIT 1", (row["id"],))
        return {
            "id": row["id"], "name": row["name"], "status": row["status"], "suspended": bool(row["suspended"]),
            "plan": plan, "location": self.catalog.location(row["location"]) or {"id": row["location"], "name": row["location"]},
            "image": self.catalog.image(row["image"]) or {"id": row["image"], "name": row["image"]},
            "ipv4": row["ipv4"], "ipv6": row["ipv6"], "price": row["price_cents"] / 100,
            "paid_until": row["paid_until"], "created_at": row["created_at"],
            "password_state": row["password_state"],
            "agent": bool(last_agent and last_agent["ts"] > now() - 180),
        }

    def get_server(self, user: dict, server_id: int) -> dict:
        row = self.db.one("SELECT * FROM servers WHERE id = ? AND deleted_at IS NULL", (server_id,))
        if not row or (row["user_id"] != user["id"] and not user["is_admin"]):
            raise ServiceError("Сервер не найден", 404)
        return row

    def list_servers(self, user: dict) -> list[dict]:
        rows = self.db.all("SELECT * FROM servers WHERE user_id = ? AND deleted_at IS NULL ORDER BY id", (user["id"],))
        return [self.server_view(self.refresh(r)) for r in rows]

    def refresh(self, row: dict, force: bool = False) -> dict:
        """Подтягивает статус и IP у провайдера, не чаще раза в 8 секунд на сервер."""
        if not row["provider_id"]:
            return row
        key = ("state", row["id"])
        st = None if force else self.cache.get(key, 8)
        if st is None:
            try:
                st = self.p.vps.get_server(row["provider_id"])
            except ProviderError as e:
                log.warning("refresh %s: %s", row["id"], e.message)
                return row
            self.cache.put(key, st)
        changes = {}
        if st.status != row["status"]:
            changes["status"] = st.status
        if st.ipv4 and st.ipv4 != row["ipv4"]:
            changes["ipv4"] = st.ipv4
        if st.ipv6 and st.ipv6 != row["ipv6"]:
            changes["ipv6"] = st.ipv6
        if changes:
            sets = ", ".join(f"{k} = ?" for k in changes)
            self.db.run(f"UPDATE servers SET {sets} WHERE id = ?", (*changes.values(), row["id"]))
            row = {**row, **changes}
        return row

    def order_server(self, user: dict, *, plan_id: str, location: str, image: str, name: str,
                     root_password: str | None, ip: str = "") -> tuple[dict, str | None]:
        plan = self.catalog.plan(plan_id)
        if not plan:
            raise ServiceError("Такого тарифа нет", field="plan")
        if not self.catalog.location(location):
            raise ServiceError("Такой локации нет", field="location")
        if not self.catalog.image(image):
            raise ServiceError("Такой ОС нет", field="image")
        try:
            name = validate_server_name(name)
        except ValidationError as e:
            raise ServiceError(e.message, field="name") from None
        if root_password:
            problems = root_password_problems(root_password)
            if problems:
                raise ServiceError("Пароль: " + ", ".join(problems), field="root_password")
        if self.db.one("SELECT 1 FROM servers WHERE user_id = ? AND name = ? AND deleted_at IS NULL", (user["id"], name)):
            raise ServiceError("Сервер с таким именем уже есть", field="name")

        price = cents(plan["price_month"])
        if not self.db.charge(user["id"], price, f"Сервер {name} ({plan['name']}), 1 месяц"):
            raise ServiceError("Недостаточно средств на балансе", 402)

        agent_token = secrets.token_urlsafe(32)
        sid = self.db.run(
            "INSERT INTO servers(user_id, name, plan, location, image, provider, status, price_cents, paid_until,"
            " agent_token_hash, password_state, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (user["id"], name, plan_id, location, image, self.p.vps.name, "creating", price, now() + MONTH,
             sha256(agent_token), "pending" if root_password else "", now()))
        # У Hetzner имя сервера уникально в проекте, поэтому добавляем номер заказа.
        provider_name = f"{name}-{sid}"
        try:
            created = self.p.vps.create_server(
                name=provider_name, server_type=plan["server_type"], image=image, location=location,
                user_data=build_user_data(self.s.public_url, sid, agent_token),
                labels={"panel_server": str(sid), "panel_user": str(user["id"])})
        except ProviderError as e:
            self.db.run("UPDATE servers SET deleted_at = ?, status = 'failed' WHERE id = ?", (now(), sid))
            self.db.credit(user["id"], price, "refund", f"Возврат: сервер {name} не создан")
            self.db.audit(user["id"], "server.create_failed", f"{sid}:{e.code}", ip)
            raise ServiceError(f"Не удалось создать сервер: {e.message}", 502) from None
        self.db.run("UPDATE servers SET provider_id = ?, status = ?, ipv4 = ?, ipv6 = ? WHERE id = ?",
                    (created.provider_id, created.status, created.ipv4, created.ipv6, sid))
        self.db.audit(user["id"], "server.create", str(sid), ip)
        row = self.db.one("SELECT * FROM servers WHERE id = ?", (sid,))
        if root_password:
            self.run_async(self._apply_initial_password, sid, created.root_password, root_password)
            return row, None
        return row, created.root_password

    def _apply_initial_password(self, sid: int, temp: str | None, new: str) -> None:
        """Ждём, пока сервер загрузится, и ставим пароль, который клиент указал при заказе."""
        try:
            deadline = time.time() + 300
            row = self.db.one("SELECT * FROM servers WHERE id = ?", (sid,))
            while time.time() < deadline:
                row = self.refresh(row, force=True)
                if row["status"] == "running" and row["ipv4"]:
                    break
                time.sleep(5 if self.p.vps.name != "demo" else 0.2)
            self._set_password(row, new, temp=temp)
            self.db.run("UPDATE servers SET password_state = 'applied' WHERE id = ?", (sid,))
        except (ServiceError, ProviderError, SshError) as e:
            msg = getattr(e, "message", str(e))
            log.warning("initial password %s: %s", sid, msg)
            self.db.run("UPDATE servers SET password_state = ? WHERE id = ?", (f"failed: {msg}"[:200], sid))

    def _set_password(self, row: dict, new: str, temp: str | None = None) -> None:
        if self.p.vps.name == "demo":
            time.sleep(self.demo_password_delay)
            return
        if temp is None:
            temp = self.p.vps.reset_password(row["provider_id"])
            time.sleep(3)  # qemu-guest-agent применяет пароль не мгновенно
        hostkey = set_root_password(row["ipv4"], temp, new, known_hostkey=row["ssh_hostkey"])
        if hostkey and hostkey != row["ssh_hostkey"]:
            self.db.run("UPDATE servers SET ssh_hostkey = ? WHERE id = ?", (hostkey, row["id"]))

    def _require_active(self, row: dict) -> None:
        if row["suspended"]:
            raise ServiceError("Сервер приостановлен за неуплату. Пополните баланс.", 402)

    def change_root_password(self, user: dict, row: dict, new_password: str | None, ip: str = "") -> dict:
        self._require_active(row)
        row = self.refresh(row, force=True)
        if row["status"] != "running":
            raise ServiceError("Сервер должен быть включён", 409)
        try:
            if new_password is None:
                pw = self.p.vps.reset_password(row["provider_id"])
                self.db.audit(user["id"], "server.password_reset", str(row["id"]), ip)
                return {"mode": "generated", "password": pw}
            problems = root_password_problems(new_password)
            if problems:
                raise ServiceError("Пароль: " + ", ".join(problems), field="root_password")
            self._set_password(row, new_password)
        except ProviderError as e:
            raise ServiceError(e.message, e.status if e.status < 500 else 502) from None
        except SshError as e:
            raise ServiceError(
                f"{e} Можно сбросить пароль на случайный кнопкой «Сгенерировать на сервере».", 502) from None
        self.db.run("UPDATE servers SET password_state = 'applied' WHERE id = ?", (row["id"],))
        self.db.audit(user["id"], "server.password_set", str(row["id"]), ip)
        return {"mode": "custom"}

    def power(self, user: dict, row: dict, action: str, ip: str = "") -> dict:
        if action != "stop" and action != "force_stop":
            self._require_active(row)
        try:
            self.p.vps.power(row["provider_id"], action)
        except ProviderError as e:
            raise ServiceError(e.message, e.status if e.status < 500 else 502) from None
        self.cache.drop(("state", row["id"]))
        self.db.audit(user["id"], f"server.{action}", str(row["id"]), ip)
        transitional = {"start": "starting", "stop": "stopping", "force_stop": "off", "reboot": "rebooting", "reset": "rebooting"}
        self.db.run("UPDATE servers SET status = ? WHERE id = ?", (transitional.get(action, row["status"]), row["id"]))
        return self.server_view(self.db.one("SELECT * FROM servers WHERE id = ?", (row["id"],)))

    def rebuild(self, user: dict, row: dict, image: str, ip: str = "") -> str | None:
        self._require_active(row)
        if not self.catalog.image(image):
            raise ServiceError("Такой ОС нет", field="image")
        try:
            pw = self.p.vps.rebuild(row["provider_id"], image)
        except ProviderError as e:
            raise ServiceError(e.message, 502) from None
        # Новая система — новый ключ SSH и новый агент нужно ставить заново (cloud-init не перезапускается).
        self.db.run("UPDATE servers SET image = ?, status = 'rebuilding', ssh_hostkey = '', password_state = '' WHERE id = ?",
                    (image, row["id"]))
        self.cache.drop(("state", row["id"]))
        self.db.audit(user["id"], "server.rebuild", f"{row['id']}:{image}", ip)
        return pw

    def delete_server(self, user: dict, row: dict, ip: str = "") -> None:
        try:
            self.p.vps.delete_server(row["provider_id"])
        except ProviderError as e:
            raise ServiceError(e.message, 502) from None
        self.db.run("UPDATE servers SET deleted_at = ?, status = 'deleted' WHERE id = ?", (now(), row["id"]))
        self.db.audit(user["id"], "server.delete", str(row["id"]), ip)

    # ── Графики ──
    def metrics(self, row: dict, rng: str) -> dict:
        if rng not in RANGES:
            raise ServiceError("Диапазон: 1h, 24h или 7d")
        span, step = RANGES[rng]
        end = now()
        start = end - span
        key = ("metrics", row["id"], rng)
        data = self.cache.get(key, 50 if rng == "1h" else 600)
        if data is None:
            try:
                m = self.p.vps.metrics(row["provider_id"], start, end, step)
            except ProviderError as e:
                raise ServiceError(e.message, 502) from None
            data = {"step": m.step, "series": m.series}
            self.cache.put(key, data)

        agent_rows = self.db.all(
            "SELECT ts, mem_used, mem_total FROM agent_metrics WHERE server_id = ? AND ts >= ? ORDER BY ts",
            (row["id"], start))
        mem = _downsample([[r["ts"], round(r["mem_used"] / r["mem_total"] * 100, 2)] for r in agent_rows if r["mem_total"]], step)
        last = self.db.one("SELECT * FROM agent_metrics WHERE server_id = ? ORDER BY ts DESC LIMIT 1", (row["id"],))
        agent = None
        if last and last["ts"] > end - 180:
            agent = {"ts": last["ts"], "mem_used": last["mem_used"], "mem_total": last["mem_total"],
                     "disk_used": last["disk_used"], "disk_total": last["disk_total"], "load1": last["load1"],
                     "procs": json.loads(last["procs"] or "[]")}
        if agent is None and self.p.vps.name == "demo":
            agent, mem = _demo_agent(row, self.catalog.plan(row["plan"]) or {}, data["series"].get("cpu", []))
        return {"range": rng, "step": data["step"], "series": {**data["series"], "mem": mem}, "agent": agent}

    def agent_report(self, token: str, payload: dict) -> None:
        sid = int(payload.get("server_id") or 0)
        row = self.db.one("SELECT id, agent_token_hash FROM servers WHERE id = ? AND deleted_at IS NULL", (sid,))
        if not row or not secrets.compare_digest(row["agent_token_hash"], sha256(token or "")):
            raise ServiceError("Неверный токен агента", 401)
        last = self.db.one("SELECT ts FROM agent_metrics WHERE server_id = ? ORDER BY ts DESC LIMIT 1", (sid,))
        if last and last["ts"] > now() - 10:
            return  # не чаще раза в 10 секунд
        procs = []
        for p in (payload.get("procs") or [])[:5]:
            try:
                procs.append({"name": str(p["name"])[:40], "cpu": float(p["cpu"]), "mem": int(p["mem"])})
            except (KeyError, TypeError, ValueError):
                continue
        try:
            vals = [int(payload["mem_used"]), int(payload["mem_total"]), int(payload["disk_used"]),
                    int(payload["disk_total"]), float(payload["load1"])]
        except (KeyError, TypeError, ValueError):
            raise ServiceError("Некорректные данные агента") from None
        self.db.run("INSERT INTO agent_metrics(server_id, ts, mem_used, mem_total, disk_used, disk_total, load1, procs)"
                    " VALUES (?,?,?,?,?,?,?,?)", (sid, now(), *vals, json.dumps(procs)))

    # ═══════════════════════ Домены и DNS ═══════════════════════
    def check_domains(self, raw: str) -> list[dict]:
        name = raw.strip().lower()
        name = name.removeprefix("https://").removeprefix("http://").split("/")[0]
        label = name.split(".")[0]
        zones = [t["zone"] for t in self.catalog.tlds]
        if "." in name and name.split(".", 1)[1] in zones:
            first = name.split(".", 1)[1]
            zones = [first] + [z for z in zones if z != first]
        try:
            normalize_domain(f"{label}.com")
        except ValidationError:
            raise ServiceError("Имя: латиница, цифры и дефис, например mysite", field="domain") from None
        out = []
        for z in zones:
            d = f"{label}.{z}"
            taken_here = self.db.one("SELECT 1 FROM domains WHERE name = ?", (d,))
            free = not taken_here and self.p.registrar.check(d)
            out.append({"domain": d, "zone": z, "available": free, "price": self.catalog.tld(z)["price_year"]})
        return out

    def domain_view(self, row: dict) -> dict:
        n = self.db.one("SELECT COUNT(*) AS n FROM dns_records WHERE domain_id = ?", (row["id"],))["n"]
        return {"id": row["id"], "name": row["name"], "kind": row["kind"], "expires_at": row["expires_at"],
                "auto_renew": bool(row["auto_renew"]), "status": row["status"], "records": n,
                "price": row["price_cents"] / 100, "nameservers": self.s.nameservers}

    def list_domains(self, user: dict) -> list[dict]:
        rows = self.db.all("SELECT * FROM domains WHERE user_id = ? ORDER BY name", (user["id"],))
        return [self.domain_view(r) for r in rows]

    def get_domain(self, user: dict, domain_id: int) -> dict:
        row = self.db.one("SELECT * FROM domains WHERE id = ?", (domain_id,))
        if not row or (row["user_id"] != user["id"] and not user["is_admin"]):
            raise ServiceError("Домен не найден", 404)
        return row

    def add_domain(self, user: dict, raw: str, register: bool, ip: str = "") -> dict:
        try:
            domain = normalize_domain(raw)
        except ValidationError as e:
            raise ServiceError(e.message, field="domain") from None
        if self.db.one("SELECT 1 FROM domains WHERE name = ?", (domain,)):
            raise ServiceError("Этот домен уже добавлен в панель", 409, field="domain")
        price = 0
        expires = None
        if register:
            zone = domain.split(".", 1)[1]
            tld = self.catalog.tld(zone)
            if not tld:
                raise ServiceError(f"Зону .{zone} мы пока не регистрируем", field="domain")
            if not self.p.registrar.check(domain):
                raise ServiceError("Домен уже занят", 409, field="domain")
            price = cents(tld["price_year"])
            if not self.db.charge(user["id"], price, f"Регистрация домена {domain}, 1 год"):
                raise ServiceError("Недостаточно средств на балансе", 402)
            try:
                expires = self.p.registrar.register(domain, 1)
            except ProviderError as e:
                self.db.credit(user["id"], price, "refund", f"Возврат: домен {domain} не зарегистрирован")
                raise ServiceError(e.message, 502) from None
        try:
            self.p.dns.ensure_zone(domain)
        except ProviderError as e:
            if register:
                log.error("zone for registered %s failed: %s", domain, e.message)
            else:
                raise ServiceError(f"Не удалось создать DNS-зону: {e.message}", 502) from None
        did = self.db.run(
            "INSERT INTO domains(user_id, name, kind, price_cents, expires_at, auto_renew, status, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (user["id"], domain, "registered" if register else "external", price, expires, 1, "active", now()))
        self.db.audit(user["id"], "domain.register" if register else "domain.add", domain, ip)
        return self.domain_view(self.db.one("SELECT * FROM domains WHERE id = ?", (did,)))

    def records(self, domain_row: dict) -> list[dict]:
        return self.db.all("SELECT id, type, name, value, ttl FROM dns_records WHERE domain_id = ? ORDER BY name, type, id",
                           (domain_row["id"],))

    def _push(self, domain_row: dict, name: str, rtype: str) -> None:
        rows = self.db.all("SELECT value, ttl FROM dns_records WHERE domain_id = ? AND name = ? AND type = ? ORDER BY id",
                           (domain_row["id"], name, rtype))
        ttl = min((r["ttl"] for r in rows), default=3600)
        try:
            self.p.dns.set_rrset(domain_row["name"], name, rtype, ttl, [r["value"] for r in rows])
        except ProviderError as e:
            raise ServiceError(f"DNS-сервер не принял изменение: {e.message}", 502) from None

    def add_record(self, user: dict, domain_row: dict, rtype: str, name: str, value: str, ttl: int, ip: str = "") -> dict:
        try:
            t, n, v, ttl = validate_record(rtype, name, value, int(ttl))
        except ValidationError as e:
            raise ServiceError(e.message, field=e.field) from None
        except (TypeError, ValueError):
            raise ServiceError("Недопустимый TTL", field="ttl") from None
        same_name = self.db.all("SELECT type, value FROM dns_records WHERE domain_id = ? AND name = ?", (domain_row["id"], n))
        if t == "CNAME" and same_name:
            raise ServiceError(f"CNAME нельзя ставить рядом с другими записями для «{n}»", 409, field="name")
        if t != "CNAME" and any(r["type"] == "CNAME" for r in same_name):
            raise ServiceError(f"Для «{n}» уже есть CNAME — другие записи с этим именем не допускаются", 409, field="name")
        if any(r["type"] == t and r["value"] == v for r in same_name):
            raise ServiceError("Такая запись уже есть", 409, field="value")
        if len(self.records(domain_row)) >= 500:
            raise ServiceError("Не больше 500 записей в зоне", 400)
        rid = self.db.run("INSERT INTO dns_records(domain_id, type, name, value, ttl, created_at) VALUES (?,?,?,?,?,?)",
                          (domain_row["id"], t, n, v, ttl, now()))
        try:
            self._push(domain_row, n, t)
        except ServiceError:
            self.db.run("DELETE FROM dns_records WHERE id = ?", (rid,))
            raise
        self.db.audit(user["id"], "dns.add", f"{domain_row['name']}:{t}:{n}", ip)
        return {"id": rid, "type": t, "name": n, "value": v, "ttl": ttl}

    def delete_record(self, user: dict, domain_row: dict, record_id: int, ip: str = "") -> None:
        rec = self.db.one("SELECT * FROM dns_records WHERE id = ? AND domain_id = ?", (record_id, domain_row["id"]))
        if not rec:
            raise ServiceError("Запись не найдена", 404)
        self.db.run("DELETE FROM dns_records WHERE id = ?", (record_id,))
        try:
            self._push(domain_row, rec["name"], rec["type"])
        except ServiceError:
            self.db.run("INSERT INTO dns_records(id, domain_id, type, name, value, ttl, created_at) VALUES (?,?,?,?,?,?,?)",
                        (rec["id"], rec["domain_id"], rec["type"], rec["name"], rec["value"], rec["ttl"], rec["created_at"]))
            raise
        self.db.audit(user["id"], "dns.delete", f"{domain_row['name']}:{rec['type']}:{rec['name']}", ip)

    def set_auto_renew(self, domain_row: dict, value: bool) -> None:
        self.db.run("UPDATE domains SET auto_renew = ? WHERE id = ?", (int(value), domain_row["id"]))

    # ═══════════════════════ Биллинг ═══════════════════════
    def run_billing(self) -> dict:
        """Продление серверов и доменов. Вызывается раз в несколько минут."""
        t = now()
        stats = {"renewed": 0, "suspended": 0, "resumed": 0, "domains_renewed": 0, "domains_expired": 0}
        for s in self.db.all("SELECT * FROM servers WHERE deleted_at IS NULL AND paid_until <= ?", (t,)):
            if self.db.charge(s["user_id"], s["price_cents"], f"Продление сервера {s['name']}, 1 месяц"):
                self.db.run("UPDATE servers SET paid_until = ?, suspended = 0 WHERE id = ?",
                            (max(s["paid_until"], t) + MONTH, s["id"]))
                stats["renewed"] += 1
                if s["suspended"]:
                    try:
                        self.p.vps.power(s["provider_id"], "start")
                        stats["resumed"] += 1
                    except ProviderError as e:
                        log.warning("resume %s: %s", s["id"], e.message)
            elif not s["suspended"] and t >= s["paid_until"] + self.s.grace_days * 86400:
                try:
                    self.p.vps.power(s["provider_id"], "force_stop")
                except ProviderError as e:
                    log.warning("suspend %s: %s", s["id"], e.message)
                self.db.run("UPDATE servers SET suspended = 1 WHERE id = ?", (s["id"],))
                self.db.audit(s["user_id"], "server.suspend", str(s["id"]))
                stats["suspended"] += 1

        for d in self.db.all("SELECT * FROM domains WHERE kind = 'registered' AND status != 'expired' AND expires_at <= ?",
                             (t + 7 * 86400,)):
            if d["auto_renew"] and self.db.charge(d["user_id"], d["price_cents"], f"Продление домена {d['name']}, 1 год"):
                try:
                    exp = self.p.registrar.renew(d["name"], 1, d["expires_at"])
                except ProviderError as e:
                    self.db.credit(d["user_id"], d["price_cents"], "refund", f"Возврат: продление {d['name']} не прошло")
                    log.warning("renew %s: %s", d["name"], e.message)
                    continue
                self.db.run("UPDATE domains SET expires_at = ? WHERE id = ?", (exp, d["id"]))
                stats["domains_renewed"] += 1
            elif d["expires_at"] <= t:
                self.db.run("UPDATE domains SET status = 'expired' WHERE id = ?", (d["id"],))
                stats["domains_expired"] += 1

        self.db.run("DELETE FROM agent_metrics WHERE ts < ?", (t - 8 * 86400,))
        self.db.run("DELETE FROM sessions WHERE expires_at < ?", (t,))
        return stats


def _downsample(points: list[list[float]], step: int) -> list[list[float]]:
    """Сводит точки агента (раз в 30 с) к шагу графика провайдера — среднее по корзине."""
    if step <= 30 or not points:
        return points
    buckets: dict[int, list[float]] = {}
    for ts, v in points:
        buckets.setdefault(int(ts) - int(ts) % step, []).append(v)
    return [[k, round(sum(v) / len(v), 2)] for k, v in sorted(buckets.items())]


def _demo_agent(row: dict, plan: dict, cpu: list[list[float]]) -> tuple[dict, list[list[float]]]:
    """Демо-режим: правдоподобные данные агента, чтобы кабинет выглядел как настоящий."""
    total = int(plan.get("ram_gb", 4)) * 1024 ** 3
    disk_total = int(plan.get("disk_gb", 40)) * 1024 ** 3
    mem = [[t, round(min(92.0, 38 + v * 0.35 + (int(t) // 60 % 7) * 0.6), 2)] for t, v in cpu]
    used_pct = mem[-1][1] if mem else 40.0
    last_cpu = cpu[-1][1] if cpu else 20.0
    agent = {
        "ts": now(), "mem_used": int(total * used_pct / 100), "mem_total": total,
        "disk_used": int(disk_total * 0.31), "disk_total": disk_total, "load1": round(last_cpu / 100 * plan.get("cpu", 2), 2),
        "procs": [
            {"name": "nginx", "cpu": round(last_cpu * 0.38, 1), "mem": 212 * 1024 ** 2},
            {"name": "php-fpm8.3", "cpu": round(last_cpu * 0.27, 1), "mem": 640 * 1024 ** 2},
            {"name": "postgres", "cpu": round(last_cpu * 0.16, 1), "mem": 1210 * 1024 ** 2},
            {"name": "node", "cpu": round(last_cpu * 0.09, 1), "mem": 380 * 1024 ** 2},
            {"name": "sshd", "cpu": 0.1, "mem": 9 * 1024 ** 2},
        ],
    }
    return agent, mem
