<?php

declare(strict_types=1);

use Hosting\Config;
use Hosting\Worker\JobHandler;

// ── Живучесть воркера ───────────────────────────────────────────────────────
//
// Реальный случай с боевого сервера: воркер не мог подключиться к MariaDB,
// падал, systemd поднимал его каждые 5 секунд, и служба навсегда застревала
// в состоянии "activating". Снаружи это выглядело как «висит», а настоящая
// причина тонула в потоке одинаковых рестартов. Ни одно задание при этом
// не выполнялось: ни создание сайта, ни базы, ни SSL.
//
// Поэтому проверяем не «код выглядит правильно», а поведение процесса.

function test_worker_stays_alive_when_database_is_down(): void
{
    $root = dirname(__DIR__, 2);
    $script = $root . '/hosting/worker/bin/hosting-worker.php';

    // Порт 1 гарантированно не слушает MariaDB — это и есть «база недоступна».
    // Env::load не перетирает уже выставленные переменные окружения, поэтому
    // эти значения побеждают всё, что лежит в .env сервера.
    $env = [
        'PATH'        => getenv('PATH') ?: '/usr/bin:/bin',
        'DB_DRIVER'   => 'mysql',
        'DB_HOST'     => '127.0.0.1',
        'DB_PORT'     => '1',
        'DB_DATABASE' => 'hosting_panel_absent',
        'DB_USERNAME' => 'nobody',
        'DB_PASSWORD' => 'nothing',
    ];

    $descriptors = [1 => ['pipe', 'w'], 2 => ['pipe', 'w']];
    $process = proc_open([PHP_BINARY, $script], $descriptors, $pipes, $root, $env);
    assert_true(is_resource($process), 'Воркер не запустился вовсе');

    stream_set_blocking($pipes[2], false);

    $stderr = '';
    $alive = false;
    // Первая попытка подключения делается сразу, повтор — через 5 секунд.
    // Значит, живым процесс должен быть и через 3 секунды после старта.
    for ($i = 0; $i < 30; $i++) {
        usleep(100_000);
        $stderr .= (string) stream_get_contents($pipes[2]);
        $status = proc_get_status($process);
        $alive = $status['running'];
        if (!$alive) {
            break;
        }
    }

    proc_terminate($process, SIGTERM);
    $stderr .= (string) stream_get_contents($pipes[2]);
    fclose($pipes[1]);
    fclose($pipes[2]);
    proc_close($process);

    assert_true(
        $alive,
        'Воркер умер из-за недоступной базы — systemd загонит службу в вечный цикл рестартов'
    );
    assert_true(
        str_contains($stderr, 'нет связи с базой панели'),
        'Воркер молчит о том, почему не может работать; в журнале должна быть причина. Получено: ' . $stderr
    );
    assert_true(
        str_contains($stderr, 'DB_HOST'),
        'Сообщение об ошибке должно подсказывать, где именно чинить'
    );
}

// ── systemd-юнит ────────────────────────────────────────────────────────────

function test_worker_unit_recovers_after_repeated_failures(): void
{
    $tpl = (string) file_get_contents(dirname(__DIR__) . '/templates/systemd-worker.service.tpl');

    assert_true(str_contains($tpl, 'Restart='), 'Юнит без Restart= не поднимется после падения');
    // Без этого пять быстрых падений подряд переводят службу в failed навсегда,
    // и её приходится поднимать руками — на боевом сервере это простой хостинга.
    assert_true(
        str_contains($tpl, 'StartLimitIntervalSec=0'),
        'Юнит должен возвращаться сам, а не залипать в failed после серии падений'
    );
    assert_true(
        str_contains($tpl, 'StandardError=journal'),
        'Ошибки воркера должны попадать в journalctl -u hosting-worker'
    );
}

// ── ping: проверка живости ──────────────────────────────────────────────────

function test_worker_ping_job_is_whitelisted_and_harmless(): void
{
    assert_true(
        in_array('ping', JobHandler::TYPES, true),
        'Без типа ping doctor.sh не может отличить «служба запущена» от «воркер разбирает очередь»'
    );

    $db = hosting_test_db();
    $handler = new JobHandler($db, Config::fromEnv(), dirname(__DIR__) . '/templates');

    $result = $handler->handle(['id' => 1, 'type' => 'ping', 'user_id' => null, 'site_id' => null, 'payload' => null]);
    assert_true($result === null, 'ping не должен ничего возвращать и ничего менять');
}

function test_worker_rejects_job_type_outside_whitelist(): void
{
    $db = hosting_test_db();
    $handler = new JobHandler($db, Config::fromEnv(), dirname(__DIR__) . '/templates');

    assert_throws(static function () use ($handler): void {
        $handler->handle(['id' => 1, 'type' => 'rm_rf', 'user_id' => null, 'site_id' => null, 'payload' => null]);
    }, 'Задание не из белого списка должно отклоняться, а не выполняться');
}
