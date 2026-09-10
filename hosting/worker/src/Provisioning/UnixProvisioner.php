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

    /**
     * Общая группа веб-слоя: в неё входят hosting-panel (файловый менеджер панели)
     * и www-data (nginx). Она же — группа каталогов клиента.
     *
     * Одной группы hosting-panel мало: nginx проверяет существование файла сам
     * (try_files) и отдаёт статику, поэтому без доступа к каталогу он отвечает
     * 404 на всё, включая index.php, — сайт выглядит несозданным. Отдельная
     * группа лучше, чем добавлять www-data в группу панели: у неё понятное имя
     * и понятный смысл — «кому веб-слой разрешает читать файлы клиентов».
     */
    public const PANEL_GROUP = 'hosting-web';

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
            // Владелец — клиент, группа — hosting-panel: под ней работает веб-процесс
            // панели, и без доступа к группе файловый менеджер не может ни прочитать,
            // ни создать ни одного файла клиента. Права 2770: setgid, чтобы всё
            // созданное внутри наследовало группу, и «остальные» не видят ничего —
            // клиенты по-прежнему изолированы друг от друга.
            Shell::run(sprintf(
                'chown -R %s:%s %s',
                escapeshellarg($systemUser),
                escapeshellarg(self::PANEL_GROUP),
                escapeshellarg($path)
            ), 15);
            Shell::run(sprintf('chmod 2770 %s', escapeshellarg($path)), 15);
        }

        // ВАЖНО: сам $home (корень chroot для SFTP, см. etc/ssh/sshd-hosting.conf) обязан
        // принадлежать root и быть недоступен на запись группе/остальным — таково требование
        // OpenSSH к ChrootDirectory. Владеть им клиенту нельзя, поэтому chown клиенту делаем
        // только на подкаталоги ВНУТРИ (sites/, logs/, tmp/, backups/ — уже сделано выше),
        // а сам $home остаётся root:root 0755.
        chown($home, 'root');
        chgrp($home, 'root');
        chmod($home, 0o755);
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
