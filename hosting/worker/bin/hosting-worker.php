#!/usr/bin/env php
<?php

declare(strict_types=1);

/**
 * Root-воркер панели: единственный процесс, который выполняет системные операции.
 * Постоянно опрашивает таблицу jobs, забирает pending-задания и выполняет их через
 * JobHandler (whitelist типов — см. JobHandler::TYPES). Панель (веб-процесс, www-data)
 * никогда не делает этого сама — она только кладёт строку в jobs и уходит.
 *
 * Запускается через systemd (systemd/hosting-worker.service), под root.
 * Останавливается по SIGTERM/SIGINT — дорабатывает текущий job и выходит.
 */

$root = dirname(__DIR__, 3);
require $root . '/hosting/autoload.php';

use Hosting\Config;
use Hosting\Database;
use Hosting\Model\JobRepository;
use Hosting\Support\Env;
use Hosting\Worker\JobHandler;

Env::load($root . '/.env');
Env::load('/etc/hosting/worker.env'); // root-only файл с MYSQL_ADMIN_*, см. install.sh

$config = Config::fromEnv();
$db = new Database($config);
$jobs = new JobRepository($db);
$handler = new JobHandler($db, $config, $root . '/hosting/templates');

$running = true;
if (function_exists('pcntl_async_signals')) {
    pcntl_async_signals(true);
    pcntl_signal(SIGTERM, function () use (&$running): void { $running = false; });
    pcntl_signal(SIGINT, function () use (&$running): void { $running = false; });
}

fwrite(STDOUT, "[hosting-worker] запущен, опрашиваю очередь заданий\n");

$idleStreak = 0;

while ($running) {
    try {
        $claimed = $jobs->claimPending(5);
    } catch (\Throwable $e) {
        fwrite(STDERR, '[hosting-worker] ошибка чтения очереди: ' . $e->getMessage() . "\n");
        sleep(5);
        continue;
    }

    if ($claimed === []) {
        $idleStreak++;
        // Полли не чаще раза в 2 секунды, но не спим дольше 10 секунд, если завал в очереди.
        usleep(min(2_000_000, 200_000 * $idleStreak));
        continue;
    }

    $idleStreak = 0;

    foreach ($claimed as $job) {
        $jobId = (int) $job['id'];
        fwrite(STDOUT, sprintf("[hosting-worker] job #%d: %s\n", $jobId, $job['type']));

        try {
            $secret = $handler->handle($job);
            $jobs->markSuccess($jobId, $secret);
            fwrite(STDOUT, "[hosting-worker] job #{$jobId}: OK\n");
        } catch (\Throwable $e) {
            $jobs->markFailed($jobId, $e->getMessage());
            $db->recordSecurityEvent('job_failed', 'warning', '', [
                'job_id' => $jobId,
                'type'   => $job['type'],
                'error'  => $e->getMessage(),
            ], $job['user_id'] !== null ? (int) $job['user_id'] : null);
            fwrite(STDERR, "[hosting-worker] job #{$jobId}: ОШИБКА — " . $e->getMessage() . "\n");
        }
    }
}

fwrite(STDOUT, "[hosting-worker] остановлен\n");
