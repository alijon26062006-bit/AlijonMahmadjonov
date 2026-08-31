-- ============================================================
-- AVERIX Freelance — учётные записи
--
-- Первая миграция маркетплейса. До неё в проекте было две роли
-- с отдельными таблицами: админ и специалист студии. Появляется
-- третья, самостоятельная: пользователь площадки.
--
-- Почему отдельная таблица, а не расширение freelancers:
--   * на freelancers завязаны tasks — внутренняя работа студии,
--     и ломать её нельзя;
--   * у одного человека может быть два лица — заказчик и специалист,
--     а учётная запись при этом одна;
--   * вход по почте, а не по логину, выданному администратором.
--
-- Существующие анкеты остаются как были: user_id у них NULL, они
-- по-прежнему видны только студии. Ни одна из них не превращается
-- в учётную запись от этой миграции.
--
-- Таблицы маркетплейса живут без колонок *_ru / *_tj: приложение
-- русскоязычное. Двуязычие остаётся у витрины студии.
-- ============================================================

-- ---------- учётная запись ----------
CREATE TABLE users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    -- NOCASE, чтобы Ivan@mail.ru и ivan@mail.ru не стали двумя людьми.
    -- В коде адрес всё равно приводится к нижнему регистру: NOCASE
    -- в SQLite складывает только латиницу.
    email          TEXT NOT NULL COLLATE NOCASE,
    password_hash  TEXT NOT NULL,
    telegram       TEXT,
    status         TEXT NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active', 'suspended', 'deleted')),
    -- Значок «почта подтверждена» ставится только по факту перехода
    -- по ссылке из письма. Ничего другого он не означает.
    email_verified INTEGER NOT NULL DEFAULT 0,
    suspend_reason TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at   TEXT
);
CREATE UNIQUE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status, created_at DESC);

-- ---------- сессии пользователей ----------
-- Своя таблица, как у админов и у специалистов студии. Общая таблица
-- на три роли однажды выдала бы одной роли токен другой.
-- В базе лежит только sha256 токена: укравший базу не получит cookie.
CREATE TABLE user_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    csrf_token TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    ip         TEXT,
    user_agent TEXT
);
CREATE INDEX idx_user_sessions_owner ON user_sessions(user_id);
CREATE INDEX idx_user_sessions_exp   ON user_sessions(expires_at);

-- ---------- одноразовые ссылки из писем ----------
-- Подтверждение почты и сброс пароля. Хранится хеш, а не сам код:
-- база с этими строками не даёт войти ни под кем.
CREATE TABLE user_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL CHECK (kind IN ('verify', 'reset')),
    expires_at TEXT NOT NULL,
    used_at    TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_user_tokens_owner ON user_tokens(user_id, kind, created_at DESC);

-- ---------- лицо заказчика ----------
-- Своя таблица, а не колонки в users: у одного человека может быть
-- и лицо заказчика, и лицо специалиста, и оба заполняются по-разному.
CREATE TABLE client_profiles (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    about        TEXT,
    location     TEXT,
    avatar       TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------- лицо специалиста ----------
-- Профилем специалиста становится существующая таблица freelancers:
-- в ней уже есть имя, специализация, навыки, рассказ о себе, ставка,
-- занятость и фотография, и на неё ссылаются задачи студии.
-- Заводить рядом вторую такую же таблицу — верный способ развести
-- два источника правды об одном человеке.
--
-- У старых строк user_id остаётся NULL: это закрытая база студии.
ALTER TABLE freelancers ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
CREATE UNIQUE INDEX idx_freelancers_user ON freelancers(user_id)
       WHERE user_id IS NOT NULL;

-- ---------- счётчик попыток для форм маркетплейса ----------
-- Отдельно от login_attempts: тот считает подбор пароля, и записывать
-- туда регистрации значило бы блокировать вход честным людям.
CREATE TABLE fl_rate_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ip         TEXT NOT NULL,
    kind       TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_fl_rate ON fl_rate_events(kind, ip, created_at);
