<?php
/** @var string $csrf
 *  @var list<array<string,mixed>> $sites
 *  @var array<string,mixed> $user
 *  @var string $rootDomain
 *  @var array<string,mixed>|null $plan
 *  @var array{used:int,limit:int,percent:int,exceeded:bool} $quota
 *  @var array{balance:float,ends_at:?string,days_left:?int,status:?string} $summary
 */
use Hosting\Support\Html;
use Hosting\Support\Path;

$statusText = [
    'pending'   => 'Создаётся',
    'active'    => 'Активен',
    'suspended' => 'Приостановлен',
    'error'     => 'Ошибка',
    'deleted'   => 'Удалён',
];
$statusClass = ['active' => 'active', 'pending' => 'pending'];

// Лимит считаем по тем же статусам, что и SiteController::create, иначе кнопка
// будет доступна, а сервер ответит отказом — худший вид интерфейса.
$activeCount = 0;
foreach ($sites as $s) {
    if (($s['status'] ?? '') !== 'deleted') {
        $activeCount++;
    }
}
$maxSites = (int) $user['max_sites'];
$limitReached = $activeCount >= $maxSites;
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

<?php if ($sites !== []): ?>
  <?php $first = $sites[0]; $sid = (int) $first['id']; ?>
  <div class="card" style="background:linear-gradient(135deg,#2563EB,#1D4ED8);border:0;color:#fff;">
    <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px;">
      <span style="font-size:12.5px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;opacity:.85;">Ваши сайты</span>
      <span style="padding:4px 12px;border-radius:999px;background:rgba(255,255,255,.18);font-size:13px;font-weight:700;">
        <?= $activeCount ?>/<?= $maxSites ?>
      </span>
    </div>
    <div style="display:flex;align-items:center;gap:9px;margin-bottom:6px;">
      <span style="width:9px;height:9px;border-radius:50%;background:<?= $first['status'] === 'active' ? '#4ADE80' : '#FBBF24' ?>;"></span>
      <b style="font-size:19px;word-break:break-all;"><?= Html::e($first['domain']) ?></b>
    </div>
    <div style="opacity:.8;font-size:13.5px;margin-bottom:16px;">
      PHP <?= Html::e($first['php_version']) ?> · Nginx<?= $first['status'] === 'active' ? ' · SSL' : '' ?>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;">
      <a class="btn" style="background:rgba(255,255,255,.16);color:#fff;border:1px solid rgba(255,255,255,.3);"
         href="https://<?= Html::e($first['domain']) ?>" target="_blank" rel="noopener">Открыть</a>
      <a class="btn" style="background:rgba(255,255,255,.16);color:#fff;border:1px solid rgba(255,255,255,.3);"
         href="/sites/<?= $sid ?>/files">Файлы</a>
      <a class="btn" style="background:rgba(255,255,255,.16);color:#fff;border:1px solid rgba(255,255,255,.3);"
         href="/sites/<?= $sid ?>">Управление</a>
    </div>
  </div>
<?php endif; ?>

