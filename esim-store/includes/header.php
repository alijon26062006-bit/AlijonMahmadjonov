<?php
/** @var array $config expected in scope */
$pageTitle = $pageTitle ?? $config['site_name'];
?><!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?= h($pageTitle) ?></title>
    <link rel="stylesheet" href="<?= h(url('assets/css/style.css')) ?>">
    <link rel="icon" href="data:,">
</head>
<body>
<header class="site-header">
    <div class="container header-inner">
        <a class="logo" href="<?= h(url('index.php')) ?>">
            <span class="logo-mark">◍</span> <?= h($config['site_name']) ?>
        </a>
        <nav class="main-nav">
            <a href="<?= h(url('destinations.php')) ?>">Каталог</a>
            <a href="<?= h(url('index.php#how-it-works')) ?>">Как это работает</a>
        </nav>
        <a class="cart-link" href="<?= h(url('cart.php')) ?>">
            Корзина
            <?php $n = cart_count(); if ($n > 0): ?>
                <span class="cart-badge"><?= (int) $n ?></span>
            <?php endif; ?>
        </a>
    </div>
</header>
<?php $flashOk = flash_get('ok'); $flashErr = flash_get('error'); ?>
<?php if ($flashOk): ?>
    <div class="container"><div class="flash flash-ok"><?= h($flashOk) ?></div></div>
<?php endif; ?>
<?php if ($flashErr): ?>
    <div class="container"><div class="flash flash-error"><?= h($flashErr) ?></div></div>
<?php endif; ?>
<main>
