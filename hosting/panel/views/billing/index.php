<?php
/** @var string $csrf
 *  @var array<string,mixed> $user
 *  @var array{balance:float,ends_at:?string,days_left:?int,status:?string} $summary
 *  @var list<array<string,mixed>> $payments
 *  @var string $details
 */
use Hosting\Service\Billing;
use Hosting\Support\Html;

$statusText = ['paid' => 'Зачислено', 'pending' => 'Ожидает подтверждения', 'failed' => 'Отклонено', 'refunded' => 'Возврат'];
?>
<div class="tiles">
  <div class="tile">
    <span class="tile-ico t-orange">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><path d="M12 3v18"/><path d="M16.5 7.5c0-1.7-2-2.5-4.5-2.5s-4.5.8-4.5 2.5S9.5 11 12 11s4.5 1.3 4.5 3-2 3-4.5 3-4.5-1.3-4.5-3"/></svg>
    </span>
    <b><?= Html::e(number_format($summary['balance'], 2, '.', ' ')) ?></b>
    <span>Баланс, TJS</span>
  </div>
  <div class="tile">
    <span class="tile-ico t-green">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 11h18"/></svg>
    </span>
    <b><?= $summary['days_left'] === null ? '∞' : (int) $summary['days_left'] ?></b>
    <span>Осталось дней</span>
  </div>
</div>

<div class="card" style="margin-top:16px;">
  <h2 style="margin-top:0;">Пополнить баланс</h2>
  <form method="post" action="/billing/topup" style="display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap;">
    <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
    <div style="flex:1 1 180px;">
      <label>Сумма, TJS</label>
      <input type="number" name="amount" min="1" max="100000" step="1" placeholder="25" required>
    </div>
    <button type="submit">Создать заявку</button>
  </form>

  <div style="margin-top:16px;padding:14px 16px;background:var(--warning-soft);border:1px solid #F6D9B0;border-radius:var(--r-md);">
    <b style="color:#9A3412;">Как это работает</b>
    <p class="muted" style="margin:6px 0 0;color:#9A3412;">
      Автоматической оплаты картой пока нет. Создайте заявку, переведите сумму по реквизитам
      ниже и напишите в поддержку — администратор зачислит деньги на баланс.
    </p>
  </div>

  <?php if (trim($details) !== ''): ?>
    <div style="margin-top:14px;">
      <span class="field-label">Реквизиты для перевода</span>
      <pre style="margin:6px 0 0;white-space:pre-wrap;word-break:break-word;overflow-x:visible;"><?= Html::e($details) ?></pre>
    </div>
  <?php else: ?>
    <p class="muted" style="margin-top:14px;">
      Реквизиты не заданы. Администратор задаёт их в <code>PAYMENT_DETAILS</code> в файле настроек.
    </p>
  <?php endif; ?>
</div>

<div class="card">
  <h2 style="margin-top:0;">История</h2>
  <?php if ($payments === []): ?>
    <p class="muted" style="margin:0;">Движений по счёту ещё не было.</p>
  <?php else: ?>
    <div style="display:grid;gap:8px;">
      <?php foreach ($payments as $p): ?>
        <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;
                    padding:12px 14px;background:var(--surface-2);border-radius:var(--r-md);">
          <span style="min-width:0;">
            <b><?= Html::e(Billing::money((float) $p['amount_tjs'])) ?></b><br>
            <span class="muted"><?= Html::e(date('d.m.Y H:i', strtotime((string) $p['created_at']))) ?></span>
          </span>
          <span style="flex:0 0 auto;" class="badge <?= $p['status'] === 'paid' ? 'active' : ($p['status'] === 'pending' ? 'pending' : 'suspended') ?>">
            <?= Html::e($statusText[$p['status']] ?? $p['status']) ?>
          </span>
        </div>
      <?php endforeach; ?>
    </div>
  <?php endif; ?>
</div>
