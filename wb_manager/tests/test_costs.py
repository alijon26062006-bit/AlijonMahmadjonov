from __future__ import annotations

import io
from decimal import Decimal

import pytest
from openpyxl import Workbook

from wbm.costs import CostFileError, parse_cost_file


def test_csv_with_header_semicolon_and_comma_decimals() -> None:
    content = "Артикул;Себестоимость\nPLATYE-01;850\nBRUKI-2; 1 250,50 ₽\n\n".encode()

    result = parse_cost_file("costs.csv", content)

    assert result.prices == {"platye-01": Decimal("850.00"), "bruki-2": Decimal("1250.50")}
    assert result.errors == []


def test_csv_without_header_comma_separator_cp1251() -> None:
    content = "АРТ-1,100.5\nАРТ-2,200\n".encode("cp1251")

    result = parse_cost_file("c.csv", content)

    assert result.prices == {"арт-1": Decimal("100.50"), "арт-2": Decimal("200.00")}


def test_bad_rows_are_reported_not_fatal() -> None:
    content = "A;100\nB;сто\nC;-5\nA;120\nD\n".encode()

    result = parse_cost_file("c.csv", content)

    assert result.prices == {"a": Decimal("120.00")}
    assert len(result.errors) == 4
    assert "не число" in result.errors[0]


def test_xlsx() -> None:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["артикул", "себестоимость"])
    sheet.append(["SKU-1", 99.9])
    sheet.append(["SKU-2", 1500])
    buffer = io.BytesIO()
    workbook.save(buffer)

    result = parse_cost_file("Себестоимость.xlsx", buffer.getvalue())

    assert result.prices == {"sku-1": Decimal("99.90"), "sku-2": Decimal("1500.00")}


@pytest.mark.parametrize(
    ("name", "content", "message"),
    [
        ("c.csv", b"", "пустой"),
        ("c.pdf", b"x", ".xlsx"),
        ("c.csv", "только;заголовок\n".encode(), "Не нашли"),
        ("c.xlsx", b"not excel", "Excel"),
        ("c.csv", b"a;1\n" * 2_000_000, "5 МБ"),
    ],
)
def test_unreadable_files(name: str, content: bytes, message: str) -> None:
    with pytest.raises(CostFileError, match=message):
        parse_cost_file(name, content)
