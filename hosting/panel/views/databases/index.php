<?php
/** @var string $csrf
 *  @var list<array<string,mixed>> $databases
 *  @var array<string,mixed> $user
 *  @var string $rootDomain
 */
use Hosting\Support\Html;
?>
<div class="card">
  <h2>Новая база данных</h2>
  <form method="post" action="/databases" style="display:flex;gap:10px;align-items:end;flex-wrap:wrap;">
    <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
    <div style="flex:1;min-width:200px;">
      <label>Имя (без префикса)</label>
      <input type="text" name="name" placeholder="shop" required pattern="[a-z][a-z0-9_]{1,24}">
    </div>
    <button type="submit">Создать</button>
  </form>
  <p class="muted">Баз: <?= count($databases) ?> / <?= Html::e($user['max_databases']) ?> по тарифу.
     Полное имя будет: <code><?= Html::e($user['system_user']) ?>_имя</code></p>
</div>

<div class="card">
  <h2>Мои базы данных</h2>
  <?php if ($databases === []): ?>
    <p class="muted">Пока нет ни одной базы.</p>
  <?php else: ?>
  <table>
    <thead><tr><th>База</th><th>Статус</th><th></th></tr></thead>
    <tbody>
    <?php foreach ($databases as $database): ?>
      <tr>
        <td><code><?= Html::e($database['db_name']) ?></code></td>
        <td><span class="badge <?= Html::e($database['status']) ?>"><?= Html::e($database['status']) ?></span></td>
        <td>
          <form method="post" action="/databases/<?= (int) $database['id'] ?>/delete" style="display:inline;"
                onsubmit="return confirm('Удалить базу безвозвратно?');">
            <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
            <button type="submit" class="danger">Удалить</button>
          </form>
        </td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table>
  <?php endif; ?>
  <p class="muted" style="margin-top:16px;">
    Управлять таблицами удобнее через <a href="https://db.<?= Html::e($rootDomain) ?>" target="_blank" rel="noopener">phpMyAdmin</a> —
    войдите именем <code><?= Html::e($user['system_user']) ?></code> и паролем, который вы получили при создании базы.
  </p>
</div>
