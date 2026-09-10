#!/usr/bin/env php
<?php

declare(strict_types=1);

/**
 * Возвращает user_id владельца сайта/базы по её id — нужен hostingctl, который
 * принимает от админа только один числовой ID объекта (см. спецификацию,
 * раздел ROOT HELPER SECURITY: "hostingctl create-site 55"), а не пару (user, site).
 *
 * Использование: resolve-owner.php site|database <id>
 * Печатает user_id или завершает с кодом 1, если объект не найден.
 */

$root = dirname(__DIR__, 3);
require $root . '/hosting/autoload.php';

use Hosting\Config;
use Hosting\Database;
use Hosting\Support\Env;

$type = $argv[1] ?? '';
$id = (int) ($argv[2] ?? 0);

if (!in_array($type, ['site', 'database'], true) || $id <= 0) {
    fwrite(STDERR, "Использование: resolve-owner.php site|database <id>\n");
    exit(1);
}

Env::load($root . '/.env');
Env::load('/etc/hosting/worker.env');
$db = new Database(Config::fromEnv());

$table = $type === 'site' ? 'sites' : 'client_databases';
$stmt = $db->pdo()->prepare("SELECT user_id FROM {$table} WHERE id = ?");
$stmt->execute([$id]);
$row = $stmt->fetch();

if ($row === false) {
    fwrite(STDERR, "{$type} #{$id} не найден\n");
    exit(1);
}

echo (int) $row['user_id'] . "\n";
