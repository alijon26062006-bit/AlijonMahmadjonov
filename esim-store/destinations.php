<?php
require __DIR__ . '/includes/bootstrap.php';

$pageTitle = 'Все направления — ' . $config['site_name'];
$destinations = get_destinations($config);
$q = trim((string) ($_GET['q'] ?? ''));
if ($q !== '') {
    $needle = mb_strtolower($q);
    $destinations = array_values(array_filter($destinations, function ($d) use ($needle) {
        return str_contains(mb_strtolower($d['name']), $needle);
    }));
}

require __DIR__ . '/includes/header.php';
?>
<section class="container">
    <h1>Все направления</h1>
    <form class="search-form" method="get" action="<?= h(url('destinations.php')) ?>">
        <input class="input" type="text" name="q" placeholder="Поиск по стране…" value="<?= h($q) ?>">
        <button class="btn btn-secondary" type="submit">Найти</button>
    </form>

    <?php if (empty($destinations)): ?>
        <p class="muted">Ничего не найдено.</p>
    <?php endif; ?>

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
<?php require __DIR__ . '/includes/footer.php'; ?>
