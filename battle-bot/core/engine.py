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
from core.scheduler import next_deadline
from services import keyboards, links, member_channel, texts
from services.channel import ChannelPublisher
from services.tg import is_blocked
from storage.repo import Repo
from storage.settings import Settings

log = logging.getLogger(__name__)


class BattleEngine:
    def __init__(
        self, bot: Bot, repo: Repo, config: Config, emoji_skip: set[int] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.bot = bot
        self.repo = repo
        self.config = config
        # настройки нужны, чтобы знать, включены ли личные каналы участников
        self.settings = settings or Settings(repo.conn, config)
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

    # ------------------------------------------------------------------ заявки

    async def join(self, user_id: int, nickname: str) -> tuple[bool, str]:
        """Записать в очередь на следующий батл.

        Очередь копится всегда — и пока батла нет, и пока идёт текущий.
        Пары составляются в момент, когда админ создаёт батл.

        Лок здесь сознательно не берётся. Подведение итогов держит его
        минутами: там сотни сообщений в канал и в личку. Если бы заявка ждала
        его, человек в это время видел бы зависшую кнопку. А ждать нечего:
        заявка трогает только очередь, и запись ровно одна — `enqueue`
        отдаёт False, если человек уже в ней. Худшее, что может случиться при
        совпадении с созданием батла, — заявка достанется следующему батлу.
        """
        if self.repo.is_banned(user_id):
            return False, "Вы не можете участвовать в батлах."

        battle = self.repo.current_battle()
        if battle is not None and self.repo.is_participant(int(battle["id"]), user_id):
            return False, texts.ALREADY_IN_BATTLE

        if not self.repo.enqueue(user_id, nickname):
            return False, texts.already_queued(self.repo.queue_size())

        return True, texts.queued(self.repo.queue_size())

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
        markup = keyboards.my_match(
            match_id, self.config, self._post_url(message_id),
            member_channel.enabled(self.settings),
        )
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

    async def close_round(self, force: bool = False) -> None:
        """Подвести итоги текущего раунда и запустить следующий.

        Лок держим на весь подсчёт: пока идут итоги, ничто не должно
        вмешиваться в закрываемый раунд.

        ``force`` — итоги по кнопке админа. Без него дедлайн проверяется
        второй раз, уже под локом. Это важно: подсчёт большого раунда идёт
        минутами, и за это время в очереди на лок мог оказаться ещё один
        вызов. Он дождался бы своей очереди и закрыл уже следующий раунд —
        на полтора часа раньше срока, вместе со всеми голосами, которые в нём
        не успели отдать.
        """
        async with self._lock:
            if not force and not self._deadline_passed():
                log.info("Итоги не подводим: дедлайн раунда ещё не наступил")
                return
            await self._close_round_locked()

    def _deadline_passed(self) -> bool:
        deadline = self.current_deadline()
        return deadline is not None and self.now() >= deadline

    async def _close_round_locked(self) -> None:
        battle = self.repo.current_battle()
        if battle is None:
            return
        battle_id = int(battle["id"])
        round_no = int(battle["round_no"])
        matches = self.repo.open_matches(battle_id, round_no)

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
            await self._publish_result_to_own_channel(
                slot.user_id, round_no, is_final, result.ranking
            )

    async def _publish_to_own_channel(self, user_id: int, match_id: int) -> None:
        """Пара участника уходит в его собственный канал, если он его подключил."""
        try:
            await member_channel.publish_match(
                self.bot, self.repo, self.config, self.settings, user_id, match_id,
                self.publisher.emoji_skip,
            )
        except Exception:  # публикация к себе не должна ронять ход батла
            log.exception("Не удалось опубликовать пару в канале участника %s", user_id)

    async def _publish_result_to_own_channel(
        self, user_id: int, round_no: int, is_final: bool, ranking: list[Slot]
    ) -> None:
        try:
            await member_channel.publish_result(
                self.bot, self.repo, self.settings, user_id, round_no, is_final, ranking,
                self.publisher.emoji_skip,
            )
        except Exception:
            log.exception("Не удалось опубликовать итог в канале участника %s", user_id)

    async def _start_round(self, battle_id: int, round_no: int) -> None:
        alive = self.repo.alive_players(battle_id)

        if len(alive) < 2:
            if alive:
                await self._finish_battle(
                    battle_id, [Slot(alive[0].user_id, alive[0].nickname, 0, 1)]
                )
            else:
                self.repo.close_battle(battle_id, BattleStatus.CANCELLED)
            return

        deadline = next_deadline(self.now(), self.config.round_times)
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
            markup = keyboards.my_match(
                match_id, self.config, self._post_url(message_id),
                member_channel.enabled(self.settings),
            )
            for player in group:
                rivals = [p.nickname for p in group if p.user_id != player.user_id]
                await self._dm(player.user_id, texts.advanced(rivals), markup)
                await self._publish_to_own_channel(player.user_id, match_id)

    async def create_from_queue(self) -> tuple[bool, str]:
        """Собрать батл из очереди. Вызывается админом из панели."""
        async with self._lock:
            if self.repo.current_battle() is not None:
                return False, "Батл уже идёт. Сначала подведите итоги или отмените его."

            waiting = self.repo.queue_players(self.config.max_participants)
            if len(waiting) < self.config.min_participants:
                return False, (
                    f"В очереди {len(waiting)} из "
                    f"{self.config.min_participants} нужных. Батл не начат."
                )

            deadline = next_deadline(self.now(), self.config.round_times)
            battle_id = self.repo.create_battle(deadline)
            for player in waiting:
                self.repo.add_participant(battle_id, player.user_id, player.nickname)
            self.repo.take_from_queue([p.user_id for p in waiting])
            log.info("Батл #%s создан из очереди: %s участников", battle_id, len(waiting))

            await self._start_round(battle_id, 1)
            return True, f"Батл #{battle_id} начат: {len(waiting)} участников."

    async def cancel(self, battle_id: int) -> int:
        """Отменить батл: голосование встаёт, участники узнают, набор открывается заново.

        Возвращает число закрытых матчей.
        """
        async with self._lock:
            participants = [p.user_id for p in self.repo.alive_players(battle_id)]
            closed = self.repo.close_battle(battle_id, BattleStatus.CANCELLED)
            log.info("Батл #%s отменён, закрыто матчей: %s", battle_id, closed)

        await self.publisher.announce(texts.battle_cancelled(self.repo.queue_size()))
        await self._notify_many(participants, texts.BATTLE_CANCELLED_DM)
        return closed

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
            await self._publish_result_to_own_channel(slot.user_id, 0, True, ranking)
        log.info("Батл #%s завершён", battle_id)

        log.info("Очередь на следующий батл: %s", self.repo.queue_size())

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
            if is_blocked(error):
                # больше не тратим на него запросы, пока сам не напишет
                self.repo.mark_blocked(user_id)
            log.info("Не доставлено пользователю %s: %s", user_id, error)
        await asyncio.sleep(self.config.dm_delay)  # мягкий рейт-лимит на рассылку
