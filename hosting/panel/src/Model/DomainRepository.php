<?php
declare(strict_types=1);

namespace Hosting\Model;

use Hosting\Database;

/** Собственные домены клиентов, привязанные к сайту (custom domain + SSL flow). */
final class DomainRepository
{
    public function __construct(private Database $db)
    {
    }

    public function create(int $siteId, string $domain): array
    {
        $stmt = $this->db->pdo()->prepare(
            'INSERT INTO domains (site_id, domain, is_primary, verified, ssl_status, created_at)
             VALUES (?, ?, 0, 0, \'none\', ?)'
        );
        $stmt->execute([$siteId, strtolower($domain), gmdate('Y-m-d H:i:s')]);

        return $this->findById((int) $this->db->pdo()->lastInsertId())
            ?? throw new \RuntimeException('Не удалось сохранить домен');
    }

    public function findById(int $id): ?array
    {
        $stmt = $this->db->pdo()->prepare('SELECT * FROM domains WHERE id = ?');
        $stmt->execute([$id]);
        $row = $stmt->fetch();
        return $row === false ? null : $row;
    }

    public function findByDomain(string $domain): ?array
    {
        $stmt = $this->db->pdo()->prepare('SELECT * FROM domains WHERE domain = ?');
        $stmt->execute([strtolower($domain)]);
        $row = $stmt->fetch();
        return $row === false ? null : $row;
    }

    /** @return list<array<string,mixed>> */
    public function forSite(int $siteId): array
    {
        $stmt = $this->db->pdo()->prepare('SELECT * FROM domains WHERE site_id = ? ORDER BY id');
        $stmt->execute([$siteId]);
        return $stmt->fetchAll();
    }

    public function markVerified(int $id): void
    {
        $this->db->pdo()->prepare(
            'UPDATE domains SET verified = 1, verified_at = ?, last_error = "" WHERE id = ?'
        )->execute([gmdate('Y-m-d H:i:s'), $id]);
    }

    public function markVerificationFailed(int $id, string $error): void
    {
        $this->db->pdo()->prepare(
            'UPDATE domains SET verified = 0, last_check_at = ?, last_error = ? WHERE id = ?'
        )->execute([gmdate('Y-m-d H:i:s'), substr($error, 0, 255), $id]);
    }

    public function setSslStatus(int $id, string $status): void
    {
        $allowed = ['none', 'pending', 'issued', 'failed'];
        if (!in_array($status, $allowed, true)) {
            throw new \InvalidArgumentException('Недопустимый статус SSL: ' . $status);
        }
        $issuedAt = $status === 'issued' ? gmdate('Y-m-d H:i:s') : null;
        $this->db->pdo()->prepare(
            'UPDATE domains SET ssl_status = ?, ssl_issued_at = COALESCE(?, ssl_issued_at) WHERE id = ?'
        )->execute([$status, $issuedAt, $id]);
    }

    public function delete(int $id): void
    {
        $this->db->pdo()->prepare('DELETE FROM domains WHERE id = ?')->execute([$id]);
    }
}
