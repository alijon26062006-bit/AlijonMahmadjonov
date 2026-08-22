"""/start, deep-links и главное меню."""
from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

from aiogram import Bot

from config import Config
from core.engine import BattleEngine
from handlers.referral import welcome_invited
from handlers import voting
from handlers.voting import show_voting
from services import keyboards, links, referral, sponsors, texts, ui
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
        if await voting.gate(bot, message, value, config, settings, message.from_user.id):
            return
        await show_voting(
            message, value, repo, config, links.vote_target(command.args),
            scope=settings.get("free_vote_scope"),
        )
        return

    if kind == "join":
        await _do_join(message, repo, config, engine, settings, bot=bot)
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
    message: Message, bot: Bot, repo: Repo, config: Config, engine: BattleEngine,
    settings: Settings,
) -> None:
    await _do_join(message, repo, config, engine, settings, bot=bot)


@router.callback_query(F.data.in_({"join", "join:retry"}))
async def join_again(
    callback: CallbackQuery, repo: Repo, config: Config, engine: BattleEngine,
    settings: Settings
) -> None:
    await _do_join(
        callback, repo, config, engine, settings,
        user=callback.from_user, bot=callback.bot,
    )
    await callback.answer()


async def _do_join(
    target,
    repo: Repo,
    config: Config,
    engine: BattleEngine,
    settings: Settings,
    user=None,
    bot: Bot | None = None,
) -> None:
    user = user or ui.message_of(target).from_user
    repo.upsert_user(user.id, user.username, user.first_name)

    # бот берётся явно: у сообщения под кнопкой его может не оказаться
    bot = bot or getattr(ui.message_of(target), "bot", None)
    unsubscribed = await sponsors.missing(bot, config, settings, user.id)
    if unsubscribed:
        await ui.send(
            target,
            sponsors.text(unsubscribed),
            reply_markup=sponsors.keyboard(unsubscribed, "join:retry"),
            disable_web_page_preview=True,
        )
        return

    nickname = user.username
    if not nickname:
        if config.require_username:
            await ui.send(target, texts.NEED_USERNAME)
            return
        nickname = user.first_name or f"id{user.id}"

    # отдыхающему показываем не голый отказ, а кнопку выкупа
    rest = repo.cooldown_for(user.id)
    price = int(settings.get("cooldown_skip_price") or 0)
    if rest is not None and price:
        _, response = await engine.join(user.id, nickname)
        await ui.send(
            target, response, reply_markup=keyboards.buy_cooldown(price),
            disable_web_page_preview=True,
        )
        return

    accepted, response = await engine.join(user.id, nickname)
    if accepted and settings.get("member_channels_enabled"):
        # записался — самое время предложить рекламировать себя в своём канале
        markup = keyboards.after_join()
    elif accepted:
        markup = None
    else:
        markup = keyboards.join_again(config)
    await ui.send(target, response, reply_markup=markup, disable_web_page_preview=True)


@router.message(F.text.in_(keyboards.variants(keyboards.BTN_HELP)))
@router.message(Command("help"))
async def help_command(message: Message, config: Config, settings: Settings) -> None:
    await message.answer(
        texts.help_screen(),
        reply_markup=keyboards.help_links(_help_links(config, settings), config.premium_emoji),
        disable_web_page_preview=True,
    )


def _help_links(config: Config, settings: Settings) -> dict[str, str]:
    """Ссылки для кнопок «Помощи».

    Канал с батлами бот знает сам, поэтому его кнопка работает сразу — но
    админ может задать свою ссылку и перекрыть её.
    """
    links = {label_key: settings.get(label_key) for _, label_key, _ in keyboards.HELP_LINKS}
    if not links.get("link_battles"):
        links["link_battles"] = config.channel_url
    return links


@router.callback_query(F.data == "help:how")
async def how_it_works(callback: CallbackQuery) -> None:
    """Подробные правила — отдельной кнопкой, чтобы экран остался коротким."""
    await ui.send(callback, texts.HELP, disable_web_page_preview=True)
    await callback.answer()


@router.message(F.text.in_(keyboards.variants(keyboards.BTN_PROFILE)))
@router.message(Command("me"))
async def profile(message: Message, repo: Repo, settings: Settings) -> None:
    user_id = message.from_user.id
    repo.upsert_user(user_id, message.from_user.username, message.from_user.first_name)

    body = texts.profile(
        message.from_user.username, repo.stats_for(user_id), repo.vote_balance(user_id)
    )
    # если человек отдыхает после приза — он должен видеть это в профиле
    rest = repo.cooldown_for(user_id)
    markup = None
    if rest is not None:
        price = int(settings.get("cooldown_skip_price") or 0)
        body += "\n\n" + texts.profile_rest(
            int(rest["place"]), datetime.fromisoformat(rest["until"])
        )
        markup = keyboards.buy_cooldown(price) if price else None

    await message.answer(body, reply_markup=markup)


@router.message(Command("top"))
async def leaderboard(message: Message, repo: Repo) -> None:
    await message.answer(texts.leaderboard(repo.leaderboard()))


@router.message(Command("vote"))
async def my_match(
    message: Message, repo: Repo, config: Config, settings: Settings
) -> None:
    """Открыть экран голосования своего текущего матча."""
    match = repo.active_match_for(message.from_user.id)
    if match is None:
        battle = repo.current_battle()
        match = repo.latest_open_match(int(battle["id"])) if battle else None
    if match is None:
        await message.answer(texts.NO_ACTIVE_BATTLE)
        return
    await show_voting(
        message, int(match["id"]), repo, config,
        scope=settings.get("free_vote_scope"),
    )
