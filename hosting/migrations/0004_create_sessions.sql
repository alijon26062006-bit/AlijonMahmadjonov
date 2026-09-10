-- Серверные сессии (и для web-логина, и для Telegram Mini App после проверки initData).
-- id — sha256 токена из cookie, сам токен в базе не хранится.
CREATE TABLE IF NOT EXISTS sessions (
    id            CHAR(64) PRIMARY KEY,
    user_id       BIGINT UNSIGNED NOT NULL,
    ip            VARCHAR(45) NOT NULL DEFAULT '',
    user_agent    VARCHAR(255) NOT NULL DEFAULT '',
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at    TIMESTAMP NOT NULL,
    CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_sessions_user (user_id),
    INDEX idx_sessions_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
