"""Тарифы, локации, образы ОС и цены доменных зон из catalog.json."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .config import BASE_DIR


@dataclass
class Catalog:
    plans: list[dict]
    locations: list[dict]
    images: list[dict]
    tlds: list[dict]

    @classmethod
    def load(cls, path: Path | None = None) -> "Catalog":
        data = json.loads((path or BASE_DIR / "catalog.json").read_text(encoding="utf-8"))
        return cls(data["plans"], data["locations"], data["images"], data["tlds"])

    def plan(self, plan_id: str) -> dict | None:
        return next((p for p in self.plans if p["id"] == plan_id), None)

    def location(self, loc_id: str) -> dict | None:
        return next((x for x in self.locations if x["id"] == loc_id), None)

    def image(self, image_id: str) -> dict | None:
        return next((x for x in self.images if x["id"] == image_id), None)

    def tld(self, zone: str) -> dict | None:
        return next((t for t in self.tlds if t["zone"] == zone), None)

    def public(self) -> dict:
        return {"plans": self.plans, "locations": self.locations, "images": self.images, "tlds": self.tlds}


def cents(amount: float) -> int:
    return int(round(amount * 100))
