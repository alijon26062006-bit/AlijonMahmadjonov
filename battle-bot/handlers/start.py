"""/start, deep-links и главное меню."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

from aiogram import Bot

from config import Config
from core.engine import BattleEngine
from handlers.referral import welcome_invited
from handlers import voting
from handlers.voting import show_voting
from services import keyboards, links, referral, sponsors, texts
from storage.repo import Repo
from storage.settings import Settings

router = Router(name="start")


@router.message(CommandStart(deep_link=True))
async def start_with_payload(
    message: Message,
    command: CommandObject,
    bot: Bot,
    repo: Repo,
    config: Config,
    engine: BattleEngine,
    settings: Settings,
) -> None:
    kind, value = links.parse_start_payload(command.args)

    # приглашение запоминаем до создания пользователя: засчитываем только новичков
    invited = kind == "ref" and value is not None and referral.remember(
        repo, message.from_user.id, value, settings
    )

    repo.upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name)

    if kind == "vote" and value is not None:
        # экран голосования открываем только подписчику — голос без подписки невозможен
        if await voting.gate(message, value, config, settings, message.from_user.id):
            return
        await show_voting(message, value, repo, config)
        return

    if kind == "join":
        await _do_join(message, repo, config, engine, settings)
        return

    await _greet(message, config)
    if invited:
        await welcome_invited(message, bot, repo, config, settings)


@router.message(CommandStart())
async def start(message: Message, repo: Repo, config: Config) -> None:
    repo.upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await _greet(message, config)


async def _greet(message: Message, config: Config) -> None:
    await message.answer(
        texts.welcome(config.channel_url),
        reply_markup=keyboards.main_menu(config),
        disable_web_page_preview=True,
    )


@router.message(F.text.in_(keyboards.variants(keyboards.BTN_JOIN)))
@router.message(Command("join", "battle"))
async def join_button(
    message: Message, repo: Repo, config: Config, engine: BattleEngine, settings: Settings
) -> None:
    await _do_join(message, repo, config, engine, settings)


@router.callback_query(F.data.in_({"join", "join:retry"}))
async def join_again(
    callback: CallbackQuery, repo: Repo, config: Config, engine: BattleEngine,
    settings: Settings
) -> None:
    await _do_join(callback.message, repo, config, engine, settings, user=callback.from_user)
    await callback.answer()


async def _do_join(
    message: Message,
    repo: Repo,
    config: Config,
    engine: BattleEngine,
    settings: Settings,
    user=None,
) -> None:
    user = user or message.from_user
    repo.upsert_user(user.id, user.username, user.first_name)

    unsubscribed = await sponsors.missing(message.bot, config, settings, user.id)
    if unsubscribed:
        await message.answer(
            sponsors.text(unsubscribed),
            reply_markup=sponsors.keyboard(unsubscribed, "join:retry"),
            disable_web_page_preview=True,
        )
        return

    nickname = user.username
    if not nickname:
        if config.require_username:
            await message.answer(texts.NEED_USERNAME)
            return
        nickname = user.first_name or f"id{user.id}"

    accepted, response = await engine.join(user.id, nickname)
    await message.answer(
        response,
        reply_markup=None if accepted else keyboards.join_again(config),
        disable_web_page_preview=True,
    )


@router.message(F.text.in_(keyboards.variants(keyboards.BTN_HELP)))
@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(texts.HELP, disable_web_page_preview=True)


@router.message(F.text.in_(keyboards.variants(keyboards.BTN_PROFILE)))
@router.message(Command("me"))
async def profile(message: Message, repo: Repo) -> None:
    repo.upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer(
        texts.profile(
            message.from_user.username,
            repo.stats_for(message.from_user.id),
            repo.vote_balance(message.from_user.id),
        )
    )


@router.message(Command("top"))
async def leaderboard(message: Message, repo: Repo) -> None:
    await message.answer(texts.leaderboard(repo.leaderboard()))


@router.message(Command("vote"))
async def my_match(message: Message, repo: Repo, config: Config) -> None:
    """Открыть экран голосования своего текущего матча."""
    match = repo.active_match_for(message.from_user.id)
    if match is None:
        battle = repo.current_battle()
        match = repo.latest_open_match(int(battle["id"])) if battle else None
    if match is None:
        await message.answer(texts.NO_ACTIVE_BATTLE)
        return
    await show_voting(message, int(match["id"]), repo, config)
