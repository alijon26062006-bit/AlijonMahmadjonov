<?php

namespace CargoBot\Repository;

use CargoBot\Database;

class UserRepo
{
    private Database $db;

    public function __construct(Database $db)
    {
        $this->db = $db;
    }

    public function byTgId(int $tgId): ?array
    {
        return $this->db->one('SELECT * FROM users WHERE tg_id = :t', ['t' => $tgId]);
    }

    public function byId(int $id): ?array
    {
        return $this->db->one('SELECT * FROM users WHERE id = :i', ['i' => $id]);
    }

    /**
     * Создаёт или обновляет пользователя.
     * @return array{0:array,1:bool} [пользователь, создан ли только что]
     */
    public function upsert(int $tgId, ?string $username, ?string $fullName): array
    {
        $user = $this->byTgId($tgId);
        if ($user) {
            if (($user['username'] ?? null) !== $username || ($user['full_name'] ?? null) !== $fullName) {
                $this->db->update('users', (int) $user['id'], [
                    'username'  => $username,
                    'full_name' => $fullName,
                ]);
                $user['username'] = $username;
                $user['full_name'] = $fullName;
            }
            return [$user, false];
        }
        $id = $this->db->insert('users', [
            'tg_id'      => $tgId,
            'username'   => $username,
            'full_name'  => $fullName,
            'created_at' => $this->db->now(),
        ]);
        return [$this->byId($id), true];
    }

    /** @return int[] Telegram ID активных админов из таблицы admins. */
    public function adminTgIds(): array
    {
        $rows = $this->db->all('SELECT tg_id FROM admins WHERE is_active = 1');
        return array_map(fn($r) => (int) $r['tg_id'], $rows);
    }
}
