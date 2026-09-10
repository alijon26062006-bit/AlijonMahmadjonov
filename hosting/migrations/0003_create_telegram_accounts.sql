-- Привязка Telegram-аккаунта к клиенту. Один Telegram id — один клиент.
CREATE TABLE IF NOT EXISTS telegram_accounts (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id      BIGINT UNSIGNED NOT NULL UNIQUE,
    telegram_id  BIGINT UNSIGNED NOT NULL UNIQUE,
    username     VARCHAR(64)  NOT NULL DEFAULT '',
    first_name   VARCHAR(128) NOT NULL DEFAULT '',
    last_name    VARCHAR(128) NOT NULL DEFAULT '',
    linked_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_tg_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
