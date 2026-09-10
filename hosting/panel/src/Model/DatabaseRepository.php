<?php
declare(strict_types=1);

namespace Hosting\Model;

use Hosting\Database;

/** Учёт баз данных MySQL/MariaDB, выданных клиентам. */
final class DatabaseRepository
{
    public function __construct(private Database $db)
    {
    }

    public function create(int $userId, string $name, string $dbUser): array
    {
        $stmt = $this->db->pdo()->prepare(
            'INSERT INTO databases (user_id, name, db_user, created_at) VALUES (?, ?, ?, ?)'
        );
        $stmt->execute([$userId, $name, $dbUser, gmdate('c')]);

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

    /** @return list<array<string,mixed>> */
    public function forUser(int $userId): array
    {
        $stmt = $this->db->pdo()->prepare('SELECT * FROM databases WHERE user_id = ? ORDER BY id');
        $stmt->execute([$userId]);
        return $stmt->fetchAll();
    }

    public function countForUser(int $userId): int
    {
        $stmt = $this->db->pdo()->prepare('SELECT COUNT(*) AS c FROM databases WHERE user_id = ?');
        $stmt->execute([$userId]);
        return (int) $stmt->fetch()['c'];
    }

    public function delete(int $id): void
    {
        $this->db->pdo()->prepare('DELETE FROM databases WHERE id = ?')->execute([$id]);
    }
}
