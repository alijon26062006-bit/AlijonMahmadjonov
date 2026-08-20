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


FIELDS: dict[str, Field] = {
    field.key: field
    for field in (
        Field("prizes", "Призы за 1/2/3 место", _ints_to_text, _text_to_ints,
              "числа через запятую, например 1000,500,250"),
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
        Field("referral_enabled", "Приглашения", lambda v: "1" if v else "0",
              lambda raw: raw == "1"),
        Field("main_channel_id", "Главный канал", str, int,
              "перешлите сюда любой пост из канала — ID определится сам, "
              "либо пришлите ID вида -100..."),
        Field("main_post_photo", "Фото главного поста", str, str, "file_id из Telegram"),
        Field("main_post_text", "Текст главного поста", str, str, "любой текст"),
        Field("main_post_message_id", "ID опубликованного главного поста", str, int, ""),
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
        self.apply()

    # значения, которых нет в .env — только в базе
    OWN_DEFAULTS = {
        "main_channel_id": 0,
        "main_post_photo": "",
        "main_post_text": "",
        "main_post_message_id": 0,
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
