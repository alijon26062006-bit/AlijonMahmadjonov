<?php
require __DIR__ . '/includes/bootstrap.php';

$id = (string) ($_GET['id'] ?? '');
$moreIds = array_filter(explode(',', (string) ($_GET['more'] ?? '')));
$ids = array_merge([$id], $moreIds);

$orders = [];
foreach ($ids as $oid) {
    $order = order_get($pdo, $oid);
    if ($order) {
        $orders[] = $order;
    }
}

if (empty($orders)) {
    http_response_code(404);
    $pageTitle = 'Заказ не найден';
    require __DIR__ . '/includes/header.php';
    echo '<section class="container"><h1>Заказ не найден</h1><p><a href="' . h(url('destinations.php')) . '">← В каталог</a></p></section>';
    require __DIR__ . '/includes/footer.php';
    exit;
}

$pageTitle = 'Заказ ' . $orders[0]['id'] . ' — ' . $config['site_name'];
require __DIR__ . '/includes/header.php';
?>
<section class="container order-page">
    <h1>Спасибо за заказ!</h1>
    <p class="muted">Сохраните эту страницу — по ней можно проверить статус заказа и получить eSIM.</p>

    <?php foreach ($orders as $order): $badge = order_status_badge($order['status']); ?>
        <div class="card order-card">
            <div class="order-card-head">
                <div>
                    <div class="order-id">Заказ #<?= h($order['id']) ?></div>
                    <div class="muted"><?= h($order['country_flag']) ?> <?= h($order['country_name']) ?> — <?= h($order['plan_title']) ?> × <?= (int) $order['quantity']; ?></div>
                </div>
                <span class="badge <?= h($badge['class']) ?>"><?= h($badge['label']) ?></span>
            </div>

            <?php if ($order['status'] === 'pending_review'): ?>
                <p>Мы проверяем ваш чек об оплате. Обычно это занимает не больше нескольких часов — статус на этой странице обновится автоматически.</p>
            <?php elseif ($order['status'] === 'rejected'): ?>
                <p>Оплату подтвердить не удалось<?= $order['admin_note'] ? ': ' . h($order['admin_note']) : '.' ?> Свяжитесь с поддержкой: <?= h($config['support_email']) ?>.</p>
            <?php elseif ($order['status'] === 'failed'): ?>
                <p>При выдаче eSIM произошла ошибка. Мы уже разбираемся — напишите нам, если долго нет ответа: <?= h($config['support_email']) ?>.</p>
            <?php elseif ($order['status'] === 'issued'): ?>
                <?php if (!empty($order['esim_demo'])): ?>
                    <div class="flash flash-ok">Демо-режим: реальный поставщик Airalo ещё не подключён (нет ключей в config.local.php), поэтому это тестовый eSIM.</div>
                <?php endif; ?>
                <div class="esim-box">
                    <?php if (!empty($order['esim_qr_url'])): ?>
                        <img class="esim-qr" src="<?= h($order['esim_qr_url']) ?>" alt="QR-код eSIM">
                    <?php endif; ?>
                    <div>
                        <?php if (!empty($order['esim_iccid'])): ?>
                            <div><span class="muted">ICCID:</span> <code><?= h($order['esim_iccid']) ?></code></div>
                        <?php endif; ?>
                        <?php if (!empty($order['esim_qr_url'])): ?>
                            <p>Отсканируйте QR-код камерой в настройках eSIM на телефоне.</p>
                        <?php elseif (!empty($order['esim_iccid'])): ?>
                            <p class="muted">QR-изображение недоступно — используйте ручную активацию eSIM в настройках телефона с этим ICCID/кодом активации.</p>
                        <?php endif; ?>
                    </div>
                </div>
            <?php endif; ?>
        </div>
    <?php endforeach; ?>

    <a class="btn btn-secondary" href="<?= h(url('destinations.php')) ?>">Купить ещё один тариф</a>
</section>
<?php require __DIR__ . '/includes/footer.php'; ?>
