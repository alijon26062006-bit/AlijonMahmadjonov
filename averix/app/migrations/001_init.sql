-- ============================================================
-- AVERIX — начальная схема
-- Текст хранится парами RU/TJ. Машинного перевода нет:
-- если таджикский не заполнен, показывается русский.
-- ============================================================

CREATE TABLE admins (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at TEXT
);

-- Токен сессии хранится хешем: утечка базы не даёт войти под админом
CREATE TABLE sessions (
    token_hash TEXT PRIMARY KEY,
    admin_id   INTEGER NOT NULL REFERENCES admins(id) ON DELETE CASCADE,
    csrf_token TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    ip         TEXT,
    user_agent TEXT
);
CREATE INDEX idx_sessions_admin ON sessions(admin_id);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);

-- Учёт попыток входа для защиты от перебора
CREATE TABLE login_attempts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ip           TEXT NOT NULL,
    username     TEXT,
    success      INTEGER NOT NULL DEFAULT 0,
    attempted_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_attempts_ip_time ON login_attempts(ip, attempted_at);

CREATE TABLE projects (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    slug               TEXT NOT NULL UNIQUE,
    category           TEXT NOT NULL,
    year               INTEGER,

    title_ru           TEXT NOT NULL,
    title_tj           TEXT,
    excerpt_ru         TEXT,
    excerpt_tj         TEXT,
    body_ru            TEXT,
    body_tj            TEXT,
    task_ru            TEXT,
    task_tj            TEXT,
    solution_ru        TEXT,
    solution_tj        TEXT,
    features_ru        TEXT,
    features_tj        TEXT,
    result_ru          TEXT,
    result_tj          TEXT,

    cover_image_id     INTEGER REFERENCES project_images(id) ON DELETE SET NULL,
    project_url        TEXT,
    github_url         TEXT,

    featured           INTEGER NOT NULL DEFAULT 0,
    status             TEXT NOT NULL DEFAULT 'draft'
                       CHECK (status IN ('draft', 'published')),
    sort_order         INTEGER NOT NULL DEFAULT 0,

    seo_title_ru       TEXT,
    seo_title_tj       TEXT,
    seo_description_ru TEXT,
    seo_description_tj TEXT,

    created_at         TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_projects_status ON projects(status, sort_order);
CREATE INDEX idx_projects_featured ON projects(featured, sort_order);
CREATE INDEX idx_projects_category ON projects(category);

CREATE TABLE project_images (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    filename   TEXT NOT NULL,
    alt_ru     TEXT,
    alt_tj     TEXT,
    width      INTEGER,
    height     INTEGER,
    bytes      INTEGER,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_images_project ON project_images(project_id, sort_order);

CREATE TABLE project_tech (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_tech_project ON project_tech(project_id, sort_order);

-- Настройки сайта: hero, контакты, тексты, реальные цифры
CREATE TABLE site_settings (
    key        TEXT PRIMARY KEY,
    value_ru   TEXT,
    value_tj   TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
