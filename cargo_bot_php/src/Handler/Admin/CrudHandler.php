<?php

namespace CargoBot\Handler\Admin;

use CargoBot\Bot;
use CargoBot\Repository\Repository;
use CargoBot\Service\Audit;
use CargoBot\Telegram\Keyboard;
use CargoBot\Texts;
use CargoBot\Util\Format;

/**
 * Универсальный движок управления справочниками.
 *
 * Работает для любой сущности из Registry: список с пагинацией, карточка,
 * пошаговое добавление, правка отдельного поля, включение/отключение,
 * удаление с подтверждением. Каждое изменение пишется в журнал (logs)
 * со старыми и новыми значениями.
 *
 * Формат callback-данных:
 *   e:<ключ>:list:<стр>              список
 *   e:<ключ>:view:<id>               карточка
 *   e:<ключ>:add                     начать добавление
 *   e:<ключ>:av:<значение>           выбор значения при добавлении
 *   e:<ключ>:ef:<id>:<поле>          правка поля
 *   e:<ключ>:sv:<id>:<поле>:<знач>   сохранение выбранного значения
 *   e:<ключ>:tg:<id>                 вкл/выкл
 *   e:<ключ>:dc:<id> / dl:<id>       удаление
 */
class CrudHandler
{
    private const SKIP = '_';

    private Bot $bot;

    public function __construct(Bot $bot)
    {
        $this->bot = $bot;
    }

    public function onCallback(string $data): void
    {
        $bot = $this->bot;
        $parts = explode(':', $data);
        $key = $parts[1] ?? '';
        $action = $parts[2] ?? '';
        $entity = Registry::get($key);
        if (!$entity) {
            $bot->answer('Неизвестный раздел', true);
            return;
        }
        $repo = new Repository($bot->db, $entity['table']);

        switch ($action) {
            case 'list':
                $bot->state->clear($bot->chatId);
                [$text, $kb] = $this->renderList($key, $entity, (int) ($parts[3] ?? 1));
                $bot->edit($text, $kb);
                break;

            case 'view':
                $row = $repo->get((int) ($parts[3] ?? 0));
                if (!$row) {
                    $bot->answer('Запись не найдена', true);
                    return;
                }
                [$text, $kb] = $this->renderView($key, $entity, $row);
                $bot->edit($text, $kb);
                break;

            case 'add':
                if (($entity['can_add'] ?? true) === false) {
                    $bot->answer('В этот раздел нельзя добавлять записи', true);
                    return;
                }
                $bot->state->set($bot->chatId, 'crud:add', ['ent' => $key, 'vals' => [], 'idx' => 0]);
                $bot->send('➕ Новая запись: ' . $entity['one'], Texts::cancelMenu($bot->lang));
                $this->askField($entity, 0, $key);
                break;

            case 'av':
                $this->onAddValue($key, $entity, implode(':', array_slice($parts, 3)));
                break;

            case 'ef':
                $this->onEditField($key, $entity, (int) $parts[3], (int) $parts[4]);
                break;

            case 'sv':
                $this->onSaveValue($key, $entity, (int) $parts[3], (int) $parts[4],
                                   implode(':', array_slice($parts, 5)));
                break;

            case 'tg':
                $row = $repo->get((int) ($parts[3] ?? 0));
                if (!$row) {
                    $bot->answer('Запись не найдена', true);
                    return;
                }
                $new = ((int) $row['is_active'] === 1) ? 0 : 1;
                $repo->update((int) $row['id'], ['is_active' => $new]);
                $bot->audit->log($bot->tgId, 'toggle', $entity['table'], (int) $row['id'],
                    ['is_active' => (string) $row['is_active']], ['is_active' => (string) $new]);
                $row['is_active'] = $new;
                [$text, $kb] = $this->renderView($key, $entity, $row);
                $bot->edit($text, $kb);
                break;

            case 'dc':
                $id = (int) ($parts[3] ?? 0);
                $bot->edit('Удалить запись безвозвратно?', Keyboard::inline([
                    [['🗑 Да, удалить', "e:$key:dl:$id"], ['◀️ Отмена', "e:$key:view:$id"]],
                ]));
                break;

            case 'dl':
                $id = (int) ($parts[3] ?? 0);
                $row = $repo->get($id);
                if ($row) {
                    $repo->delete($id);
                    $bot->audit->log($bot->tgId, 'delete', $entity['table'], $id,
                                     Audit::snapshot($row), null);
                }
                [$text, $kb] = $this->renderList($key, $entity, 1);
                $bot->edit("🗑 Удалено.\n\n" . $text, $kb);
                break;
        }
        $bot->answer();
    }

