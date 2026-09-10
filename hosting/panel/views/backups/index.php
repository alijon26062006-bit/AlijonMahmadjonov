<?php
/** @var string $csrf
 *  @var list<array<string,mixed>> $backups
 */
use Hosting\Support\Html;
use Hosting\Support\Path;
$statusLabel = ['pending' => 'создаётся', 'success' => 'готова', 'failed' => 'ошибка'];
?>
<div class="card">
  <h2>Резервные копии</h2>
  <p class="muted">Автоматически создаются каждую ночь. Можно также создать копию вручную.</p>
  <form method="post" action="/backups">
    <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
    <button type="submit">Создать копию сейчас</button>
  </form>
</div>

<div class="card">
  <?php if ($backups === []): ?>
    <p class="muted">Резервных копий пока нет.</p>
  <?php else: ?>
  <table>
    <thead><tr><th>Когда</th><th>Тип</th><th>Размер</th><th>Статус</th><th></th></tr></thead>
    <tbody>
    <?php foreach ($backups as $backup): ?>
      <tr>
        <td><?= Html::e($backup['created_at']) ?></td>
        <td><?= Html::e($backup['type']) ?></td>
        <td class="muted"><?= $backup['size_bytes'] ? Html::e(Path::humanSize($backup['size_bytes'])) : '—' ?></td>
        <td><span class="badge <?= $backup['status'] === 'success' ? 'active' : ($backup['status'] === 'failed' ? 'suspended' : 'pending') ?>">
          <?= Html::e($statusLabel[$backup['status']] ?? $backup['status']) ?></span></td>
        <td>
          <?php if ($backup['status'] === 'success'): ?>
            <form method="post" action="/backups/<?= (int) $backup['id'] ?>/restore" style="display:inline;"
                  onsubmit="return confirm('Восстановить из этой копии? Текущие файлы и базы будут заменены.');">
              <input type="hidden" name="csrf" value="<?= Html::e($csrf) ?>">
              <button type="submit" class="secondary">Восстановить</button>
            </form>
          <?php endif; ?>
        </td>
      </tr>
    <?php endforeach; ?>
    </tbody>
  </table>
  <?php endif; ?>
</div>
