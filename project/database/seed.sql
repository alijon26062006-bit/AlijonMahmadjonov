-- =============================================================
--  Demo content for CineWave (optional).
--  Run after schema.sql:  mysql -u root -p cinema < database/seed.sql
--  Images use remote placeholder URLs so the app renders immediately.
-- =============================================================
USE `cinema`;

INSERT INTO `movies`
    (title, slug, description, poster, backdrop, trailer, watch_url, category, country,
     release_date, year, age_rating, duration, rating, language, director, actors, status,
     is_new, is_popular, is_recommended, views_count)
VALUES
    ('Орбита теней',
     'orbita-teney',
     'Экипаж исследовательского корабля обнаруживает сигнал с окраины Солнечной системы и оказывается втянут в игру, где ставка — само человечество.',
     'https://picsum.photos/seed/orbita_p/400/600',
     'https://picsum.photos/seed/orbita_b/1280/720',
     'https://www.youtube.com/watch?v=aqz-KE-bpKQ', 'https://example.com/watch/1',
     'movie', 'США', '2026-03-14', 2026, '16+', 142, 8.7, 'Английский',
     'Дени Вильнёв', 'Тимоти Шаламе, Зендея, Оскар Айзек', 'published', 1, 1, 1, 1240),

    ('Последний рубеж',
     'posledniy-rubezh',
     'Ветеран спецназа возвращается в родной город и обнаруживает, что за фасадом тишины скрывается преступный синдикат.',
     'https://picsum.photos/seed/rubezh_p/400/600',
     'https://picsum.photos/seed/rubezh_b/1280/720',
     'https://www.youtube.com/watch?v=aqz-KE-bpKQ', 'https://example.com/watch/2',
     'movie', 'Франция', '2025-11-02', 2025, '18+', 118, 7.9, 'Французский',
     'Люк Бессон', 'Омар Си, Леа Сейду', 'published', 1, 1, 0, 880),

    ('Хроники Аркадии',
     'hroniki-arkadii',
     'В мире, где магия угасает, юная наследница должна собрать осколки древнего артефакта, чтобы спасти королевство.',
     'https://picsum.photos/seed/arkadia_p/400/600',
     'https://picsum.photos/seed/arkadia_b/1280/720',
     NULL, 'https://example.com/watch/3',
     'series', 'Великобритания', '2026-01-20', 2026, '12+', 52, 9.1, 'Английский',
     'Кейт Херрон', 'Милли Бобби Браун, Генри Кавилл', 'published', 1, 1, 1, 2100),

    ('Клинок рассвета',
     'klinok-rassveta',
     'Молодой мечник вступает в орден охотников на демонов, чтобы отомстить за свою семью и защитить младшую сестру.',
     'https://picsum.photos/seed/klinok_p/400/600',
     'https://picsum.photos/seed/klinok_b/1280/720',
     NULL, 'https://example.com/watch/4',
     'anime', 'Япония', '2025-10-10', 2025, '16+', 24, 9.4, 'Японский',
     'Харуо Сотозаки', 'Нацуки Ханаэ, Акари Кито', 'published', 1, 1, 1, 3400),

    ('Звёздный экспресс',
     'zvezdnyy-ekspress',
     'Весёлая команда роботов отправляется в путешествие через галактику, полное приключений и неожиданных друзей.',
     'https://picsum.photos/seed/express_p/400/600',
     'https://picsum.photos/seed/express_b/1280/720',
     NULL, 'https://example.com/watch/5',
     'cartoon', 'США', '2026-06-01', 2026, '0+', 96, 8.2, 'Английский',
     'Пит Доктер', 'Том Хэнкс, Эми Полер', 'published', 1, 0, 1, 640),

    ('Тихий город',
     'tihiy-gorod',
     'Детектив расследует серию загадочных исчезновений в приморском городке, где у каждого есть свой секрет.',
     'https://picsum.photos/seed/gorod_p/400/600',
     'https://picsum.photos/seed/gorod_b/1280/720',
     NULL, 'https://example.com/watch/6',
     'series', 'Норвегия', '2025-09-15', 2025, '16+', 48, 8.5, 'Норвежский',
     'Ханс Петтер Моланд', 'Стеллан Скарсгард', 'published', 0, 1, 0, 1500),

    ('Неоновый горизонт',
     'neonovyy-gorizont',
     'В киберпанк-мегаполисе хакер-одиночка бросает вызов корпорации, контролирующей сознание миллионов.',
     'https://picsum.photos/seed/neon_p/400/600',
     'https://picsum.photos/seed/neon_b/1280/720',
     NULL, NULL,
     'movie', 'Япония', '2026-08-30', 2026, '18+', 130, 0, 'Японский',
     'Мамору Осии', 'Рэй Фудзита', 'coming_soon', 0, 0, 0, 0),

    ('Гранд Отель',
     'grand-otel',
     'Комедийная драма о буднях сотрудников роскошного отеля и гостях, чьи судьбы переплетаются самым неожиданным образом.',
     'https://picsum.photos/seed/otel_p/400/600',
     'https://picsum.photos/seed/otel_b/1280/720',
     NULL, 'https://example.com/watch/8',
     'movie', 'Германия', '2025-07-07', 2025, '12+', 108, 7.6, 'Немецкий',
     'Уэс Андерсон', 'Рэйф Файнс, Сирша Ронан', 'in_cinema', 0, 1, 1, 990);

