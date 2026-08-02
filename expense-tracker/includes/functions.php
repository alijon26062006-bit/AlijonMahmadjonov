<?php
require_once __DIR__ . '/../config/db.php';

function get_exchange_rate(): float
{
    $stmt = get_db()->query('SELECT exchange_rate_kzt_per_usd FROM settings WHERE id = 1');
    $row = $stmt->fetch();
    return $row ? (float) $row['exchange_rate_kzt_per_usd'] : 480.0;
}

function set_exchange_rate(float $rate): void
{
    $stmt = get_db()->prepare('UPDATE settings SET exchange_rate_kzt_per_usd = ? WHERE id = 1');
    $stmt->execute([$rate]);
}

function to_usd(float $amount, string $currency, float $rate): float
{
    return $currency === 'KZT' ? $amount / $rate : $amount;
}

/**
 * Сводка по расходам пользователя за месяц: зарплата, потрачено, остаток/долг.
 * Остаток и долг возвращаются и в USD, и в KZT (по текущему курсу) для отображения.
 */
function get_month_summary(int $userId, int $year, int $month): array
{
    $db = get_db();
    $rate = get_exchange_rate();

    $stmt = $db->prepare('SELECT monthly_salary_usd FROM users WHERE id = ?');
    $stmt->execute([$userId]);
    $salaryUsd = (float) ($stmt->fetchColumn() ?: 0);

    $start = sprintf('%04d-%02d-01', $year, $month);
    $end = date('Y-m-t', strtotime($start));

    $stmt = $db->prepare(
        'SELECT amount, currency FROM expenses WHERE user_id = ? AND expense_date BETWEEN ? AND ?'
    );
    $stmt->execute([$userId, $start, $end]);

    $totalSpentUsd = 0.0;
    foreach ($stmt->fetchAll() as $row) {
        $totalSpentUsd += to_usd((float) $row['amount'], $row['currency'], $rate);
    }

    $remainingUsd = $salaryUsd - $totalSpentUsd;

    return [
        'salary_usd' => $salaryUsd,
        'total_spent_usd' => $totalSpentUsd,
        'total_spent_kzt' => $totalSpentUsd * $rate,
        'remaining_usd' => $remainingUsd,
        'remaining_kzt' => $remainingUsd * $rate,
        'is_overspent' => $remainingUsd < 0,
        'rate' => $rate,
    ];
}

function list_month_expenses(int $userId, int $year, int $month): array
{
    $start = sprintf('%04d-%02d-01', $year, $month);
    $end = date('Y-m-t', strtotime($start));

    $stmt = get_db()->prepare(
        'SELECT * FROM expenses WHERE user_id = ? AND expense_date BETWEEN ? AND ? ORDER BY expense_date DESC, id DESC'
    );
    $stmt->execute([$userId, $start, $end]);
    return $stmt->fetchAll();
}

function format_money(float $amount, string $currency): string
{
    $symbol = $currency === 'USD' ? '$' : '₸';
    return number_format($amount, 2, '.', ' ') . ' ' . $symbol;
}

function month_name_ru(int $month): string
{
    $names = [
        1 => 'Январь', 2 => 'Февраль', 3 => 'Март', 4 => 'Апрель',
        5 => 'Май', 6 => 'Июнь', 7 => 'Июль', 8 => 'Август',
        9 => 'Сентябрь', 10 => 'Октябрь', 11 => 'Ноябрь', 12 => 'Декабрь',
    ];
    return $names[$month] ?? (string) $month;
}
