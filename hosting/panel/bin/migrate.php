#!/usr/bin/env php
<?php

declare(strict_types=1);

/**
 * Применяет SQL-миграции из hosting/migrations к панельной MariaDB по порядку имён файлов.
 * Уже применённые миграции пропускаются (таблица schema_migrations) — повторный запуск безопасен.
 *
 * Использование:
 *   php panel/bin/migrate.php            — применить все новые миграции
 *   php panel/bin/migrate.php --status   — показать, что применено
 */

$root = dirname(__DIR__, 3);
require $root . '/hosting/autoload.php';

use Hosting\Config;
use Hosting\Support\Env;

Env::load($root . '/.env');

$config = Config::fromEnv();
$migrationsDir = $root . '/hosting/migrations';

$dsn = sprintf(
    'mysql:host=%s;port=%d;charset=utf8mb4',
    $config->str('db_host'),
    $config->int('db_port'),
);

$pdo = new PDO($dsn, $config->str('db_username'), $config->str('db_password'), [
    PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
]);

$dbName = $config->str('db_database');
$pdo->exec(sprintf(
    'CREATE DATABASE IF NOT EXISTS `%s` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci',
    str_replace('`', '', $dbName)
));
$pdo->exec('USE `' . str_replace('`', '', $dbName) . '`');

$pdo->exec(<<<'SQL'
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version    VARCHAR(190) PRIMARY KEY,
        applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
SQL);

$applied = $pdo->query('SELECT version FROM schema_migrations')->fetchAll(PDO::FETCH_COLUMN);
$applied = array_flip($applied);

$showStatus = in_array('--status', $argv, true);

$files = glob($migrationsDir . '/*.sql') ?: [];
sort($files, SORT_STRING);

if ($files === []) {
    fwrite(STDERR, "Миграции не найдены в {$migrationsDir}\n");
    exit(1);
}

$appliedCount = 0;

foreach ($files as $file) {
    $version = basename($file);
    $isApplied = isset($applied[$version]);

    if ($showStatus) {
        echo ($isApplied ? '[x] ' : '[ ] ') . $version . "\n";
        continue;
    }

    if ($isApplied) {
        continue;
    }

    $sql = (string) file_get_contents($file);
    echo "Применяю {$version}... ";

    try {
        // Несколько statements в одном файле — выполняем без emulate prepares,
        // поэтому используем exec() на полном файле (multi-statement допустим в PDO_MYSQL exec).
        $pdo->exec($sql);
        $stmt = $pdo->prepare('INSERT INTO schema_migrations (version) VALUES (?)');
        $stmt->execute([$version]);
        echo "OK\n";
        $appliedCount++;
    } catch (\Throwable $e) {
        echo "ОШИБКА\n";
        fwrite(STDERR, $version . ': ' . $e->getMessage() . "\n");
        exit(1);
    }
}

if (!$showStatus) {
    echo $appliedCount === 0 ? "Новых миграций нет.\n" : "Применено миграций: {$appliedCount}\n";
}
