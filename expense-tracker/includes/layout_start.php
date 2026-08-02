<?php
/**
 * @var string $pageTitle
 * Ожидает, что $pageTitle задан перед подключением, и current_user() уже доступна (auth.php подключён).
 */
$user = current_user();
?>
<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title><?= htmlspecialchars($pageTitle ?? 'Учёт расходов') ?></title>
<link rel="stylesheet" href="/assets/style.css">
</head>
<body>
<?php if ($user): ?>
<header class="topbar">
    <div class="topbar-title">Учёт расходов</div>
    <nav class="topbar-nav">
        <?php if ($user['role'] === 'boss'): ?>
            <a href="/boss/dashboard.php">Все работники</a>
            <a href="/boss/add_worker.php">Добавить работника</a>
            <a href="/boss/settings.php">Настройки</a>
        <?php else: ?>
            <a href="/worker/dashboard.php">Моя панель</a>
            <a href="/worker/add_expense.php">Добавить расход</a>
            <a href="/worker/settings.php">Настройки</a>
        <?php endif; ?>
        <span class="topbar-user"><?= htmlspecialchars($user['name']) ?></span>
        <a href="/logout.php">Выйти</a>
    </nav>
</header>
<?php endif; ?>
<main class="container">
