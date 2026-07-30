<?php

namespace Controllers;

use Core\Controller;
use Core\Response;
use Models\Movie;
use Models\History;
use Models\Episode;

/**
 * Handles the ▶ Смотреть action.
 *
 * The web server never streams large video files. When a movie has a Telegram
 * File ID, the film is delivered straight into the user's chat with the bot;
 * otherwise a watch/trailer link is returned for the Mini App to open.
 */
final class WatchController extends Controller
{
    /** POST /watch — {movie_id} or {episode_id}. */
    public function store(): void
    {
        $user      = $this->authenticate(false); // delivery needs the user's chat id
        $episodeId = (int) $this->input('episode_id', 0);

        // Episode delivery (series / anime).
        if ($episodeId > 0) {
            $this->deliverEpisode($episodeId, $user['id'] ?? null);
            return;
        }

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
            $caption = "\u{1F3AC} <b>" . htmlspecialchars((string) $play['title'], ENT_QUOTES) . '</b>';
            $res = $api->sendVideo((int) $chatId, (string) $play['telegram_file_id'], $caption);

            if (!empty($res['ok'])) {
                Response::ok([
                    'via'       => 'telegram',
                    'delivered' => true,
                    'message'   => "\u{424}\u{438}\u{43B}\u{44C}\u{43C} \u{43E}\u{442}\u{43F}\u{440}\u{430}\u{432}\u{43B}\u{435}\u{43D} \u{432} \u{447}\u{430}\u{442} \u{441} \u{431}\u{43E}\u{442}\u{43E}\u{43C}",
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

        Response::error("\u{418}\u{441}\u{442}\u{43E}\u{447}\u{43D}\u{438}\u{43A} \u{43F}\u{440}\u{43E}\u{441}\u{43C}\u{43E}\u{442}\u{440}\u{430} \u{43F}\u{43E}\u{43A}\u{430} \u{43D}\u{435} \u{434}\u{43E}\u{431}\u{430}\u{432}\u{43B}\u{435}\u{43D}", 404);
    }

    /** Deliver one series/anime episode via the bot, or return its link. */
    private function deliverEpisode(int $episodeId, $chatId): void
    {
        $ep = (new Episode())->playable($episodeId);
        if (!$ep) {
            Response::error('Episode not found', 404);
        }

        $caption = "\u{1F3AC} <b>" . htmlspecialchars((string) $ep['movie_title'], ENT_QUOTES) . "</b> \u{2014} "
            . 'S' . (int) $ep['season'] . 'E' . (int) $ep['episode'];

        if (!empty($ep['telegram_file_id']) && $chatId) {
            require_once __DIR__ . '/../../bot/TelegramApi.php';
            $api = new \Bot\TelegramApi($this->config['telegram']['bot_token']);
            $res = $api->sendVideo((int) $chatId, (string) $ep['telegram_file_id'], $caption);
            if (!empty($res['ok'])) {
                Response::ok(['via' => 'telegram', 'delivered' => true, 'message' => "\u{421}\u{435}\u{440}\u{438}\u{44F} \u{43E}\u{442}\u{43F}\u{440}\u{430}\u{432}\u{43B}\u{435}\u{43D}\u{430} \u{432} \u{447}\u{430}\u{442} \u{441} \u{431}\u{43E}\u{442}\u{43E}\u{43C}"]);
            }
        }

        if (!empty($ep['watch_url'])) {
            Response::ok(['via' => 'link', 'watch_url' => $ep['watch_url']]);
        }

        Response::error("\u{418}\u{441}\u{442}\u{43E}\u{447}\u{43D}\u{438}\u{43A} \u{441}\u{435}\u{440}\u{438}\u{438} \u{43F}\u{43E}\u{43A}\u{430} \u{43D}\u{435} \u{434}\u{43E}\u{431}\u{430}\u{432}\u{43B}\u{435}\u{43D}", 404);
    }
}
