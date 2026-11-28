"""Отчёт по ревизии в Excel: итог по сотрудникам и все записи."""

from __future__ import annotations

import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font

from . import db


def _local(iso: str | None) -> str:
    if not iso:
        return ""
    return datetime.fromisoformat(iso).astimezone().strftime("%d.%m.%Y %H:%M:%S")


def build_xlsx(conn) -> tuple[bytes, str]:
    summary = db.admin_summary(conn)
    rev = summary["revision"]
    bold = Font(bold=True)

    book = Workbook()
    people = book.active
    people.title = "Сотрудники"
    people.append([rev["title"]])
    people["A1"].font = Font(bold=True, size=14)
    people.append([])
    people.append(["Сотрудник", "Сканов", "Сумма", "Минусов", "Сумма минусов", "Отмен", "Последняя запись"])
    for cell in people[3]:
        cell.font = bold
    for u in summary["users"]:
        people.append([u["name"], u["scans"], u["sum"], u["minuses"], u["minus_sum"], u["voids"], _local(u["last_at"])])
    people.append([])
    people.append(["ИТОГО", summary["scans"], summary["sum"], "", summary["minus_sum"]])
    for cell in people[people.max_row]:
        cell.font = bold
    for col, width in zip("ABCDEFG", (26, 10, 14, 10, 16, 8, 22)):
        people.column_dimensions[col].width = width

    rows = book.create_sheet("Записи")
    rows.append(["№", "Время", "Сотрудник", "Сумма", "Читал, сек", "Отменено"])
    for cell in rows[1]:
        cell.font = bold
    for e in db.all_entries(conn, rev["id"]):
        rows.append([e["id"], _local(e["created_at"]), e["name"], e["amt"], e["sec"], "да" if e["voided"] else ""])
    for col, width in zip("ABCDEF", (8, 22, 26, 12, 12, 10)):
        rows.column_dimensions[col].width = width

    buf = io.BytesIO()
    book.save(buf)
    filename = "reviziya-" + datetime.now().strftime("%Y-%m-%d-%H%M") + ".xlsx"
    return buf.getvalue(), filename
