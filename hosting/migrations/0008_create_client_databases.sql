-- Базы MariaDB, выданные клиентам. Реальные CREATE DATABASE/CREATE USER выполняет root worker,
-- эта таблица — учёт и разрешение операций (кто чем владеет для IDOR-проверок).
CREATE TABLE IF NOT EXISTS client_databases (
    id         BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id    BIGINT UNSIGNED NOT NULL,
    site_id    BIGINT UNSIGNED NULL,
    db_name    VARCHAR(64) NOT NULL UNIQUE,
    status     ENUM('pending','active','failed','deleted') NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_databases_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_databases_site FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS database_users (
    id               BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id          BIGINT UNSIGNED NOT NULL,
    db_user          VARCHAR(32) NOT NULL UNIQUE,
    max_connections  INT UNSIGNED NOT NULL DEFAULT 5,
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_dbusers_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
