<?php
/** @var string $csrf
 *  @var list<array<string,mixed>> $users
 *  @var list<array<string,mixed>> $sites
 *  @var list<array<string,mixed>> $auditLog
 *  @var int $pendingJobs
 *  @var list<array<string,mixed>> $requests
 */
use Hosting\Service\Billing;
use Hosting\Support\Html;

$statusText = [
    'active'         => 'Активен',
    'grace'          => 'Льготный период',
    'suspended'      => 'Приостановлен',
    'pending_delete' => 'На удаление',
];
?>
<style>
  /* Никаких широких таблиц: владелец хостинга заходит сюда и с телефона. */
  .ad-list { display:grid; gap:10px; }
  .ad-item { display:grid; gap:10px; padding:14px; background:var(--surface-2);
             border:1px solid var(--border); border-radius:var(--r-md); }
  .ad-top { display:flex; align-items:center; justify-content:space-between; gap:10px; flex-wrap:wrap; }
  .ad-who { min-width:0; }
  .ad-who b { display:block; word-break:break-word; }
  .ad-acts { display:flex; gap:8px; flex-wrap:wrap; }
  .ad-acts form { display:contents; }
  .ad-acts button { padding:8px 14px; font-size:14px; }
  .ad-credit { display:flex; gap:8px; flex-wrap:wrap; }
  .ad-credit input { min-width:0; }
  .ad-credit input[name=amount] { flex:0 1 110px; }
  .ad-credit input[name=comment] { flex:1 1 140px; }
  .ad-log { display:grid; gap:6px; }
  .ad-log div { display:flex; gap:8px; flex-wrap:wrap; align-items:baseline;
                padding:8px 10px; background:var(--surface-2); border-radius:9px; font-size:13.5px; }
</style>

<div class="tiles">
  <div class="tile"><b><?= count($users) ?></b><span>Клиентов</span></div>
  <div class="tile"><b><?= count($sites) ?></b><span>Активных сайтов</span></div>
  <div class="tile"><b><?= (int) $pendingJobs ?></b><span>Заданий в очереди</span></div>
  <div class="tile"><b><?= count($requests) ?></b><span>Заявок на оплату</span></div>
</div>

<div class="card" style="margin-top:16px;">
  <h2 style="margin-top:0;">Заявки на пополнение</h2>
  <?php if ($requests === []): ?>
    <p class="muted" style="margin:0;">Новых заявок нет.</p>
  <?php else: ?>
    <p class="muted" style="margin-top:0;">
      Нажимайте «Зачислить» только после того, как увидели перевод: панель деньги не принимает,
      она лишь записывает их на баланс.
    </p>
    <div class="ad-list">
      <?php foreach ($requests as $r): ?>
        <div class="ad-item">
          <div class="ad-top">
            <span class="ad-who">
              <b><?= Html::e(Billing::money((float) $r['amount_tjs'])) ?></b>
              <span class="muted">
                <?= Html::e($r['display_name'] ?: $r['email'] ?: $r['system_user']) ?>
                · <?= Html::e(date('d.m.Y H:i', strtotime((string) $r['created_at']))) ?>
              </span>
            </span>
            <span class="badge pending">Ожидает</span>
          </div>
          <div class="ad-acts">
            <form method="post" action="/admin/payments/<?= (int) $r['id'] ?>/approve"
                  data-confirm="Зачислить <?= Html::e(Billing::money((float) $r['amount_tjs'])) ?> на баланс? Деньги должны быть уже получены.">
              <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
              <button type="submit">Зачислить</button>
            </form>
            <form method="post" action="/admin/payments/<?= (int) $r['id'] ?>/reject"
                  data-confirm="Отклонить заявку?">
              <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
              <button type="submit" class="secondary">Отклонить</button>
            </form>
          </div>
        </div>
      <?php endforeach; ?>
    </div>
  <?php endif; ?>
</div>

<div class="card">
  <h2 style="margin-top:0;">Клиенты</h2>
  <div class="ad-list">
    <?php foreach ($users as $u): $uid = (int) $u['id']; ?>
      <div class="ad-item">
        <div class="ad-top">
          <span class="ad-who">
            <b><?= Html::e($u['display_name'] ?: $u['email'] ?: $u['system_user']) ?></b>
            <span class="muted">
              <?= Html::e($u['system_user']) ?> · тариф #<?= (int) $u['plan_id'] ?>
              · баланс <?= Html::e(Billing::money((float) ($u['balance_tjs'] ?? 0))) ?>
            </span>
          </span>
          <span class="badge <?= $u['status'] === 'active' ? 'active' : 'suspended' ?>">
            <?= Html::e($statusText[$u['status']] ?? $u['status']) ?>
          </span>
        </div>

        <form method="post" action="/admin/users/<?= $uid ?>/credit" class="ad-credit">
          <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
          <input type="number" name="amount" min="0.01" max="100000" step="0.01" placeholder="25" required>
          <input type="text" name="comment" maxlength="120" placeholder="за что (необязательно)">
          <button type="submit" class="secondary">Пополнить</button>
        </form>

        <div class="ad-acts">
          <?php if ($u['status'] === 'active'): ?>
            <form method="post" action="/admin/users/<?= $uid ?>/suspend"
                  data-confirm="Приостановить клиента? Его сайты перестанут открываться.">
              <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
              <button type="submit" class="danger">Приостановить</button>
            </form>
          <?php else: ?>
            <form method="post" action="/admin/users/<?= $uid ?>/activate">
              <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
              <button type="submit" class="secondary">Возобновить</button>
            </form>
          <?php endif; ?>
        </div>
      </div>
    <?php endforeach; ?>
  </div>
</div>

<div class="card">
  <h2 style="margin-top:0;">Журнал действий (последние 50)</h2>
  <div class="ad-log">
    <?php foreach ($auditLog as $row): ?>
      <div>
        <span class="muted"><?= Html::e($row['created_at']) ?></span>
        <b><?= Html::e($row['actor']) ?></b>
        <span><?= Html::e($row['action']) ?></span>
        <span class="muted"><?= Html::e($row['object_type']) ?> #<?= Html::e($row['object_id']) ?></span>
        <span class="badge <?= $row['result'] === 'success' ? 'active' : 'suspended' ?>"><?= Html::e($row['result']) ?></span>
      </div>
    <?php endforeach; ?>
    <?php if ($auditLog === []): ?>
      <p class="muted" style="margin:0;">Записей пока нет.</p>
    <?php endif; ?>
  </div>
</div>
