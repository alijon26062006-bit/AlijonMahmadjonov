<?php
/** @var string $csrf
 *  @var array<string,mixed> $user
 *  @var array{balance:float,ends_at:?string,days_left:?int,status:?string} $summary
 */
use Hosting\Service\Billing;
use Hosting\Support\Html;
?>
<div class="card">
  <h2 style="margin-top:0;">Профиль</h2>
  <form method="post" action="/profile">
    <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
    <label>Имя</label>
    <input type="text" name="display_name" value="<?= Html::e($user['display_name'] ?? '') ?>" maxlength="60" placeholder="Как к вам обращаться">

    <label>E-mail</label>
    <input type="text" value="<?= Html::e($user['email'] ?? '') ?>" disabled>

    <label>Новый пароль для входа в панель</label>
    <input type="password" name="password" minlength="8" autocomplete="new-password" placeholder="оставьте пустым, чтобы не менять">
    <div class="muted" style="margin-top:6px;">Пароль от базы данных — отдельный, он на странице «Базы данных».</div>

    <div style="margin-top:16px;"><button type="submit">Сохранить</button></div>
  </form>
</div>

<div class="card">
  <h2 style="margin-top:0;">Учётная запись</h2>
  <div class="field">
    <span class="field-main"><span class="field-label">Системный пользователь</span>
      <span class="field-value"><?= Html::e($user['system_user']) ?></span></span>
  </div>
  <div class="field">
    <span class="field-main"><span class="field-label">Баланс</span>
      <span class="field-value"><?= Html::e(Billing::money((float) ($user['balance_tjs'] ?? 0))) ?></span></span>
  </div>
  <?php if ($summary['ends_at'] !== null): ?>
    <div class="field">
      <span class="field-main"><span class="field-label">Тариф действует до</span>
        <span class="field-value"><?= Html::e(date('d.m.Y', strtotime((string) $summary['ends_at']))) ?></span></span>
    </div>
  <?php endif; ?>
</div>
