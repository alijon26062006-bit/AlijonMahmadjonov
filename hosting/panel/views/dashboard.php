<?php
/** @var array<string,mixed> $user
 *  @var list<array<string,mixed>> $sites
 *  @var array<string,mixed>|null $plan
 *  @var array{balance:float,ends_at:?string,days_left:?int,status:?string} $summary
 *  @var int $databaseCount
 */
use Hosting\Service\Billing;
use Hosting\Support\Html;
use Hosting\Support\Path;

$ico = static function (string $d): string {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"
                 stroke-linecap="round" stroke-linejoin="round">' . $d . '</svg>';
};
$icons = [
    'site'   => '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>',
    'check'  => '<circle cx="12" cy="12" r="9"/><path d="m8.5 12.5 2.5 2.5 4.5-5"/>',
    'money'  => '<path d="M12 3v18"/><path d="M16.5 7.5c0-1.7-2-2.5-4.5-2.5s-4.5.8-4.5 2.5S9.5 11 12 11s4.5 1.3 4.5 3-2 3-4.5 3-4.5-1.3-4.5-3"/>',
    'cal'    => '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 11h18"/>',
    'files'  => '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"/>',
    'db'     => '<ellipse cx="12" cy="6" rx="8" ry="3"/><path d="M4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6"/><path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    'domain' => '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3a15 15 0 0 1 0 18a15 15 0 0 1 0-18Z"/>',
    'backup' => '<path d="M4 12a8 8 0 1 0 3-6.2"/><path d="M3 4v5h5"/>',
    'plus'   => '<path d="M12 5v14M5 12h14"/>',
    'user'   => '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
];
$firstSite = $sites[0] ?? null;
$daysLeft = $summary['days_left'];
?>
<div class="tiles">
  <div class="tile">
    <span class="tile-ico t-blue"><?= $ico($icons['site']) ?></span>
    <b><?= count($sites) ?></b><span>Сайтов</span>
  </div>
  <div class="tile">
    <span class="tile-ico t-green"><?= $ico($icons['db']) ?></span>
    <b><?= (int) $databaseCount ?></b><span>Баз данных</span>
  </div>
  <div class="tile">
    <span class="tile-ico t-orange"><?= $ico($icons['money']) ?></span>
    <b><?= Html::e(number_format($summary['balance'], 2, '.', ' ')) ?></b>
    <span>Баланс, TJS</span>
  </div>
  <div class="tile">
    <span class="tile-ico t-green"><?= $ico($icons['cal']) ?></span>
    <b><?= $daysLeft === null ? '∞' : (int) $daysLeft ?></b><span>Осталось дней</span>
  </div>
</div>

<div class="tiles" style="margin-top:12px;">
  <a class="tile is-action" href="/sites"><span class="tile-ico t-blue"><?= $ico($icons['site']) ?></span><b>Мои сайты</b></a>
  <a class="tile is-action" href="<?= $firstSite !== null ? '/sites/' . (int) $firstSite['id'] . '/files' : '/sites' ?>">
    <span class="tile-ico t-orange"><?= $ico($icons['files']) ?></span><b>Файлы</b></a>
  <a class="tile is-action" href="<?= $firstSite !== null ? '/sites/' . (int) $firstSite['id'] . '/domains' : '/sites' ?>">
    <span class="tile-ico t-blue"><?= $ico($icons['domain']) ?></span><b>Домены</b></a>
  <a class="tile is-action" href="/databases"><span class="tile-ico t-orange"><?= $ico($icons['db']) ?></span><b>Базы данных</b></a>
  <a class="tile is-action" href="/backups"><span class="tile-ico t-purple"><?= $ico($icons['backup']) ?></span><b>Бэкапы</b></a>
  <a class="tile is-action" href="/billing"><span class="tile-ico t-green"><?= $ico($icons['plus']) ?></span><b>Пополнить</b></a>
  <a class="tile is-action" href="/billing"><span class="tile-ico t-purple"><?= $ico($icons['money']) ?></span><b>Платежи</b></a>
  <a class="tile is-action" href="/profile"><span class="tile-ico t-green"><?= $ico($icons['user']) ?></span><b>Профиль</b></a>
</div>

<?php if ($plan !== null): ?>
  <div class="card" style="margin-top:16px;">
    <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:14px;">
      <span class="tile-ico t-blue" style="width:44px;height:44px;">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9"
             stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2"/>
        </svg>
      </span>
      <span style="flex:1 1 auto;">
        <b style="font-size:18px;"><?= Html::e($plan['title']) ?></b><br>
        <span class="muted"><?= Html::e(round((int) $user['disk_quota_mb'] / 1024, 1)) ?> ГБ ·
          <?= (int) $user['max_sites'] ?> <?= Html::plural((int) $user['max_sites'], 'сайт', 'сайта', 'сайтов') ?> ·
          <?= Html::e(Billing::money((float) $plan['price_tjs'])) ?>/мес</span>
      </span>
      <span class="badge active">Активен</span>
    </div>

    <?php if ($summary['ends_at'] !== null): ?>
      <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;">
        <span class="muted">Действует до <b><?= Html::e(date('d.m.Y', strtotime((string) $summary['ends_at']))) ?></b></span>
        <span class="<?= ($daysLeft ?? 99) <= 7 ? 'badge suspended' : 'badge active' ?>">
          <?= $daysLeft !== null ? (int) $daysLeft . ' ' . Html::plural((int) $daysLeft, 'день', 'дня', 'дней') . ' осталось' : 'без срока' ?>
        </span>
      </div>
    <?php else: ?>
      <p class="muted" style="margin:0;">Срок действия не задан — тариф не отключится автоматически.</p>
    <?php endif; ?>
  </div>
<?php endif; ?>

<?php if ($sites === []): ?>
  <div class="card" style="margin-top:16px;text-align:center;">
    <h2 style="margin-top:0;">Создайте первый сайт</h2>
    <p class="muted">Адрес выдаётся сразу, файлы и база — из панели. Займёт минуту.</p>
    <a class="btn" href="/sites">Создать сайт</a>
  </div>
<?php endif; ?>
