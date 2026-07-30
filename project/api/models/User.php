<?php
declare(strict_types=1);

namespace Models;

final class User extends Model
{
    /**
     * Insert or update a user from a validated Telegram `user` object.
     * Returns the internal users.id.
     */
    public function upsertFromTelegram(array $tg): int
    {
        $sql = "INSERT INTO users
                    (telegram_id, username, first_name, last_name, language_code, photo_url, is_premium, last_seen_at)
                VALUES
                    (:tid, :username, :first_name, :last_name, :lang, :photo, :premium, NOW())
                ON DUPLICATE KEY UPDATE
                    username      = VALUES(username),
                    first_name    = VALUES(first_name),
                    last_name     = VALUES(last_name),
                    language_code = VALUES(language_code),
                    photo_url     = VALUES(photo_url),
                    is_premium    = VALUES(is_premium),
                    last_seen_at  = NOW()";

        $stmt = $this->db->prepare($sql);
        $stmt->execute([
            ':tid'        => (int) ($tg['id'] ?? 0),
            ':username'   => $tg['username']      ?? null,
            ':first_name' => $tg['first_name']    ?? null,
            ':last_name'  => $tg['last_name']     ?? null,
            ':lang'       => $tg['language_code'] ?? 'ru',
            ':photo'      => $tg['photo_url']     ?? null,
            ':premium'    => !empty($tg['is_premium']) ? 1 : 0,
        ]);

        $stmt = $this->db->prepare("SELECT id FROM users WHERE telegram_id = ?");
        $stmt->execute([(int) ($tg['id'] ?? 0)]);
        return (int) $stmt->fetchColumn();
    }

    public function profile(int $userId): ?array
    {
        $stmt = $this->db->prepare(
            "SELECT u.*,
                    (SELECT COUNT(*) FROM favorites f WHERE f.user_id = u.id) AS favorites_count,
                    (SELECT COUNT(*) FROM history   h WHERE h.user_id = u.id) AS history_count
             FROM users u WHERE u.id = ?"
        );
        $stmt->execute([$userId]);
        $row = $stmt->fetch();
        return $row ?: null;
    }
}
