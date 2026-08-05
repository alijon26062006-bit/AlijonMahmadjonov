"""
Plan catalog. Tries the live Airalo Partner API first (when credentials are
configured); falls back to a bundled mock catalog otherwise, or if the API
call fails, so the storefront always has something to show.
"""

import logging

from django.conf import settings
from django.core.cache import cache

from . import airalo

logger = logging.getLogger(__name__)


def mock_catalog() -> list[dict]:
    return [
        {"slug": "turkey", "name": "Турция", "flag": "🇹🇷", "plans": [
            {"data": "1 GB", "days": 7, "price": 4.5},
            {"data": "3 GB", "days": 15, "price": 9.0},
            {"data": "10 GB", "days": 30, "price": 19.0},
        ]},
        {"slug": "uae", "name": "ОАЭ", "flag": "🇦🇪", "plans": [
            {"data": "1 GB", "days": 7, "price": 5.5},
            {"data": "5 GB", "days": 30, "price": 16.0},
            {"data": "10 GB", "days": 30, "price": 26.0},
        ]},
        {"slug": "russia", "name": "Россия", "flag": "🇷🇺", "plans": [
            {"data": "1 GB", "days": 7, "price": 3.5},
            {"data": "5 GB", "days": 30, "price": 12.0},
            {"data": "20 GB", "days": 30, "price": 24.0},
        ]},
        {"slug": "usa", "name": "США", "flag": "🇺🇸", "plans": [
            {"data": "1 GB", "days": 7, "price": 6.0},
            {"data": "5 GB", "days": 30, "price": 18.0},
            {"data": "10 GB", "days": 30, "price": 29.0},
        ]},
        {"slug": "schengen", "name": "Европа (Шенген)", "flag": "🇪🇺", "plans": [
            {"data": "3 GB", "days": 15, "price": 11.0},
            {"data": "10 GB", "days": 30, "price": 27.0},
            {"data": "20 GB", "days": 30, "price": 39.0},
        ]},
        {"slug": "thailand", "name": "Таиланд", "flag": "🇹🇭", "plans": [
            {"data": "1 GB", "days": 7, "price": 4.0},
            {"data": "5 GB", "days": 15, "price": 10.5},
            {"data": "10 GB", "days": 30, "price": 18.0},
        ]},
        {"slug": "china", "name": "Китай", "flag": "🇨🇳", "plans": [
            {"data": "1 GB", "days": 7, "price": 5.0},
            {"data": "5 GB", "days": 15, "price": 13.0},
            {"data": "10 GB", "days": 30, "price": 22.0},
        ]},
        {"slug": "georgia", "name": "Грузия", "flag": "🇬🇪", "plans": [
            {"data": "1 GB", "days": 7, "price": 3.0},
            {"data": "5 GB", "days": 30, "price": 10.0},
            {"data": "10 GB", "days": 30, "price": 16.0},
        ]},
        {"slug": "kazakhstan", "name": "Казахстан", "flag": "🇰🇿", "plans": [
            {"data": "1 GB", "days": 7, "price": 3.0},
            {"data": "5 GB", "days": 30, "price": 9.5},
            {"data": "10 GB", "days": 30, "price": 15.5},
        ]},
        {"slug": "egypt", "name": "Египет", "flag": "🇪🇬", "plans": [
            {"data": "1 GB", "days": 7, "price": 4.0},
            {"data": "5 GB", "days": 30, "price": 12.5},
            {"data": "10 GB", "days": 30, "price": 20.0},
        ]},
        {"slug": "uk", "name": "Великобритания", "flag": "🇬🇧", "plans": [
            {"data": "1 GB", "days": 7, "price": 5.5},
            {"data": "5 GB", "days": 30, "price": 17.0},
            {"data": "10 GB", "days": 30, "price": 27.0},
        ]},
        {"slug": "south-korea", "name": "Южная Корея", "flag": "🇰🇷", "plans": [
            {"data": "1 GB", "days": 5, "price": 4.5},
            {"data": "5 GB", "days": 15, "price": 12.0},
            {"data": "10 GB", "days": 30, "price": 21.0},
        ]},
        {"slug": "global", "name": "Весь мир", "flag": "🌍", "plans": [
            {"data": "1 GB", "days": 7, "price": 9.0},
            {"data": "3 GB", "days": 30, "price": 22.0},
            {"data": "10 GB", "days": 30, "price": 55.0},
        ]},
    ]


def mock_plans() -> list[dict]:
    plans = []
    for country in mock_catalog():
        for p in country["plans"]:
            data_slug = p["data"].lower().replace(" ", "")
            plan_id = f"{country['slug']}-{data_slug}-{p['days']}d"
            plans.append({
                "id": plan_id,
                "country_slug": country["slug"],
                "country_name": country["name"],
                "country_flag": country["flag"],
                "title": f"{p['data']} / {p['days']} дней",
                "data_amount": p["data"],
                "days": p["days"],
                "price_usd": p["price"],
                "source": "mock",
            })
    return plans


def get_all_plans() -> list[dict]:
    """Full flat list of plans - live Airalo data when configured, mock otherwise."""
    cached = cache.get("catalog_plans")
    if cached is not None:
        return cached

    plans = None
    if airalo.is_configured():
        try:
            live = airalo.fetch_plans()
            if live:
                plans = live
        except Exception:
            logger.exception("[airalo] catalog fetch failed, falling back to mock")

    if plans is None:
        plans = mock_plans()

    cache.set("catalog_plans", plans, timeout=300)
    return plans


def get_destinations() -> list[dict]:
    by_country: dict[str, dict] = {}
    for plan in get_all_plans():
        slug = plan["country_slug"]
        if slug not in by_country:
            by_country[slug] = {
                "slug": slug,
                "name": plan["country_name"],
                "flag": plan["country_flag"],
                "plans_from": plan["price_usd"],
            }
        else:
            by_country[slug]["plans_from"] = min(by_country[slug]["plans_from"], plan["price_usd"])
    return sorted(by_country.values(), key=lambda d: d["name"])


def get_destination(slug: str) -> dict | None:
    for d in get_destinations():
        if d["slug"] == slug:
            return d
    return None


def get_plans_for_country(slug: str) -> list[dict]:
    return [p for p in get_all_plans() if p["country_slug"] == slug]


def get_plan_by_id(plan_id: str) -> dict | None:
    for plan in get_all_plans():
        if plan["id"] == plan_id:
            return plan
    return None
