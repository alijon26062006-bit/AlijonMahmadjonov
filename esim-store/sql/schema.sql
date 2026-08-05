-- Reference schema for MySQL (matches what includes/db.php auto-creates on first run).
-- You normally do NOT need to run this by hand: the app creates these tables itself
-- the first time it connects, as long as the DB user has CREATE privileges.
-- Kept here in case you prefer to import it manually via phpMyAdmin on Somonhost.

CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR(24) PRIMARY KEY,
    created_at VARCHAR(32) NOT NULL,
    updated_at VARCHAR(32) NOT NULL,
    status VARCHAR(24) NOT NULL,
    customer_email VARCHAR(190) NOT NULL,
    customer_phone VARCHAR(32) NOT NULL,
    phone_verified TINYINT(1) NOT NULL DEFAULT 0,
    plan_id VARCHAR(64) NOT NULL,
    plan_title VARCHAR(190) NOT NULL,
    country_name VARCHAR(120) NOT NULL,
    country_flag VARCHAR(16) NOT NULL,
    plan_days INT NOT NULL,
    plan_data VARCHAR(32) NOT NULL,
    price_usd DECIMAL(10,2) NOT NULL,
    quantity INT NOT NULL DEFAULT 1,
    total_usd DECIMAL(10,2) NOT NULL,
    receipt_filename VARCHAR(190) DEFAULT NULL,
    receipt_uploaded_at VARCHAR(32) DEFAULT NULL,
    esim_iccid VARCHAR(64) DEFAULT NULL,
    esim_qr_url VARCHAR(255) DEFAULT NULL,
    esim_demo TINYINT(1) NOT NULL DEFAULT 0,
    admin_note VARCHAR(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS verification_codes (
    phone VARCHAR(32) PRIMARY KEY,
    code VARCHAR(10) NOT NULL,
    expires_at VARCHAR(32) NOT NULL,
    attempts INT NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
