<?php

namespace CargoBot\Handler\User;

use CargoBot\Bot;
use CargoBot\Telegram\Keyboard;
use CargoBot\Texts;
use CargoBot\Util\Format;

/** Пошаговый расчёт: тип доставки → категория → вес → объём → результат. */
class CalcHandler
{
    private Bot $bot;

    public function __construct(Bot $bot)
    {
        $this->bot = $bot;
    }

    public function start(): void
    {
        $bot = $this->bot;
        $types = $bot->db->all('SELECT * FROM delivery_types WHERE is_active = 1 ORDER BY sort_order, id');
        if (!$types) {
            $bot->send($bot->text('calc_no_tariff'), Texts::mainMenu($bot->lang));
            return;
        }
        $bot->state->set($bot->chatId, 'calc:type', []);
        $rows = [];
        foreach ($types as $t) {
            $label = trim(($t['emoji'] ?? '') . ' ' . $t['name']);
            $rows[] = [[$label, 'calc:dt:' . $t['id']]];
        }
        $bot->send($bot->text('calc_delivery_type'), Keyboard::inline($rows));
    }

    public function onCallback(string $data): void
    {
        $bot = $this->bot;
        $parts = explode(':', $data);
        $what = $parts[1] ?? '';

        if ($what === 'dt') {
            $bot->state->set($bot->chatId, 'calc:category', ['delivery_type_id' => (int) $parts[2]]);
            $cats = $bot->db->all('SELECT * FROM categories WHERE is_active = 1 ORDER BY sort_order, id');
            $rows = [];
            $line = [];
            foreach ($cats as $c) {
                $line[] = [$c['name'], 'calc:cat:' . $c['id']];
                if (count($line) === 2) {
                    $rows[] = $line;
                    $line = [];
                }
            }
            if ($line) {
                $rows[] = $line;
            }
            $bot->edit($bot->text('calc_category'), Keyboard::inline($rows));
            $bot->answer();
            return;
        }

        if ($what === 'cat') {
            $bot->state->merge($bot->chatId, ['category_id' => (int) $parts[2]]);
            $bot->state->set($bot->chatId, 'calc:weight');
            $bot->edit($bot->text('calc_weight'));
            $bot->send('Жду вес в кг 👇', Texts::cancelMenu($bot->lang));
            $bot->answer();
            return;
        }

        $bot->answer();
    }

    public function onState(string $step, array $message): bool
    {
        $bot = $this->bot;
        $text = (string) ($message['text'] ?? '');

        if ($step === 'weight') {
            $weight = Format::parseNumber($text);
            if ($weight === null || $weight <= 0) {
                $bot->send($bot->text('calc_bad_number'));
                return true;
            }
            $bot->state->merge($bot->chatId, ['weight' => $weight]);
            $bot->state->set($bot->chatId, 'calc:volume');
            $bot->send($bot->text('calc_volume'), Texts::cancelMenu($bot->lang));
            return true;
        }

        if ($step === 'volume') {
            $volume = Format::parseNumber($text);
            if ($volume === null) {
                $bot->send($bot->text('calc_bad_number'));
                return true;
            }
            $data = $bot->state->data($bot->chatId);
            $bot->state->clear($bot->chatId);

            $result = $bot->calc->calculate(
                (int) ($data['delivery_type_id'] ?? 0),
                (int) ($data['category_id'] ?? 0),
                (float) ($data['weight'] ?? 0),
                $volume,
                $bot->userId()
            );
            if (!$result) {
                $bot->send($bot->text('calc_no_tariff'), Texts::mainMenu($bot->lang));
                return true;
            }

            // Данные расчёта пригодятся для быстрого оформления заявки
            $bot->state->set($bot->chatId, null, [
                'prefill_weight' => $data['weight'] ?? null,
                'prefill_volume' => $volume,
                'prefill_calc'   => trim(($result['delivery_type']['name'] ?? '') . ', ' . ($result['category']['name'] ?? '')),
            ]);

            $bot->send($this->render($result), Texts::mainMenu($bot->lang));
            $bot->send(
                'Оформить заявку на эту доставку?',
                Keyboard::inline([[[$bot->text('btn_make_order'), 'order:start']]])
            );
            return true;
        }

        if ($step === 'type' || $step === 'category') {
            $bot->send('Выберите вариант кнопкой выше 👆');
            return true;
        }

        return false;
    }

    /** Текст результата расчёта. */
    public function render(array $r): string
    {
        $cur = Format::esc($r['currency_code']);
        $dtLabel = trim((($r['delivery_type']['emoji'] ?? '') . ' ' . ($r['delivery_type']['name'] ?? '—')));

        $lines = [
            '🧮 <b>Результат расчёта</b>',
            '',
            '🚚 Тип доставки: <b>' . Format::esc($dtLabel) . '</b>',
            '🗂 Категория: <b>' . Format::esc($r['category']['name'] ?? '—') . '</b>',
            '📋 Тариф: <b>' . Format::esc($r['tariff']['name']) . '</b>',
            '💵 Стоимость за кг: <b>' . Format::money($r['price_per_kg']) . ' ' . $cur . '</b>',
            '⚖️ Вес: <b>' . Format::num($r['weight']) . ' кг</b>',
        ];
        if ($r['volume'] > 0) {
            $lines[] = '📐 Объём: <b>' . Format::num($r['volume']) . ' м³</b> (объёмный вес: '
                       . Format::num($r['volumetric_weight']) . ' кг)';
        }
        if (abs($r['chargeable_weight'] - $r['weight']) > 0.0001) {
            $lines[] = '🏋️ Оплачиваемый вес: <b>' . Format::num($r['chargeable_weight']) . ' кг</b>';
        }
        $lines[] = '💰 Базовая стоимость: <b>' . Format::money($r['base_cost']) . ' ' . $cur . '</b>';
        if ($r['min_order_applied']) {
            $lines[] = 'ℹ️ Применена минимальная стоимость заказа.';
        }
        foreach ($r['lines'] as $line) {
            $isDiscount = $line['amount'] < 0;
            $lines[] = ($isDiscount ? '🎁 ' : '➕ ') . Format::esc($line['name']) . ': '
                       . ($isDiscount ? '−' : '+') . Format::money(abs($line['amount'])) . ' ' . $cur;
        }
        $lines[] = '';
        $lines[] = '✅ <b>Итого: ' . Format::money($r['total']) . ' ' . $cur . '</b>';
        if ($r['total_tjs'] !== null) {
            $lines[] = '≈ ' . Format::money($r['total_tjs']) . ' TJS (по текущему курсу)';
        }
        if (!empty($r['delivery_time'])) {
            $lines[] = '🕓 Срок доставки: <b>' . Format::esc($r['delivery_time']) . '</b>';
        }
        return implode("\n", $lines);
    }
}
