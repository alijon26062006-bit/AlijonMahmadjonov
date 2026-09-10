<?php
declare(strict_types=1);

namespace Hosting\Model;

use Hosting\Database;

final class PlanRepository
{
    public function __construct(private Database $db)
    {
    }

    /** @return list<array<string,mixed>> */
    public function all(bool $activeOnly = true): array
    {
        $sql = 'SELECT * FROM plans' . ($activeOnly ? ' WHERE is_active = 1' : '') . ' ORDER BY price_tjs';
        return $this->db->pdo()->query($sql)->fetchAll();
    }

    public function findByCode(string $code): ?array
    {
        $stmt = $this->db->pdo()->prepare('SELECT * FROM plans WHERE code = ?');
        $stmt->execute([$code]);
        $row = $stmt->fetch();
        return $row === false ? null : $row;
    }

    public function findById(int $id): ?array
    {
        $stmt = $this->db->pdo()->prepare('SELECT * FROM plans WHERE id = ?');
        $stmt->execute([$id]);
        $row = $stmt->fetch();
        return $row === false ? null : $row;
    }

    public function exists(string $code): bool
    {
        return $this->findByCode($code) !== null;
    }
}
