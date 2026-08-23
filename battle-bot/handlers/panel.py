"""Админ-панель: одно сообщение, которое перерисовывается на месте.

Доступ только у ADMIN_IDS. Любое значение, которое вводит человек, проходит
через services.validation — при ошибке панель объясняет, что не так, и остаётся
на месте, а не теряет контекст.
"""
from __future__ import annotations

import logging
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from config import Config
from core import background, bracket
from core.engine import BattleEngine
from services import (
    keyboards, main_post, panel_ui, prizes, sponsors, subscription, texts, ui,
    validation,
)
from services.validation import InputError
from storage.repo import Repo
from storage.settings import FIELDS, Settings

log = logging.getLogger(__name__)
router = Router(name="panel")


class Panel(StatesGroup):
    waiting_value = State()
    promo_text = State()
    promo_label = State()
    promo_url = State()


def _link_or_none(raw: str) -> str:
    """Ссылка для кнопки. Дефис или «нет» убирают кнопку совсем."""
    text = (raw or "").strip()
    if text in {"-", "—", "нет", "убрать"}:
        return ""
    return validation.as_url(text)


# какой проверкой встречать каждое поле и куда возвращаться после ввода
EDITORS: dict[str, dict] = {
    "prizes": {"check": prizes.check, "back": "prizes"},
    "vote_price": {
        "check": lambda raw: validation.as_int(raw, minimum=1, maximum=2500, example="5"),
        "back": "votes",
    },
    "stars_link": {"check": lambda raw: raw.strip(), "back": "votes"},
    "sponsor_channels": {
        "check": lambda raw: _channel_list(raw),
        "back": "settings",
    },
    "reminder_hours": {
        "check": lambda raw: _hours_list(raw),
        "back": "auto",
    },
    "promo_interval_hours": {
        "check": lambda raw: validation.as_int(raw, minimum=0, maximum=168, example="6"),
        "back": "auto",
    },
    "referral_reward": {
        "check": lambda raw: validation.as_int(raw, minimum=0, maximum=100, example="1"),
        "back": "referrals",
    },
    "round_times": {"check": validation.as_times, "back": "settings"},
    "rejoin_price": {
        "check": lambda raw: validation.as_int(raw, minimum=0, maximum=2500, example="50"),
        "back": "people:left",
    },
    "cooldown_days": {
        "check": lambda raw: validation.as_int(raw, minimum=0, maximum=90, example="3"),
        "back": "people:rest",
    },
    "cooldown_places": {
        "check": lambda raw: validation.as_int(raw, minimum=0, maximum=10, example="3"),
        "back": "people:rest",
    },
    "cooldown_skip_price": {
        "check": lambda raw: validation.as_int(raw, minimum=0, maximum=2500, example="50"),
        "back": "people:rest",
    },
    **{
        key: {"check": _link_or_none, "back": "links"}
        for _, key, _ in keyboards.HELP_LINKS
    },
    "late_join_until_round": {
        # 0 — подсадки нет; больше пяти раундов батл почти не живёт
        "check": lambda raw: validation.as_int(raw, minimum=0, maximum=10, example="2"),
        "back": "settings",
    },
    "min_participants": {
        "check": lambda raw: validation.as_int(raw, minimum=2, maximum=1000, example="4"),
        "back": "settings",
    },
    "max_participants": {
        "check": lambda raw: validation.as_int(raw, minimum=2, maximum=10_000, example="512"),
        "back": "settings",
    },
    "main_channel_id": {
        "check": lambda raw: validation.as_int(raw, example="-1001234567890"),
        "back": "channel",
    },
    "main_post_text": {"check": lambda raw: raw.strip(), "back": "channel"},
    "main_post_photo": {"check": lambda raw: raw.strip(), "back": "channel"},
}


def _hours_list(raw: str) -> str:
    """«3,1» — за сколько часов до итогов напоминать."""
    text = (raw or "").strip()
    if not text or text in {"-", "—"}:
        return ""
    hours = validation.as_int_list(
        text.replace(" ", ","), minimum=1, maximum=48, max_items=6, example="3,1"
    )
    return ",".join(str(value) for value in sorted(set(hours), reverse=True))


def _channel_list(raw: str) -> str:
    """Список ID каналов через запятую. Пусто — вернуться к главному каналу."""
    text = (raw or "").strip()
    if not text or text in {"-", "—"}:
        return ""
    ids = validation.as_int_list(text.replace(" ", ","), example="-1001234567890")
    return ",".join(str(value) for value in ids)


