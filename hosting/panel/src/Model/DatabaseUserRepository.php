<?php
declare(strict_types=1);

namespace Hosting\Model;

use Hosting\Database;
use Hosting\Service\MysqlManager;

/**
 * У каждого клиента ровно один DB-пользователь (client1001), с правами
 * только на свои базы (GRANT ALL ON `client1001_%`.*). Эта таблица — учёт,
 * реальный CREATE USER выполняет root worker.
 */
final class DatabaseUserRepository
{
    public function __construct(private Database $db)
    {
    }

    public function findForUser(int $userId): ?array
    {
        $stmt = $this->db->pdo()->prepare('SELECT * FROM database_users WHERE user_id = ?');
        $stmt->execute([$userId]);
        $row = $stmt->fetch();
        return $row === false ? null : $row;
    }

    /** Возвращает существующую запись или создаёт новую с системным именем клиента. */
    public function getOrCreateForUser(array $user, int $maxConnections): array
    {
        $existing = $this->findForUser((int) $user['id']);
        if ($existing !== null) {
            return $existing;
        }

        $dbUser = (string) $user['system_user'];
        $this->db->pdo()->prepare(
            'INSERT INTO database_users (user_id, db_user, max_connections, created_at) VALUES (?, ?, ?, ?)'
        )->execute([$user['id'], $dbUser, $maxConnections, gmdate('Y-m-d H:i:s')]);

        return $this->findForUser((int) $user['id'])
            ?? throw new \RuntimeException('Не удалось создать учётку базы данных');
    }

    /**
     * Сохраняет пароль в зашифрованном виде.
     *
     * Клиенту пароль нужно видеть в панели, поэтому хеш не годится — нужно
     * обратимое шифрование. Ключ лежит в .env (см. Support\Secret), а не в базе:
     * дамп панельной базы сам по себе паролей не выдаёт.
     */
    public function storePassword(int $userId, string $password, string $appKey): void
    {
        if ($appKey === '') {
            // Без ключа не храним ничего: лучше не показать пароль, чем положить
            // его в базу открытым текстом.
            return;
        }

        $this->db->pdo()
            ->prepare('UPDATE database_users SET password_enc = ? WHERE user_id = ?')
            ->execute([\Hosting\Support\Secret::encrypt($password, $appKey), $userId]);
    }

    /** @return string|null null, если пароль не сохранён или ключ не подходит */
    public function revealPassword(int $userId, string $appKey): ?string
    {
        if ($appKey === '') {
            return null;
        }
        $row = $this->findForUser($userId);
        $stored = $row['password_enc'] ?? null;

        return is_string($stored) && $stored !== ''
            ? \Hosting\Support\Secret::decrypt($stored, $appKey)
            : null;
    }
}
