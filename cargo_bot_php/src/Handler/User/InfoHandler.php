<?php

namespace CargoBot\Handler\User;

use CargoBot\Bot;
use CargoBot\Telegram\Keyboard;
use CargoBot\Util\Format;

/**
 * Информационные разделы: тарифы, склады, контакты, FAQ.
 * Весь контент берётся из базы и правится через админ-панель.
 */
class InfoHandler
{
    private Bot $bot;

    public function __construct(Bot $bot)
    {
        $this->bot = $bot;
    }

    public function tariffs(): void
    {
        $bot = $this->bot;
        $rows = $bot->db->all(
            'SELECT t.*, d.name AS dt_name, d.emoji AS dt_emoji
             FROM tariffs t
             LEFT JOIN delivery_types d ON d.id = t.delivery_type_id
             WHERE t.is_active = 1
             ORDER BY d.sort_order, t.id'
        );
        if (!$rows) {
            $bot->send($bot->text('no_data'));
            return;
        }
        $lines = ['💰 <b>Актуальные тарифы</b>'];
        $currentType = null;
        foreach ($rows as $t) {
            if ($t['dt_name'] !== $currentType) {
                $currentType = $t['dt_name'];
                $lines[] = '';
                $lines[] = '<b>' . Format::esc(trim(($t['dt_emoji'] ?? '') . ' ' . $currentType)) . '</b>';
            }
            $extra = [];
            if ((float) $t['min_weight'] > 0) {
                $extra[] = 'от ' . Format::num($t['min_weight']) . ' кг';
            }
            if ((float) $t['min_order_cost'] > 0) {
                $extra[] = 'мин. ' . Format::money($t['min_order_cost']) . ' ' . $t['currency_code'];
            }
            $suffix = $extra ? ' (' . implode(', ', $extra) . ')' : '';
            $time = !empty($t['delivery_time']) ? ' — ' . Format::esc($t['delivery_time']) : '';
            $lines[] = '• ' . Format::esc($t['name']) . ': <b>' . Format::money($t['price_per_kg'])
                       . ' ' . Format::esc($t['currency_code']) . '/кг</b>' . $suffix . $time;
        }
        $bot->send(implode("\n", $lines));
    }

    public function warehouses(): void
    {
        $bot = $this->bot;
        $rows = $bot->db->all('SELECT * FROM warehouses WHERE is_active = 1 ORDER BY sort_order, id');
        if (!$rows) {
            $bot->send($bot->text('no_data'));
            return;
        }
        $lines = ['📍 <b>Адреса складов</b>'];
        foreach ($rows as $w) {
            $lines[] = '';
            $lines[] = '<b>' . Format::esc($w['name']) . '</b>';
            $lines[] = Format::esc($w['address']);
            if (!empty($w['note'])) {
                $lines[] = 'ℹ️ ' . Format::esc($w['note']);
            }
        }
        $bot->send(implode("\n", $lines));
    }

    public function contacts(): void
    {
        $bot = $this->bot;
        $rows = $bot->db->all('SELECT * FROM contacts WHERE is_active = 1 ORDER BY sort_order, id');
        if (!$rows) {
            $bot->send($bot->text('no_data'));
            return;
        }
        $lines = ['☎ <b>Контакты</b>', ''];
        foreach ($rows as $c) {
            $lines[] = '• <b>' . Format::esc($c['title']) . ':</b> ' . Format::esc($c['value']);
        }
        $bot->send(implode("\n", $lines));
    }

    public function faq(): void
    {
        $bot = $this->bot;
        $rows = $bot->db->all('SELECT * FROM faq WHERE is_active = 1 ORDER BY sort_order, id');
        if (!$rows) {
            $bot->send($bot->text('no_data'));
            return;
        }
        $kb = [];
        foreach ($rows as $f) {
            $kb[] = [[Format::trunc($f['question'], 60), 'faq:' . $f['id']]];
        }
        $bot->send($bot->text('faq_title'), Keyboard::inline($kb));
    }

    public function onCallback(string $data): void
    {
        $bot = $this->bot;
        $id = (int) (explode(':', $data)[1] ?? 0);
        $faq = $bot->db->one('SELECT * FROM faq WHERE id = :i', ['i' => $id]);
        $bot->answer();
        if ($faq) {
            $bot->send('❓ <b>' . Format::esc($faq['question']) . "</b>\n\n" . Format::esc($faq['answer']));
        }
    }
}
