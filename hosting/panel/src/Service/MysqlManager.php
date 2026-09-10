<?php
declare(strict_types=1);

namespace Hosting\Service;

use Hosting\Config;
use PDO;

/**
 * Управление базами MySQL/MariaDB клиентов. Используется только root-воркером —
 * веб-процесс панели этот класс с реальными admin-кредами не инстанцирует.
 *
 * Модель прав (см. спецификацию, раздел MARIADB): один DB-пользователь на клиента
 * (client1001, MAX_USER_CONNECTIONS ограничен тарифом) с правом
 * GRANT ALL ON `client1001_%`.* — то есть доступ ко всем СВОИМ базам сразу,
 * без выдачи отдельного пользователя на каждую базу.
 *
 * Учётка заводится сразу для двух хостов — 'localhost' и '127.0.0.1'. Для MariaDB
 * это разные пользователи: первый пускает через unix-сокет, второй по TCP. Клиенты
 * пишут в конфиг своего приложения то одно, то другое (WordPress обычно localhost,
 * Laravel по умолчанию 127.0.0.1), и если завести только один вариант, половина
 * приложений получает загадочную ошибку 1130. Наружу это ничего не открывает:
 * MariaDB слушает только 127.0.0.1 (см. etc/mariadb/hosting.cnf), а порт 3306
 * закрыт firewall'ом.
 */
final class MysqlManager
{
    /** Хосты, для которых заводится учётка клиента (см. комментарий к классу). */
    private const USER_HOSTS = ['localhost', '127.0.0.1'];

    private ?PDO $pdo = null;

    public function __construct(private Config $config)
    {
    }

    /** Проверка имени, которое вводит клиент (без префикса системного пользователя). */
    public static function isValidName(string $name): bool
    {
        return preg_match('~^[a-z][a-z0-9_]{1,24}$~', $name) === 1;
    }

    public static function fullDatabaseName(array $user, string $name): string
    {
        return $user['system_user'] . '_' . $name;
    }

    public static function generatePassword(int $length = 24): string
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
            PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_TIMEOUT => 5,
        ]);

        return $this->pdo;
    }

    public function userExists(string $dbUser): bool
    {
        $this->assertIdentifier($dbUser);
        $placeholders = implode(',', array_fill(0, count(self::USER_HOSTS), '?'));
        $stmt = $this->connect()->prepare(
            "SELECT COUNT(*) FROM mysql.user WHERE User = ? AND Host IN ({$placeholders})"
        );
        $stmt->execute([$dbUser, ...self::USER_HOSTS]);
        return (int) $stmt->fetchColumn() === count(self::USER_HOSTS);
    }

    /**
     * Идемпотентно создаёт DB-пользователя клиента, если его ещё нет. Существующему
     * пользователю пароль НЕ переустанавливается (иначе на каждый create_database
     * сломались бы уже подключённые сайты клиента).
     *
     * @return string|null сгенерированный пароль, если пользователь был создан впервые; null, если уже существовал
     */
    public function ensureUser(string $dbUser, int $maxConnections): ?string
    {
        $this->assertIdentifier($dbUser);

        if ($this->userExists($dbUser)) {
            return null;
        }

        $pdo = $this->connect();
        $password = self::generatePassword();

        // Один и тот же пароль на оба хоста — для клиента это одна учётка,
        // разделение на localhost/127.0.0.1 чисто внутреннее для MariaDB.
        foreach (self::USER_HOSTS as $host) {
            $pdo->exec(sprintf(
                "CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s WITH MAX_USER_CONNECTIONS %d",
                $pdo->quote($dbUser),
                $pdo->quote($host),
                $pdo->quote($password),
                $maxConnections,
            ));

            // Сюда мы попадаем, только если хотя бы одного из двух хостов не было
            // (иначе выше сработал бы ранний return). Одна из учёток при этом
            // могла остаться со старым паролем: CREATE USER IF NOT EXISTS для
            // существующей учётки молча не делает ничего. Клиенту же мы отдаём
            // $password — значит, обе учётки обязаны его принимать, иначе сайт
            // клиента работал бы по TCP и отказывал через сокет.
            $pdo->exec(sprintf(
                'ALTER USER %s@%s IDENTIFIED BY %s',
                $pdo->quote($dbUser),
                $pdo->quote($host),
                $pdo->quote($password),
            ));

            // Лимит подключений на уже существовавшей учётке мог быть не выставлен.
            $pdo->exec(sprintf(
                'GRANT USAGE ON *.* TO %s@%s WITH MAX_USER_CONNECTIONS %d',
                $pdo->quote($dbUser),
                $pdo->quote($host),
                $maxConnections,
            ));
        }
        $pdo->exec('FLUSH PRIVILEGES');

        return $password;
    }

    /** Создаёт базу и выдаёт права уже существующему DB-пользователю клиента (см. ensureUser). */
    public function createDatabase(string $dbName, string $dbUser): void
    {
        $this->assertIdentifier($dbName);
        $this->assertIdentifier($dbUser);
        $this->assertOwnedByUser($dbName, $dbUser);

        $pdo = $this->connect();
        $pdo->exec(sprintf(
            'CREATE DATABASE IF NOT EXISTS `%s` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci',
            $dbName
        ));
        foreach (self::USER_HOSTS as $host) {
            $pdo->exec(sprintf(
                'GRANT ALL PRIVILEGES ON `%s`.* TO %s@%s',
                $dbName,
                $pdo->quote($dbUser),
                $pdo->quote($host),
            ));
        }
        $pdo->exec('FLUSH PRIVILEGES');
    }

    public function changePassword(string $dbUser, ?string $password = null): string
    {
        $this->assertIdentifier($dbUser);

        $pdo = $this->connect();
        $password = $password ?? self::generatePassword();
        foreach (self::USER_HOSTS as $host) {
            $pdo->exec(sprintf(
                'ALTER USER IF EXISTS %s@%s IDENTIFIED BY %s',
                $pdo->quote($dbUser),
                $pdo->quote($host),
                $pdo->quote($password),
            ));
        }
        $pdo->exec('FLUSH PRIVILEGES');

        return $password;
    }

    public function dropDatabase(string $dbName): void
    {
        $this->assertIdentifier($dbName);
        $this->connect()->exec(sprintf('DROP DATABASE IF EXISTS `%s`', $dbName));
    }

    /** Удалять только когда у клиента не осталось ни одной базы (см. JobHandler). */
    public function dropUser(string $dbUser): void
    {
        $this->assertIdentifier($dbUser);
        $pdo = $this->connect();
        foreach (self::USER_HOSTS as $host) {
            $pdo->exec(sprintf('DROP USER IF EXISTS %s@%s', $pdo->quote($dbUser), $pdo->quote($host)));
        }
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

    private function assertIdentifier(string $identifier): void
    {
        if (preg_match('~^[A-Za-z0-9_]{1,64}$~', $identifier) !== 1) {
            throw new \InvalidArgumentException('Недопустимое имя базы или пользователя');
        }
    }

    /** База обязана быть в неймспейсе клиента (client1001_*) — иначе GRANT попал бы не туда. */
    private function assertOwnedByUser(string $dbName, string $dbUser): void
    {
        if (!str_starts_with($dbName, $dbUser . '_')) {
            throw new \InvalidArgumentException("База {$dbName} не принадлежит неймспейсу {$dbUser}_*");
        }
    }
}
