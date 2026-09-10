CREATE TABLE IF NOT EXISTS backups (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id      BIGINT UNSIGNED NOT NULL,
    type         ENUM('files','database','full') NOT NULL,
    local_path   VARCHAR(255) NOT NULL DEFAULT '',
    remote_path  VARCHAR(255) NOT NULL DEFAULT '',
    checksum     VARCHAR(128) NOT NULL DEFAULT '',
    size_bytes   BIGINT UNSIGNED NOT NULL DEFAULT 0,
    status       ENUM('pending','success','failed') NOT NULL DEFAULT 'pending',
    verified_at  TIMESTAMP NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_backups_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_backups_user (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
