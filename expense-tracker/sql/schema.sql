-- Схема базы данных для "Учёт расходов сотрудников"
-- Импортируйте этот файл в вашу MySQL базу (через phpMyAdmin, cPanel -> phpMyAdmin -> Import,
-- или консольно: mysql -u USER -p DBNAME < schema.sql)

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS users (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    username VARCHAR(50) NOT NULL UNIQUE,
    phone VARCHAR(30) NULL,
    email VARCHAR(255) NULL UNIQUE,
    google_id VARCHAR(255) NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('worker', 'boss') NOT NULL DEFAULT 'worker',
    monthly_salary_usd DECIMAL(10,2) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS expenses (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    currency ENUM('USD', 'KZT') NOT NULL DEFAULT 'KZT',
    description VARCHAR(255) NULL,
    expense_date DATE NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_date (user_id, expense_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS settings (
    id TINYINT UNSIGNED PRIMARY KEY DEFAULT 1,
    exchange_rate_kzt_per_usd DECIMAL(10,2) NOT NULL DEFAULT 480.00,
    last_summary_sent VARCHAR(7) NULL COMMENT 'YYYY-MM месяца, за который уже отправлена рассылка',
    CONSTRAINT single_row CHECK (id = 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO settings (id, exchange_rate_kzt_per_usd) VALUES (1, 480.00)
    ON DUPLICATE KEY UPDATE id = id;

-- Учётная запись шефа по умолчанию.
-- Логин: boss   Пароль: boss12345
-- ОБЯЗАТЕЛЬНО смените пароль после первого входа (Настройки -> сменить пароль)!
-- Хеш ниже сгенерирован через password_hash('boss12345', PASSWORD_DEFAULT).
INSERT INTO users (name, username, password_hash, role)
VALUES ('Шеф', 'boss', '$2y$12$U/q/IYrRiu.TvsezV17b3etqX9.7uDdXae8k3NZF4pYR.jbxQE1rK', 'boss')
    ON DUPLICATE KEY UPDATE id = id;
