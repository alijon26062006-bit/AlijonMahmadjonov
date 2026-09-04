"""База сайта: меню, настройки и заказы. SQLite — файл рядом с приложением.

Цены и суммы считаются здесь, на сервере. Данные из браузера для этого
не используются: их можно подделать.
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / 'data' / 'burger.db'

SCHEMA = """
CREATE TABLE IF NOT EXISTS sections (
    id       TEXT PRIMARY KEY,
    title    TEXT NOT NULL,
    note     TEXT NOT NULL DEFAULT '',
    layout   TEXT NOT NULL DEFAULT 'cards',   -- cards | rows
    position INTEGER NOT NULL DEFAULT 0,
    show_from TEXT NOT NULL DEFAULT '',       -- окно, когда раздел идёт первым
    show_to   TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS dishes (
    id        TEXT PRIMARY KEY,
    section   TEXT NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    name      TEXT NOT NULL,
    about     TEXT NOT NULL DEFAULT '',
    weight    INTEGER NOT NULL DEFAULT 0,
    kcal      INTEGER NOT NULL DEFAULT 0,
    cook      TEXT NOT NULL DEFAULT '',
    price     INTEGER NOT NULL,
    old_price INTEGER,
    tag       TEXT NOT NULL DEFAULT '',
    parts     TEXT NOT NULL DEFAULT '[]',     -- JSON-список состава
    photo     TEXT NOT NULL DEFAULT '',
    active    INTEGER NOT NULL DEFAULT 1,     -- 0 = временно нет в наличии
    position  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS addons (
    id       TEXT PRIMARY KEY,
    section  TEXT NOT NULL DEFAULT '',        -- к какому разделу предлагать
    name     TEXT NOT NULL,
    price    INTEGER NOT NULL,
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS removals (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    section  TEXT NOT NULL,
    name     TEXT NOT NULL,
    gen      TEXT NOT NULL DEFAULT ''         -- «без лука» — родительный падеж
);

CREATE TABLE IF NOT EXISTS zones (
    id       TEXT PRIMARY KEY,
    name     TEXT NOT NULL,
    price    INTEGER,                          -- NULL = по договорённости
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    number     INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    status     TEXT NOT NULL DEFAULT 'new',    -- new | confirmed | cooking | done | canceled
    mode       TEXT NOT NULL,                  -- delivery | pickup
    zone       TEXT NOT NULL DEFAULT '',
    name       TEXT NOT NULL,
    phone      TEXT NOT NULL,
    address    TEXT NOT NULL DEFAULT '',
    flat       TEXT NOT NULL DEFAULT '',
    landmark   TEXT NOT NULL DEFAULT '',
    note       TEXT NOT NULL DEFAULT '',
    goods      INTEGER NOT NULL,
    delivery   INTEGER NOT NULL,
    total      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS order_items (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    dish_id  TEXT NOT NULL,
    name     TEXT NOT NULL,
    qty      INTEGER NOT NULL,
    price    INTEGER NOT NULL,                 -- цена за штуку с добавками
    options  TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_order ON order_items(order_id);
"""


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys = ON')
    return con


def setup():
    with connect() as con:
        con.executescript(SCHEMA)
        # базы, созданные до появления расписания разделов
        cols = {r['name'] for r in con.execute('PRAGMA table_info(sections)')}
        for col in ('show_from', 'show_to'):
            if col not in cols:
                con.execute(f"ALTER TABLE sections ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")


def seed_if_empty():
    """Первый запуск: переносим меню из seed_data.py. Повторно не трогаем."""
    try:
        from . import seed_data as sd
    except ImportError:      # запуск не как пакет
        import seed_data as sd

    with connect() as con:
        if con.execute('SELECT COUNT(*) FROM dishes').fetchone()[0]:
            return False

        for i, s in enumerate(sd.SECTIONS):
            layout = s.get('layout', 'cards')
            con.execute('''INSERT OR REPLACE INTO sections
                (id, title, note, layout, position, show_from, show_to) VALUES (?,?,?,?,?,?,?)''',
                (s['id'], s['title'], s.get('note', ''), layout, i,
                 s.get('showFrom', ''), s.get('showTo', '')))

        for i, d in enumerate(sd.DISHES):
            con.execute("""INSERT INTO dishes
                (id, section, name, about, weight, kcal, cook, price, old_price, tag, parts, photo, position)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (d['id'], d['section'], d['name'], d.get('about', ''), d.get('weight', 0),
                 d.get('kcal', 0), d.get('cook', ''), d['price'], d.get('oldPrice'),
                 d.get('tag', ''), json.dumps(d.get('parts', []), ensure_ascii=False),
                 f"{d['id']}.jpg", i))

        for i, a in enumerate(sd.ADDONS):
            con.execute('INSERT OR REPLACE INTO addons (id, section, name, price, position) VALUES (?,?,?,?,?)',
                        (a['id'], a['section'], a['name'], a['price'], i))

        for r in sd.REMOVALS:
            con.execute('INSERT INTO removals (section, name, gen) VALUES (?,?,?)',
                        (r['section'], r['name'], r['gen']))

        for i, z in enumerate(sd.ZONES):
            con.execute('INSERT OR REPLACE INTO zones (id, name, price, position) VALUES (?,?,?,?)',
                        (z['id'], z['name'], z['price'], i))

        for k, v in sd.SETTINGS.items():
            con.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)', (k, str(v)))
    return True


# ── чтение ──────────────────────────────────────────────

def settings():
    with connect() as con:
        return {r['key']: r['value'] for r in con.execute('SELECT key, value FROM settings')}


def setting(key, default=''):
    return settings().get(key, default)


def save_setting(key, value):
    with connect() as con:
        con.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)', (key, str(value)))


def sections():
    with connect() as con:
        return [dict(r) for r in con.execute('SELECT * FROM sections ORDER BY position, id')]


def save_section_hours(section_id, show_from, show_to):
    with connect() as con:
        con.execute('UPDATE sections SET show_from = ?, show_to = ? WHERE id = ?',
                    (show_from, show_to, section_id))


def dishes(only_active=True):
    sql = 'SELECT * FROM dishes'
    if only_active:
        sql += ' WHERE active = 1'
    sql += ' ORDER BY position, id'
    with connect() as con:
        out = []
        for r in con.execute(sql):
            d = dict(r)
            d['parts'] = json.loads(d['parts'] or '[]')
            out.append(d)
        return out


def dish(dish_id):
    with connect() as con:
        r = con.execute('SELECT * FROM dishes WHERE id = ?', (dish_id,)).fetchone()
        if not r:
            return None
        d = dict(r)
        d['parts'] = json.loads(d['parts'] or '[]')
        return d


def addons(section=None):
    sql = 'SELECT * FROM addons'
    args = []
    if section:
        sql += ' WHERE section = ?'
        args.append(section)
    sql += ' ORDER BY position, id'
    with connect() as con:
        return [dict(r) for r in con.execute(sql, args)]


def addon(addon_id):
    with connect() as con:
        r = con.execute('SELECT * FROM addons WHERE id = ?', (addon_id,)).fetchone()
        return dict(r) if r else None


def removals(section=None):
    sql = 'SELECT * FROM removals'
    args = []
    if section:
        sql += ' WHERE section = ?'
        args.append(section)
    sql += ' ORDER BY id'
    with connect() as con:
        return [dict(r) for r in con.execute(sql, args)]


def save_addon(addon_id, section, name, price):
    with connect() as con:
        con.execute('INSERT OR REPLACE INTO addons (id, section, name, price, position) VALUES (?,?,?,?,'
                    'COALESCE((SELECT position FROM addons WHERE id = ?), 99))',
                    (addon_id, section, name, price, addon_id))


def delete_addon(addon_id):
    with connect() as con:
        con.execute('DELETE FROM addons WHERE id = ?', (addon_id,))


def zones():
    with connect() as con:
        return [dict(r) for r in con.execute('SELECT * FROM zones ORDER BY position, id')]


def zone(zone_id):
    with connect() as con:
        r = con.execute('SELECT * FROM zones WHERE id = ?', (zone_id,)).fetchone()
        return dict(r) if r else None


# ── запись меню ─────────────────────────────────────────

def save_dish(data, new=False):
    fields = ('id', 'section', 'name', 'about', 'weight', 'kcal', 'cook',
              'price', 'old_price', 'tag', 'parts', 'photo', 'active', 'position')
    row = {k: data.get(k) for k in fields}
    row['parts'] = json.dumps(data.get('parts', []), ensure_ascii=False)

    with connect() as con:
        if new:
            con.execute(f"""INSERT INTO dishes ({','.join(fields)})
                            VALUES ({','.join('?' * len(fields))})""",
                        [row[k] for k in fields])
        else:
            sets = ','.join(f'{k} = ?' for k in fields if k != 'id')
            con.execute(f'UPDATE dishes SET {sets} WHERE id = ?',
                        [row[k] for k in fields if k != 'id'] + [row['id']])


def delete_dish(dish_id):
    with connect() as con:
        con.execute('DELETE FROM dishes WHERE id = ?', (dish_id,))


def save_zone(zone_id, name, price):
    with connect() as con:
        con.execute('INSERT OR REPLACE INTO zones (id, name, price, position) VALUES (?,?,?,'
                    'COALESCE((SELECT position FROM zones WHERE id = ?), 99))',
                    (zone_id, name, price, zone_id))


def delete_zone(zone_id):
    with connect() as con:
        con.execute('DELETE FROM zones WHERE id = ?', (zone_id,))


# ── заказы ──────────────────────────────────────────────

def next_number():
    with connect() as con:
        last = con.execute('SELECT MAX(number) FROM orders').fetchone()[0]
        return (last or 123) + 1


def create_order(order, items):
    with connect() as con:
        cur = con.execute("""INSERT INTO orders
            (number, mode, zone, name, phone, address, flat, landmark, note, goods, delivery, total)
            VALUES (:number,:mode,:zone,:name,:phone,:address,:flat,:landmark,:note,:goods,:delivery,:total)""",
            order)
        oid = cur.lastrowid
        for it in items:
            con.execute("""INSERT INTO order_items (order_id, dish_id, name, qty, price, options)
                           VALUES (?,?,?,?,?,?)""",
                        (oid, it['dish_id'], it['name'], it['qty'], it['price'], it['options']))
        return oid


def orders(status=None, limit=200):
    sql = 'SELECT * FROM orders'
    args = []
    if status:
        sql += ' WHERE status = ?'
        args.append(status)
    sql += ' ORDER BY id DESC LIMIT ?'
    args.append(limit)

    with connect() as con:
        out = []
        for r in con.execute(sql, args):
            o = dict(r)
            o['items'] = [dict(i) for i in con.execute(
                'SELECT * FROM order_items WHERE order_id = ? ORDER BY id', (o['id'],))]
            out.append(o)
        return out


def set_status(order_id, status):
    with connect() as con:
        con.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))


def counts():
    with connect() as con:
        rows = con.execute('SELECT status, COUNT(*) n FROM orders GROUP BY status')
        return {r['status']: r['n'] for r in rows}
