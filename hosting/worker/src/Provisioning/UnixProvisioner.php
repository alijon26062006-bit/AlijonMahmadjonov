<?php
declare(strict_types=1);

namespace Hosting\Worker\Provisioning;

use Hosting\Support\Shell;

/**
 * Создание/удаление unix-пользователей клиентов. Работает только под root (worker).
 * Логина по паролю у клиента нет: shell = /usr/sbin/nologin, доступ — только SFTP
 * через internal-sftp (см. etc/sshd-hosting.conf), группа hosting-sftp.
 */
final class UnixProvisioner
{
    public function __construct(private string $usersRoot)
    {
    }

    public function homeDir(string $systemUser): string
    {
        return $this->usersRoot . '/' . $systemUser;
    }

    public function exists(string $systemUser): bool
    {
        $result = Shell::run('id -u ' . escapeshellarg($systemUser), 5);
        return $result['code'] === 0;
    }

    public function createUser(string $systemUser): void
    {
        if (!preg_match('~^client[0-9]{1,10}$~', $systemUser)) {
            throw new \InvalidArgumentException('Недопустимое системное имя: ' . $systemUser);
        }

        if ($this->exists($systemUser)) {
            return;
        }

        $home = $this->homeDir($systemUser);
        $cmd = sprintf(
            'useradd --home-dir %s --create-home --shell /usr/sbin/nologin --groups hosting-sftp %s',
            escapeshellarg($home),
            escapeshellarg($systemUser)
        );
        $result = Shell::run($cmd, 15);
        if ($result['code'] !== 0) {
            throw new \RuntimeException('useradd не удался: ' . $result['err']);
        }

        foreach (['sites', 'logs', 'tmp', 'backups'] as $dir) {
            $path = $home . '/' . $dir;
            if (!is_dir($path)) {
                mkdir($path, 0o750, true);
            }
        }

        Shell::run(sprintf('chown -R %1$s:%1$s %2$s', escapeshellarg($systemUser), escapeshellarg($home)), 15);
        chmod($home, 0o710);
    }

    /** Удаляет пользователя вместе с домашним каталогом. Вызывающий отвечает за бэкап до удаления. */
    public function deleteUser(string $systemUser): void
    {
        if (!preg_match('~^client[0-9]{1,10}$~', $systemUser)) {
            throw new \InvalidArgumentException('Недопустимое системное имя: ' . $systemUser);
        }
        if (!$this->exists($systemUser)) {
            return;
        }
        $result = Shell::run('userdel --remove ' . escapeshellarg($systemUser), 30);
        if ($result['code'] !== 0) {
            throw new \RuntimeException('userdel не удался: ' . $result['err']);
        }
    }
}
