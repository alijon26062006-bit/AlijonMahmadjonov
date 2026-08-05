"""
Airalo Partner API client (https://partners-api.airalo.com).
OAuth2 client_credentials for the token, then Bearer auth for packages/orders.

NOTE: written from the public Airalo Partner API docs. Field names on the
packages/orders payloads can change between API versions - if a real account
shows different JSON shapes, adjust the fetch_plans()/create_order() parsing
below; the rest of the app only depends on the normalized dict shape they
return.
"""

import random
import secrets

import requests
from django.conf import settings
from django.core.cache import cache


class AiraloError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(settings.AIRALO_CLIENT_ID and settings.AIRALO_CLIENT_SECRET)


def _get_token() -> str:
    cached = cache.get("airalo_token")
    if cached:
        return cached

    try:
        resp = requests.post(
            f"{settings.AIRALO_BASE_URL}/v2/token",
            data={
                "client_id": settings.AIRALO_CLIENT_ID,
                "client_secret": settings.AIRALO_CLIENT_SECRET,
                "grant_type": "client_credentials",
            },
            headers={"Accept": "application/json"},
            timeout=20,
        )
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        raise AiraloError(f"airalo_token_request_failed: {e}") from e

    token = (data.get("data") or {}).get("access_token") or data.get("access_token")
    expires_in = int((data.get("data") or {}).get("expires_in") or data.get("expires_in") or 3600)
    if not token:
        raise AiraloError(f"airalo_token_missing: {data}")

    cache.set("airalo_token", token, timeout=max(30, expires_in - 30))
    return token


def _request(method: str, path: str, params: dict | None = None) -> dict:
    token = _get_token()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    url = f"{settings.AIRALO_BASE_URL}{path}"

    try:
        if method == "GET":
            resp = requests.get(url, params=params or {}, headers=headers, timeout=25)
        else:
            resp = requests.post(url, data=params or {}, headers=headers, timeout=25)
        return resp.json()
    except (requests.RequestException, ValueError) as e:
        raise AiraloError(f"airalo_request_failed: {e}") from e


def fetch_plans() -> list[dict]:
    response = _request("GET", "/v2/packages", {"limit": 200})
    countries = response.get("data") or []
    if not isinstance(countries, list):
        return []

    plans = []
    for country in countries:
        country_name = country.get("title") or country.get("name") or "Unknown"
        country_slug = str(country.get("slug") or country_name.lower().replace(" ", "-"))
        country_flag = (country.get("image") or {}).get("flag") or "🌍"

        for operator in country.get("operators") or []:
            for pkg in operator.get("packages") or []:
                days = int(pkg.get("day") or pkg.get("validity") or 0)
                data_amount = pkg.get("data")
                if not data_amount and "amount" in pkg:
                    data_amount = f"{round(pkg['amount'] / 1024, 1)} GB"
                data_amount = data_amount or "—"
                price = float(pkg.get("price") or pkg.get("net_price") or 0)
                if "id" not in pkg or price <= 0:
                    continue
                plans.append({
                    "id": str(pkg["id"]),
                    "country_slug": country_slug,
                    "country_name": country_name,
                    "country_flag": country_flag,
                    "title": f"{data_amount} / {days} дней",
                    "data_amount": data_amount,
                    "days": days,
                    "price_usd": price,
                    "source": "airalo",
                })
    return plans


def create_order(package_id: str, quantity: int = 1) -> dict:
    """Places a real eSIM order with Airalo and returns normalized eSIM details."""
    response = _request("POST", "/v2/orders", {"package_id": package_id, "quantity": quantity})
    sims = (response.get("data") or {}).get("sims") or []
    if not sims:
        raise AiraloError(f"airalo_order_no_sim: {response}")

    first = sims[0]
    return {
        "iccid": first.get("iccid"),
        "qr_code_url": first.get("qrcode_url"),
        "qr_code_data": first.get("qrcode") or first.get("lpa"),
        "demo": False,
    }


def create_demo_order() -> dict:
    """Used when Airalo isn't configured yet, so the admin flow stays testable end-to-end."""
    fake_iccid = "8988" + str(random.randint(0, 999_999_999_999)).zfill(12)
    return {
        "iccid": fake_iccid,
        "qr_code_url": None,
        "qr_code_data": f"LPA:1$demo.esim.local${secrets.token_hex(8).upper()}",
        "demo": True,
    }
