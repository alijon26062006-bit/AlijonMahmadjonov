<?php

namespace CargoBot\Handler\User;

use CargoBot\Bot;
use CargoBot\Service\Audit;
use CargoBot\Texts;
use CargoBot\Util\Format;

/** Оформление заявки: имя → телефон → ссылка → описание → вес → объём → комментарий. */
class OrderHandler
{
    private Bot $bot;

    public function __construct(Bot $bot)
    {
        $this->bot = $bot;
    }

    public function start(): void
    {
        $bot = $this->bot;
        $bot->state->set($bot->chatId, 'order:name', []);
        $bot->send($bot->text('order_name'), Texts::cancelMenu($bot->lang));
    }

    /** Запуск из кнопки после расчёта — данные расчёта сохраняются. */
    public function onCallback(string $data): void
    {
        $bot = $this->bot;
        if ($data !== 'order:start') {
            $bot->answer();
            return;
        }
        $prefill = $bot->state->data($bot->chatId); // prefill_* от расчёта
        $bot->state->set($bot->chatId, 'order:name', $prefill);
        $bot->answer();
        $bot->send($bot->text('order_name'), Texts::cancelMenu($bot->lang));
    }

    public function onState(string $step, array $message): bool
    {
        $bot = $this->bot;
        $text = trim((string) ($message['text'] ?? ''));

        switch ($step) {
            case 'name':
                if ($text === '') {
                    $bot->send('Пожалуйста, напишите ваше имя.');
                    return true;
                }
                $bot->state->merge($bot->chatId, ['name' => $text]);
                $bot->state->set($bot->chatId, 'order:phone');
                $bot->send($bot->text('order_phone'));
                return true;

            case 'phone':
                if ($text === '') {
                    $bot->send('Пожалуйста, укажите номер телефона.');
                    return true;
                }
                $bot->state->merge($bot->chatId, ['phone' => $text]);
                $bot->state->set($bot->chatId, 'order:url');
                $bot->send($bot->text('order_url'));
                return true;

            case 'url':
                $bot->state->merge($bot->chatId, [
                    'product_url' => Format::isSkip($text) ? null : $text,
                ]);
                $bot->state->set($bot->chatId, 'order:description');
                $bot->send($bot->text('order_description'));
                return true;

            case 'description':
                $data = $bot->state->merge($bot->chatId, [
                    'description' => Format::isSkip($text) ? null : $text,
                ]);
                // если пришли из расчёта — вес и объём уже известны
                if (isset($data['prefill_weight']) && $data['prefill_weight'] !== null) {
                    $bot->state->merge($bot->chatId, [
                        'weight' => $data['prefill_weight'],
                        'volume' => $data['prefill_volume'] ?? null,
                    ]);
                    $bot->state->set($bot->chatId, 'order:comment');
                    $bot->send($bot->text('order_comment'));
                } else {
                    $bot->state->set($bot->chatId, 'order:weight');
                    $bot->send($bot->text('order_weight'));
                }
                return true;

            case 'weight':
                $weight = null;
                if (!Format::isSkip($text)) {
                    $weight = Format::parseNumber($text);
                    if ($weight === null) {
                        $bot->send($bot->text('calc_bad_number'));
                        return true;
                    }
                }
                $bot->state->merge($bot->chatId, ['weight' => $weight]);
                $bot->state->set($bot->chatId, 'order:volume');
                $bot->send($bot->text('order_volume'));
                return true;

            case 'volume':
                $volume = null;
                if (!Format::isSkip($text)) {
                    $volume = Format::parseNumber($text);
                    if ($volume === null) {
                        $bot->send($bot->text('calc_bad_number'));
                        return true;
                    }
                }
                $bot->state->merge($bot->chatId, ['volume' => $volume]);
                $bot->state->set($bot->chatId, 'order:comment');
                $bot->send($bot->text('order_comment'));
                return true;

            case 'comment':
                $data = $bot->state->data($bot->chatId);
                $bot->state->clear($bot->chatId);
                $comment = Format::isSkip($text) ? null : $text;
                if (!empty($data['prefill_calc'])) {
                    $comment = trim(($comment ?? '') . "\n[Расчёт: " . $data['prefill_calc'] . ']');
                }
                $this->createOrder($data, $comment);
                return true;
        }

        return false;
    }

    private function createOrder(array $data, ?string $comment): void
    {
        $bot = $this->bot;
        $now = $bot->db->now();

        $id = $bot->db->insert('orders', [
            'number'      => 'TMP',
            'user_id'     => $bot->userId(),
            'name'        => (string) ($data['name'] ?? '—'),
            'phone'       => (string) ($data['phone'] ?? '—'),
            'product_url' => $data['product_url'] ?? null,
            'description' => $data['description'] ?? null,
            'weight'      => $data['weight'] ?? null,
            'volume'      => $data['volume'] ?? null,
            'comment'     => $comment,
            'status'      => 'Новая',
            'created_at'  => $now,
        ]);
        $number = 'ORD-' . str_pad((string) $id, 5, '0', STR_PAD_LEFT);
        $bot->db->update('orders', $id, ['number' => $number, 'updated_at' => $now]);

        $order = $bot->db->one('SELECT * FROM orders WHERE id = :i', ['i' => $id]);
        $bot->audit->log($bot->tgId, 'create', 'orders', $id, null, Audit::snapshot($order));

        $bot->send(
            sprintf($bot->text('order_done'), Format::esc($number)),
            Texts::mainMenu($bot->lang)
        );

        $weightStr = $order['weight'] !== null ? Format::num($order['weight']) . ' кг' : '—';
        $volumeStr = $order['volume'] !== null ? Format::num($order['volume']) . ' м³' : '—';
        $bot->notify->toAdmins(implode("\n", [
            '🆕 <b>Новая заявка ' . Format::esc($number) . '</b>',
            '👤 ' . Format::esc($order['name']),
            '📱 ' . Format::esc($order['phone']),
            '🔗 ' . Format::esc($order['product_url'] ?? '—'),
            '📄 ' . Format::esc($order['description'] ?? '—'),
            '⚖️ ' . $weightStr . ' | 📐 ' . $volumeStr,
            '💬 ' . Format::esc($order['comment'] ?? '—'),
            'От: @' . Format::esc($bot->user['username'] ?? '-') . ' (id ' . $bot->tgId . ')',
        ]));
    }
}
