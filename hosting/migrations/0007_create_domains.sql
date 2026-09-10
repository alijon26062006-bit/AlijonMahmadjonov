-- Дополнительные (собственные) домены, привязанные к сайту, включая статус проверки и SSL.
CREATE TABLE IF NOT EXISTS domains (
    id            BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    site_id       BIGINT UNSIGNED NOT NULL,
    domain        VARCHAR(190) NOT NULL UNIQUE,
    is_primary    TINYINT(1) NOT NULL DEFAULT 0,
    verified      TINYINT(1) NOT NULL DEFAULT 0,
    verified_at   TIMESTAMP NULL,
    ssl_status    ENUM('none','pending','issued','failed') NOT NULL DEFAULT 'none',
    ssl_issued_at TIMESTAMP NULL,
    last_check_at TIMESTAMP NULL,
    last_error    VARCHAR(255) NOT NULL DEFAULT '',
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_domains_site FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
