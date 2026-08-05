<?php
require __DIR__ . '/includes/bootstrap.php';

$slug = (string) ($_GET['slug'] ?? '');
$destination = get_destination($config, $slug);
if (!$destination) {
    http_response_code(404);
    $pageTitle = 'Страна не найдена';
    require __DIR__ . '/includes/header.php';
    echo '<section class="container"><h1>Страна не найдена</h1><p><a href="' . h(url('destinations.php')) . '">← Ко всем направлениям</a></p></section>';
    require __DIR__ . '/includes/footer.php';
    exit;
}

$plans = get_plans_for_country($config, $slug);
$pageTitle = $destination['name'] . ' — тарифы eSIM';

require __DIR__ . '/includes/header.php';
?>
<section class="container">
    <p><a class="muted" href="<?= h(url('destinations.php')) ?>">← Ко всем направлениям</a></p>
    <h1><span class="dest-flag-inline"><?= h($destination['flag']) ?></span> eSIM для «<?= h($destination['name']) ?>»</h1>

    <div class="grid grid-3">
        <?php foreach ($plans as $plan): ?>
            <div class="card plan-card">
                <div class="plan-data"><?= h($plan['data_amount']) ?></div>
                <div class="plan-days"><?= (int) $plan['days'] ?> дней</div>
                <div class="plan-price"><?= money($plan['price_usd']) ?></div>
                <form method="post" action="<?= h(url('cart.php')) ?>">
                    <?= csrf_field() ?>
                    <input type="hidden" name="action" value="add">
                    <input type="hidden" name="plan_id" value="<?= h($plan['id']) ?>">
                    <button class="btn btn-primary" type="submit">В корзину</button>
                </form>
            </div>
        <?php endforeach; ?>
        <?php if (empty($plans)): ?>
            <p class="muted">Для этого направления пока нет тарифов.</p>
        <?php endif; ?>
    </div>
</section>
<?php require __DIR__ . '/includes/footer.php'; ?>
