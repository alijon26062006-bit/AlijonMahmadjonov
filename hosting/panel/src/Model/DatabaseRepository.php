<?php
declare(strict_types=1);

namespace Hosting\Model;

use Hosting\Database;

/**
 * Учёт клиентских баз MariaDB. Панель только записывает намерение и читает статус —
 * реальные CREATE DATABASE/CREATE USER выполняет root worker через таблицу jobs
 * (см. Hosting\Worker и JobRepository). Веб-процесс панели учётки администратора MySQL не держит.
 */
final class DatabaseRepository
{
    public function __construct(private Database $db)
    {
    }

    public function create(int $userId, ?int $siteId, string $dbName): array
    {
        $stmt = $this->db->pdo()->prepare(
            'INSERT INTO databases (user_id, site_id, db_name, status, created_at) VALUES (?, ?, ?, "pending", ?)'
        );
        $stmt->execute([$userId, $siteId, $dbName, gmdate('Y-m-d H:i:s')]);

        return $this->findById((int) $this->db->pdo()->lastInsertId())
            ?? throw new \RuntimeException('Не удалось создать запись о базе');
    }

    public function findById(int $id): ?array
    {
        $stmt = $this->db->pdo()->prepare('SELECT * FROM databases WHERE id = ?');
        $stmt->execute([$id]);
        $row = $stmt->fetch();
        return $row === false ? null : $row;
    }

    public function findByName(string $dbName): ?array
    {
        $stmt = $this->db->pdo()->prepare('SELECT * FROM databases WHERE db_name = ?');
        $stmt->execute([$dbName]);
        $row = $stmt->fetch();
        return $row === false ? null : $row;
    }

    /** @return list<array<string,mixed>> */
    public function forUser(int $userId): array
    {
        $stmt = $this->db->pdo()->prepare("SELECT * FROM databases WHERE user_id = ? AND status != 'deleted' ORDER BY id");
        $stmt->execute([$userId]);
        return $stmt->fetchAll();
    }

    public function countActiveForUser(int $userId): int
    {
        $stmt = $this->db->pdo()->prepare(
            "SELECT COUNT(*) AS c FROM databases WHERE user_id = ? AND status != 'deleted'"
        );
        $stmt->execute([$userId]);
        return (int) $stmt->fetch()['c'];
    }

    public function setStatus(int $id, string $status): void
    {
        $allowed = ['pending', 'active', 'failed', 'deleted'];
        if (!in_array($status, $allowed, true)) {
            throw new \InvalidArgumentException('Недопустимый статус базы: ' . $status);
        }
        $this->db->pdo()->prepare('UPDATE databases SET status = ? WHERE id = ?')->execute([$status, $id]);
    }

    public function delete(int $id): void
    {
        $this->db->pdo()->prepare('DELETE FROM databases WHERE id = ?')->execute([$id]);
    }

    public static function belongsToUser(?array $database, int $userId): bool
    {
        return $database !== null && (int) $database['user_id'] === $userId;
    }
}
