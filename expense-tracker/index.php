<?php
require_once __DIR__ . '/includes/auth.php';

if (current_user()) {
    $u = current_user();
    header('Location: ' . ($u['role'] === 'boss' ? '/boss/dashboard.php' : '/worker/dashboard.php'));
    exit;
}

$error = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $username = trim($_POST['username'] ?? '');
    $password = $_POST['password'] ?? '';

    $stmt = get_db()->prepare('SELECT * FROM users WHERE username = ?');
    $stmt->execute([$username]);
    $user = $stmt->fetch();

    if ($user && password_verify($password, $user['password_hash'])) {
        login_user($user);
        header('Location: ' . ($user['role'] === 'boss' ? '/boss/dashboard.php' : '/worker/dashboard.php'));
        exit;
    }
    $error = 'Неверный логин или пароль.';
}

$pageTitle = 'Вход';
require __DIR__ . '/includes/layout_start.php';
?>
<div class="login-wrap">
    <h1>Вход</h1>
    <?php if ($error): ?><div class="error"><?= htmlspecialchars($error) ?></div><?php endif; ?>
    <form method="post">
        <div>
            <label>Логин (номер телефона)</label>
            <input type="text" name="username" required autofocus>
        </div>
        <div>
            <label>Пароль</label>
            <input type="password" name="password" required>
        </div>
        <button type="submit">Войти</button>
    </form>
    <div class="divider">или</div>
    <a class="btn btn-google" href="/auth/google_login.php" style="display:block;text-align:center;">Войти через Google</a>
    <p class="muted" style="margin-top:16px;">Аккаунты создаёт шеф. Если у вас нет логина — обратитесь к руководителю.</p>
</div>
<?php require __DIR__ . '/includes/layout_end.php'; ?>
