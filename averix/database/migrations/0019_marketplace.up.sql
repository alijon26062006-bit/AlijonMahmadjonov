-- 0019 marketplace: from a developer marketplace to a marketplace for every
-- kind of freelance work, in Russian.
--
-- Three things happen here and they are deliberately in one migration,
-- because none of them makes sense without the others:
--
--   1. The category tree gets a top level of *sectors* — IT, design, texts,
--      SEO, social, media, business, education — and everything that existed
--      moves under the IT sector. The tree allows four levels; IT already used
--      three, so it becomes the deepest branch and nothing else needs to be.
--   2. Every name a user sees is in Russian. Technology names stay as they
--      are (React is React), profession names and category names do not.
--   3. Non-IT professions, categories and skills arrive, together with the
--      links that decide whose feed a project reaches and which skills a
--      profession is asked about. Without those links a design brief would
--      be visible to nobody.
--
-- Reference data, not seed data: this ships to production.

-- ── Language ────────────────────────────────────────────────────────────────
ALTER TABLE users ALTER COLUMN locale SET DEFAULT 'ru';
UPDATE users SET locale = 'ru' WHERE locale = 'en';

-- Full-text search stems Russian. 'simple' stays for titles so a technology
-- name is matched exactly, and the description gets the Russian dictionary.
CREATE OR REPLACE FUNCTION projects_refresh_search_doc() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.search_doc :=
      setweight(to_tsvector('simple',  coalesce(NEW.title, '')), 'A')
   || setweight(to_tsvector('russian', coalesce(NEW.title, '')), 'A')
   || setweight(to_tsvector('simple',  coalesce(NEW.summary, '')), 'B')
   || setweight(to_tsvector('russian', coalesce(NEW.summary, '')), 'B')
   || setweight(to_tsvector('russian', coalesce(NEW.description, '')), 'C');
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION services_refresh_search_doc() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.search_doc :=
      setweight(to_tsvector('simple',  coalesce(NEW.title, '')), 'A')
   || setweight(to_tsvector('russian', coalesce(NEW.title, '')), 'A')
   || setweight(to_tsvector('simple',  coalesce(NEW.summary, '')), 'B')
   || setweight(to_tsvector('russian', coalesce(NEW.summary, '')), 'B')
   || setweight(to_tsvector('russian', coalesce(NEW.description, '')), 'C');
  RETURN NEW;
END;
$$;

-- Re-index what already exists under the new configuration.
UPDATE projects SET title = title;
UPDATE services SET title = title;

-- ── 1. Sectors ──────────────────────────────────────────────────────────────
-- Everything that exists today is IT work, so the whole tree moves down one
-- level first, then the sectors are inserted above it.
UPDATE categories SET path = 'it/' || path, depth = depth + 1;

INSERT INTO categories (slug, name, description, path, depth, sort_order) VALUES
  ('it',        'Разработка и IT',           'Сайты, приложения, боты, интеграции, серверы и всё, что работает на коде.', 'it', 0, 10),
  ('design',    'Дизайн',                    'Логотипы, интерфейсы, полиграфия, иллюстрации, 3D и оформление.',           'design', 0, 20),
  ('texts',     'Тексты и переводы',         'Копирайтинг, статьи, редактура, переводы и сценарии.',                     'texts', 0, 30),
  ('seo',       'SEO и трафик',              'Продвижение сайтов, контекстная реклама, аналитика и аудит.',              'seo', 0, 40),
  ('smm',       'Соцсети и реклама',         'Ведение соцсетей, таргет, контент и продвижение каналов.',                 'smm', 0, 50),
  ('media',     'Аудио, видео и съёмка',     'Монтаж, анимация, озвучка, музыка, обработка фото и видео.',               'media', 0, 60),
  ('business',  'Бизнес и жизнь',            'Бухгалтерия, юристы, аналитика, ассистенты, поиск данных и HR.',           'business', 0, 70),
  ('education', 'Обучение и консультации',   'Репетиторы, IT-консультации, языки, карьера и творчество.',                'education', 0, 80);

UPDATE categories c SET parent_id = it.id
FROM categories it
WHERE it.slug = 'it' AND c.depth = 1 AND c.parent_id IS NULL AND c.slug <> 'it';

-- ── 2. Russian names for what already exists ────────────────────────────────
UPDATE specialisations sp SET name = v.name, short_name = v.short_name, description = v.description
FROM (VALUES
  ('backend-developer',       'Бэкенд-разработчик',              'Бэкенд',    'Серверная логика, API, данные и надёжность.'),
  ('frontend-developer',      'Фронтенд-разработчик',            'Фронтенд',  'Интерфейсы, состояние, скорость и доступность в браузере.'),
  ('fullstack-developer',     'Fullstack-разработчик',           'Fullstack', 'Продукт целиком — от интерфейса до сервера.'),
  ('telegram-developer',      'Разработчик Telegram-ботов',      'Telegram',  'Боты, Mini Apps и платежи в Telegram.'),
  ('mobile-developer',        'Мобильный разработчик',           'Мобильные', 'iOS, Android и кроссплатформенные приложения.'),
  ('ai-automation-developer', 'Разработчик ИИ и автоматизации',  'ИИ',        'Интеграция моделей, агенты, пайплайны и автоматизация процессов.'),
  ('devops-engineer',         'DevOps-инженер',                  'DevOps',    'CI/CD, контейнеры, мониторинг и инфраструктура.'),
  ('ui-ux-designer',          'UI/UX-дизайнер',                  'UI/UX',     'Интерфейсы и взаимодействие в цифровых продуктах.')
) AS v(slug, name, short_name, description)
WHERE sp.slug = v.slug;

