<?php

namespace CargoBot\Handler\Admin;

use CargoBot\Bot;
use CargoBot\Telegram\Keyboard;
use CargoBot\Texts;
use CargoBot\Util\Format;

/** Треки: список, создание, смена статуса, история, уведомления клиента. */
class TracksHandler
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

        if ($action === 'tracks') {
            $this->listTracks((int) ($parts[2] ?? 1));
        } elseif ($action === 'track') {
            $this->view((int) ($parts[2] ?? 0));
        } elseif ($action === 'track_new') {
            $bot->state->set($bot->chatId, 'trk:number', []);
            $bot->send(
                'Введите трек-номер (или отправьте <b>auto</b> для автогенерации):',
                Texts::cancelMenu($bot->lang)
            );
        } elseif ($action === 'tstatus') {
            $this->changeStatus((int) ($parts[2] ?? 0), (int) ($parts[3] ?? -1));
            return;
        }
        $bot->answer();
    }

    private function listTracks(int $page): void
    {
        $db = $this->bot->db;
        $total = (int) $db->value('SELECT COUNT(*) FROM tracks');
        $pages = max(1, (int) ceil($total / self::PER_PAGE));
        $page = max(1, min($page, $pages));
        $rows = $db->all('SELECT * FROM tracks ORDER BY id DESC LIMIT ' . self::PER_PAGE
                         . ' OFFSET ' . (($page - 1) * self::PER_PAGE));
        $buttons = [];
        foreach ($rows as $t) {
            $buttons[] = [[
                Format::trunc($t['track_number'] . ' | ' . $t['status'], 46),
                'adm:track:' . $t['id'],
            ]];
        }
        $buttons[] = [['➕ Создать трек', 'adm:track_new']];
        $this->bot->edit(
            "🔎 <b>Треки</b> (всего: $total)",
            Keyboard::paginate('adm:tracks', $page, $pages, $buttons)
        );
    }

    private function view(int $id): void
    {
        $bot = $this->bot;
        [$text, $kb] = $this->render($id);
        if ($text === null) {
            $bot->answer('Трек не найден', true);
            return;
        }
        $bot->edit($text, $kb);
    }

    /** @return array{0:?string,1:?array} */
    private function render(int $trackId): array
    {
        $bot = $this->bot;
        $track = $bot->db->one('SELECT * FROM tracks WHERE id = :i', ['i' => $trackId]);
        if (!$track) {
            return [null, null];
        }
        $history = $bot->db->all(
            'SELECT * FROM track_history WHERE track_id = :t ORDER BY created_at, id',
            ['t' => $trackId]
        );
        $user = $track['user_id']
            ? $bot->db->one('SELECT * FROM users WHERE id = :i', ['i' => (int) $track['user_id']])
            : null;
        $statuses = (array) $bot->settings->getJson('track_statuses', []);

        $lines = [
            '📦 <b>Трек ' . Format::esc($track['track_number']) . '</b>',
            'Статус: <b>' . Format::esc($track['status']) . '</b>',
            'Клиент: ' . ($user ? '@' . Format::esc($user['username'] ?: (string) $user['tg_id'])
                                  . ' (<code>' . $user['tg_id'] . '</code>)' : '—'),
        ];
        if ($history) {
            $lines[] = '';
            $lines[] = '📜 История:';
            foreach ($history as $h) {
                $lines[] = '• ' . Format::date($h['created_at'], 'd.m H:i') . ' — ' . Format::esc($h['status']);
            }
        }
        $lines[] = '';
        $lines[] = 'Сменить статус:';

        $kb = [];
        foreach ($statuses as $i => $status) {
            $mark = ($status === $track['status']) ? '✅ ' : '';
            $kb[] = [[$mark . $status, 'adm:tstatus:' . $trackId . ':' . $i]];
        }
        $kb[] = [['◀️ К трекам', 'adm:tracks:1']];
        return [implode("\n", $lines), Keyboard::inline($kb)];
    }

    private function changeStatus(int $trackId, int $statusIndex): void
    {
        $bot = $this->bot;
        $track = $bot->db->one('SELECT * FROM tracks WHERE id = :i', ['i' => $trackId]);
        $statuses = (array) $bot->settings->getJson('track_statuses', []);
        if (!$track || !isset($statuses[$statusIndex])) {
            $bot->answer('Ошибка: статус не найден', true);
            return;
        }
        $new = (string) $statuses[$statusIndex];
        $old = (string) $track['status'];
        if ($new === $old) {
            $bot->answer('Этот статус уже установлен');
            return;
        }

        $now = $bot->db->now();
        $bot->db->update('tracks', $trackId, ['status' => $new, 'updated_at' => $now]);
        $bot->db->insert('track_history', [
            'track_id' => $trackId, 'status' => $new, 'created_at' => $now,
        ]);
        $bot->audit->log($bot->tgId, 'status', 'tracks', $trackId,
                         ['status' => $old], ['status' => $new]);

        if ($track['user_id']) {
            $user = $bot->db->one('SELECT * FROM users WHERE id = :i', ['i' => (int) $track['user_id']]);
            if ($user) {
                $bot->notify->toUser((int) $user['tg_id'],
                    '📦 Статус вашего груза <b>' . Format::esc($track['track_number'])
                    . '</b> изменён: <b>' . Format::esc($new) . '</b>');
            }
        }

        [$text, $kb] = $this->render($trackId);
        $bot->edit($text, $kb);
        $bot->answer('Статус обновлён');
    }

    // ------------------------------------------------- создание трека
    public function onState(string $step, array $message): bool
    {
        $bot = $this->bot;
        $text = trim((string) ($message['text'] ?? ''));

        if ($step === 'number') {
            $number = $text;
            if (mb_strtolower($number) === 'auto') {
                $number = 'TRK-' . strtoupper(bin2hex(random_bytes(4)));
            }
            if ($number === '') {
                $bot->send('Введите трек-номер или «auto».');
                return true;
            }
            $exists = $bot->db->one('SELECT id FROM tracks WHERE track_number = :n', ['n' => $number]);
            if ($exists) {
                $bot->send('Такой трек уже существует, введите другой номер.');
                return true;
            }
            $bot->state->set($bot->chatId, 'trk:user', ['track_number' => $number]);
            $bot->send('Telegram ID клиента для уведомлений (или «-», если не привязывать):');
            return true;
        }

        if ($step === 'user') {
            $userId = null;
            if (!Format::isSkip($text)) {
                if (!preg_match('/^\d+$/', $text)) {
                    $bot->send('Введите числовой Telegram ID или «-».');
                    return true;
                }
                $user = $bot->db->one('SELECT * FROM users WHERE tg_id = :t', ['t' => (int) $text]);
                if (!$user) {
                    $bot->send('Пользователь с таким ID не найден в боте (он должен сначала '
                               . 'нажать /start). Введите другой ID или «-».');
                    return true;
                }
                $userId = (int) $user['id'];
            }

            $data = $bot->state->data($bot->chatId);
            $bot->state->clear($bot->chatId);

            $statuses = (array) $bot->settings->getJson('track_statuses', []);
            $first = (string) ($statuses[0] ?? 'Получен на складе');
            $now = $bot->db->now();

            $trackId = $bot->db->insert('tracks', [
                'track_number' => (string) $data['track_number'],
                'user_id'      => $userId,
                'status'       => $first,
                'created_at'   => $now,
                'updated_at'   => $now,
            ]);
            $bot->db->insert('track_history', [
                'track_id' => $trackId, 'status' => $first, 'created_at' => $now,
            ]);
            $bot->audit->log($bot->tgId, 'create', 'tracks', $trackId, null, [
                'track_number' => (string) $data['track_number'],
                'status'       => $first,
            ]);

            if ($userId !== null) {
                $user = $bot->db->one('SELECT * FROM users WHERE id = :i', ['i' => $userId]);
                if ($user) {
                    $bot->notify->toUser((int) $user['tg_id'],
                        '📦 Для вас создан груз с трек-номером <b>'
                        . Format::esc((string) $data['track_number']) . "</b>\nСтатус: <b>"
                        . Format::esc($first) . '</b>');
                }
            }

            [$text2, $kb] = $this->render($trackId);
            $bot->send("✅ Трек создан.\n\n" . $text2, $kb);
            $bot->send('Готово.', Texts::mainMenu($bot->lang));
            return true;
        }

        return false;
    }
}
