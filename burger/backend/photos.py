#!/usr/bin/env python3
"""Разложить фотографии блюд по местам.

Картинки лежат в интернете, список — в photos.json рядом. Скрипт скачивает
каждую, кладёт в uploads/ и прописывает блюду в базе. Запускать на сервере:

    .venv/bin/python photos.py             — скачать те, у которых фото ещё нет
    .venv/bin/python photos.py --force     — перекачать всё заново
    .venv/bin/python photos.py --optimize  — ужать те, что уже лежат
    .venv/bin/python photos.py --clear     — убрать фото у всех блюд

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

MAX_BYTES = 12 * 1024 * 1024
MAGIC = ((b'\xff\xd8\xff', '.jpg'), (b'\x89PNG\r\n\x1a\n', '.png'))

# Карточка блюда на телефоне — это 200 точек шириной, на большом экране 600.
# Держать ради неё двухмегабайтный PNG нельзя: в Душанбе мобильный интернет,
# и меню из 94 таких картинок не откроется никогда.
WIDTH = 900
QUALITY = 78

# Какой формат легче — заранее не известно. На гладком снимке еды WebP
# выигрывает у JPEG больше половины веса, а на пёстром, с крупой и зеленью,
# наоборот проигрывает. Поэтому жмём обоими и оставляем тот, что меньше:
# лишняя секунда на сервере против лишних килобайт у каждого клиента.


def kind_of(body):
    for head, ext in MAGIC:
        if body.startswith(head):
            return ext
    if body[:4] == b'RIFF' and body[8:12] == b'WEBP':
        return '.webp'
    return None


def shrink(body):
    """Ужать до разумного размера. Нет Pillow — сохраняем как есть."""
    try:
        import io

        from PIL import Image
    except ImportError:
        return body, kind_of(body), False

    try:
        img = Image.open(io.BytesIO(body))
        img = img.convert('RGB')
        if img.width > WIDTH:
            height = round(img.height * WIDTH / img.width)
            img = img.resize((WIDTH, height), Image.LANCZOS)
    except Exception:
        return body, kind_of(body), False

    tries = []
    for kind, ext, extra in (
            ('WEBP', '.webp', dict(method=6)),
            ('JPEG', '.jpg', dict(optimize=True, progressive=True))):
        try:
            out = io.BytesIO()
            img.save(out, kind, quality=QUALITY, **extra)
            tries.append((len(out.getvalue()), out.getvalue(), ext))
        except Exception:
            continue

    if not tries:
        return body, kind_of(body), False

    _, best, ext = min(tries, key=lambda t: t[0])
    return best, ext, True


def fetch(url):
    """Скачиваем и убеждаемся, что это правда картинка, а не страница с ошибкой."""
    r = httpx.get(url, timeout=60, follow_redirects=True)
    r.raise_for_status()
    body = r.content
    if len(body) > MAX_BYTES:
        raise ValueError('файл слишком большой')
    if not kind_of(body):
        raise ValueError('это не картинка')

    was = len(body)
    body, ext, squeezed = shrink(body)
    return body, ext, was, squeezed


def squeeze_existing():
    """Ужать фотографии, которые уже лежат в uploads — в том числе те,
    что загрузили руками через админку прямо с телефона."""
    db.setup()
    saved = 0
    for d in db.dishes(only_active=False):
        if not d['photo']:
            continue
        path = UPLOADS / d['photo']
        if not path.is_file():
            continue

        was = path.stat().st_size
        body, ext, squeezed = shrink(path.read_bytes())
        if not squeezed or len(body) >= was:
            continue

        name = f"{d['id']}{ext}"
        (UPLOADS / name).write_bytes(body)
        if name != d['photo']:
            path.unlink(missing_ok=True)
            db.set_dish_photo(d['id'], name)
        print(f"  ~ {d['id']}: {was // 1024} КБ → {len(body) // 1024} КБ")
        saved += was - len(body)

    print(f'\nСэкономлено {saved // 1024} КБ на каждой загрузке меню.')


def main():
    force = '--force' in sys.argv
    clear = '--clear' in sys.argv
    only_squeeze = '--optimize' in sys.argv

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

    if only_squeeze:
        squeeze_existing()
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
            body, ext, was, squeezed = fetch(url)
        except Exception as e:
            print(f'  ! {dish_id}: {e}')
            failed += 1
            continue

        name = f'{dish_id}{ext}'
        for old_file in UPLOADS.glob(f'{dish_id}.*'):    # старое фото того же блюда
            if old_file.name != name:
                old_file.unlink(missing_ok=True)
        (UPLOADS / name).write_bytes(body)
        db.set_dish_photo(dish_id, name)

        size = f'{len(body) // 1024} КБ'
        if squeezed and was > len(body):
            size += f' (было {was // 1024})'
        print(f'  + {dish_id} → {name} ({size})')
        added += 1

    print(f'\nГотово. Добавлено: {added}, уже было: {skipped}, '
          f'не нашлось блюд: {missing}, не скачалось: {failed}')
    if added:
        print('Обновите страницу меню — фотографии уже на месте.')


if __name__ == '__main__':
    main()
