<?php
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/functions.php';

$boss = require_role('boss');

$year = (int) ($_GET['year'] ?? date('Y'));
$month = (int) ($_GET['month'] ?? date('n'));

$stmt = get_db()->prepare('SELECT * FROM users WHERE role = ? ORDER BY name');
$stmt->execute(['worker']);
$workers = $stmt->fetchAll();

$rows = [];
foreach ($workers as $w) {
    $rows[] = ['worker' => $w, 'summary' => get_month_summary($w['id'], $year, $month)];
}

$pageTitle = 'Все работники';
require __DIR__ . '/../includes/layout_start.php';
?>
<h1>Работники — сводка за месяц</h1>

<form method="get" class="month-picker">
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

<div class="card">
    <?php if (!$rows): ?>
        <p class="muted">Работники ещё не добавлены. <a href="/boss/add_worker.php">Добавить работника</a>.</p>
    <?php else: ?>
        <table>
            <thead>
                <tr>
                    <th>Работник</th>
                    <th>Зарплата</th>
                    <th>Потрачено</th>
                    <th>Остаток / Долг</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                <?php foreach ($rows as $r): $s = $r['summary']; $w = $r['worker']; ?>
                    <tr>
                        <td><?= htmlspecialchars($w['name']) ?></td>
                        <td><?= format_money($s['salary_usd'], 'USD') ?></td>
                        <td><?= format_money($s['total_spent_usd'], 'USD') ?></td>
                        <td>
                            <span class="badge <?= $s['is_overspent'] ? 'badge-red' : 'badge-green' ?>">
                                <?= $s['is_overspent'] ? 'Долг' : 'Остаток' ?>:
                                <?= format_money(abs($s['remaining_usd']), 'USD') ?>
                            </span>
                        </td>
                        <td><a href="/boss/worker_detail.php?id=<?= $w['id'] ?>&year=<?= $year ?>&month=<?= $month ?>">Подробнее</a></td>
                    </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
    <?php endif; ?>
</div>

<?php require __DIR__ . '/../includes/layout_end.php'; ?>
