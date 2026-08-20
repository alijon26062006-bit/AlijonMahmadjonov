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
from core.models import BattleStatus, Player, Slot
from core.scheduler import deadline_for_round
from services import keyboards, links, texts
from services.channel import ChannelPublisher
from storage.repo import Repo

log = logging.getLogger(__name__)


class BattleEngine:
    def __init__(
        self, bot: Bot, repo: Repo, config: Config, emoji_skip: set[int] | None = None
    ) -> None:
        self.bot = bot
        self.repo = repo
        self.config = config
        self.publisher = ChannelPublisher(bot, repo, config, emoji_skip)
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
        markup = keyboards.my_match(match_id, self.config, self._post_url(message_id))
        for player in pair:
            rival = next(p.nickname for p in pair if p.user_id != player.user_id)
            await self._dm(player.user_id, texts.pair_published(rival), markup)

    def _post_url(self, message_id: int | None) -> str | None:
        if not message_id:
            return None
        if self.config.channel_url.startswith("https://t.me/") and "/c/" not in self.config.channel_url:
            return links.public_post_link(self.config.channel_url, message_id)
        return links.post_link(self.config.channel_id, message_id)

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

        if round_no == 1:
            applied = self.repo.participant_count(battle_id)
            if applied < self.config.min_participants:
                # заявок слишком мало — играть батл с призами нет смысла,
                # продлеваем приём и переносим итоги на следующий слот
                await self._reschedule_registration(battle_id, applied)
                return

        if not matches:
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
                # каждому участнику матча — его личный итог с соперниками и счётом
                await self._send_match_results(result, int(row["round_no"]), is_final=False)

        if final_ranking:
            await self._finish_battle(battle_id, final_ranking)
            return

        # тот, кто в первом раунде остался без пары, проходит без боя
        byes = [p.user_id for p in self.repo.unassigned_players(battle_id)] if round_no == 1 else []
        self.repo.eliminate(battle_id, eliminated)
        self.repo.bump_wins(advanced)

        await self._notify_many(byes, texts.BYE_ROUND)

        await self._start_round(battle_id, round_no + 1)

    async def _send_match_results(self, result, round_no: int, is_final: bool) -> None:
        """Разослать участникам матча честный итог: вся таблица, а не «вы проиграли»."""
        winners = set(result.winners)
        for slot in result.ranking:
            await self._dm(
                slot.user_id,
                texts.match_result_dm(
                    ranking=result.ranking,
                    you_id=slot.user_id,
                    round_no=round_no,
                    is_final=is_final,
                    advanced=slot.user_id in winners,
                    tie_broken=result.tie_broken,
                ),
            )

    async def _start_round(self, battle_id: int, round_no: int) -> None:
        alive = self.repo.alive_players(battle_id)

        if len(alive) < 2:
            if alive:
                await self._finish_battle(
                    battle_id, [Slot(alive[0].user_id, alive[0].nickname, 0, 1)]
                )
            else:
                self.repo.close_battle(battle_id, BattleStatus.CANCELLED)
                await self._open_registration_locked()
            return

        deadline = deadline_for_round(round_no, self.now(), self.config.round_times)
        self.repo.set_round(battle_id, round_no, deadline)
        self.repo.set_battle_status(battle_id, BattleStatus.RUNNING)

        plan = bracket.plan_round(alive, round_no, self.rng)
        advance = bracket.base_advance(plan)

        await self.publisher.announce(
            texts.round_announcement(
                round_no, plan.is_final, len(alive), plan.match_count, deadline
            )
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
            message_id = await self.publisher.publish_match(match_id)
            markup = keyboards.my_match(match_id, self.config, self._post_url(message_id))
            for player in group:
                rivals = [p.nickname for p in group if p.user_id != player.user_id]
                await self._dm(player.user_id, texts.advanced(rivals), markup)

    async def cancel(self, battle_id: int) -> int:
        """Отменить батл: голосование встаёт, участники узнают, набор открывается заново.

        Возвращает число закрытых матчей.
        """
        async with self._lock:
            participants = [p.user_id for p in self.repo.alive_players(battle_id)]
            closed = self.repo.close_battle(battle_id, BattleStatus.CANCELLED)
            log.info("Батл #%s отменён, закрыто матчей: %s", battle_id, closed)

        await self.publisher.announce(texts.battle_cancelled())
        await self._notify_many(participants, texts.BATTLE_CANCELLED_DM)
        await self.open_registration()
        return closed

    async def open_registration(self) -> int | None:
        """Открыть приём заявок в новый батл и объявить об этом.

        Вызывается после финала и после отмены: батл кончился — сразу собираем
        людей на следующий, иначе бот выглядит мёртвым до первой заявки.
        """
        async with self._lock:
            return await self._open_registration_locked()

    async def _open_registration_locked(self) -> int | None:
        """То же, но для кода, который уже держит лок.

        asyncio.Lock не реентерабельный: подведение итогов держит его целиком,
        и повторный захват из финала остановил бы бота намертво.
        """
        if self.repo.current_battle() is not None:
            return None

        battle_id = self.ensure_battle()
        deadline = datetime.fromisoformat(self.repo.current_battle()["deadline"])
        await self.publisher.announce(
            texts.registration_open(deadline, self.config.prizes), battle_id
        )
        return battle_id

    async def _reschedule_registration(self, battle_id: int, applied: int) -> None:
        """Мало заявок: сдвигаем дедлайн, уже отданные голоса сохраняются."""
        deadline = deadline_for_round(1, self.now(), self.config.round_times)
        self.repo.extend_deadlines(battle_id, deadline)
        log.info("Заявок %s из %s — приём продлён до %s",
                 applied, self.config.min_participants, deadline)
        await self.publisher.announce(
            texts.postponed(applied, self.config.min_participants, deadline)
        )

    async def _finish_battle(self, battle_id: int, ranking: list[Slot]) -> None:
        for slot in ranking:
            self.repo.set_place(battle_id, slot.user_id, slot.position or 1)
            self.repo.record_place(slot.user_id, slot.position or 1)

        self.repo.close_battle(battle_id, BattleStatus.FINISHED)
        await self.publisher.announce(texts.final_announcement(ranking, self.config.prizes))

        # финалистам — та же честная таблица, что и в раундах
        for slot in ranking:
            await self._dm(
                slot.user_id,
                texts.match_result_dm(
                    ranking=ranking,
                    you_id=slot.user_id,
                    round_no=0,
                    is_final=True,
                    advanced=slot.position == 1,
                    tie_broken=False,
                ),
            )
            place = slot.position or 1
            if place <= len(self.config.prizes):
                await self._dm(
                    slot.user_id, texts.took_place(place, self.config.prizes[place - 1])
                )
        log.info("Батл #%s завершён", battle_id)

        # батл кончился — сразу собираем людей на следующий
        await self._open_registration_locked()

    # ---------------------------------------------------------------- рассылка

    async def _notify_many(self, user_ids: list[int], text: str) -> None:
        for user_id in user_ids:
            await self._dm(user_id, text)

    async def _dm(self, user_id: int, text: str, markup=None) -> None:
        try:
            await self.bot.send_message(
                user_id, text, reply_markup=markup, disable_web_page_preview=True
            )
        except TelegramAPIError as error:
            log.info("Не доставлено пользователю %s: %s", user_id, error)
        await asyncio.sleep(self.config.dm_delay)  # мягкий рейт-лимит на рассылку
