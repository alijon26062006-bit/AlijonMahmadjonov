<?php

declare(strict_types=1);

/**
 * Тестовый бутстрап: поднимает SQLite in-memory по зеркальной схеме (schema.sqlite.sql)
 * и собирает те же классы, что использует боевая панель, только с Config, где
 * db_driver=sqlite. Никакой отдельной "тестовой" бизнес-логики — тестируется тот же код.
 */

require dirname(__DIR__) . '/autoload.php';

use Hosting\Config;
use Hosting\Database;

/** Создаёт новую independent-от-других-тестов in-memory базу с применённой схемой. */
function hosting_test_db(): Database
{
    $pdo = new PDO('sqlite::memory:', null, null, [
        PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
        PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
    ]);
    $pdo->exec('PRAGMA foreign_keys = ON');

    $schema = (string) file_get_contents(__DIR__ . '/schema.sqlite.sql');
    $pdo->exec($schema);

    return Database::fromPdo($pdo, 'sqlite');
}

function hosting_test_config(array $overrides = []): Config
{
    return Config::fromEnv(array_merge([
        'HOSTING_ROOT_DOMAIN' => 'myhost.tj',
        'DB_DRIVER'           => 'sqlite',
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