UPDATE categories c SET name = v.name, description = v.description
FROM (VALUES
  ('backend-development',  'Бэкенд-разработка',          'API, сервисы, работа с данными и серверная бизнес-логика.'),
  ('frontend-development', 'Фронтенд-разработка',        'Интерфейсы в браузере на современных фреймворках.'),
  ('fullstack-development','Fullstack-разработка',       'Продукт целиком: интерфейс и сервер.'),
  ('telegram-bots',        'Telegram-боты',              'Чат-боты, продажи в мессенджере и автоматизация Telegram.'),
  ('telegram-mini-apps',   'Telegram Mini Apps',         'Веб-приложения, которые открываются внутри Telegram.'),
  ('mobile-applications',  'Мобильные приложения',       'Нативные и кроссплатформенные приложения для телефонов и планшетов.'),
  ('ai-automation',        'ИИ и автоматизация',         'Интеграция моделей, агенты, пайплайны данных и автоматизация.'),
  ('api-development',      'Разработка API',             'Публичные и внутренние API, SDK и проектирование контрактов.'),
  ('web-applications',     'Веб-приложения',             'Панели, порталы и внутренние инструменты в браузере.'),
  ('saas',                 'SaaS',                       'Подписочные продукты, биллинг и онбординг.'),
  ('ecommerce',            'Интернет-магазины',          'Витрины, корзины, оплата, каталог и доставка.'),
  ('devops',               'DevOps',                     'CI/CD, контейнеры, автоматизация деплоя и мониторинг.'),
  ('infrastructure',       'Инфраструктура',             'Серверы, сети, базы данных и облачная архитектура.'),
  ('ui-ux-digital',        'UI/UX цифровых продуктов',   'Интерфейсы и взаимодействие для сайтов и приложений.'),
  ('integrations',         'Интеграции',                 'Сторонние API, платёжные шлюзы, CRM и синхронизация данных.'),
  ('ai-llm-integration',   'Интеграция LLM',             NULL),
  ('ai-agents',            'Агенты и инструменты',       NULL),
  ('ai-data-pipelines',    'Пайплайны данных',           NULL),
  ('ai-computer-vision',   'Компьютерное зрение',        NULL),
  ('ai-workflow-automation','Автоматизация процессов',   NULL),
  ('telegram-commerce-bot','Бот для продаж',             NULL),
  ('telegram-service-bot', 'Сервисный бот',              NULL),
  ('telegram-admin-bot',   'Администрирование и модерация', NULL),
  ('devops-containers',    'Контейнеры и оркестрация',   NULL),
  ('devops-observability', 'Мониторинг',                 NULL),
  ('infra-cloud',          'Облачная архитектура',       NULL),
  ('infra-databases',      'Базы данных',                NULL),
  ('infra-networking',     'Сети и безопасность',        NULL),
  ('go-stdlib',            'Стандартная библиотека',     NULL)
) AS v(slug, name, description)
WHERE c.slug = v.slug;

UPDATE skills s SET name = v.name
FROM (VALUES
  ('testing',       'Автоматизированное тестирование'),
  ('accessibility', 'Доступность'),
  ('performance',   'Оптимизация производительности'),
  ('security',      'Безопасность приложений'),
  ('s3',            'S3-совместимое хранилище')
) AS v(slug, name)
WHERE s.slug = v.slug;

-- ── 3. Professions outside IT ───────────────────────────────────────────────
INSERT INTO specialisations (slug, name, short_name, description, sort_order) VALUES
  ('graphic-designer',   'Графический дизайнер',          'Графика',     'Логотипы, айдентика, полиграфия и рекламные материалы.', 110),
  ('web-designer',       'Веб-дизайнер',                  'Веб-дизайн',  'Лендинги, сайты и макеты страниц.', 120),
  ('illustrator',        'Иллюстратор',                   'Иллюстрация', 'Рисованные и векторные иллюстрации, персонажи, стикеры.', 130),
  ('motion-designer',    'Моушн-дизайнер',                'Моушн',       'Анимация, интро, заставки и анимированная графика.', 140),
  ('3d-artist',          '3D-художник',                   '3D',          'Моделирование, визуализация и рендер.', 150),
  ('copywriter',         'Копирайтер',                    'Тексты',      'Продающие и информационные тексты, статьи, описания.', 210),
  ('editor',             'Редактор',                      'Редактура',   'Редактура, корректура и подготовка текстов к публикации.', 220),
  ('translator',         'Переводчик',                    'Перевод',     'Письменный перевод, локализация и вычитка.', 230),
  ('seo-specialist',     'SEO-специалист',                'SEO',         'Продвижение сайтов в поиске, аудит и семантика.', 310),
  ('ppc-specialist',     'Специалист по контекстной рекламе', 'Контекст', 'Яндекс Директ, Google Ads, аналитика кампаний.', 320),
  ('smm-manager',        'SMM-менеджер',                  'SMM',         'Ведение соцсетей, контент-план, вовлечение аудитории.', 410),
  ('targetologist',      'Таргетолог',                    'Таргет',      'Таргетированная реклама в соцсетях и мессенджерах.', 420),
  ('marketer',           'Маркетолог',                    'Маркетинг',   'Стратегия, позиционирование, воронки и аналитика.', 430),
  ('video-editor',       'Видеомонтажёр',                 'Монтаж',      'Монтаж роликов, цветокоррекция, обработка звука.', 510),
  ('voice-actor',        'Диктор',                        'Озвучка',     'Озвучка роликов, рекламы, аудиокниг и IVR.', 520),
  ('sound-designer',     'Звукорежиссёр',                 'Звук',        'Сведение, мастеринг, музыка и звуковой дизайн.', 530),
  ('photographer',       'Фотограф и ретушёр',            'Фото',        'Съёмка и обработка фотографий.', 540),
  ('accountant',         'Бухгалтер',                     'Бухгалтерия', 'Учёт, отчётность, налоги для бизнеса и ИП.', 610),
  ('lawyer',             'Юрист',                         'Право',       'Договоры, консультации, регистрация и претензии.', 620),
  ('business-analyst',   'Бизнес-аналитик',               'Аналитика',   'Требования, процессы, финансовые модели и отчёты.', 630),
  ('virtual-assistant',  'Личный ассистент',              'Ассистент',   'Административная поддержка, поиск, сбор данных, переписка.', 640),
  ('hr-recruiter',       'HR-специалист',                 'HR',          'Подбор персонала, описания вакансий и собеседования.', 650),
  ('tutor',              'Репетитор',                     'Обучение',    'Индивидуальные занятия и консультации.', 710);

