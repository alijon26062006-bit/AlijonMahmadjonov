<?php

namespace CargoBot\Handler\Admin;

use CargoBot\Bot;
use CargoBot\Service\Export;
use CargoBot\Telegram\Keyboard;
use CargoBot\Util\Format;

/** Админ-меню, статистика, пользователи, история расчётов, журнал, экспорт. */
class AdminHandler
{
    private const PER_PAGE = 10;

    private Bot $bot;

    public function __construct(Bot $bot)
    {
        $this->bot = $bot;
    }

    public static function menuKeyboard(): array
    {
        return Keyboard::inline([
            [['📊 Статистика', 'adm:stats'], ['📦 Заявки', 'adm:orders:1']],
            [['💰 Тарифы', 'e:trf:list:1'], ['🧮 Коэффициенты', 'e:cof:list:1']],
            [['🚚 Типы доставки', 'e:dtp:list:1'], ['🗂 Категории', 'e:cat:list:1']],
            [['💱 Валюты', 'e:cur:list:1'], ['📈 Курсы валют', 'e:rate:list:1']],
            [['➕ Сборы и скидки', 'e:svc:list:1'], ['⚙️ Настройки', 'e:set:list:1']],
            [['❓ FAQ', 'e:faq:list:1'], ['📍 Склады', 'e:whs:list:1']],
            [['☎ Контакты', 'e:cnt:list:1'], ['👮 Администраторы', 'e:adm:list:1']],
            [['👥 Пользователи', 'adm:users:1'], ['🔎 Треки', 'adm:tracks:1']],
            [['📣 Рассылка', 'adm:broadcast'], ['📤 Экспорт', 'adm:export']],
            [['🧾 История расчётов', 'adm:calcs:1'], ['📜 Журнал изменений', 'adm:logs:1']],
        ]);
    }

    public function menu(bool $edit = true): void
    {
        $text = "🛠 <b>Панель администратора</b>\n\nВсё, что здесь меняется, сразу применяется в расчётах.";
        if ($edit) {
            $this->bot->edit($text, self::menuKeyboard());
        } else {
            $this->bot->send($text, self::menuKeyboard());
        }
    }

    public function onCallback(string $data): void
    {
        $bot = $this->bot;
        $parts = explode(':', $data);
        $action = $parts[1] ?? '';
        $page = (int) ($parts[2] ?? 1);

        switch ($action) {
            case 'menu':
                $bot->state->clear($bot->chatId);
                $this->menu();
                break;
            case 'stats':
                $this->stats();
                break;
            case 'users':
                $this->users($page);
                break;
            case 'calcs':
                $this->calcs($page);
                break;
            case 'logs':
                $this->logs($page);
                break;
            case 'export':
                $this->exportMenu();
                break;
            case 'exp':
                $this->exportRun((string) ($parts[2] ?? ''));
                return; // answer уже отправлен внутри
        }
        $bot->answer();
    }

    private function stats(): void
    {
        $db = $this->bot->db;
        $lines = [
            '📊 <b>Статистика</b>',
            '',
            '👥 Пользователей: <b>' . (int) $db->value('SELECT COUNT(*) FROM users') . '</b>',
            '📦 Заявок: <b>' . (int) $db->value('SELECT COUNT(*) FROM orders') . '</b>',
            '🧮 Расчётов: <b>' . (int) $db->value('SELECT COUNT(*) FROM calculations') . '</b>',
            '🔎 Треков: <b>' . (int) $db->value('SELECT COUNT(*) FROM tracks') . '</b>',
            '💰 Активных тарифов: <b>' . (int) $db->value('SELECT COUNT(*) FROM tariffs WHERE is_active = 1') . '</b>',
        ];
        $byStatus = $db->all('SELECT status, COUNT(*) AS cnt FROM orders GROUP BY status ORDER BY cnt DESC');
        if ($byStatus) {
            $lines[] = '';
            $lines[] = '<b>Заявки по статусам:</b>';
            foreach ($byStatus as $row) {
                $lines[] = '• ' . Format::esc($row['status']) . ': ' . $row['cnt'];
            }
        }
        $top = $db->all(
            'SELECT delivery_type, COUNT(*) AS cnt FROM calculations
             WHERE delivery_type IS NOT NULL GROUP BY delivery_type ORDER BY cnt DESC LIMIT 5'
        );
        if ($top) {
            $lines[] = '';
            $lines[] = '<b>Популярные типы доставки:</b>';
            foreach ($top as $row) {
                $lines[] = '• ' . Format::esc($row['delivery_type']) . ': ' . $row['cnt'];
            }
        }
        $this->bot->edit(implode("\n", $lines), Keyboard::inline([[['◀️ Админ-меню', 'adm:menu']]]));
    }

