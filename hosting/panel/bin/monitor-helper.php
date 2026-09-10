#!/usr/bin/env php
<?php

declare(strict_types=1);

/**
 * Мост между monitor.sh и панельной БД: список клиентов с их лимитами по тарифу
 * (для проверки злоупотреблений на уровне процессов/CPU/RAM), запись resource_usage,
 * и число заданий в очереди (backlog воркера).
 */

$root = dirname(__DIR__, 3);
require $root . '/hosting/autoload.php';

use Hosting\Config;
use Hosting\Database;
use Hosting\Model\JobRepository;
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

Env::load($root . '/.env');
Env::load('/etc/hosting/worker.env');
$db = new Database(Config::fromEnv());

$args = array_slice($argv, 1);
$command = array_shift($args) ?? '';

if ($command === 'client-limits') {
    $stmt = $db->pdo()->query(
        'SELECT u.system_user, u.disk_quota_mb, u.inode_limit, p.cpu_quota_percent, p.memory_max_mb, p.tasks_max
         FROM users u JOIN plans p ON p.id = u.plan_id
         WHERE u.status = "active"'
    );
    foreach ($stmt->fetchAll() as $row) {
        echo implode("\t", [
            $row['system_user'], $row['cpu_quota_percent'], $row['memory_max_mb'],
            $row['disk_quota_mb'], $row['inode_limit'], $row['tasks_max'],
        ]) . "\n";
    }
    exit(0);
}

if ($command === 'record-usage') {
    $systemUser = opt($args, 'user', '');
    $stmt = $db->pdo()->prepare('SELECT id FROM users WHERE system_user = ?');
    $stmt->execute([$systemUser]);
    $row = $stmt->fetch();
    if ($row === false) {
        fwrite(STDERR, "клиент {$systemUser} не найден\n");
        exit(1);
    }

    $db->pdo()->prepare(
        'INSERT INTO resource_usage (user_id, cpu_percent, memory_mb, disk_mb, inode_count, process_count, recorded_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)'
    )->execute([
        $row['id'],
        (float) opt($args, 'cpu', '0'),
        (int) opt($args, 'mem', '0'),
        (int) opt($args, 'disk', '0'),
        (int) opt($args, 'inodes', '0'),
        (int) opt($args, 'procs', '0'),
        gmdate('Y-m-d H:i:s'),
    ]);
    exit(0);
}

if ($command === 'pending-jobs') {
    echo (new JobRepository($db))->countPending() . "\n";
    exit(0);
}

if ($command === 'stale-backups') {
    // Клиенты старше N дней без успешного бэкапа (см. --days=, по умолчанию 2).
    $days = (int) (opt($args, 'days') ?? 2);
    $stmt = $db->pdo()->prepare(
        "SELECT u.system_user FROM users u
         WHERE u.status = 'active' AND NOT EXISTS (
             SELECT 1 FROM backups b WHERE b.user_id = u.id AND b.status = 'success'
               AND b.created_at >= ?
         )"
    );
    $stmt->execute([gmdate('Y-m-d H:i:s', time() - $days * 86400)]);
    foreach ($stmt->fetchAll() as $row) {
        echo $row['system_user'] . "\n";
    }
    exit(0);
}

fwrite(STDERR, "Неизвестная команда: {$command} (client-limits|record-usage|pending-jobs|stale-backups)\n");
exit(1);
