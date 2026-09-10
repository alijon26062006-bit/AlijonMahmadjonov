-- Контролируемый планировщик задач клиента (замена прямого доступа к system cron).
CREATE TABLE IF NOT EXISTS scheduled_jobs (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id       BIGINT UNSIGNED NOT NULL,
    site_id       BIGINT UNSIGNED NOT NULL,
    command       VARCHAR(64) NOT NULL COMMENT 'whitelist-код команды, не произвольная строка',
    schedule_expr VARCHAR(64) NOT NULL COMMENT 'например */15 * * * *',
    is_enabled    TINYINT(1) NOT NULL DEFAULT 1,
    last_run_at   TIMESTAMP NULL,
    last_status   ENUM('success','failed') NULL,
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_schedjobs_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_schedjobs_site FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
