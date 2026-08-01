<?php

namespace CargoBot\Handler\Admin;

use CargoBot\Bot;
use CargoBot\Telegram\Keyboard;
use CargoBot\Texts;
use CargoBot\Util\Format;

/**
 * Массовая рассылка.
 *
 * Отправка идёт порциями: у PHP на хостинге ограничено время выполнения
 * запроса, поэтому после каждой порции показывается кнопка «Продолжить».
 * Текст и прогресс хранятся в таблице broadcasts, ничего не теряется.
 */
class BroadcastHandler
{
    private const BATCH = 25;

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

        if ($action === 'broadcast') {
            $bot->state->set($bot->chatId, 'bc:text', []);
            $bot->send(
                "📣 Введите текст рассылки.\nМожно использовать <b>жирный</b>, <i>курсив</i> и ссылки.",
                Texts::cancelMenu($bot->lang)
            );
            $bot->answer();
            return;
        }

        if ($action === 'bc_go') {
            $this->startSending((int) ($parts[2] ?? 0));
            return;
        }

        if ($action === 'bc_next') {
            $this->sendBatch((int) ($parts[2] ?? 0), (int) ($parts[3] ?? 0));
            return;
        }

        $bot->answer();
    }

    public function onState(string $step, array $message): bool
    {
        if ($step !== 'text') {
            return false;
        }
        $bot = $this->bot;
        $text = (string) ($message['text'] ?? '');
        if (trim($text) === '') {
            $bot->send('Текст пустой. Напишите сообщение для рассылки.');
            return true;
        }
        $bot->state->clear($bot->chatId);

        $total = (int) $bot->db->value('SELECT COUNT(*) FROM users WHERE is_blocked = 0');
        $id = $bot->db->insert('broadcasts', [
            'admin_tg_id' => $bot->tgId,
            'text'        => $text,
            'total'       => $total,
            'created_at'  => $bot->db->now(),
        ]);

        $bot->send(
            "Проверьте текст:\n\n" . $text . "\n\n<b>Получателей: $total</b>",
            Keyboard::inline([
                [['✅ Отправить всем', "adm:bc_go:$id"]],
                [['❌ Отмена', 'adm:menu']],
            ])
        );
        return true;
    }

    private function startSending(int $broadcastId): void
    {
        $bot = $this->bot;
        $bc = $bot->db->one('SELECT * FROM broadcasts WHERE id = :i', ['i' => $broadcastId]);
        if (!$bc) {
            $bot->answer('Рассылка не найдена', true);
            return;
        }
        $bot->answer('Начинаю рассылку...');
        $bot->edit('⏳ Рассылка запущена, получателей: ' . $bc['total']);
        $this->sendBatch($broadcastId, 0, false);
    }

    private function sendBatch(int $broadcastId, int $offset, bool $answer = true): void
    {
        $bot = $this->bot;
        $bc = $bot->db->one('SELECT * FROM broadcasts WHERE id = :i', ['i' => $broadcastId]);
        if (!$bc) {
            $bot->answer('Рассылка не найдена', true);
            return;
        }
        if ($answer) {
            $bot->answer('Отправляю...');
        }

        @set_time_limit(120);
        $users = $bot->db->all(
            'SELECT tg_id FROM users WHERE is_blocked = 0 ORDER BY id LIMIT ' . self::BATCH
            . ' OFFSET ' . $offset
        );

        $sent = (int) $bc['sent'];
        $failed = (int) $bc['failed'];
        foreach ($users as $u) {
            if ($bot->api->sendMessage((int) $u['tg_id'], (string) $bc['text']) !== null) {
                $sent++;
            } else {
                $failed++;
            }
            usleep(60000); // ~16 сообщений в секунду, чтобы не упереться в лимиты Telegram
        }
        $bot->db->update('broadcasts', $broadcastId, ['sent' => $sent, 'failed' => $failed]);

        $done = $offset + count($users);
        $total = (int) $bc['total'];

        if (count($users) === self::BATCH && $done < $total) {
            $bot->send(
                "📤 Отправлено: <b>$done</b> из <b>$total</b>\n"
                . "✅ Успешно: $sent   ⚠️ Ошибок: $failed",
                Keyboard::inline([
                    [['▶️ Продолжить рассылку', "adm:bc_next:$broadcastId:$done"]],
                    [['⏹ Остановить', 'adm:menu']],
                ])
            );
            return;
        }

        $bot->audit->log($bot->tgId, 'broadcast', 'broadcasts', $broadcastId, null, [
            'total'  => (string) $total,
            'sent'   => (string) $sent,
            'failed' => (string) $failed,
        ]);
        $bot->send(
            "✅ <b>Рассылка завершена</b>\nОтправлено: $sent\nОшибок: $failed",
            Keyboard::inline([[['◀️ Админ-меню', 'adm:menu']]])
        );
    }
}
