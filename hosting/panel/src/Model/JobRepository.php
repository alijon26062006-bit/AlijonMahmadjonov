<?php
declare(strict_types=1);

namespace Hosting\Model;

use Hosting\Database;
use PDO;

/**
 * Очередь заданий для root worker. Панель кладёт сюда задание и возвращается — она НИКОГДА
 * не выполняет системные команды сама. Разрешённые типы — Hosting\Worker\JobHandler::TYPES.
 */
final class JobRepository
{
    public function __construct(private Database $db)
    {
    }

    public function enqueue(string $type, ?int $userId, ?int $siteId, array $payload = []): array
    {
        $stmt = $this->db->pdo()->prepare(
            'INSERT INTO jobs (type, user_id, site_id, status, payload, created_at)
             VALUES (?, ?, ?, \'pending\', ?, ?)'
        );
        $stmt->execute([
            $type,
            $userId,
            $siteId,
            $payload === [] ? null : json_encode($payload, JSON_UNESCAPED_UNICODE),
            gmdate('Y-m-d H:i:s'),
        ]);

        return $this->findById((int) $this->db->pdo()->lastInsertId())
            ?? throw new \RuntimeException('Не удалось поставить задание в очередь');
    }

    public function findById(int $id): ?array
    {
        $stmt = $this->db->pdo()->prepare('SELECT * FROM jobs WHERE id = ?');
        $stmt->execute([$id]);
        $row = $stmt->fetch();
        return $row === false ? null : $row;
    }

    /**
     * Забирает до $limit ожидающих заданий и сразу переводит их в running,
     * чтобы два воркера не схватили одно и то же задание (SKIP LOCKED на MariaDB ≥10.6,
     * на SQLite в тестах транзакция и так однопоточная).
     *
     * @return list<array<string,mixed>>
     */
    public function claimPending(int $limit = 5): array
    {
        $pdo = $this->db->pdo();
        $pdo->beginTransaction();

        try {
            $lockClause = $this->db->isMysql() ? ' FOR UPDATE SKIP LOCKED' : '';
            $stmt = $pdo->prepare(
                "SELECT id FROM jobs WHERE status = 'pending' ORDER BY id LIMIT ?" . $lockClause
            );
            $stmt->bindValue(1, $limit, PDO::PARAM_INT);
            $stmt->execute();
            $ids = $stmt->fetchAll(PDO::FETCH_COLUMN);

            $claimed = [];
            foreach ($ids as $id) {
                $pdo->prepare(
                    "UPDATE jobs SET status = 'running', started_at = ?, attempts = attempts + 1 WHERE id = ?"
                )->execute([gmdate('Y-m-d H:i:s'), $id]);
                $claimed[] = $this->findById((int) $id);
            }

            $pdo->commit();
            return array_values(array_filter($claimed));
        } catch (\Throwable $e) {
            $pdo->rollBack();
            throw $e;
        }
    }

    public function markSuccess(int $id, ?string $resultSecret = null): void
    {
        $this->db->pdo()->prepare(
            "UPDATE jobs SET status = 'success', finished_at = ?, error_text = NULL, result_secret = ? WHERE id = ?"
        )->execute([gmdate('Y-m-d H:i:s'), $resultSecret, $id]);
    }

    /**
     * Читает и СРАЗУ стирает одноразовый секрет (например, пароль только что созданной БД).
     * Второй вызов для того же задания уже вернёт null — секрет живёт в базе считаные секунды.
     */
    public function consumeResultSecret(int $id): ?string
    {
        $pdo = $this->db->pdo();
        $stmt = $pdo->prepare('SELECT result_secret FROM jobs WHERE id = ?');
        $stmt->execute([$id]);
        $secret = $stmt->fetchColumn();

        if ($secret !== false && $secret !== null) {
            $pdo->prepare('UPDATE jobs SET result_secret = NULL WHERE id = ?')->execute([$id]);
            return (string) $secret;
        }

        return null;
    }

    public function markFailed(int $id, string $error): void
    {
        $this->db->pdo()->prepare(
            "UPDATE jobs SET status = 'failed', finished_at = ?, error_text = ? WHERE id = ?"
        )->execute([gmdate('Y-m-d H:i:s'), substr($error, 0, 4000), $id]);
    }

    /** @return list<array<string,mixed>> */
    public function recentForUser(int $userId, int $limit = 20): array
    {
        $stmt = $this->db->pdo()->prepare('SELECT * FROM jobs WHERE user_id = ? ORDER BY id DESC LIMIT ?');
        $stmt->bindValue(1, $userId, PDO::PARAM_INT);
        $stmt->bindValue(2, $limit, PDO::PARAM_INT);
        $stmt->execute();
        return $stmt->fetchAll();
    }

    public function countPending(): int
    {
        return (int) $this->db->pdo()->query("SELECT COUNT(*) AS c FROM jobs WHERE status IN ('pending','running')")->fetch()['c'];
    }
}
