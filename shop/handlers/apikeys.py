"""«🔌 API барои барномасозон»: харидор худаш калиди API месозад."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from .. import devapi, keyboards, texts
from ..config import Config
from ..db import Database
from .common import current_user, safe_edit

router = Router(name="apikeys")


async def _show(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    user = current_user(cb, db)
    key = db.active_api_key(user.id)
    is_open = devapi.api_open(db, cfg)
    url = devapi.docs_url(cfg)
    await safe_edit(
        cb,
        texts.api_screen(key, user.balance, url, is_open, cfg.currency),
        keyboards.api_menu(key is not None, url, is_open),
    )


@router.callback_query(F.data == keyboards.CB_API)
async def cb_api(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    await _show(cb, db, cfg)
    await cb.answer()


@router.callback_query(F.data == keyboards.CB_API_NEW)
async def cb_api_new(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    if not devapi.api_open(db, cfg):
        await cb.answer(texts.API_CLOSED, show_alert=True)
        return
    if db.active_api_key(cb.from_user.id) is not None:
        # Калиди кор мекардагиро бе пурсиш иваз намекунем — барномаи харидор меафтад.
        await safe_edit(
            cb, texts.API_CONFIRM_RENEW,
            keyboards.api_confirm(texts.BTN_API_YES_RENEW, keyboards.CB_API_NEW_OK),
        )
        await cb.answer()
        return
    await _create(cb, db, cfg)


@router.callback_query(F.data == keyboards.CB_API_NEW_OK)
async def cb_api_new_ok(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    if not devapi.api_open(db, cfg):
        await cb.answer(texts.API_CLOSED, show_alert=True)
        return
    await _create(cb, db, cfg)


async def _create(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    user = current_user(cb, db)
    plain = devapi.issue_key(db, user.id)
    await safe_edit(cb, texts.api_key_created(plain), keyboards.api_after_create(devapi.docs_url(cfg)))
    await cb.answer("✅")


@router.callback_query(F.data == keyboards.CB_API_DEL)
async def cb_api_del(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    if db.active_api_key(cb.from_user.id) is None:
        await _show(cb, db, cfg)
        await cb.answer()
        return
    await safe_edit(
        cb, texts.API_CONFIRM_REVOKE,
        keyboards.api_confirm(texts.BTN_API_YES_REVOKE, keyboards.CB_API_DEL_OK),
    )
    await cb.answer()


@router.callback_query(F.data == keyboards.CB_API_DEL_OK)
async def cb_api_del_ok(cb: CallbackQuery, db: Database, cfg: Config) -> None:
    db.revoke_api_keys(cb.from_user.id)
    await _show(cb, db, cfg)
    await cb.answer(texts.API_REVOKED)
