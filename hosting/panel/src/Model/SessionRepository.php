<?php
declare(strict_types=1);

namespace Hosting\Model;

use Hosting\Database;

/**
 * Серверные сессии. В cookie кладём случайный токен, в базе — только его sha256.
 * Так утечка дампа БД не даёт злоумышленнику готовые сессионные токены.
 */
final class SessionRepository
{
    public function __construct(private Database $db, private int $ttlSeconds = 1_209_600)
    {
    }

    /** @return array{token:string,expires_at:string} */
    public function create(int $userId, string $ip, string $userAgent): array
    {
        $token = bin2hex(random_bytes(32));
        $id = hash('sha256', $token);
        $now = gmdate('Y-m-d H:i:s');
        $expires = gmdate('Y-m-d H:i:s', time() + $this->ttlSeconds);

        $this->db->pdo()->prepare(
            'INSERT INTO sessions (id, user_id, ip, user_agent, created_at, last_seen_at, expires_at)
             VALUES (?, ?, ?, ?, ?, ?, ?)'
        )->execute([$id, $userId, $ip, substr($userAgent, 0, 255), $now, $now, $expires]);

        return ['token' => $token, 'expires_at' => $expires];
    }

    /** Находит сессию по «сырому» токену из cookie и продлевает last_seen_at. */
    public function findByToken(string $token): ?array
    {
        $id = hash('sha256', $token);
        $stmt = $this->db->pdo()->prepare('SELECT * FROM sessions WHERE id = ?');
        $stmt->execute([$id]);
        $row = $stmt->fetch();

        if ($row === false) {
            return null;
        }
        if (strtotime((string) $row['expires_at']) < time()) {
            $this->destroy($token);
            return null;
        }

        $this->db->pdo()
            ->prepare('UPDATE sessions SET last_seen_at = ? WHERE id = ?')
            ->execute([gmdate('Y-m-d H:i:s'), $id]);

        return $row;
    }

    public function destroy(string $token): void
    {
        $id = hash('sha256', $token);
        $this->db->pdo()->prepare('DELETE FROM sessions WHERE id = ?')->execute([$id]);
    }

    public function destroyAllForUser(int $userId): void
    {
        $this->db->pdo()->prepare('DELETE FROM sessions WHERE user_id = ?')->execute([$userId]);
    }

    public function purgeExpired(): int
    {
        $stmt = $this->db->pdo()->prepare('DELETE FROM sessions WHERE expires_at < ?');
        $stmt->execute([gmdate('Y-m-d H:i:s')]);
        return $stmt->rowCount();
    }
}
