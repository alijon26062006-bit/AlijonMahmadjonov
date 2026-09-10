<?php
declare(strict_types=1);

namespace Hosting;

use PDO;

/**
 * Подключение к панельной БД.
 *
 * Production: только MariaDB (см. migrations/*.sql, применяются bin/migrate.php).
 * Тесты: SQLite в памяти с зеркальной схемой (tests/schema.sqlite.sql) — чтобы юнит-тесты
 * репозиториев и security-тесты можно было гонять без поднятого сервера MariaDB.
 * Драйвер выбирается через DB_DRIVER=mysql|sqlite, по умолчанию mysql.
 *
 * Сама Database НЕ содержит бизнес-схемы — таблицы создаются миграциями/тестовым бутстрапом,
 * а не здесь, чтобы существовал ровно один источник истины для схемы (миграции).
 */
final class Database
{
    private PDO $pdo;
    private string $driver;

    public function __construct(Config $config)
    {
        $this->driver = $config->str('db_driver') === 'sqlite' ? 'sqlite' : 'mysql';

        if ($this->driver === 'sqlite') {
            $path = $config->str('db_sqlite_path');
            if ($path !== ':memory:') {
                $dir = dirname($path);
                if (!is_dir($dir)) {
                    mkdir($dir, 0o750, true);
                }
            }
            $this->pdo = new PDO('sqlite:' . $path, null, null, [
                PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
                PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            ]);
            $this->pdo->exec('PRAGMA foreign_keys = ON');
            return;
        }

        $dsn = sprintf(
            'mysql:host=%s;port=%d;dbname=%s;charset=utf8mb4',
            $config->str('db_host'),
            $config->int('db_port'),
            $config->str('db_database'),
        );

        $this->pdo = new PDO($dsn, $config->str('db_username'), $config->str('db_password'), [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES   => false,
            PDO::MYSQL_ATTR_INIT_COMMAND => "SET time_zone = '+00:00'",
        ]);
    }

    /** Для тестов: обернуть уже открытое PDO-соединение (например, SQLite in-memory с готовой схемой). */
    public static function fromPdo(PDO $pdo, string $driver = 'sqlite'): self
    {
        $instance = (new \ReflectionClass(self::class))->newInstanceWithoutConstructor();
        $instance->pdo = $pdo;
        $instance->driver = $driver;
        return $instance;
    }

    public function pdo(): PDO
    {
        return $this->pdo;
    }

    public function driver(): string
    {
        return $this->driver;
    }

    public function isMysql(): bool
    {
        return $this->driver === 'mysql';
    }

    public function log(?int $userId, string $action, string $objectType = '', ?int $objectId = null, string $result = 'success', array $details = [], string $ip = ''): void
    {
        $stmt = $this->pdo->prepare(
            'INSERT INTO audit_logs (user_id, actor, action, object_type, object_id, ip, result, details, created_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)'
        );
        $stmt->execute([
            $userId,
            $userId !== null ? ('user:' . $userId) : 'system',
            $action,
            $objectType,
            $objectId,
            $ip,
            $result,
            $details === [] ? null : json_encode($details, JSON_UNESCAPED_UNICODE),
            gmdate('Y-m-d H:i:s'),
        ]);
    }

    public function recordSecurityEvent(string $eventType, string $severity, string $ip, array $details = [], ?int $userId = null): void
    {
        $stmt = $this->pdo->prepare(
            'INSERT INTO security_events (user_id, event_type, severity, ip, details, created_at) VALUES (?, ?, ?, ?, ?, ?)'
        );
        $stmt->execute([
            $userId,
            $eventType,
            $severity,
            $ip,
            $details === [] ? null : json_encode($details, JSON_UNESCAPED_UNICODE),
            gmdate('Y-m-d H:i:s'),
        ]);
    }

    /** @return list<array<string,mixed>> */
    public function recentAuditLog(int $limit = 50, ?int $userId = null): array
    {
        if ($userId === null) {
            $stmt = $this->pdo->prepare('SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?');
            $stmt->bindValue(1, $limit, PDO::PARAM_INT);
        } else {
            $stmt = $this->pdo->prepare('SELECT * FROM audit_logs WHERE user_id = ? ORDER BY id DESC LIMIT ?');
            $stmt->bindValue(1, $userId, PDO::PARAM_INT);
            $stmt->bindValue(2, $limit, PDO::PARAM_INT);
        }
        $stmt->execute();
        return $stmt->fetchAll();
    }
}
