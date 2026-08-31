-- ============================================================
-- AVERIX Freelance — профиль специалиста и портфолио
--
-- Профилем остаётся таблица freelancers: в ней уже есть имя,
-- навыки, рассказ о себе, фотография и занятость. Добавляем то,
-- чего не хватает площадке, и не заводим вторую таблицу про того же
-- человека.
--
-- Разделение, на котором всё держится:
--   user_id IS NULL     — анкета в закрытой базе студии. Такая строка
--                         не попадает в каталог никогда, чем бы ни было
--                         заполнено остальное. Людям, оставившим анкету
--                         под обещанием «мы никого не публикуем», ничего
--                         публиковать нельзя.
--   user_id IS NOT NULL — специалист площадки. Он сам заполняет профиль
--                         и сам решает, показывать ли его.
-- ============================================================

-- ---------- кто вы и в чём ----------
ALTER TABLE freelancers ADD COLUMN title TEXT;
ALTER TABLE freelancers ADD COLUMN category_id INTEGER
       REFERENCES fl_categories(id) ON DELETE SET NULL;
ALTER TABLE freelancers ADD COLUMN level TEXT NOT NULL DEFAULT 'middle'
       CHECK (level IN ('junior', 'middle', 'senior', 'expert'));

-- ---------- деньги ----------
-- Целые в минорных единицах (дирамах). Дробное в деньгах — способ
-- однажды получить 0.1 + 0.2 = 0.30000000000000004 в счёте.
-- Старая колонка rate остаётся текстовой: ею пользуется закрытая база
-- студии, и переписывать её задним числом нечем — там свободный текст.
ALTER TABLE freelancers ADD COLUMN rate_hour INTEGER;
ALTER TABLE freelancers ADD COLUMN rate_project_min INTEGER;

-- ---------- показ в каталоге ----------
-- Ось, отдельная от status. status — отношения студии с человеком,
-- listing — его собственное согласие быть на сайте.
--   draft     — профиль ещё заполняется, никому не виден
--   pending   — попросил публикацию, студия ещё не смотрела
--   published — виден в каталоге
--   rejected  — студия отказала, причина в admin_note
ALTER TABLE freelancers ADD COLUMN listing TEXT NOT NULL DEFAULT 'draft'
       CHECK (listing IN ('draft', 'pending', 'published', 'rejected'));
ALTER TABLE freelancers ADD COLUMN public_slug TEXT;
ALTER TABLE freelancers ADD COLUMN listed_at TEXT;
ALTER TABLE freelancers ADD COLUMN published_at TEXT;

CREATE UNIQUE INDEX idx_freelancers_pubslug ON freelancers(public_slug)
       WHERE public_slug IS NOT NULL;
CREATE INDEX idx_freelancers_listing ON freelancers(listing, category_id);

-- Все существующие анкеты остаются черновиками и вне каталога.
-- Строка ничего не меняет (умолчание уже 'draft') и оставлена нарочно:
-- это то место, куда посмотрит человек, который спросит «а старые
-- анкеты точно не всплыли?».
UPDATE freelancers SET listing = 'draft' WHERE listing IS NULL;

-- ---------- портфолио ----------
CREATE TABLE fl_portfolio (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    freelancer_id  INTEGER NOT NULL REFERENCES freelancers(id) ON DELETE CASCADE,
    title          TEXT NOT NULL,
    description    TEXT,
    category_id    INTEGER REFERENCES fl_categories(id) ON DELETE SET NULL,
    tech           TEXT,
    url            TEXT,
    cover_image_id INTEGER,
    sort_order     INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_fl_portfolio_owner ON fl_portfolio(freelancer_id, sort_order);

CREATE TABLE fl_portfolio_images (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id    INTEGER NOT NULL REFERENCES fl_portfolio(id) ON DELETE CASCADE,
    filename   TEXT NOT NULL,
    width      INTEGER,
    height     INTEGER,
    bytes      INTEGER,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_fl_portfolio_images ON fl_portfolio_images(item_id, sort_order);

-- ---------- настройки площадки ----------
INSERT INTO site_settings (key, value_ru, value_tj) VALUES
  ('freelance_currency', 'сомони', 'сомонӣ'),
  ('freelance_currency_short', 'смн', 'смн');
