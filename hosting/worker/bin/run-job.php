#!/usr/bin/env php
<?php

declare(strict_types=1);

/**
 * Ставит одно задание в очередь и сразу же выполняет именно его (не ждёт демона).
 * Нужен для hostingctl (см. scripts/hostingctl) — админ получает результат сразу,
 * но код выполнения тот же самый JobHandler, что и у постоянного воркера.
 *
 * Использование (все ID — только числа, иначе отказ):
 *   run-job.php <type> --user=<id> [--site=<id>] [--payload='{"key":"value"}']
 *
 * Exit code 0 — успех, 1 — ошибка валидации, 2 — задание провалено.
 */

$root = dirname(__DIR__, 3);
require $root . '/hosting/autoload.php';

use Hosting\Config;
use Hosting\Database;
use Hosting\Model\JobRepository;
use Hosting\Support\Env;
use Hosting\Worker\JobHandler;

function fail(string $message, int $code = 1): never
{
    fwrite(STDERR, $message . "\n");
    exit($code);
}

$args = array_slice($argv, 1);
$type = array_shift($args) ?? '';

if (!in_array($type, JobHandler::TYPES, true)) {
    fail('Неизвестный тип задания: ' . $type . "\nДопустимые: " . implode(', ', JobHandler::TYPES));
}

$userId = null;
$siteId = null;
$payload = [];

foreach ($args as $arg) {
    if (preg_match('~^--user=([0-9]{1,10})$~', $arg, $m) === 1) {
        $userId = (int) $m[1];
    } elseif (preg_match('~^--site=([0-9]{1,10})$~', $arg, $m) === 1) {
        $siteId = (int) $m[1];
    } elseif (str_starts_with($arg, '--payload=')) {
        $decoded = json_decode(substr($arg, strlen('--payload=')), true);
        if (!is_array($decoded)) {
            fail('--payload должен быть валидным JSON-объектом');
        }
        $payload = $decoded;
    } else {
        fail('Неизвестный аргумент: ' . $arg . " (числовые ID проверяются строго, произвольные строки запрещены)");
    }
}

if ($userId === null) {
    fail('Нужен --user=<числовой id>');
}

Env::loadHosting($root);
Env::load('/etc/hosting/worker.env');

$config = Config::fromEnv();
$db = new Database($config);
$jobs = new JobRepository($db);
$handler = new JobHandler($db, $config, $root . '/hosting/templates');

$job = $jobs->enqueue($type, $userId, $siteId, $payload);
$claimed = $jobs->claimPending(1);

if ($claimed === [] || (int) $claimed[0]['id'] !== (int) $job['id']) {
    fail('Не удалось немедленно забрать задание #' . $job['id'] . ' в обработку (гонка с фоновым воркером?)', 2);
}

try {
    $secret = $handler->handle($claimed[0]);
    $jobs->markSuccess((int) $job['id'], $secret);
    echo "OK: задание #{$job['id']} ({$type}) выполнено\n";
    if ($secret !== null) {
        echo "Секрет (показан один раз): {$secret}\n";
    }
    exit(0);
} catch (\Throwable $e) {
    $jobs->markFailed((int) $job['id'], $e->getMessage());
    fail('ОШИБКА: задание #' . $job['id'] . ' провалено: ' . $e->getMessage(), 2);
}
