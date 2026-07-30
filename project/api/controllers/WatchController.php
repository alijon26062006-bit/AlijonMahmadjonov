<?php

declare(strict_types=1);

namespace Controllers;

use Core\Controller;
use Core\Response;
use Models\Movie;
use Models\History;

/**
 * Handles the ▶ Смотреть action.
 *
 * The web server never streams large video files. When a movie has a Telegram
 * File ID, the film is delivered straight into the user's chat with the bot;
 * otherwise a watch/trailer link is returned for the Mini App to open.
 */
final class WatchController extends Controller
{
    /** POST /watch — {movie_id}. */
    public function store(): void
    {
        $user    = $this->authenticate(false); // delivery needs the user's chat id
        $movieId = (int) $this->input('movie_id', 0);
        if ($movieId <= 0) {
            Response::error('Missing movie_id', 422);
        }

        $movieModel = new Movie();
        $play = $movieModel->playable($movieId);
        if (!$play) {
            Response::error('Movie not found', 404);
        }

        // Analytics + "continue watching"
        $movieModel->incrementViews($movieId, $this->userId);
        if ($this->userId) {
            (new History())->record($this->userId, $movieId, 0);
        }

        // 1) Deliver the video through Telegram when we have a file id + a chat.
        $chatId = $user['id'] ?? null;
        if (!empty($play['telegram_file_id']) && $chatId) {
            require_once __DIR__ . '/../../bot/TelegramApi.php';
            $api = new \Bot\TelegramApi($this->config['telegram']['bot_token']);
            $caption = '🎬 <b>' . htmlspecialchars((string) $play['title'], ENT_QUOTES) . '</b>';
            $res = $api->sendVideo((int) $chatId, (string) $play['telegram_file_id'], $caption);

            if (!empty($res['ok'])) {
                Response::ok([
                    'via'       => 'telegram',
                    'delivered' => true,
                    'message'   => 'Фильм отправлен в чат с ботом',
                ]);
            }
            // Fall through to a link if Telegram delivery failed.
        }

        // 2) Otherwise return a link to open.
        $link = $play['watch_url'] ?: $play['trailer'];
        if ($link) {
            Response::ok([
                'via'       => 'link',
                'watch_url' => $link,
                'title'     => $play['title'],
            ]);
        }

        Response::error('Источник просмотра пока не добавлен', 404);
    }
}
