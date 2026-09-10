<?php
declare(strict_types=1);

namespace Hosting\Model;

use Hosting\Database;
use Hosting\Service\Plans;

/**
 * Клиенты хостинга. Зарегистрироваться можно двумя способами:
 * по e-mail с паролем или входом через Telegram Mini App.
 */
final class UserRepository
{
    public function __construct(private Database $db)
    {
    }

    public function create(string $email, string $password, string $plan, bool $isAdmin = false): array
    {
        $email = strtolower(trim($email));
        if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
            throw new \InvalidArgumentException('Неверный e-mail');
        }
        if (strlen($password) < 8) {
            throw new \InvalidArgumentException('Пароль короче 8 символов');
        }
        if ($this->findByEmail($email) !== null) {
            throw new \RuntimeException('Такой e-mail уже зарегистрирован');
        }

        return $this->insert([
            'email'         => $email,
            'password_hash' => password_hash($password, PASSWORD_DEFAULT),
            'display_name'  => explode('@', $email)[0],
            'plan'          => $plan,
            'is_admin'      => $isAdmin,
        ]);
    }

    /**
     * Регистрация из Mini App. Пароля нет: клиента опознаёт подпись Telegram.
     *
     * @param array{id:int,username?:string,first_name?:string,last_name?:string} $tgUser
     */
    public function createFromTelegram(array $tgUser, string $plan): array
    {
        $telegramId = (int) $tgUser['id'];
        if ($telegramId <= 0) {
            throw new \InvalidArgumentException('Некорректный Telegram id');
        }
        if ($this->findByTelegramId($telegramId) !== null) {
            throw new \RuntimeException('Этот Telegram уже привязан к аккаунту');
        }

        $name = trim(($tgUser['first_name'] ?? '') . ' ' . ($tgUser['last_name'] ?? ''));
        if ($name === '') {
            $name = $tgUser['username'] ?? ('tg' . $telegramId);
        }

        return $this->insert([
            'telegram_id'   => $telegramId,
            'telegram_name' => (string) ($tgUser['username'] ?? ''),
            'display_name'  => $name,
            'plan'          => $plan,
        ]);
    }

    /** Привязывает Telegram к уже существующему аккаунту с паролем. */
    public function linkTelegram(int $userId, array $tgUser): void
    {
        $telegramId = (int) $tgUser['id'];
        $existing = $this->findByTelegramId($telegramId);
        if ($existing !== null && (int) $existing['id'] !== $userId) {
            throw new \RuntimeException('Этот Telegram уже привязан к другому аккаунту');
        }

        $this->db->pdo()
            ->prepare('UPDATE users SET telegram_id = ?, telegram_name = ? WHERE id = ?')
            ->execute([$telegramId, (string) ($tgUser['username'] ?? ''), $userId]);
    }

    private function insert(array $fields): array
    {
        $plan = (string) $fields['plan'];
        $limits = Plans::get($plan);
        $pdo = $this->db->pdo();

        $stmt = $pdo->prepare(
            'INSERT INTO users (email, password_hash, telegram_id, telegram_name, display_name,
                                system_user, plan, disk_quota_mb, max_sites, max_databases,
                                is_admin, is_active, created_at)
             VALUES (:email, :password_hash, :telegram_id, :telegram_name, :display_name,
                     "", :plan, :disk, :sites, :dbs, :is_admin, 1, :created_at)'
        );
        $stmt->execute([
            'email'         => $fields['email'] ?? null,
            'password_hash' => $fields['password_hash'] ?? '',
            'telegram_id'   => $fields['telegram_id'] ?? null,
            'telegram_name' => $fields['telegram_name'] ?? '',
            'display_name'  => $fields['display_name'] ?? '',
            'plan'          => $plan,
            'disk'          => $limits['disk_quota_mb'],
            'sites'         => $limits['max_sites'],
            'dbs'           => $limits['max_databases'],
            'is_admin'      => !empty($fields['is_admin']) ? 1 : 0,
            'created_at'    => gmdate('c'),
        ]);

        $id = (int) $pdo->lastInsertId();
        // Системное имя вида u17: unix-пользователь, пул php-fpm и префикс баз данных.
        $pdo->prepare('UPDATE users SET system_user = ? WHERE id = ?')->execute(['u' . $id, $id]);

        return $this->findById($id) ?? throw new \RuntimeException('Не удалось создать клиента');
    }

    public function findById(int $id): ?array
    {
        return $this->fetchOne('SELECT * FROM users WHERE id = ?', [$id]);
    }

    public function findByEmail(string $email): ?array
    {
        return $this->fetchOne('SELECT * FROM users WHERE email = ?', [strtolower(trim($email))]);
    }

    public function findByTelegramId(int $telegramId): ?array
    {
        return $this->fetchOne('SELECT * FROM users WHERE telegram_id = ?', [$telegramId]);
    }

    private function fetchOne(string $sql, array $params): ?array
    {
        $stmt = $this->db->pdo()->prepare($sql);
        $stmt->execute($params);
        $row = $stmt->fetch();
        return $row === false ? null : $row;
    }

    /** @return list<array<string,mixed>> */
    public function all(): array
    {
        return $this->db->pdo()->query('SELECT * FROM users ORDER BY id')->fetchAll();
    }

    public function count(): int
    {
        return (int) $this->db->pdo()->query('SELECT COUNT(*) AS c FROM users')->fetch()['c'];
    }

    public function verifyPassword(array $user, string $password): bool
    {
        $hash = (string) $user['password_hash'];
        if ($hash === '') {
            return false;
        }
        return password_verify($password, $hash);
    }

    public function setPassword(int $id, string $password): void
    {
        if (strlen($password) < 8) {
            throw new \InvalidArgumentException('Пароль короче 8 символов');
        }
        $this->db->pdo()
            ->prepare('UPDATE users SET password_hash = ? WHERE id = ?')
            ->execute([password_hash($password, PASSWORD_DEFAULT), $id]);
    }

    public function setActive(int $id, bool $active): void
    {
        $this->db->pdo()
            ->prepare('UPDATE users SET is_active = ? WHERE id = ?')
            ->execute([$active ? 1 : 0, $id]);
    }

    public function setAdmin(int $id, bool $isAdmin): void
    {
        $this->db->pdo()
            ->prepare('UPDATE users SET is_admin = ? WHERE id = ?')
            ->execute([$isAdmin ? 1 : 0, $id]);
    }

    /** Смена тарифа: лимиты перечитываются из тарифа. */
    public function setPlan(int $id, string $plan): void
    {
        $limits = Plans::get($plan);
        $this->db->pdo()->prepare(
            'UPDATE users SET plan = ?, disk_quota_mb = ?, max_sites = ?, max_databases = ? WHERE id = ?'
        )->execute([$plan, $limits['disk_quota_mb'], $limits['max_sites'], $limits['max_databases'], $id]);
    }

    public function delete(int $id): void
    {
        $this->db->pdo()->prepare('DELETE FROM users WHERE id = ?')->execute([$id]);
    }

    public static function displayName(array $user): string
    {
        $name = trim((string) ($user['display_name'] ?? ''));
        if ($name !== '') {
            return $name;
        }
        return (string) ($user['email'] ?? $user['system_user'] ?? 'клиент');
    }
}
