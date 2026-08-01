<?php

namespace CargoBot;

/** Обёртка над PDO: работает и с MySQL, и с SQLite. */
class Database
{
    private \PDO $pdo;
    private string $driver;

    public function __construct(array $db)
    {
        $dsn = $db['dsn'];
        if (strncmp($dsn, 'sqlite:', 7) === 0) {
            $file = substr($dsn, 7);
            $dir = dirname($file);
            if ($file !== ':memory:' && !is_dir($dir)) {
                @mkdir($dir, 0775, true);
            }
        }
        $this->pdo = new \PDO($dsn, $db['user'] ?? null, $db['pass'] ?? null, [
            \PDO::ATTR_ERRMODE            => \PDO::ERRMODE_EXCEPTION,
            \PDO::ATTR_DEFAULT_FETCH_MODE => \PDO::FETCH_ASSOC,
            \PDO::ATTR_EMULATE_PREPARES   => false,
        ]);
        $this->driver = $this->pdo->getAttribute(\PDO::ATTR_DRIVER_NAME);
        if ($this->driver === 'sqlite') {
            $this->pdo->exec('PRAGMA foreign_keys = ON');
        }
    }

    public function pdo(): \PDO
    {
        return $this->pdo;
    }

    public function driver(): string
    {
        return $this->driver;
    }

    public function run(string $sql, array $params = []): \PDOStatement
    {
        $stmt = $this->pdo->prepare($sql);
        $stmt->execute($params);
        return $stmt;
    }

    /** @return array<string,mixed>|null */
    public function one(string $sql, array $params = []): ?array
    {
        $row = $this->run($sql, $params)->fetch();
        return $row === false ? null : $row;
    }

    /** @return array<int,array<string,mixed>> */
    public function all(string $sql, array $params = []): array
    {
        return $this->run($sql, $params)->fetchAll();
    }

    /** @return mixed */
    public function value(string $sql, array $params = [])
    {
        $v = $this->run($sql, $params)->fetchColumn();
        return $v === false ? null : $v;
    }

    public function insert(string $table, array $data): int
    {
        $cols = array_keys($data);
        $ph = array_map(fn($c) => ':' . $c, $cols);
        $sql = sprintf(
            'INSERT INTO %s (%s) VALUES (%s)',
            $table,
            implode(', ', $cols),
            implode(', ', $ph)
        );
        $this->run($sql, $data);
        return (int) $this->pdo->lastInsertId();
    }

    public function update(string $table, int $id, array $data): void
    {
        if (!$data) {
            return;
        }
        $sets = array_map(fn($c) => "$c = :$c", array_keys($data));
        $data['__id'] = $id;
        $this->run(
            sprintf('UPDATE %s SET %s WHERE id = :__id', $table, implode(', ', $sets)),
            $data
        );
    }

    public function delete(string $table, int $id): void
    {
        $this->run("DELETE FROM $table WHERE id = :id", ['id' => $id]);
    }

    public function now(): string
    {
        return date('Y-m-d H:i:s');
    }
}
