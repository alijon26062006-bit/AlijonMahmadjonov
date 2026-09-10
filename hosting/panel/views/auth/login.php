<?php
/** @var string $csrf */
use Hosting\Support\Html;
?>
<div class="card" style="max-width:400px;margin:40px auto;">
  <h2>Вход</h2>
  <form method="post" action="/login">
    <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
    <label>E-mail</label>
    <input type="email" name="email" required autofocus>
    <label>Пароль</label>
    <input type="password" name="password" required>
    <div style="margin-top:16px;"><button type="submit">Войти</button></div>
  </form>
  <p class="muted" style="margin-top:16px;">Нет аккаунта? <a href="/register">Зарегистрироваться</a></p>
  <p class="muted">Открыли из Telegram? <a href="/telegram">Войти через Telegram</a></p>
</div>
