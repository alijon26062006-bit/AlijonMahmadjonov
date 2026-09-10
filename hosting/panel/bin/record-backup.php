#!/usr/bin/env php
<?php

declare(strict_types=1);

/**
 * Тонкий мостик между bash-скриптами бэкапа и таблицей backups — вызывается
 * из scripts/backup.sh после того, как архив/дамп реально создан на диске.
 *
 * Использование:
 *   record-backup.php create --user=<id> --type=files|database|full
 *     -> печатает id новой записи (используйте его дальше как --backup-id)
 *   record-backup.php result --backup-id=<id> --status=success|failed
 *     --local=<path> [--checksum=<sha256>] [--size=<bytes>] [--remote=<path>]
 */

$root = dirname(__DIR__, 3);
require $root . '/hosting/autoload.php';

use Hosting\Config;
use Hosting\Database;
use Hosting\Model\BackupRepository;
use Hosting\Support\Env;

function opt(array $args, string $name, ?string $default = null): ?string
{
    foreach ($args as $arg) {
        if (str_starts_with($arg, "--{$name}=")) {
            return substr($arg, strlen($name) + 3);
        }
    }
    return $default;
}

$args = array_slice($argv, 1);
$command = array_shift($args) ?? '';

Env::loadHosting($root);
Env::load('/etc/hosting/worker.env');
$db = new Database(Config::fromEnv());
$backups = new BackupRepository($db);

if ($command === 'create') {
    $userId = (int) (opt($args, 'user') ?? 0);
    $type = opt($args, 'type', 'full');
    if ($userId <= 0) {
        fwrite(STDERR, "нужен --user=<id>\n");
        exit(1);
    }
    $row = $backups->create($userId, $type);
    echo $row['id'] . "\n";
    exit(0);
}

if ($command === 'result') {
    $id = (int) (opt($args, 'backup-id') ?? 0);
    $status = opt($args, 'status', 'failed');
    $local = opt($args, 'local', '');
    $checksum = opt($args, 'checksum', '');
    $size = (int) (opt($args, 'size') ?? 0);
    $remote = opt($args, 'remote', '');

    if ($id <= 0) {
        fwrite(STDERR, "нужен --backup-id=<id>\n");
        exit(1);
    }

    $backups->markResult($id, $status, (string) $local, (string) $checksum, $size, (string) $remote);
    exit(0);
}

if ($command === 'get') {
    $id = (int) (opt($args, 'backup-id') ?? 0);
    $row = $id > 0 ? $backups->findById($id) : null;
    if ($row === null) {
        fwrite(STDERR, "Резервная копия #{$id} не найдена\n");
        exit(1);
    }
    echo json_encode($row, JSON_UNESCAPED_SLASHES) . "\n";
    exit(0);
}

fwrite(STDERR, "Неизвестная команда: {$command} (create|result|get)\n");
exit(1);
