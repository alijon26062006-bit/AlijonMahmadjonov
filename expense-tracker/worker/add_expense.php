<?php
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/functions.php';

$user = require_role('worker');
$error = '';
$success = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $amount = (float) str_replace(',', '.', $_POST['amount'] ?? '0');
    $currency = ($_POST['currency'] ?? 'KZT') === 'USD' ? 'USD' : 'KZT';
    $description = trim($_POST['description'] ?? '');
    $date = $_POST['expense_date'] ?? date('Y-m-d');

    if ($amount <= 0) {
        $error = 'Укажите сумму расхода больше нуля.';
    } else {
        $stmt = get_db()->prepare(
            'INSERT INTO expenses (user_id, amount, currency, description, expense_date) VALUES (?, ?, ?, ?, ?)'
        );
        $stmt->execute([$user['id'], $amount, $currency, $description ?: null, $date]);
        $success = 'Расход добавлен.';
    }
}

$pageTitle = 'Добавить расход';
require __DIR__ . '/../includes/layout_start.php';
?>
<h1>Добавить расход</h1>
<?php if ($error): ?><div class="error"><?= htmlspecialchars($error) ?></div><?php endif; ?>
<?php if ($success): ?><div class="success"><?= htmlspecialchars($success) ?> <a href="/worker/dashboard.php">К панели</a></div><?php endif; ?>

<div class="card">
    <form method="post">
        <div>
            <label>Сумма</label>
            <input type="text" name="amount" inputmode="decimal" required>
        </div>
        <div>
            <label>Валюта</label>
            <select name="currency">
                <option value="KZT">Тенге (₸)</option>
                <option value="USD">Доллары ($)</option>
            </select>
        </div>
        <div>
            <label>Дата</label>
            <input type="date" name="expense_date" value="<?= date('Y-m-d') ?>" required>
        </div>
        <div>
            <label>Описание (необязательно)</label>
            <input type="text" name="description" placeholder="Например: наличка, вещи...">
        </div>
        <button type="submit">Сохранить</button>
    </form>
</div>

<?php require __DIR__ . '/../includes/layout_end.php'; ?>
