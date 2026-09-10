<?php
/** @var string $csrf
 *  @var list<array{code:string,title:string,price_tjs:float,disk_quota_mb:int,max_sites:int}> $plans
 */
use Hosting\Support\Html;
?>
<div class="card" style="max-width:420px;margin:40px auto;">
  <h2>Регистрация</h2>
  <form method="post" action="/register">
    <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
    <label>E-mail</label>
    <input type="email" name="email" required autofocus>
    <label>Пароль (минимум 8 символов)</label>
    <input type="password" name="password" required minlength="8">
    <label>Тариф</label>
    <select name="plan">
      <?php foreach ($plans as $plan): ?>
        <option value="<?= Html::e($plan['code']) ?>">
          <?= Html::e($plan['title']) ?> — <?= Html::e($plan['price_tjs']) ?> TJS/мес
          (<?= Html::e($plan['disk_quota_mb']) ?> МБ, <?= Html::e($plan['max_sites']) ?> сайт(ов))
        </option>
      <?php endforeach; ?>
    </select>
    <div style="margin-top:16px;"><button type="submit">Создать аккаунт</button></div>
  </form>
  <p class="muted" style="margin-top:16px;">Уже есть аккаунт? <a href="/login">Войти</a></p>
</div>