def is_admin(user_id: int, config: Config) -> bool:
    return user_id in config.admin_ids


@router.callback_query.outer_middleware()
async def leave_input_mode(handler, event: CallbackQuery, data: dict):
    """Нажали любую кнопку панели — значит ввод значения больше не ждём.

    Без этого «Отмена» и переходы по разделам оставляли включённым режим
    ожидания, и следующее сообщение человека уходило в проверку значения.
    """
    if (event.data or "").startswith("p:") and not event.data.startswith("p:edit:"):
        state: FSMContext | None = data.get("state")
        if state is not None:
            await state.clear()
    return await handler(event, data)


# ------------------------------------------------------------------ сводка

def collect(repo: Repo, engine: BattleEngine) -> dict:
    settings_min = engine.config.min_participants
    battle = repo.current_battle()
    sold_votes, sold_stars = repo.sold_votes()
    data = {
        "users": repo.user_count(),
        "new_users": repo.new_users(),
        "banned": repo.banned_count(),
        "resting": repo.cooldown_count(),
        "leavers": repo.leaver_count(),
        "blocked": repo.blocked_count(),
        "votes": repo.total_votes_cast(),
        "sold_votes": sold_votes,
        "sold_stars": sold_stars,
        "referrals": repo.referral_totals()[1],
        "battle": battle,
        "queue": repo.queue_size(),
        "min_participants": settings_min,
        "participants": 0,
        "alive": 0,
        "open_matches": 0,
        "is_final": False,
        "deadline": "—",
        "projection": "—",
        "waiting_rival": 0,
        "late_join_until": engine.late_join_limit(),
    }
    if battle:
        battle_id = int(battle["id"])
        alive = repo.alive_players(battle_id)
        matches = repo.open_matches(battle_id, int(battle["round_no"]))
        data.update(
            participants=repo.participant_count(battle_id),
            alive=len(alive),
            open_matches=len(matches),
            waiting_rival=len(repo.unassigned_players(battle_id)),
            is_final=bool(matches and matches[0]["is_final"]),
            deadline=datetime.fromisoformat(battle["deadline"]).strftime("%H:%M %d.%m"),
            projection=" → ".join(map(str, bracket.project_rounds(len(alive)))) if alive else "—",
        )
    return data


async def render(target: Message | CallbackQuery, screen: tuple) -> None:
    """Перерисовать панель на месте, не плодя сообщения."""
    text, markup = screen
    if not isinstance(target, CallbackQuery):
        await ui.send(target, text, reply_markup=markup)
        return

    if ui.photo_of(target.message):  # экран после загрузки фото — заменяем сообщением
        await ui.send(target, text, reply_markup=markup)
        return

    await ui.edit_or_send(target, text, reply_markup=markup)


async def edit_in_place(message, text: str, markup) -> None:
    """Перерисовать сообщение; не вышло — прислать новое.

    Панель живёт одним сообщением, и оно может устареть или быть удалено.
    Раньше в этом случае падал AttributeError, и вся панель переставала
    отвечать на кнопки.
    """
    await ui.edit_or_send(message, text, reply_markup=markup)


# ------------------------------------------------------------------- вход

@router.message(Command("panel", "admin"))
async def open_panel(
    message: Message, repo: Repo, config: Config, engine: BattleEngine, state: FSMContext
) -> None:
    if not is_admin(message.from_user.id, config):
        return
    await state.clear()
    await render(message, panel_ui.home(collect(repo, engine)))


@router.callback_query(F.data == "p:home")
async def go_home(
    callback: CallbackQuery, repo: Repo, config: Config, engine: BattleEngine, state: FSMContext
) -> None:
    if not is_admin(callback.from_user.id, config):
        await callback.answer("Панель доступна только администраторам.", show_alert=True)
        return
    await state.clear()
    await render(callback, panel_ui.home(collect(repo, engine)))
    await callback.answer()


# ----------------------------------------------------------------- разделы

