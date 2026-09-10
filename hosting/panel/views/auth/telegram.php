<div class="card" style="max-width:420px;margin:40px auto;text-align:center;">
  <h2>Вход через Telegram</h2>
  <p class="muted">Подождите, идёт проверка…</p>
  <form id="tg-form" method="post" action="/telegram/callback">
    <input type="hidden" name="init_data" id="tg-init-data">
    <input type="hidden" name="plan" value="start">
  </form>
  <noscript><p>Откройте эту страницу внутри Telegram — без JavaScript вход недоступен.</p></noscript>
</div>
<script>
  var tg = window.Telegram && window.Telegram.WebApp;
  if (tg && tg.initData) {
    tg.ready();
    document.getElementById('tg-init-data').value = tg.initData;
    document.getElementById('tg-form').submit();
  } else {
    document.querySelector('.muted').textContent =
      'Эта страница открывается только изнутри Telegram Mini App.';
  }
</script>
