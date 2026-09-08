"""Морской бой: поле, корабли, выстрелы.

Здесь только правила — ни сети, ни базы, ни очерёдности ходов. Поэтому всё
проверяется тестами, не поднимая сервер.

Поля обоих игроков живут на сервере. Клиент знает своё поле и то, что уже
нащупал у соперника, — подсмотреть чужую расстановку неоткуда.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

SIZE = 7
# Корабли: трёхпалубный, два двухпалубных, два однопалубных — девять клеток.
FLEET = (3, 2, 2, 1, 1)

MISS = "miss"
HIT = "hit"
SUNK = "sunk"
REPEAT = "repeat"


class PlacementError(Exception):
    """Расстановка не по правилам."""


Cell = tuple[int, int]


def inside(row: int, col: int) -> bool:
    return 0 <= row < SIZE and 0 <= col < SIZE


def around(cells: tuple[Cell, ...]) -> set[Cell]:
    """Клетки вокруг корабля, включая углы.

    Корабли не должны соприкасаться: иначе расставлять их незачем — любая
    куча в углу будет не хуже продуманной расстановки.
    """

    halo: set[Cell] = set()
    for row, col in cells:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                spot = (row + dr, col + dc)
                if inside(*spot) and spot not in cells:
                    halo.add(spot)
    return halo


def ship_cells(row: int, col: int, size: int, horizontal: bool) -> tuple[Cell, ...]:
    if horizontal:
        return tuple((row, col + i) for i in range(size))
    return tuple((row + i, col) for i in range(size))


@dataclass
class Ship:
    """Один корабль и что от него осталось."""

    cells: tuple[Cell, ...]
    hits: set[Cell] = field(default_factory=set)

    @property
    def size(self) -> int:
        return len(self.cells)

    @property
    def sunk(self) -> bool:
        return len(self.hits) == len(self.cells)

    def halo(self) -> set[Cell]:
        return around(self.cells)


@dataclass
class Board:
    """Поле одного игрока."""

    ships: list[Ship] = field(default_factory=list)
    shots: set[Cell] = field(default_factory=set)

    @property
    def alive(self) -> int:
        """Сколько кораблей ещё на плаву."""

        return sum(1 for ship in self.ships if not ship.sunk)

    @property
    def total_cells(self) -> int:
        return sum(ship.size for ship in self.ships)

    @property
    def hit_cells(self) -> int:
        return sum(len(ship.hits) for ship in self.ships)

    @property
    def defeated(self) -> bool:
        return bool(self.ships) and all(ship.sunk for ship in self.ships)

    def ship_at(self, spot: Cell) -> Ship | None:
        for ship in self.ships:
            if spot in ship.cells:
                return ship
        return None

    def fire(self, row: int, col: int) -> dict[str, object]:
        """Выстрел по клетке. Решает только сервер — здесь вся правда о поле."""

        spot = (row, col)
        if not inside(row, col):
            return {"result": REPEAT, "cell": spot}
        if spot in self.shots:
            # Повторный выстрел в ту же клетку ничего не стоит и ничего не даёт.
            return {"result": REPEAT, "cell": spot}

        self.shots.add(spot)
        ship = self.ship_at(spot)
        if ship is None:
            return {"result": MISS, "cell": spot}

        ship.hits.add(spot)
        if not ship.sunk:
            return {"result": HIT, "cell": spot}

        # Потопил — вокруг корабля стрелять уже незачем, отмечаем это сразу.
        halo = sorted(ship.halo())
        self.shots.update(halo)
        return {
            "result": SUNK,
            "cell": spot,
            "ship": sorted(ship.cells),
            "halo": halo,
        }

    def own_view(self) -> dict[str, object]:
        """Своё поле целиком: его хозяин видит всё."""

        return {
            "ships": [sorted(ship.cells) for ship in self.ships],
            "hits": sorted(spot for ship in self.ships for spot in ship.hits),
            "misses": sorted(
                spot for spot in self.shots if self.ship_at(spot) is None
            ),
            "alive": self.alive,
            "left": self.total_cells - self.hit_cells,
        }


def validate(layout: list[dict]) -> list[Ship]:
    """Проверяет расстановку и собирает корабли.

    Расстановку присылает клиент, поэтому верить ей нельзя: проверяем состав
    флота, границы поля, наложения и касания.
    """

    if not isinstance(layout, list) or len(layout) != len(FLEET):
        raise PlacementError(f"кораблей должно быть {len(FLEET)}")

    parsed = []
    for item in layout:
        try:
            parsed.append(
                (
                    int(item["row"]),
                    int(item["col"]),
                    int(item["size"]),
                    bool(item.get("horizontal", True)),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise PlacementError("корабль записан неверно") from exc

    # Состав флота проверяем раньше геометрии: «прислан не тот флот» понятнее,
    # чем жалоба на то, что лишний корабль кого-то задел.
    sizes = sorted((size for _, _, size, _ in parsed), reverse=True)
    if tuple(sizes) != tuple(sorted(FLEET, reverse=True)):
        raise PlacementError(f"флот должен быть {sorted(FLEET, reverse=True)}")

    ships: list[Ship] = []
    taken: set[Cell] = set()
    forbidden: set[Cell] = set()

    for row, col, size, horizontal in parsed:
        cells = ship_cells(row, col, size, horizontal)
        if not all(inside(*spot) for spot in cells):
            raise PlacementError("корабль вышел за поле")
        if any(spot in taken for spot in cells):
            raise PlacementError("корабли наложились друг на друга")
        if any(spot in forbidden for spot in cells):
            raise PlacementError("корабли касаются друг друга")

        ship = Ship(cells=cells)
        ships.append(ship)
        taken.update(cells)
        forbidden.update(ship.halo())

    return ships


def build_board(layout: list[dict]) -> Board:
    return Board(ships=validate(layout))


def random_layout(rng: random.Random | None = None) -> list[dict]:
    """Случайная расстановка — для кнопки «Расставить» и для робота."""

    rng = rng or random.Random()
    for _ in range(200):
        layout: list[dict] = []
        taken: set[Cell] = set()
        forbidden: set[Cell] = set()
        ok = True

        # Крупные корабли ставим первыми: под них меньше места.
        for size in sorted(FLEET, reverse=True):
            spot = _find_spot(rng, size, taken, forbidden)
            if spot is None:
                ok = False
                break
            row, col, horizontal = spot
            cells = ship_cells(row, col, size, horizontal)
            layout.append(
                {"row": row, "col": col, "size": size, "horizontal": horizontal}
            )
            taken.update(cells)
            forbidden.update(around(cells))

        if ok:
            return layout
    raise PlacementError("не удалось расставить корабли")


def _find_spot(
    rng: random.Random, size: int, taken: set[Cell], forbidden: set[Cell]
) -> tuple[int, int, bool] | None:
    spots = []
    for horizontal in (True, False):
        limit = SIZE - size + 1
        rows = range(SIZE if horizontal else limit)
        cols = range(limit if horizontal else SIZE)
        for row in rows:
            for col in cols:
                cells = ship_cells(row, col, size, horizontal)
                if any(spot in taken or spot in forbidden for spot in cells):
                    continue
                spots.append((row, col, horizontal))
    return rng.choice(spots) if spots else None