    // ------------------------------------------------------------------ списки
    private function renderList(string $key, array $entity, int $page): array
    {
        $bot = $this->bot;
        $perPage = (int) ($entity['per_page'] ?? 8);
        $repo = new Repository($bot->db, $entity['table']);
        $total = $repo->count();
        $pages = max(1, (int) ceil($total / $perPage));
        $page = max(1, min($page, $pages));
        $rows = $repo->all([], $entity['order'], $perPage, ($page - 1) * $perPage);

        $buttons = [];
        foreach ($rows as $row) {
            $mark = (!empty($entity['has_active']) && (int) $row['is_active'] === 0) ? '🚫 ' : '';
            $label = $mark . Format::trunc(($entity['row'])($row));
            $buttons[] = [[$label, "e:$key:view:" . $row['id']]];
        }
        if (($entity['can_add'] ?? true) !== false) {
            $buttons[] = [['➕ Добавить', "e:$key:add"]];
        }

        $text = $entity['title'] . "\nВсего записей: " . $total;
        return [$text, Keyboard::paginate("e:$key:list", $page, $pages, $buttons)];
    }

    private function renderView(string $key, array $entity, array $row): array
    {
        $bot = $this->bot;
        $lines = ['<b>' . Format::esc($entity['one']) . '</b> #' . $row['id'], ''];
        $kb = [];
        foreach ($entity['fields'] as $i => $_) {
            $f = Registry::field($entity, $i);
            $value = $this->displayValue($f, $row[$f['name']] ?? null);
            $lines[] = '<b>' . Format::esc($f['label']) . ':</b> ' . Format::esc($value);
            $kb[] = [['✏️ ' . Format::trunc($f['label'], 34), "e:$key:ef:" . $row['id'] . ":$i"]];
        }
        if (!empty($entity['has_active'])) {
            $status = ((int) $row['is_active'] === 1) ? '✅ Активен' : '🚫 Отключён';
            $lines[] = '';
            $lines[] = '<b>Статус:</b> ' . $status;
            $kb[] = [['🔁 Включить / отключить', "e:$key:tg:" . $row['id']]];
        }
        if (($entity['can_delete'] ?? true) !== false) {
            $kb[] = [['🗑 Удалить', "e:$key:dc:" . $row['id']]];
        }
        $kb[] = [['◀️ К списку', "e:$key:list:1"]];
        return [implode("\n", $lines), Keyboard::inline($kb)];
    }

    // ------------------------------------------------------- ввод значений
    /** Спрашивает значение поля: кнопками или текстом. */
    private function askField(array $entity, int $index, string $key): void
    {
        $bot = $this->bot;
        $f = Registry::field($entity, $index);
        $total = count($entity['fields']);
        $prompt = '(' . ($index + 1) . "/$total) <b>" . Format::esc($f['label']) . '</b>';
        if ($f['hint'] !== '') {
            $prompt .= "\nℹ️ " . Format::esc($f['hint']);
        }

        $options = $this->options($f);
        if ($options !== null) {
            $rows = [];
            foreach ($options as $value => $label) {
                $rows[] = [[Format::trunc((string) $label, 34), "e:$key:av:$value"]];
            }
            if (!$f['required']) {
                $rows[] = [['⏭ Пропустить', "e:$key:av:" . self::SKIP]];
            }
            $bot->send($prompt, Keyboard::inline($rows));
        } else {
            if (!$f['required']) {
                $prompt .= "\n(Отправьте «-», чтобы пропустить)";
            }
            $bot->send($prompt);
        }
    }

    private function onAddValue(string $key, array $entity, string $raw): void
    {
        $bot = $this->bot;
        if ($bot->state->state($bot->chatId) !== 'crud:add') {
            $bot->answer('Добавление уже завершено', true);
            return;
        }
        $data = $bot->state->data($bot->chatId);
        if (($data['ent'] ?? '') !== $key) {
            $bot->answer('Добавление уже завершено', true);
            return;
        }
        $idx = (int) ($data['idx'] ?? 0);
        $f = Registry::field($entity, $idx);
        if (!$f) {
            return;
        }
        $vals = $data['vals'] ?? [];
        $vals[$f['name']] = $this->parseChoice($f, $raw);
        $this->advance($key, $entity, $vals, $idx + 1);
    }

