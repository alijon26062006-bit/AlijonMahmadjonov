<?php
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/functions.php';

$boss = require_role('boss');
$error = '';
$success = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = $_POST['action'] ?? '';

    if ($action === 'rate') {
        $rate = (float) str_replace(',', '.', $_POST['exchange_rate_kzt_per_usd'] ?? '0');
        if ($rate <= 0) {
            $error = 'Курс должен быть больше нуля.';
        } else {
            set_exchange_rate($rate);
            $success = 'Курс обновлён.';
        }
    } elseif ($action === 'password') {
        $current = $_POST['current_password'] ?? '';
        $new = $_POST['new_password'] ?? '';
        if (!password_verify($current, $boss['password_hash'])) {
            $error = 'Текущий пароль указан неверно.';
        } elseif (strlen($new) < 6) {
            $error = 'Новый пароль должен быть не короче 6 символов.';
        } else {
            $stmt = get_db()->prepare('UPDATE users SET password_hash = ? WHERE id = ?');
            $stmt->execute([password_hash($new, PASSWORD_DEFAULT), $boss['id']]);
            $success = 'Пароль изменён.';
        }
    }
}

$currentRate = get_exchange_rate();

$pageTitle = 'Настройки';
require __DIR__ . '/../includes/layout_start.php';
?>
<h1>Настройки</h1>
<?php if ($error): ?><div class="error"><?= htmlspecialchars($error) ?></div><?php endif; ?>
<?php if ($success): ?><div class="success"><?= htmlspecialchars($success) ?></div><?php endif; ?>

<div class="card">
    <h2>Курс обмена</h2>
    <p class="muted">Сколько тенге за 1 доллар — используется для пересчёта расходов в тенге в общий баланс.</p>
    <form method="post">
        <input type="hidden" name="action" value="rate">
        <div>
            <label>Тенге за $1</label>
            <input type="text" name="exchange_rate_kzt_per_usd" inputmode="decimal"
                   value="<?= htmlspecialchars((string) $currentRate) ?>" required>
        </div>
        <button type="submit">Сохранить</button>
    </form>
</div>

<div class="card">
    <h2>Сменить пароль</h2>
    <form method="post">
        <input type="hidden" name="action" value="password">
        <div>
            <label>Текущий пароль</label>
            <input type="password" name="current_password" required>
        </div>
        <div>
            <label>Новый пароль</label>
            <input type="password" name="new_password" required minlength="6">
        </div>
        <button type="submit">Сменить пароль</button>
    </form>
</div>

<?php require __DIR__ . '/../includes/layout_end.php'; ?>
