-- Клиенты панели. Вход возможен по e-mail+паролю и/или через Telegram (см. telegram_accounts).
-- system_user —unix-имя вида client1001, выдаётся один раз при создании и не меняется.
CREATE TABLE IF NOT EXISTS users (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    email           VARCHAR(190) NULL UNIQUE,
    password_hash   VARCHAR(255) NULL,
    display_name    VARCHAR(190) NOT NULL DEFAULT '',
    system_user     VARCHAR(32)  NOT NULL DEFAULT '' UNIQUE,
    role            ENUM('client','admin') NOT NULL DEFAULT 'client',
    plan_id         BIGINT UNSIGNED NULL,
    status          ENUM('active','grace','suspended','pending_delete') NOT NULL DEFAULT 'active',
    disk_quota_mb   INT UNSIGNED NOT NULL DEFAULT 0,
    inode_limit     INT UNSIGNED NOT NULL DEFAULT 0,
    max_sites       INT UNSIGNED NOT NULL DEFAULT 0,
    max_databases   INT UNSIGNED NOT NULL DEFAULT 0,
    two_factor_secret VARCHAR(64) NULL,
    grace_until       TIMESTAMP NULL,
    suspended_until   TIMESTAMP NULL,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_users_plan FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE SET NULL,
    INDEX idx_users_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
