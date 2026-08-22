"""Настройки, которые админ меняет из панели.

Живут в базе, а не в .env: перезапускать бота ради смены призов неправильно.
`.env` остаётся источником начальных значений — при первом запуске они
переносятся в базу, дальше правит панель.

Значения применяются к рабочему Config, поэтому остальной код продолжает
читать `config.prizes` и не знает, что настройка приехала из базы.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from datetime import time
from typing import Any, Callable

from config import Config, VotePack, _parse_times
from services import prizes

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Field:
    """Описание одной настройки: как хранить, как читать, как показать."""

    key: str
    title: str
    to_text: Callable[[Any], str]
    from_text: Callable[[str], Any]
    hint: str = ""

    def load(self, raw: str) -> Any:
        return self.from_text(raw)

    def dump(self, value: Any) -> str:
        return self.to_text(value)


def _times_to_text(values: list[time]) -> str:
    return ",".join(t.strftime("%H:%M") for t in values)


def _ints_to_text(values: list[int]) -> str:
    return ",".join(str(v) for v in values)


def _text_to_ints(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


LINK_HINT = "ссылка вида https://t.me/... или @канал; «-» убирает кнопку"

FIELDS: dict[str, Field] = {
    field.key: field
    for field in (
        Field("prizes", "Призы за места", prizes.dump, prizes.parse,
              "каждый приз с новой строки; число — это звёзды, "
              "текст показывается как есть"),
        Field("vote_price", "Цена одного голоса в звёздах", str, int, "целое число"),
        Field("paid_votes_enabled", "Продажа голосов", lambda v: "1" if v else "0",
              lambda raw: raw == "1"),
        Field("round_times", "Время подведения итогов", _times_to_text, _parse_times,
              "время через запятую, например 18:00,19:30,21:00"),
        Field("min_participants", "Минимум участников", str, int, "целое число"),
        Field("max_participants", "Максимум участников", str, int, "целое число"),
        Field("require_subscription", "Обязательная подписка", lambda v: "1" if v else "0",
              lambda raw: raw == "1"),
        Field("require_username", "Требовать @username", lambda v: "1" if v else "0",
              lambda raw: raw == "1"),
        Field("premium_emoji_in_channel", "Премиум-эмодзи в канале", str, str,
              "auto, 1 или 0"),
        Field("referral_reward", "Голосов за приглашение", str, int, "целое число"),
        Field("autopilot_enabled", "Автопилот", lambda v: "1" if v else "0",
              lambda raw: raw == "1"),
        Field("reminder_hours", "Напоминать за (часов)", str, str,
              "часы через запятую, например 3,1"),
        Field("promo_interval_hours", "Реклама раз в (часов)", str, int, "целое число"),
        Field("sponsor_channels", "Каналы обязательной подписки", str, str,
              "ID через запятую; пусто — берётся главный канал"),
        Field("stars_link", "Ссылка «звёзды дешевле»", str, str,
              "ссылка вида https://t.me/... или пусто, чтобы убрать строку"),
        Field("referral_enabled", "Приглашения", lambda v: "1" if v else "0",
              lambda raw: raw == "1"),
        Field("main_channel_id", "Главный канал", str, int,
              "перешлите сюда любой пост из канала — ID определится сам, "
              "либо пришлите ID вида -100..."),
        Field("main_post_photo", "Фото главного поста", str, str, "file_id из Telegram"),
        Field("main_post_text", "Текст главного поста", str, str, "любой текст"),
        Field("main_post_message_id", "ID опубликованного главного поста", str, int, ""),
        Field("member_channels_enabled", "Каналы участников",
              lambda v: "1" if v else "0", lambda raw: raw == "1"),
        Field("free_vote_scope", "Бесплатный голос", str, str,
              "battle — один на весь батл, round — один на раунд, "
              "match — один на каждую пару"),
        Field("late_join_until_round", "Приём заявок до раунда", str, int,
              "номер раунда; 0 — подсадки нет, только очередь"),
        # кнопки-ссылки под экраном «Помощь»; пусто — кнопки нет
        Field("link_main_channel", "Ссылка «Основной канал»", str, str, LINK_HINT),
        Field("link_battles", "Ссылка «Канал с батлами»", str, str, LINK_HINT),
        Field("link_payouts", "Ссылка «Выплаты»", str, str, LINK_HINT),
        Field("link_contact", "Ссылка «Связаться»", str, str, LINK_HINT),
        Field("link_rules", "Ссылка «Правила»", str, str, LINK_HINT),
    )
}


class Settings:
    """Чтение и запись настроек с зеркалированием в рабочий Config."""

    def __init__(self, conn: sqlite3.Connection, config: Config) -> None:
        self.conn = conn
        self.config = config

    # ------------------------------------------------------------- первичный

    def bootstrap(self) -> None:
        """Перенести значения из .env в базу — только те, которых там ещё нет."""
        for key, field in FIELDS.items():
            if self._raw(key) is not None:
                continue
            current = self._from_config(key)
            self._write(key, field.dump(current))
            log.debug("Настройка %s перенесена из .env: %s", key, current)
        self._one_time_fixes()
        self.apply()

    # Разовые правки уже сохранённых значений. Новое значение по умолчанию
    # не помогает: в базе настройка уже лежит, и bootstrap её не трогает.
    # Каждая правка отмечается своим ключом, поэтому выполняется один раз и
    # не откатывает то, что админ поменял потом сам.
    FIXES = (
        # приём заявок сузили до первого раунда: со второго сетка уже сошлась
        ("fix:late_join_1", "late_join_until_round", "2", "1"),
    )

    def _one_time_fixes(self) -> None:
        for marker, key, was, becomes in self.FIXES:
            if self._raw(marker) is not None:
                continue
            if self._raw(key) == was:
                self._write(key, becomes)
                log.info("Настройка %s обновлена: %s -> %s", key, was, becomes)
            self._write(marker, "done")

    # значения, которых нет в .env — только в базе
    OWN_DEFAULTS = {
        "autopilot_enabled": True,
        "reminder_hours": "3,1",
        "promo_interval_hours": 6,
        "sponsor_channels": "",
        "stars_link": "",
        "main_channel_id": 0,
        "main_post_photo": "",
        "main_post_text": "",
        "main_post_message_id": 0,
        "member_channels_enabled": True,
        # до конца какого раунда новичок попадает в идущий батл, а не в очередь.
        # 1 — приём идёт весь первый раунд и закрывается, когда начинается второй
        "late_join_until_round": 1,
        # один бесплатный голос на весь батл: за остальные пары — купленными
        "free_vote_scope": "battle",
        "link_main_channel": "",
        "link_battles": "",
        "link_payouts": "",
        "link_contact": "",
        "link_rules": "",
    }

    def _from_config(self, key: str) -> Any:
        if key in self.OWN_DEFAULTS:
            return self.OWN_DEFAULTS[key]
        if key == "vote_price":
            # раньше цена жила в пакетах; берём стоимость одного голоса
            single = next((p for p in self.config.vote_packs if p.votes == 1), None)
            return single.stars if single else 5
        return getattr(self.config, key)

    # ---------------------------------------------------------------- доступ

    def _raw(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def _write(self, key: str, raw: str) -> None:
        self.conn.execute(
            """INSERT INTO settings(key, value) VALUES(?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                              updated_at = datetime('now')""",
            (key, raw),
        )
        self.conn.commit()

    def get(self, key: str) -> Any:
        field = FIELDS[key]
        raw = self._raw(key)
        if raw is None:
            return self._from_config(key)
        try:
            return field.load(raw)
        except (ValueError, TypeError) as error:
            log.error("Испорченная настройка %s=%r (%s) — беру значение из .env", key, raw, error)
            return self._from_config(key)

    def set(self, key: str, value: Any) -> None:
        field = FIELDS[key]
        self._write(key, field.dump(value))
        self.apply()

    def all(self) -> dict[str, Any]:
        return {key: self.get(key) for key in FIELDS}

    # ------------------------------------------------------------ применение

    def apply(self) -> None:
        """Перелить настройки в рабочий Config, чтобы код читал их как раньше."""
        for key in FIELDS:
            if key == "vote_price" or key in self.OWN_DEFAULTS:
                continue
            setattr(self.config, key, self.get(key))
        self.config.vote_packs = [VotePack(1, self.get("vote_price"))]

    @property
    def vote_price(self) -> int:
        return self.get("vote_price")
