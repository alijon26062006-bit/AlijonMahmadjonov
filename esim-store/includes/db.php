<?php
declare(strict_types=1);

function db(array $config): PDO
{
    static $pdo = null;
    if ($pdo !== null) {
        return $pdo;
    }

    if ($config['db_driver'] === 'mysql') {
        $dsn = sprintf(
            'mysql:host=%s;dbname=%s;charset=utf8mb4',
            $config['db_host'],
            $config['db_name']
        );
        $pdo = new PDO($dsn, $config['db_user'], $config['db_pass'], [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
        ]);
    } else {
        $dir = dirname($config['db_sqlite_path']);
        if (!is_dir($dir)) {
            mkdir($dir, 0775, true);
        }
        $pdo = new PDO('sqlite:' . $config['db_sqlite_path']);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
        $pdo->exec('PRAGMA foreign_keys = ON');
    }

    ensure_schema($pdo, $config['db_driver']);

    return $pdo;
}

function ensure_schema(PDO $pdo, string $driver): void
{
    $isMysql = $driver === 'mysql';
    $idType = $isMysql ? 'VARCHAR(24) PRIMARY KEY' : 'TEXT PRIMARY KEY';
    $engine = $isMysql ? ' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4' : '';

    $pdo->exec("CREATE TABLE IF NOT EXISTS orders (
        id $idType,
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
    )$engine");

    $pdo->exec("CREATE TABLE IF NOT EXISTS verification_codes (
        phone VARCHAR(32) PRIMARY KEY,
        code VARCHAR(10) NOT NULL,
        expires_at VARCHAR(32) NOT NULL,
        attempts INT NOT NULL DEFAULT 0
    )$engine");
}
