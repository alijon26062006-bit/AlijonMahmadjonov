-- =============================================================
--  CineWave — AI upgrade migration
--  Adds columns used by the AI-assisted movie wizard.
--  Run ONCE on an existing database:
--      mysql -u root -p cinema < database/ai_upgrade.sql
--  (Fresh installs already include these columns via schema.sql.)
-- =============================================================
USE `cinema`;

ALTER TABLE `movies`
    ADD COLUMN `original_title`   VARCHAR(255) DEFAULT NULL AFTER `title`,
    ADD COLUMN `thumbnail`        VARCHAR(512) DEFAULT NULL AFTER `poster`,
    ADD COLUMN `banner`           VARCHAR(512) DEFAULT NULL AFTER `backdrop`,
    ADD COLUMN `keywords`         TEXT         DEFAULT NULL AFTER `actors`,
    ADD COLUMN `similar_titles`   JSON         DEFAULT NULL AFTER `screenshots`,
    ADD COLUMN `telegram_file_id` VARCHAR(255) DEFAULT NULL AFTER `watch_url`;
