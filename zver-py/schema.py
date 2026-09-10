"""Создание и обновление структуры базы.

Полностью повторяет migrate() из PHP-версии: те же таблицы z_*, те же
колонки и индексы, те же настройки по умолчанию. Запускается при каждом
старте бота — все запросы идемпотентны, повторный вызов ничего не ломает
и данные не трогает.

Благодаря этому Python-бот больше не зависит от PHP: он поднимает базу
сам, на чистом сервере.
"""
from __future__ import annotations

import db
from handlers.common import log

CHARSET = "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"

TABLES: tuple[str, ...] = (
    f"""CREATE TABLE IF NOT EXISTS z_users (
        id BIGINT PRIMARY KEY, username VARCHAR(64) NULL, name VARCHAR(128) NULL,
        phone VARCHAR(32) NULL, lang VARCHAR(4) DEFAULT 'tj',
        balance DECIMAL(14,2) DEFAULT 0, spent DECIMAL(14,2) DEFAULT 0,
        orders_cnt INT DEFAULT 0, blocked TINYINT DEFAULT 0,
        ref_by BIGINT NULL, ref_paid TINYINT DEFAULT 0,
        ref_cnt INT DEFAULT 0, ref_sum DECIMAL(14,2) DEFAULT 0,
        created_at INT, seen_at INT) {CHARSET}""",

    f"""CREATE TABLE IF NOT EXISTS z_games (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(120), image VARCHAR(255) NULL,
        need_server TINYINT DEFAULT 0,
        id_label VARCHAR(60) DEFAULT 'ID',
        server_label VARCHAR(60) DEFAULT 'Server',
        hint VARCHAR(191) NULL,
        sort INT DEFAULT 0, active TINYINT DEFAULT 1,
        created_at INT) {CHARSET}""",

    f"""CREATE TABLE IF NOT EXISTS z_packs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        game_id INT, name VARCHAR(120), price DECIMAL(12,2),
        old_price DECIMAL(12,2) NULL, tag VARCHAR(24) NULL,
        sort INT DEFAULT 0, active TINYINT DEFAULT 1,
        INDEX (game_id)) {CHARSET}""",

    f"""CREATE TABLE IF NOT EXISTS z_orders (
        id INT AUTO_INCREMENT PRIMARY KEY,
        uid BIGINT, game_id INT, pack_id INT,
        game_name VARCHAR(120), pack_name VARCHAR(120),
        player_id VARCHAR(64), server_id VARCHAR(64) NULL,
        qty INT DEFAULT 1, price DECIMAL(12,2),
        status VARCHAR(16) DEFAULT 'new',
        code VARCHAR(191) NULL, note VARCHAR(191) NULL,
        admin_id BIGINT NULL, refunded TINYINT DEFAULT 0,
        created_at INT, done_at INT NULL,
        INDEX (uid), INDEX (status)) {CHARSET}""",

    f"""CREATE TABLE IF NOT EXISTS z_topups (
        id INT AUTO_INCREMENT PRIMARY KEY,
        uid BIGINT, amount DECIMAL(12,2), req_id INT NULL,
        file_id VARCHAR(191) NULL, status VARCHAR(16) DEFAULT 'new',
        admin_id BIGINT NULL, created_at INT, done_at INT NULL,
        INDEX (uid), INDEX (status)) {CHARSET}""",

    f"""CREATE TABLE IF NOT EXISTS z_tx (
        id INT AUTO_INCREMENT PRIMARY KEY, uid BIGINT,
        kind VARCHAR(16), amount DECIMAL(12,2), balance DECIMAL(14,2) DEFAULT 0,
        title VARCHAR(160) NULL, ref_id INT NULL, created_at INT,
        INDEX (uid, id), INDEX (created_at)) {CHARSET}""",

    f"""CREATE TABLE IF NOT EXISTS z_reqs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        bank VARCHAR(80), owner VARCHAR(120), number VARCHAR(80),
        kind VARCHAR(12) DEFAULT 'card', pay_url VARCHAR(255) NULL,
        active TINYINT DEFAULT 1, sort INT DEFAULT 0) {CHARSET}""",

    f"""CREATE TABLE IF NOT EXISTS z_settings (k VARCHAR(64) PRIMARY KEY, v TEXT)
        {CHARSET}""",

    f"""CREATE TABLE IF NOT EXISTS z_state (
        uid BIGINT PRIMARY KEY, st VARCHAR(64) NULL, data MEDIUMTEXT NULL, at INT)
        {CHARSET}""",

    f"""CREATE TABLE IF NOT EXISTS z_promo (
        id INT AUTO_INCREMENT PRIMARY KEY, code VARCHAR(32) UNIQUE,
        kind VARCHAR(8) DEFAULT 'pct', val DECIMAL(10,2),
        min_sum DECIMAL(12,2) DEFAULT 0, max_uses INT DEFAULT 0, per_user INT DEFAULT 1,
        used INT DEFAULT 0, saved DECIMAL(14,2) DEFAULT 0, until INT NULL,
        active TINYINT DEFAULT 1, created_at INT) {CHARSET}""",

    f"""CREATE TABLE IF NOT EXISTS z_promo_use (
        id INT AUTO_INCREMENT PRIMARY KEY, promo_id INT, uid BIGINT, order_id INT NULL,
        sum_off DECIMAL(12,2), at INT,
        INDEX (promo_id), INDEX (uid)) {CHARSET}""",

    f"""CREATE TABLE IF NOT EXISTS z_subs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        chat VARCHAR(120), title VARCHAR(120), link VARCHAR(255) NULL,
        active TINYINT DEFAULT 1, sort INT DEFAULT 0,
        created_at INT DEFAULT 0) {CHARSET}""",

    f"""CREATE TABLE IF NOT EXISTS z_reviews (
        id INT AUTO_INCREMENT PRIMARY KEY, uid BIGINT, order_id INT, stars TINYINT,
        txt TEXT NULL, posted TINYINT DEFAULT 0, created_at INT,
        UNIQUE KEY uq_rev (order_id)) {CHARSET}""",

    f"""CREATE TABLE IF NOT EXISTS z_queue (
        id INT AUTO_INCREMENT PRIMARY KEY, order_id INT UNIQUE, uid BIGINT,
        tries INT DEFAULT 0, last_err VARCHAR(191) NULL, created_at INT,
        INDEX (uid)) {CHARSET}""",

    f"""CREATE TABLE IF NOT EXISTS z_bank (
        id INT AUTO_INCREMENT PRIMARY KEY,
        op_no VARCHAR(64) NULL, amount DECIMAL(12,2), top_id INT NULL,
        comment VARCHAR(120) NULL, op_date VARCHAR(24) NULL, op_time VARCHAR(16) NULL,
        card VARCHAR(40) NULL, sender VARCHAR(120) NULL,
        matched INT NULL, raw TEXT NULL, created_at INT,
        UNIQUE KEY uq_op (op_no), INDEX (amount), INDEX (created_at)) {CHARSET}""",

    f"""CREATE TABLE IF NOT EXISTS z_checks (
        id INT AUTO_INCREMENT PRIMARY KEY, topup_id INT NULL, uid BIGINT,
        img_hash VARCHAR(40) NULL, op_no VARCHAR(64) NULL,
        amount DECIMAL(12,2) NULL, op_date VARCHAR(24) NULL, op_time VARCHAR(16) NULL,
        bank VARCHAR(80) NULL, receiver VARCHAR(120) NULL, sender VARCHAR(120) NULL,
        verdict VARCHAR(16) DEFAULT 'ok', reason VARCHAR(191) NULL,
        raw MEDIUMTEXT NULL, created_at INT,
        INDEX (uid), INDEX (img_hash), INDEX (op_no)) {CHARSET}""",

    f"""CREATE TABLE IF NOT EXISTS z_hooks (eid VARCHAR(80) PRIMARY KEY, at INT)
        {CHARSET}""",

    f"""CREATE TABLE IF NOT EXISTS z_rate (
        k VARCHAR(80) PRIMARY KEY, cnt INT DEFAULT 0, win INT DEFAULT 0) {CHARSET}""",

    f"""CREATE TABLE IF NOT EXISTS z_bans (
        ip VARCHAR(64) PRIMARY KEY, until INT, why VARCHAR(64) NULL) {CHARSET}""",

    f"""CREATE TABLE IF NOT EXISTS z_log (
        id INT AUTO_INCREMENT PRIMARY KEY,
        tag VARCHAR(32), txt MEDIUMTEXT, at INT) {CHARSET}""",
)