@router.callback_query(F.data == "p:battle")
async def show_battle(
    callback: CallbackQuery, repo: Repo, config: Config, engine: BattleEngine
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await render(callback, panel_ui.battle(collect(repo, engine)))
    await callback.answer()


@router.callback_query(F.data == "p:prizes")
async def show_prizes(callback: CallbackQuery, config: Config, settings: Settings) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await render(callback, panel_ui.prizes(settings.get("prizes")))
    await callback.answer()


@router.callback_query(F.data == "p:votes")
async def show_votes(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await render(callback, _votes_screen(repo, settings))
    await callback.answer()


@router.callback_query(F.data == "p:referrals")
async def show_referrals(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await render(
        callback,
        panel_ui.referrals(
            settings.get("referral_reward"),
            settings.get("referral_enabled"),
            repo.referral_report(),
            repo.top_inviters(10),
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "p:referrals:toggle")
async def toggle_referrals(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    settings.set("referral_enabled", not settings.get("referral_enabled"))
    await render(
        callback,
        panel_ui.referrals(
            settings.get("referral_reward"),
            settings.get("referral_enabled"),
            repo.referral_report(),
            repo.top_inviters(10),
        ),
    )
    await callback.answer("Сохранено")


def _auto_screen(repo: Repo, settings: Settings):
    return panel_ui.autopilot(settings.all(), repo.promos())


@router.callback_query(F.data == "p:fraud")
async def show_fraud(callback: CallbackQuery, repo: Repo, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await render(callback, panel_ui.fraud(_fraud_signals(repo)))
    await callback.answer("Пересчитано")


def _fraud_signals(repo: Repo) -> dict:
    return {
        "own_referrals": repo.self_referral_votes(),
        "bursts": repo.vote_bursts(),
        "loyal": repo.loyal_voters(),
        "fresh": repo.fresh_account_votes(),
    }


@router.callback_query(F.data == "p:auto")
async def show_autopilot(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await render(callback, _auto_screen(repo, settings))
    await callback.answer()


@router.callback_query(F.data == "p:auto:toggle")
async def toggle_autopilot(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    settings.set("autopilot_enabled", not settings.get("autopilot_enabled"))
    await render(callback, _auto_screen(repo, settings))
    await callback.answer("Сохранено")


@router.callback_query(F.data == "p:auto:promo:add")
async def add_promo(callback: CallbackQuery, config: Config, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await state.set_state(Panel.promo_text)
    await render(
        callback,
        panel_ui.ask(
            "Текст рекламного поста", "—",
            "бот будет публиковать его в оба канала по очереди", "auto",
        ),
    )
    await callback.answer()


@router.message(
    Panel.promo_text,
    F.text.startswith("/") | F.text.in_(keyboards.menu_labels()),
)
@router.message(
    Panel.promo_label,
    F.text.startswith("/") | F.text.in_(keyboards.menu_labels()),
)
@router.message(
    Panel.promo_url,
    F.text.startswith("/") | F.text.in_(keyboards.menu_labels()),
)
async def leave_promo(message: Message, state: FSMContext) -> None:
    await state.clear()
    raise SkipHandler()


@router.message(Panel.promo_text)
async def promo_text(message: Message, config: Config, state: FSMContext) -> None:
    if not is_admin(message.from_user.id, config):
        return
    try:
        text = validation.as_text(message.html_text or message.text or "", limit=3000)
    except InputError as error:
        await message.answer(f"⚠️ {error}")
        return

    await state.update_data(promo_text=text)
    await state.set_state(Panel.promo_label)
    await message.answer(
        "✏️ <b>Название кнопки</b> под постом.\n<i>Например: Участвовать</i>",
        reply_markup=panel_ui.keyboard(
            [panel_ui.button("Без кнопки →", "auto:promo:nobutton")],
            [panel_ui.button("Отмена", "auto")],
        ),
    )


@router.callback_query(F.data == "p:auto:promo:nobutton")
async def promo_without_button(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings, state: FSMContext
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    data = await state.get_data()
    repo.add_promo(data.get("promo_text", ""), None, None)
    await state.clear()
    await render(callback, _auto_screen(repo, settings))
    await callback.answer("Пост добавлен")


@router.message(Panel.promo_label)
async def promo_label(message: Message, config: Config, state: FSMContext) -> None:
    if not is_admin(message.from_user.id, config):
        return
    try:
        label = validation.as_text(message.text or "", limit=64)
    except InputError as error:
        await message.answer(f"⚠️ {error}")
        return

    await state.update_data(promo_label=label)
    await state.set_state(Panel.promo_url)
    await message.answer(
        f"🔗 <b>Ссылка</b> для кнопки «{label}».\n"
        "<i>Например: https://t.me/realed или @realed</i>",
        reply_markup=panel_ui.keyboard([panel_ui.button("Отмена", "auto")]),
    )


@router.message(Panel.promo_url)
async def promo_url(
    message: Message, repo: Repo, config: Config, settings: Settings, state: FSMContext
) -> None:
    if not is_admin(message.from_user.id, config):
        return
    try:
        url = validation.as_url(message.text or "")
    except InputError as error:
        await message.answer(f"⚠️ {error}")
        return

    data = await state.get_data()
    repo.add_promo(data.get("promo_text", ""), data.get("promo_label"), url)
    await state.clear()
    await message.answer("✅ Рекламный пост добавлен.")
    await render(message, _auto_screen(repo, settings))


@router.callback_query(F.data == "p:auto:promos")
async def show_promos(
    callback: CallbackQuery, repo: Repo, config: Config
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await render(callback, panel_ui.promo_list(repo.promos()))
    await callback.answer()


@router.callback_query(F.data.startswith("p:auto:promo:toggle:"))
async def switch_promo(
    callback: CallbackQuery, repo: Repo, config: Config
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    repo.toggle_promo(int(callback.data.split(":")[-1]))
    await render(callback, panel_ui.promo_list(repo.promos()))
    await callback.answer("Сохранено")


@router.callback_query(F.data.startswith("p:auto:promo:del:"))
async def drop_promo(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    repo.delete_promo(int(callback.data.split(":")[-1]))
    remaining = repo.promos()
    await render(
        callback,
        panel_ui.promo_list(remaining) if remaining else _auto_screen(repo, settings),
    )
    await callback.answer("Удалено")


@router.callback_query(F.data == "p:channel")
async def show_channel(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await render(callback, panel_ui.channel(main_post.state(repo, config, settings)))
    await callback.answer()


@router.callback_query(F.data == "p:people")
async def show_people(
    callback: CallbackQuery, repo: Repo, config: Config, engine: BattleEngine
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await render(callback, panel_ui.people(collect(repo, engine)))
    await callback.answer()


@router.callback_query(F.data == "p:settings")
async def show_settings(callback: CallbackQuery, config: Config, settings: Settings) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await render(
        callback,
        panel_ui.settings_screen(settings.all(), sponsors.required(config, settings)),
    )
    await callback.answer()


def _person_screen(repo: Repo, user_id: int):
    """Карточка участника — вместе с действующей паузой, если она есть."""
    return panel_ui.person(
        repo.get_user(user_id),
        repo.stats_for(user_id),
        repo.vote_balance(user_id),
        repo.referral_stats(user_id),
        repo.cooldown_for(user_id),
        repo.leaver(user_id),
    )


@router.callback_query(F.data == "p:people:left")
async def show_leavers(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await render(callback, _leavers_screen(repo, settings))
    await callback.answer()


def _leavers_screen(repo: Repo, settings: Settings):
    return panel_ui.leavers(
        repo.leavers(limit=15),
        settings.get("leave_penalty_enabled"),
        settings.get("rejoin_price"),
        repo.leaver_count(),
    )


@router.callback_query(F.data.startswith("p:person:left:"))
async def forgive_leaver(
    callback: CallbackQuery, bot: Bot, repo: Repo, config: Config
) -> None:
    """Вернуть доступ вручную — например, если человек вышел по ошибке."""
    if not is_admin(callback.from_user.id, config):
        return
    user_id = int(callback.data.split(":")[-1])
    forgiven = repo.forgive_leaver(user_id)
    if forgiven:
        try:
            await bot.send_message(user_id, texts.leaver_forgiven())
        except TelegramAPIError as error:
            log.info("Не смог сказать %s о возврате доступа: %s", user_id, error)
    await render(callback, _person_screen(repo, user_id))
    await callback.answer("Доступ возвращён" if forgiven else "Отметки и не было")


@router.callback_query(F.data == "p:people:rest")
async def show_cooldowns(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await render(callback, _cooldowns_screen(repo, settings))
    await callback.answer()


def _cooldowns_screen(repo: Repo, settings: Settings):
    return panel_ui.cooldowns(
        repo.active_cooldowns(limit=15),
        settings.get("cooldown_days"),
        settings.get("cooldown_places"),
        settings.get("cooldown_skip_price"),
    )


@router.callback_query(F.data.startswith("p:person:rest:"))
async def lift_cooldown(
    callback: CallbackQuery, bot: Bot, repo: Repo, config: Config
) -> None:
    """Снять паузу человеку вручную — например, если это была ошибка."""
    if not is_admin(callback.from_user.id, config):
        return
    user_id = int(callback.data.split(":")[-1])
    lifted = repo.clear_cooldown(user_id)
    if lifted:
        try:
            await bot.send_message(user_id, texts.cooldown_lifted(paid=False))
        except TelegramAPIError as error:
            log.info("Не смог сказать %s о снятии паузы: %s", user_id, error)
    await render(callback, _person_screen(repo, user_id))
    await callback.answer("Пауза снята" if lifted else "Паузы и не было")


@router.callback_query(F.data == "p:people:top")
async def show_top(callback: CallbackQuery, repo: Repo, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    text = texts.leaderboard(repo.leaderboard(limit=15))
    await render(
        callback,
        (text, panel_ui.keyboard(panel_ui.back_row("people"))),
    )
    await callback.answer()


# --------------------------------------------------------- переключатели

def _votes_screen(repo: Repo, settings: Settings):
    return panel_ui.votes(
        settings.vote_price,
        settings.get("paid_votes_enabled"),
        repo.sold_votes(),
        settings.get("stars_link"),
        settings.get("free_vote_scope"),
    )


@router.callback_query(F.data == "p:votes:scope")
async def cycle_free_scope(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings
) -> None:
    """Переключить, насколько широко действует бесплатный голос."""
    if not is_admin(callback.from_user.id, config):
        return
    current = settings.get("free_vote_scope")
    settings.set("free_vote_scope", panel_ui.SCOPE_NEXT.get(current, "battle"))
    await render(callback, _votes_screen(repo, settings))
    await callback.answer("Сохранено")


@router.callback_query(F.data == "p:votes:toggle")
async def toggle_votes(callback: CallbackQuery, repo: Repo, config: Config,
                       settings: Settings) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    settings.set("paid_votes_enabled", not settings.get("paid_votes_enabled"))
    await render(
        callback,
        _votes_screen(repo, settings),
    )
    await callback.answer("Сохранено")


@router.callback_query(F.data == "p:links")
async def show_links(callback: CallbackQuery, config: Config, settings: Settings) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await render(callback, panel_ui.links(settings.all(), config.channel_url))
    await callback.answer()


@router.callback_query(F.data == "p:health")
async def show_health(callback: CallbackQuery, repo: Repo, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await render(callback, _health_screen(repo))
    await callback.answer()


@router.callback_query(F.data == "p:health:clear")
async def clear_health(callback: CallbackQuery, repo: Repo, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    removed = repo.clear_errors()
    await render(callback, _health_screen(repo))
    await callback.answer(f"Удалено записей: {removed}")


def _health_screen(repo: Repo):
    return panel_ui.health(
        repo.error_summary(), repo.recent_errors(limit=8), background.report()
    )


@router.callback_query(F.data == "p:mych")
async def show_member_channels(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await render(callback, _member_channels_screen(repo, settings))
    await callback.answer()


@router.callback_query(F.data == "p:mych:toggle")
async def toggle_member_channels(
    callback: CallbackQuery, repo: Repo, config: Config, settings: Settings
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    settings.set("member_channels_enabled", not settings.get("member_channels_enabled"))
    await render(callback, _member_channels_screen(repo, settings))
    await callback.answer("Сохранено")


def _member_channels_screen(repo: Repo, settings: Settings):
    total, live, posts = repo.member_channel_stats()
    return panel_ui.member_channels(
        settings.get("member_channels_enabled"), total, live, posts,
        repo.member_channels(limit=15),
    )


@router.callback_query(F.data == "p:settings:check")
async def check_subscription(
    callback: CallbackQuery, config: Config, settings: Settings
) -> None:
    """Проверить, что бот действительно видит подписчиков каждого канала."""
    if not is_admin(callback.from_user.id, config):
        return
    rows = [
        (channel_id, await subscription.diagnose(callback.bot, channel_id, callback.from_user.id))
        for channel_id in sponsors.required(config, settings)
    ]
    await render(callback, panel_ui.subscription_check(rows))
    await callback.answer()


@router.callback_query(F.data == "p:settings:seeding")
async def toggle_seeding(
    callback: CallbackQuery, config: Config, settings: Settings
) -> None:
    """Переключить, как подбираются соперники со второго раунда."""
    if not is_admin(callback.from_user.id, config):
        return
    current = settings.get("seeding")
    settings.set("seeding", panel_ui.SEEDING_NEXT.get(current, "snake"))
    await render(
        callback,
        panel_ui.settings_screen(settings.all(), sponsors.required(config, settings)),
    )
    await callback.answer("Сохранено")


@router.callback_query(F.data.startswith("p:settings:toggle:"))
async def toggle_setting(callback: CallbackQuery, config: Config, settings: Settings) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    key = callback.data.split(":")[-1]
    if key not in FIELDS:
        await callback.answer("Нет такой настройки.", show_alert=True)
        return
    settings.set(key, not settings.get(key))
    await render(
        callback,
        panel_ui.settings_screen(settings.all(), sponsors.required(config, settings)),
    )
    await callback.answer("Сохранено")


# ------------------------------------------------------------ ввод значений

@router.callback_query(F.data.startswith("p:edit:"))
async def ask_value(
    callback: CallbackQuery, config: Config, settings: Settings, state: FSMContext
) -> None:
    if not is_admin(callback.from_user.id, config):
        return

    parts = callback.data.split(":")
    key = parts[2]
    extra = parts[3] if len(parts) > 3 else None

    if key == "find_user":
        await state.set_state(Panel.waiting_value)
        await state.update_data(key="find_user", back="people")
        await render(callback, panel_ui.ask("Поиск участника", "—", "ник или ID", "people"))
        await callback.answer()
        return

    if key == "grant":
        await state.set_state(Panel.waiting_value)
        await state.update_data(key="grant", back="people", target=int(extra))
        await render(callback, panel_ui.ask("Сколько голосов начислить", "0", "число", "people"))
        await callback.answer()
        return

    editor = EDITORS.get(key)
    if editor is None:
        await callback.answer("Это поле нельзя менять здесь.", show_alert=True)
        return

    field = FIELDS.get(key)
    current = settings.get(key) if field else ""
    shown = field.dump(current) if field else str(current)
    if key == "main_post_photo":
        shown = "загружено" if shown else "нет"

    await state.set_state(Panel.waiting_value)
    await state.update_data(key=key, back=editor["back"])
    await render(
        callback,
        panel_ui.ask(
            field.title if field else key,
            shown or "—",
            "пришлите фото" if key == "main_post_photo" else (field.hint if field else ""),
            editor["back"],
        ),
    )
    await callback.answer()


@router.message(
    Panel.waiting_value,
    F.text.startswith("/") | F.text.in_(keyboards.menu_labels()),
)
async def command_escapes_input(message: Message, state: FSMContext) -> None:
    """Из режима ввода всегда можно выйти командой или кнопкой меню.

    Иначе /start и «Принять участие» попадали в проверку значения, человек
    получал «это не похоже на ник» и оставался заперт в экране ввода.
    """
    await state.clear()
    raise SkipHandler()  # пусть обработает тот, кому это адресовано


@router.message(Panel.waiting_value)
async def receive_value(
    message: Message,
    repo: Repo,
    config: Config,
    engine: BattleEngine,
    settings: Settings,
    state: FSMContext,
) -> None:
    if not is_admin(message.from_user.id, config):
        return

    data = await state.get_data()
    key = data.get("key")

    try:
        await _apply(message, key, data, repo, config, engine, settings, state)
    except InputError as error:
        # остаёмся на том же экране: человек просто пробует ещё раз
        await message.answer(f"⚠️ {error}")


async def _apply(
    message: Message,
    key: str,
    data: dict,
    repo: Repo,
    config: Config,
    engine: BattleEngine,
    settings: Settings,
    state: FSMContext,
) -> None:
    if key == "find_user":
        needle = validation.as_username(message.text or "") if not (
            message.text or ""
        ).strip().lstrip("@").isdigit() else (message.text or "").strip()
        rows = repo.find_users(needle)
        if not rows:
            raise InputError(f"Никого не нашёл по «{needle}». Попробуйте другой ник или ID.")
        row = rows[0]
        await state.clear()
        await render(
            message,
            _person_screen(repo, int(row["user_id"])),
        )
        return

    if key == "grant":
        amount = validation.as_int(message.text or "", minimum=1, maximum=10_000, example="5")
        target = int(data["target"])
        repo.add_votes(target, amount)
        await state.clear()
        await message.answer(f"✅ Начислено <b>{amount}</b> голосов.")
        row = repo.get_user(target)
        await render(
            message,
            _person_screen(repo, target),
        )
        return

    if key == "main_channel_id":
        # ID искать не надо: достаточно переслать в бота любой пост из канала
        channel_id = _channel_from_forward(message)
        if channel_id is None:
            channel_id = validation.as_int(message.text or "", example="-1001234567890")
        settings.set("main_channel_id", channel_id)
        settings.set("main_post_message_id", 0)  # новый канал — новый пост
        await state.clear()
        await message.answer(f"✅ Главный канал: <code>{channel_id}</code>")
        await render(message, panel_ui.channel(main_post.state(repo, config, settings)))
        return

    if key == "main_post_photo":
        if not message.photo:
            raise InputError("Нужно прислать фото картинкой, а не текстом или файлом.")
        settings.set("main_post_photo", message.photo[-1].file_id)
        settings.set("main_post_message_id", 0)  # пост придётся опубликовать заново
        await state.clear()
        await message.answer("✅ Фото сохранено.")
        await render(message, panel_ui.channel(main_post.state(repo, config, settings)))
        return

    editor = EDITORS[key]
    value = editor["check"](message.text or "")
    settings.set(key, value)
    await state.clear()

    field = FIELDS[key]
    await message.answer(f"✅ <b>{field.title}</b> — сохранено: <b>{field.dump(value)}</b>")
    await _back_to(message, editor["back"], repo, config, engine, settings)


def _channel_from_forward(message: Message) -> int | None:
    """Достать ID канала из пересланного сообщения, если это оно."""
    origin = getattr(message, "forward_origin", None)
    chat = getattr(origin, "chat", None)
    return chat.id if chat is not None else None


async def _back_to(
    message: Message, section: str, repo: Repo, config: Config,
    engine: BattleEngine, settings: Settings
) -> None:
    if section == "prizes":
        await render(message, panel_ui.prizes(settings.get("prizes")))
    elif section == "votes":
        await render(
            message,
            _votes_screen(repo, settings),
        )
    elif section == "auto":
        await render(message, _auto_screen(repo, settings))
    elif section == "referrals":
        await render(
            message,
            panel_ui.referrals(
                settings.get("referral_reward"),
                settings.get("referral_enabled"),
                repo.referral_report(),
                repo.top_inviters(10),
            ),
        )
    elif section == "channel":
        await render(message, panel_ui.channel(main_post.state(repo, config, settings)))
    elif section == "people:left":
        await render(message, _leavers_screen(repo, settings))
    elif section == "people:rest":
        await render(message, _cooldowns_screen(repo, settings))
    elif section == "links":
        await render(message, panel_ui.links(settings.all(), config.channel_url))
    elif section == "settings":
        await render(
            message,
            panel_ui.settings_screen(settings.all(), sponsors.required(config, settings)),
        )
    else:
        await render(message, panel_ui.home(collect(repo, engine)))


# ------------------------------------------------------------ действия: батл

@router.callback_query(F.data == "p:battle:create")
async def create_battle(
    callback: CallbackQuery, repo: Repo, config: Config, engine: BattleEngine
) -> None:
    if not is_admin(callback.from_user.id, config):
        return

    await callback.answer("Собираю батл…")
    started, note = await engine.create_from_queue()
    await render(callback, panel_ui.battle(collect(repo, engine)))
    await callback.message.answer(("✅ " if started else "⚠️ ") + note)


@router.callback_query(F.data == "p:battle:clear:ask")
async def ask_clear_queue(callback: CallbackQuery, repo: Repo, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await render(
        callback,
        panel_ui.confirm(
            f"Очистить очередь из <b>{repo.queue_size()}</b> человек?\n\n"
            "<i>Они смогут записаться заново.</i>",
            "battle:clear:do",
            "battle",
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "p:battle:clear:do")
async def clear_queue(
    callback: CallbackQuery, repo: Repo, config: Config, engine: BattleEngine
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    removed = repo.clear_queue()
    await render(callback, panel_ui.battle(collect(repo, engine)))
    await callback.answer(f"Очередь очищена: {removed}")


@router.callback_query(F.data == "p:battle:close")
async def close_round(
    callback: CallbackQuery, repo: Repo, config: Config, engine: BattleEngine
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await callback.answer("Подвожу итоги…")
    await engine.close_round(force=True)  # админ подводит итоги досрочно осознанно
    await render(callback, panel_ui.battle(collect(repo, engine)))


@router.callback_query(F.data == "p:battle:postpone")
async def postpone(
    callback: CallbackQuery, repo: Repo, config: Config, engine: BattleEngine
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    battle = repo.current_battle()
    if battle is None:
        await callback.answer("Батл не идёт.", show_alert=True)
        return

    from core.scheduler import next_deadline

    deadline = next_deadline(engine.now(), config.round_times)
    repo.extend_deadlines(int(battle["id"]), deadline)
    await render(callback, panel_ui.battle(collect(repo, engine)))
    await callback.answer(f"Дедлайн перенесён на {deadline.strftime('%H:%M')}")


@router.callback_query(F.data == "p:battle:cancel:ask")
async def ask_cancel(callback: CallbackQuery, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await render(
        callback,
        panel_ui.confirm(
            "Батл будет отменён: участники выбывают, призы никому не достаются. "
            "Голоса и статистика сохранятся.",
            "battle:cancel:do",
            "battle",
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "p:battle:cancel:do")
async def do_cancel(
    callback: CallbackQuery, repo: Repo, config: Config, engine: BattleEngine
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    battle = repo.current_battle()
    if battle is None:
        await callback.answer("Уже нечего отменять.", show_alert=True)
    else:
        await callback.answer("Отменяю…")
        closed = await engine.cancel(int(battle["id"]))
        await callback.message.answer(
            f"🛑 Батл #{battle['id']} отменён. Закрыто матчей: <b>{closed}</b>.\n"
            "Набор в новый батл открыт."
        )
    await render(callback, panel_ui.battle(collect(repo, engine)))


# ---------------------------------------------------------- действия: канал

@router.callback_query(F.data == "p:channel:publish")
async def publish_main(
    callback: CallbackQuery, bot: Bot, repo: Repo, config: Config, settings: Settings
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    try:
        await main_post.publish(bot, repo, config, settings)
    except main_post.MainPostError as error:
        await callback.answer(str(error)[:190], show_alert=True)
        return
    await render(callback, panel_ui.channel(main_post.state(repo, config, settings)))
    await callback.answer("Главный пост обновлён")


@router.callback_query(F.data == "p:channel:pin")
async def pin_main(
    callback: CallbackQuery, bot: Bot, repo: Repo, config: Config, settings: Settings
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    try:
        await main_post.pin(bot, settings)
    except main_post.MainPostError as error:
        await callback.answer(str(error)[:190], show_alert=True)
        return
    await callback.answer("Закреплено")


@router.callback_query(F.data == "p:channel:wipe:ask")
async def ask_wipe(callback: CallbackQuery, repo: Repo, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    count = len(repo.posts(chat_id=config.channel_id))
    await render(
        callback,
        panel_ui.confirm(
            f"Удалить <b>{count}</b> постов батла из канала?\n\n"
            "<i>Telegram не даёт удалять сообщения старше 48 часов — такие останутся.</i>",
            "channel:wipe:do",
            "channel",
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "p:channel:wipe:do")
async def do_wipe(
    callback: CallbackQuery, bot: Bot, repo: Repo, config: Config, settings: Settings
) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    await callback.answer("Удаляю…")
    deleted, failed = await main_post.wipe_battle_posts(bot, repo, config)
    await render(callback, panel_ui.channel(main_post.state(repo, config, settings)))
    note = f"Удалено: {deleted}"
    if failed:
        note += f", не вышло: {failed}"
    await callback.message.answer(f"🗑 {note}")


# ---------------------------------------------------------- действия: люди

@router.callback_query(F.data.startswith("p:person:"))
async def person_action(callback: CallbackQuery, repo: Repo, config: Config) -> None:
    if not is_admin(callback.from_user.id, config):
        return
    _, _, action, raw_id = callback.data.split(":")
    user_id = int(raw_id)

    repo.set_banned(user_id, action == "ban")
    await render(
        callback,
        _person_screen(repo, user_id),
    )
    await callback.answer("Заблокирован" if action == "ban" else "Разблокирован")


# ---------------------------------------------------------- страховка

# Отдельный роутер: он подключается последним, после всех остальных. Иначе
# страховка перехватывала бы кнопки соседних разделов — например «Рассылку»,
# которая живёт в своём мастере, — и они переставали бы работать.
fallback_router = Router(name="panel-fallback")


@fallback_router.callback_query(F.data.startswith("p:"))
async def unknown_button(
    callback: CallbackQuery, repo: Repo, config: Config, engine: BattleEngine,
    state: FSMContext
) -> None:
    """Кнопка панели, для которой не нашлось обработчика.

    Так бывает у старого сообщения панели, оставшегося от прошлой версии бота.
    Молчащая кнопка выглядит как поломка, поэтому отвечаем и открываем панель
    заново вместо тишины.
    """
    if not is_admin(callback.from_user.id, config):
        await callback.answer("Панель доступна только администраторам.", show_alert=True)
        return

    log.warning("Панель: неизвестная кнопка %s", callback.data)
    await state.clear()
    await callback.answer("Эта кнопка из старой версии — открываю панель заново.")
    await render(callback, panel_ui.home(collect(repo, engine)))
