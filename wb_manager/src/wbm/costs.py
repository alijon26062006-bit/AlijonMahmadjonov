"""Файл себестоимости от продавца: CSV или Excel, две колонки — артикул и себестоимость.

Понимаем: разделители «;», «,», табуляцию; заголовок есть или нет; запятую или точку
в дробной части; пробелы между разрядами («1 250,50»), знак ₽.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from wbm.domain.data import normalize_vendor_code

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_ROWS = 100_000
MAX_COST = Decimal("10000000")

_HEADER_WORDS = ("артикул", "vendor", "sku", "код", "себестоим", "цена", "cost")


class CostFileError(ValueError):
    """Файл не прочитать целиком (не тот формат, пусто, слишком большой)."""


@dataclass(slots=True)
class CostFile:
    prices: dict[str, Decimal] = field(default_factory=dict)
    """Артикул (в нижнем регистре) → себестоимость."""
    errors: list[str] = field(default_factory=list)
    """Строки, которые пропустили, — чтобы показать продавцу."""


def parse_cost_file(filename: str, content: bytes) -> CostFile:
    if len(content) > MAX_FILE_BYTES:
        raise CostFileError("Файл больше 5 МБ")
    if not content:
        raise CostFileError("Файл пустой")
    name = filename.lower()
    if name.endswith((".xlsx", ".xlsm")):
        rows = _xlsx_rows(content)
    elif name.endswith((".csv", ".txt")):
        rows = _csv_rows(content)
    else:
        raise CostFileError("Нужен файл .xlsx или .csv")
    return _parse_rows(rows)


def _csv_rows(content: bytes) -> list[list[str]]:
    for encoding in ("utf-8-sig", "cp1251"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise CostFileError("Не удалось прочитать кодировку файла (нужна UTF-8 или Windows-1251)")
    sample = text[:4096]
    delimiter = max((";", "\t", ","), key=sample.count)
    return list(csv.reader(io.StringIO(text), delimiter=delimiter))


def _xlsx_rows(content: bytes) -> list[list[str]]:
    from openpyxl import load_workbook  # тяжёлый импорт — только когда нужен

    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise CostFileError("Не удалось открыть Excel-файл") from exc
    try:
        sheet = workbook.worksheets[0]
        rows: list[list[str]] = []
        for row in sheet.iter_rows(values_only=True):
            rows.append(["" if cell is None else str(cell) for cell in row])
            if len(rows) > MAX_ROWS + 1:
                break
        return rows
    finally:
        workbook.close()


def _parse_rows(rows: list[list[str]]) -> CostFile:
    rows = [row for row in rows if any(cell.strip() for cell in row)]
    if not rows:
        raise CostFileError("В файле нет строк")
    if len(rows) > MAX_ROWS + 1:
        raise CostFileError(f"Слишком много строк (больше {MAX_ROWS})")
    if _is_header(rows[0]):
        rows = rows[1:]

    result = CostFile()
    for number, row in enumerate(rows, start=1):
        cells = [cell.strip() for cell in row if cell.strip()]
        if len(cells) < 2:
            result.errors.append(f"строка {number}: нужны артикул и себестоимость")
            continue
        vendor_code, raw_cost = cells[0], cells[1]
        cost = _parse_money(raw_cost)
        if cost is None:
            result.errors.append(f"строка {number}: «{raw_cost[:30]}» — не число")
            continue
        if cost <= 0 or cost > MAX_COST:
            result.errors.append(f"строка {number}: себестоимость должна быть больше нуля")
            continue
        key = normalize_vendor_code(vendor_code)[:100]
        if key in result.prices:
            result.errors.append(f"строка {number}: артикул «{vendor_code[:30]}» повторяется")
        result.prices[key] = cost
    if not result.prices:
        raise CostFileError("Не нашли ни одной строки «артикул; себестоимость»")
    return result


def _is_header(row: list[str]) -> bool:
    text = " ".join(row).lower()
    return any(word in text for word in _HEADER_WORDS) and _parse_money(row[-1]) is None


def _parse_money(raw: str) -> Decimal | None:
    cleaned = re.sub(r"[\s ₽руб.р]+$", "", raw.strip().lower())
    cleaned = re.sub(r"[\s ]", "", cleaned).replace(",", ".")
    if not re.fullmatch(r"-?\d+(\.\d+)?", cleaned):
        return None
    try:
        return Decimal(cleaned).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
