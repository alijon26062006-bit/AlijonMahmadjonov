"""Регистрация доменов через ResellerClub (HTTP API LogicBoxes).

Тот же API используют и другие регистраторы на платформе LogicBoxes, поэтому адрес настраивается.
Авторизация: параметры auth-userid и api-key в каждом запросе.
Важно: в панели ResellerClub нужно разрешить IP-адрес вашего сервера (Settings → API).

Модель: все домены регистрируются на одного «клиента» реселлера (RESELLERCLUB_CUSTOMER_ID),
а владельцем домена (registrant) указывается отдельный контакт с данными вашего покупателя.
"""
from __future__ import annotations

import time

import httpx

from .base import ProviderError, RegisteredDomain

LIVE_URL = "https://httpapi.com/api"
LIVE_CHECK_URL = "https://domaincheck.httpapi.com/api"
TEST_URL = "https://test.httpapi.com/api"
YEAR = 365 * 24 * 3600


class ResellerClub:
    name = "resellerclub"

    def __init__(self, user_id: str, api_key: str, customer_id: str, test: bool = True,
                 transport: httpx.BaseTransport | None = None, timeout: float = 30.0):
        if not (user_id and api_key and customer_id):
            raise ProviderError("Не заданы RESELLERCLUB_USER_ID, RESELLERCLUB_API_KEY или RESELLERCLUB_CUSTOMER_ID",
                                code="config", status=500)
        self.auth = [("auth-userid", user_id), ("api-key", api_key)]
        self.customer_id = customer_id
        self.base = TEST_URL if test else LIVE_URL
        self.check_base = TEST_URL if test else LIVE_CHECK_URL
        self.http = httpx.Client(timeout=timeout, transport=transport, headers={"User-Agent": "hosting-panel/1.0"})

    # ── низкий уровень ──
    def _call(self, method: str, path: str, params: list[tuple[str, str]], base: str | None = None):
        url = f"{base or self.base}/{path}"
        try:
            r = self.http.request(method, url, params=self.auth + params)
        except httpx.HTTPError as e:
            raise ProviderError(f"Нет связи с регистратором: {e.__class__.__name__}", code="network") from e
        try:
            data = r.json()
        except ValueError:
            data = r.text.strip()
        if isinstance(data, dict) and str(data.get("status", "")).lower() == "error":
            raise ProviderError(_ru(str(data.get("message") or "Регистратор вернул ошибку")), code="registrar_error")
        if r.status_code >= 400:
            msg = data.get("message") if isinstance(data, dict) else str(data)[:200]
            raise ProviderError(_ru(msg or f"Ошибка регистратора {r.status_code}"), code=f"http_{r.status_code}")
        return data

    # ── проверка ──
    def check_many(self, label: str, zones: list[str]) -> dict[str, bool]:
        if not zones:
            return {}
        params = [("domain-name", label)] + [("tlds", z) for z in zones]
        data = self._call("GET", "domains/available.json", params, base=self.check_base)
        out = {}
        for z in zones:
            d = f"{label}.{z}"
            info = data.get(d) if isinstance(data, dict) else None
            out[d] = bool(info) and str(info.get("status", "")).lower() == "available"
        return out

    def check(self, domain: str) -> bool:
        label, zone = domain.split(".", 1)
        return self.check_many(label, [zone]).get(domain, False)

    # ── контакт владельца ──
    def ensure_contact(self, user: dict) -> str:
        if user.get("registrar_contact_id"):
            return user["registrar_contact_id"]
        cc, number = split_phone(user.get("phone", ""))
        params = [
            ("name", user.get("name") or user["email"]),
            ("company", user.get("company") or "N/A"),
            ("email", user["email"]),
            ("address-line-1", user.get("address", "")),
            ("city", user.get("city", "")),
            ("country", (user.get("country") or "").upper()),
            ("zipcode", user.get("zipcode", "")),
            ("phone-cc", cc),
            ("phone", number),
            ("customer-id", self.customer_id),
            ("type", "Contact"),
        ]
        data = self._call("POST", "contacts/add.json", params)
        contact_id = str(data).strip() if not isinstance(data, dict) else str(data.get("entityid") or data.get("contactid") or "")
        if not contact_id.isdigit():
            raise ProviderError("Регистратор не вернул номер контакта", code="no_contact")
        return contact_id

    # ── регистрация, продление, NS ──
    def register(self, domain: str, years: int, contact_id: str, nameservers: list[str]) -> RegisteredDomain:
        params = [("domain-name", domain), ("years", str(years))]
        params += [("ns", ns) for ns in nameservers]
        params += [
            ("customer-id", self.customer_id),
            ("reg-contact-id", contact_id), ("admin-contact-id", contact_id),
            ("tech-contact-id", contact_id), ("billing-contact-id", contact_id),
            ("invoice-option", "NoInvoice"), ("protect-privacy", "false"),
        ]
        data = self._call("POST", "domains/register.json", params)
        if not isinstance(data, dict) or str(data.get("actionstatus", "")).lower() != "success":
            desc = data.get("actionstatusdesc") if isinstance(data, dict) else str(data)
            raise ProviderError(_ru(desc or "Регистратор не подтвердил регистрацию"), code="register_failed")
        order_id = str(data.get("entityid") or "") or self.order_id(domain)
        return RegisteredDomain(order_id=order_id, expires_at=self.expiry(domain) or int(time.time()) + years * YEAR)

    def renew(self, domain: str, order_id: str, years: int, current_expiry: int) -> int:
        params = [("order-id", order_id or self.order_id(domain)), ("years", str(years)),
                  ("exp-date", str(int(current_expiry))), ("invoice-option", "NoInvoice")]
        data = self._call("POST", "domains/renew.json", params)
        if isinstance(data, dict) and data.get("actionstatus") and str(data["actionstatus"]).lower() != "success":
            raise ProviderError(_ru(data.get("actionstatusdesc") or "Продление не прошло"), code="renew_failed")
        return self.expiry(domain) or max(current_expiry, int(time.time())) + years * YEAR

    def set_nameservers(self, domain: str, order_id: str, nameservers: list[str]) -> None:
        params = [("order-id", order_id or self.order_id(domain))] + [("ns", ns) for ns in nameservers]
        data = self._call("POST", "domains/modify-ns.json", params)
        if isinstance(data, dict) and data.get("actionstatus") and str(data["actionstatus"]).lower() != "success":
            raise ProviderError(_ru(data.get("actionstatusdesc") or "Регистратор не принял неймсерверы"), code="ns_failed")

    def order_id(self, domain: str) -> str:
        data = self._call("GET", "domains/orderid.json", [("domain-name", domain)])
        return str(data).strip()

    def expiry(self, domain: str) -> int | None:
        try:
            data = self._call("GET", "domains/details-by-name.json", [("domain-name", domain), ("options", "OrderDetails")])
            return int(data.get("endtime")) if isinstance(data, dict) and data.get("endtime") else None
        except (ProviderError, ValueError, TypeError):
            return None

    def ping(self) -> str:
        """Проверка ключа, разрешённого IP и номера клиента — для админки."""
        data = self._call("GET", "customers/details-by-id.json", [("customer-id", self.customer_id)])
        who = data.get("username") or data.get("name") if isinstance(data, dict) else None
        return f"подключено, клиент {who or self.customer_id}" + (" (тестовый режим)" if self.base == TEST_URL else "")


def split_phone(raw: str) -> tuple[str, str]:
    """«992 900123456» → ("992", "900123456"). Код страны и номер хранятся через пробел."""
    parts = raw.replace("+", "").split()
    if len(parts) >= 2:
        return parts[0], "".join(parts[1:])
    digits = "".join(ch for ch in raw if ch.isdigit())
    return digits[:3], digits[3:]


_RU = {
    "invalid auth": "Регистратор отклонил ключ: проверьте RESELLERCLUB_USER_ID и RESELLERCLUB_API_KEY",
    "ip address": "Регистратор не разрешает запросы с этого IP: добавьте IP сервера в настройках API ResellerClub",
    "insufficient": "На счёте реселлера у регистратора недостаточно средств",
    "not available": "Домен уже занят",
}


def _ru(message: str) -> str:
    low = message.lower()
    for key, text in _RU.items():
        if key in low:
            return text
    return message
