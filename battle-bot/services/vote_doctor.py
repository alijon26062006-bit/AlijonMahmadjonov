"""Почему человек не может проголосовать.

Отказ приходит короткой всплывашкой, и по ней не видно, что именно
сработало: подписка, потраченный бесплатный голос, пустой баланс, закрытый
матч. Этот модуль проходит по всем условиям сразу и отвечает по-человечески.

Проверки идут в том же порядке, что и при настоящем голосовании, поэтому
ответ совпадает с тем, что человек увидит на кнопке.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from aiogram import Bot

from config import Config
from services import sponsors, subscription
from storage.repo import Repo
from storage.settings import Settings


@dataclass
class Report:
    lines: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    @property
    def can_vote(self) -> bool:
        return not self.blockers

    def ok(self, line: str) -> None:
        self.lines.append(f"✅ {line}")

    def stop(self, line: str) -> None:
        self.lines.append(f"⛔️ {line}")
        self.blockers.append(line)

    def note(self, line: str) -> None:
        self.lines.append(f"• {line}")


async def diagnose(
    bot: Bot, repo: Repo, config: Config, settings: Settings, user_id: int,
    match_id: int | None = None,
) -> Report:
    """Пройти по всем условиям голосования для этого человека."""
    report = Report()

    if repo.is_banned(user_id):
        report.stop("Аккаунт заблокирован — голоса не принимаются.")
        return report

    match = repo.get_match(match_id) if match_id else repo.active_match_for(user_id)
    if match is None:
        battle = repo.current_battle()
        match = repo.latest_open_match(int(battle["id"])) if battle else None
    if match is None:
        report.stop("Сейчас нет открытого голосования — голосовать негде.")
        return report

    match_id = int(match["id"])
    report.note(f"Проверяю по матчу <b>#{match_id}</b>.")

    if match["status"] != "voting":
        report.stop("Голосование по этому матчу уже закрыто.")
    else:
        report.ok("Матч открыт.")

    await _check_subscription(bot, config, settings, user_id, report)
    _check_votes(repo, settings, user_id, match_id, report)
    return report


async def _check_subscription(
    bot: Bot, config: Config, settings: Settings, user_id: int, report: Report
) -> None:
    for channel_id in sponsors.required(config, settings):
        inside = await subscription.check(bot, channel_id, user_id)
        if inside is None:
            report.stop(
                f"Telegram не ответил про канал <code>{channel_id}</code> — "
                "чаще всего бот там не администратор."
            )
        elif inside:
            report.ok(f"Подписан на <code>{channel_id}</code>.")
        else:
            report.stop(f"Нет подписки на <code>{channel_id}</code>.")


def _check_votes(
    repo: Repo, settings: Settings, user_id: int, match_id: int, report: Report
) -> None:
    scope = settings.get("free_vote_scope")
    balance = repo.vote_balance(user_id)
    spent_free = repo.free_vote_used(match_id, user_id, scope)

    if not spent_free:
        report.ok("Бесплатный голос ещё не потрачен — проголосовать может.")
        return

    from services import texts

    report.note(f"Бесплатный голос {texts.FREE_SCOPE_WORDS.get(scope, 'здесь')} уже потрачен.")

    limit = int(settings.get("paid_votes_per_match") or 0)
    used = repo.paid_votes_in_match(match_id, user_id)
    if limit:
        report.note(f"Купленных в эту пару: <b>{used}</b> из <b>{limit}</b>.")
        if used >= limit:
            report.stop("Достигнут лимит купленных голосов на одну пару.")
            return

    if balance > 0:
        report.ok(f"Купленных голосов на балансе: <b>{balance}</b> — их можно тратить.")
    else:
        report.stop("Купленных голосов нет — баланс пуст.")
