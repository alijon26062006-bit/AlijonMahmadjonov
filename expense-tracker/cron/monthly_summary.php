<?php
/**
 * Рассылка ежемесячных итогов по email.
 *
 * Настройте на хостинге cron-задачу, вызывающую этот скрипт раз в день, например:
 *   0 5 * * * php /path/to/expense-tracker/cron/monthly_summary.php
 * Скрипт сам определяет, что сегодня 1-е число и рассылка за прошлый месяц ещё не
 * отправлена (settings.last_summary_sent), поэтому лишние запуски безопасны.
 */

require_once __DIR__ . '/../config/db.php';
require_once __DIR__ . '/../includes/functions.php';

if (php_sapi_name() !== 'cli') {
    http_response_code(403);
    exit('Этот скрипт запускается только из cron / командной строки.');
}

if ((int) date('j') !== 1) {
    exit("Сегодня не 1-е число, рассылка не требуется.\n");
}

$prevMonthTs = strtotime('first day of last month');
$year = (int) date('Y', $prevMonthTs);
$month = (int) date('n', $prevMonthTs);
$periodKey = sprintf('%04d-%02d', $year, $month);

$db = get_db();
$stmt = $db->query('SELECT last_summary_sent FROM settings WHERE id = 1');
$alreadySent = $stmt->fetchColumn();

if ($alreadySent === $periodKey) {
    exit("Рассылка за {$periodKey} уже была отправлена.\n");
}

$stmt = $db->prepare('SELECT * FROM users WHERE role = ? ORDER BY name');
$stmt->execute(['worker']);
$workers = $stmt->fetchAll();

$monthLabel = month_name_ru($month) . ' ' . $year;
$sentCount = 0;

foreach ($workers as $worker) {
    if (empty($worker['email'])) {
        continue;
    }
    $summary = get_month_summary($worker['id'], $year, $month);
    $status = $summary['is_overspent'] ? 'Перерасход (долг)' : 'Остаток';

    $body = "Здравствуйте, {$worker['name']}!\n\n"
        . "Ваш итог за {$monthLabel}:\n"
        . "Зарплата: " . format_money($summary['salary_usd'], 'USD') . "\n"
        . "Потрачено: " . format_money($summary['total_spent_usd'], 'USD')
        . ' (' . format_money($summary['total_spent_kzt'], 'KZT') . ")\n"
        . "{$status}: " . format_money(abs($summary['remaining_usd']), 'USD')
        . ' (' . format_money(abs($summary['remaining_kzt']), 'KZT') . ")\n";

    if (mail($worker['email'], "Итог за {$monthLabel}", $body)) {
        $sentCount++;
    }
}

$stmt = $db->prepare('SELECT * FROM users WHERE role = ?');
$stmt->execute(['boss']);
$bosses = $stmt->fetchAll();

if ($bosses) {
    $bossBody = "Сводка по работникам за {$monthLabel}:\n\n";
    foreach ($workers as $worker) {
        $summary = get_month_summary($worker['id'], $year, $month);
        $status = $summary['is_overspent'] ? 'долг' : 'остаток';
        $bossBody .= "{$worker['name']}: зарплата "
            . format_money($summary['salary_usd'], 'USD') . ', потрачено '
            . format_money($summary['total_spent_usd'], 'USD') . ", {$status} "
            . format_money(abs($summary['remaining_usd']), 'USD') . "\n";
    }
    foreach ($bosses as $boss) {
        if (!empty($boss['email'])) {
            mail($boss['email'], "Сводка за {$monthLabel}", $bossBody);
        }
    }
}

$stmt = $db->prepare('UPDATE settings SET last_summary_sent = ? WHERE id = 1');
$stmt->execute([$periodKey]);

echo "Готово. Писем работникам отправлено: {$sentCount}.\n";