-- ── 4. Categories outside IT ────────────────────────────────────────────────
INSERT INTO categories (parent_id, slug, name, description, path, depth, sort_order)
SELECT p.id, v.slug, v.name, v.description, p.path || '/' || v.leaf, 1, v.sort_order
FROM (VALUES
  -- Дизайн
  ('design', 'design-logo',          'Логотипы и фирменный стиль',   'Логотип, айдентика, брендбук.',                               'logo', 10),
  ('design', 'design-web',           'Веб-дизайн и интерфейсы',      'Лендинги, сайты, мобильные и веб-интерфейсы.',                'web', 20),
  ('design', 'design-social',        'Дизайн для соцсетей',          'Оформление профилей, посты, сторис, обложки.',                'social', 30),
  ('design', 'design-banners',       'Баннеры и реклама',            'Рекламные креативы, баннеры для сайтов и сетей.',             'banners', 40),
  ('design', 'design-print',         'Полиграфия',                   'Визитки, листовки, буклеты, упаковка.',                       'print', 50),
  ('design', 'design-illustration',  'Иллюстрации и персонажи',      'Иллюстрации, стикеры, персонажи, маскоты.',                   'illustration', 60),
  ('design', 'design-presentations', 'Презентации',                  'Презентации для инвесторов, продаж и обучения.',              'presentations', 70),
  ('design', 'design-3d',            '3D и визуализация',            'Моделирование, интерьеры, рендер продукта.',                  '3d', 80),
  ('design', 'design-marketplace',   'Оформление маркетплейсов',     'Карточки товаров для Wildberries, Ozon и других площадок.',   'marketplace', 90),
  -- Тексты и переводы
  ('texts', 'texts-copywriting',     'Копирайтинг',                  'Тексты для сайтов, рассылок и рекламы.',                      'copywriting', 10),
  ('texts', 'texts-articles',        'Статьи и контент',             'Статьи, обзоры, блоги и контент-планы.',                      'articles', 20),
  ('texts', 'texts-sales',           'Продающие тексты',             'Лендинги, коммерческие предложения, офферы.',                 'sales', 30),
  ('texts', 'texts-editing',         'Редактура и корректура',       'Правка, вычитка, приведение к стилю.',                        'editing', 40),
  ('texts', 'texts-translation',     'Переводы',                     'Перевод документов, сайтов, субтитров и приложений.',         'translation', 50),
  ('texts', 'texts-scripts',         'Сценарии',                     'Сценарии для роликов, рекламы и подкастов.',                  'scripts', 60),
  ('texts', 'texts-business',        'Деловые тексты и резюме',      'Резюме, письма, описания вакансий, документы.',               'business', 70),
  ('texts', 'texts-content-filling', 'Наполнение сайтов',            'Внесение и оформление контента, карточки товаров.',           'content-filling', 80),
  -- SEO и трафик
  ('seo', 'seo-optimisation',        'SEO-продвижение',              'Внутренняя и внешняя оптимизация, рост позиций.',             'optimisation', 10),
  ('seo', 'seo-audit',               'Аудит сайта',                  'Технический и SEO-аудит с планом правок.',                    'audit', 20),
  ('seo', 'seo-semantics',           'Семантическое ядро',           'Сбор и кластеризация запросов.',                              'semantics', 30),
  ('seo', 'seo-links',               'Ссылки и упоминания',          'Ссылочное продвижение и крауд-маркетинг.',                    'links', 40),
  ('seo', 'seo-context',             'Контекстная реклама',          'Яндекс Директ и Google Ads: настройка и ведение.',            'context', 50),
  ('seo', 'seo-analytics',           'Веб-аналитика',                'Метрика, GA4, цели, сквозная аналитика.',                     'analytics', 60),
  -- Соцсети и реклама
  ('smm', 'smm-management',          'Ведение соцсетей',             'Контент-план, публикации, общение с аудиторией.',             'management', 10),
  ('smm', 'smm-targeting',           'Таргетированная реклама',      'Настройка и ведение рекламы в соцсетях.',                     'targeting', 20),
  ('smm', 'smm-content',             'Контент для соцсетей',         'Посты, сторис, рилсы и визуал.',                              'content', 30),
  ('smm', 'smm-telegram',            'Продвижение в Telegram',       'Каналы, чаты, посевы и Telegram Ads.',                        'telegram', 40),
  ('smm', 'smm-youtube',             'YouTube и видеоплатформы',     'Продвижение каналов, оформление, стратегия.',                 'youtube', 50),
  ('smm', 'smm-email',               'Рассылки',                     'Email- и мессенджер-рассылки, цепочки писем.',                'email', 60),
  ('smm', 'smm-influence',           'Инфлюенс-маркетинг',           'Подбор блогеров и интеграции.',                               'influence', 70),
  -- Аудио, видео и съёмка
  ('media', 'media-video-editing',   'Видеомонтаж',                  'Монтаж роликов, рилсов, обзоров и рекламы.',                  'video-editing', 10),
  ('media', 'media-motion',          'Анимация и моушн',             'Анимированная графика, интро, заставки, объясняющие ролики.', 'motion', 20),
  ('media', 'media-voiceover',       'Озвучка и дикторы',            'Голос для роликов, рекламы, IVR и аудиокниг.',               'voiceover', 30),
  ('media', 'media-music',           'Музыка и звук',                'Композиции, джинглы, сведение и мастеринг.',                  'music', 40),
  ('media', 'media-photo',           'Обработка фото',               'Ретушь, цветокоррекция, предметная обработка.',               'photo', 50),
  ('media', 'media-shooting',        'Видео- и фотосъёмка',          'Съёмка на месте: реклама, продукт, мероприятия.',             'shooting', 60),
  ('media', 'media-transcription',   'Субтитры и транскрибация',     'Расшифровка аудио, субтитры, тайминг.',                       'transcription', 70),
  -- Бизнес и жизнь
  ('business', 'business-accounting','Бухгалтерия и финансы',        'Учёт, отчётность, налоги, финансовые модели.',                'accounting', 10),
  ('business', 'business-legal',     'Юридические услуги',           'Договоры, претензии, регистрация, консультации.',             'legal', 20),
  ('business', 'business-plans',     'Бизнес-планы и презентации',   'Бизнес-планы, инвестиционные презентации, unit-экономика.',   'plans', 30),
  ('business', 'business-analytics', 'Аналитика и исследования',     'Анализ рынка, конкурентов, требований и данных.',             'analytics', 40),
  ('business', 'business-assistant', 'Личный ассистент',             'Административные задачи, переписка, планирование.',           'assistant', 50),
  ('business', 'business-data',      'Сбор и обработка данных',      'Парсинг, базы контактов, таблицы, ввод данных.',              'data', 60),
  ('business', 'business-hr',        'HR и подбор персонала',        'Поиск кандидатов, вакансии, собеседования.',                  'hr', 70),
  ('business', 'business-consulting','Консультации для бизнеса',     'Стратегия, процессы, запуск продукта.',                       'consulting', 80),
  -- Обучение и консультации
  ('education', 'education-tutoring','Репетиторы',                   'Школьные и вузовские предметы, подготовка к экзаменам.',      'tutoring', 10),
  ('education', 'education-it',      'IT-консультации и код-ревью',  'Разбор кода, архитектуры, менторство.',                       'it', 20),
  ('education', 'education-languages','Иностранные языки',           'Занятия с преподавателем и разговорная практика.',            'languages', 30),
  ('education', 'education-creative','Дизайн и творчество',          'Обучение дизайну, рисунку, музыке и монтажу.',                'creative', 40),
  ('education', 'education-career',  'Карьера и коучинг',            'Резюме, собеседования, карьерные консультации.',              'career', 50)
) AS v(parent_slug, slug, name, description, leaf, sort_order)
JOIN categories p ON p.slug = v.parent_slug;

