"""Ҳамаи роутерҳои бот."""

from __future__ import annotations

from aiogram import Router

from . import admin, menu, purchase, topup


def build_router() -> Router:
    """Тартиб муҳим аст: аввал админ, баъд бахшҳо, дар охир «дигар»."""
    root = Router(name="shop")
    root.include_router(admin.router)
    root.include_router(menu.router)
    root.include_router(purchase.router)
    root.include_router(topup.router)
    root.include_router(menu.fallback_router)
    return root


__all__ = ["build_router"]
