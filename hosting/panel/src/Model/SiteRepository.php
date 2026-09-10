<?php
declare(strict_types=1);

namespace Hosting\Model;

use Hosting\Database;

final class SiteRepository
{
    public function __construct(private Database $db)
    {
    }

    public function create(int $userId, string $domain, string $phpVersion, string $docRoot = 'public_html'): array
    {
        $stmt = $this->db->pdo()->prepare(
            'INSERT INTO sites (user_id, domain, doc_root, php_version, is_active, created_at)
             VALUES (?, ?, ?, ?, 1, ?)'
        );
        $stmt->execute([$userId, $domain, $docRoot, $phpVersion, gmdate('c')]);

        return $this->findById((int) $this->db->pdo()->lastInsertId())
            ?? throw new \RuntimeException('Не удалось создать сайт');
    }

    public function findById(int $id): ?array
    {
        $stmt = $this->db->pdo()->prepare('SELECT * FROM sites WHERE id = ?');
        $stmt->execute([$id]);
        $row = $stmt->fetch();
        return $row === false ? null : $row;
    }

    public function findByDomain(string $domain): ?array
    {
        $stmt = $this->db->pdo()->prepare('SELECT * FROM sites WHERE domain = ?');
        $stmt->execute([strtolower($domain)]);
        $row = $stmt->fetch();
        return $row === false ? null : $row;
    }

    /** @return list<array<string,mixed>> */
    public function forUser(int $userId): array
    {
        $stmt = $this->db->pdo()->prepare('SELECT * FROM sites WHERE user_id = ? ORDER BY id');
        $stmt->execute([$userId]);
        return $stmt->fetchAll();
    }

    /** @return list<array<string,mixed>> */
    public function all(): array
    {
        return $this->db->pdo()->query('SELECT * FROM sites ORDER BY id')->fetchAll();
    }

    public function countForUser(int $userId): int
    {
        $stmt = $this->db->pdo()->prepare('SELECT COUNT(*) AS c FROM sites WHERE user_id = ?');
        $stmt->execute([$userId]);
        return (int) $stmt->fetch()['c'];
    }

    public function setActive(int $id, bool $active): void
    {
        $this->db->pdo()->prepare('UPDATE sites SET is_active = ? WHERE id = ?')
            ->execute([$active ? 1 : 0, $id]);
    }

    public function setPhpVersion(int $id, string $version): void
    {
        $this->db->pdo()->prepare('UPDATE sites SET php_version = ? WHERE id = ?')
            ->execute([$version, $id]);
    }

    public function delete(int $id): void
    {
        $this->db->pdo()->prepare('DELETE FROM sites WHERE id = ?')->execute([$id]);
    }
}