-- ── 5. Skills outside IT ────────────────────────────────────────────────────
-- Tools are what a person works in; practices are what they can do. Both
-- appear on a profile and both are searchable, which is why an SMM manager
-- is asked about Canva and about контент-план in the same step.
INSERT INTO skills (slug, name, kind, github_aliases, manifest_hints, colour) VALUES
  -- Инструменты дизайна и медиа
  ('photoshop',        'Adobe Photoshop',     'tool', '{}', '{}', '#31A8FF'),
  ('adobe-illustrator','Adobe Illustrator',   'tool', '{}', '{}', '#FF9A00'),
  ('indesign',         'Adobe InDesign',      'tool', '{}', '{}', '#FF3366'),
  ('after-effects',    'After Effects',       'tool', '{}', '{}', '#9999FF'),
  ('premiere-pro',     'Premiere Pro',        'tool', '{}', '{}', '#9999FF'),
  ('davinci-resolve',  'DaVinci Resolve',     'tool', '{}', '{}', '#233A5E'),
  ('capcut',           'CapCut',              'tool', '{}', '{}', '#000000'),
  ('blender',          'Blender',             'tool', '{}', '{}', '#F5792A'),
  ('cinema-4d',        'Cinema 4D',           'tool', '{}', '{}', '#011A6A'),
  ('lightroom',        'Lightroom',           'tool', '{}', '{}', '#31A8FF'),
  ('canva',            'Canva',               'tool', '{}', '{}', '#00C4CC'),
  ('sketch',           'Sketch',              'tool', '{}', '{}', '#F7B500'),
  ('procreate',        'Procreate',           'tool', '{}', '{}', '#1E1E1E'),
  ('audacity',         'Audacity',            'tool', '{}', '{}', '#0000CC'),
  ('ableton',          'Ableton Live',        'tool', '{}', '{}', '#000000'),
  ('fl-studio',        'FL Studio',           'tool', '{}', '{}', '#F7A21B'),
  ('midjourney',       'Midjourney',          'tool', '{}', '{}', '#111111'),
  ('stable-diffusion', 'Stable Diffusion',    'tool', '{}', '{}', '#7C3AED'),
  ('chatgpt',          'ChatGPT',             'tool', '{}', '{}', '#10A37F'),
  -- Платформы и сервисы
  ('tilda',            'Tilda',               'platform', '{}', '{}', '#000000'),
  ('wordpress',        'WordPress',           'platform', '{}', '{wp-config.php}', '#21759B'),
  ('wix',              'Wix',                 'platform', '{}', '{}', '#0C6EFC'),
  ('bitrix24',         'Битрикс24',           'platform', '{}', '{}', '#2FC7F7'),
  ('amocrm',           'amoCRM',              'platform', '{}', '{}', '#4C8BF5'),
  ('1c',               '1С',                  'platform', '{}', '{}', '#E31E24'),
  ('yandex-direct',    'Яндекс Директ',       'platform', '{}', '{}', '#FC3F1D'),
  ('google-ads',       'Google Ads',          'platform', '{}', '{}', '#4285F4'),
  ('yandex-metrika',   'Яндекс Метрика',      'platform', '{}', '{}', '#FC3F1D'),
  ('google-analytics', 'Google Analytics',    'platform', '{}', '{}', '#E37400'),
  ('vk-ads',           'VK Реклама',          'platform', '{}', '{}', '#0077FF'),
  ('telegram-ads',     'Telegram Ads',        'platform', '{}', '{}', '#26A5E4'),
  ('meta-ads',         'Meta Ads',            'platform', '{}', '{}', '#0866FF'),
  ('youtube',          'YouTube',             'platform', '{}', '{}', '#FF0000'),
  ('tiktok',           'TikTok',              'platform', '{}', '{}', '#000000'),
  ('vk',               'ВКонтакте',           'platform', '{}', '{}', '#0077FF'),
  ('unisender',        'Unisender',           'platform', '{}', '{}', '#4B2AAD'),
  ('mailchimp',        'Mailchimp',           'platform', '{}', '{}', '#FFE01B'),
  ('notion',           'Notion',              'platform', '{}', '{}', '#000000'),
  ('google-sheets',    'Google Таблицы',      'platform', '{}', '{}', '#34A853'),
  ('excel',            'Excel',               'platform', '{}', '{}', '#217346'),
  ('wildberries',      'Wildberries',         'platform', '{}', '{}', '#CB11AB'),
  ('ozon',             'Ozon',                'platform', '{}', '{}', '#005BFF'),
  -- Навыки
  ('copywriting',      'Копирайтинг',                 'practice', '{}', '{}', '#6B7280'),
  ('editing',          'Редактура и корректура',      'practice', '{}', '{}', '#6B7280'),
  ('storytelling',     'Сторителлинг',                'practice', '{}', '{}', '#6B7280'),
  ('english',          'Английский язык',             'practice', '{}', '{}', '#6B7280'),
  ('german',           'Немецкий язык',               'practice', '{}', '{}', '#6B7280'),
  ('chinese',          'Китайский язык',              'practice', '{}', '{}', '#6B7280'),
  ('turkish',          'Турецкий язык',               'practice', '{}', '{}', '#6B7280'),
  ('uzbek',            'Узбекский язык',              'practice', '{}', '{}', '#6B7280'),
  ('seo',              'SEO',                         'practice', '{}', '{}', '#6B7280'),
  ('ppc',              'Контекстная реклама',         'practice', '{}', '{}', '#6B7280'),
  ('targeting',        'Таргетированная реклама',     'practice', '{}', '{}', '#6B7280'),
  ('smm',              'SMM',                         'practice', '{}', '{}', '#6B7280'),
  ('content-planning', 'Контент-план',                'practice', '{}', '{}', '#6B7280'),
  ('email-marketing',  'Email-маркетинг',             'practice', '{}', '{}', '#6B7280'),
  ('branding',         'Брендинг и айдентика',        'practice', '{}', '{}', '#6B7280'),
  ('typography',       'Типографика',                 'practice', '{}', '{}', '#6B7280'),
  ('ux-research',      'UX-исследования',             'practice', '{}', '{}', '#6B7280'),
  ('prototyping',      'Прототипирование',            'practice', '{}', '{}', '#6B7280'),
  ('illustration',     'Иллюстрация',                 'practice', '{}', '{}', '#6B7280'),
  ('3d-modelling',     '3D-моделирование',            'practice', '{}', '{}', '#6B7280'),
  ('motion-graphics',  'Моушн-графика',               'practice', '{}', '{}', '#6B7280'),
  ('video-editing',    'Видеомонтаж',                 'practice', '{}', '{}', '#6B7280'),
  ('color-grading',    'Цветокоррекция',              'practice', '{}', '{}', '#6B7280'),
  ('voice-over',       'Дикторская озвучка',          'practice', '{}', '{}', '#6B7280'),
  ('sound-design',     'Звуковой дизайн',             'practice', '{}', '{}', '#6B7280'),
  ('mixing-mastering', 'Сведение и мастеринг',        'practice', '{}', '{}', '#6B7280'),
  ('photo-retouching', 'Ретушь',                      'practice', '{}', '{}', '#6B7280'),
  ('photography',      'Фотосъёмка',                  'practice', '{}', '{}', '#6B7280'),
  ('accounting',       'Бухгалтерский учёт',          'practice', '{}', '{}', '#6B7280'),
  ('taxes',            'Налоги и отчётность',         'practice', '{}', '{}', '#6B7280'),
  ('contract-law',     'Договорное право',            'practice', '{}', '{}', '#6B7280'),
  ('financial-modelling','Финансовое моделирование',  'practice', '{}', '{}', '#6B7280'),
  ('market-research',  'Анализ рынка',                'practice', '{}', '{}', '#6B7280'),
  ('data-entry',       'Сбор и ввод данных',          'practice', '{}', '{}', '#6B7280'),
  ('web-scraping',     'Парсинг данных',              'practice', '{}', '{}', '#6B7280'),
  ('recruiting',       'Подбор персонала',            'practice', '{}', '{}', '#6B7280'),
  ('project-management','Управление проектами',       'practice', '{}', '{}', '#6B7280'),
  ('presentations',    'Презентации',                 'practice', '{}', '{}', '#6B7280'),
  ('teaching',         'Преподавание',                'practice', '{}', '{}', '#6B7280'),
  ('mentoring',        'Менторство',                  'practice', '{}', '{}', '#6B7280'),
  ('transcription',    'Транскрибация',               'practice', '{}', '{}', '#6B7280'),
  ('subtitling',       'Субтитры',                    'practice', '{}', '{}', '#6B7280');

