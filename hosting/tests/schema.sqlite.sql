-- ЗЕРКАЛО схемы hosting/migrations/*.sql для автотестов в песочнице без сервера MariaDB.
-- Это НЕ то, что разворачивается на проде — там работает bin/migrate.php по-настоящему
-- (см. migrations/*.sql). Колонки и имена таблиц здесь совпадают 1:1 с миграциями,
-- типы упрощены под SQLite (ENUM -> TEXT CHECK, JSON -> TEXT).

CREATE TABLE plans (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    code                    TEXT NOT NULL UNIQUE,
    title                   TEXT NOT NULL,
    price_tjs               REAL NOT NULL DEFAULT 0,
    disk_quota_mb           INTEGER NOT NULL,
    inode_limit             INTEGER NOT NULL,
    max_sites               INTEGER NOT NULL,
    max_databases           INTEGER NOT NULL,
    pm_max_children         INTEGER NOT NULL,
    memory_limit_mb         INTEGER NOT NULL,
    db_max_user_connections INTEGER NOT NULL,
    cpu_quota_percent       INTEGER NOT NULL,
    memory_max_mb           INTEGER NOT NULL,
    tasks_max               INTEGER NOT NULL,
    is_active               INTEGER NOT NULL DEFAULT 1,
    created_at              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now'))
);

CREATE TABLE users (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    email             TEXT UNIQUE,
    password_hash     TEXT,
    display_name      TEXT NOT NULL DEFAULT '',
    system_user       TEXT NOT NULL DEFAULT '' UNIQUE,
    role              TEXT NOT NULL DEFAULT 'client' CHECK (role IN ('client','admin')),
    plan_id           INTEGER REFERENCES plans(id) ON DELETE SET NULL,
    status            TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','grace','suspended','pending_delete')),
    disk_quota_mb     INTEGER NOT NULL DEFAULT 0,
    inode_limit       INTEGER NOT NULL DEFAULT 0,
    max_sites         INTEGER NOT NULL DEFAULT 0,
    max_databases     INTEGER NOT NULL DEFAULT 0,
    two_factor_secret TEXT,
    grace_until       TEXT,
    suspended_until   TEXT,
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')),
    updated_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now'))
);

CREATE TABLE telegram_accounts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    telegram_id INTEGER NOT NULL UNIQUE,
    username    TEXT NOT NULL DEFAULT '',
    first_name  TEXT NOT NULL DEFAULT '',
    last_name   TEXT NOT NULL DEFAULT '',
    linked_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now'))
);

CREATE TABLE sessions (
    id           TEXT PRIMARY KEY,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ip           TEXT NOT NULL DEFAULT '',
    user_agent   TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')),
    last_seen_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')),
    expires_at   TEXT NOT NULL
);

CREATE TABLE subscriptions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id            INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_id            INTEGER NOT NULL REFERENCES plans(id),
    status             TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','grace','suspended','cancelled')),
    started_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')),
    current_period_end TEXT,
    grace_until        TEXT,
    suspended_at       TEXT,
    cancelled_at       TEXT
);

CREATE TABLE sites (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slug        TEXT NOT NULL,
    domain      TEXT NOT NULL UNIQUE,
    doc_root    TEXT NOT NULL DEFAULT 'public',
    php_version TEXT NOT NULL DEFAULT '8.3',
    status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','active','suspended','deleted')),
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')),
    UNIQUE (user_id, slug)
);

CREATE TABLE domains (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id       INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    domain        TEXT NOT NULL UNIQUE,
    is_primary    INTEGER NOT NULL DEFAULT 0,
    verified      INTEGER NOT NULL DEFAULT 0,
    verified_at   TEXT,
    ssl_status    TEXT NOT NULL DEFAULT 'none' CHECK (ssl_status IN ('none','pending','issued','failed')),
    ssl_issued_at TEXT,
    last_check_at TEXT,
    last_error    TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now'))
);

CREATE TABLE databases (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    site_id    INTEGER REFERENCES sites(id) ON DELETE SET NULL,
    db_name    TEXT NOT NULL UNIQUE,
    status     TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','active','failed','deleted')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now'))
);

CREATE TABLE database_users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    db_user         TEXT NOT NULL UNIQUE,
    max_connections INTEGER NOT NULL DEFAULT 5,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now'))
);

CREATE TABLE jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    type        TEXT NOT NULL,
    user_id     INTEGER,
    site_id     INTEGER,
    status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','success','failed')),
    payload     TEXT,
    error_text  TEXT,
    attempts    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now')),
    started_at  TEXT,
    finished_at TEXT
);

CREATE TABLE payments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    subscription_id INTEGER REFERENCES subscriptions(id) ON DELETE SET NULL,
    provider        TEXT NOT NULL DEFAULT 'manual' CHECK (provider IN ('telegram_stars','manual','other')),
    amount_tjs      REAL NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'TJS',
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','paid','failed','refunded')),
    external_id     TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now'))
);

CREATE TABLE backups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type        TEXT NOT NULL CHECK (type IN ('files','database','full')),
    local_path  TEXT NOT NULL DEFAULT '',
    remote_path TEXT NOT NULL DEFAULT '',
    checksum    TEXT NOT NULL DEFAULT '',
    size_bytes  INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','success','failed')),
    verified_at TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now'))
);

CREATE TABLE resource_usage (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cpu_percent   REAL NOT NULL DEFAULT 0,
    memory_mb     INTEGER NOT NULL DEFAULT 0,
    disk_mb       INTEGER NOT NULL DEFAULT 0,
    inode_count   INTEGER NOT NULL DEFAULT 0,
    process_count INTEGER NOT NULL DEFAULT 0,
    recorded_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now'))
);

CREATE TABLE audit_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    actor       TEXT NOT NULL DEFAULT '',
    action      TEXT NOT NULL,
    object_type TEXT NOT NULL DEFAULT '',
    object_id   INTEGER,
    ip          TEXT NOT NULL DEFAULT '',
    result      TEXT NOT NULL DEFAULT 'success' CHECK (result IN ('success','failure')),
    details     TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now'))
);

CREATE TABLE security_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    event_type TEXT NOT NULL,
    severity   TEXT NOT NULL DEFAULT 'info' CHECK (severity IN ('info','warning','critical')),
    ip         TEXT NOT NULL DEFAULT '',
    details    TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now'))
);

CREATE TABLE login_attempts (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    identifier TEXT NOT NULL,
    ip         TEXT NOT NULL DEFAULT '',
    success    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now'))
);

CREATE TABLE notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    channel    TEXT NOT NULL DEFAULT 'panel' CHECK (channel IN ('telegram','email','panel')),
    title      TEXT NOT NULL,
    body       TEXT NOT NULL,
    is_read    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now'))
);

CREATE TABLE scheduled_jobs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    site_id       INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    command       TEXT NOT NULL,
    schedule_expr TEXT NOT NULL,
    is_enabled    INTEGER NOT NULL DEFAULT 1,
    last_run_at   TEXT,
    last_status   TEXT CHECK (last_status IN ('success','failed')),
    created_at    TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%S','now'))
);

INSERT INTO plans
    (code, title, price_tjs, disk_quota_mb, inode_limit, max_sites, max_databases,
     pm_max_children, memory_limit_mb, db_max_user_connections,
     cpu_quota_percent, memory_max_mb, tasks_max)
VALUES
    ('start',  'Старт',  15.00,  2048,  100000, 1,  1,  2, 128,  5,  50,  256, 30),
    ('medium', 'Бизнес', 45.00,  5120,  250000, 5,  5,  4, 192, 10, 100,  512, 50),
    ('pro',    'Про',    90.00, 15360,  500000, 25, 25, 6, 256, 20, 200, 1024, 80);

ALTER TABLE jobs ADD COLUMN result_secret TEXT;