# Колонки и индексы, добавленные к таблицам позже. Каждый запрос
# выполняется отдельно: «уже существует» — это норма, а не ошибка.
PATCHES: tuple[str, ...] = (
    "ALTER TABLE z_games ADD COLUMN ft_code VARCHAR(128) NULL",
    "ALTER TABLE z_games ADD COLUMN ft_type VARCHAR(32) NULL",
    "ALTER TABLE z_games ADD COLUMN vcode VARCHAR(64) NULL",
    "ALTER TABLE z_games ADD COLUMN can_chk TINYINT DEFAULT 0",
    "ALTER TABLE z_games ADD COLUMN fields MEDIUMTEXT NULL",
    "ALTER TABLE z_games ADD COLUMN hidden TINYINT DEFAULT 0",
    "ALTER TABLE z_games ADD COLUMN title VARCHAR(120) NULL",
    "ALTER TABLE z_games ADD COLUMN cat_order VARCHAR(255) NULL",
    "ALTER TABLE z_games ADD COLUMN base VARCHAR(120) NULL",
    "ALTER TABLE z_games ADD COLUMN region VARCHAR(16) NULL",
    "ALTER TABLE z_games ADD COLUMN flag VARCHAR(8) NULL",
    "ALTER TABLE z_games ADD INDEX idx_base (base)",
    "ALTER TABLE z_games ADD UNIQUE KEY uq_ft (ft_code)",

    "ALTER TABLE z_packs ADD COLUMN title VARCHAR(120) NULL",
    "ALTER TABLE z_packs ADD COLUMN fixed TINYINT DEFAULT 0",
    "ALTER TABLE z_packs ADD COLUMN cat VARCHAR(16) DEFAULT 'main'",
    "ALTER TABLE z_packs ADD COLUMN ft_code VARCHAR(160) NULL",
    "ALTER TABLE z_packs ADD COLUMN cost DECIMAL(12,4) DEFAULT 0",
    "ALTER TABLE z_packs ADD INDEX idx_game_active (game_id, active)",
    "ALTER TABLE z_packs ADD UNIQUE KEY uq_ftp (ft_code)",

    "ALTER TABLE z_orders ADD COLUMN promo VARCHAR(32) NULL",
    "ALTER TABLE z_orders ADD COLUMN discount DECIMAL(12,2) DEFAULT 0",
    "ALTER TABLE z_orders ADD COLUMN ft_id VARCHAR(64) NULL",
    "ALTER TABLE z_orders ADD COLUMN ref VARCHAR(64) NULL",
    "ALTER TABLE z_orders ADD COLUMN nick VARCHAR(191) NULL",
    "ALTER TABLE z_orders ADD UNIQUE KEY uq_ref (ref)",
    "ALTER TABLE z_orders ADD INDEX idx_uid_id (uid, id)",
    "ALTER TABLE z_orders ADD INDEX idx_status_created (status, created_at)",
    "ALTER TABLE z_orders ADD INDEX idx_status_ref (status, refunded)",

    "ALTER TABLE z_topups ADD COLUMN comment VARCHAR(64) NULL",
    "ALTER TABLE z_topups ADD INDEX idx_uid_status (uid, status)",
    "ALTER TABLE z_topups ADD INDEX idx_status_created (status, created_at)",

    "ALTER TABLE z_reqs ADD COLUMN fname VARCHAR(80) NULL",
    "ALTER TABLE z_reqs ADD COLUMN lname VARCHAR(80) NULL",
    "ALTER TABLE z_reqs ADD COLUMN note VARCHAR(160) NULL",
    "ALTER TABLE z_reqs ADD COLUMN logo VARCHAR(191) NULL",

    "ALTER TABLE z_users ADD COLUMN sub_ok_at INT DEFAULT 0",
    "ALTER TABLE z_settings ADD COLUMN v2 TEXT NULL",
    "ALTER TABLE z_reviews ADD INDEX idx_posted (posted)",
    "ALTER TABLE z_rate ADD INDEX idx_win (win)",
)

