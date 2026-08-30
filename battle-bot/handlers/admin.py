"""Админские команды. Доступны только ID из ADMIN_IDS."""
from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from config import Config
from core import bracket
from core.engine import BattleEngine
from core.models import BattleStatus
from services import vote_doctor
from storage.repo import Repo
from storage.settings import Settings

log = logging.getLogger(__name__)
router = Router(name="admin")


def _is_admin(message: Message, config: Config) -> bool:
    return message.from_user.id in config.admin_ids


@router.message(Command("cmds"))
async def admin_help(message: Message, config: Config) -> None:
    if not _is_admin(message, config):
        return
    await message.answer(
        "🛠 <b>Команды администратора</b>\n\n"
        "Всё то же самое удобнее делать в /panel.\n\n"
        "/state — что сейчас происходит\n"
        "/close — подвести итоги раунда прямо сейчас\n"
        "/cancel — отменить текущий батл\n"
        "/ban &lt;id&gt; — исключить аккаунт\n"
        "/unban &lt;id&gt;\n"
        "/votelog &lt;match_id&gt; — лог голосов матча\n"
        "/whyvote [id] — почему человек не может проголосовать\n"
        "/broadcast — мастер рассылки"
    )


@router.message(Command("whyvote"))
async def why_vote(
    message: Message, command: CommandObject, bot: Bot, repo: Repo, config: Config,
    settings: Settings,
) -> None:
    """Разобрать по шагам, почему голос не проходит.

    Без аргумента проверяет самого админа — так быстрее всего понять, что
    именно мешает: подписка, потраченный бесплатный голос или пустой баланс.
    """
    if not _is_admin(message, config):
        return

    raw = (command.args or "").strip().lstrip("@")
    user_id = int(raw) if raw.isdigit() else message.from_user.id
    report = await vote_doctor.diagnose(bot, repo, config, settings, user_id)
    verdict = (
        "✅ <b>Может голосовать</b>" if report.can_vote
        else "⛔️ <b>Проголосовать не сможет</b>"
    )
    await message.answer(
        f"🗳 <b>Проверка голоса</b> · <code>{user_id}</code>\n\n"
        + "\n".join(report.lines)
        + f"\n\n{verdict}"
    )


@router.message(Command("state"))
async def state(message: Message, repo: Repo, config: Config) -> None:
    if not _is_admin(message, config):
        return
    battle = repo.current_battle()
    if battle is None:
        await message.answer("Активного батла нет. Первая заявка откроет новый.")
        return

    battle_id = int(battle["id"])
    alive = repo.alive_players(battle_id)
    matches = repo.open_matches(battle_id, int(battle["round_no"]))
    await message.answer(
        f"Батл #{battle_id} · {battle['status']}\n"
        f"Раунд: {battle['round_no']}\n"
        f"Дедлайн: {battle['deadline']}\n"
        f"Заявок всего: {repo.participant_count(battle_id)}\n"
        f"В игре: {len(alive)}\n"
        f"Открытых матчей: {len(matches)}\n"
        f"Прогноз сетки: {bracket.project_rounds(len(alive)) if alive else '—'}"
    )


@router.message(Command("close"))
async def close_now(message: Message, config: Config, engine: BattleEngine) -> None:
    if not _is_admin(message, config):
        return
    await message.answer("Подвожу итоги…")
    await engine.close_round(force=True)  # команда админа — итоги досрочно
    await message.answer("Готово.")


@router.message(Command("cancel"))
async def cancel(message: Message, repo: Repo, config: Config) -> None:
    if not _is_admin(message, config):
        return
    battle = repo.current_battle()
    if battle is None:
        await message.answer("Нечего отменять.")
        return
    repo.set_battle_status(int(battle["id"]), BattleStatus.CANCELLED)
    await message.answer(f"Батл #{battle['id']} отменён.")


@router.message(Command("ban"))
async def ban(message: Message, command: CommandObject, repo: Repo, config: Config) -> None:
    if not _is_admin(message, config):
        return
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Формат: /ban 123456789")
        return
    repo.set_banned(int(command.args.strip()), True)
    await message.answer("Аккаунт исключён.")


@router.message(Command("unban"))
async def unban(message: Message, command: CommandObject, repo: Repo, config: Config) -> None:
    if not _is_admin(message, config):
        return
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Формат: /unban 123456789")
        return
    repo.set_banned(int(command.args.strip()), False)
    await message.answer("Аккаунт восстановлен.")


@router.message(Command("votelog"))
async def votelog(message: Message, command: CommandObject, repo: Repo, config: Config) -> None:
    """Разбор спорного матча: кто, за кого и когда голосовал."""
    if not _is_admin(message, config):
        return
    if not command.args or not command.args.strip().isdigit():
        await message.answer("Формат: /votelog 12")
        return

    rows = repo.vote_log(int(command.args.strip()))
    if not rows:
        await message.answer("Голосов нет.")
        return

    lines = [
        f"{row['created_at']} · {row['voter_id']} → {row['target_id']} ({row['source']})"
        for row in rows[-50:]
    ]
    await message.answer(f"Голосов: {len(rows)}\n\n<code>" + "\n".join(lines) + "</code>")