-- ── 6. Profession -> skills ─────────────────────────────────────────────────
INSERT INTO specialisation_skills (specialisation_id, skill_id, is_core)
SELECT sp.id, sk.id, v.core
FROM (VALUES
  ('graphic-designer','photoshop',true),('graphic-designer','adobe-illustrator',true),('graphic-designer','indesign',false),
  ('graphic-designer','figma',true),('graphic-designer','canva',false),('graphic-designer','branding',true),
  ('graphic-designer','typography',true),('graphic-designer','midjourney',false),('graphic-designer','presentations',false),
  ('web-designer','figma',true),('web-designer','tilda',true),('web-designer','photoshop',false),('web-designer','wordpress',false),
  ('web-designer','wix',false),('web-designer','prototyping',true),('web-designer','ux-research',false),('web-designer','typography',false),
  ('illustrator','procreate',true),('illustrator','adobe-illustrator',true),('illustrator','photoshop',true),
  ('illustrator','illustration',true),('illustrator','midjourney',false),('illustrator','stable-diffusion',false),
  ('motion-designer','after-effects',true),('motion-designer','motion-graphics',true),('motion-designer','cinema-4d',false),
  ('motion-designer','blender',false),('motion-designer','premiere-pro',false),('motion-designer','figma',false),
  ('3d-artist','blender',true),('3d-artist','cinema-4d',true),('3d-artist','3d-modelling',true),('3d-artist','photoshop',false),
  ('copywriter','copywriting',true),('copywriter','storytelling',true),('copywriter','seo',false),('copywriter','editing',false),
  ('copywriter','chatgpt',false),('copywriter','english',false),('copywriter','email-marketing',false),
  ('editor','editing',true),('editor','copywriting',false),('editor','storytelling',false),('editor','english',false),
  ('translator','english',true),('translator','german',false),('translator','chinese',false),('translator','turkish',false),
  ('translator','uzbek',false),('translator','editing',true),('translator','subtitling',false),
  ('seo-specialist','seo',true),('seo-specialist','yandex-metrika',true),('seo-specialist','google-analytics',true),
  ('seo-specialist','wordpress',false),('seo-specialist','tilda',false),('seo-specialist','copywriting',false),('seo-specialist','google-sheets',false),
  ('ppc-specialist','ppc',true),('ppc-specialist','yandex-direct',true),('ppc-specialist','google-ads',true),
  ('ppc-specialist','yandex-metrika',true),('ppc-specialist','google-analytics',false),('ppc-specialist','google-sheets',false),
  ('smm-manager','smm',true),('smm-manager','content-planning',true),('smm-manager','canva',true),('smm-manager','capcut',false),
  ('smm-manager','vk',true),('smm-manager','tiktok',false),('smm-manager','youtube',false),('smm-manager','copywriting',false),('smm-manager','chatgpt',false),
  ('targetologist','targeting',true),('targetologist','vk-ads',true),('targetologist','meta-ads',true),('targetologist','telegram-ads',false),
  ('targetologist','yandex-direct',false),('targetologist','canva',false),('targetologist','google-sheets',false),
  ('marketer','market-research',true),('marketer','email-marketing',false),('marketer','seo',false),('marketer','ppc',false),
  ('marketer','targeting',false),('marketer','presentations',true),('marketer','google-analytics',false),('marketer','yandex-metrika',false),
  ('video-editor','premiere-pro',true),('video-editor','davinci-resolve',true),('video-editor','capcut',false),('video-editor','after-effects',false),
  ('video-editor','video-editing',true),('video-editor','color-grading',true),('video-editor','subtitling',false),
  ('voice-actor','voice-over',true),('voice-actor','audacity',false),('voice-actor','english',false),
  ('sound-designer','ableton',true),('sound-designer','fl-studio',false),('sound-designer','audacity',false),
  ('sound-designer','sound-design',true),('sound-designer','mixing-mastering',true),
  ('photographer','photography',true),('photographer','lightroom',true),('photographer','photoshop',true),('photographer','photo-retouching',true),
  ('accountant','accounting',true),('accountant','taxes',true),('accountant','1c',true),('accountant','excel',true),('accountant','google-sheets',false),
  ('lawyer','contract-law',true),('lawyer','taxes',false),
  ('business-analyst','market-research',true),('business-analyst','financial-modelling',true),('business-analyst','excel',true),
  ('business-analyst','google-sheets',true),('business-analyst','presentations',true),('business-analyst','notion',false),('business-analyst','sql',false),
  ('virtual-assistant','google-sheets',true),('virtual-assistant','notion',true),('virtual-assistant','data-entry',true),
  ('virtual-assistant','english',false),('virtual-assistant','excel',false),('virtual-assistant','chatgpt',false),
  ('hr-recruiter','recruiting',true),('hr-recruiter','google-sheets',false),('hr-recruiter','notion',false),
  ('tutor','teaching',true),('tutor','mentoring',true),('tutor','english',false),('tutor','german',false)
) AS v(spec_slug, skill_slug, core)
JOIN specialisations sp ON sp.slug = v.spec_slug
JOIN skills sk ON sk.slug = v.skill_slug
ON CONFLICT DO NOTHING;

