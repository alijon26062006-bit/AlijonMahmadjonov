-- Сайт клиента. domain — основной адрес (поддомен или собственный домен после привязки).
CREATE TABLE IF NOT EXISTS sites (
    id           BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id      BIGINT UNSIGNED NOT NULL,
    slug         VARCHAR(64)  NOT NULL,
    domain       VARCHAR(190) NOT NULL UNIQUE,
    doc_root     VARCHAR(190) NOT NULL DEFAULT 'public',
    php_version  VARCHAR(8)   NOT NULL DEFAULT '8.3',
    status       ENUM('pending','active','suspended','deleted') NOT NULL DEFAULT 'pending',
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_sites_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uq_sites_user_slug (user_id, slug),
    INDEX idx_sites_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
