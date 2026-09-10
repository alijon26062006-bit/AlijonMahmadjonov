CREATE TABLE IF NOT EXISTS payments (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id         BIGINT UNSIGNED NOT NULL,
    subscription_id BIGINT UNSIGNED NULL,
    provider        ENUM('telegram_stars','manual','other') NOT NULL DEFAULT 'manual',
    amount_tjs      DECIMAL(10,2) NOT NULL,
    currency        VARCHAR(8) NOT NULL DEFAULT 'TJS',
    status          ENUM('pending','paid','failed','refunded') NOT NULL DEFAULT 'pending',
    external_id     VARCHAR(190) NOT NULL DEFAULT '',
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_payments_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_payments_sub FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
