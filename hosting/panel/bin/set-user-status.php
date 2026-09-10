#!/usr/bin/env php
<?php

declare(strict_types=1);

/**
 * Приостанавливает/возобновляет клиента целиком: меняет users.status и ставит
 * suspend_site/unsuspend_site в очередь для каждого его сайта. То же самое, что
 * делает AdminController::suspendUser()/activateUser() из веб-панели — используется
 * hostingctl для той же операции из командной строки root'а.
 *
 * Использование: set-user-status.php <user_id> suspended|active
 */

$root = dirname(__DIR__, 3);
require $root . '/hosting/autoload.php';

use Hosting\Config;
use Hosting\Database;
use Hosting\Model\JobRepository;
use Hosting\Model\SiteRepository;
use Hosting\Model\UserRepository;
use Hosting\Model\PlanRepository;
use Hosting\Support\Env;

$userId = (int) ($argv[1] ?? 0);
$status = $argv[2] ?? '';

if ($userId <= 0 || !in_array($status, ['suspended', 'active'], true)) {
    fwrite(STDERR, "Использование: set-user-status.php <user_id> suspended|active\n");
    exit(1);
}

Env::loadHosting($root);
Env::load('/etc/hosting/worker.env');
$db = new Database(Config::fromEnv());

$users = new UserRepository($db, new PlanRepository($db));
$sites = new SiteRepository($db);
$jobs = new JobRepository($db);

$user = $users->findById($userId);
if ($user === null) {
    fwrite(STDERR, "Клиент #{$userId} не найден\n");
    exit(1);
}

$users->setStatus($userId, $status);

foreach ($sites->forUser($userId) as $site) {
    if ($status === 'suspended' && $site['status'] === 'active') {
        $jobs->enqueue('suspend_site', $userId, (int) $site['id'], ['site_id' => $site['id']]);
    } elseif ($status === 'active' && $site['status'] === 'suspended') {
        $jobs->enqueue('unsuspend_site', $userId, (int) $site['id'], ['site_id' => $site['id']]);
    }
}

$db->log(null, 'hostingctl.user_status', 'user', $userId, 'success', ['status' => $status], '');
echo "OK: клиент #{$userId} ({$user['system_user']}) -> {$status}\n";
