#!/usr/bin/env python3
"""Разложить фотографии блюд по местам.

Картинки лежат в интернете, список — в photos.json рядом. Скрипт скачивает
каждую, кладёт в uploads/ и прописывает блюду в базе. Запускать на сервере:

    .venv/bin/python photos.py            — скачать те, у которых фото ещё нет
    .venv/bin/python photos.py --force    — перекачать всё заново
    .venv/bin/python photos.py --clear    — убрать фото у всех блюд

Скрипт можно запускать сколько угодно раз: уже скачанное он не трогает.
Фото, загруженные вручную через админку, остаются на месте — если не --force.
"""

import json
import sys
from pathlib import Path

import httpx

try:
    from . import db
except ImportError:
    import db

HERE = Path(__file__).parent
UPLOADS = HERE / 'uploads'
LIST = HERE / 'photos.json'

MAX_BYTES = 8 * 1024 * 1024
MAGIC = ((b'\xff\xd8\xff', '.jpg'), (b'\x89PNG\r\n\x1a\n', '.png'))


def kind_of(body):
    for head, ext in MAGIC:
        if body.startswith(head):
            return ext
    if body[:4] == b'RIFF' and body[8:12] == b'WEBP':
        return '.webp'
    return None


def fetch(url):
    """Скачиваем и убеждаемся, что это правда картинка, а не страница с ошибкой."""
    r = httpx.get(url, timeout=60, follow_redirects=True)
    r.raise_for_status()
    body = r.content
    if len(body) > MAX_BYTES:
        raise ValueError('файл больше 8 МБ')
    ext = kind_of(body)
    if not ext:
        raise ValueError('это не картинка')
    return body, ext


def main():
    force = '--force' in sys.argv
    clear = '--clear' in sys.argv

    db.setup()
    UPLOADS.mkdir(exist_ok=True)

    if clear:
        gone = 0
        for d in db.dishes(only_active=False):
            if d['photo']:
                db.set_dish_photo(d['id'], '')
                gone += 1
        print(f'Фото убраны у {gone} блюд.')
        return

    if not LIST.exists():
        sys.exit(f'Нет файла {LIST.name} — положите его рядом со скриптом')

    plan = json.loads(LIST.read_text(encoding='utf-8'))
    known = {d['id']: d for d in db.dishes(only_active=False)}
    if not known:
        sys.exit('В базе нет ни одного блюда. Сначала запустите сервер — '
                 'он наполнит базу меню, потом повторите.')

    added = skipped = missing = failed = 0
    for dish_id, url in plan.items():
        d = known.get(dish_id)
        if not d:
            print(f'  · {dish_id}: такого блюда нет в базе, пропускаю')
            missing += 1
            continue

        if d['photo'] and not force:
            skipped += 1
            continue

        try:
            body, ext = fetch(url)
        except Exception as e:
            print(f'  ! {dish_id}: {e}')
            failed += 1
            continue

        name = f'{dish_id}{ext}'
        (UPLOADS / name).write_bytes(body)
        db.set_dish_photo(dish_id, name)
        print(f'  + {dish_id} → {name} ({len(body) // 1024} КБ)')
        added += 1

    print(f'\nГотово. Добавлено: {added}, уже было: {skipped}, '
          f'не нашлось блюд: {missing}, не скачалось: {failed}')
    if added:
        print('Обновите страницу меню — фотографии уже на месте.')


if __name__ == '__main__':
    main()
