-- Очередь заданий для root worker. Панель НИКОГДА не выполняет привилегированные
-- операции сама — она только кладёт сюда строку и ждёт результата.
CREATE TABLE IF NOT EXISTS jobs (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    type        VARCHAR(64) NOT NULL,
    user_id     BIGINT UNSIGNED NULL,
    site_id     BIGINT UNSIGNED NULL,
    status      ENUM('pending','running','success','failed') NOT NULL DEFAULT 'pending',
    payload     JSON NULL,
    error_text  TEXT NULL,
    attempts    INT UNSIGNED NOT NULL DEFAULT 0,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at  TIMESTAMP NULL,
    finished_at TIMESTAMP NULL,
    INDEX idx_jobs_status (status),
    INDEX idx_jobs_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
