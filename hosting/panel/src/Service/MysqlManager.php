<?php
declare(strict_types=1);

namespace Hosting\Service;

use Hosting\Config;
use PDO;

/**
 * Создание баз MySQL/MariaDB для клиентов.
 *
 * Имена баз и пользователей строятся как <системное имя клиента>_<имя>, поэтому
 * клиенты не могут пересечься. В DDL параметры подставлять нельзя, поэтому
 * идентификаторы жёстко валидируются, а пароль экранируется драйвером.
 */
final class MysqlManager
{
    private ?PDO $pdo = null;

    public function __construct(private Config $config)
    {
    }

    /** Проверка имени, которое вводит клиент (без префикса). */
    public static function isValidName(string $name): bool
    {
        return preg_match('~^[a-z][a-z0-9_]{1,24}$~', $name) === 1;
    }

    public static function fullName(array $user, string $name): string
    {
        return $user['system_user'] . '_' . $name;
    }

    public static function generatePassword(int $length = 20): string
    {
        $alphabet = 'abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789';
        $password = '';
        for ($i = 0; $i < $length; $i++) {
            $password .= $alphabet[random_int(0, strlen($alphabet) - 1)];
        }
        return $password;
    }

    public function isAvailable(): bool
    {
        try {
            $this->connect();
            return true;
        } catch (\Throwable) {
            return false;
        }
    }

    private function connect(): PDO
    {
        if ($this->pdo instanceof PDO) {
            return $this->pdo;
        }

        $dsn = sprintf(
            'mysql:host=%s;port=%d;charset=utf8mb4',
            $this->config->str('mysql_host'),
            $this->config->int('mysql_port'),
        );

        $this->pdo = new PDO($dsn, $this->config->str('mysql_admin'), $this->config->str('mysql_password'), [
            PDO::ATTR_ERRMODE  => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_TIMEOUT  => 5,
        ]);

        return $this->pdo;
    }

    /**
     * Создаёт базу и пользователя с полными правами только на неё.
     * Возвращает пароль — показать клиенту один раз, в панели он не хранится.
     */
    public function createDatabase(string $dbName, string $dbUser, ?string $password = null): string
    {
        $this->assertIdentifier($dbName);
        $this->assertIdentifier($dbUser);

        $pdo = $this->connect();
        $password = $password ?? self::generatePassword();
        $quotedPassword = $pdo->quote($password);
        $quotedUser = $pdo->quote($dbUser);

        $pdo->exec(sprintf(
            'CREATE DATABASE IF NOT EXISTS `%s` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci',
            $dbName
        ));
        $pdo->exec(sprintf("CREATE USER IF NOT EXISTS %s@'%%' IDENTIFIED BY %s", $quotedUser, $quotedPassword));
        $pdo->exec(sprintf("GRANT ALL PRIVILEGES ON `%s`.* TO %s@'%%'", $dbName, $quotedUser));
        $pdo->exec('FLUSH PRIVILEGES');

        return $password;
    }

    public function changePassword(string $dbUser, ?string $password = null): string
    {
        $this->assertIdentifier($dbUser);

        $pdo = $this->connect();
        $password = $password ?? self::generatePassword();
        $pdo->exec(sprintf(
            "ALTER USER %s@'%%' IDENTIFIED BY %s",
            $pdo->quote($dbUser),
            $pdo->quote($password)
        ));
        $pdo->exec('FLUSH PRIVILEGES');

        return $password;
    }

    public function dropDatabase(string $dbName, string $dbUser): void
    {
        $this->assertIdentifier($dbName);
        $this->assertIdentifier($dbUser);

        $pdo = $this->connect();
        $pdo->exec(sprintf('DROP DATABASE IF EXISTS `%s`', $dbName));
        $pdo->exec(sprintf("DROP USER IF EXISTS %s@'%%'", $pdo->quote($dbUser)));
        $pdo->exec('FLUSH PRIVILEGES');
    }

    /** Размер базы в байтах — для показа в панели. */
    public function sizeBytes(string $dbName): int
    {
        $this->assertIdentifier($dbName);

        $stmt = $this->connect()->prepare(
            'SELECT COALESCE(SUM(data_length + index_length), 0) AS bytes
             FROM information_schema.tables WHERE table_schema = ?'
        );
        $stmt->execute([$dbName]);

        return (int) $stmt->fetchColumn();
    }

    /** Полное имя базы или пользователя, уже с префиксом клиента. */
    private function assertIdentifier(string $identifier): void
    {
        if (preg_match('~^[A-Za-z0-9_]{1,64}$~', $identifier) !== 1) {
            throw new \InvalidArgumentException('Недопустимое имя базы или пользователя');
        }
    }
}
