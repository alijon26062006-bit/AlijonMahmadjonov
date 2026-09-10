-- Тарифы. Значения — стартовые ориентиры для VPS 4 vCPU / 8 GB, править по факту нагрузки.
CREATE TABLE IF NOT EXISTS plans (
    id                      BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    code                    VARCHAR(32)  NOT NULL UNIQUE,
    title                   VARCHAR(64)  NOT NULL,
    price_tjs               DECIMAL(10,2) NOT NULL DEFAULT 0,
    disk_quota_mb           INT UNSIGNED NOT NULL,
    inode_limit             INT UNSIGNED NOT NULL,
    max_sites               INT UNSIGNED NOT NULL,
    max_databases           INT UNSIGNED NOT NULL,
    pm_max_children         INT UNSIGNED NOT NULL,
    memory_limit_mb         INT UNSIGNED NOT NULL,
    db_max_user_connections INT UNSIGNED NOT NULL,
    cpu_quota_percent       INT UNSIGNED NOT NULL,
    memory_max_mb           INT UNSIGNED NOT NULL,
    tasks_max               INT UNSIGNED NOT NULL,
    is_active               TINYINT(1)   NOT NULL DEFAULT 1,
    created_at              TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO plans
    (code, title, price_tjs, disk_quota_mb, inode_limit, max_sites, max_databases,
     pm_max_children, memory_limit_mb, db_max_user_connections,
     cpu_quota_percent, memory_max_mb, tasks_max)
VALUES
    ('start',    'Старт',   15.00,  2048,  100000, 1,  1,  2, 128,  5,  50,  256, 30),
    ('medium',   'Бизнес',  45.00,  5120,  250000, 5,  5,  4, 192, 10, 100,  512, 50),
    ('pro',      'Про',     90.00, 15360,  500000, 25, 25, 6, 256, 20, 200, 1024, 80)
ON DUPLICATE KEY UPDATE title = VALUES(title);
