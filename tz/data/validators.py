"""
Валидаторы идентификаторов для доски объявлений.

Все проверки работают локально, без обращения к внешним сервисам:
контрольные суммы математически заложены в сам идентификатор.

Проверено на эталонных значениях — см. блок самопроверки внизу файла.
"""

from __future__ import annotations

import re

# ─────────────────────────────────────────────────────────────
# VIN — идентификационный номер автомобиля (17 символов)
# ─────────────────────────────────────────────────────────────

# Буквы I, O, Q в VIN запрещены — их путают с 1 и 0
VIN_ALLOWED = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"

# Таблица транслитерации букв в числа для расчёта контрольной суммы
VIN_TRANSLIT = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "P": 7, "R": 9,
    "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9,
}

# Веса позиций. 9-я позиция (индекс 8) — сама контрольная цифра, вес 0
VIN_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]

# Код года выпуска — 10-й символ VIN. Цикл повторяется каждые 30 лет
VIN_YEAR_CODES = "ABCDEFGHJKLMNPRSTVWXY123456789"


def normalize_vin(raw: str) -> str:
    """Приводит VIN к каноническому виду: верхний регистр, без пробелов и дефисов."""
    return re.sub(r"[\s\-]", "", (raw or "")).upper()


def vin_check_digit(vin: str) -> str:
    """Вычисляет контрольный символ VIN (9-я позиция)."""
    total = 0
    for i, ch in enumerate(vin):
        value = VIN_TRANSLIT[ch] if ch in VIN_TRANSLIT else int(ch)
        total += value * VIN_WEIGHTS[i]
    remainder = total % 11
    return "X" if remainder == 10 else str(remainder)


def validate_vin(raw: str) -> dict:
    """
    Проверяет VIN и извлекает то, что закодировано в нём самом.

    Возвращает словарь с полями:
      valid        — прошёл ли все проверки
      error        — причина отказа, если не прошёл
      vin          — нормализованный VIN
      wmi          — код изготовителя (первые 3 символа)
      country_hint — страна сборки по первому символу
      year         — год выпуска, вычисленный из 10-го символа
      serial       — серийный номер кузова
    """
    vin = normalize_vin(raw)

    if len(vin) != 17:
        return {"valid": False, "error": "VIN должен содержать ровно 17 символов", "vin": vin}

    bad = [c for c in vin if c not in VIN_ALLOWED]
    if bad:
        return {
            "valid": False,
            "error": f"Недопустимые символы: {', '.join(sorted(set(bad)))}. "
                     f"Буквы I, O, Q в VIN не используются",
            "vin": vin,
        }

    expected = vin_check_digit(vin)
    if vin[8] != expected:
        return {
            "valid": False,
            "error": "Контрольная сумма не сошлась — вероятно, опечатка в номере",
            "vin": vin,
        }

    return {
        "valid": True,
        "error": None,
        "vin": vin,
        "wmi": vin[:3],
        "country_hint": vin_country(vin[0]),
        "year": vin_year(vin),
        "serial": vin[11:],
    }


def vin_country(first_char: str) -> str | None:
    """Определяет регион сборки по первому символу VIN."""
    ranges = [
        ("AH", "Африка"),
        ("JR", "Азия"),
        ("SZ", "Европа"),
        ("12345", "США"),
        ("6 7", "Океания"),
        ("89", "Южная Америка"),
    ]
    for chars, name in ranges:
        if len(chars) == 2 and chars[0].isalpha():
            if chars[0] <= first_char <= chars[1]:
                return name
        elif first_char in chars:
            return name
    return None


def vin_year(vin: str) -> int | None:
    """
    Вычисляет год выпуска по 10-му символу.

    Код повторяется каждые 30 лет, поэтому используется общепринятое
    правило различения: у легковых машин 7-я позиция — цифра для
    периода 1980–2009 и буква для 2010 и новее.
    """
    code = vin[9]
    if code not in VIN_YEAR_CODES:
        return None
    index = VIN_YEAR_CODES.index(code)
    base = 2010 if vin[6].isalpha() else 1980
    return base + index


# ─────────────────────────────────────────────────────────────
# IMEI — идентификатор мобильного устройства (15 цифр)
# ─────────────────────────────────────────────────────────────


def normalize_imei(raw: str) -> str:
    """Оставляет только цифры."""
    return re.sub(r"\D", "", raw or "")


def luhn_is_valid(digits: str) -> bool:
    """Проверка контрольной суммы по алгоритму Луна."""
    total = 0
    # Идём справа налево, удваивая каждую вторую цифру
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def validate_imei(raw: str) -> dict:
    """
    Проверяет IMEI.

    TAC — первые 8 цифр — однозначно определяют марку и модель устройства
    по справочнику Type Allocation Code.
    """
    imei = normalize_imei(raw)

    if len(imei) != 15:
        return {"valid": False, "error": "IMEI должен содержать ровно 15 цифр", "imei": imei}

    if not luhn_is_valid(imei):
        return {
            "valid": False,
            "error": "Контрольная сумма не сошлась — вероятно, опечатка в номере",
            "imei": imei,
        }

    return {
        "valid": True,
        "error": None,
        "imei": imei,
        "tac": imei[:8],
        "serial": imei[8:14],
    }


# ─────────────────────────────────────────────────────────────
# Артикул запчасти
# ─────────────────────────────────────────────────────────────


def normalize_part_number(raw: str) -> str:
    """
    Приводит артикул к виду, пригодному для точного поиска.

    Производители пишут один и тот же номер по-разному:
    MR-968455, mr 968455, MR968455 — это одна деталь.
    """
    return re.sub(r"[^A-Z0-9]", "", (raw or "").upper())


# ─────────────────────────────────────────────────────────────
# Самопроверка на эталонных значениях
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    checks: list[tuple[str, bool, bool]] = []

    def check(name: str, got: bool, want: bool) -> None:
        checks.append((name, got, want))

    # Эталонный VIN, используемый в стандартах как пример корректного
    r = validate_vin("1HGBH41JXMN109186")
    check("Эталонный VIN валиден", r["valid"], True)
    check("VIN: WMI распознан", r.get("wmi") == "1HG", True)

    # Тот же VIN с испорченной контрольной цифрой
    check("VIN с ошибкой отклонён", validate_vin("1HGBH41J1MN109186")["valid"], False)
    # Буква O недопустима
    check("VIN с буквой O отклонён", validate_vin("1HGBH41JXMN1O9186")["valid"], False)
    # Недостаточная длина
    check("Короткий VIN отклонён", validate_vin("1HGBH41JX")["valid"], False)
    # Нормализация: пробелы и дефисы не мешают
    check("VIN с дефисами принят", validate_vin("1HG-BH41JX MN109186")["valid"], True)

    # Эталонный IMEI из документации GSM
    check("Эталонный IMEI валиден", validate_imei("490154203237518")["valid"], True)
    check("IMEI: TAC выделен", validate_imei("490154203237518")["tac"] == "49015420", True)
    check("IMEI с ошибкой отклонён", validate_imei("490154203237519")["valid"], False)
    check("Короткий IMEI отклонён", validate_imei("49015420")["valid"], False)

    # Артикулы
    check(
        "Артикулы приводятся к одному виду",
        normalize_part_number("MR-968455") == normalize_part_number("mr 968455"),
        True,
    )

    failed = [c for c in checks if c[1] != c[2]]
    for name, got, want in checks:
        print(f"{'OK  ' if got == want else 'СБОЙ'} {name}")
    print()
    print(f"Пройдено {len(checks) - len(failed)} из {len(checks)}")
    if failed:
        raise SystemExit(1)
