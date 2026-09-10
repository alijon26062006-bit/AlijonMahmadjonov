<?php
declare(strict_types=1);

namespace Hosting\Model;

use Hosting\Database;
use PDO;

final class NotificationRepository
{
    public function __construct(private Database $db)
    {
    }

    public function create(?int $userId, string $channel, string $title, string $body): void
    {
        $this->db->pdo()->prepare(
            'INSERT INTO notifications (user_id, channel, title, body, is_read, created_at) VALUES (?, ?, ?, ?, 0, ?)'
        )->execute([$userId, $channel, $title, $body, gmdate('Y-m-d H:i:s')]);
    }

    /** @return list<array<string,mixed>> */
    public function forUser(int $userId, int $limit = 20): array
    {
        $stmt = $this->db->pdo()->prepare('SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT ?');
        $stmt->bindValue(1, $userId, PDO::PARAM_INT);
        $stmt->bindValue(2, $limit, PDO::PARAM_INT);
        $stmt->execute();
        return $stmt->fetchAll();
    }

    public function unreadCount(int $userId): int
    {
        $stmt = $this->db->pdo()->prepare('SELECT COUNT(*) AS c FROM notifications WHERE user_id = ? AND is_read = 0');
        $stmt->execute([$userId]);
        return (int) $stmt->fetch()['c'];
    }

    public function markAllRead(int $userId): void
    {
        $this->db->pdo()->prepare('UPDATE notifications SET is_read = 1 WHERE user_id = ?')->execute([$userId]);
    }
}
