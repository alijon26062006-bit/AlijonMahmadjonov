<?php
declare(strict_types=1);

namespace Hosting\Model;

use Hosting\Database;

/**
 * Клиенты хостинга. Зарегистрироваться можно двумя способами: по e-mail с паролем
 * или входом через Telegram Mini App (см. TelegramAccountRepository).
 *
 * system_user — unix-логин клиента вида client1001 (id + 1000, чтобы совпадать
 * с примерами из архитектуры и не начинаться с однозначных чисел).
 */
final class UserRepository
{
    public function __construct(private Database $db, private PlanRepository $plans)
    {
    }

    public function create(string $email, string $password, string $planCode): array
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
            'plan'          => $planCode,
        ]);
    }

    /**
     * Регистрация из Mini App. Пароля нет: клиента опознаёт подпись Telegram
     * (см. Hosting\Service\TelegramAuth) — она уже проверена до вызова этого метода.
     *
     * @param array{id:int,username?:string,first_name?:string,last_name?:string} $tgUser
     */
    public function createFromTelegram(array $tgUser, string $planCode): array
    {
        $name = trim(($tgUser['first_name'] ?? '') . ' ' . ($tgUser['last_name'] ?? ''));
        if ($name === '') {
            $name = $tgUser['username'] ?? ('tg' . $tgUser['id']);
        }

        $user = $this->insert([
            'display_name' => $name,
            'plan'         => $planCode,
        ]);

        return $user;
    }

    private function insert(array $fields): array
    {
        $plan = $this->plans->findByCode((string) $fields['plan']);
        if ($plan === null) {
            throw new \InvalidArgumentException('Неизвестный тариф: ' . $fields['plan']);
        }

        $pdo = $this->db->pdo();
        $stmt = $pdo->prepare(
            'INSERT INTO users (email, password_hash, display_name, system_user, role,
                                plan_id, status, disk_quota_mb, inode_limit, max_sites, max_databases,
                                created_at, updated_at)
             VALUES (:email, :password_hash, :display_name, "", "client",
                     :plan_id, "active", :disk, :inodes, :sites, :dbs, :now, :now)'
        );
        $now = gmdate('Y-m-d H:i:s');
        $stmt->execute([
            'email'         => $fields['email'] ?? null,
            'password_hash' => $fields['password_hash'] ?? null,
            'display_name'  => $fields['display_name'] ?? '',
            'plan_id'       => $plan['id'],
            'disk'          => $plan['disk_quota_mb'],
            'inodes'        => $plan['inode_limit'],
            'sites'         => $plan['max_sites'],
            'dbs'           => $plan['max_databases'],
            'now'           => $now,
        ]);

        $id = (int) $pdo->lastInsertId();
        $systemUser = 'client' . (1000 + $id);
        $pdo->prepare('UPDATE users SET system_user = ? WHERE id = ?')->execute([$systemUser, $id]);

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

    public function findBySystemUser(string $systemUser): ?array
    {
        return $this->fetchOne('SELECT * FROM users WHERE system_user = ?', [$systemUser]);
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
        $hash = (string) ($user['password_hash'] ?? '');
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
            ->prepare('UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?')
            ->execute([password_hash($password, PASSWORD_DEFAULT), gmdate('Y-m-d H:i:s'), $id]);
    }

    public function setStatus(int $id, string $status): void
    {
        $allowed = ['active', 'grace', 'suspended', 'pending_delete'];
        if (!in_array($status, $allowed, true)) {
            throw new \InvalidArgumentException('Недопустимый статус: ' . $status);
        }
        $this->db->pdo()
            ->prepare('UPDATE users SET status = ?, updated_at = ? WHERE id = ?')
            ->execute([$status, gmdate('Y-m-d H:i:s'), $id]);
    }

    public function setRole(int $id, string $role): void
    {
        if (!in_array($role, ['client', 'admin'], true)) {
            throw new \InvalidArgumentException('Недопустимая роль: ' . $role);
        }
        $this->db->pdo()->prepare('UPDATE users SET role = ? WHERE id = ?')->execute([$role, $id]);
    }

    public function setPlan(int $id, string $planCode): void
    {
        $plan = $this->plans->findByCode($planCode);
        if ($plan === null) {
            throw new \InvalidArgumentException('Неизвестный тариф: ' . $planCode);
        }
        $this->db->pdo()->prepare(
            'UPDATE users SET plan_id = ?, disk_quota_mb = ?, inode_limit = ?, max_sites = ?, max_databases = ?, updated_at = ? WHERE id = ?'
        )->execute([
            $plan['id'], $plan['disk_quota_mb'], $plan['inode_limit'],
            $plan['max_sites'], $plan['max_databases'], gmdate('Y-m-d H:i:s'), $id,
        ]);
    }

    public function delete(int $id): void
    {
        $this->db->pdo()->prepare('DELETE FROM users WHERE id = ?')->execute([$id]);
    }

    public static function isActive(array $user): bool
    {
        return in_array($user['status'], ['active', 'grace'], true);
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
