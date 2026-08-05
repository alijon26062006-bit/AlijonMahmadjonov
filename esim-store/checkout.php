<?php
require __DIR__ . '/includes/bootstrap.php';

['items' => $items, 'total' => $total] = get_cart_items($config);
if (empty($items)) {
    flash_set('error', 'Сначала добавьте тариф в корзину.');
    redirect(url('cart.php'));
}

$co = &$_SESSION['checkout'];
if (!is_array($co)) {
    $co = ['email' => '', 'phone' => '', 'phone_verified' => false, 'code_sent' => false, 'demo_code' => null];
}

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!csrf_check()) {
        flash_set('error', 'Сессия устарела, попробуйте ещё раз.');
        redirect(url('checkout.php'));
    }

    $action = (string) ($_POST['action'] ?? '');

    if ($action === 'send_code') {
        $email = trim((string) ($_POST['email'] ?? ''));
        $phone = normalize_phone((string) ($_POST['phone'] ?? ''));

        if (!is_valid_email($email)) {
            flash_set('error', 'Укажите корректный email.');
        } elseif (!is_valid_phone($phone)) {
            flash_set('error', 'Укажите номер телефона в международном формате, например +992900000000.');
        } else {
            $result = verification_send($pdo, $config, $phone);
            $co['email'] = $email;
            $co['phone'] = $phone;
            $co['phone_verified'] = false;
            $co['code_sent'] = true;
            $co['demo_code'] = $result['demo'] ?? false ? ($result['demo_code'] ?? null) : null;
            flash_set('ok', 'Код подтверждения отправлен на ' . $phone . '.');
        }
        redirect(url('checkout.php'));
    }

    if ($action === 'resend_code' && $co['phone']) {
        $result = verification_send($pdo, $config, $co['phone']);
        $co['demo_code'] = $result['demo'] ?? false ? ($result['demo_code'] ?? null) : null;
        flash_set('ok', 'Код отправлен повторно.');
        redirect(url('checkout.php'));
    }

    if ($action === 'change_contact') {
        $co = ['email' => '', 'phone' => '', 'phone_verified' => false, 'code_sent' => false, 'demo_code' => null];
        redirect(url('checkout.php'));
    }

    if ($action === 'verify_code' && $co['phone']) {
        $code = trim((string) ($_POST['code'] ?? ''));
        if (verification_check($pdo, $co['phone'], $code)) {
            $co['phone_verified'] = true;
            flash_set('ok', 'Номер телефона подтверждён.');
        } else {
            flash_set('error', 'Неверный или истёкший код.');
        }
        redirect(url('checkout.php'));
    }

    if ($action === 'submit_order' && $co['phone_verified']) {
        $upload = save_receipt_upload($_FILES['receipt'] ?? [], $config);
        if (!$upload['ok']) {
            flash_set('error', $upload['error']);
            redirect(url('checkout.php'));
        }

        $createdIds = [];
        foreach ($items as $item) {
            $order = order_create($pdo, $item['plan'], $item['quantity'], $co['email'], $co['phone'], true);
            order_attach_receipt($pdo, $order['id'], $upload['filename']);
            $createdIds[] = $order['id'];
        }

        cart_clear();
        $co = ['email' => '', 'phone' => '', 'phone_verified' => false, 'code_sent' => false, 'demo_code' => null];

        $firstId = array_shift($createdIds);
        $target = url('order.php?id=' . urlencode($firstId));
        if (!empty($createdIds)) {
            $target .= '&more=' . urlencode(implode(',', $createdIds));
        }
        redirect($target);
    }
}

