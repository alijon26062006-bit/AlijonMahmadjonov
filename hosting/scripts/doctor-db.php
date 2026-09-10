#!/usr/bin/env php
<?php

declare(strict_types=1);

/**
 * Проверки, которые нельзя сделать из bash: подключение к панельной БД теми же
 * настройками, что использует сама панель, полнота схемы и живость очереди заданий.
 *
 * Печатает по строке на проверку в формате «СТАТУС|текст», где СТАТУС —
 * OK / WARN / FAIL. Разбирает эти строки scripts/doctor.sh.
 * Отдельным скриптом, а не heredoc внутри bash, чтобы его ловил php -l.
 */

$root = dirname(__DIR__, 2);
require $root . '/hosting/autoload.php';

use Hosting\Config;
use Hosting\Database;
use Hosting\Support\Env;

Env::loadHosting($root);

function out(string $status, string $text): void
{
    fwrite(STDOUT, $status . '|' . $text . "\n");
}

try {
    $config = Config::fromEnv();
} catch (\Throwable $e) {
    out('FAIL', 'не читается конфигурация из .env: ' . $e->getMessage());
    exit(1);
}

try {
    $db = new Database($config);
    out('OK', sprintf(
        'подключение к базе панели (%s@%s/%s)',
        $config->str('db_username'),
        $config->str('db_host'),
        $config->str('db_database'),
    ));
} catch (\Throwable $e) {
    out('FAIL', 'нет подключения к базе панели: ' . $e->getMessage());
    out('FAIL', 'без базы не работают ни панель, ни воркер — проверьте DB_* в .env и systemctl status mariadb');
    exit(1);
}

$pdo = $db->pdo();

// ── схема ────────────────────────────────────────────────────────────────
// Сверяем не «база не пустая», а наличие каждой таблицы из migrations/:
// частично применённые миграции — самый неприятный случай, панель при этом
// открывается и падает только на конкретной странице.
$expected = [];
foreach (glob($root . '/hosting/migrations/*.sql') ?: [] as $file) {
    if (preg_match_all('~CREATE TABLE IF NOT EXISTS\s+([A-Za-z0-9_]+)~i', (string) file_get_contents($file), $m)) {
        foreach ($m[1] as $table) {
            $expected[$table] = true;
        }
    }
}

$existing = [];
foreach ($pdo->query('SHOW TABLES')->fetchAll(\PDO::FETCH_NUM) as $row) {
    $existing[$row[0]] = true;
}

$missing = array_keys(array_diff_key($expected, $existing));
if ($missing === []) {
    out('OK', 'схема базы полная (' . count($expected) . ' таблиц)');
} else {
    out('FAIL', 'в базе не хватает таблиц: ' . implode(', ', $missing)
        . ' — выполните: php hosting/panel/bin/migrate.php');
}

// ── тарифы ───────────────────────────────────────────────────────────────
if (isset($existing['plans'])) {
    $plans = (int) $pdo->query('SELECT COUNT(*) FROM plans')->fetchColumn();
    if ($plans > 0) {
        out('OK', "тарифы заведены ({$plans} шт.) — публичная главная покажет их клиентам");
    } else {
        out('FAIL', 'таблица plans пуста — на главной не будет ни одного тарифа, регистрация не пройдёт');
    }
}

// ── администратор ────────────────────────────────────────────────────────
if (isset($existing['users'])) {
    $admins = (int) $pdo->query("SELECT COUNT(*) FROM users WHERE role = 'admin'")->fetchColumn();
    if ($admins > 0) {
        out('OK', "администратор существует ({$admins})");
    } else {
        out('WARN', 'ни одного администратора — создайте: sudo bash hosting/setup.sh');
    }

    $clients = (int) $pdo->query("SELECT COUNT(*) FROM users WHERE role = 'client'")->fetchColumn();
    out('OK', "клиентов в панели: {$clients}");
}

// ── очередь заданий: главный признак живости воркера ─────────────────────
if (isset($existing['jobs'])) {
    $stuck = (int) $pdo->query(
        "SELECT COUNT(*) FROM jobs
          WHERE status = 'pending' AND created_at < (NOW() - INTERVAL 3 MINUTE)"
    )->fetchColumn();

    if ($stuck > 0) {
        out('FAIL', "в очереди {$stuck} заданий висят в pending дольше 3 минут — воркер их не забирает"
            . ' (journalctl -u hosting-worker -n 50)');
    } else {
        out('OK', 'зависших заданий в очереди нет');
    }

    $running = (int) $pdo->query(
        "SELECT COUNT(*) FROM jobs
          WHERE status = 'running' AND started_at < (NOW() - INTERVAL 10 MINUTE)"
    )->fetchColumn();
    if ($running > 0) {
        out('WARN', "{$running} заданий в статусе running дольше 10 минут — возможно, воркер убили посреди работы");
    }

    $failed = $pdo->query(
        "SELECT type, error_text, finished_at FROM jobs
          WHERE status = 'failed' ORDER BY id DESC LIMIT 3"
    )->fetchAll();
    foreach ($failed as $job) {
        out('WARN', sprintf(
            'провалившееся задание %s (%s): %s',
            $job['type'],
            (string) $job['finished_at'],
            mb_substr((string) $job['error_text'], 0, 160),
        ));
    }
}

// ── проверка живости воркера прямо сейчас ────────────────────────────────
// Кладём служебное задание ping и ждём, заберёт ли его кто-нибудь. Это
// единственный способ отличить «воркер запущен» от «воркер реально работает».
if (isset($existing['jobs']) && in_array('--probe', $argv, true)) {
    $pdo->prepare("INSERT INTO jobs (type, status, payload) VALUES ('ping', 'pending', '{}')")->execute();
    $id = (int) $pdo->lastInsertId();

    $picked = false;
    for ($i = 0; $i < 20; $i++) {
        usleep(500_000);
        $stmt = $pdo->prepare('SELECT status, error_text FROM jobs WHERE id = :id');
        $stmt->execute(['id' => $id]);
        $row = $stmt->fetch();
        if ($row !== false && $row['status'] !== 'pending') {
            $picked = true;
            if ($row['status'] === 'success') {
                out('OK', 'воркер живой: тестовое задание выполнено за ' . round(($i + 1) * 0.5, 1) . ' с');
            } else {
                out('FAIL', 'воркер забрал тестовое задание, но провалил его: ' . (string) $row['error_text']);
            }
            break;
        }
    }
    if (!$picked) {
        out('FAIL', 'воркер НЕ забрал тестовое задание за 10 секунд — провизионинг сайтов и баз работать не будет');
    }
    $pdo->prepare('DELETE FROM jobs WHERE id = :id')->execute(['id' => $id]);
}
