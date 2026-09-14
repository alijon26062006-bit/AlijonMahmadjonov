"""Ҳамаи роутерҳои бот."""

from __future__ import annotations

from aiogram import Router

from . import admin, menu, purchase, topup


_root: Router | None = None


def build_router() -> Router:
    """Тартиб муҳим аст: аввал админ, баъд бахшҳо, дар охир «дигар».

    Роутерҳо якдонагӣ (singleton) ҳастанд ва як бор ба волид мепайванданд,
    бинобар ин натиҷа нигоҳ дошта мешавад — даъвати такрорӣ хато намедиҳад.
    """
    global _root
    if _root is not None:
        return _root
    root = Router(name="shop")
    root.include_router(admin.router)
    root.include_router(menu.router)
    root.include_router(purchase.router)
    root.include_router(topup.router)
    root.include_router(menu.fallback_router)
    _root = root
    return root


__all__ = ["build_router"]
