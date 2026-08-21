"""Автопилот: бот сам напоминает, анонсирует и крутит рекламу.

Задача — чтобы каналы жили без ежедневного участия админа. Раз в минуту
проверяется, не пора ли что-то отправить:

* напоминание перед закрытием раунда — в канал и участникам в личку;
* ежедневный анонс набора, если приём заявок открыт;
* рекламный пост из очереди с заданным интервалом.

Каждое разовое действие отмечается в базе одним запросом, поэтому повтор
невозможен: ни при двух тиках подряд, ни после перезапуска бота.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import MSK, Config
from core.engine import BattleEngine
from core.models import BattleStatus
from services import texts
from services.keyboards import GREEN
from storage.repo import Repo
from storage.settings import Settings

log = logging.getLogger(__name__)

DAILY_ANNOUNCE_HOUR = 12  # полдень МСК: до вечерних итогов есть время подать заявку


def parse_hours(raw: str) -> list[int]:
    """«3,1» -> [3, 1]. Мусор молча пропускается, автопилот из-за него не встаёт."""
    hours = []
    for part in (raw or "").replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit() and 0 < int(part) <= 48:
            hours.append(int(part))
    return sorted(set(hours), reverse=True)


class Autopilot:
    def __init__(
        self, bot: Bot, repo: Repo, config: Config, settings: Settings, engine: BattleEngine
    ) -> None:
        self.bot = bot
        self.repo = repo
        self.config = config
        self.settings = settings
        self.engine = engine

    def now(self) -> datetime:
        return datetime.now(MSK)

    async def tick(self) -> None:
        """Один проход. Ошибка в одной задаче не мешает остальным."""
        if not self.settings.get("autopilot_enabled"):
            return

        for task in (self._remind_before_deadline, self._daily_call, self._promo):
            try:
                await task()
            except Exception:  # noqa: BLE001 - автопилот не должен ронять бота
                log.exception("Автопилот: сбой в %s", task.__name__)

    # ------------------------------------------------ напоминание о дедлайне

    async def _remind_before_deadline(self) -> None:
        battle = self.repo.current_battle()
        if battle is None or not battle["deadline"]:
            return

        deadline = datetime.fromisoformat(battle["deadline"])
        left = deadline - self.now()
        if left.total_seconds() <= 0:
            return

        for hours in parse_hours(self.settings.get("reminder_hours")):
            window = timedelta(hours=hours)
            # попадаем в окно «осталось примерно столько-то»
            if not (window - timedelta(minutes=5) < left <= window):
                continue

            key = f"{battle['id']}:{battle['round_no']}:{hours}"
            if not self.repo.mark_done("reminder", key):
                return

            await self._announce_reminder(battle, hours, deadline)
            await self._nudge_participants(battle, hours)
            return

    async def _announce_reminder(self, battle, hours: int, deadline: datetime) -> None:
        registration = battle["status"] == BattleStatus.REGISTRATION.value
        text = texts.reminder_post(hours, deadline, registration)
        await self.engine.publisher.announce(text, int(battle["id"]))

        main_channel = self.settings.get("main_channel_id")
        if main_channel and main_channel != self.config.channel_id:
            await self._post(main_channel, text, join=registration)

    async def _nudge_participants(self, battle, hours: int) -> None:
        """Живым участникам — личное «зови голосовать»."""
        battle_id = int(battle["id"])
        for player in self.repo.alive_players(battle_id):
            match = self.repo.active_match_for(player.user_id)
            if match is None:
                continue
            from services import links

            await self.engine._dm(
                player.user_id,
                texts.reminder_dm(
                    hours, links.vote_link(self.config.bot_username, int(match["id"]))
                ),
            )

    # -------------------------------------------------- ежедневный анонс

    async def _daily_call(self) -> None:
        """Раз в день позвать людей записаться.

        Батлы теперь запускает админ, и между ними активного батла попросту
        нет. Раньше зов был привязан к открытому приёму заявок — и после
        перехода на ручной запуск он замолчал совсем. Поэтому зовём и в
        очередь: именно из неё собирается следующий батл.
        """
        moment = self.now()
        if moment.hour != DAILY_ANNOUNCE_HOUR or moment.minute > 5:
            return

        battle = self.repo.current_battle()
        registration = (
            battle is not None
            and battle["status"] == BattleStatus.REGISTRATION.value
            and battle["deadline"]
        )
        if battle is not None and not registration:
            return  # батл уже идёт: звать некуда, люди голосуют

        if not self.repo.mark_done("daily", moment.strftime("%Y-%m-%d")):
            return

        prizes = self.settings.get("prizes")
        if registration:
            text = texts.daily_call(
                self.repo.participant_count(int(battle["id"])),
                datetime.fromisoformat(battle["deadline"]),
                prizes,
            )
        else:
            text = texts.queue_call(self.repo.queue_size(), prizes)

        battle_id = int(battle["id"]) if battle is not None else None
        await self.engine.publisher.announce(text, battle_id)
        main_channel = self.settings.get("main_channel_id")
        if main_channel and main_channel != self.config.channel_id:
            await self._post(main_channel, text, join=True)

    # ------------------------------------------------------------ реклама

    async def _promo(self) -> None:
        interval = self.settings.get("promo_interval_hours")
        if interval <= 0:
            return

        promo = self.repo.next_promo()
        if promo is None:
            return

        # ключ окна: пока идёт тот же интервал, второй пост не уйдёт
        slot = int(self.now().timestamp() // (interval * 3600))
        if not self.repo.mark_done("promo", str(slot)):
            return

        markup = None
        if promo["button_label"] and promo["button_url"]:
            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=promo["button_label"], url=promo["button_url"], style=GREEN
                        )
                    ]
                ]
            )

        targets = {self.config.channel_id}
        main_channel = self.settings.get("main_channel_id")
        if main_channel:
            targets.add(main_channel)

        for channel_id in targets:
            await self._post(channel_id, promo["text"], markup=markup)
        self.repo.mark_promo_sent(int(promo["id"]))
        log.info("Автопилот опубликовал рекламу #%s", promo["id"])

    # ------------------------------------------------------------ отправка

    async def _post(self, chat_id: int, text: str, join: bool = False, markup=None) -> None:
        from services import links

        if markup is None and join:
            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="⚡ Участвовать",
                            url=links.join_link(self.config.bot_username),
                            style=GREEN,
                        )
                    ]
                ]
            )
        try:
            message = await self.bot.send_message(
                chat_id=chat_id, text=text, reply_markup=markup,
                disable_web_page_preview=True,
            )
            self.repo.record_post(chat_id, message.message_id, None, kind="auto")
        except TelegramAPIError as error:
            log.warning("Автопилот не смог написать в %s: %s", chat_id, error)
