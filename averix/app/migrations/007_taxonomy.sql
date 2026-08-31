-- ============================================================
-- AVERIX Freelance — категории и навыки
--
-- Два справочника, которыми управляет администратор, а не код.
-- Захардкоженный список категорий живёт ровно до первого «а добавьте
-- ещё вот такую» — и дальше требует правки кода и деплоя ради одной
-- строки текста.
--
-- Навык опознаётся по slug, а не по написанию. React, react и REACT
-- дают один и тот же slug «react» и попадают в одну строку. Разные
-- написания вроде «React.js» останутся отдельными — их администратор
-- сливает вручную, и связи специалистов при этом переезжают.
-- ============================================================

-- ---------- категории и подкатегории ----------
-- Одна таблица со ссылкой на саму себя: у категории есть родитель
-- или его нет. Двух уровней достаточно, третий тут не нужен никому.
CREATE TABLE fl_categories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id  INTEGER REFERENCES fl_categories(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    slug       TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    enabled    INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_fl_categories_parent ON fl_categories(parent_id, sort_order);

-- ---------- навыки ----------
--   pending — навык завёл пользователь, администратор ещё не смотрел:
--             в анкете он уже работает, в фильтрах каталога — нет
--   active  — проверен, участвует в фильтрах
--   hidden  — отключён или слит с другим (см. merged_into_id)
--
-- Закрытый список тут не годится: человек с настоящим редким навыком
-- не должен упираться в «такого варианта нет». Открытый без разбора —
-- тоже: через месяц в фильтрах двадцать написаний одного слова.
CREATE TABLE fl_skills (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    slug           TEXT NOT NULL UNIQUE,
    category_id    INTEGER REFERENCES fl_categories(id) ON DELETE SET NULL,
    status         TEXT NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending', 'active', 'hidden')),
    merged_into_id INTEGER REFERENCES fl_skills(id) ON DELETE SET NULL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_fl_skills_status ON fl_skills(status, name);

-- ---------- навыки специалиста ----------
CREATE TABLE fl_freelancer_skills (
    freelancer_id INTEGER NOT NULL REFERENCES freelancers(id) ON DELETE CASCADE,
    skill_id      INTEGER NOT NULL REFERENCES fl_skills(id) ON DELETE CASCADE,
    PRIMARY KEY (freelancer_id, skill_id)
);
CREATE INDEX idx_fl_fs_skill ON fl_freelancer_skills(skill_id);

-- ============================================================
-- Начальное наполнение справочников
--
-- Это не выдуманный контент, а словарь: названия направлений
-- и технологий. Ни одного человека, проекта или отзыва здесь нет.
-- Всё это администратор может переименовать, отключить или дополнить.
-- ============================================================

INSERT INTO fl_categories (id, parent_id, name, slug, sort_order) VALUES
  (1, NULL, 'Разработка', 'razrabotka', 1),
  (2, NULL, 'Дизайн',     'dizayn',     2),
  (3, NULL, 'Маркетинг',  'marketing',  3),
  (4, NULL, 'Контент',    'kontent',    4),
  (5, NULL, 'Другое',     'drugoe',     5);

INSERT INTO fl_categories (parent_id, name, slug, sort_order) VALUES
  (1, 'Frontend',              'frontend',      1),
  (1, 'Backend',               'backend',       2),
  (1, 'Fullstack',             'fullstack',     3),
  (1, 'Telegram-боты',         'telegram-boty', 4),
  (1, 'Мобильная разработка',  'mobilnaya',     5),
  (1, 'DevOps',                'devops',        6),
  (1, 'AI и машинное обучение','ai',            7),
  (1, 'Тестирование',          'testirovanie',  8),
  (1, 'WordPress',             'wordpress',     9),

  (2, 'UI/UX',                 'ui-ux',         1),
  (2, 'Графический дизайн',    'grafika',       2),
  (2, 'Логотип и фирстиль',    'logotip',       3),
  (2, '3D',                    '3d',            4),

  (3, 'SMM',                   'smm',           1),
  (3, 'SEO',                   'seo',           2),
  (3, 'Таргетированная реклама','targeting',    3),

  (4, 'Видео',                 'video',         1),
  (4, 'Копирайтинг',           'kopirayting',   2),
  (4, 'Перевод',               'perevod',       3);

INSERT INTO fl_skills (name, slug, category_id, status) VALUES
  ('HTML',          'html',          1, 'active'),
  ('CSS',           'css',           1, 'active'),
  ('JavaScript',    'javascript',    1, 'active'),
  ('TypeScript',    'typescript',    1, 'active'),
  ('React',         'react',         1, 'active'),
  ('Vue',           'vue',           1, 'active'),
  ('Next.js',       'next-js',       1, 'active'),
  ('Python',        'python',        1, 'active'),
  ('Django',        'django',        1, 'active'),
  ('FastAPI',       'fastapi',       1, 'active'),
  ('PHP',           'php',           1, 'active'),
  ('Laravel',       'laravel',       1, 'active'),
  ('Node.js',       'node-js',       1, 'active'),
  ('Go',            'go',            1, 'active'),
  ('C#',            'c-sharp',       1, 'active'),
  ('Java',          'java',          1, 'active'),
  ('Kotlin',        'kotlin',        1, 'active'),
  ('Swift',         'swift',         1, 'active'),
  ('Flutter',       'flutter',       1, 'active'),
  ('PostgreSQL',    'postgresql',    1, 'active'),
  ('MySQL',         'mysql',         1, 'active'),
  ('SQLite',        'sqlite',        1, 'active'),
  ('MongoDB',       'mongodb',       1, 'active'),
  ('Redis',         'redis',         1, 'active'),
  ('Docker',        'docker',        1, 'active'),
  ('Linux',         'linux',         1, 'active'),
  ('Nginx',         'nginx',         1, 'active'),
  ('Git',           'git',           1, 'active'),
  ('Telegram API',  'telegram-api',  1, 'active'),
  ('aiogram',       'aiogram',       1, 'active'),
  ('1С',            '1s',            1, 'active'),
  ('Figma',         'figma',         2, 'active'),
  ('Adobe Photoshop','photoshop',    2, 'active'),
  ('Adobe Illustrator','illustrator',2, 'active'),
  ('Blender',       'blender',       2, 'active'),
  ('After Effects', 'after-effects', 4, 'active'),
  ('Premiere Pro',  'premiere-pro',  4, 'active'),
  ('Копирайтинг',   'kopirayting-skill', 4, 'active'),
  ('Google Ads',    'google-ads',    3, 'active'),
  ('Meta Ads',      'meta-ads',      3, 'active');