DEFAULTS: dict[str, str] = {
    "shop":        "ZVER TAJ",
    "markup":      "20",
    "rate":        "11",
    "round":       "0.5",
    "sandbox":     "0",
    "lowbal":      "5",
    "lownote":     "0",
    "ft_nick":     "1",
    "sub_ch":      "",
    "ask_rev":     "1",
    "rev_ch":      "",
    "rev_min":     "4",
    "rev_anon":    "0",
    "live_base":   "0",
    "live_add":    "0",
    "pay_tpl":     "https://pay.dc.tj/?a={NUM}&c={COMMENT}&f1=133&s={SUM}",
    "bank_wait":   "20",
    "bank_reject": "0",
    "top":         ("free fire,pubg,mobile legends,call of duty,standoff,genshin,"
                    "delta force,roblox,brawl stars,clash of clans,valorant,efootball"),
    "auto":        "1",
    "cur":         "TJS",
    "support":     "",
    "wa":          "",
    "channel":     "",
    "reviews":     "",
    "ref_bonus":   "0.50",
    "welcome":     "",
}


async def ensure() -> dict:
    """Создать недостающие таблицы, колонки и настройки.

    Возвращает сводку: сколько таблиц есть, сколько колонок добавлено,
    сколько настроек записано впервые.
    """
    for sql in TABLES:
        await db.run(sql)

    added = 0
    for sql in PATCHES:
        try:
            await db.run(sql)
            added += 1
        except Exception:
            # колонка или индекс уже на месте — так и должно быть
            pass

    seeded = 0
    for key, val in DEFAULTS.items():
        try:
            async with db._p().acquire() as conn:          # noqa: SLF001
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT IGNORE INTO z_settings (k, v) VALUES (%s, %s)",
                        (key, val))
                    seeded += cur.rowcount
        except Exception as e:
            log.warning("настройка %s не записана: %s", key, e)

    row = await db.one(
        "SELECT COUNT(*) AS c FROM information_schema.tables "
        "WHERE table_schema = DATABASE() AND table_name LIKE 'z\\_%'")
    tables = int((row or {}).get("c", 0))

    log.info("база готова: таблиц %s, новых колонок %s, настроек записано %s",
             tables, added, seeded)
    return {"tables": tables, "columns_added": added, "settings_seeded": seeded}


if __name__ == "__main__":
    import asyncio

    async def _main() -> None:
        await db.init()
        res = await ensure()
        print(f"Таблиц: {res['tables']}, добавлено колонок: {res['columns_added']}, "
              f"настроек: {res['settings_seeded']}")
        await db.close()

    asyncio.run(_main())
