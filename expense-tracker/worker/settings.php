<?php
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/functions.php';

$user = require_role('worker');
$error = '';
$success = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = $_POST['action'] ?? '';

    if ($action === 'salary') {
        $salary = (float) str_replace(',', '.', $_POST['monthly_salary_usd'] ?? '0');
        if ($salary <= 0) {
            $error = 'Укажите зарплату больше нуля.';
        } else {
            $stmt = get_db()->prepare('UPDATE users SET monthly_salary_usd = ? WHERE id = ?');
            $stmt->execute([$salary, $user['id']]);
            $success = 'Зарплата обновлена.';
            $user['monthly_salary_usd'] = $salary;
        }
    } elseif ($action === 'password') {
        $current = $_POST['current_password'] ?? '';
        $new = $_POST['new_password'] ?? '';
        if (!password_verify($current, $user['password_hash'])) {
            $error = 'Текущий пароль указан неверно.';
        } elseif (strlen($new) < 6) {
            $error = 'Новый пароль должен быть не короче 6 символов.';
        } else {
            $stmt = get_db()->prepare('UPDATE users SET password_hash = ? WHERE id = ?');
            $stmt->execute([password_hash($new, PASSWORD_DEFAULT), $user['id']]);
            $success = 'Пароль изменён.';
        }
    } elseif ($action === 'email') {
        $email = trim($_POST['email'] ?? '');
        $stmt = get_db()->prepare('UPDATE users SET email = ? WHERE id = ?');
        $stmt->execute([$email ?: null, $user['id']]);
        $success = 'Email обновлён.';
        $user['email'] = $email;
    }
}

$pageTitle = 'Настройки';
require __DIR__ . '/../includes/layout_start.php';
?>
<h1>Настройки</h1>
<?php if ($error): ?><div class="error"><?= htmlspecialchars($error) ?></div><?php endif; ?>
<?php if ($success): ?><div class="success"><?= htmlspecialchars($success) ?></div><?php endif; ?>

<div class="card">
    <h2>Моя месячная зарплата</h2>
    <form method="post">
        <input type="hidden" name="action" value="salary">
        <div>
            <label>Зарплата в долларах ($)</label>
            <input type="text" name="monthly_salary_usd" inputmode="decimal"
                   value="<?= htmlspecialchars((string) ($user['monthly_salary_usd'] ?? '')) ?>" required>
        </div>
        <button type="submit">Сохранить</button>
    </form>
</div>

<div class="card">
    <h2>Email (для входа через Google и уведомлений)</h2>
    <form method="post">
        <input type="hidden" name="action" value="email">
        <div>
            <label>Email</label>
            <input type="email" name="email" value="<?= htmlspecialchars($user['email'] ?? '') ?>">
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
