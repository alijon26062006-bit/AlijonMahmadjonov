-- Журнал привилегированных операций. Секреты (пароли, токены) сюда не пишем — только факт действия.
CREATE TABLE IF NOT EXISTS audit_logs (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id     BIGINT UNSIGNED NULL,
    actor       VARCHAR(64) NOT NULL DEFAULT '',
    action      VARCHAR(64) NOT NULL,
    object_type VARCHAR(32) NOT NULL DEFAULT '',
    object_id   BIGINT UNSIGNED NULL,
    ip          VARCHAR(45) NOT NULL DEFAULT '',
    result      ENUM('success','failure') NOT NULL DEFAULT 'success',
    details     JSON NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_audit_user (user_id),
    INDEX idx_audit_action (action)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS security_events (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id     BIGINT UNSIGNED NULL,
    event_type  VARCHAR(64) NOT NULL,
    severity    ENUM('info','warning','critical') NOT NULL DEFAULT 'info',
    ip          VARCHAR(45) NOT NULL DEFAULT '',
    details     JSON NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_secevents_type (event_type),
    INDEX idx_secevents_severity (severity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS login_attempts (
    id          BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    identifier  VARCHAR(190) NOT NULL,
    ip          VARCHAR(45) NOT NULL DEFAULT '',
    success     TINYINT(1) NOT NULL DEFAULT 0,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_login_attempts_id_time (identifier, created_at),
    INDEX idx_login_attempts_ip_time (ip, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
