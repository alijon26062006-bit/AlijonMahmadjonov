<?php
declare(strict_types=1);

namespace Hosting\Model;

use Hosting\Database;

/** Учёт попыток входа — основа для rate limit на /login (в дополнение к Fail2ban). */
final class LoginAttemptRepository
{
    public function __construct(private Database $db)
    {
    }

    public function record(string $identifier, string $ip, bool $success): void
    {
        $this->db->pdo()->prepare(
            'INSERT INTO login_attempts (identifier, ip, success, created_at) VALUES (?, ?, ?, ?)'
        )->execute([strtolower($identifier), $ip, $success ? 1 : 0, gmdate('Y-m-d H:i:s')]);
    }

    /** Сколько неудачных попыток за последние $windowSeconds секунд по идентификатору ИЛИ по IP. */
    public function recentFailures(string $identifier, string $ip, int $windowSeconds): int
    {
        $since = gmdate('Y-m-d H:i:s', time() - $windowSeconds);
        $stmt = $this->db->pdo()->prepare(
            'SELECT COUNT(*) AS c FROM login_attempts
             WHERE success = 0 AND created_at >= ? AND (identifier = ? OR ip = ?)'
        );
        $stmt->execute([$since, strtolower($identifier), $ip]);
        return (int) $stmt->fetch()['c'];
    }
}