<?php if ($plan !== null): ?>
  <?php
    $usedMb = (int) round($quota['used'] / 1048576);
    $limitMb = max(1, (int) $user['disk_quota_mb']);
    $percent = min(100, (int) round($usedMb / $limitMb * 100));
  ?>
  <div class="card">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px;">
      <span class="tile-ico t-blue" style="width:44px;height:44px;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/></svg>
      </span>
      <span style="flex:1 1 auto;">
        <b style="font-size:17px;"><?= Html::e($plan['title']) ?></b><br>
        <span class="muted"><?= Html::e(round($limitMb / 1024, 1)) ?> ГБ диск</span>
      </span>
      <span class="badge active">Активен</span>
    </div>

    <div style="background:var(--surface-2);border-radius:var(--r-md);padding:14px;margin-bottom:14px;">
      <div style="display:flex;justify-content:space-between;margin-bottom:8px;font-size:14px;">
        <b>Диск</b>
        <span class="muted"><?= Html::e(Path::humanSize($quota['used'])) ?> из <?= Html::e(round($limitMb / 1024, 1)) ?> ГБ</span>
      </div>
      <div class="progress"><i style="width:<?= $percent ?>%;"></i></div>
    </div>

    <div class="tiles" style="grid-template-columns:repeat(3,1fr);gap:8px;">
      <div class="tile" style="padding:14px 10px;align-items:center;text-align:center;">
        <span class="muted" style="font-size:12.5px;">Цена</span>
        <b style="font-size:20px;color:var(--primary);"><?= (int) $plan['price_tjs'] ?> <small style="font-size:12px;">TJS/мес</small></b>
      </div>
      <div class="tile" style="padding:14px 10px;align-items:center;text-align:center;">
        <span class="muted" style="font-size:12.5px;">До</span>
        <b style="font-size:15px;"><?= $summary['ends_at'] !== null ? Html::e(date('d.m.Y', strtotime((string) $summary['ends_at']))) : '—' ?></b>
      </div>
      <div class="tile" style="padding:14px 10px;align-items:center;text-align:center;">
        <span class="muted" style="font-size:12.5px;">Баланс</span>
        <b style="font-size:20px;color:<?= $summary['balance'] > 0 ? 'var(--success)' : 'var(--danger)' ?>;">
          <?= Html::e(number_format($summary['balance'], 2, '.', ' ')) ?> <small style="font-size:12px;">TJS</small></b>
      </div>
    </div>

    <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-top:14px;">
      <span style="color:var(--success);font-weight:700;">
        <?= $summary['days_left'] !== null
              ? (int) $summary['days_left'] . ' ' . Html::plural((int) $summary['days_left'], 'день', 'дня', 'дней') . ' осталось'
              : 'Срок не ограничен' ?>
      </span>
      <a class="btn secondary" href="/billing">+ Пополнить баланс</a>
    </div>
  </div>
<?php endif; ?>

<div class="card">
  <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:14px;">
    <b style="font-size:17px;">Создать новый сайт</b>
    <span class="muted"><?= $activeCount ?>/<?= $maxSites ?></span>
  </div>
  <?php if ($limitReached): ?>
    <p class="muted" style="margin:0 0 12px;">
      По тарифу<?= $plan !== null ? ' «' . Html::e($plan['title']) . '»' : '' ?>
      доступно <?= $maxSites ?> <?= Html::plural($maxSites, 'сайт', 'сайта', 'сайтов') ?>,
      и они уже созданы. Удалите ненужный сайт или перейдите на тариф побольше.
    </p>
    <a class="btn secondary" href="/billing">Сменить тариф</a>
  <?php else: ?>
    <form method="post" action="/sites">
      <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
      <div style="display:flex;margin-bottom:12px;">
        <input type="text" name="slug" placeholder="mysayt" required pattern="[a-z0-9-]{3,30}"
               style="border-radius:var(--r-md) 0 0 var(--r-md);border-right:0;">
        <span style="display:flex;align-items:center;padding:0 14px;background:var(--surface-2);
                     border:1px solid var(--border);border-radius:0 var(--r-md) var(--r-md) 0;
                     font-size:14px;color:var(--muted);white-space:nowrap;">.<?= Html::e($rootDomain) ?></span>
      </div>
      <button type="submit">+ Создать</button>
    </form>
  <?php endif; ?>
</div>

<?php if (count($sites) > 1): ?>
  <h2 style="margin:24px 0 14px;">Все сайты</h2>
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
        </div>
      </div>
    <?php endforeach; ?>
  </div>
<?php elseif ($sites === []): ?>
  <div class="card"><p class="muted" style="margin:0;">Пока нет ни одного сайта. Создайте первый — это займёт полминуты.</p></div>
<?php endif; ?>