-- Attach a couple of genres to each demo title
INSERT IGNORE INTO `movie_genres` (movie_id, genre_id)
SELECT m.id, g.id FROM movies m JOIN genres g
WHERE (m.slug='orbita-teney'      AND g.slug IN ('sci-fi','adventure'))
   OR (m.slug='posledniy-rubezh'  AND g.slug IN ('action','crime'))
   OR (m.slug='hroniki-arkadii'   AND g.slug IN ('fantasy','adventure'))
   OR (m.slug='klinok-rassveta'   AND g.slug IN ('anime','action'))
   OR (m.slug='zvezdnyy-ekspress' AND g.slug IN ('cartoon','family'))
   OR (m.slug='tihiy-gorod'       AND g.slug IN ('detective','thriller'))
   OR (m.slug='neonovyy-gorizont' AND g.slug IN ('sci-fi','thriller'))
   OR (m.slug='grand-otel'        AND g.slug IN ('comedy','drama'));

-- Announcements (also feed the hero banner via the app's fallback)
INSERT INTO `announcements`
    (title, description, poster, backdrop, trailer, category, genre, rating, release_date, priority, is_active)
VALUES
    ('Орбита теней', 'Космический триллер года. Уже в каталоге.',
     'https://picsum.photos/seed/orbita_p/400/600', 'https://picsum.photos/seed/orbita_b/1280/720',
     NULL, 'movie', 'Фантастика', 8.7, '2026-03-14', 100, 1),
    ('Хроники Аркадии', 'Эпическое фэнтези-приключение. Новый сезон.',
     'https://picsum.photos/seed/arkadia_p/400/600', 'https://picsum.photos/seed/arkadia_b/1280/720',
     NULL, 'series', 'Фэнтези', 9.1, '2026-01-20', 90, 1),
    ('Неоновый горизонт', 'Киберпанк-премьера уже этим летом.',
     'https://picsum.photos/seed/neon_p/400/600', 'https://picsum.photos/seed/neon_b/1280/720',
     NULL, 'movie', 'Киберпанк', 0, '2026-08-30', 80, 1);

-- Dedicated hero banners linked to movies
INSERT INTO `banners` (title, subtitle, image, movie_id, priority, is_active)
SELECT m.title, 'Смотрите сейчас', m.backdrop, m.id, 50, 1
FROM movies m WHERE m.slug IN ('orbita-teney','klinok-rassveta','hroniki-arkadii');
