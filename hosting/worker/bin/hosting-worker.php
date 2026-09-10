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

Env::loadHosting($root);
Env::load('/etc/hosting/worker.env'); // root-only файл с MYSQL_ADMIN_*, см. install.sh

$running = true;
if (function_exists('pcntl_async_signals')) {
    pcntl_async_signals(true);
    pcntl_signal(SIGTERM, function () use (&$running): void { $running = false; });
    pcntl_signal(SIGINT, function () use (&$running): void { $running = false; });
}

$config = Config::fromEnv();

// Подключение к панельной БД — с повторами, а не с падением.
//
// Если упасть здесь, systemd (Restart=..., RestartSec=5) будет поднимать процесс
// заново каждые 5 секунд, служба навсегда застрянет в состоянии
// "activating (auto-restart)", а настоящая причина утонет в потоке одинаковых
// рестартов. Вместо этого остаёмся живыми, печатаем причину и ждём: как только
// MariaDB поднимется (или починят пароль в .env), воркер сам начнёт разбирать
// очередь — без ручного systemctl restart.
$db = null;
$attempt = 0;
while ($running && $db === null) {
    try {
        $db = new Database($config);
    } catch (\Throwable $e) {
        $attempt++;
        $wait = min(60, 5 * $attempt);
        fwrite(STDERR, sprintf(
            "[hosting-worker] нет связи с базой панели (попытка %d): %s\n"
            . "[hosting-worker] проверьте DB_HOST/DB_USERNAME/DB_PASSWORD в %s и `systemctl status mariadb`; повтор через %d с\n",
            $attempt,
            $e->getMessage(),
            $root . '/.env',
            $wait,
        ));
        for ($i = 0; $i < $wait && $running; $i++) {
            sleep(1);
        }
    }
}

if ($db === null) { // получили SIGTERM, так и не подключившись
    fwrite(STDOUT, "[hosting-worker] остановлен до подключения к базе\n");
    exit(0);
}

$jobs = new JobRepository($db);
$handler = new JobHandler($db, $config, $root . '/hosting/templates');

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
