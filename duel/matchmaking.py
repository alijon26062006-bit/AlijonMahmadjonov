"""Подбор соперника: общая очередь и приватные комнаты для игры с другом.

Сначала ищем ровню — того, кто выбрал ту же длительность, тот же уровень и
близок по рейтингу. Чем дольше человек ждёт, тем шире круг поиска: сидеть в
очереди в одиночку хуже, чем сыграть с чуть более сильным соперником.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass, field

from .game import Match, Side

# Стартовая разница в рейтинге и насколько она растёт за секунду ожидания.
WINDOW_START = 120
WINDOW_GROWTH = 90
WINDOW_MAX = 5000
# Когда перестаём держаться за выбранный уровень, а когда — и за длительность.
FLEX_LEVEL_SEC = 20.0
FLEX_ANY_SEC = 40.0
# Код комнаты: без похожих друг на друга символов (0/O, 1/I).
ROOM_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ROOM_CODE_LEN = 6
ROOM_TTL_SEC = 15 * 60
# Друг принял вызов, а хозяин вышел из игры — столько ждём его возвращения.
HOST_GRACE_SEC = 3 * 60


@dataclass
class Ticket:
    """Заявка на матч."""

    user_id: int
    name: str
    rating: int = 1000
    games: int = 0
    lang: str = "ru"
    photo_url: str = ""
    duration: int = 60
    level: str = "auto"
    joined_at: float = 0.0

    def window(self, now: float) -> int:
        waited = max(0.0, now - self.joined_at)
        return min(WINDOW_MAX, int(WINDOW_START + WINDOW_GROWTH * waited))

    def waited(self, now: float) -> float:
        return max(0.0, now - self.joined_at)

    def to_side(self) -> Side:
        return Side(
            user_id=self.user_id,
            name=self.name,
            rating=self.rating,
            games=self.games,
            lang=self.lang,
            photo_url=self.photo_url,
        )


@dataclass
class Room:
    """Приватная комната: играют только те, у кого есть код.

    target — если вызов адресный, входит только тот, кого позвали.
    """

    code: str
    host: Ticket
    created_at: float = 0.0
    target: int = 0
    # Друг уже нажал «В бой», но хозяина в игре нет — ждём, пока он зайдёт.
    accepted_by: int = 0
    accepted_at: float = 0.0


@dataclass
class Queue:
    """Очередь ожидающих. Один игрок — одна заявка."""

    tickets: dict[int, Ticket] = field(default_factory=dict)
    rooms: dict[str, Room] = field(default_factory=dict)
    _rng: random.Random = field(default_factory=random.Random)

    # ── общая очередь ───────────────────────────────────────────────

    def add(self, ticket: Ticket) -> None:
        """Ставит в очередь. Повторный вход заменяет прошлую заявку."""

        self.tickets[ticket.user_id] = ticket

    def remove(self, user_id: int) -> Ticket | None:
        """Уходит совсем: снимаем и заявку, и созданную им комнату."""

        self.drop_rooms_of(user_id)
        return self.tickets.pop(user_id, None)

    def drop_ticket(self, user_id: int) -> Ticket | None:
        """Просто закрыл приложение. Комнату не трогаем: он мог уйти делиться
        ссылкой, и убивать её вместе с ним — значит рвать приглашение."""

        return self.tickets.pop(user_id, None)

    def rooms_of(self, user_id: int) -> list[Room]:
        return [room for room in self.rooms.values() if room.host.user_id == user_id]

    def __len__(self) -> int:
        return len(self.tickets)

    def waiting_like(self, duration: int, level: str) -> int:
        return sum(
            1 for t in self.tickets.values() if t.duration == duration and t.level == level
        )

    def _fits(self, one: Ticket, other: Ticket, now: float) -> bool:
        gap = abs(one.rating - other.rating)
        return gap <= max(one.window(now), other.window(now))

    def _pair_within(
        self, group: list[Ticket], now: float, taken: set[int]
    ) -> list[tuple[Ticket, Ticket]]:
        """Внутри группы соединяет соседей по рейтингу, кто друг другу подходит."""

        pool = sorted(
            (t for t in group if t.user_id not in taken),
            key=lambda t: (t.rating, t.joined_at),
        )
        pairs: list[tuple[Ticket, Ticket]] = []
        index = 0
        while index + 1 < len(pool):
            one, other = pool[index], pool[index + 1]
            if self._fits(one, other, now):
                pairs.append((one, other))
                taken.add(one.user_id)
                taken.add(other.user_id)
                index += 2
            else:
                index += 1
        return pairs

    def find_pairs(self, now: float) -> list[tuple[Ticket, Ticket]]:
        """Все пары, которые можно составить прямо сейчас. Найденные уходят из очереди."""

        taken: set[int] = set()
        pairs: list[tuple[Ticket, Ticket]] = []

        # Точное совпадение: та же длительность, тот же уровень.
        buckets: dict[tuple[int, str], list[Ticket]] = {}
        for ticket in self.tickets.values():
            buckets.setdefault((ticket.duration, ticket.level), []).append(ticket)
        for group in buckets.values():
            pairs += self._pair_within(group, now, taken)

        # Ждёт долго — забываем про уровень, держимся за длительность.
        patient = [
            t
            for t in self.tickets.values()
            if t.user_id not in taken and t.waited(now) >= FLEX_LEVEL_SEC
        ]
        by_duration: dict[int, list[Ticket]] = {}
        for ticket in patient:
            by_duration.setdefault(ticket.duration, []).append(ticket)
        for group in by_duration.values():
            pairs += self._pair_within(group, now, taken)

        # Ждёт совсем долго — сведём с кем угодно, лишь бы не сидел один.
        desperate = [
            t
            for t in self.tickets.values()
            if t.user_id not in taken and t.waited(now) >= FLEX_ANY_SEC
        ]
        pairs += self._pair_within(desperate, now, taken)

        for one, other in pairs:
            self.tickets.pop(one.user_id, None)
            self.tickets.pop(other.user_id, None)
        return pairs

    # ── приватные комнаты ───────────────────────────────────────────

    def new_code(self) -> str:
        while True:
            code = "".join(self._rng.choice(ROOM_ALPHABET) for _ in range(ROOM_CODE_LEN))
            if code not in self.rooms:
                return code

    def create_room(self, host: Ticket, now: float, target: int = 0) -> Room:
        """Хозяин создаёт комнату и зовёт друга: по коду или лично."""

        self.drop_rooms_of(host.user_id)
        self.tickets.pop(host.user_id, None)
        room = Room(code=self.new_code(), host=host, created_at=now, target=target)
        self.rooms[room.code] = room
        return room

    def find_room(self, code: str) -> Room | None:
        """Смотрит комнату по коду, не занимая её."""

        return self.rooms.get(code.strip().upper())

    def join_room(self, code: str, guest: Ticket) -> tuple[Ticket, Ticket] | None:
        """Гость входит по коду. Возвращает пару или None, если комнаты нет."""

        room = self.rooms.get(code.strip().upper())
        if room is None or room.host.user_id == guest.user_id:
            return None
        # Позвали лично — чужой по коду не влезет.
        if room.target and room.target != guest.user_id:
            return None
        del self.rooms[room.code]
        self.tickets.pop(guest.user_id, None)
        return room.host, guest

    def drop_rooms_of(self, user_id: int) -> None:
        for code in [c for c, r in self.rooms.items() if r.host.user_id == user_id]:
            del self.rooms[code]

    def sweep_rooms(self, now: float) -> list[Room]:
        """Убирает комнаты, в которые так никто и не зашёл."""

        stale = [r for r in self.rooms.values() if now - r.created_at > ROOM_TTL_SEC]
        for room in stale:
            self.rooms.pop(room.code, None)
        return stale


def make_match(
    one: Ticket,
    other: Ticket,
    now: float,
    *,
    private: bool = False,
    seed: int | None = None,
) -> Match:
    """Собирает матч из двух заявок. Длительность и уровень — у того, кто ждёт дольше."""

    host = one if one.joined_at <= other.joined_at else other
    level = host.level
    if one.level != other.level and "auto" in (one.level, other.level):
        level = one.level if other.level == "auto" else other.level

    match = Match(
        a=one.to_side(),
        b=other.to_side(),
        duration=host.duration,
        level=level,
        private=private,
        seed=seed,
    )
    match.begin(now)
    return match