    /** Переход к следующему полю или сохранение записи. */
    private function advance(string $key, array $entity, array $vals, int $next): void
    {
        $bot = $this->bot;
        if ($next < count($entity['fields'])) {
            $bot->state->set($bot->chatId, 'crud:add',
                ['ent' => $key, 'vals' => $vals, 'idx' => $next]);
            $this->askField($entity, $next, $key);
            return;
        }

        $bot->state->clear($bot->chatId);
        if (!empty($entity['stamp_updater'])) {
            $vals['updated_by'] = $bot->tgId;
            $vals['updated_at'] = $bot->db->now();
        }
        if (in_array('created_at', $this->columns($entity['table']), true)) {
            $vals['created_at'] = $bot->db->now();
        }
        $repo = new Repository($bot->db, $entity['table']);
        $id = $repo->insert($vals);
        $row = $repo->get($id);
        $bot->audit->log($bot->tgId, 'create', $entity['table'], $id, null, Audit::snapshot($row));

        [$text, $kb] = $this->renderView($key, $entity, $row);
        $bot->send("✅ Запись создана.\n\n" . $text, $kb);
        $bot->send('Готово.', Texts::mainMenu($bot->lang));
    }

    private function onEditField(string $key, array $entity, int $id, int $fi): void
    {
        $bot = $this->bot;
        $f = Registry::field($entity, $fi);
        if (!$f) {
            $bot->answer('Поле не найдено', true);
            return;
        }
        $options = $this->options($f);
        if ($options !== null) {
            $rows = [];
            foreach ($options as $value => $label) {
                $rows[] = [[Format::trunc((string) $label, 34), "e:$key:sv:$id:$fi:$value"]];
            }
            if (!$f['required']) {
                $rows[] = [['🚫 Очистить', "e:$key:sv:$id:$fi:" . self::SKIP]];
            }
            $rows[] = [['◀️ Назад', "e:$key:view:$id"]];
            $bot->edit('<b>' . Format::esc($f['label']) . '</b> — выберите значение:', Keyboard::inline($rows));
            return;
        }

        $bot->state->set($bot->chatId, 'crud:edit', ['ent' => $key, 'id' => $id, 'fi' => $fi]);
        $hint = $f['hint'] !== '' ? "\nℹ️ " . Format::esc($f['hint']) : '';
        $nullHint = $f['required'] ? '' : "\n(Отправьте «-», чтобы очистить)";
        $bot->send('Введите новое значение поля <b>' . Format::esc($f['label']) . "</b>:$hint$nullHint",
                   Texts::cancelMenu($bot->lang));
    }

    private function onSaveValue(string $key, array $entity, int $id, int $fi, string $raw): void
    {
        $bot = $this->bot;
        $f = Registry::field($entity, $fi);
        $repo = new Repository($bot->db, $entity['table']);
        $row = $repo->get($id);
        if (!$f || !$row) {
            $bot->answer('Запись не найдена', true);
            return;
        }
        $value = $this->parseChoice($f, $raw);
        if ($value === null && $f['required']) {
            $bot->answer('Поле обязательно', true);
            return;
        }
        $this->saveField($entity, $row, $f, $value);
        $row[$f['name']] = $value;
        [$text, $kb] = $this->renderView($key, $entity, $row);
        $bot->edit("✅ Сохранено.\n\n" . $text, $kb);
    }

    private function saveField(array $entity, array $row, array $f, $value): void
    {
        $bot = $this->bot;
        $update = [$f['name'] => $value];
        if (!empty($entity['stamp_updater'])) {
            $update['updated_by'] = $bot->tgId;
            $update['updated_at'] = $bot->db->now();
        } elseif (in_array('updated_at', $this->columns($entity['table']), true)) {
            $update['updated_at'] = $bot->db->now();
        }
        (new Repository($bot->db, $entity['table']))->update((int) $row['id'], $update);
        $bot->audit->log($bot->tgId, 'update', $entity['table'], (int) $row['id'],
            [$f['name'] => $row[$f['name']] === null ? null : (string) $row[$f['name']]],
            [$f['name'] => $value === null ? null : (string) $value]);
    }