$pageTitle = 'Оформление заказа — ' . $config['site_name'];
require __DIR__ . '/includes/header.php';
?>
<section class="container checkout">
    <h1>Оформление заказа</h1>

    <div class="checkout-grid">
        <div class="checkout-main">
            <?php if (!$co['phone_verified']): ?>
                <?php if (!$co['code_sent']): ?>
                    <div class="card">
                        <h2>1. Контактные данные</h2>
                        <p class="muted">Email нужен для связи по заказу, телефон — для подтверждения по SMS.</p>
                        <form method="post" action="<?= h(url('checkout.php')) ?>" class="form-stack">
                            <?= csrf_field() ?>
                            <input type="hidden" name="action" value="send_code">
                            <label>Email
                                <input class="input" type="email" name="email" required value="<?= h($co['email']) ?>">
                            </label>
                            <label>Телефон (с кодом страны)
                                <input class="input" type="tel" name="phone" required placeholder="+992900000000" value="<?= h($co['phone']) ?>">
                            </label>
                            <button class="btn btn-primary" type="submit">Получить код по SMS</button>
                        </form>
                    </div>
                <?php else: ?>
                    <div class="card">
                        <h2>2. Подтверждение номера</h2>
                        <p class="muted">Код отправлен на <strong><?= h($co['phone']) ?></strong>.</p>
                        <?php if (!empty($co['demo_code'])): ?>
                            <div class="flash flash-ok">Демо-режим (Zadarma не настроен): ваш код — <strong><?= h($co['demo_code']) ?></strong></div>
                        <?php endif; ?>
                        <form method="post" action="<?= h(url('checkout.php')) ?>" class="form-stack">
                            <?= csrf_field() ?>
                            <input type="hidden" name="action" value="verify_code">
                            <label>Код из SMS
                                <input class="input" type="text" name="code" inputmode="numeric" maxlength="6" required autofocus>
                            </label>
                            <button class="btn btn-primary" type="submit">Подтвердить</button>
                        </form>
                        <div class="checkout-links">
                            <form method="post" action="<?= h(url('checkout.php')) ?>">
                                <?= csrf_field() ?>
                                <input type="hidden" name="action" value="resend_code">
                                <button class="link-btn" type="submit">Отправить код ещё раз</button>
                            </form>
                            <form method="post" action="<?= h(url('checkout.php')) ?>">
                                <?= csrf_field() ?>
                                <input type="hidden" name="action" value="change_contact">
                                <button class="link-btn" type="submit">Изменить номер / email</button>
                            </form>
                        </div>
                    </div>
                <?php endif; ?>
            <?php else: ?>
                <div class="card">
                    <h2>Контакты</h2>
                    <p><?= h($co['email']) ?> · <?= h($co['phone']) ?> <span class="badge badge-success">подтверждён</span></p>
                </div>

                <div class="card">
                    <h2>3. Оплата</h2>
                    <p class="payment-instructions"><?= nl2br(h($config['payment_instructions'])) ?></p>
                    <p class="checkout-total-line">К оплате: <strong><?= money($total) ?></strong></p>
                    <form method="post" action="<?= h(url('checkout.php')) ?>" enctype="multipart/form-data" class="form-stack">
                        <?= csrf_field() ?>
                        <input type="hidden" name="action" value="submit_order">
                        <label>Скриншот чека об оплате (JPG/PNG/WEBP/PDF, до <?= (int) $config['max_receipt_size_mb'] ?> МБ)
                            <input class="input" type="file" name="receipt" accept="image/jpeg,image/png,image/webp,application/pdf" required>
                        </label>
                        <button class="btn btn-primary" type="submit">Отправить заказ на проверку</button>
                    </form>
                </div>
            <?php endif; ?>
        </div>

        <aside class="checkout-summary card">
            <h2>Ваш заказ</h2>
            <?php foreach ($items as $item): $plan = $item['plan']; ?>
                <div class="summary-row">
                    <span><?= h($plan['country_flag']) ?> <?= h($plan['country_name']) ?> — <?= h($plan['title']) ?> × <?= (int) $item['quantity'] ?></span>
                    <span><?= money($item['subtotal']) ?></span>
                </div>
            <?php endforeach; ?>
            <div class="summary-row summary-total">
                <span>Итого</span>
                <span><?= money($total) ?></span>
            </div>
        </aside>
    </div>
</section>
<?php require __DIR__ . '/includes/footer.php'; ?>
