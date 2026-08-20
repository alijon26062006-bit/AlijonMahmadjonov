"""Логика турнирной сетки.

Модуль намеренно ничего не знает ни про Telegram, ни про базу — только списки
игроков и голоса. Благодаря этому вся сетка покрывается обычными тестами.

Правила батла:

* 1 раунд — 1vs1. Пары собираются «на лету»: как только пришли двое, публикуется
  пост. Кто остался без пары к дедлайну — проходит дальше без боя (bye).
* 2 раунд и дальше — группы по 4 ника, дальше проходит лучший.
* Исключение ради призов: если групп меньше четырёх, из каждой проходят двое —
  иначе в финале не набралось бы участников на три призовых места.
* Финал — когда в живых осталось не больше 7 человек: все голосуются одним
  матчем, места 1/2/3 забирают призы.
"""
from __future__ import annotations

import random
from typing import Iterable, Sequence

from .models import MatchResult, Player, RoundPlan, Slot

GROUP_SIZE = 4
FINAL_MAX = 7  # при таком числе выживших играем финал одним матчем
PAIR_SIZE = 2


def rolling_pairs(queue: Sequence[Player]) -> tuple[list[list[Player]], list[Player]]:
    """Разбить очередь заявок на пары для первого раунда.

    Возвращает (пары, остаток). Остаток — 0 или 1 игрок, который ждёт соперника.
    Функция вызывается каждый раз при новой заявке, поэтому пары публикуются
    сразу, а не ждут дедлайна.
    """
    pairs = [list(queue[i:i + PAIR_SIZE]) for i in range(0, len(queue), PAIR_SIZE)]
    if pairs and len(pairs[-1]) < PAIR_SIZE:
        return pairs[:-1], pairs[-1]
    return pairs, []


def split_groups(players: Sequence[Player], size: int = GROUP_SIZE) -> list[list[Player]]:
    """Нарезать на группы по size. Хвост из одного игрока подклеиваем к последней
    группе, чтобы не создавать матч из одного человека."""
    groups = [list(players[i:i + size]) for i in range(0, len(players), size)]
    if len(groups) > 1 and len(groups[-1]) == 1:
        groups[-2].extend(groups.pop())
    return groups


def advance_count(group_size: int, base: int) -> int:
    """Сколько человек проходит из группы. Хотя бы один всегда выбывает."""
    return max(1, min(base, group_size - 1))


def plan_round(
    alive: Sequence[Player],
    round_no: int,
    rng: random.Random | None = None,
) -> RoundPlan:
    """Составить раунд из списка выживших."""
    if len(alive) < 2:
        raise ValueError("Для раунда нужно минимум два участника")

    rng = rng or random.Random()
    players = list(alive)
    rng.shuffle(players)

    if len(players) <= FINAL_MAX:
        return RoundPlan(round_no=round_no, groups=[players], is_final=True)

    if round_no == 1:
        groups, leftover = rolling_pairs(players)
        return RoundPlan(round_no=round_no, groups=groups, byes=leftover)

    return RoundPlan(round_no=round_no, groups=split_groups(players))


def base_advance(plan: RoundPlan) -> int:
    """Сколько проходит из каждой группы этого раунда."""
    if plan.is_final:
        return 0
    return 1 if len(plan.groups) >= GROUP_SIZE else 2


def rank_slots(slots: Iterable[Slot], rng: random.Random | None = None) -> tuple[list[Slot], bool]:
    """Отсортировать участников матча по голосам. Ничья решается жребием.

    Возвращает (ранжированный список, была ли ничья на границе прохода).
    """
    rng = rng or random.Random()
    shuffled = list(slots)
    rng.shuffle(shuffled)  # чтобы при равных голосах порядок был случайным
    ranked = sorted(shuffled, key=lambda s: s.votes, reverse=True)
    tie = len(ranked) > 1 and ranked[0].votes == ranked[1].votes
    return ranked, tie


def resolve_match(
    match_id: int,
    slots: Sequence[Slot],
    advance: int,
    rng: random.Random | None = None,
) -> MatchResult:
    """Закрыть матч: посчитать места, выбрать проходящих дальше."""
    ranked, tie = rank_slots(slots, rng)
    for index, slot in enumerate(ranked, start=1):
        slot.position = index

    take = advance_count(len(ranked), advance) if advance else 0
    winners = [slot.user_id for slot in ranked[:take]]
    losers = [slot.user_id for slot in ranked[take:]]
    return MatchResult(
        match_id=match_id,
        ranking=ranked,
        winners=winners,
        losers=losers,
        tie_broken=tie and take > 0,
    )


def project_rounds(count: int) -> list[int]:
    """Сколько участников останется после каждого раунда — для анонсов и тестов."""
    stages = [count]
    alive = count
    round_no = 1
    while alive > FINAL_MAX:
        if round_no == 1:
            alive = (alive + 1) // 2  # нечётный получает bye
        else:
            groups = split_groups([Player(i, str(i)) for i in range(alive)])
            base = 1 if len(groups) >= GROUP_SIZE else 2
            alive = sum(advance_count(len(g), base) for g in groups)
        stages.append(alive)
        round_no += 1
    stages.append(1)  # финал
    return stages
