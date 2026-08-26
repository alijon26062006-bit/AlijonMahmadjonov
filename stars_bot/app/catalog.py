"""Каталог товаров: пакеты звёзд и подписки Premium.

Цены лежат в prices.json рядом с ботом — правь их там, код трогать не нужно.
Файл перечитывается на каждый запрос, поэтому цены можно менять без перезапуска.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.config import BASE_DIR

PRICES_FILE = BASE_DIR / "prices.json"


@dataclass(frozen=True)
class StarsPackage:
    amount: int
    price: int

    @property
    def key(self) -> str:
        return f"stars:{self.amount}"

    @property
    def title(self) -> str:
        return f"⭐ {self.amount} звёзд"


@dataclass(frozen=True)
class PremiumPackage:
    months: int
    price: int

    @property
    def key(self) -> str:
        return f"premium:{self.months}"

    @property
    def title(self) -> str:
        return f"💎 Premium {self.months} мес."


def _load() -> dict:
    with PRICES_FILE.open(encoding="utf-8") as fh:
        return json.load(fh)


def stars_packages() -> list[StarsPackage]:
    return [StarsPackage(**item) for item in _load().get("stars", [])]


def premium_packages() -> list[PremiumPackage]:
    return [PremiumPackage(**item) for item in _load().get("premium", [])]


def find_stars(amount: int) -> StarsPackage | None:
    return next((p for p in stars_packages() if p.amount == amount), None)


def find_premium(months: int) -> PremiumPackage | None:
    return next((p for p in premium_packages() if p.months == months), None)
