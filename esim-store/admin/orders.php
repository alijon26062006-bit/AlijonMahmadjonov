<?php
require __DIR__ . '/../includes/bootstrap.php';
admin_require(url('admin/index.php'));

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!csrf_check()) {
        flash_set('error', 'Сессия устарела, попробуйте ещё раз.');
        redirect(url('admin/orders.php'));
    }

    $action = (string) ($_POST['action'] ?? '');
    $orderId = (string) ($_POST['order_id'] ?? '');

    if ($action === 'confirm' && $orderId !== '') {
        $result = order_confirm_and_issue($pdo, $config, $orderId);
        flash_set($result['ok'] ? 'ok' : 'error', $result['ok']
            ? "Заказ $orderId подтверждён, eSIM выдан."
            : "Не удалось выдать eSIM для заказа $orderId: " . ($result['error'] ?? ''));
    } elseif ($action === 'reject' && $orderId !== '') {
        $note = trim((string) ($_POST['note'] ?? ''));
        order_reject($pdo, $orderId, $note);
        flash_set('ok', "Заказ $orderId отклонён.");
    }

    redirect(url('admin/orders.php') . (isset($_GET['status']) ? '?status=' . urlencode((string) $_GET['status']) : ''));
}

$statusFilter = $_GET['status'] ?? null;
$statusFilter = $statusFilter !== '' ? $statusFilter : null;
$orders = order_list_all($pdo, $statusFilter);

$pageTitle = 'Заказы — Админ-панель';
$statuses = [
    null => 'Все',
    'pending_review' => 'На проверке',
    'pending_payment' => 'Ждут оплаты',
    'issued' => 'Выданы',
    'rejected' => 'Отклонены',
    'failed' => 'Ошибка выдачи',
];
?><!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title><?= h($pageTitle) ?></title>
    <link rel="stylesheet" href="<?= h(url('assets/css/style.css')) ?>">
</head>
<body class="admin-body">
<div class="container admin-page">
    <div class="admin-topbar">
        <h1>Заказы</h1>
        <form method="post" action="<?= h(url('admin/logout.php')) ?>"><button class="link-btn" type="submit">Выйти</button></form>
    </div>

    <?php $flashOk = flash_get('ok'); $flashErr = flash_get('error'); ?>
    <?php if ($flashOk): ?><div class="flash flash-ok"><?= h($flashOk) ?></div><?php endif; ?>
    <?php if ($flashErr): ?><div class="flash flash-error"><?= h($flashErr) ?></div><?php endif; ?>

    <div class="admin-filters">
        <?php foreach ($statuses as $value => $label): ?>
            <a class="filter-pill <?= $statusFilter === $value ? 'active' : '' ?>"
               href="<?= h(url('admin/orders.php') . ($value ? '?status=' . urlencode($value) : '')) ?>"><?= h($label) ?></a>
        <?php endforeach; ?>
    </div>

    <?php if (empty($orders)): ?>
        <p class="muted">Заказов нет.</p>
    <?php endif; ?>

    <div class="admin-order-list">
        <?php foreach ($orders as $order): $badge = order_status_badge($order['status']); ?>
            <div class="card admin-order">
                <div class="admin-order-head">
                    <div>
                        <strong>#<?= h($order['id']) ?></strong>
                        <span class="muted"><?= h($order['created_at']) ?></span>
                    </div>
                    <span class="badge <?= h($badge['class']) ?>"><?= h($badge['label']) ?></span>
                </div>
                <div class="admin-order-body">
                    <div><?= h($order['country_flag']) ?> <?= h($order['country_name']) ?> — <?= h($order['plan_title']) ?> × <?= (int) $order['quantity'] ?> · <strong><?= money((float) $order['total_usd']) ?></strong></div>
                    <div class="muted"><?= h($order['customer_email']) ?> · <?= h($order['customer_phone']) ?></div>
                    <?php if (!empty($order['receipt_filename'])): ?>
                        <a class="link-btn" target="_blank" rel="noopener" href="<?= h(url('admin/receipt.php?order=' . urlencode($order['id']))) ?>">Открыть чек →</a>
                    <?php endif; ?>
                    <?php if (!empty($order['esim_iccid'])): ?>
                        <div class="muted">ICCID: <code><?= h($order['esim_iccid']) ?></code><?= !empty($order['esim_demo']) ? ' (демо)' : '' ?></div>
                    <?php endif; ?>
                    <?php if (!empty($order['admin_note'])): ?>
                        <div class="muted">Заметка: <?= h($order['admin_note']) ?></div>
                    <?php endif; ?>
                </div>

                <?php if (in_array($order['status'], ['pending_review', 'failed'], true)): ?>
                    <div class="admin-order-actions">
                        <form method="post" action="<?= h(url('admin/orders.php')) ?>">
                            <?= csrf_field() ?>
                            <input type="hidden" name="action" value="confirm">
                            <input type="hidden" name="order_id" value="<?= h($order['id']) ?>">
                            <button class="btn btn-primary" type="submit">
                                <?= $order['status'] === 'failed' ? 'Повторить выдачу' : 'Подтвердить и выдать eSIM' ?>
                            </button>
                        </form>
                        <?php if ($order['status'] === 'pending_review'): ?>
                            <form method="post" action="<?= h(url('admin/orders.php')) ?>" class="admin-reject-form">
                                <?= csrf_field() ?>
                                <input type="hidden" name="action" value="reject">
                                <input type="hidden" name="order_id" value="<?= h($order['id']) ?>">
                                <input class="input" type="text" name="note" placeholder="Причина отказа (необязательно)">
                                <button class="btn btn-danger" type="submit">Отклонить</button>
                            </form>
                        <?php endif; ?>
                    </div>
                <?php endif; ?>
            </div>
        <?php endforeach; ?>
    </div>
</div>
</body>
</html>
