<?php
/** @var string $csrf
 *  @var list<array<string,mixed>> $sites
 *  @var array<string,mixed> $user
 *  @var string $rootDomain
 */
use Hosting\Support\Html;

$statusText = [
    'pending'   => 'Создаётся',
    'active'    => 'Активен',
    'suspended' => 'Приостановлен',
    'error'     => 'Ошибка',
    'deleted'   => 'Удалён',
];
$statusClass = ['active' => 'active', 'pending' => 'pending'];
?>
<style>
  /* Карточки вместо таблицы на любой ширине: таблица с кнопками на телефоне
     обязательно уезжает за экран, а горизонтальная прокрутка в панели
     управления — это не «мелкое неудобство», это невозможность нажать кнопку. */
  .sl-grid { display:grid; gap:16px; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); }
  .sl-card { background:var(--surface); border:1px solid var(--border); border-radius:var(--r-lg);
             padding:20px; box-shadow:var(--shadow-sm); }
  .sl-top { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-bottom:6px; }
  .sl-domain { font-weight:700; font-size:16px; word-break:break-all; }
  .sl-meta { font-size:13.5px; color:var(--muted); margin-bottom:14px; }
  .sl-actions { display:grid; gap:8px; grid-template-columns:1fr 1fr; }
  .sl-actions .btn, .sl-actions button { width:100%; justify-content:center; padding:9px 12px; font-size:14px; }
  .sl-actions form { display:contents; }
  .sl-wide { grid-column:1 / -1; }
  .sl-new { display:flex; gap:10px; align-items:flex-end; flex-wrap:wrap; }
  .sl-new > div { flex:1 1 200px; }
</style>

<div class="card">
  <h2 style="margin-top:0;">Новый сайт</h2>
  <form method="post" action="/sites" class="sl-new">
    <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
    <div>
      <label>Имя сайта</label>
      <input type="text" name="slug" placeholder="shop" required pattern="[a-z0-9-]{3,30}">
      <div class="muted" style="margin-top:6px;">Адрес будет: <code>имя.<?= Html::e($rootDomain) ?></code></div>
    </div>
    <button type="submit">Создать сайт</button>
  </form>
  <p class="muted" style="margin-bottom:0;">Сайтов: <?= count($sites) ?> из <?= Html::e($user['max_sites']) ?> по тарифу</p>
</div>

<h2 style="margin:24px 0 14px;">Мои сайты</h2>

<?php if ($sites === []): ?>
  <div class="card"><p class="muted" style="margin:0;">Пока нет ни одного сайта. Создайте первый — это займёт полминуты.</p></div>
<?php else: ?>
  <div class="sl-grid">
    <?php foreach ($sites as $site): $sid = (int) $site['id']; ?>
      <div class="sl-card">
        <div class="sl-top">
          <span class="sl-domain"><?= Html::e($site['domain']) ?></span>
          <span class="badge <?= Html::e($statusClass[$site['status']] ?? 'suspended') ?>">
            <?= Html::e($statusText[$site['status']] ?? $site['status']) ?>
          </span>
        </div>
        <div class="sl-meta">PHP <?= Html::e($site['php_version']) ?></div>

        <div class="sl-actions">
          <a class="btn" href="/sites/<?= $sid ?>">Открыть</a>
          <a class="btn secondary" href="/sites/<?= $sid ?>/files">Файлы</a>
          <a class="btn secondary" href="/sites/<?= $sid ?>/logs">Логи</a>
          <a class="btn secondary" href="/sites/<?= $sid ?>/domains">Домены</a>

          <?php if ($site['status'] === 'active'): ?>
            <form method="post" action="/sites/<?= $sid ?>/suspend">
              <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
              <button type="submit" class="secondary">Приостановить</button>
            </form>
          <?php elseif ($site['status'] === 'suspended'): ?>
            <form method="post" action="/sites/<?= $sid ?>/unsuspend">
              <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
              <button type="submit" class="secondary">Возобновить</button>
            </form>
          <?php else: ?>
            <a class="btn secondary" href="https://<?= Html::e($site['domain']) ?>" target="_blank" rel="noopener">Сайт</a>
          <?php endif; ?>

          <form method="post" action="/sites/<?= $sid ?>/delete"
                data-confirm="Удалить сайт <?= Html::e($site['domain']) ?> вместе со всеми файлами? Это необратимо.">
            <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
            <button type="submit" class="danger">Удалить</button>
          </form>
        </div>
      </div>
    <?php endforeach; ?>
  </div>
<?php endif; ?>
