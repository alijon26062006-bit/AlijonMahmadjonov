"""Движок батла: заявки, публикация пар, закрытие раундов, финал."""
from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from config import Config, MSK
from core import bracket
from core.models import BattleStatus, Player, Slot
from core.scheduler import first_deadline, next_deadline
from services import keyboards, links, main_post, member_channel, texts
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
        """Принять заявку.

        Пока батл в начальных раундах, новичок попадает **в него**: как только
        наберётся пара, её пост сразу выходит в канале. Так канал живёт всё
        время батла, а не только в момент старта.

        Позже подсаживать нельзя — сетка уже сошлась к финалу, и свежий
        участник получил бы преимущество перед теми, кто прошёл два раунда.
        С этого момента заявки просто копятся в очереди на следующий батл.

        До какого раунда пускать — настройка «Приём заявок до раунда»
        (по умолчанию 2).
        """
        if self.repo.is_banned(user_id):
            return False, "Вы не можете участвовать в батлах."

        # вышел из обязательного канала — заявки не принимаем, пока не вернёт
        # доступ. Подписаться обратно недостаточно: отметка снимается оплатой
        # или админом
        if self.settings.get("leave_penalty_enabled"):
            left = self.repo.leaver(user_id)
            if left is not None:
                return False, texts.leaver_refused(
                    int(left["times"]), int(self.settings.get("rejoin_price") or 0)
                )

        rest = self.repo.cooldown_for(user_id, self.now())
        if rest is not None:
            return False, texts.on_cooldown(
                int(rest["place"]),
                datetime.fromisoformat(rest["until"]),
                self.now(),
                int(self.settings.get("cooldown_skip_price") or 0),
            )

        battle = self.repo.current_battle()
        if battle is not None and self.repo.is_participant(int(battle["id"]), user_id):
            return False, texts.ALREADY_IN_BATTLE

        if self._accepts_latecomers(battle):
            joined = await self._join_running(user_id, nickname)
            if joined is not None:
                return joined

        # очередь трогает только саму себя, поэтому лок ей не нужен: заявка
        # не должна ждать подведения итогов, которое идёт минутами
        if not self.repo.enqueue(user_id, nickname):
            return False, texts.already_queued(self.repo.queue_size())

        waiting = self.repo.queue_size()
        await self._tell_admins_queue_is_ready(waiting)
        return True, texts.queued(waiting)

    async def _tell_admins_queue_is_ready(self, waiting: int) -> None:
        """Сказать админу ровно один раз: людей хватает, можно запускать.

        Момент ловим по точному совпадению с минимумом — так сообщение уходит
        один раз за набор, а не на каждую следующую заявку.
        """
        if waiting != self.config.min_participants:
            return
        if self.repo.current_battle() is not None:
            return  # батл уже идёт, запускать всё равно нечего

        for admin_id in self.config.admin_ids:
            await self._dm(admin_id, texts.queue_ready(waiting, self.config.min_participants))

    def late_join_limit(self) -> int:
        try:
            return int(self.settings.get("late_join_until_round"))
        except (TypeError, ValueError):
            return 0

    def _accepts_latecomers(self, battle) -> bool:
        """Можно ли ещё подсадить новичка в этот батл."""
        if battle is None:
            return False
        return int(battle["round_no"]) <= self.late_join_limit()

    async def _join_running(self, user_id: int, nickname: str) -> tuple[bool, str] | None:
        """Подсадить в идущий батл. None — не получилось, пусть идёт в очередь.

        Лок нужен: заявка заводит матч, а подведение итогов в это же время
        закрывает раунд. Без него пара могла бы родиться в раунде, который
        уже закрывают, и умереть с нулём голосов.
        """
        async with self._lock:
            battle = self.repo.current_battle()
            if not self._accepts_latecomers(battle):
                return None  # пока ждали лок, раунд сменился или батл кончился

            battle_id = int(battle["id"])
            round_no = int(battle["round_no"])
            if self.repo.participant_count(battle_id) >= self.config.max_participants:
                return None  # батл переполнен — такому место в очереди

            # В маленьком батле финал наступает уже во втором раунде. Подсадить
            # туда нельзя: финал разыгрывает призовые места, и пара, заведённая
            # рядом с ним, просто сгорела бы вместе с концом батла.
            if any(row["is_final"] for row in self.repo.open_matches(battle_id, round_no)):
                return None

            if not self.repo.add_participant(battle_id, user_id, nickname):
                return False, texts.ALREADY_IN_BATTLE
            self.repo.leave_queue(user_id)  # он уже в батле, в очереди ему делать нечего

            waiting = self.repo.unassigned_players(battle_id)
            if len(waiting) < 2:
                return True, texts.joined_running(round_no)

            await self._pair_latecomers(battle, waiting[:2])
            rival = next(p.nickname for p in waiting[:2] if p.user_id != user_id)
            return True, texts.pair_published(rival)

    async def _pair_latecomers(self, battle, pair: list[Player]) -> None:
        """Завести и опубликовать пару из двух подсевших."""
        battle_id = int(battle["id"])
        round_no = int(battle["round_no"])
        deadline = datetime.fromisoformat(battle["deadline"])

        match_id = self.repo.create_match(
            battle_id=battle_id,
            round_no=round_no,
            number=self.repo.match_count(battle_id, round_no) + 1,
            players=pair,
            advance=1,
            is_final=False,
            deadline=deadline,
        )
        message_id = await self.publisher.publish_match(match_id)
        markup = keyboards.my_match(
            match_id, self.config, self._post_url(message_id),
            member_channel.enabled(self.settings),
        )
        for player in pair:
            rival = next(p.nickname for p in pair if p.user_id != player.user_id)
            await self._dm(player.user_id, texts.pair_published(rival), markup)
            await self._publish_to_own_channel(player.user_id, match_id)
        log.info("Подсадил пару в батл #%s, раунд %s: матч %s", battle_id, round_no, match_id)

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
            # первый раунд закончился, а пар так и не набралось: батл пустой
            if round_no == 1:
                await self._give_up_empty_battle(battle_id)
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

        # кому не досталось пары — проходит без боя. Это и нечётный участник
        # первого раунда, и новичок, подсевший под конец раунда
        byes = [p.user_id for p in self.repo.unassigned_players(battle_id)]
        self.repo.eliminate(battle_id, eliminated)
        self.repo.bump_wins(advanced)

        await self._notify_many(byes, texts.BYE_ROUND)

        await self._start_round(battle_id, round_no + 1)

    async def _give_up_empty_battle(self, battle_id: int) -> None:
        """Время вышло, а пар не набралось — закрываем и никого не теряем.

        Тот единственный, кто успел заявиться, возвращается в очередь: он
        подал заявку и не виноват, что соперника не нашлось.
        """
        left = self.repo.alive_players(battle_id)
        self.repo.close_battle(battle_id, BattleStatus.CANCELLED)
        for player in left:
            self.repo.enqueue(player.user_id, player.nickname)

        log.info("Батл #%s закрыт: заявок не набралось", battle_id)
        await self.publisher.announce(texts.battle_empty())
        await self._notify_many([p.user_id for p in left], texts.BATTLE_EMPTY_DM)
        for admin_id in self.config.admin_ids:
            await self._dm(admin_id, texts.battle_empty_admin(len(left)))

    async def _send_match_results(self, result, round_no: int, is_final: bool) -> None:
        """Разослать участникам матча честный итог: вся таблица, а не «вы проиграли»."""
        winners = set(result.winners)
        invite = self.settings.get("referral_enabled")
        for slot in result.ranking:
            advanced = slot.user_id in winners
            await self._dm(
                slot.user_id,
                texts.match_result_dm(
                    ranking=result.ranking,
                    you_id=slot.user_id,
                    round_no=round_no,
                    is_final=is_final,
                    advanced=advanced,
                    tie_broken=result.tie_broken,
                ),
                # вылетевшему — сразу кнопку реванша, пока обида свежая
                None if advanced else keyboards.next_battle(self.config, invite),
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
            if round_no == 1:
                # Батл только что создан и пока пустой — это нормально.
                # Люди придут из главного канала по кнопке «Участвовать»,
                # и каждая пара будет опубликована по мере набора.
                await self._open_empty_first_round(battle_id, len(alive))
                return
            if alive:
                await self._finish_battle(
                    battle_id, [Slot(alive[0].user_id, alive[0].nickname, 0, 1)]
                )
            else:
                self.repo.close_battle(battle_id, BattleStatus.CANCELLED)
            return

        # первый раунд идёт до первого времени из списка (при необходимости —
        # завтрашнего), дальше раунды берут ближайшие оставшиеся слоты
        deadline = (
            first_deadline(self.now(), self.config.round_times)
            if round_no == 1
            else next_deadline(self.now(), self.config.round_times)
        )
        self.repo.set_round(battle_id, round_no, deadline)
        self.repo.set_battle_status(battle_id, BattleStatus.RUNNING)

        # со второго раунда соперников подбирает посев: сильные разводятся
        # по разным группам и встречаются только в финале
        strength = (
            self.repo.player_strength(battle_id)
            if self.settings.get("seeding") == "snake"
            else None
        )
        plan = bracket.plan_round(alive, round_no, self.rng, strength)
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

    async def _open_empty_first_round(self, battle_id: int, waiting: int) -> None:
        """Открыть первый раунд, когда участников ещё нет или всего один."""
        deadline = first_deadline(self.now(), self.config.round_times)
        self.repo.set_round(battle_id, 1, deadline)
        self.repo.set_battle_status(battle_id, BattleStatus.RUNNING)
        await self.publisher.announce(texts.battle_opened(deadline, waiting))
        log.info("Батл #%s открыт без пар: ждём заявок", battle_id)

    async def create_from_queue(self) -> tuple[bool, str]:
        """Собрать батл из очереди. Вызывается админом из панели."""
        async with self._lock:
            if self.repo.current_battle() is not None:
                return False, "Батл уже идёт. Сначала подведите итоги или отмените его."

            # минимума на создание нет и быть не должно: батл заводится
            # первым, а люди подтягиваются из главного канала по кнопке
            # «Участвовать» — весь первый раунд идёт именно на это
            waiting = self.repo.queue_players(self.config.max_participants)
            deadline = first_deadline(self.now(), self.config.round_times)
            battle_id = self.repo.create_battle(deadline)
            for player in waiting:
                self.repo.add_participant(battle_id, player.user_id, player.nickname)
            self.repo.take_from_queue([p.user_id for p in waiting])
            log.info("Батл #%s создан из очереди: %s участников", battle_id, len(waiting))

            await self._start_round(battle_id, 1)
            await self._call_main_channel(
                battle_id, self.current_deadline() or deadline, len(waiting)
            )
            if waiting:
                note = f"Батл #{battle_id} начат: {len(waiting)} участников."
            else:
                note = (
                    f"Батл #{battle_id} открыт. Пока никого — "
                    "зов ушёл в главный канал, ждём заявок."
                )
            return True, note

    async def _call_main_channel(self, battle_id: int, deadline, participants: int) -> None:
        """Позвать людей в главный канал: батл начался, заявку ещё можно подать.

        Пост уходит именно в момент запуска — пока идёт первый раунд, бот
        подберёт соперника любому, кто нажмёт кнопку. Сбой публикации не
        должен рушить уже начатый батл, поэтому ошибку только пишем в лог.
        """
        channel_id = self.settings.get("main_channel_id")
        if not channel_id:
            log.info("Главный канал не задан — зов о начале батла не отправлен")
            return

        try:
            message = await self.bot.send_message(
                channel_id,
                texts.battle_started_post(
                    participants, deadline, self.settings.get("prizes")
                ),
                reply_markup=main_post.keyboard(
                    self.config.bot_username, self.config.premium_emoji
                ),
                disable_web_page_preview=True,
            )
        except TelegramAPIError as error:
            log.warning("Не удалось позвать в главный канал: %s", error)
            return

        # запоминаем пост, чтобы панель могла убрать его вместе с остальными
        self.repo.record_post(channel_id, message.message_id, battle_id, kind="call")

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
        await self._show_off_in_main_channel(battle_id, ranking)

        # финалистам — та же честная таблица, что и в раундах
        invite = self.settings.get("referral_enabled")
        for slot in ranking:
            place = slot.position or 1
            # кто уйдёт на паузу призёра, тому кнопка «в следующий батл» ни к
            # чему: он на неё нажмёт и получит отказ. Ему придёт выкуп паузы
            resting = place <= int(self.settings.get("cooldown_places") or 0) and int(
                self.settings.get("cooldown_days") or 0
            ) > 0
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
                None if resting else keyboards.next_battle(self.config, invite),
            )
            if place <= len(self.config.prizes):
                await self._dm(
                    slot.user_id, texts.took_place(place, self.config.prizes[place - 1])
                )
            await self._rest_after_prize(slot.user_id, place, battle_id)
            await self._publish_result_to_own_channel(slot.user_id, 0, True, ranking)
        log.info("Батл #%s завершён", battle_id)

        log.info("Очередь на следующий батл: %s", self.repo.queue_size())

    async def _show_off_in_main_channel(self, battle_id: int, ranking: list[Slot]) -> None:
        """Итоги батла — в главный канал, с кнопкой на следующий.

        Финал это пик внимания за весь батл: призы названы, победитель
        известен. Раньше этот момент видел только канал батлов, а главный —
        витрина с самой большой аудиторией — не получал ничего.
        """
        channel_id = self.settings.get("main_channel_id")
        if not channel_id:
            return

        try:
            message = await self.bot.send_message(
                channel_id,
                texts.battle_finished_post(ranking, self.settings.get("prizes")),
                reply_markup=main_post.keyboard(
                    self.config.bot_username, self.config.premium_emoji
                ),
                disable_web_page_preview=True,
            )
        except TelegramAPIError as error:
            log.warning("Не удалось показать итоги в главном канале: %s", error)
            return

        self.repo.record_post(channel_id, message.message_id, battle_id, kind="final")

    async def _rest_after_prize(self, user_id: int, place: int, battle_id: int) -> None:
        """Отправить призёра на паузу: пусть призы достаются не одним и тем же."""
        days = int(self.settings.get("cooldown_days") or 0)
        places = int(self.settings.get("cooldown_places") or 0)
        if days <= 0 or place > places:
            return

        until = self.now() + timedelta(days=days)
        self.repo.set_cooldown(user_id, place, battle_id, until)
        price = int(self.settings.get("cooldown_skip_price") or 0)
        await self._dm(
            user_id,
            texts.cooldown_started(place, until, price),
            keyboards.buy_cooldown(price) if price else None,
        )

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
