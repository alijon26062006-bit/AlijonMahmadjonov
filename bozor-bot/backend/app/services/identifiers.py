"""Проверка идентификаторов: VIN, номер кузова, IMEI, артикул, серийник.

Все проверки локальные — контрольные суммы заложены в сам номер.
Возврат: (ok, normalized, error, autofill) — autofill подставляется в мастер.
"""
import json
import re
from pathlib import Path

_VIN_ALLOWED = set("ABCDEFGHJKLMNPRSTUVWXYZ0123456789")
_VIN_TRANSLIT = {
    "A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8,
    "J": 1, "K": 2, "L": 3, "M": 4, "N": 5, "P": 7, "R": 9,
    "S": 2, "T": 3, "U": 4, "V": 5, "W": 6, "X": 7, "Y": 8, "Z": 9,
}
_VIN_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]
_VIN_YEARS = "ABCDEFGHJKLMNPRSTVWXY123456789"
_FRAME_RE = re.compile(r"^[A-Z]{2,4}[0-9]{2,3}-?[0-9]{6,7}$")

_data = Path(__file__).resolve().parent.parent / "seed" / "data" / "vin_wmi.json"
_WMI: dict[str, str] = json.loads(_data.read_text(encoding="utf-8"))["wmi"]


def norm(raw: str) -> str:
    return re.sub(r"[\s\-]", "", (raw or "")).upper()


def norm_part(raw: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (raw or "").upper())


def _vin_check(vin: str) -> str:
    total = sum((_VIN_TRANSLIT[c] if c in _VIN_TRANSLIT else int(c)) * _VIN_WEIGHTS[i]
                for i, c in enumerate(vin))
    r = total % 11
    return "X" if r == 10 else str(r)


def _vin_year(vin: str) -> int | None:
    code = vin[9]
    if code not in _VIN_YEARS:
        return None
    base = 2010 if vin[6].isalpha() else 1980
    return base + _VIN_YEARS.index(code)


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
    return total % 10 == 0


def validate(kind: str, raw: str) -> tuple[bool, str, str | None, dict]:
    """kind: vin | vin_or_frame | imei | part_number | serial"""
    if kind in ("vin", "vin_or_frame"):
        v = norm(raw)
        if len(v) == 17 and set(v) <= _VIN_ALLOWED:
            if v[8] != _vin_check(v):
                return False, v, "Контрольная сумма VIN не сошлась — проверьте номер", {}
            auto: dict = {}
            if (year := _vin_year(v)):
                auto["year"] = year
            if (maker := _WMI.get(v[:3]) or _WMI.get(v[:2])):
                auto["brand_hint"] = maker
            return True, v, None, auto
        if kind == "vin_or_frame" and _FRAME_RE.match(v):
            return True, v, None, {}
        if len(v) == 17:
            bad = sorted(set(v) - _VIN_ALLOWED)
            return False, v, f"Недопустимые символы: {', '.join(bad)}. Буквы I, O, Q в VIN не используются", {}
        return False, v, "VIN — 17 символов, номер кузова — вида ACV30-1234567", {}

    if kind == "imei":
        d = re.sub(r"\D", "", raw or "")
        if len(d) != 15:
            return False, d, "IMEI — ровно 15 цифр (наберите *#06#)", {}
        if not _luhn(d):
            return False, d, "Контрольная сумма IMEI не сошлась — проверьте номер", {}
        return True, d, None, {"tac": d[:8]}

    if kind == "part_number":
        p = norm_part(raw)
        if len(p) < 2:
            return False, p, "Слишком короткий артикул", {}
        return True, p, None, {}

    # serial и всё остальное — только нормализация
    s = norm_part(raw)
    if len(s) < 3:
        return False, s, "Слишком короткий номер", {}
    return True, s, None, {}
