<div class="card" style="max-width:420px;margin:40px auto;text-align:center;">
  <h2 style="margin-top:0;">Вход через Telegram</h2>
  <p class="muted" data-tg-status>Подождите, идёт проверка…</p>
  <form id="tg-form" method="post" action="/telegram/callback">
    <input type="hidden" name="init_data" id="tg-init-data">
    <input type="hidden" name="plan" value="start">
  </form>
  <noscript><p>Откройте эту страницу внутри Telegram — без JavaScript вход недоступен.</p></noscript>
</div>
<script src="/assets/telegram-login.js"></script>
