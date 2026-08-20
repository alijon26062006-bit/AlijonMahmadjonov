"""Экран приглашений и начисление голоса за приведённого друга."""
from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from config import Config
from services import keyboards, links, referral, texts
from storage.repo import Repo
from storage.settings import Settings

router = Router(name="referral")


@router.message(F.text.in_(keyboards.variants(keyboards.BTN_INVITE)))
@router.message(Command("invite"))
async def show_invite(
    message: Message, repo: Repo, config: Config, settings: Settings, user=None
) -> None:
    """Экран приглашений. user передаётся, когда экран открыт кнопкой."""
    if not settings.get("referral_enabled"):
        await message.answer("Приглашения сейчас отключены.")
        return

    user = user or message.from_user
    repo.upsert_user(user.id, user.username, user.first_name)
    invited, rewarded = repo.referral_stats(user.id)
    await message.answer(
        texts.invite_screen(
            link=links.invite_link(config.bot_username, user.id),
            invited=invited,
            rewarded=rewarded,
            reward=settings.get("referral_reward"),
            channel_url=config.channel_url,
        ),
        disable_web_page_preview=True,
    )


async def welcome_invited(
    message: Message, bot: Bot, repo: Repo, config: Config, settings: Settings
) -> None:
    """Приглашённый открыл ссылку: наградить сразу или попросить подписаться."""
    if await referral.try_reward(bot, repo, config, settings, message.from_user.id):
        return
    if repo.pending_referral(message.from_user.id) is None:
        return

    await message.answer(
        texts.referral_pending(config.channel_url),
        reply_markup=keyboards.invited_check(config.channel_url),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "ref:check")
async def check_subscription(
    callback: CallbackQuery, bot: Bot, repo: Repo, config: Config, settings: Settings
) -> None:
    inviter = await referral.try_reward(bot, repo, config, settings, callback.from_user.id)
    if inviter:
        await callback.message.edit_text("✅ <b>Спасибо!</b> Приглашение засчитано.")
        await callback.answer("Готово")
        return

    if repo.pending_referral(callback.from_user.id) is None:
        await callback.answer("Это приглашение уже засчитано.", show_alert=True)
        return

    await callback.answer("Подписки пока не вижу. Подпишитесь и нажмите ещё раз.", show_alert=True)
