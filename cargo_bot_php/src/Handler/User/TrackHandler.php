<?php

namespace CargoBot\Handler\User;

use CargoBot\Bot;
use CargoBot\Texts;
use CargoBot\Util\Format;

/** Отслеживание груза по трек-номеру. */
class TrackHandler
{
    private Bot $bot;

    public function __construct(Bot $bot)
    {
        $this->bot = $bot;
    }

    public function start(): void
    {
        $bot = $this->bot;
        $bot->state->set($bot->chatId, 'track:number', []);
        $bot->send($bot->text('track_ask'), Texts::cancelMenu($bot->lang));
    }

    public function onState(string $step, array $message): bool
    {
        if ($step !== 'number') {
            return false;
        }
        $bot = $this->bot;
        $number = trim((string) ($message['text'] ?? ''));

        $track = $bot->db->one(
            'SELECT * FROM tracks WHERE track_number = :n',
            ['n' => $number]
        );
        if (!$track) {
            $bot->send($bot->text('track_not_found'));
            return true;
        }
        $bot->state->clear($bot->chatId);

        $history = $bot->db->all(
            'SELECT * FROM track_history WHERE track_id = :t ORDER BY created_at, id',
            ['t' => (int) $track['id']]
        );

        $lines = [
            '📦 <b>Груз ' . Format::esc($track['track_number']) . '</b>',
            'Текущий статус: <b>' . Format::esc($track['status']) . '</b>',
            'Обновлено: ' . Format::date($track['updated_at'] ?? $track['created_at']),
        ];
        if ($history) {
            $lines[] = '';
            $lines[] = '📜 <b>История:</b>';
            foreach ($history as $h) {
                $lines[] = '• ' . Format::date($h['created_at'], 'd.m.Y H:i') . ' — ' . Format::esc($h['status'])
                           . ($h['comment'] ? ' (' . Format::esc($h['comment']) . ')' : '');
            }
        }
        $bot->send(implode("\n", $lines), Texts::mainMenu($bot->lang));
        return true;
    }
}
