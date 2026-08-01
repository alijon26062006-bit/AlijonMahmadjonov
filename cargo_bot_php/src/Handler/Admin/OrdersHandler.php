<?php

namespace CargoBot\Handler\Admin;

use CargoBot\Bot;
use CargoBot\Telegram\Keyboard;
use CargoBot\Util\Format;

/** Заявки: список, карточка, смена статуса с уведомлением клиента. */
class OrdersHandler
{
    private const PER_PAGE = 8;

    private Bot $bot;

    public function __construct(Bot $bot)
    {
        $this->bot = $bot;
    }

    public function onCallback(string $data): void
    {
        $bot = $this->bot;
        $parts = explode(':', $data);
        $action = $parts[1] ?? '';

        if ($action === 'orders') {
            $this->listOrders((int) ($parts[2] ?? 1));
        } elseif ($action === 'order') {
            $this->view((int) ($parts[2] ?? 0));
        } elseif ($action === 'ostatus') {
            $this->changeStatus((int) ($parts[2] ?? 0), (int) ($parts[3] ?? -1));
            return; // answer отправлен внутри
        }
        $bot->answer();
    }

    private function listOrders(int $page): void
    {
        $db = $this->bot->db;
        $total = (int) $db->value('SELECT COUNT(*) FROM orders');
        $pages = max(1, (int) ceil($total / self::PER_PAGE));
        $page = max(1, min($page, $pages));
        $rows = $db->all('SELECT * FROM orders ORDER BY id DESC LIMIT ' . self::PER_PAGE
                         . ' OFFSET ' . (($page - 1) * self::PER_PAGE));
        $buttons = [];
        foreach ($rows as $o) {
            $buttons[] = [[
                Format::trunc($o['number'] . ' | ' . $o['name'] . ' | ' . $o['status'], 46),
                'adm:order:' . $o['id'],
            ]];
        }
        $this->bot->edit(
            "📦 <b>Заявки</b> (всего: $total)",
            Keyboard::paginate('adm:orders', $page, $pages, $buttons)
        );
    }

    private function view(int $id): void
    {
        $bot = $this->bot;
        $order = $bot->db->one('SELECT * FROM orders WHERE id = :i', ['i' => $id]);
        if (!$order) {
            $bot->answer('Заявка не найдена', true);
            return;
        }
        [$text, $kb] = $this->render($order);
        $bot->edit($text, $kb);
    }

    /** @return array{0:string,1:array} */
    private function render(array $order): array
    {
        $bot = $this->bot;
        $user = $order['user_id']
            ? $bot->db->one('SELECT * FROM users WHERE id = :i', ['i' => (int) $order['user_id']])
            : null;
        $statuses = (array) $bot->settings->getJson('order_statuses', []);

        $weight = $order['weight'] !== null ? Format::num($order['weight']) . ' кг' : '—';
        $volume = $order['volume'] !== null ? Format::num($order['volume']) . ' м³' : '—';

        $lines = [
            '📦 <b>Заявка ' . Format::esc($order['number']) . '</b>',
            'Статус: <b>' . Format::esc($order['status']) . '</b>',
            '',
            '👤 ' . Format::esc($order['name']),
            '📱 ' . Format::esc($order['phone']),
            '🔗 ' . Format::esc($order['product_url'] ?? '—'),
            '📄 ' . Format::esc($order['description'] ?? '—'),
            '⚖️ ' . $weight . ' | 📐 ' . $volume,
            '💬 ' . Format::esc($order['comment'] ?? '—'),
            '🕓 ' . Format::date($order['created_at']),
            'Клиент: ' . ($user ? '@' . Format::esc($user['username'] ?? '-') . ' (<code>' . $user['tg_id'] . '</code>)' : '—'),
            '',
            'Сменить статус:',
        ];

        $kb = [];
        foreach ($statuses as $i => $status) {
            $mark = ($status === $order['status']) ? '✅ ' : '';
            $kb[] = [[$mark . $status, 'adm:ostatus:' . $order['id'] . ':' . $i]];
        }
        $kb[] = [['◀️ К заявкам', 'adm:orders:1']];
        return [implode("\n", $lines), Keyboard::inline($kb)];
    }

    private function changeStatus(int $orderId, int $statusIndex): void
    {
        $bot = $this->bot;
        $order = $bot->db->one('SELECT * FROM orders WHERE id = :i', ['i' => $orderId]);
        $statuses = (array) $bot->settings->getJson('order_statuses', []);
        if (!$order || !isset($statuses[$statusIndex])) {
            $bot->answer('Ошибка: статус не найден', true);
            return;
        }
        $new = (string) $statuses[$statusIndex];
        $old = (string) $order['status'];
        if ($new === $old) {
            $bot->answer('Этот статус уже установлен');
            return;
        }

        $bot->db->update('orders', $orderId, ['status' => $new, 'updated_at' => $bot->db->now()]);
        $bot->audit->log($bot->tgId, 'status', 'orders', $orderId,
                         ['status' => $old], ['status' => $new]);
        $order['status'] = $new;

        if ($order['user_id']) {
            $user = $bot->db->one('SELECT * FROM users WHERE id = :i', ['i' => (int) $order['user_id']]);
            if ($user) {
                $bot->notify->toUser((int) $user['tg_id'],
                    'ℹ️ Статус вашей заявки <b>' . Format::esc($order['number'])
                    . '</b> изменён: <b>' . Format::esc($new) . '</b>');
            }
        }

        [$text, $kb] = $this->render($order);
        $bot->edit($text, $kb);
        $bot->answer('Статус обновлён');
    }
}
