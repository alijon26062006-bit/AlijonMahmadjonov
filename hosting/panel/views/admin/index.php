<?php
/** @var string $csrf
 *  @var list<array<string,mixed>> $users
 *  @var list<array<string,mixed>> $sites
 *  @var list<array<string,mixed>> $auditLog
 *  @var int $pendingJobs
 */
use Hosting\Support\Html;
?>
<div class="card">
  <h2>Обзор</h2>
  <p>Клиентов: <?= count($users) ?> · Активных сайтов: <?= count($sites) ?> · В очереди заданий: <?= $pendingJobs ?></p>
</div>

<div class="card">
  <h2>Клиенты</h2>
  <table>
    <thead><tr><th>Клиент</th><th>Тариф</th><th>Статус</th><th></th></tr></thead>
    <tbody>
    <?php foreach ($users as $u): ?>
      <tr>
        <td><?= Html::e($u['display_name'] ?: $u['email']) ?><br><span class="muted"><?= Html::e($u['system_user']) ?></span></td>
        <td><?= Html::e($u['plan_id']) ?></td>
        <td><span class="badge <?= $u['status'] === 'active' ? 'active' : 'suspended' ?>"><?= Html::e($u['status']) ?></span></td>
        <td>
          <?php if ($u['status'] === 'active'): ?>
            <form method="post" action="/admin/users/<?= (int) $u['id'] ?>/suspend" style="display:inline;">
              <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
              <button type="submit" class="danger">Приостановить</button>
            </form>
          <?php else: ?>
            <form method="post" action="/admin/users/<?= (int) $u['id'] ?>/activate" style="display:inline;">
              <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
              <button type="submit" class="secondary">Возобновить</button>
            </form>
          <?php endif; ?>
        </td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table>
</div>

<div class="card">
  <h2>Журнал действий (последние 50)</h2>
  <table>
    <thead><tr><th>Когда</th><th>Кто</th><th>Действие</th><th>Объект</th><th>Результат</th></tr></thead>
    <tbody>
    <?php foreach ($auditLog as $row): ?>
      <tr>
        <td class="muted"><?= Html::e($row['created_at']) ?></td>
        <td><?= Html::e($row['actor']) ?></td>
        <td><?= Html::e($row['action']) ?></td>
        <td class="muted"><?= Html::e($row['object_type']) ?> #<?= Html::e($row['object_id']) ?></td>
        <td><span class="badge <?= $row['result'] === 'success' ? 'active' : 'suspended' ?>"><?= Html::e($row['result']) ?></span></td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table>
</div>
