"""Разбор чисел из речи и текста: русский и узбекский, слова и цифры.

Здесь нет нейросетей. Только словарь числительных и правила, поэтому
результат всегда одинаковый и его можно проверить тестами.

Числа храним в сотых (как копейки), чтобы «7600,5» не превращалось
в неточное дробное число.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SCALE = 100  # одна единица = 100 сотых

# ── Словари числительных ───────────────────────────────────────────────────
# «Простые» слова — те, что складываются: сто двадцать три = 100 + 20 + 3.
RU_PLAIN: dict[str, int] = {
    "ноль": 0, "нуль": 0,
    "один": 1, "одна": 1, "одно": 1, "адин": 1,
    "два": 2, "две": 2, "двух": 2,
    "три": 3, "трех": 3,
    "четыре": 4, "четырех": 4,
    "пять": 5, "пяти": 5,
    "шесть": 6, "шести": 6,
    "семь": 7, "семи": 7,
    "восемь": 8, "восьми": 8,
    "девять": 9, "девяти": 9,
    "десять": 10, "десяти": 10,
    "одиннадцать": 11, "двенадцать": 12, "тринадцать": 13, "четырнадцать": 14,
    "пятнадцать": 15, "шестнадцать": 16, "семнадцать": 17, "восемнадцать": 18,
    "девятнадцать": 19,
    "двадцать": 20, "тридцать": 30, "сорок": 40, "пятьдесят": 50,
    "шестьдесят": 60, "семьдесят": 70, "восемьдесят": 80, "девяносто": 90,
    "сто": 100, "ста": 100,
    "двести": 200, "двухсот": 200,
    "триста": 300, "трехсот": 300,
    "четыреста": 400, "четырехсот": 400,
    "пятьсот": 500, "пятисот": 500,
    "шестьсот": 600, "шестисот": 600,
    "семьсот": 700, "семисот": 700,
    "восемьсот": 800, "восьмисот": 800,
    "девятьсот": 900, "девятисот": 900,
}
RU_MULT: dict[str, int] = {
    "тысяча": 1000, "тысячи": 1000, "тысяч": 1000, "тысячу": 1000,
    "тыща": 1000, "тыщи": 1000, "тыщ": 1000,
    "миллион": 1_000_000, "миллиона": 1_000_000, "миллионов": 1_000_000,
    "лям": 1_000_000, "ляма": 1_000_000,
}

# Узбекский. Апострофы в o‘n / to‘rt заранее убираются, поэтому пишем без них.
UZ_PLAIN: dict[str, int] = {
    "nol": 0,
    "bir": 1, "ikki": 2, "uch": 3, "tort": 4, "besh": 5,
    "olti": 6, "yetti": 7, "etti": 7, "sakkiz": 8, "toqqiz": 9,
    "on": 10, "yigirma": 20, "ottiz": 30, "qirq": 40, "ellik": 50,
    "oltmish": 60, "yetmish": 70, "sakson": 80, "toqson": 90,
}
UZ_MULT: dict[str, int] = {
    "yuz": 100, "ming": 1000, "million": 1_000_000, "mln": 1_000_000,
}

PLAIN: dict[str, int] = {**RU_PLAIN, **UZ_PLAIN}
MULT: dict[str, int] = {**RU_MULT, **UZ_MULT}

# Слова-связки: не число, но и не конец числа («семь тысяч и шестьсот»).
FILLER: frozenset[str] = frozenset({"и", "да", "va", "yana", "ва"})

# Все слова, которые бот вообще готов услышать. Отдаём их в Vosk как
# словарь — тогда он не пытается расслышать посторонние слова.
VOCABULARY: tuple[str, ...] = tuple(sorted(set(PLAIN) | set(MULT) | set(FILLER)))

_APOSTROPHES = "'‘’ʻʼ`´"
_DIGIT_TOKEN = re.compile(r"\d+(?:\.\d+)?$")


@dataclass(frozen=True)
class Found:
    """Найденное число: значение в сотых и кусок текста, откуда оно взято."""

    value: int
    text: str

    @property
    def units(self) -> float:
        return self.value / SCALE


# ── Нормализация текста ────────────────────────────────────────────────────
def normalize(text: str) -> str:
    """Привести текст к виду, удобному для разбора."""
    low = (text or "").lower().replace("ё", "е")
    for ch in _APOSTROPHES:
        low = low.replace(ch, "")
    # «7,5» → «7.5», но запятая между словами остаётся разделителем
    low = re.sub(r"(?<=\d),(?=\d)", ".", low)
    # «7 600» и «7 600» (неразрывный пробел) → «7600»
    prev = None
    while prev != low:
        prev = low
        low = re.sub(r"(?<=\d)[   '](?=\d{3}(?!\d))", "", low)
    # всё, что не буква/цифра/точка/минус — разделитель
    low = re.sub(r"[^\w\d.\-]+", " ", low, flags=re.UNICODE)
    low = re.sub(r"(?<!\d)\.(?!\d)", " ", low)  # точка не между цифрами — мусор
    return re.sub(r"\s+", " ", low).strip()


# ── Разбор ─────────────────────────────────────────────────────────────────
def _magnitude(value: int) -> int:
    if value < 10:
        return 1
    if value < 100:
        return 2
    return 3


def _evaluate(tokens: list[tuple[int, str]]) -> int:
    """Сложить группу числительных: (значение, вид) → число."""
    total = 0
    current = 0
    for value, kind in tokens:
        if kind == "mult":
            current = (current or 1) * value
            if value >= 1000:
                total += current
                current = 0
        else:
            current += value
    return total + current


def _has_thousand(tokens: list[tuple[int, str]]) -> bool:
    return any(kind == "mult" and value >= 1000 for value, kind in tokens)


def parse_numbers(text: str) -> list[Found]:
    """Вытащить из текста все числа. Буквы, кроме числительных, игнорируются."""
    words = normalize(text).split()

    groups: list[dict] = []
    current: dict | None = None
    last_magnitude: int | None = None

    def close() -> None:
        """Закончить текущее число."""
        nonlocal current, last_magnitude
        if current and current["tokens"]:
            groups.append(current)
        current = None
        last_magnitude = None

    for word in words:
        negative = word.startswith("-")
        bare = word.lstrip("-")

        if _DIGIT_TOKEN.match(bare):
            # Цифры всегда самостоятельное число.
            close()
            value = int(round(float(bare) * SCALE))
            groups.append(
                {
                    "tokens": [],
                    "value": -value if negative else value,
                    "words": [word],
                    "glued": True,
                }
            )
            continue

        if bare in FILLER:
            continue

        if bare in MULT:
            if current is None:
                current = {"tokens": [], "words": [], "glued": False}
            current["tokens"].append((MULT[bare], "mult"))
            current["words"].append(bare)
            # После «тысяча» снова можно называть сотни и десятки.
            last_magnitude = None if MULT[bare] >= 1000 else _magnitude(MULT[bare])
            continue

        if bare in PLAIN:
            value = PLAIN[bare]
            magnitude = _magnitude(value)
            if current is not None and last_magnitude is not None and magnitude >= last_magnitude:
                # Разряд не уменьшился («семь шестьсот») — это уже новое число,
                # но соседнее: ниже попробуем склеить такие в тысячи.
                close()
                current = {"tokens": [], "words": [], "glued": True}
            elif current is None:
                current = {"tokens": [], "words": [], "glued": False}
            current["tokens"].append((value, "plain"))
            current["words"].append(bare)
            last_magnitude = magnitude
            continue

        # Незнакомое слово — конец числа.
        close()

    close()

    for group in groups:
        if "value" not in group:
            group["value"] = _evaluate(group["tokens"]) * SCALE

    return _glue_thousands(groups)


def _glue_thousands(groups: list[dict]) -> list[Found]:
    """«семь шестьсот» → 7600, «yetti olti yuz» → 7600.

    Так говорят вслух, когда лень выговаривать «тысяч». Склеиваем только
    соседние числа: единица 1–9 и сразу за ней сотни 100–999.
    """
    out: list[Found] = []
    index = 0
    while index < len(groups):
        group = groups[index]
        following = groups[index + 1] if index + 1 < len(groups) else None
        if (
            following is not None
            and following.get("glued")
            and SCALE <= group["value"] <= 9 * SCALE
            and group["value"] % SCALE == 0
            and 100 * SCALE <= following["value"] <= 999 * SCALE
            and not _has_thousand(group.get("tokens") or [])
            and not _has_thousand(following.get("tokens") or [])
        ):
            value = group["value"] * 1000 + following["value"]
            words = " ".join(group["words"] + following["words"])
            out.append(Found(value=value, text=words))
            index += 2
            continue
        out.append(Found(value=group["value"], text=" ".join(group["words"])))
        index += 1
    return out


def parse_single(text: str) -> int | None:
    """Ровно одно число в тексте — вернуть его, иначе None."""
    found = parse_numbers(text)
    return found[0].value if len(found) == 1 else None


# ── Показ чисел человеку ───────────────────────────────────────────────────
def format_amount(value: int) -> str:
    """7600 сотых → «76», 760000 → «7 600», 760050 → «7 600,5»."""
    sign = "-" if value < 0 else ""
    value = abs(value)
    whole, rest = divmod(value, SCALE)
    text = f"{whole:,}".replace(",", " ")
    if rest:
        text += "," + f"{rest:02d}".rstrip("0")
    return sign + text