-- ── 7. Category -> profession targeting ─────────────────────────────────────
-- The table that decides whose feed a brief reaches. A logo brief is 1.0 for
-- a graphic designer, 0.6 for an illustrator, and invisible to a copywriter.
INSERT INTO category_specialisations (category_id, specialisation_id, relevance)
SELECT c.id, sp.id, v.relevance
FROM (VALUES
  ('design-logo',          'graphic-designer', 1.00), ('design-logo',          'illustrator',      0.60), ('design-logo', 'web-designer', 0.40),
  ('design-web',           'web-designer',     1.00), ('design-web',           'ui-ux-designer',   0.90), ('design-web', 'graphic-designer', 0.40),
  ('design-social',        'graphic-designer', 1.00), ('design-social',        'smm-manager',      0.60), ('design-social', 'web-designer', 0.40),
  ('design-banners',       'graphic-designer', 1.00), ('design-banners',       'web-designer',     0.60), ('design-banners', 'targetologist', 0.30),
  ('design-print',         'graphic-designer', 1.00), ('design-print',         'illustrator',      0.40),
  ('design-illustration',  'illustrator',      1.00), ('design-illustration',  'graphic-designer', 0.55),
  ('design-presentations', 'graphic-designer', 1.00), ('design-presentations', 'business-analyst', 0.45), ('design-presentations', 'marketer', 0.35),
  ('design-3d',            '3d-artist',        1.00), ('design-3d',            'motion-designer',  0.50),
  ('design-marketplace',   'graphic-designer', 1.00), ('design-marketplace',   'photographer',     0.50), ('design-marketplace', 'copywriter', 0.35),
  ('texts-copywriting',    'copywriter',       1.00), ('texts-copywriting',    'editor',           0.50), ('texts-copywriting', 'marketer', 0.30),
  ('texts-articles',       'copywriter',       1.00), ('texts-articles',       'editor',           0.60), ('texts-articles', 'seo-specialist', 0.35),
  ('texts-sales',          'copywriter',       1.00), ('texts-sales',          'marketer',         0.60),
  ('texts-editing',        'editor',           1.00), ('texts-editing',        'copywriter',       0.60), ('texts-editing', 'translator', 0.30),
  ('texts-translation',    'translator',       1.00), ('texts-translation',    'editor',           0.30),
  ('texts-scripts',        'copywriter',       1.00), ('texts-scripts',        'video-editor',     0.30),
  ('texts-business',       'copywriter',       0.90), ('texts-business',       'hr-recruiter',     0.80), ('texts-business', 'editor', 0.50),
  ('texts-content-filling','virtual-assistant',1.00), ('texts-content-filling','copywriter',       0.60), ('texts-content-filling', 'seo-specialist', 0.40),
  ('seo-optimisation',     'seo-specialist',   1.00), ('seo-optimisation',     'marketer',         0.40),
  ('seo-audit',            'seo-specialist',   1.00), ('seo-audit',            'devops-engineer',  0.25), ('seo-audit', 'frontend-developer', 0.25),
  ('seo-semantics',        'seo-specialist',   1.00), ('seo-semantics',        'ppc-specialist',   0.50),
  ('seo-links',            'seo-specialist',   1.00),
  ('seo-context',          'ppc-specialist',   1.00), ('seo-context',          'targetologist',    0.50), ('seo-context', 'marketer', 0.40),
  ('seo-analytics',        'ppc-specialist',   0.80), ('seo-analytics',        'seo-specialist',   0.80), ('seo-analytics', 'business-analyst', 0.60), ('seo-analytics', 'marketer', 0.50),
  ('smm-management',       'smm-manager',      1.00), ('smm-management',       'marketer',         0.40), ('smm-management', 'copywriter', 0.35),
  ('smm-targeting',        'targetologist',    1.00), ('smm-targeting',        'ppc-specialist',   0.50), ('smm-targeting', 'smm-manager', 0.40),
  ('smm-content',          'smm-manager',      1.00), ('smm-content',          'graphic-designer', 0.50), ('smm-content', 'video-editor', 0.50), ('smm-content', 'copywriter', 0.45),
  ('smm-telegram',         'smm-manager',      1.00), ('smm-telegram',         'targetologist',    0.60), ('smm-telegram', 'telegram-developer', 0.30),
  ('smm-youtube',          'smm-manager',      1.00), ('smm-youtube',          'video-editor',     0.60), ('smm-youtube', 'marketer', 0.40),
  ('smm-email',            'marketer',         1.00), ('smm-email',            'copywriter',       0.70), ('smm-email', 'smm-manager', 0.40),
  ('smm-influence',        'marketer',         1.00), ('smm-influence',        'smm-manager',      0.80),
  ('media-video-editing',  'video-editor',     1.00), ('media-video-editing',  'motion-designer',  0.50),
  ('media-motion',         'motion-designer',  1.00), ('media-motion',         'video-editor',     0.50), ('media-motion', '3d-artist', 0.40),
  ('media-voiceover',      'voice-actor',      1.00), ('media-voiceover',      'sound-designer',   0.30),
  ('media-music',          'sound-designer',   1.00), ('media-music',          'voice-actor',      0.20),
  ('media-photo',          'photographer',     1.00), ('media-photo',          'graphic-designer', 0.50),
  ('media-shooting',       'photographer',     1.00), ('media-shooting',       'video-editor',     0.60),
  ('media-transcription',  'translator',       0.70), ('media-transcription',  'virtual-assistant',0.80), ('media-transcription', 'editor', 0.50),
  ('business-accounting',  'accountant',       1.00), ('business-accounting',  'business-analyst', 0.40),
  ('business-legal',       'lawyer',           1.00),
  ('business-plans',       'business-analyst', 1.00), ('business-plans',       'marketer',         0.50), ('business-plans', 'graphic-designer', 0.30),
  ('business-analytics',   'business-analyst', 1.00), ('business-analytics',   'marketer',         0.50), ('business-analytics', 'ai-automation-developer', 0.25),
  ('business-assistant',   'virtual-assistant',1.00), ('business-assistant',   'hr-recruiter',     0.30),
  ('business-data',        'virtual-assistant',0.90), ('business-data',        'business-analyst', 0.50), ('business-data', 'backend-developer', 0.40), ('business-data', 'ai-automation-developer', 0.40),
  ('business-hr',          'hr-recruiter',     1.00), ('business-hr',          'virtual-assistant',0.30),
  ('business-consulting',  'business-analyst', 1.00), ('business-consulting',  'marketer',         0.60), ('business-consulting', 'accountant', 0.30),
  ('education-tutoring',   'tutor',            1.00),
  ('education-it',         'backend-developer',0.80), ('education-it',         'frontend-developer',0.80), ('education-it', 'fullstack-developer', 0.90),
  ('education-it',         'devops-engineer',  0.60), ('education-it',         'tutor',            0.40),
  ('education-languages',  'tutor',            1.00), ('education-languages',  'translator',       0.60),
  ('education-creative',   'tutor',            0.80), ('education-creative',   'graphic-designer', 0.60), ('education-creative', 'video-editor', 0.50), ('education-creative', 'illustrator', 0.50),
  ('education-career',     'hr-recruiter',     1.00), ('education-career',     'tutor',            0.40), ('education-career', 'copywriter', 0.30)
) AS v(cat_slug, spec_slug, relevance)
JOIN categories c ON c.slug = v.cat_slug
JOIN specialisations sp ON sp.slug = v.spec_slug
ON CONFLICT DO NOTHING;