    /** @return array{0:array,1:int,2:int,3:int} [строки, страница, всего страниц, всего записей] */
    private function paged(string $table, int $page): array
    {
        $db = $this->bot->db;
        $total = (int) $db->value("SELECT COUNT(*) FROM $table");
        $pages = max(1, (int) ceil($total / self::PER_PAGE));
        $page = max(1, min($page, $pages));
        $rows = $db->all(
            "SELECT * FROM $table ORDER BY id DESC LIMIT " . self::PER_PAGE
            . ' OFFSET ' . (($page - 1) * self::PER_PAGE)
        );
        return [$rows, $page, $pages, $total];
    }

    private function users(int $page): void
    {
        [$rows, $page, $pages, $total] = $this->paged('users', $page);
        $lines = ["👥 <b>Пользователи</b> (всего: $total)", ''];
        foreach ($rows as $u) {
            $lines[] = '• #' . $u['id'] . ' ' . Format::esc($u['full_name'] ?? '—')
                       . ' @' . Format::esc($u['username'] ?? '-')
                       . ' (<code>' . $u['tg_id'] . '</code>) — ' . Format::date($u['created_at'], 'd.m.Y');
        }
        $this->bot->edit(implode("\n", $lines), Keyboard::paginate('adm:users', $page, $pages));
    }

    private function calcs(int $page): void
    {
        [$rows, $page, $pages, $total] = $this->paged('calculations', $page);
        $lines = ["🧾 <b>История расчётов</b> (всего: $total)", ''];
        foreach ($rows as $c) {
            $lines[] = '• ' . Format::date($c['created_at'], 'd.m H:i') . ' | '
                       . Format::esc($c['delivery_type'] ?? '—') . ' / ' . Format::esc($c['category'] ?? '—')
                       . ' | ' . Format::num($c['weight']) . ' кг → <b>'
                       . Format::money($c['total']) . ' ' . Format::esc($c['currency_code'] ?? '') . '</b>';
        }
        $this->bot->edit(implode("\n", $lines), Keyboard::paginate('adm:calcs', $page, $pages));
    }

    private function logs(int $page): void
    {
        [$rows, $page, $pages, $total] = $this->paged('logs', $page);
        $lines = ["📜 <b>Журнал изменений</b> (всего: $total)", ''];
        foreach ($rows as $log) {
            $entry = '• ' . Format::date($log['created_at'], 'd.m H:i')
                     . ' | <code>' . ($log['actor_tg_id'] ?? '—') . '</code> | '
                     . Format::esc($log['action']) . ' ' . Format::esc($log['entity'])
                     . '#' . ($log['entity_id'] ?? '—');
            if (!empty($log['old_data'])) {
                $entry .= "\n   было: " . Format::esc(Format::trunc((string) $log['old_data'], 120));
            }
            if (!empty($log['new_data'])) {
                $entry .= "\n   стало: " . Format::esc(Format::trunc((string) $log['new_data'], 120));
            }
            $lines[] = $entry;
        }
        $this->bot->edit(implode("\n", $lines), Keyboard::paginate('adm:logs', $page, $pages));
    }

    private function exportMenu(): void
    {
        $this->bot->edit('📤 Что выгрузить? Файл откроется в Excel.', Keyboard::inline([
            [['📦 Заявки', 'adm:exp:orders']],
            [['👥 Пользователи', 'adm:exp:users']],
            [['◀️ Админ-меню', 'adm:menu']],
        ]));
    }

    private function exportRun(string $kind): void
    {
        $bot = $this->bot;
        $bot->answer('Готовлю файл...');
        $export = new Export($bot->db, $bot->dataDir() . '/export');
        $path = $kind === 'users' ? $export->users() : $export->orders();
        $bot->api->sendDocument($bot->chatId, $path,
            $kind === 'users' ? 'Пользователи' : 'Заявки');
        @unlink($path);
    }
}
