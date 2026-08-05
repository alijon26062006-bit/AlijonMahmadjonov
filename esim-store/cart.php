<?php
require __DIR__ . '/includes/bootstrap.php';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    if (!csrf_check()) {
        flash_set('error', 'Сессия устарела, попробуйте ещё раз.');
        redirect(url('cart.php'));
    }

    $action = (string) ($_POST['action'] ?? '');
    $planId = (string) ($_POST['plan_id'] ?? '');

    if ($action === 'add' && $planId !== '') {
        if (get_plan_by_id($config, $planId)) {
            cart_add($planId, 1);
            flash_set('ok', 'Тариф добавлен в корзину.');
        } else {
            flash_set('error', 'Этот тариф больше недоступен.');
        }
    } elseif ($action === 'update' && $planId !== '') {
        $qty = max(0, (int) ($_POST['quantity'] ?? 1));
        if ($qty === 0) {
            cart_remove($planId);
        } else {
            $_SESSION['cart'][$planId]['quantity'] = $qty;
        }
    } elseif ($action === 'remove' && $planId !== '') {
        cart_remove($planId);
        flash_set('ok', 'Тариф удалён из корзины.');
    }

    redirect(url('cart.php'));
}

$pageTitle = 'Корзина — ' . $config['site_name'];

$cartBefore = count(cart_get());
['items' => $items, 'total' => $total] = get_cart_items($config);
if (count($items) < $cartBefore) {
    flash_set('error', 'Часть тарифов из корзины больше недоступна и была удалена.');
}

require __DIR__ . '/includes/header.php';
?>
<section class="container">
    <h1>Корзина</h1>

    <?php if (empty($items)): ?>
        <p class="muted">Корзина пуста.</p>
        <a class="btn btn-primary" href="<?= h(url('destinations.php')) ?>">Выбрать тариф</a>
    <?php else: ?>
        <div class="cart-list">
            <?php foreach ($items as $item): $plan = $item['plan']; ?>
                <div class="card cart-row">
                    <div class="cart-row-info">
                        <div class="dest-flag-inline"><?= h($plan['country_flag']) ?></div>
                        <div>
                            <div class="cart-row-title"><?= h($plan['country_name']) ?> — <?= h($plan['title']) ?></div>
                            <div class="muted"><?= money($plan['price_usd']) ?> за шт.</div>
                        </div>
                    </div>
                    <form method="post" action="<?= h(url('cart.php')) ?>" class="cart-row-qty">
                        <?= csrf_field() ?>
                        <input type="hidden" name="action" value="update">
                        <input type="hidden" name="plan_id" value="<?= h($plan['id']) ?>">
                        <input class="input" type="number" name="quantity" min="0" max="10" value="<?= (int) $item['quantity'] ?>">
                        <button class="btn btn-secondary" type="submit">Обновить</button>
                    </form>
                    <div class="cart-row-subtotal"><?= money($item['subtotal']) ?></div>
                    <form method="post" action="<?= h(url('cart.php')) ?>">
                        <?= csrf_field() ?>
                        <input type="hidden" name="action" value="remove">
                        <input type="hidden" name="plan_id" value="<?= h($plan['id']) ?>">
                        <button class="btn btn-secondary" type="submit">Удалить</button>
                    </form>
                </div>
            <?php endforeach; ?>
        </div>

        <div class="cart-total card">
            <div>Итого</div>
            <div class="cart-total-amount"><?= money($total) ?></div>
        </div>

        <a class="btn btn-primary" href="<?= h(url('checkout.php')) ?>">Оформить заказ</a>
    <?php endif; ?>
</section>
<?php require __DIR__ . '/includes/footer.php'; ?>
