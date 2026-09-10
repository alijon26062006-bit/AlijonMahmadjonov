<?php
declare(strict_types=1);

namespace Hosting\Model;

use Hosting\Database;

final class SiteRepository
{
    public function __construct(private Database $db)
    {
    }

    public function create(int $userId, string $slug, string $domain, string $phpVersion, string $docRoot = 'public'): array
    {
        $now = gmdate('Y-m-d H:i:s');
        $stmt = $this->db->pdo()->prepare(
            'INSERT INTO sites (user_id, slug, domain, doc_root, php_version, status, created_at, updated_at)
             VALUES (?, ?, ?, ?, ?, "pending", ?, ?)'
        );
        $stmt->execute([$userId, $slug, strtolower($domain), $docRoot, $phpVersion, $now, $now]);

        return $this->findById((int) $this->db->pdo()->lastInsertId())
            ?? throw new \RuntimeException('Не удалось создать сайт');
    }

    public function findById(int $id): ?array
    {
        return $this->fetchOne('SELECT * FROM sites WHERE id = ?', [$id]);
    }

    public function findByDomain(string $domain): ?array
    {
        return $this->fetchOne('SELECT * FROM sites WHERE domain = ?', [strtolower($domain)]);
    }

    public function findBySlugForUser(int $userId, string $slug): ?array
    {
        return $this->fetchOne('SELECT * FROM sites WHERE user_id = ? AND slug = ?', [$userId, $slug]);
    }

    private function fetchOne(string $sql, array $params): ?array
    {
        $stmt = $this->db->pdo()->prepare($sql);
        $stmt->execute($params);
        $row = $stmt->fetch();
        return $row === false ? null : $row;
    }

    /** @return list<array<string,mixed>> */
    public function forUser(int $userId): array
    {
        $stmt = $this->db->pdo()->prepare("SELECT * FROM sites WHERE user_id = ? AND status != 'deleted' ORDER BY id");
        $stmt->execute([$userId]);
        return $stmt->fetchAll();
    }

    /** @return list<array<string,mixed>> */
    public function allActive(): array
    {
        return $this->db->pdo()->query("SELECT * FROM sites WHERE status = 'active' ORDER BY id")->fetchAll();
    }

    public function countActiveForUser(int $userId): int
    {
        $stmt = $this->db->pdo()->prepare(
            "SELECT COUNT(*) AS c FROM sites WHERE user_id = ? AND status != 'deleted'"
        );
        $stmt->execute([$userId]);
        return (int) $stmt->fetch()['c'];
    }

    public function setStatus(int $id, string $status): void
    {
        $allowed = ['pending', 'active', 'suspended', 'deleted'];
        if (!in_array($status, $allowed, true)) {
            throw new \InvalidArgumentException('Недопустимый статус сайта: ' . $status);
        }
        $this->db->pdo()
            ->prepare('UPDATE sites SET status = ?, updated_at = ? WHERE id = ?')
            ->execute([$status, gmdate('Y-m-d H:i:s'), $id]);
    }

    public function setPhpVersion(int $id, string $version): void
    {
        $this->db->pdo()
            ->prepare('UPDATE sites SET php_version = ?, updated_at = ? WHERE id = ?')
            ->execute([$version, gmdate('Y-m-d H:i:s'), $id]);
    }

    public function delete(int $id): void
    {
        $this->db->pdo()->prepare('DELETE FROM sites WHERE id = ?')->execute([$id]);
    }

    /** IDOR-защита: сайт существует И принадлежит именно этому клиенту. */
    public static function belongsToUser(?array $site, int $userId): bool
    {
        return $site !== null && (int) $site['user_id'] === $userId;
    }
}