-- Any category without targeting of its own inherits its parent's. Run three
-- times because the tree is four deep and each pass copies one level down:
-- the framework categories (Go → Gin) had nothing before this, since the
-- single pass in 0016 saw its parents' rows only as they stood before that
-- statement ran — a brief filed under Gin reached nobody.
INSERT INTO category_specialisations (category_id, specialisation_id, relevance)
SELECT child.id, cs.specialisation_id, cs.relevance
FROM categories child
JOIN category_specialisations cs ON cs.category_id = child.parent_id
WHERE NOT EXISTS (SELECT 1 FROM category_specialisations x WHERE x.category_id = child.id)
ON CONFLICT DO NOTHING;
INSERT INTO category_specialisations (category_id, specialisation_id, relevance)
SELECT child.id, cs.specialisation_id, cs.relevance
FROM categories child
JOIN category_specialisations cs ON cs.category_id = child.parent_id
WHERE NOT EXISTS (SELECT 1 FROM category_specialisations x WHERE x.category_id = child.id)
ON CONFLICT DO NOTHING;
INSERT INTO category_specialisations (category_id, specialisation_id, relevance)
SELECT child.id, cs.specialisation_id, cs.relevance
FROM categories child
JOIN category_specialisations cs ON cs.category_id = child.parent_id
WHERE NOT EXISTS (SELECT 1 FROM category_specialisations x WHERE x.category_id = child.id)
ON CONFLICT DO NOTHING;

