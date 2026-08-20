"""Движок батла: заявки, публикация пар, закрытие раундов, финал."""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from config import Config, MSK
from core import bracket
from core.models import BattleStatus, ParticipantStatus, Player, Slot
from core.scheduler import deadline_for_round
from services import links, texts
from services.channel import ChannelPublisher
from storage.repo import Repo

log = logging.getLogger(__name__)


class BattleEngine:
    def __init__(self, bot: Bot, repo: Repo, config: Config) -> None:
        self.bot = bot
        self.repo = repo
        self.config = config
        self.publisher = ChannelPublisher(bot, repo, config)
        self.rng = random.Random()
        self._lock = asyncio.Lock()  # заявки приходят пачками — пары режем по одной

    # --------------------------------------------------------------- служебное

    def now(self) -> datetime:
        return datetime.now(MSK)

    def current_deadline(self) -> datetime | None:
        battle = self.repo.current_battle()
        if battle is None or not battle["deadline"]:
            return None
        return datetime.fromisoformat(battle["deadline"])

    def ensure_battle(self) -> int:
        """Вернуть текущий батл, при необходимости открыв новый приём заявок."""
        battle = self.repo.current_battle()
        if battle is not None:
            return int(battle["id"])
        deadline = deadline_for_round(1, self.now(), self.config.round_times)
        battle_id = self.repo.create_battle(deadline)
        log.info("Открыт батл #%s, приём заявок до %s", battle_id, deadline)
        return battle_id

    # ------------------------------------------------------------------ заявки

    async def join(self, user_id: int, nickname: str) -> tuple[bool, str]:
        """Принять заявку и, если набралась пара, сразу опубликовать пост.

        Возвращает (принято, текст ответа).
        """
        pending: tuple[int, list[Player]] | None = None

        async with self._lock:
            if self.repo.is_banned(user_id):
                return False, "Вы не можете участвовать в батлах."

            battle = self.repo.current_battle()
            if battle is not None and battle["status"] == BattleStatus.RUNNING.value:
                return False, "Батл уже идёт — заявки на следующий откроются после финала."

            battle_id = self.ensure_battle()
            if self.repo.participant_count(battle_id) >= self.config.max_participants:
                return False, "Мест в этом батле больше нет, ждите следующий."

            if not self.repo.add_participant(battle_id, user_id, nickname):
                return False, texts.ALREADY_IN_BATTLE

            waiting = self.repo.unassigned_players(battle_id)
            if len(waiting) >= 2:
                # матч создаём под локом, иначе две одновременные заявки
                # успеют увидеть одну и ту же очередь и создать дубль пары
                pending = self._create_pair_match(battle_id, waiting[:2])

        # публикацию выносим из-под лока — сеть может тормозить
        if pending is not None:
            match_id, pair = pending
            message_id = await self.publisher.publish_match(match_id)
            await self._notify_pair(match_id, pair, message_id)
            return True, texts.APPLICATION_ACCEPTED
        return True, texts.IN_QUEUE

    def _create_pair_match(self, battle_id: int, pair: list[Player]) -> tuple[int, list[Player]]:
        """Завести матч первого раунда для двух заявок."""
        battle = self.repo.current_battle()
        deadline = datetime.fromisoformat(battle["deadline"])
        number = len(self.repo.open_matches(battle_id, 1)) + 1
        match_id = self.repo.create_match(
            battle_id=battle_id,
            round_no=1,
            number=number,
            players=pair,
            advance=1,
            is_final=False,
            deadline=deadline,
        )
        return match_id, pair

    async def _notify_pair(self, match_id: int, pair: list[Player], message_id: int | None) -> None:
        link = links.vote_link(self.config.bot_username, match_id)
        for player in pair:
            rival = next(p.nickname for p in pair if p.user_id != player.user_id)
            text = (
                "⚔️ <b>Ваш пост опубликован!</b>\n\n"
                f"Соперник: {texts.nick(rival)}\n\n"
                "Ссылка для ваших голосующих:\n"
                f"<code>{link}</code>"
            )
            await self._dm(player.user_id, text)

    # ------------------------------------------------------------ ход раундов

    async def close_round(self) -> None:
        """Подвести итоги текущего раунда и запустить следующий.

        Лок держим на весь подсчёт: пока идут итоги, новые заявки не должны
        подмешиваться в закрываемый раунд.
        """
        async with self._lock:
            await self._close_round_locked()

    async def _close_round_locked(self) -> None:
        battle = self.repo.current_battle()
        if battle is None:
            return
        battle_id = int(battle["id"])
        round_no = int(battle["round_no"])
        matches = self.repo.open_matches(battle_id, round_no)

        if not matches:
            # ни одной пары не набралось — переносим приём заявок
            if round_no == 1:
                await self._reschedule_registration(battle_id)
            return

        advanced: list[int] = []
        eliminated: list[int] = []
        final_ranking: list[Slot] = []

        for row in matches:
            match_id = int(row["id"])
            slots = self.repo.match_slots(match_id)
            result = bracket.resolve_match(
                match_id=match_id,
                slots=slots,
                advance=0 if row["is_final"] else int(row["advance"]),
                rng=self.rng,
            )
            self.repo.close_match(match_id, result.ranking)
            await self.publisher.publish_results(match_id, result.ranking, result.tie_broken)

            if row["is_final"]:
                final_ranking = result.ranking
            else:
                advanced.extend(result.winners)
                eliminated.extend(result.losers)

        if final_ranking:
            await self._finish_battle(battle_id, final_ranking)
            return

        # тот, кто в первом раунде остался без пары, проходит без боя
        byes = [p.user_id for p in self.repo.unassigned_players(battle_id)] if round_no == 1 else []
        self.repo.eliminate(battle_id, eliminated)
        self.repo.bump_wins(advanced)

        await self._notify_many(eliminated, texts.YOU_LOST)
        await self._notify_many(byes, "🎟 Соперник не нашёлся — вы проходите в следующий раунд без боя.")

        await self._start_round(battle_id, round_no + 1)

    async def _start_round(self, battle_id: int, round_no: int) -> None:
        alive = self.repo.alive_players(battle_id)

        if len(alive) < 2:
            if alive:
                await self._finish_battle(
                    battle_id, [Slot(alive[0].user_id, alive[0].nickname, 0, 1)]
                )
            else:
                self.repo.set_battle_status(battle_id, BattleStatus.CANCELLED)
            return

        deadline = deadline_for_round(round_no, self.now(), self.config.round_times)
        self.repo.set_round(battle_id, round_no, deadline)
        self.repo.set_battle_status(battle_id, BattleStatus.RUNNING)

        plan = bracket.plan_round(alive, round_no, self.rng)
        advance = bracket.base_advance(plan)

        await self.publisher.announce(
            f"<b>{texts.round_title(round_no, plan.is_final)}</b>\n\n"
            f"В игре: {len(alive)} ников · матчей: {plan.match_count}\n"
            f"{texts.deadline_line(deadline)}"
        )

        for number, group in enumerate(plan.groups, start=1):
            match_id = self.repo.create_match(
                battle_id=battle_id,
                round_no=round_no,
                number=number,
                players=group,
                advance=advance,
                is_final=plan.is_final,
                deadline=deadline,
            )
            await self.publisher.publish_match(match_id)
            await self._notify_many(
                [p.user_id for p in group],
                f"{texts.YOU_ADVANCED}\n\nВаша ссылка: "
                f"<code>{links.vote_link(self.config.bot_username, match_id)}</code>",
            )

    async def _reschedule_registration(self, battle_id: int) -> None:
        deadline = deadline_for_round(1, self.now(), self.config.round_times)
        self.repo.set_round(battle_id, 1, deadline)
        log.info("Пар не набралось, приём заявок продлён до %s", deadline)

    async def _finish_battle(self, battle_id: int, ranking: list[Slot]) -> None:
        for slot in ranking:
            self.repo.set_place(battle_id, slot.user_id, slot.position or 1)
            self.repo.record_place(slot.user_id, slot.position or 1)

        self.repo.set_battle_status(battle_id, BattleStatus.FINISHED)
        await self.publisher.announce(texts.final_announcement(ranking, self.config.prizes))

        for slot in ranking:
            place = slot.position or 1
            if place <= len(self.config.prizes):
                prize = self.config.prizes[place - 1]
                await self._dm(
                    slot.user_id,
                    f"{texts.MEDAL.get(place, '')} <b>{place} место!</b>\n\nПриз: {prize}⭐",
                )
            else:
                await self._dm(slot.user_id, texts.YOU_LOST)
        log.info("Батл #%s завершён", battle_id)

    # ---------------------------------------------------------------- рассылка

    async def _notify_many(self, user_ids: list[int], text: str) -> None:
        for user_id in user_ids:
            await self._dm(user_id, text)

    async def _dm(self, user_id: int, text: str) -> None:
        try:
            await self.bot.send_message(user_id, text, disable_web_page_preview=True)
        except TelegramAPIError as error:
            log.info("Не доставлено пользователю %s: %s", user_id, error)
        await asyncio.sleep(self.config.dm_delay)  # мягкий рейт-лимит на рассылку
