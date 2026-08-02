<?php
require_once __DIR__ . '/../includes/auth.php';
require_once __DIR__ . '/../includes/functions.php';

$boss = require_role('boss');
$error = '';
$success = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $name = trim($_POST['name'] ?? '');
    $username = trim($_POST['username'] ?? '');
    $phone = trim($_POST['phone'] ?? '');
    $email = trim($_POST['email'] ?? '');
    $password = $_POST['password'] ?? '';
    $salary = (float) str_replace(',', '.', $_POST['monthly_salary_usd'] ?? '0');

    if ($name === '' || $username === '' || strlen($password) < 6) {
        $error = 'Заполните имя, логин и пароль (минимум 6 символов).';
    } else {
        $stmt = get_db()->prepare('SELECT id FROM users WHERE username = ?');
        $stmt->execute([$username]);
        if ($stmt->fetch()) {
            $error = 'Такой логин уже занят.';
        } else {
            $stmt = get_db()->prepare(
                'INSERT INTO users (name, username, phone, email, password_hash, role, monthly_salary_usd)
                 VALUES (?, ?, ?, ?, ?, ?, ?)'
            );
            $stmt->execute([
                $name,
                $username,
                $phone ?: null,
                $email ?: null,
                password_hash($password, PASSWORD_DEFAULT),
                'worker',
                $salary > 0 ? $salary : null,
            ]);
            $success = 'Работник добавлен: ' . htmlspecialchars($name);
        }
    }
}

$pageTitle = 'Добавить работника';
require __DIR__ . '/../includes/layout_start.php';
?>
<h1>Добавить работника</h1>
<?php if ($error): ?><div class="error"><?= htmlspecialchars($error) ?></div><?php endif; ?>
<?php if ($success): ?><div class="success"><?= $success ?> <a href="/boss/dashboard.php">К списку работников</a></div><?php endif; ?>

<div class="card">
    <form method="post">
        <div>
            <label>Имя</label>
            <input type="text" name="name" required>
        </div>
        <div>
            <label>Логин (например, номер телефона)</label>
            <input type="text" name="username" required>
        </div>
        <div>
            <label>Телефон</label>
            <input type="text" name="phone">
        </div>
        <div>
            <label>Email (для входа через Google и уведомлений)</label>
            <input type="email" name="email">
        </div>
        <div>
            <label>Пароль</label>
            <input type="password" name="password" required minlength="6">
        </div>
        <div>
            <label>Месячная зарплата, $ (можно указать позже)</label>
            <input type="text" name="monthly_salary_usd" inputmode="decimal">
        </div>
        <button type="submit">Добавить</button>
    </form>
</div>

<?php require __DIR__ . '/../includes/layout_end.php'; ?>