-- A sector root is what a client picks first; a brief filed at the root level
-- reaches every profession under it, at a lower relevance than a precise
-- category would give.
INSERT INTO category_specialisations (category_id, specialisation_id, relevance)
SELECT root.id, cs.specialisation_id, round(max(cs.relevance) * 0.6, 2)
FROM categories root
JOIN categories child ON child.parent_id = root.id
JOIN category_specialisations cs ON cs.category_id = child.id
WHERE root.depth = 0
GROUP BY root.id, cs.specialisation_id
ON CONFLICT DO NOTHING;

-- ── 8. Category -> skill hints ──────────────────────────────────────────────
INSERT INTO category_skills (category_id, skill_id, weight)
SELECT c.id, sk.id, v.weight
FROM (VALUES
  ('design-logo','adobe-illustrator',0.90),('design-logo','branding',1.00),('design-logo','figma',0.50),
  ('design-web','figma',1.00),('design-web','tilda',0.60),('design-web','prototyping',0.60),('design-web','wordpress',0.30),
  ('design-social','canva',0.80),('design-social','photoshop',0.70),('design-social','figma',0.50),
  ('design-banners','photoshop',0.90),('design-banners','figma',0.60),('design-banners','adobe-illustrator',0.50),
  ('design-print','indesign',0.90),('design-print','adobe-illustrator',0.80),('design-print','typography',0.60),
  ('design-illustration','illustration',1.00),('design-illustration','procreate',0.70),('design-illustration','adobe-illustrator',0.60),
  ('design-presentations','presentations',1.00),('design-presentations','figma',0.50),('design-presentations','canva',0.40),
  ('design-3d','blender',0.90),('design-3d','3d-modelling',1.00),('design-3d','cinema-4d',0.60),
  ('design-marketplace','photoshop',0.80),('design-marketplace','wildberries',0.70),('design-marketplace','ozon',0.60),
  ('texts-copywriting','copywriting',1.00),('texts-articles','copywriting',0.90),('texts-articles','seo',0.40),
  ('texts-sales','copywriting',1.00),('texts-sales','storytelling',0.50),
  ('texts-editing','editing',1.00),('texts-translation','english',0.80),('texts-translation','editing',0.40),
  ('texts-scripts','storytelling',0.90),('texts-scripts','copywriting',0.70),
  ('texts-business','copywriting',0.80),('texts-content-filling','data-entry',0.80),('texts-content-filling','wordpress',0.40),
  ('seo-optimisation','seo',1.00),('seo-optimisation','yandex-metrika',0.50),('seo-audit','seo',1.00),
  ('seo-semantics','seo',0.90),('seo-links','seo',0.90),
  ('seo-context','ppc',1.00),('seo-context','yandex-direct',0.90),('seo-context','google-ads',0.70),
  ('seo-analytics','yandex-metrika',0.90),('seo-analytics','google-analytics',0.80),
  ('smm-management','smm',1.00),('smm-management','content-planning',0.80),('smm-management','canva',0.50),
  ('smm-targeting','targeting',1.00),('smm-targeting','vk-ads',0.70),('smm-targeting','meta-ads',0.60),
  ('smm-content','canva',0.70),('smm-content','capcut',0.60),('smm-content','copywriting',0.50),
  ('smm-telegram','telegram-ads',0.70),('smm-telegram','smm',0.80),
  ('smm-youtube','youtube',1.00),('smm-youtube','video-editing',0.50),
  ('smm-email','email-marketing',1.00),('smm-email','unisender',0.50),('smm-email','mailchimp',0.40),
  ('smm-influence','smm',0.70),
  ('media-video-editing','video-editing',1.00),('media-video-editing','premiere-pro',0.70),('media-video-editing','davinci-resolve',0.60),('media-video-editing','capcut',0.40),
  ('media-motion','after-effects',0.90),('media-motion','motion-graphics',1.00),
  ('media-voiceover','voice-over',1.00),('media-music','sound-design',0.80),('media-music','mixing-mastering',0.80),('media-music','ableton',0.50),
  ('media-photo','photo-retouching',1.00),('media-photo','lightroom',0.70),('media-photo','photoshop',0.80),
  ('media-shooting','photography',1.00),('media-transcription','transcription',1.00),('media-transcription','subtitling',0.80),
  ('business-accounting','accounting',1.00),('business-accounting','taxes',0.80),('business-accounting','1c',0.70),
  ('business-legal','contract-law',1.00),
  ('business-plans','financial-modelling',0.90),('business-plans','presentations',0.80),
  ('business-analytics','market-research',1.00),('business-analytics','excel',0.60),('business-analytics','google-sheets',0.60),
  ('business-assistant','notion',0.50),('business-assistant','google-sheets',0.60),
  ('business-data','data-entry',0.90),('business-data','web-scraping',0.70),('business-data','google-sheets',0.60),('business-data','python',0.30),
  ('business-hr','recruiting',1.00),('business-consulting','project-management',0.60),('business-consulting','market-research',0.60),
  ('education-tutoring','teaching',1.00),('education-it','mentoring',0.90),('education-languages','english',0.90),('education-languages','teaching',0.70),
  ('education-creative','teaching',0.80),('education-career','recruiting',0.70),('education-career','mentoring',0.60)
) AS v(cat_slug, skill_slug, weight)
JOIN categories c ON c.slug = v.cat_slug
JOIN skills sk ON sk.slug = v.skill_slug
ON CONFLICT DO NOTHING;
