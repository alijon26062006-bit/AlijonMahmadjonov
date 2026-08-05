<?php
require __DIR__ . '/../includes/bootstrap.php';

if (admin_is_logged_in()) {
    redirect(url('admin/orders.php'));
}

$error = null;
if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!csrf_check()) {
        $error = 'Сессия устарела, обновите страницу.';
    } elseif (admin_login_locked()) {
        $error = 'Слишком много неудачных попыток. Подождите минуту.';
    } elseif (admin_login($config, (string) ($_POST['password'] ?? ''))) {
        redirect(url('admin/orders.php'));
    } else {
        $error = 'Неверный пароль.';
    }
}

$pageTitle = 'Вход в админ-панель — ' . $config['site_name'];
?><!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?= h($pageTitle) ?></title>
    <link rel="stylesheet" href="<?= h(url('assets/css/style.css')) ?>">
</head>
<body class="admin-body">
<div class="admin-login card">
    <h1>Админ-панель</h1>
    <p class="muted"><?= h($config['site_name']) ?></p>
    <?php if ($error): ?>
        <div class="flash flash-error"><?= h($error) ?></div>
    <?php endif; ?>
    <form method="post" action="<?= h(url('admin/index.php')) ?>" class="form-stack">
        <?= csrf_field() ?>
        <label>Пароль
            <input class="input" type="password" name="password" required autofocus>
        </label>
        <button class="btn btn-primary" type="submit">Войти</button>
    </form>
</div>
</body>
</html>
