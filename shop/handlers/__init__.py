"""Ҳамаи роутерҳои бот."""

from __future__ import annotations

from aiogram import F, Router

from . import admin, apikeys, constructor, menu, purchase, reviews, settings, topup


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
    # Бот танҳо дар чати шахсӣ ҷавоб медиҳад (дар гурӯҳи обуна хомӯш аст).
    root.message.filter(F.chat.type == "private")
    root.include_router(menu.commands_router)
    # Конструктор пеш аз админ: дар боти шарик бахшҳои соҳибро мебандад.
    root.include_router(constructor.tenant_router)
    root.include_router(constructor.owner_router)
    root.include_router(constructor.partner_router)
    root.include_router(admin.router)
    root.include_router(settings.router)
    root.include_router(menu.router)
    root.include_router(purchase.router)
    root.include_router(topup.router)
    root.include_router(reviews.router)
    root.include_router(apikeys.router)
    root.include_router(menu.fallback_router)
    _root = root
    return root


__all__ = ["build_router"]
