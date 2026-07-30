<?php
/**
 * Обновление базы (безопасно, данные не трогает).
 * Добавляет таблицу episodes (сезоны/серии).
 *
 * Откройте один раз:
 *   https://ваш-домен/kino/upgrade.php?key=ВАШ_WEBHOOK_SECRET
 * Потом УДАЛИТЕ этот файл.
 */

declare(strict_types=1);
header('Content-Type: text/plain; charset=utf-8');

$config = require __DIR__ . '/config/config.php';

if (($_GET['key'] ?? '') !== $config['telegram']['webhook_secret']) {
    http_response_code(403);
    exit("Доступ запрещён. Откройте: upgrade.php?key=ВАШ_WEBHOOK_SECRET\n");
}

$db = $config['db'];
try {
    $dsn = "mysql:host={$db['host']};port={$db['port']};dbname={$db['name']};charset={$db['charset']}";
    $pdo = new PDO($dsn, $db['user'], $db['pass'], [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION]);
} catch (Throwable $e) {
    exit("❌ База: " . $e->getMessage() . "\n");
}

// CREATE TABLE IF NOT EXISTS — существующие таблицы и данные не затрагиваются.
$sql = "CREATE TABLE IF NOT EXISTS `episodes` (
    `id`               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    `movie_id`         BIGINT UNSIGNED NOT NULL,
    `season`           SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    `episode`          SMALLINT UNSIGNED NOT NULL DEFAULT 1,
    `title`            VARCHAR(255) DEFAULT NULL,
    `telegram_file_id` VARCHAR(255) DEFAULT NULL,
    `watch_url`        VARCHAR(512) DEFAULT NULL,
    `duration`         INT UNSIGNED DEFAULT NULL,
    `created_at`       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_ep` (`movie_id`, `season`, `episode`),
    KEY `idx_ep_movie` (`movie_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci";

try {
    $pdo->exec($sql);
    echo "✅ Таблица episodes готова.\n";
} catch (Throwable $e) {
    exit("❌ Ошибка: " . $e->getMessage() . "\n");
}

$tables = $pdo->query("SHOW TABLES")->fetchAll(PDO::FETCH_COLUMN);
echo "📋 Всего таблиц: " . count($tables) . "\n";
echo "\n🎉 Готово! Теперь УДАЛИТЕ upgrade.php.\n";
