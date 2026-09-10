<?php
/** @var array<string,mixed> $user
 *  @var array<string,mixed>|null $plan
 *  @var array{used:int,limit:int,percent:int,exceeded:bool} $quota
 *  @var list<array<string,mixed>> $sites
 *  @var list<array<string,mixed>> $databases
 *  @var list<array<string,mixed>> $recentJobs
 *  @var array<string,mixed>|null $lastBackup
 *  @var list<array<string,mixed>> $notifications
 */
use Hosting\Support\Html;
use Hosting\Support\Path;

$jobStatusLabel = ['pending' => 'в очереди', 'running' => 'выполняется', 'success' => 'готово', 'failed' => 'ошибка'];
?>
<div class="card">
  <h2>Тариф: <?= Html::e($plan['title'] ?? '—') ?></h2>
  <p class="muted">Статус аккаунта: <span class="badge <?= $user['status'] === 'active' ? 'active' : 'pending' ?>"><?= Html::e($user['status']) ?></span></p>
  <p>Диск: <?= Html::e(Path::humanSize($quota['used'])) ?> / <?= Html::e(Path::humanSize($quota['limit'])) ?> (<?= $quota['percent'] ?>%)</p>
  <p>Сайты: <?= count($sites) ?> / <?= Html::e($user['max_sites']) ?> · Базы данных: <?= count($databases) ?> / <?= Html::e($user['max_databases']) ?></p>
  <p class="muted">
    Последняя резервная копия:
    <?= $lastBackup ? Html::e($lastBackup['created_at']) : 'ещё не создавалась' ?>
  </p>
</div>

<?php if ($notifications !== []): ?>
<div class="card">
  <h2>Уведомления</h2>
  <?php foreach ($notifications as $n): ?>
    <div style="margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid var(--border);">
      <strong><?= Html::e($n['title']) ?></strong>
      <div class="muted" style="white-space:pre-wrap;"><?= Html::e($n['body']) ?></div>
    </div>
  <?php endforeach; ?>
</div>
<?php endif; ?>

<div class="card">
  <h2>Последние операции</h2>
  <?php if ($recentJobs === []): ?>
    <p class="muted">Пока ничего не выполнялось.</p>
  <?php else: ?>
  <table>
    <thead><tr><th>Задание</th><th>Статус</th><th>Когда</th></tr></thead>
    <tbody>
    <?php foreach ($recentJobs as $job): ?>
      <tr>
        <td><?= Html::e($job['type']) ?></td>
        <td><span class="badge <?= $job['status'] === 'success' ? 'active' : ($job['status'] === 'failed' ? 'suspended' : 'pending') ?>">
          <?= Html::e($jobStatusLabel[$job['status']] ?? $job['status']) ?></span></td>
        <td class="muted"><?= Html::e($job['created_at']) ?></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table>
  <?php endif; ?>
</div>
