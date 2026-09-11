<?php
/** @var string $csrf
 *  @var list<array<string,mixed>> $databases
 *  @var array<string,mixed> $user
 *  @var string $rootDomain
 *  @var string $dbUser
 *  @var string|null $freshPassword
 */
use Hosting\Support\Html;

$pma = 'https://db.' . $rootDomain;
?>
<style>
  .db-cred { display:grid; gap:10px; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); }
  .db-cred div { background:var(--surface-2); border:1px solid var(--border);
                 border-radius:var(--r-md); padding:12px 14px; }
  .db-cred dt { font-size:12.5px; color:var(--muted); font-weight:600;
                text-transform:uppercase; letter-spacing:.05em; }
  .db-cred dd { margin:5px 0 0; font-family:ui-monospace,monospace; font-size:14px; word-break:break-all; }
  .db-pass { border:2px solid var(--success); background:var(--success-soft);
             border-radius:var(--r-lg); padding:18px; margin-bottom:18px; }
  .db-pass h3 { margin:0 0 8px; color:#14532D; }
  .db-pass code { display:block; background:#fff; border:1px solid #BBE9CD; padding:12px 14px;
                  border-radius:var(--r-md); font-size:16px; word-break:break-all; user-select:all; }
  .db-list { display:grid; gap:12px; }
  .db-item { display:flex; flex-wrap:wrap; align-items:center; gap:10px; padding:14px;
             background:var(--surface-2); border:1px solid var(--border); border-radius:var(--r-md); }
  .db-item .db-name { flex:1 1 auto; font-family:ui-monospace,monospace; font-weight:600; word-break:break-all; }
  .db-new { display:flex; gap:10px; align-items:flex-end; flex-wrap:wrap; }
  .db-new > div { flex:1 1 200px; }
  @media (max-width:640px) {
    .db-item .btn, .db-item button { width:100%; }
    .db-item form { flex:1 1 100%; }
  }
</style>

<?php if ($freshPassword !== null): ?>
  <div class="db-pass">
    <h3>Сохраните пароль — он показывается один раз</h3>
    <code><?= Html::e($freshPassword) ?></code>
    <p class="muted" style="margin:10px 0 0;color:#14532D;">
      Мы его не храним: ни в панели, ни в логах. Потеряете — нажмите «Сменить пароль»,
      но тогда придётся обновить его во всех сайтах.
    </p>
  </div>
<?php endif; ?>

<div class="card">
  <h2 style="margin-top:0;">Данные для подключения</h2>
  <p class="muted" style="margin-top:0;">
    Учётная запись MariaDB у вас одна на все базы — логин и пароль везде одинаковые.
  </p>
  <div class="db-cred">
    <div><dt>Логин</dt><dd><?= Html::e($dbUser) ?></dd></div>
    <div><dt>Пароль</dt><dd><?= $freshPassword !== null ? 'показан выше' : 'показан при создании' ?></dd></div>
    <div><dt>Хост</dt><dd>localhost или 127.0.0.1</dd></div>
    <div><dt>Порт</dt><dd>3306</dd></div>
  </div>
  <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:16px;">
    <a class="btn" href="<?= Html::e($pma) ?>" target="_blank" rel="noopener">Открыть phpMyAdmin</a>
    <form method="post" action="/databases/password"
          data-confirm="Сменить пароль? Старый перестанет работать, и его придётся обновить во всех сайтах.">
      <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
      <button type="submit" class="secondary">Сменить пароль</button>
    </form>
  </div>
</div>

<div class="card">
  <h2 style="margin-top:0;">Новая база данных</h2>
  <form method="post" action="/databases" class="db-new">
    <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
    <div>
      <label>Имя базы</label>
      <input type="text" name="name" placeholder="shop" required pattern="[a-z][a-z0-9_]{1,24}">
      <div class="muted" style="margin-top:6px;">Полное имя: <code><?= Html::e($user['system_user']) ?>_имя</code></div>
    </div>
    <button type="submit">Создать базу</button>
  </form>
  <p class="muted" style="margin-bottom:0;">Баз: <?= count($databases) ?> из <?= Html::e($user['max_databases']) ?> по тарифу</p>
</div>

<div class="card">
  <h2 style="margin-top:0;">Мои базы</h2>
  <?php if ($databases === []): ?>
    <p class="muted" style="margin:0;">Пока нет ни одной базы. Создайте первую — логин и пароль выдадутся сразу.</p>
  <?php else: ?>
    <div class="db-list">
      <?php foreach ($databases as $database): ?>
        <div class="db-item">
          <span class="db-name"><?= Html::e($database['db_name']) ?></span>
          <span class="badge <?= $database['status'] === 'active' ? 'active' : 'pending' ?>">
            <?= Html::e($database['status'] === 'active' ? 'Готова' : 'Создаётся') ?>
          </span>
          <form method="post" action="/databases/<?= (int) $database['id'] ?>/delete"
                data-confirm="Удалить базу <?= Html::e($database['db_name']) ?> со всеми таблицами? Это необратимо.">
            <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
            <button type="submit" class="danger">Удалить</button>
          </form>
        </div>
      <?php endforeach; ?>
    </div>
  <?php endif; ?>
</div>

<div class="card">
  <h2 style="margin-top:0;">Как подключиться из сайта</h2>
  <pre><?= Html::e('<?php
$pdo = new PDO(
    "mysql:host=127.0.0.1;dbname=' . ($databases[0]['db_name'] ?? ($user['system_user'] . '_shop')) . ';charset=utf8mb4",
    "' . $dbUser . '",
    "ваш пароль"
);') ?></pre>
  <p class="muted" style="margin-bottom:0;">
    Пароль лучше держать в файле <code>.env</code> над <code>public/</code> — из браузера он недоступен.
  </p>
</div>
