<?php
declare(strict_types=1);

namespace Hosting\Model;

use Hosting\Database;

final class TelegramAccountRepository
{
    public function __construct(private Database $db)
    {
    }

    /** @param array{id:int,username?:string,first_name?:string,last_name?:string} $tgUser */
    public function link(int $userId, array $tgUser): void
    {
        $telegramId = (int) $tgUser['id'];
        $existing = $this->findByTelegramId($telegramId);
        if ($existing !== null && (int) $existing['user_id'] !== $userId) {
            throw new \RuntimeException('Этот Telegram уже привязан к другому аккаунту');
        }

        $stmt = $this->db->pdo()->prepare(
            'INSERT INTO telegram_accounts (user_id, telegram_id, username, first_name, last_name, linked_at)
             VALUES (?, ?, ?, ?, ?, ?)
             ON DUPLICATE KEY UPDATE username = VALUES(username), first_name = VALUES(first_name), last_name = VALUES(last_name)'
        );

        if ($this->db->driver() === 'sqlite') {
            // SQLite не понимает ON DUPLICATE KEY UPDATE — эмулируем через INSERT OR REPLACE.
            $stmt = $this->db->pdo()->prepare(
                'INSERT INTO telegram_accounts (user_id, telegram_id, username, first_name, last_name, linked_at)
                 VALUES (?, ?, ?, ?, ?, ?)'
            );
        }

        $stmt->execute([
            $userId,
            $telegramId,
            (string) ($tgUser['username'] ?? ''),
            (string) ($tgUser['first_name'] ?? ''),
            (string) ($tgUser['last_name'] ?? ''),
            gmdate('Y-m-d H:i:s'),
        ]);
    }

    public function findByTelegramId(int $telegramId): ?array
    {
        $stmt = $this->db->pdo()->prepare('SELECT * FROM telegram_accounts WHERE telegram_id = ?');
        $stmt->execute([$telegramId]);
        $row = $stmt->fetch();
        return $row === false ? null : $row;
    }

    public function findByUserId(int $userId): ?array
    {
        $stmt = $this->db->pdo()->prepare('SELECT * FROM telegram_accounts WHERE user_id = ?');
        $stmt->execute([$userId]);
        $row = $stmt->fetch();
        return $row === false ? null : $row;
    }
}
