"""Бизнес-логика панели: заказ серверов, пароли, графики, домены, DNS и биллинг."""
from __future__ import annotations

import json
import re
import logging
import secrets
import threading
import time

from .catalog import Catalog, cents
from .cloudinit import build_user_data
from .config import Settings
from .db import Database, now
from .notify import Notifier
from .providers import ProviderError, Providers
from .security import generate_root_password, root_password_problems, sha256
from .ssh import SshError, set_root_password
from .validators import (HOST_RE, ValidationError, normalize_domain, validate_record, validate_server_name)

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
                 run_async=None, demo_password_delay: float = 1.5, notifier: Notifier | None = None):
        self.s = settings
        self.db = db
        self.catalog = catalog
        self.p = providers
        self.notify = notifier or Notifier(settings)
        self.provider_factory = None  # тесты подменяют; по умолчанию build_providers
        # Реквизиты, оплата, контакты и ключи, сохранённые в админке, важнее .env.
        site = db.get_setting("site")
        if site:
            try:
                self._apply_site(json.loads(site), rebuild=True)
            except (ValueError, ProviderError) as e:
                log.error("site settings ignored: %s", e)
        # Цены и тарифы, изменённые в админке, важнее catalog.json.
        override = db.get_setting("catalog")
        if override:
            try:
                self.catalog = Catalog.from_dict(json.loads(override))
            except (ValueError, KeyError) as e:
                log.error("catalog override ignored: %s", e)
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
        if not plan or not plan.get("enabled", True):
            raise ServiceError("Этот тариф сейчас не продаётся", field="plan")
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
        if not user.get("verified") and not user.get("is_admin"):
            active = self.db.one("SELECT COUNT(*) AS n FROM servers WHERE user_id = ? AND deleted_at IS NULL", (user["id"],))["n"]
            if active >= self.s.new_user_server_limit:
                raise ServiceError(
                    f"Новым аккаунтам доступно серверов: {self.s.new_user_server_limit}. Чтобы заказать больше, "
                    "напишите в поддержку — мы подтвердим аккаунт.", 403)

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
            self.notify.admin(f"⚠️ Не создан сервер {name} ({plan['name']}, {location}) для {user['email']}: {e.message}. "
                              "Деньги возвращены клиенту.")
            raise ServiceError(f"Не удалось создать сервер: {e.message}", 502) from None
        self.db.run("UPDATE servers SET provider_id = ?, status = ?, ipv4 = ?, ipv6 = ? WHERE id = ?",
                    (created.provider_id, created.status, created.ipv4, created.ipv6, sid))
        self.db.audit(user["id"], "server.create", str(sid), ip)
        self.notify.admin(f"🟢 Новый сервер {name}: {plan['name']}, {location}, {image}. Клиент {user['email']}, "
                          f"{price / 100:.2f} {self.s.currency}/мес.")
        self.notify.email(user["email"], f"Сервер {name} создаётся",
                          f"Ваш сервер {name} ({plan['name']}) создаётся и будет готов примерно через минуту.\n"
                          f"IPv4: {created.ipv4 or 'появится в личном кабинете'}\nЛогин: root\n"
                          "Пароль мы не отправляем по почте: он показан в кабинете при заказе или задан вами.")
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
        # Новая система — новый ключ SSH; агент ставится заново через user_data с новым токеном.
        agent_token = secrets.token_urlsafe(32)
        try:
            pw = self.p.vps.rebuild(row["provider_id"], image,
                                    user_data=build_user_data(self.s.public_url, row["id"], agent_token))
        except ProviderError as e:
            raise ServiceError(e.message, 502) from None
        self.db.run("UPDATE servers SET image = ?, status = 'rebuilding', ssh_hostkey = '', password_state = '',"
                    " agent_token_hash = ? WHERE id = ?", (image, sha256(agent_token), row["id"]))
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
            series = m.series
            if self.p.vps.name == "hetzner":
                # Hetzner считает CPU на ядро: 100 = одно ядро загружено. Приводим к 0–100% всего сервера.
                cores = max(1, int((self.catalog.plan(row["plan"]) or {}).get("cpu") or 1))
                series = {**series, "cpu": normalize_cpu(series.get("cpu", []), cores)}
            data = {"step": m.step, "series": series}
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
        zones = [t["zone"] for t in self.catalog.tlds if t.get("enabled", True)]
        if "." in name and name.split(".", 1)[1] in zones:
            first = name.split(".", 1)[1]
            zones = [first] + [z for z in zones if z != first]
        try:
            normalize_domain(f"{label}.com")
        except ValidationError:
            raise ServiceError("Имя: латиница, цифры и дефис, например mysite", field="domain") from None
        taken_here = {r["name"] for r in self.db.all(
            f"SELECT name FROM domains WHERE name IN ({','.join('?' * len(zones))})", [f"{label}.{z}" for z in zones])}
        try:
            free = self.p.registrar.check_many(label, [z for z in zones if f"{label}.{z}" not in taken_here])
        except ProviderError as e:
            raise ServiceError(f"Регистратор не ответил: {e.message}", 502) from None
        return [{"domain": f"{label}.{z}", "zone": z, "available": free.get(f"{label}.{z}", False),
                 "price": self.catalog.tld(z)["price_year"]} for z in zones]

    def domain_view(self, row: dict) -> dict:
        n = self.db.one("SELECT COUNT(*) AS n FROM dns_records WHERE domain_id = ?", (row["id"],))["n"]
        custom = json.loads(row["custom_ns"]) if row.get("custom_ns") else []
        return {"id": row["id"], "name": row["name"], "kind": row["kind"], "expires_at": row["expires_at"],
                "auto_renew": bool(row["auto_renew"]), "status": row["status"], "records": n,
                "price": row["price_cents"] / 100, "nameservers": custom or self.s.nameservers,
                "default_nameservers": self.s.nameservers, "custom_ns": bool(custom)}

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
        order_id = ""
        if register:
            zone = domain.split(".", 1)[1]
            tld = self.catalog.tld(zone)
            if not tld or not tld.get("enabled", True):
                raise ServiceError(f"Зону .{zone} мы пока не регистрируем", field="domain")
            missing = profile_missing(user)
            if missing:
                raise ServiceError("Чтобы зарегистрировать домен, заполните данные владельца в профиле: "
                                   + ", ".join(missing), 400, field="profile")
            try:
                if not self.p.registrar.check(domain):
                    raise ServiceError("Домен уже занят", 409, field="domain")
                contact = self.p.registrar.ensure_contact(user)
            except ProviderError as e:
                raise ServiceError(f"Регистратор: {e.message}", 502) from None
            if contact != user.get("registrar_contact_id"):
                self.db.run("UPDATE users SET registrar_contact_id = ? WHERE id = ?", (contact, user["id"]))
            price = cents(tld["price_year"])
            if not self.db.charge(user["id"], price, f"Регистрация домена {domain}, 1 год"):
                raise ServiceError("Недостаточно средств на балансе", 402)
            try:
                reg = self.p.registrar.register(domain, 1, contact, self.s.nameservers)
            except ProviderError as e:
                self.db.credit(user["id"], price, "refund", f"Возврат: домен {domain} не зарегистрирован")
                self.notify.admin(f"⚠️ Не зарегистрирован домен {domain} для {user['email']}: {e.message}. Деньги возвращены.")
                raise ServiceError(f"Регистратор: {e.message}", 502) from None
            expires, order_id = reg.expires_at, reg.order_id
        try:
            self.p.dns.ensure_zone(domain)
        except ProviderError as e:
            if register:
                log.error("zone for registered %s failed: %s", domain, e.message)
            else:
                raise ServiceError(f"Не удалось создать DNS-зону: {e.message}", 502) from None
        did = self.db.run(
            "INSERT INTO domains(user_id, name, kind, price_cents, expires_at, auto_renew, status, created_at,"
            " registrar, registrar_order_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (user["id"], domain, "registered" if register else "external", price, expires, 1, "active", now(),
             self.p.registrar.name if register else "", order_id))
        self.db.audit(user["id"], "domain.register" if register else "domain.add", domain, ip)
        if register:
            self.notify.admin(f"🌐 Зарегистрирован домен {domain} для {user['email']} ({price / 100:.2f} {self.s.currency}).")
            self.notify.email(user["email"], f"Домен {domain} зарегистрирован",
                              f"Домен {domain} зарегистрирован на 1 год, до {_date(expires)}.\n"
                              "DNS-записи можно настроить в личном кабинете. Обычно домен начинает открываться в течение часа.")
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

    def set_nameservers(self, user: dict, domain_row: dict, nameservers: list[str] | None, ip: str = "") -> dict:
        """None — вернуть наши неймсерверы; список — свои (например, Cloudflare)."""
        if domain_row["kind"] != "registered":
            raise ServiceError("Неймсерверы меняются у регистратора, где куплен домен", 400)
        if nameservers is None:
            ns, stored = self.s.nameservers, ""
        else:
            ns = [n.strip().lower().rstrip(".") for n in nameservers if n.strip()]
            if not 2 <= len(ns) <= 13:
                raise ServiceError("Укажите от 2 до 13 неймсерверов", field="nameservers")
            if len(set(ns)) != len(ns) or not all(HOST_RE.match(n) for n in ns):
                raise ServiceError("Неймсервер — это имя хоста, например ns1.example.com", field="nameservers")
            stored = json.dumps(ns)
        try:
            self.p.registrar.set_nameservers(domain_row["name"], domain_row["registrar_order_id"], ns)
        except ProviderError as e:
            raise ServiceError(f"Регистратор: {e.message}", 502) from None
        self.db.run("UPDATE domains SET custom_ns = ? WHERE id = ?", (stored, domain_row["id"]))
        self.db.audit(user["id"], "domain.nameservers", f"{domain_row['name']}:{','.join(ns)}", ip)
        return self.domain_view(self.db.one("SELECT * FROM domains WHERE id = ?", (domain_row["id"],)))

    # ═══════════════════════ Профиль ═══════════════════════
    PROFILE_FIELDS = ("name", "company", "phone", "country", "city", "address", "zipcode")

    def update_profile(self, user: dict, data: dict) -> dict:
        clean = {}
        for f in self.PROFILE_FIELDS:
            v = str(data.get(f) or "").strip()
            if len(v) > 120:
                raise ServiceError("Слишком длинное значение", field=f)
            clean[f] = v
        clean["country"] = clean["country"].upper()
        if clean["country"] and not re.fullmatch(r"[A-Z]{2}", clean["country"]):
            raise ServiceError("Страна — двухбуквенный код, например TJ, UZ, KZ, RU", field="country")
        if clean["phone"]:
            digits = re.sub(r"[^\d ]", "", clean["phone"]).split()
            if len(digits) < 2 or not (1 <= len(digits[0]) <= 3) or not 5 <= len("".join(digits[1:])) <= 13:
                raise ServiceError("Телефон: код страны и номер через пробел, например +992 900123456", field="phone")
            clean["phone"] = f"{digits[0]} {''.join(digits[1:])}"
        changed_contact = any(clean[f] != (user.get(f) or "") for f in self.PROFILE_FIELDS)
        sets = ", ".join(f"{f} = ?" for f in self.PROFILE_FIELDS)
        # Данные владельца изменились — при следующей регистрации у регистратора создастся новый контакт.
        self.db.run(f"UPDATE users SET {sets}{', registrar_contact_id = ' + chr(39) * 2 if changed_contact else ''} WHERE id = ?",
                    (*[clean[f] for f in self.PROFILE_FIELDS], user["id"]))
        return self.db.one("SELECT * FROM users WHERE id = ?", (user["id"],))

    # ═══════════════════════ Пополнение баланса ═══════════════════════
    def create_topup_request(self, user: dict, amount: float, method: str, reference: str, ip: str = "") -> dict:
        if not self.s.payment_methods:
            raise ServiceError("Способы оплаты ещё не настроены. Напишите в поддержку.", 501)
        if method not in self.s.payment_methods:
            raise ServiceError("Выберите способ оплаты", field="method")
        if not 1 <= amount <= 10000:
            raise ServiceError("Сумма от 1 до 10 000", field="amount")
        reference = reference.strip()[:200]
        if not reference:
            raise ServiceError("Укажите номер или время перевода, чтобы мы нашли платёж", field="reference")
        pending = self.db.one("SELECT COUNT(*) AS n FROM topup_requests WHERE user_id = ? AND status = 'pending'", (user["id"],))["n"]
        if pending >= 5:
            raise ServiceError("У вас уже 5 заявок на проверке. Дождитесь их подтверждения.", 429)
        rid = self.db.run("INSERT INTO topup_requests(user_id, amount_cents, method, reference, created_at) VALUES (?,?,?,?,?)",
                          (user["id"], cents(amount), method, reference, now()))
        self.db.audit(user["id"], "billing.topup_request", f"{rid}:{amount}", ip)
        self.notify.admin(f"💳 Заявка на пополнение №{rid}: {amount:.2f} {self.s.currency} от {user['email']}\n"
                          f"Способ: {method}\nПеревод: {reference}\nПодтвердите в админке.")
        return self.db.one("SELECT * FROM topup_requests WHERE id = ?", (rid,))

    def decide_topup(self, admin: dict, request_id: int, approve: bool, note: str = "", ip: str = "") -> dict:
        with self.db.transaction():
            req = self.db.one("SELECT * FROM topup_requests WHERE id = ?", (request_id,))
            if not req:
                raise ServiceError("Заявка не найдена", 404)
            if req["status"] != "pending":
                raise ServiceError("Заявка уже обработана", 409)
            self.db.run("UPDATE topup_requests SET status = ?, admin_note = ?, decided_at = ?, decided_by = ? WHERE id = ?",
                        ("approved" if approve else "rejected", note[:200], now(), admin["id"], request_id))
            if approve:
                self.db.credit(req["user_id"], req["amount_cents"], "topup", f"Пополнение: {req['method']}")
        user = self.db.one("SELECT email FROM users WHERE id = ?", (req["user_id"],))
        amount = req["amount_cents"] / 100
        self.db.audit(admin["id"], "admin.topup_" + ("approve" if approve else "reject"), f"{request_id}:{amount}", ip)
        if approve:
            self.notify.email(user["email"], "Баланс пополнен",
                              f"Мы зачислили {amount:.2f} {self.s.currency} на ваш баланс ({req['method']}).")
        else:
            self.notify.email(user["email"], "Платёж не найден",
                              f"Мы не нашли перевод на {amount:.2f} {self.s.currency} ({req['method']}, {req['reference']})."
                              + (f"\nКомментарий: {note}" if note else "") + "\nНапишите в поддержку, мы разберёмся.")
        return self.db.one("SELECT * FROM topup_requests WHERE id = ?", (request_id,))

    # ═══════════════════════ Цены и тарифы (админка) ═══════════════════════
    def update_catalog(self, admin: dict, plans: list[dict], tlds: list[dict], ip: str = "") -> dict:
        current = {p["id"]: p for p in self.catalog.plans}
        new_plans = []
        for p in plans:
            pid = str(p.get("id", ""))
            if pid not in current:
                raise ServiceError(f"Неизвестный тариф {pid}")
            try:
                price = round(float(p["price_month"]), 2)
            except (KeyError, TypeError, ValueError):
                raise ServiceError(f"Цена тарифа {pid} — число", field=pid) from None
            if not 0.5 <= price <= 10000:
                raise ServiceError(f"Цена тарифа {pid}: от 0.5 до 10 000", field=pid)
            st = str(p.get("server_type") or current[pid]["server_type"]).strip()
            if not re.fullmatch(r"[a-z0-9-]{2,30}", st):
                raise ServiceError(f"Тип сервера {pid}: латиница и цифры, например cx23", field=pid)
            new_plans.append({**current[pid], "price_month": price, "server_type": st, "enabled": bool(p.get("enabled", True)),
                              "featured": bool(p.get("featured", current[pid].get("featured", False)))})
        if len(new_plans) != len(current):
            raise ServiceError("Нужно передать все тарифы")
        new_tlds = []
        seen = set()
        for t in tlds:
            zone = str(t.get("zone", "")).strip().lower().lstrip(".")
            if not re.fullmatch(r"[a-z]{2,24}(\.[a-z]{2,24})?", zone) or zone in seen:
                raise ServiceError(f"Некорректная зона «{zone}»", field="tlds")
            try:
                price = round(float(t["price_year"]), 2)
            except (KeyError, TypeError, ValueError):
                raise ServiceError(f"Цена зоны .{zone} — число", field="tlds") from None
            if not 0.5 <= price <= 10000:
                raise ServiceError(f"Цена зоны .{zone}: от 0.5 до 10 000", field="tlds")
            seen.add(zone)
            new_tlds.append({"zone": zone, "price_year": price, "enabled": bool(t.get("enabled", True))})
        data = {**self.catalog.to_dict(), "plans": new_plans, "tlds": new_tlds}
        self.db.set_setting("catalog", json.dumps(data, ensure_ascii=False))
        self.catalog = Catalog.from_dict(data)
        self.db.audit(admin["id"], "admin.catalog", f"{len(new_plans)} plans, {len(new_tlds)} tlds", ip)
        return data

    # ═══════════════════════ Настройки сайта (админка) ═══════════════════════
    SITE_FIELDS = {
        "payment_methods": "list", "payment_instructions": "text",
        "company_name": "str", "company_details": "text",
        "support_telegram": "str", "support_email": "str", "support_phone": "str",
        "telegram_bot_token": "secret", "telegram_admin_chat_id": "str",
        "smtp_host": "str", "smtp_port": "int", "smtp_user": "str", "smtp_password": "secret", "smtp_from": "str",
        "hetzner_token": "secret", "rc_user_id": "str", "rc_api_key": "secret", "rc_customer_id": "str", "rc_test": "bool",
    }
    KEY_FIELDS = ("hetzner_token", "rc_user_id", "rc_api_key", "rc_customer_id", "rc_test")

    def site_settings(self) -> dict:
        out = {}
        for f, kind in self.SITE_FIELDS.items():
            v = getattr(self.s, f)
            if kind == "secret":
                out[f] = ""
                out[f + "_set"] = bool(v)
            else:
                out[f] = v
        out["vps_provider"], out["registrar"] = self.p.vps.name, self.p.registrar.name
        return out

    def _settings_with(self, data: dict) -> Settings:
        import copy
        s = copy.copy(self.s)
        for f, v in data.items():
            setattr(s, f, v)
        if s.hetzner_token:
            s.vps_provider = s.dns_provider = "hetzner"
        if s.rc_user_id and s.rc_api_key and s.rc_customer_id:
            s.registrar = "resellerclub"
        return s

    def _build(self, s: Settings) -> Providers:
        from .providers import build_providers
        return (self.provider_factory or build_providers)(s)

    def _apply_site(self, data: dict, rebuild: bool) -> None:
        new = self._settings_with({k: v for k, v in data.items() if k in self.SITE_FIELDS})
        if rebuild and any(k in data for k in self.KEY_FIELDS):
            self.p = self._build(new)
            self.cache = _Cache()
        for f in list(self.SITE_FIELDS) + ["vps_provider", "dns_provider", "registrar"]:
            setattr(self.s, f, getattr(new, f))

    def update_site_settings(self, admin: dict, data: dict, ip: str = "") -> dict:
        clean = {}
        for f, kind in self.SITE_FIELDS.items():
            if f not in data or data[f] is None:
                continue
            v = data[f]
            if kind == "secret":
                v = str(v).strip()
                if not v:
                    continue  # пусто — оставить сохранённый
            elif kind == "list":
                items = v if isinstance(v, list) else str(v).split(",")
                v = [str(x).strip()[:40] for x in items if str(x).strip()][:10]
            elif kind == "int":
                try:
                    v = int(v)
                except (TypeError, ValueError):
                    raise ServiceError("Порт SMTP — число", field=f) from None
                if not 1 <= v <= 65535:
                    raise ServiceError("Порт SMTP от 1 до 65535", field=f)
            elif kind == "bool":
                v = bool(v)
            else:
                v = str(v).strip()[:2000 if kind == "text" else 200]
            if f == "support_telegram":
                v = v.lstrip("@").removeprefix("https://t.me/")
            if f == "support_email" and v and ("@" not in v or "." not in v.split("@")[-1]):
                raise ServiceError("Некорректный email поддержки", field=f)
            clean[f] = v

        # Новые ключи сначала проверяем у поставщика и сохраняем, только если они работают.
        if any(k in clean and clean[k] != getattr(self.s, k) for k in self.KEY_FIELDS):
            candidate = self._settings_with(clean)
            try:
                providers = self._build(candidate)
                if "hetzner_token" in clean and candidate.vps_provider == "hetzner":
                    providers.vps.server_types()
                    providers.vps.check_write()
                if candidate.registrar == "resellerclub" and any(k in clean for k in ("rc_user_id", "rc_api_key", "rc_customer_id", "rc_test")):
                    providers.registrar.ping()
            except ProviderError as e:
                raise ServiceError(f"Ключ не подошёл: {e.message}", 400) from None
            self.p = providers
            self.cache = _Cache()

        stored = json.loads(self.db.get_setting("site") or "{}")
        stored.update(clean)
        self.db.set_setting("site", json.dumps(stored, ensure_ascii=False))
        self._apply_site(clean, rebuild=False)
        self.db.audit(admin["id"], "admin.settings", ",".join(sorted(clean)), ip)
        return self.site_settings()

    # ═══════════════════════ Готовность к продажам ═══════════════════════
    def readiness(self) -> list[dict]:
        s = self.s
        checks = []

        def add(key, title, ok, detail, required=True):
            checks.append({"key": key, "title": title, "ok": bool(ok), "detail": detail, "required": required})

        add("secret", "Секретный ключ сессий", s.secret_key and len(s.secret_key) >= 32 and _env_has("SECRET_KEY"),
            "Задан в .env" if _env_has("SECRET_KEY") else "Задайте SECRET_KEY, иначе после перезапуска все выйдут из кабинета")
        add("https", "Сайт работает по HTTPS", s.public_url.startswith("https://") and s.cookie_secure,
            f"PUBLIC_URL={s.public_url}, COOKIE_SECURE={'да' if s.cookie_secure else 'нет'}")
        try:
            if self.p.vps.name == "hetzner":
                types = self.p.vps.server_types()
                self.p.vps.check_write()
                names = {t["name"] for t in types}
                missing = [p["server_type"] for p in self.catalog.plans if p.get("enabled", True) and p["server_type"] not in names]
                add("vps", "Серверы: Hetzner", not missing,
                    "Ключ работает" + (f", но нет типов: {', '.join(missing)} — поправьте тарифы" if missing else ""))
            else:
                add("vps", "Серверы: Hetzner", False, "Демо-режим. Вставьте токен Hetzner: Админка → Настройки → Ключи")
        except ProviderError as e:
            add("vps", "Серверы: Hetzner", False, e.message)
        add("dns", "DNS: Hetzner", self.p.dns.name == "hetzner",
            "Подключено" if self.p.dns.name == "hetzner" else "Подключится вместе с токеном Hetzner")
        try:
            detail = self.p.registrar.ping()
            add("registrar", "Домены: регистратор", self.p.registrar.name != "demo", detail)
        except ProviderError as e:
            add("registrar", "Домены: регистратор", False, e.message)
        if self.p.registrar.name == "resellerclub" and s.rc_test:
            add("registrar_live", "Регистратор в боевом режиме", False,
                "Сейчас тестовый сервер ResellerClub. Когда проверите покупку домена, выключите «Тестовый режим» в Настройках")
        add("payments", "Приём оплаты", bool(s.payment_methods and s.payment_instructions) and not s.demo_payments,
            "Демо-пополнение включено: выключите DEMO_PAYMENTS в .env" if s.demo_payments
            else ("Способы: " + ", ".join(s.payment_methods)) if s.payment_methods and s.payment_instructions
            else "Укажите способы оплаты и реквизиты: Админка → Настройки")
        add("telegram", "Уведомления вам в Telegram", s.telegram_bot_token and s.telegram_admin_chat_id,
            "Подключены" if s.telegram_bot_token else "Укажите бота и Chat ID: Админка → Настройки", required=False)
        add("email", "Письма клиентам", s.smtp_host and s.smtp_from,
            f"Через {s.smtp_host}" if s.smtp_host else "Укажите почтовый сервер: Админка → Настройки", required=False)
        add("company", "Реквизиты для документов", s.company_name and s.company_details,
            (s.company_name if s.company_details else "") or "Укажите название и реквизиты (попадут в оферту): Админка → Настройки")
        add("support", "Контакты поддержки", s.support_telegram or s.support_email or s.support_phone,
            ", ".join(x for x in (s.support_telegram and "@" + s.support_telegram, s.support_email, s.support_phone) if x)
            or "Укажите Telegram или email поддержки: Админка → Настройки")
        return checks

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
                owner = self.db.one("SELECT email FROM users WHERE id = ?", (s["user_id"],))
                self.notify.email(owner["email"], f"Сервер {s['name']} приостановлен",
                                  f"Оплата сервера {s['name']} закончилась {_date(s['paid_until'])}, на балансе не хватило денег, "
                                  "поэтому мы его выключили. Данные сохранены. Пополните баланс — сервер включится автоматически.")
                self.notify.admin(f"⏸ Приостановлен сервер {s['name']} клиента {owner['email']} за неуплату.")

        for d in self.db.all("SELECT * FROM domains WHERE kind = 'registered' AND status != 'expired' AND expires_at <= ?",
                             (t + 7 * 86400,)):
            if d["auto_renew"] and self.db.charge(d["user_id"], d["price_cents"], f"Продление домена {d['name']}, 1 год"):
                try:
                    exp = self.p.registrar.renew(d["name"], d["registrar_order_id"], 1, d["expires_at"])
                except ProviderError as e:
                    self.db.credit(d["user_id"], d["price_cents"], "refund", f"Возврат: продление {d['name']} не прошло")
                    log.warning("renew %s: %s", d["name"], e.message)
                    self.notify.admin(f"⚠️ Не продлён домен {d['name']}: {e.message}. Деньги возвращены клиенту, проверьте вручную.")
                    continue
                self.db.run("UPDATE domains SET expires_at = ? WHERE id = ?", (exp, d["id"]))
                stats["domains_renewed"] += 1
            elif d["expires_at"] <= t:
                self.db.run("UPDATE domains SET status = 'expired' WHERE id = ?", (d["id"],))
                stats["domains_expired"] += 1

        stats["reminders"] = self._reminders(t)
        self.db.run("DELETE FROM agent_metrics WHERE ts < ?", (t - 8 * 86400,))
        self.db.run("DELETE FROM sessions WHERE expires_at < ?", (t,))
        return stats

    def _reminders(self, t: int) -> int:
        """Письмо за 3 дня до продления сервера и за 14 дней до продления домена, если на балансе не хватает."""
        sent = 0
        rows = self.db.all(
            "SELECT s.id, s.name, s.price_cents, s.paid_until, u.email, u.balance_cents FROM servers s JOIN users u ON u.id = s.user_id"
            " WHERE s.deleted_at IS NULL AND s.suspended = 0 AND s.paid_until BETWEEN ? AND ? AND s.reminded_at < s.paid_until - ?",
            (t, t + 3 * 86400, 3 * 86400))
        for r in rows:
            if r["balance_cents"] < r["price_cents"]:
                self.notify.email(r["email"], f"Пополните баланс для сервера {r['name']}",
                                  f"{_date(r['paid_until'])} нужно продлить сервер {r['name']} за {r['price_cents'] / 100:.2f} "
                                  f"{self.s.currency}, а на балансе {r['balance_cents'] / 100:.2f}. Без продления сервер выключится "
                                  f"через {self.s.grace_days} дн. после этой даты.")
                sent += 1
            self.db.run("UPDATE servers SET reminded_at = ? WHERE id = ?", (t, r["id"]))
        rows = self.db.all(
            "SELECT d.id, d.name, d.price_cents, d.expires_at, d.auto_renew, u.email, u.balance_cents FROM domains d"
            " JOIN users u ON u.id = d.user_id WHERE d.kind = 'registered' AND d.status = 'active'"
            " AND d.expires_at BETWEEN ? AND ? AND d.reminded_at < d.expires_at - ?",
            (t, t + 14 * 86400, 14 * 86400))
        for r in rows:
            if not r["auto_renew"] or r["balance_cents"] < r["price_cents"]:
                why = "автопродление выключено" if not r["auto_renew"] else (
                    f"на балансе {r['balance_cents'] / 100:.2f}, а продление стоит {r['price_cents'] / 100:.2f} {self.s.currency}")
                self.notify.email(r["email"], f"Домен {r['name']} скоро истекает",
                                  f"Регистрация домена {r['name']} заканчивается {_date(r['expires_at'])}, а {why}. "
                                  "После окончания домен перестанет открываться, а потом его может занять кто-то другой.")
                sent += 1
            self.db.run("UPDATE domains SET reminded_at = ? WHERE id = ?", (t, r["id"]))
        return sent


def normalize_cpu(points: list[list[float]], cores: int) -> list[list[float]]:
    return [[t, round(min(100.0, v / cores), 2)] for t, v in points]


def profile_missing(user: dict) -> list[str]:
    """Что нужно заполнить, чтобы регистратор принял владельца домена."""
    names = {"name": "имя", "phone": "телефон", "country": "страна", "city": "город", "address": "адрес", "zipcode": "индекс"}
    return [label for f, label in names.items() if not (user.get(f) or "").strip()]


def _date(ts: int | None) -> str:
    return time.strftime("%d.%m.%Y", time.localtime(ts)) if ts else "—"


def _env_has(name: str) -> bool:
    import os
    return bool(os.environ.get(name))


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
