#!/usr/bin/env php
<?php

declare(strict_types=1);

/**
 * Создаёт администратора панели (или повышает существующего клиента до админа).
 *
 * Использование:
 *   echo "пароль" | create-admin.php <email> [тариф]
 *
 * Пароль читается из STDIN, а не из аргументов: аргументы видны в `ps` любому
 * пользователю сервера и оседают в истории команд.
 */

$root = dirname(__DIR__, 3);
require $root . '/hosting/autoload.php';

use Hosting\Config;
use Hosting\Database;
use Hosting\Model\JobRepository;
use Hosting\Model\PlanRepository;
use Hosting\Model\UserRepository;
use Hosting\Support\Env;

$email = $argv[1] ?? '';
$planCode = $argv[2] ?? 'pro';

if ($email === '') {
    fwrite(STDERR, "Использование: echo <пароль> | create-admin.php <email> [тариф]\n");
    exit(1);
}

$password = trim((string) fgets(STDIN));
if (strlen($password) < 8) {
    fwrite(STDERR, "Пароль должен быть не короче 8 символов\n");
    exit(1);
}

Env::loadHosting($root);
Env::load('/etc/hosting/worker.env');

$config = Config::fromEnv();
$db = new Database($config);
$plans = new PlanRepository($db);
$users = new UserRepository($db, $plans);
$jobs = new JobRepository($db);

if (!$plans->exists($planCode)) {
    $planCode = $config->str('default_plan');
}

$existing = $users->findByEmail($email);

if ($existing !== null) {
    $users->setRole((int) $existing['id'], 'admin');
    $users->setPassword((int) $existing['id'], $password);
    $db->log((int) $existing['id'], 'admin.promoted', 'user', (int) $existing['id']);
    echo "Клиент {$email} повышен до администратора, пароль обновлён\n";
    exit(0);
}

try {
    $user = $users->create($email, $password, $planCode);
} catch (\Throwable $e) {
    fwrite(STDERR, 'Не удалось создать администратора: ' . $e->getMessage() . "\n");
    exit(1);
}

$users->setRole((int) $user['id'], 'admin');

// Тот же путь, что и у обычной регистрации: unix-пользователь и домашний
// каталог создаются асинхронно root-воркером.
$jobs->enqueue('create_user', (int) $user['id'], null);
$db->log((int) $user['id'], 'admin.created', 'user', (int) $user['id']);

echo "Администратор создан: {$email} (системное имя {$user['system_user']}, тариф {$planCode})\n";