    // ------------------------------------------------------- текстовый ввод
    public function onState(string $step, array $message): bool
    {
        $bot = $this->bot;
        $text = (string) ($message['text'] ?? '');
        $data = $bot->state->data($bot->chatId);
        $entity = Registry::get((string) ($data['ent'] ?? ''));
        if (!$entity) {
            return false;
        }

        if ($step === 'add') {
            $idx = (int) ($data['idx'] ?? 0);
            $f = Registry::field($entity, $idx);
            if (!$f) {
                return false;
            }
            if ($this->options($f) !== null) {
                $bot->send('Выберите значение кнопкой выше 👆');
                return true;
            }
            try {
                $value = $this->parseText($f, $text);
            } catch (\RuntimeException $err) {
                $bot->send('⚠️ ' . $err->getMessage());
                return true;
            }
            $vals = $data['vals'] ?? [];
            $vals[$f['name']] = $value;
            $this->advance((string) $data['ent'], $entity, $vals, $idx + 1);
            return true;
        }

        if ($step === 'edit') {
            $f = Registry::field($entity, (int) ($data['fi'] ?? 0));
            $repo = new Repository($bot->db, $entity['table']);
            $row = $repo->get((int) ($data['id'] ?? 0));
            if (!$f || !$row) {
                $bot->state->clear($bot->chatId);
                $bot->send('Запись не найдена.');
                return true;
            }
            try {
                $value = $this->parseText($f, $text);
            } catch (\RuntimeException $err) {
                $bot->send('⚠️ ' . $err->getMessage());
                return true;
            }
            $this->saveField($entity, $row, $f, $value);
            $bot->state->clear($bot->chatId);
            $row[$f['name']] = $value;
            [$view, $kb] = $this->renderView((string) $data['ent'], $entity, $row);
            $bot->send("✅ Сохранено.\n\n" . $view, $kb);
            $bot->send('Готово.', Texts::mainMenu($bot->lang));
            return true;
        }

        return false;
    }

    // ------------------------------------------------------------ помощники
    /** Варианты выбора для поля или null, если значение вводится текстом. */
    private function options(array $f): ?array
    {
        $bot = $this->bot;
        switch ($f['type']) {
            case 'bool':
                return ['1' => 'Да', '0' => 'Нет'];
            case 'choice':
                return $f['choices'];
            case 'currency':
                $out = [];
                foreach ($bot->db->all('SELECT * FROM currencies WHERE is_active = 1 ORDER BY id') as $c) {
                    $out[$c['code']] = $c['code'] . ' (' . $c['name'] . ')';
                }
                return $out;
            case 'fk':
                $target = Registry::get($f['fk']);
                if (!$target) {
                    return [];
                }
                $out = [];
                $rows = (new Repository($bot->db, $target['table']))->all([], $target['order'], 40);
                foreach ($rows as $row) {
                    $out[$row['id']] = ($target['row'])($row);
                }
                return $out;
        }
        return null;
    }

    /** @return mixed */
    private function parseChoice(array $f, string $raw)
    {
        if ($raw === self::SKIP || $raw === '') {
            return null;
        }
        if ($f['type'] === 'fk') {
            return (int) $raw;
        }
        if ($f['type'] === 'bool') {
            return $raw === '1' ? 1 : 0;
        }
        return $raw;
    }

    /**
     * @return mixed
     * @throws \RuntimeException при некорректном вводе
     */
    private function parseText(array $f, string $text)
    {
        $text = trim($text);
        if (Format::isSkip($text)) {
            if ($f['required']) {
                throw new \RuntimeException('Это поле обязательно, введите значение.');
            }
            return null;
        }
        if ($f['type'] === 'int') {
            if (!preg_match('/^-?\d+$/', $text)) {
                throw new \RuntimeException('Введите целое число.');
            }
            return (int) $text;
        }
        if ($f['type'] === 'dec') {
            $value = Format::parseNumber($text);
            if ($value === null) {
                throw new \RuntimeException('Введите число, например: 5.5');
            }
            return $value;
        }
        return $text;
    }

    private function displayValue(array $f, $value): string
    {
        if ($value === null || $value === '') {
            return '—';
        }
        if ($f['type'] === 'bool') {
            return ((int) $value === 1) ? 'Да' : 'Нет';
        }
        if ($f['type'] === 'choice') {
            return (string) ($f['choices'][$value] ?? $value);
        }
        if ($f['type'] === 'dec') {
            return Format::num($value);
        }
        if ($f['type'] === 'fk') {
            $target = Registry::get($f['fk']);
            if (!$target) {
                return (string) $value;
            }
            $row = (new Repository($this->bot->db, $target['table']))->get((int) $value);
            return $row ? Format::trunc(($target['row'])($row), 60) : "#$value (нет записи)";
        }
        return (string) $value;
    }

    /** @var array<string,string[]> */
    private static array $columnsCache = [];

    /** @return string[] Список колонок таблицы. */
    private function columns(string $table): array
    {
        if (isset(self::$columnsCache[$table])) {
            return self::$columnsCache[$table];
        }
        $db = $this->bot->db;
        $cols = [];
        if ($db->driver() === 'sqlite') {
            foreach ($db->all("PRAGMA table_info($table)") as $row) {
                $cols[] = (string) $row['name'];
            }
        } else {
            foreach ($db->all("SHOW COLUMNS FROM `$table`") as $row) {
                $cols[] = (string) ($row['Field'] ?? '');
            }
        }
        return self::$columnsCache[$table] = $cols;
    }
}
