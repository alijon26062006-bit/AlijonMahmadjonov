<?php
declare(strict_types=1);

namespace Hosting;

use PDO;

/**
 * SQLite-хранилище панели: пользователи, сайты, базы данных, журнал действий.
 */
final class Database
{
    private PDO $pdo;

    public function __construct(string $path)
    {
        if ($path !== ':memory:') {
            $dir = dirname($path);
            if (!is_dir($dir)) {
                mkdir($dir, 0o750, true);
            }
        }

        $this->pdo = new PDO('sqlite:' . $path, null, null, [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES   => false,
        ]);
        $this->pdo->exec('PRAGMA journal_mode = WAL');
        $this->pdo->exec('PRAGMA foreign_keys = ON');
        $this->migrate();
    }

    public function pdo(): PDO
    {
        return $this->pdo;
    }

    private function migrate(): void
    {
        $this->pdo->exec(<<<'SQL'
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                -- Вход возможен двумя путями: e-mail с паролем или Telegram Mini App.
                -- Поэтому оба поля необязательные, но каждое — уникальное.
                email         TEXT    UNIQUE,
                password_hash TEXT    NOT NULL DEFAULT '',
                telegram_id   INTEGER UNIQUE,
                telegram_name TEXT    NOT NULL DEFAULT '',
                display_name  TEXT    NOT NULL DEFAULT '',
                system_user   TEXT    NOT NULL DEFAULT '',
                plan          TEXT    NOT NULL DEFAULT 'start',
                disk_quota_mb INTEGER NOT NULL DEFAULT 1024,
                max_sites     INTEGER NOT NULL DEFAULT 1,
                max_databases INTEGER NOT NULL DEFAULT 1,
                is_admin      INTEGER NOT NULL DEFAULT 0,
                is_active     INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT    NOT NULL
            )
        SQL);

        $this->pdo->exec(<<<'SQL'
            CREATE TABLE IF NOT EXISTS sites (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                domain      TEXT    NOT NULL UNIQUE,
                doc_root    TEXT    NOT NULL DEFAULT 'public_html',
                php_version TEXT    NOT NULL DEFAULT '8.3',
                is_active   INTEGER NOT NULL DEFAULT 1,
                created_at  TEXT    NOT NULL
            )
        SQL);

        $this->pdo->exec(<<<'SQL'
            CREATE TABLE IF NOT EXISTS databases (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name       TEXT    NOT NULL UNIQUE,
                db_user    TEXT    NOT NULL UNIQUE,
                created_at TEXT    NOT NULL
            )
        SQL);

        $this->pdo->exec(<<<'SQL'
            CREATE TABLE IF NOT EXISTS audit_log (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER,
                action     TEXT NOT NULL,
                details    TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
        SQL);

        $this->pdo->exec(<<<'SQL'
            CREATE TABLE IF NOT EXISTS state (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        SQL);
    }

    public function setState(string $key, string $value): void
    {
        $stmt = $this->pdo->prepare(
            'INSERT INTO state (key, value) VALUES (?, ?)
             ON CONFLICT(key) DO UPDATE SET value = excluded.value'
        );
        $stmt->execute([$key, $value]);
    }

    public function getState(string $key, ?string $default = null): ?string
    {
        $stmt = $this->pdo->prepare('SELECT value FROM state WHERE key = ?');
        $stmt->execute([$key]);
        $row = $stmt->fetch();
        return $row === false ? $default : (string) $row['value'];
    }

    public function log(?int $userId, string $action, string $details = ''): void
    {
        $stmt = $this->pdo->prepare(
            'INSERT INTO audit_log (user_id, action, details, created_at) VALUES (?, ?, ?, ?)'
        );
        $stmt->execute([$userId, $action, $details, gmdate('c')]);
    }

    /** @return list<array<string,mixed>> */
    public function recentLog(int $limit = 50, ?int $userId = null): array
    {
        if ($userId === null) {
            $stmt = $this->pdo->prepare('SELECT * FROM audit_log ORDER BY id DESC LIMIT ?');
            $stmt->execute([$limit]);
        } else {
            $stmt = $this->pdo->prepare(
                'SELECT * FROM audit_log WHERE user_id = ? ORDER BY id DESC LIMIT ?'
            );
            $stmt->execute([$userId, $limit]);
        }
        return $stmt->fetchAll();
    }
}
