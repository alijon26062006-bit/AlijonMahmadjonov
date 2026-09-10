<?php
declare(strict_types=1);

namespace Hosting\Model;

use Hosting\Database;
use PDO;

final class BackupRepository
{
    public function __construct(private Database $db)
    {
    }

    public function create(int $userId, string $type): array
    {
        $stmt = $this->db->pdo()->prepare(
            'INSERT INTO backups (user_id, type, status, created_at) VALUES (?, ?, \'pending\', ?)'
        );
        $stmt->execute([$userId, $type, gmdate('Y-m-d H:i:s')]);

        return $this->findById((int) $this->db->pdo()->lastInsertId())
            ?? throw new \RuntimeException('Не удалось создать запись о резервной копии');
    }

    public function findById(int $id): ?array
    {
        $stmt = $this->db->pdo()->prepare('SELECT * FROM backups WHERE id = ?');
        $stmt->execute([$id]);
        $row = $stmt->fetch();
        return $row === false ? null : $row;
    }

    public function markResult(int $id, string $status, string $localPath, string $checksum, int $sizeBytes, string $remotePath = ''): void
    {
        $this->db->pdo()->prepare(
            'UPDATE backups SET status = ?, local_path = ?, remote_path = ?, checksum = ?, size_bytes = ? WHERE id = ?'
        )->execute([$status, $localPath, $remotePath, $checksum, $sizeBytes, $id]);
    }

    public function markVerified(int $id): void
    {
        $this->db->pdo()->prepare('UPDATE backups SET verified_at = ? WHERE id = ?')
            ->execute([gmdate('Y-m-d H:i:s'), $id]);
    }

    /** @return list<array<string,mixed>> */
    public function forUser(int $userId, int $limit = 20): array
    {
        $stmt = $this->db->pdo()->prepare('SELECT * FROM backups WHERE user_id = ? ORDER BY id DESC LIMIT ?');
        $stmt->bindValue(1, $userId, PDO::PARAM_INT);
        $stmt->bindValue(2, $limit, PDO::PARAM_INT);
        $stmt->execute();
        return $stmt->fetchAll();
    }

    public function latestSuccessful(int $userId): ?array
    {
        $stmt = $this->db->pdo()->prepare(
            "SELECT * FROM backups WHERE user_id = ? AND status = 'success' ORDER BY id DESC LIMIT 1"
        );
        $stmt->execute([$userId]);
        $row = $stmt->fetch();
        return $row === false ? null : $row;
    }
}
