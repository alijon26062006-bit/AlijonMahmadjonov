-- ============================================================
-- AVERIX — разделы студии: настройки, команда, вакансии, заявки
-- Текст везде парами RU/TJ. Машинного перевода нет: если
-- таджикский не заполнен, показывается русский.
-- ============================================================

-- Полей у проектов не хватало для управления выдачей в поиске
ALTER TABLE projects ADD COLUMN og_image TEXT;
ALTER TABLE projects ADD COLUMN allow_indexing INTEGER NOT NULL DEFAULT 1;

-- ---------- команда ----------
CREATE TABLE team_members (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    position_ru TEXT,
    position_tj TEXT,
    bio_ru      TEXT,
    bio_tj      TEXT,
    photo       TEXT,
    telegram    TEXT,
    github      TEXT,
    linkedin    TEXT,
    website     TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0,
    visible     INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_team_visible ON team_members(visible, sort_order);

-- ---------- вакансии ----------
CREATE TABLE vacancies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    title_ru        TEXT NOT NULL,
    title_tj        TEXT,
    description_ru  TEXT,
    description_tj  TEXT,
    requirements_ru TEXT,
    requirements_tj TEXT,
    location        TEXT,
    work_type       TEXT NOT NULL DEFAULT 'remote'
                    CHECK (work_type IN ('remote', 'office', 'hybrid')),
    employment      TEXT NOT NULL DEFAULT 'project'
                    CHECK (employment IN ('full', 'part', 'project')),
    status          TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'closed')),
    sort_order      INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_vacancies_status ON vacancies(status, sort_order);

-- ---------- отклики на вакансии ----------
CREATE TABLE job_applications (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    vacancy_id    INTEGER REFERENCES vacancies(id) ON DELETE SET NULL,
    name          TEXT NOT NULL,
    telegram      TEXT,
    email         TEXT,
    country       TEXT,
    direction     TEXT,
    experience    TEXT,
    skills        TEXT,
    portfolio_url TEXT,
    github_url    TEXT,
    message       TEXT,
    status        TEXT NOT NULL DEFAULT 'new'
                  CHECK (status IN ('new', 'viewed', 'interview', 'accepted', 'rejected')),
    admin_note    TEXT,
    ip            TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_job_status ON job_applications(status, created_at DESC);
CREATE INDEX idx_job_vacancy ON job_applications(vacancy_id);

-- ---------- заявки клиентов ----------
CREATE TABLE client_requests (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    telegram     TEXT,
    email        TEXT,
    project_type TEXT,
    budget       TEXT,
    message      TEXT,
    status       TEXT NOT NULL DEFAULT 'new'
                 CHECK (status IN ('new', 'contacted', 'in_progress', 'won', 'closed')),
    admin_note   TEXT,
    ip           TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_requests_status ON client_requests(status, created_at DESC);

-- ---------- значения настроек по умолчанию ----------
-- Берутся из того, что сейчас зашито в разметку. После этой миграции
-- контакты и тексты меняются через админку, без правки кода.
INSERT INTO site_settings (key, value_ru, value_tj) VALUES
  ('contact_telegram',  'rutsiyax', 'rutsiyax'),
  ('contact_email',     'alijon26.06.2006@gmail.com', 'alijon26.06.2006@gmail.com'),
  ('contact_instagram', '', ''),
  ('contact_github',    'alijon26062006-bit', 'alijon26062006-bit'),
  ('city',              'Душанбе, Таджикистан', 'Душанбе, Тоҷикистон'),
  ('hero_eyebrow',      'IT-студия · Душанбе · с 2023 года', 'IT-студия · Душанбе · аз соли 2023'),
  ('hero_title',        'Цифровые продукты, созданные <em>под задачу</em>',
                        'Маҳсулоти рақамӣ, ки <em>барои вазифа</em> сохта шудаанд'),
  ('hero_subtitle',     'Сайты, Telegram-боты и автоматизация — от идеи и дизайна до разработки и запуска.',
                        'Сомонаҳо, Telegram-ботҳо ва автоматизатсия — аз ғоя ва дизайн то сохтан ва оғоз.'),
  ('stat_years',        '3', '3'),
  ('stat_active',       '4', '4'),
  ('stat_accepted',     '100', '100'),
  ('about_text',        'AVERIX — студия разработки цифровых продуктов. Я превращаю идеи в работающие сайты, Telegram-боты, сервисы и системы автоматизации.',
                        'AVERIX — студияи сохтани маҳсулоти рақамӣ. Ман ғояҳоро ба сомонаҳо, Telegram-ботҳо, хизматрасониҳо ва системаҳои автоматизатсия табдил медиҳам.'),
  ('cta_title',         'Есть идея? Давайте превратим её в работающий продукт.',
                        'Ғоя доред? Биёед онро ба маҳсулоти корӣ табдил диҳем.'),
  ('careers_intro',     'Собираем людей, которым интересно создавать реальные цифровые продукты — от идеи до запуска.',
                        'Одамонеро ҷамъ меорем, ки ба сохтани маҳсулоти воқеии рақамӣ шавқ доранд — аз ғоя то оғоз.');
