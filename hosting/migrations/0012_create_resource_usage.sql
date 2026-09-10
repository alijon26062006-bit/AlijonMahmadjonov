CREATE TABLE IF NOT EXISTS resource_usage (
    id             BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id        BIGINT UNSIGNED NOT NULL,
    cpu_percent    DECIMAL(5,2) NOT NULL DEFAULT 0,
    memory_mb      INT UNSIGNED NOT NULL DEFAULT 0,
    disk_mb        INT UNSIGNED NOT NULL DEFAULT 0,
    inode_count    INT UNSIGNED NOT NULL DEFAULT 0,
    process_count  INT UNSIGNED NOT NULL DEFAULT 0,
    recorded_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_usage_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_usage_user_time (user_id, recorded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
