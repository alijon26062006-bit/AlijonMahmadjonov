"""Разовый импорт открытого списка TAC → модель устройства.

    python -m app.seed.import_tac tac.csv

Файл — CSV с заголовком. Названия колонок распознаются свободно, лишь бы
в них встречались слова tac, brand (или manufacturer/vendor) и model:

    tac,brand,model
    35123456,Samsung,Galaxy A54

Записи ложатся с пометкой «import» — своим наблюдениям площадка их не
перезаписывает. Повторный запуск обновляет, а не плодит дубликаты.

Готовых списков в проекте нет намеренно: выдуманная таблица показывала бы
людям чужую модель телефона, а это хуже, чем не показывать ничего.
Официальный реестр — у GSMA (платный, по договору с оператором); открытые
выгрузки TAC лежат на GitHub, качество у них разное, поэтому выбор источника
остаётся за владельцем площадки.
"""
import asyncio
import csv
import sys
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.base import SessionMaker
from app.db.models import TacModel


def _pick(fieldnames: list[str], *words: str) -> str | None:
    for name in fieldnames:
        low = name.strip().lower()
        if any(w in low for w in words):
            return name
    return None


async def run(path: Path) -> int:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        names = reader.fieldnames or []
        col_tac = _pick(names, "tac")
        col_brand = _pick(names, "brand", "manufacturer", "vendor", "make")
        col_model = _pick(names, "model", "name", "device")
        if not (col_tac and col_brand and col_model):
            print(f"Не нашёл нужные колонки. В файле: {names}")
            print("Ожидаются столбцы со словами tac, brand и model.")
            return 0

        rows, skipped = [], 0
        for row in reader:
            tac = "".join(ch for ch in (row.get(col_tac) or "") if ch.isdigit())
            brand = (row.get(col_brand) or "").strip()[:60]
            model = (row.get(col_model) or "").strip()[:120]
            if len(tac) != 8 or not brand or not model:
                skipped += 1
                continue
            rows.append({"tac": tac, "brand": brand, "model": model,
                         "source": "import", "confirmations": 1})

    if not rows:
        print("Подходящих строк не нашлось")
        return 0

    # дубликаты внутри файла: побеждает последняя строка
    uniq = {r["tac"]: r for r in rows}
    async with SessionMaker() as session:
        batch = list(uniq.values())
        for i in range(0, len(batch), 1000):
            chunk = batch[i:i + 1000]
            stmt = pg_insert(TacModel).values(chunk)
            await session.execute(stmt.on_conflict_do_update(
                index_elements=[TacModel.tac],
                set_={"brand": stmt.excluded.brand,
                      "model": stmt.excluded.model,
                      "source": "import",
                      "confirmations": 1}))
        await session.commit()

    print(f"Загружено моделей: {len(uniq)}"
          + (f", пропущено строк: {skipped}" if skipped else ""))
    return len(uniq)


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Файл не найден: {path}")
        raise SystemExit(2)
    asyncio.run(run(path))


if __name__ == "__main__":
    main()
