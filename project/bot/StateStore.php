<?php
declare(strict_types=1);

namespace Bot;

use Core\Database;
use PDO;

/**
 * DB-backed conversation state for admin dialogs (bot_states table).
 */
final class StateStore
{
    private PDO $db;

    public function __construct()
    {
        $this->db = Database::pdo();
    }

    public function get(int $telegramId): array
    {
        $stmt = $this->db->prepare("SELECT state, payload FROM bot_states WHERE telegram_id = ?");
        $stmt->execute([$telegramId]);
        $row = $stmt->fetch();
        if (!$row) {
            return ['state' => null, 'payload' => []];
        }
        return [
            'state'   => $row['state'],
            'payload' => json_decode($row['payload'] ?? '[]', true) ?: [],
        ];
    }

    public function set(int $telegramId, ?string $state, array $payload = []): void
    {
        $sql = "INSERT INTO bot_states (telegram_id, state, payload)
                VALUES (:id, :state, :payload)
                ON DUPLICATE KEY UPDATE state = :state2, payload = :payload2, updated_at = NOW()";
        $json = json_encode($payload, JSON_UNESCAPED_UNICODE);
        $this->db->prepare($sql)->execute([
            ':id' => $telegramId,
            ':state' => $state, ':payload' => $json,
            ':state2' => $state, ':payload2' => $json,
        ]);
    }

    public function clear(int $telegramId): void
    {
        $this->db->prepare("DELETE FROM bot_states WHERE telegram_id = ?")->execute([$telegramId]);
    }
}
