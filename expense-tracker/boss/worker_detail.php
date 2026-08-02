<?php
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/functions.php';

$boss = require_role('boss');

$workerId = (int) ($_GET['id'] ?? 0);
$year = (int) ($_GET['year'] ?? date('Y'));
$month = (int) ($_GET['month'] ?? date('n'));

$stmt = get_db()->prepare('SELECT * FROM users WHERE id = ? AND role = ?');
$stmt->execute([$workerId, 'worker']);
$worker = $stmt->fetch();

if (!$worker) {
    http_response_code(404);
    echo 'Работник не найден.';
    exit;
}

$summary = get_month_summary($worker['id'], $year, $month);
$expenses = list_month_expenses($worker['id'], $year, $month);

$pageTitle = $worker['name'];
require __DIR__ . '/../includes/layout_start.php';
?>
<p><a href="/boss/dashboard.php">&larr; Ко всем работникам</a></p>
<h1><?= htmlspecialchars($worker['name']) ?></h1>

<form method="get" class="month-picker">
    <input type="hidden" name="id" value="<?= $worker['id'] ?>">
    <select name="month">
        <?php for ($m = 1; $m <= 12; $m++): ?>
            <option value="<?= $m ?>" <?= $m === $month ? 'selected' : '' ?>><?= month_name_ru($m) ?></option>
        <?php endfor; ?>
    </select>
    <select name="year">
        <?php for ($y = (int) date('Y') - 2; $y <= (int) date('Y') + 1; $y++): ?>
            <option value="<?= $y ?>" <?= $y === $year ? 'selected' : '' ?>><?= $y ?></option>
        <?php endfor; ?>
    </select>
    <button type="submit">Показать</button>
</form>

<div class="summary-grid">
    <div class="stat">
        <div class="stat-label">Зарплата</div>
        <div class="stat-value"><?= format_money($summary['salary_usd'], 'USD') ?></div>
    </div>
    <div class="stat">
        <div class="stat-label">Потрачено за месяц</div>
        <div class="stat-value"><?= format_money($summary['total_spent_usd'], 'USD') ?></div>
        <div class="muted"><?= format_money($summary['total_spent_kzt'], 'KZT') ?></div>
    </div>
    <div class="stat">
        <div class="stat-label"><?= $summary['is_overspent'] ? 'Перерасход (долг)' : 'Остаток' ?></div>
        <div class="stat-value <?= $summary['is_overspent'] ? 'balance-negative' : 'balance-positive' ?>">
            <?= format_money(abs($summary['remaining_usd']), 'USD') ?>
        </div>
        <div class="muted"><?= format_money(abs($summary['remaining_kzt']), 'KZT') ?></div>
    </div>
</div>

<div class="card">
    <h2>Расходы за <?= month_name_ru($month) ?> <?= $year ?></h2>
    <?php if (!$expenses): ?>
        <p class="muted">Расходов за этот месяц нет.</p>
    <?php else: ?>
        <table>
            <thead><tr><th>Дата</th><th>Сумма</th><th>Описание</th></tr></thead>
            <tbody>
                <?php foreach ($expenses as $e): ?>
                    <tr>
                        <td><?= htmlspecialchars($e['expense_date']) ?></td>
                        <td><?= format_money((float) $e['amount'], $e['currency']) ?></td>
                        <td><?= htmlspecialchars($e['description'] ?? '') ?></td>
                    </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
    <?php endif; ?>
</div>

<?php require __DIR__ . '/../includes/layout_end.php'; ?>
