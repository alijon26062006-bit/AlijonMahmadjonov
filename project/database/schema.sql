-- =============================================================
--  CineWave — Telegram Mini App cinema platform
--  MySQL 8 schema
-- =============================================================
--  Run:  mysql -u root -p < database/schema.sql
-- =============================================================

CREATE DATABASE IF NOT EXISTS `cinema`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE `cinema`;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- -------------------------------------------------------------
--  users — Telegram users of the mini app
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
    `id`            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `telegram_id`   BIGINT NOT NULL,
    `username`      VARCHAR(64)  DEFAULT NULL,
    `first_name`    VARCHAR(128) DEFAULT NULL,
    `last_name`     VARCHAR(128) DEFAULT NULL,
    `language_code` VARCHAR(8)   DEFAULT 'ru',
    `photo_url`     VARCHAR(512) DEFAULT NULL,
    `is_premium`    TINYINT(1)   NOT NULL DEFAULT 0,
    `last_seen_at`  TIMESTAMP    NULL DEFAULT NULL,
    `created_at`    TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_users_tg` (`telegram_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
--  admins — Telegram users allowed to manage content
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `admins`;
CREATE TABLE `admins` (
    `id`          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `telegram_id` BIGINT NOT NULL,
    `name`        VARCHAR(128) DEFAULT NULL,
    `role`        ENUM('owner','admin') NOT NULL DEFAULT 'admin',
    `created_at`  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_admins_tg` (`telegram_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
--  genres
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `genres`;
CREATE TABLE `genres` (
    `id`    INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `name`  VARCHAR(64) NOT NULL,
    `slug`  VARCHAR(64) NOT NULL,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_genres_slug` (`slug`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
--  movies — films, series, cartoons, anime
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `movies`;
CREATE TABLE `movies` (
    `id`             BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `title`          VARCHAR(255) NOT NULL,
    `slug`           VARCHAR(280) DEFAULT NULL,
    `description`    TEXT,
    `poster`         VARCHAR(512) DEFAULT NULL,
    `backdrop`       VARCHAR(512) DEFAULT NULL,
    `trailer`        VARCHAR(512) DEFAULT NULL,
    `watch_url`      VARCHAR(512) DEFAULT NULL,
    `category`       ENUM('movie','series','cartoon','anime') NOT NULL DEFAULT 'movie',
    `country`        VARCHAR(128) DEFAULT NULL,
    `release_date`   DATE DEFAULT NULL,
    `year`           SMALLINT UNSIGNED DEFAULT NULL,
    `age_rating`     VARCHAR(8)  DEFAULT NULL,   -- 0+, 6+, 12+, 16+, 18+
    `duration`       INT UNSIGNED DEFAULT NULL,  -- minutes
    `rating`         DECIMAL(3,1) DEFAULT 0.0,   -- 0.0 .. 10.0
    `language`       VARCHAR(64) DEFAULT NULL,
    `director`       VARCHAR(255) DEFAULT NULL,
    `actors`         TEXT,                       -- comma separated
    `screenshots`    JSON DEFAULT NULL,          -- array of image URLs
    `status`         ENUM('published','draft','coming_soon','in_cinema') NOT NULL DEFAULT 'published',
    `is_new`         TINYINT(1) NOT NULL DEFAULT 0,
    `is_popular`     TINYINT(1) NOT NULL DEFAULT 0,
    `is_recommended` TINYINT(1) NOT NULL DEFAULT 0,
    `views_count`    INT UNSIGNED NOT NULL DEFAULT 0,
    `created_at`     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at`     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_movies_category` (`category`),
    KEY `idx_movies_status`   (`status`),
    KEY `idx_movies_rating`   (`rating`),
    KEY `idx_movies_created`  (`created_at`),
    FULLTEXT KEY `ft_movies`  (`title`, `description`, `actors`, `director`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
--  movie_genres — many-to-many pivot
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `movie_genres`;
CREATE TABLE `movie_genres` (
    `movie_id` BIGINT UNSIGNED NOT NULL,
    `genre_id` INT UNSIGNED NOT NULL,
    PRIMARY KEY (`movie_id`, `genre_id`),
    KEY `idx_mg_genre` (`genre_id`),
    CONSTRAINT `fk_mg_movie` FOREIGN KEY (`movie_id`) REFERENCES `movies` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_mg_genre` FOREIGN KEY (`genre_id`) REFERENCES `genres` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
--  announcements — teasers shown on the home page / hero
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `announcements`;
CREATE TABLE `announcements` (
    `id`           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `title`        VARCHAR(255) NOT NULL,
    `description`  TEXT,
    `poster`       VARCHAR(512) DEFAULT NULL,
    `backdrop`     VARCHAR(512) DEFAULT NULL,
    `trailer`      VARCHAR(512) DEFAULT NULL,
    `category`     ENUM('movie','series','cartoon','anime') NOT NULL DEFAULT 'movie',
    `genre`        VARCHAR(128) DEFAULT NULL,
    `rating`       DECIMAL(3,1) DEFAULT 0.0,
    `release_date` DATE DEFAULT NULL,
    `movie_id`     BIGINT UNSIGNED DEFAULT NULL,  -- optional link to a full movie
    `priority`     INT NOT NULL DEFAULT 0,        -- higher = shown first
    `is_active`    TINYINT(1) NOT NULL DEFAULT 1,
    `created_at`   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_ann_active` (`is_active`, `priority`),
    CONSTRAINT `fk_ann_movie` FOREIGN KEY (`movie_id`) REFERENCES `movies` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
--  banners — hero slides (can point to a movie or announcement)
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `banners`;
CREATE TABLE `banners` (
    `id`              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `title`           VARCHAR(255) NOT NULL,
    `subtitle`        VARCHAR(255) DEFAULT NULL,
    `image`           VARCHAR(512) DEFAULT NULL,
    `movie_id`        BIGINT UNSIGNED DEFAULT NULL,
    `announcement_id` BIGINT UNSIGNED DEFAULT NULL,
    `priority`        INT NOT NULL DEFAULT 0,
    `is_active`       TINYINT(1) NOT NULL DEFAULT 1,
    `created_at`      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_banners_active` (`is_active`, `priority`),
    CONSTRAINT `fk_ban_movie` FOREIGN KEY (`movie_id`) REFERENCES `movies` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_ban_ann`   FOREIGN KEY (`announcement_id`) REFERENCES `announcements` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
--  favorites
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `favorites`;
CREATE TABLE `favorites` (
    `id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id`    BIGINT UNSIGNED NOT NULL,
    `movie_id`   BIGINT UNSIGNED NOT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_fav` (`user_id`, `movie_id`),
    KEY `idx_fav_movie` (`movie_id`),
    CONSTRAINT `fk_fav_user`  FOREIGN KEY (`user_id`)  REFERENCES `users`  (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_fav_movie` FOREIGN KEY (`movie_id`) REFERENCES `movies` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
--  history — "continue watching"
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `history`;
CREATE TABLE `history` (
    `id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id`    BIGINT UNSIGNED NOT NULL,
    `movie_id`   BIGINT UNSIGNED NOT NULL,
    `progress`   SMALLINT NOT NULL DEFAULT 0,   -- percent 0..100
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_hist` (`user_id`, `movie_id`),
    KEY `idx_hist_user` (`user_id`, `updated_at`),
    CONSTRAINT `fk_hist_user`  FOREIGN KEY (`user_id`)  REFERENCES `users`  (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_hist_movie` FOREIGN KEY (`movie_id`) REFERENCES `movies` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
--  views — raw view log (analytics)
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `views`;
CREATE TABLE `views` (
    `id`        BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `movie_id`  BIGINT UNSIGNED NOT NULL,
    `user_id`   BIGINT UNSIGNED DEFAULT NULL,
    `viewed_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_views_movie` (`movie_id`, `viewed_at`),
    CONSTRAINT `fk_views_movie` FOREIGN KEY (`movie_id`) REFERENCES `movies` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
--  settings — key/value store
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `settings`;
CREATE TABLE `settings` (
    `key`        VARCHAR(64) NOT NULL,
    `value`      TEXT,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
--  notifications — broadcast / per-user notices log
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `notifications`;
CREATE TABLE `notifications` (
    `id`         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `user_id`    BIGINT UNSIGNED DEFAULT NULL,  -- NULL = broadcast
    `title`      VARCHAR(255) DEFAULT NULL,
    `body`       TEXT,
    `sent`       TINYINT(1) NOT NULL DEFAULT 0,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_notif_user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -------------------------------------------------------------
--  bot_states — finite-state machine for admin bot dialogs
-- -------------------------------------------------------------
DROP TABLE IF EXISTS `bot_states`;
CREATE TABLE `bot_states` (
    `telegram_id` BIGINT NOT NULL,
    `state`       VARCHAR(64) DEFAULT NULL,
    `payload`     JSON DEFAULT NULL,
    `updated_at`  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`telegram_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SET FOREIGN_KEY_CHECKS = 1;

-- =============================================================
--  Seed data
-- =============================================================
INSERT INTO `genres` (`name`, `slug`) VALUES
    ('Боевик','action'), ('Драма','drama'), ('Комедия','comedy'),
    ('Фантастика','sci-fi'), ('Ужасы','horror'), ('Триллер','thriller'),
    ('Мелодрама','romance'), ('Приключения','adventure'), ('Фэнтези','fantasy'),
    ('Детектив','detective'), ('Аниме','anime'), ('Семейный','family'),
    ('Документальный','documentary'), ('Мультфильм','cartoon'), ('Криминал','crime');

INSERT INTO `settings` (`key`, `value`) VALUES
    ('app_name', 'CineWave'),
    ('hero_interval', '6000'),
    ('maintenance', '0');
