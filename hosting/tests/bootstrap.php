<?php

declare(strict_types=1);

/**
 * Тестовый бутстрап. Умеет два режима:
 *
 *   SQLite (по умолчанию)  — быстро, работает где угодно, но прощает то, на чём
 *                            боевая MariaDB падает: зарезервированные слова,
 *                            повторные именованные параметры в prepared statement
 *                            и прочие расхождения диалектов.
 *   MariaDB (HOSTING_TEST_MYSQL_DB=имя_базы) — те же тесты, но на НАСТОЯЩЕЙ базе
 *                            с НАСТОЯЩИМИ миграциями из migrations/*.sql.
 *
 * Второй режим появился после того, как три бага подряд прошли SQLite-тесты и
 * упали на боевом сервере. Перед выкладкой прогонять обязательно оба:
 *
 *   php hosting/tests/run.php                              # SQLite
 *   HOSTING_TEST_MYSQL_DB=hosting_panel_test php hosting/tests/run.php   # MariaDB
 */

require dirname(__DIR__) . '/autoload.php';

use Hosting\Config;
use Hosting\Database;

function hosting_test_uses_mysql(): bool
{
    $db = getenv('HOSTING_TEST_MYSQL_DB');
    return is_string($db) && $db !== '';
}

/** Создаёт чистую базу с применённой схемой — SQLite in-memory или реальную MariaDB. */
function hosting_test_db(): Database
{
    if (hosting_test_uses_mysql()) {
        return hosting_test_mysql_db();
    }

    $pdo = new PDO('sqlite::memory:', null, null, [
        PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ]);
    $pdo->exec('PRAGMA foreign_keys = ON');

    $schema = (string) file_get_contents(__DIR__ . '/schema.sqlite.sql');
    $pdo->exec($schema);

    return Database::fromPdo($pdo, 'sqlite');
}

/**
 * Реальная MariaDB. Схема накатывается настоящими миграциями один раз за прогон,
 * между тестами таблицы просто очищаются — иначе 16 миграций на каждый тест
 * съели бы всё время.
 */
function hosting_test_mysql_db(): Database
{
    static $pdo = null;
    static $tables = [];

    $dbName = (string) getenv('HOSTING_TEST_MYSQL_DB');
    $host = getenv('HOSTING_TEST_MYSQL_HOST') ?: '127.0.0.1';
    $user = getenv('HOSTING_TEST_MYSQL_USER') ?: 'root';
    $pass = getenv('HOSTING_TEST_MYSQL_PASSWORD') ?: '';

    if ($pdo === null) {
        $root = new PDO("mysql:host={$host};charset=utf8mb4", $user, $pass, [
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
        ]);
        $root->exec("DROP DATABASE IF EXISTS `{$dbName}`");
        $root->exec("CREATE DATABASE `{$dbName}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci");

        $pdo = new PDO("mysql:host={$host};dbname={$dbName};charset=utf8mb4", $user, $pass, [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            // Ровно как в проде (см. Hosting\Database): нативные prepared statements.
            // Именно они ловят повторное использование одного :параметра — эмуляция
            // такое прощает, а сервер отвечает HY093 Invalid parameter number.
            PDO::ATTR_EMULATE_PREPARES   => false,
        ]);

        foreach (glob(dirname(__DIR__) . '/migrations/*.sql') ?: [] as $file) {
            $pdo->exec((string) file_get_contents($file));
        }

        $tables = $pdo->query('SHOW TABLES')->fetchAll(PDO::FETCH_COLUMN);
    }

    // Чистим состояние между тестами, plans пересоздаём — на них завязаны тарифы.
    $pdo->exec('SET FOREIGN_KEY_CHECKS = 0');
    foreach ($tables as $table) {
        $pdo->exec("TRUNCATE TABLE `{$table}`");
    }
    $pdo->exec('SET FOREIGN_KEY_CHECKS = 1');
    $pdo->exec((string) file_get_contents(dirname(__DIR__) . '/migrations/0001_create_plans.sql'));

    return Database::fromPdo($pdo, 'mysql');
}

function hosting_test_config(array $overrides = []): Config
{
    return Config::fromEnv(array_merge([
        'HOSTING_ROOT_DOMAIN' => 'myhost.tj',
        'DB_DRIVER'           => hosting_test_uses_mysql() ? 'mysql' : 'sqlite',
    ], $overrides));
}

/** Простейший test runner: функции test_*() в файле выполняются по очереди. */
final class HostingTestRunner
{
    private static int $passed = 0;
    private static int $failed = 0;
    private static string $current = '';

    public static function run(string $file): void
    {
        self::$current = basename($file);
        $functions = get_defined_functions()['user'];
        require $file;
        $after = get_defined_functions()['user'];
        $new = array_diff($after, $functions);

        foreach ($new as $fn) {
            if (!str_starts_with($fn, 'test_')) {
                continue;
            }
            self::runOne($fn);
        }
    }

    private static function runOne(string $fn): void
    {
        try {
            $fn();
            self::$passed++;
            echo "  ✓ {$fn}\n";
        } catch (\Throwable $e) {
            self::$failed++;
            echo "  ✗ {$fn}: {$e->getMessage()}\n";
            echo '    в ' . $e->getFile() . ':' . $e->getLine() . "\n";
        }
    }

    public static function summary(): int
    {
        $total = self::$passed + self::$failed;
        echo "\n{$total} тестов, " . self::$passed . " успешно, " . self::$failed . " провалено\n";
        return self::$failed === 0 ? 0 : 1;
    }
}

function assert_true(bool $condition, string $message = 'Ожидалось true'): void
{
    if (!$condition) {
        throw new \RuntimeException($message);
    }
}

function assert_false(bool $condition, string $message = 'Ожидалось false'): void
{
    assert_true(!$condition, $message);
}

function assert_equals(mixed $expected, mixed $actual, string $message = ''): void
{
    if ($expected !== $actual) {
        $message = $message !== '' ? $message : 'Значения не равны';
        throw new \RuntimeException(
            $message . ': ожидалось ' . var_export($expected, true) . ', получено ' . var_export($actual, true)
        );
    }
}

function assert_throws(callable $fn, string $message = 'Ожидалось исключение'): void
{
    try {
        $fn();
    } catch (\Throwable) {
        return;
    }
    throw new \RuntimeException($message);
}
