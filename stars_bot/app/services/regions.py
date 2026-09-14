"""Регионы игровых аккаунтов.

Один и тот же Free Fire у поставщика разложен по регионам: СНГ, Индонезия,
Бразилия и так далее. Это не мелочь оформления — сервер аккаунта решает,
найдётся ли игрок по ID и куда уйдут алмазы. Промахнулись регионом —
проверка ника не находит игрока, а заказ либо отклоняется, либо уходит
чужому человеку.

У поставщика регион зашит в код категории хвостом: free_fire_br,
free_fire_id, free_fire_cis. Отсюда правило: код = семья + регион.
Семья («free_fire») — то, что клиент выбирает первым шагом, регион —
вторым.
"""
from __future__ import annotations

#: Хвост кода → (как показать клиенту, код региона для поиска ников).
#: Порядок важен: первым идёт то, что чаще спрашивают в Душанбе.
REGIONS: dict[str, tuple[str, str]] = {
    "cis": ("🌍 СНГ", "RU"),
    "ru": ("🌍 СНГ", "RU"),
    "id": ("🇮🇩 Индонезия", "ID"),
    "br": ("🇧🇷 Бразилия", "BR"),
    "global": ("🌐 Глобальный", ""),
    "eu": ("🇪🇺 Европа", "EU"),
    "na": ("🌎 Северная Америка", "NA"),
    "sac": ("🌎 Южная Америка", "SAC"),
    "mena": ("🕌 Ближний Восток", "ME"),
    "me": ("🕌 Ближний Восток", "ME"),
    "ind": ("🇮🇳 Индия", "IND"),
    "in": ("🇮🇳 Индия", "IND"),
    "pk": ("🇵🇰 Пакистан", "PK"),
    "bd": ("🇧🇩 Бангладеш", "BD"),
    "th": ("🇹🇭 Таиланд", "TH"),
    "vn": ("🇻🇳 Вьетнам", "VN"),
    "ph": ("🇵🇭 Филиппины", "PH"),
    "sg": ("🇸🇬 Сингапур", "SG"),
    "my": ("🇲🇾 Малайзия", "SG"),
    "tw": ("🇹🇼 Тайвань", "TW"),
    "tr": ("🇹🇷 Турция", "TR"),
    "ua": ("🇺🇦 Украина", "RU"),
}

#: Порядок кнопок на экране выбора региона: сперва те, что нужны нам.
ORDER = ["cis", "ru", "id", "br"]


def split(category_id: str) -> tuple[str, str]:
    """Код категории → (семья, хвост региона).

    Хвост признаётся регионом, только если он есть в справочнике, — иначе
    pubg_mobile превратился бы в семью «pubg» с «регионом» mobile.
    """
    code = (category_id or "").strip().lower()
    head, _, tail = code.rpartition("_")
    if head and tail in REGIONS:
        return head, tail
    return code, ""


def family_of(category_id: str) -> str:
    return split(category_id)[0]


def suffix_of(category_id: str) -> str:
    return split(category_id)[1]


def title_of(category_id: str) -> str:
    """Как назвать регион на кнопке. Пусто — регион не распознан."""
    tail = suffix_of(category_id)
    return REGIONS[tail][0] if tail else ""


def nick_region(category_id: str) -> str:
    """Код региона для сервиса ников."""
    tail = suffix_of(category_id)
    return REGIONS[tail][1] if tail else ""


def sort_key(category_id: str) -> tuple[int, str]:
    """Сортировка регионов: сначала нужные нам, потом остальные по алфавиту."""
    tail = suffix_of(category_id)
    return (ORDER.index(tail) if tail in ORDER else len(ORDER), tail or category_id)


def group(games: list) -> list[dict]:
    """Сгруппировать игры по семьям, сохранив порядок появления.

    Клиент не должен видеть три «Free Fire» подряд: он выбирает игру,
    а регион — следующим шагом.
    """
    out: dict[str, dict] = {}
    for game in games:
        family = family_of(game.category_id)
        holder = out.setdefault(
            family, {"family": family, "title": game.title, "games": []}
        )
        holder["games"].append(game)
    for holder in out.values():
        holder["games"].sort(key=lambda g: sort_key(g.category_id))
    return list(out.values())


def region_title(game) -> str:
    """Подпись региона для кнопки: из справочника, иначе название игры."""
    return title_of(game.category_id) or game.title
