"""Забони интерфейс: тоҷикӣ (асосӣ) ё русӣ — барои ҳар бот алоҳида.

Ҳамаи модулҳо матнро аз ``texts`` мегиранд. Ин ``texts`` — миёнарав: агар
забони навсозии ҷорӣ русӣ бошад ва матн дар ``texts_ru`` ҳаст, ҳамонро
медиҳад, вагарна тоҷикиро. Забонро миёнарави бот барои ҳар навсозӣ мегузорад.
"""

from __future__ import annotations

import contextvars
import importlib

LANGS = ("tj", "ru")
LANG: contextvars.ContextVar[str] = contextvars.ContextVar("shop_lang", default="tj")

_cache: dict[str, object] = {}


def _module(lang: str):
    if lang not in _cache:
        name = "shop.texts" if lang == "tj" else f"shop.texts_{lang}"
        try:
            _cache[lang] = importlib.import_module(name)
        except ImportError:
            _cache[lang] = None
    return _cache[lang]


class _Texts:
    def __getattr__(self, name: str):
        lang = LANG.get()
        if lang != "tj":
            translated = _module(lang)
            if translated is not None and hasattr(translated, name):
                return getattr(translated, name)
        return getattr(_module("tj"), name)


texts = _Texts()


def set_lang(lang: str) -> None:
    LANG.set(lang if lang in LANGS else "tj")


#: Рақами боти шарик барои навсозии ҷорӣ (0 — боти асосӣ). Тугмаҳо аз он
#: мефаҳманд, ки панели соҳиб нишон диҳанд ё панели шарик.
TENANT: contextvars.ContextVar[int] = contextvars.ContextVar("shop_tenant", default=0)


def in_tenant() -> bool:
    return TENANT.get() > 0


def set_tenant(tenant_id: int) -> None:
    TENANT.set(int(tenant_id or 0))
