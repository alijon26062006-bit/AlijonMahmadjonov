<?php
require __DIR__ . '/includes/bootstrap.php';

$pageTitle = $config['site_name'] . ' — eSIM для путешествий';
$destinations = array_slice(get_destinations($config), 0, 8);

require __DIR__ . '/includes/header.php';
?>
<section class="hero">
    <div class="container hero-inner">
        <div>
            <h1>Интернет в поездке за минуту</h1>
            <p class="hero-sub">Купите eSIM онлайн, оплатите переводом и получите QR-код для активации — без физической SIM-карты и роуминга.</p>
            <a class="btn btn-primary" href="<?= h(url('destinations.php')) ?>">Выбрать страну</a>
        </div>
        <div class="hero-card card">
            <div class="hero-card-row"><span>1</span> Выберите тариф и страну</div>
            <div class="hero-card-row"><span>2</span> Подтвердите номер телефона по SMS</div>
            <div class="hero-card-row"><span>3</span> Оплатите и загрузите чек</div>
            <div class="hero-card-row"><span>4</span> Получите QR-код eSIM</div>
        </div>
    </div>
</section>

<section class="container">
    <div class="section-heading">
        <h2>Популярные направления</h2>
        <a href="<?= h(url('destinations.php')) ?>">Все направления →</a>
    </div>
    <div class="grid grid-4">
        <?php foreach ($destinations as $d): ?>
            <a class="card dest-card" href="<?= h(url('destination.php?slug=' . urlencode($d['slug']))) ?>">
                <div class="dest-flag"><?= h($d['flag']) ?></div>
                <div class="dest-name"><?= h($d['name']) ?></div>
                <div class="dest-price">от <?= money($d['plans_from']) ?></div>
            </a>
        <?php endforeach; ?>
    </div>
</section>

<section id="how-it-works" class="container">
    <h2>Как это работает</h2>
    <div class="grid grid-4">
        <div class="card step-card">
            <div class="step-num">1</div>
            <h3>Выбираете тариф</h3>
            <p class="muted">Страна или регион, объём трафика и срок действия.</p>
        </div>
        <div class="card step-card">
            <div class="step-num">2</div>
            <h3>Подтверждаете номер</h3>
            <p class="muted">Код по SMS присылаем через Zadarma.</p>
        </div>
        <div class="card step-card">
            <div class="step-num">3</div>
            <h3>Оплачиваете переводом</h3>
            <p class="muted">Переводите сумму на карту и прикладываете скриншот чека.</p>
        </div>
        <div class="card step-card">
            <div class="step-num">4</div>
            <h3>Получаете eSIM</h3>
            <p class="muted">После проверки чека администратором придёт QR-код для установки.</p>
        </div>
    </div>
</section>

<?php require __DIR__ . '/includes/footer.php'; ?>
