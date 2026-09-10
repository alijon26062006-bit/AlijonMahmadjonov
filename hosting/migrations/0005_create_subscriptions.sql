CREATE TABLE IF NOT EXISTS subscriptions (
    id                 BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id            BIGINT UNSIGNED NOT NULL,
    plan_id            BIGINT UNSIGNED NOT NULL,
    status             ENUM('active','grace','suspended','cancelled') NOT NULL DEFAULT 'active',
    started_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    current_period_end TIMESTAMP NULL,
    grace_until        TIMESTAMP NULL,
    suspended_at       TIMESTAMP NULL,
    cancelled_at       TIMESTAMP NULL,
    CONSTRAINT fk_sub_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_sub_plan FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE RESTRICT,
    INDEX idx_sub_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
