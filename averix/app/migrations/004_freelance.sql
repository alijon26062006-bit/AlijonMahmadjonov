-- ============================================================
-- AVERIX — фрилансеры, клиентские проекты и задачи
--
-- Разделение, на котором всё держится:
--   projects        — публичное портфолио, кейс на сайте
--   client_projects — внутренняя работа с заказчиком, наружу не видна
-- Их нельзя смешивать: в первом нет бюджета и сроков, во втором
-- нет ничего, что можно показать посетителю.
--
-- Фрилансер — не участник команды. team_members попадает на сайт,
-- freelancers не попадает туда никогда: это база специалистов,
-- к которой обращаются, когда появляется подходящая задача.
-- ============================================================

-- ---------- недостающие поля в существующих таблицах ----------
ALTER TABLE team_members ADD COLUMN skills TEXT;
ALTER TABLE vacancies    ADD COLUMN skills TEXT;

-- ---------- база специалистов ----------
CREATE TABLE freelancers (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    telegram       TEXT,
    email          TEXT,
    -- Логин появляется только после одобрения: пароль задаёт админ,
    -- сама анкета никогда не создаёт учётную запись
    login          TEXT UNIQUE,
    password_hash  TEXT,
    country        TEXT,
    city           TEXT,
    specialization TEXT NOT NULL DEFAULT 'other',
    skills         TEXT,
    experience     TEXT,
    years          TEXT,
    about          TEXT,
    portfolio_url  TEXT,
    github_url     TEXT,
    cv_file        TEXT,
    photo          TEXT,
    rate           TEXT,
    rate_type      TEXT NOT NULL DEFAULT 'hour'
                   CHECK (rate_type IN ('hour', 'project')),
    availability   TEXT NOT NULL DEFAULT 'available'
                   CHECK (availability IN ('available', 'partially_busy', 'busy')),
    status         TEXT NOT NULL DEFAULT 'new'
                   CHECK (status IN ('new', 'reviewing', 'approved', 'rejected',
                                     'active', 'busy', 'archived')),
    completed      INTEGER NOT NULL DEFAULT 0,
    admin_note     TEXT,
    ip             TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_freelancers_status ON freelancers(status, created_at DESC);
CREATE INDEX idx_freelancers_login  ON freelancers(login);

-- ---------- вход фрилансера ----------
-- Отдельно от админских сессий намеренно: у ролей разные права,
-- и общая таблица однажды дала бы админу токен фрилансера и наоборот.
CREATE TABLE freelancer_sessions (
    token_hash    TEXT PRIMARY KEY,
    freelancer_id INTEGER NOT NULL REFERENCES freelancers(id) ON DELETE CASCADE,
    csrf_token    TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at    TEXT NOT NULL
);
CREATE INDEX idx_fsessions_owner ON freelancer_sessions(freelancer_id);

-- ---------- внутренние проекты с заказчиком ----------
CREATE TABLE client_projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    client      TEXT,
    description TEXT,
    budget      TEXT,
    deadline    TEXT,
    status      TEXT NOT NULL DEFAULT 'new'
                CHECK (status IN ('new', 'planning', 'in_progress',
                                  'review', 'completed', 'cancelled')),
    request_id  INTEGER REFERENCES client_requests(id) ON DELETE SET NULL,
    admin_note  TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_cprojects_status ON client_projects(status, created_at DESC);

-- ---------- задачи внутри проекта ----------
CREATE TABLE tasks (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id     INTEGER NOT NULL REFERENCES client_projects(id) ON DELETE CASCADE,
    title          TEXT NOT NULL,
    description    TEXT,
    specialization TEXT,
    skills         TEXT,
    deadline       TEXT,
    price          TEXT,
    status         TEXT NOT NULL DEFAULT 'todo'
                   CHECK (status IN ('todo', 'assigned', 'in_progress', 'review',
                                     'revision', 'completed', 'cancelled')),
    freelancer_id  INTEGER REFERENCES freelancers(id) ON DELETE SET NULL,
    result_text    TEXT,
    result_url     TEXT,
    admin_note     TEXT,
    sort_order     INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_tasks_project ON tasks(project_id, sort_order);
CREATE INDEX idx_tasks_owner   ON tasks(freelancer_id, status);
CREATE INDEX idx_tasks_status  ON tasks(status, updated_at DESC);

-- ---------- история статусов задачи ----------
-- Нужна, чтобы спор «я сдал вовремя» / «нет, не сдавал» решался
-- записями, а не памятью.
CREATE TABLE task_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    from_status TEXT,
    to_status   TEXT NOT NULL,
    actor       TEXT NOT NULL,
    comment     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_history_task ON task_history(task_id, created_at);

-- ---------- уведомления админу ----------
CREATE TABLE notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    title      TEXT NOT NULL,
    entity     TEXT,
    entity_id  INTEGER,
    seen       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_notifications_new ON notifications(seen, created_at DESC);

-- ---------- журнал действий админа ----------
-- Паролей и токенов здесь нет и быть не может: пишутся только
-- действие, сущность и её номер.
CREATE TABLE admin_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id   INTEGER REFERENCES admins(id) ON DELETE SET NULL,
    username   TEXT,
    action     TEXT NOT NULL,
    entity     TEXT,
    entity_id  INTEGER,
    details    TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_adminlog_time ON admin_log(created_at DESC);

-- ---------- тексты страницы Freelance ----------
INSERT INTO site_settings (key, value_ru, value_tj) VALUES
  ('freelance_intro',
   'Присоединяйся к базе специалистов AVERIX. Когда появится подходящий проект, мы сможем предложить тебе работу.',
   'Ба базаи мутахассисони AVERIX ҳамроҳ шав. Вақте лоиҳаи мувофиқ пайдо шавад, мо метавонем ба ту кор пешниҳод кунем.'),
  ('privacy_note',
   'Данные из формы видит только студия. Мы не публикуем их, не передаём третьим лицам и не отдаём через открытый API.',
   'Маълумоти формаро танҳо студия мебинад. Мо онро нашр намекунем, ба шахсони сеюм намедиҳем ва тавассути API кушода намедиҳем.');
