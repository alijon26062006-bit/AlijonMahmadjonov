<?php

declare(strict_types=1);

namespace Bot;

/**
 * Step-by-step dialog for adding seasons/episodes to a series or anime.
 *
 * Flow: season number → episode number → video (forwarded from the private
 * channel, uploaded, or a link) → saved. Then "➕ Ещё серия" / "✅ Готово".
 * Large video files are never stored on the server — only a Telegram File ID
 * or a link is kept, and the bot delivers the episode inside the chat.
 */
final class EpisodeFlow
{
    public function __construct(
        private TelegramApi $api,
        private ContentRepo $repo,
        private StateStore $store
    ) {}

    /** Begin adding episodes to a given series/anime. */
    public function start(int $chatId, int $tid, int $movieId): void
    {
        $this->store->set($tid, 'ep_season', ['movie_id' => $movieId]);
        $this->api->sendMessage(
            $chatId,
            "\u{1F4FA} <b>\u{414}\u{43E}\u{431}\u{430}\u{432}\u{43B}\u{435}\u{43D}\u{438}\u{435} \u{441}\u{435}\u{440}\u{438}\u{438}</b>\n\n\u{412}\u{432}\u{435}\u{434}\u{438}\u{442}\u{435} \u{43D}\u{43E}\u{43C}\u{435}\u{440} <b>\u{441}\u{435}\u{437}\u{43E}\u{43D}\u{430}</b> (\u{447}\u{438}\u{441}\u{43B}\u{43E}):",
            $this->cancelInline()
        );
    }

    /** @return bool true if the message was consumed by this dialog. */
    public function handle(int $chatId, int $tid, array $message): bool
    {
        $state = $this->store->get($tid);
        if (!in_array($state['state'], ['ep_season', 'ep_episode', 'ep_video'], true)) {
            return false;
        }

        $text = trim((string) ($message['text'] ?? ''));
        if (in_array($text, ['/cancel', "\u{2716}\u{FE0F} \u{41E}\u{442}\u{43C}\u{435}\u{43D}\u{430}"], true)) {
            $this->store->clear($tid);
            $this->api->sendMessage($chatId, "\u{274C} \u{41E}\u{442}\u{43C}\u{435}\u{43D}\u{435}\u{43D}\u{43E}.", ['reply_markup' => json_encode(['remove_keyboard' => true])]);
            return true;
        }

        $payload = $state['payload'];

        return match ($state['state']) {
            'ep_season'  => $this->onSeason($chatId, $tid, $text, $payload),
            'ep_episode' => $this->onEpisode($chatId, $tid, $text, $payload),
            'ep_video'   => $this->onVideo($chatId, $tid, $message, $text, $payload),
            default      => false,
        };
    }

    private function onSeason(int $chatId, int $tid, string $text, array $payload): bool
    {
        $season = (int) preg_replace('/\D/', '', $text);
        if ($season <= 0) {
            $this->api->sendMessage($chatId, "\u{26A0}\u{FE0F} \u{412}\u{432}\u{435}\u{434}\u{438}\u{442}\u{435} \u{43D}\u{43E}\u{43C}\u{435}\u{440} \u{441}\u{435}\u{437}\u{43E}\u{43D}\u{430} \u{447}\u{438}\u{441}\u{43B}\u{43E}\u{43C} (\u{43D}\u{430}\u{43F}\u{440}\u{438}\u{43C}\u{435}\u{440} 1).", $this->cancelInline());
            return true;
        }
        $payload['season'] = $season;
        $this->store->set($tid, 'ep_episode', $payload);
        $this->api->sendMessage($chatId, "\u{421}\u{435}\u{437}\u{43E}\u{43D} {$season}. \u{422}\u{435}\u{43F}\u{435}\u{440}\u{44C} \u{432}\u{432}\u{435}\u{434}\u{438}\u{442}\u{435} \u{43D}\u{43E}\u{43C}\u{435}\u{440} <b>\u{441}\u{435}\u{440}\u{438}\u{438}</b> (\u{447}\u{438}\u{441}\u{43B}\u{43E}):", $this->cancelInline());
        return true;
    }

    private function onEpisode(int $chatId, int $tid, string $text, array $payload): bool
    {
        $episode = (int) preg_replace('/\D/', '', $text);
        if ($episode <= 0) {
            $this->api->sendMessage($chatId, "\u{26A0}\u{FE0F} \u{412}\u{432}\u{435}\u{434}\u{438}\u{442}\u{435} \u{43D}\u{43E}\u{43C}\u{435}\u{440} \u{441}\u{435}\u{440}\u{438}\u{438} \u{447}\u{438}\u{441}\u{43B}\u{43E}\u{43C} (\u{43D}\u{430}\u{43F}\u{440}\u{438}\u{43C}\u{435}\u{440} 1).", $this->cancelInline());
            return true;
        }
        $payload['episode'] = $episode;
        $this->store->set($tid, 'ep_video', $payload);
        $this->api->sendMessage(
            $chatId,
            "\u{421}\u{435}\u{437}\u{43E}\u{43D} {$payload['season']}, \u{441}\u{435}\u{440}\u{438}\u{44F} {$episode}.\n\n"
            . "\u{422}\u{435}\u{43F}\u{435}\u{440}\u{44C} \u{43F}\u{440}\u{438}\u{448}\u{43B}\u{438}\u{442}\u{435} \u{432}\u{438}\u{434}\u{435}\u{43E} \u{441}\u{435}\u{440}\u{438}\u{438}:\n"
            . "\u{2022} <b>\u{43F}\u{435}\u{440}\u{435}\u{448}\u{43B}\u{438}\u{442}\u{435} \u{438}\u{437} \u{437}\u{430}\u{43A}\u{440}\u{44B}\u{442}\u{43E}\u{433}\u{43E} \u{43A}\u{430}\u{43D}\u{430}\u{43B}\u{430}</b>, \u{438}\u{43B}\u{438}\n"
            . "\u{2022} \u{43E}\u{442}\u{43F}\u{440}\u{430}\u{432}\u{44C}\u{442}\u{435} \u{432}\u{438}\u{434}\u{435}\u{43E}\u{444}\u{430}\u{439}\u{43B}, \u{438}\u{43B}\u{438}\n"
            . "\u{2022} \u{43F}\u{440}\u{438}\u{448}\u{43B}\u{438}\u{442}\u{435} \u{441}\u{441}\u{44B}\u{43B}\u{43A}\u{443}.",
            $this->cancelInline()
        );
        return true;
    }

    private function onVideo(int $chatId, int $tid, array $message, string $text, array $payload): bool
    {
        $fileId = null;
        $url = null;

        if (!empty($message['video']['file_id'])) {
            $fileId = $message['video']['file_id'];
        } elseif (!empty($message['document']['file_id'])
            && str_starts_with((string) ($message['document']['mime_type'] ?? ''), 'video/')) {
            $fileId = $message['document']['file_id'];
        } elseif (preg_match('#^https?://#i', $text)) {
            $url = $text;
        } else {
            $this->api->sendMessage($chatId, "\u{26A0}\u{FE0F} \u{41F}\u{440}\u{438}\u{448}\u{43B}\u{438}\u{442}\u{435} \u{432}\u{438}\u{434}\u{435}\u{43E} (\u{43C}\u{43E}\u{436}\u{43D}\u{43E} \u{43F}\u{435}\u{440}\u{435}\u{441}\u{43B}\u{430}\u{442}\u{44C} \u{438}\u{437} \u{43A}\u{430}\u{43D}\u{430}\u{43B}\u{430}) \u{438}\u{43B}\u{438} \u{441}\u{441}\u{44B}\u{43B}\u{43A}\u{443} http\u{2026}", $this->cancelInline());
            return true;
        }

        $movieId = (int) $payload['movie_id'];
        $season  = (int) $payload['season'];
        $episode = (int) $payload['episode'];
        $this->repo->createEpisode($movieId, $season, $episode, $fileId, $url);

        $total = $this->repo->episodeCount($movieId);
        $this->store->clear($tid);

        // Auto-publish the episode into the private archive channel.
        $archiveNote = $this->postEpisodeToArchive($message, $movieId, $season, $episode, $fileId);

        $kb = ['inline_keyboard' => [
            [['text' => "\u{2795} \u{415}\u{449}\u{451} \u{441}\u{435}\u{440}\u{438}\u{44F}", 'callback_data' => 'ep:add:' . $movieId]],
            [['text' => "\u{2705} \u{413}\u{43E}\u{442}\u{43E}\u{432}\u{43E}", 'callback_data' => 'ep:done']],
        ]];
        $this->api->sendMessage(
            $chatId,
            "\u{2705} \u{421}\u{43E}\u{445}\u{440}\u{430}\u{43D}\u{435}\u{43D}\u{43E}: \u{421}\u{435}\u{437}\u{43E}\u{43D} {$season}, \u{441}\u{435}\u{440}\u{438}\u{44F} {$episode}.\n\u{412}\u{441}\u{435}\u{433}\u{43E} \u{441}\u{435}\u{440}\u{438}\u{439} \u{443} \u{441}\u{435}\u{440}\u{438}\u{430}\u{43B}\u{430}: <b>{$total}</b>.{$archiveNote}",
            ['reply_markup' => json_encode($kb)]
        );
        return true;
    }

    /**
     * Send the saved episode to the archive channel. Skips the repost when the
     * admin forwarded the video from that very channel (it is already there).
     * Returns a short status line for the admin confirmation message.
     */
    private function postEpisodeToArchive(array $message, int $movieId, int $season, int $episode, ?string $fileId): string
    {
        $channel = $this->repo->getSetting('archive_channel_id');
        if (!$channel || !$fileId) {
            return '';
        }

        // Forwarded from the archive channel itself -> already stored there.
        $originId = $message['forward_origin']['chat']['id']
            ?? ($message['forward_from_chat']['id'] ?? null);
        if ($originId !== null && (string) $originId === (string) $channel) {
            return "\n\u{1F4E1} \u{412}\u{438}\u{434}\u{435}\u{43E} \u{443}\u{436}\u{435} \u{432} \u{43A}\u{430}\u{43D}\u{430}\u{43B}\u{435}-\u{430}\u{440}\u{445}\u{438}\u{432}\u{435}.";
        }

        $play  = $this->repo->playable($movieId);
        $title = htmlspecialchars((string) ($play['title'] ?? ''), ENT_QUOTES);
        $cap   = "\u{1F4FA} <b>{$title}</b> \u{2014} \u{421}\u{435}\u{437}\u{43E}\u{43D} {$season}, \u{441}\u{435}\u{440}\u{438}\u{44F} {$episode} (#{$movieId})";

        $res = $this->api->sendVideo($channel, $fileId, $cap);
        return !empty($res['ok'])
            ? "\n\u{1F4E1} \u{421}\u{435}\u{440}\u{438}\u{44F} \u{43E}\u{442}\u{43F}\u{440}\u{430}\u{432}\u{43B}\u{435}\u{43D}\u{430} \u{432} \u{43A}\u{430}\u{43D}\u{430}\u{43B}-\u{430}\u{440}\u{445}\u{438}\u{432}."
            : "\n\u{26A0}\u{FE0F} \u{41D}\u{435} \u{443}\u{434}\u{430}\u{43B}\u{43E}\u{441}\u{44C} \u{43E}\u{442}\u{43F}\u{440}\u{430}\u{432}\u{438}\u{442}\u{44C} \u{432} \u{43A}\u{430}\u{43D}\u{430}\u{43B}-\u{430}\u{440}\u{445}\u{438}\u{432} (\u{431}\u{43E}\u{442} \u{434}\u{43E}\u{43B}\u{436}\u{435}\u{43D} \u{431}\u{44B}\u{442}\u{44C} \u{430}\u{434}\u{43C}\u{438}\u{43D}\u{43E}\u{43C} \u{43A}\u{430}\u{43D}\u{430}\u{43B}\u{430}).";
    }

    /** @return bool true if the callback belonged to this dialog. */
    public function handleCallback(int $chatId, int $tid, string $data, string $cbId): bool
    {
        if (str_starts_with($data, 'ep:add:')) {
            $movieId = (int) substr($data, 7);
            $this->api->answerCallbackQuery($cbId);
            $this->start($chatId, $tid, $movieId);
            return true;
        }
        if ($data === 'ep:done') {
            $this->api->answerCallbackQuery($cbId, "\u{413}\u{43E}\u{442}\u{43E}\u{432}\u{43E} \u{2705}");
            $this->store->clear($tid);
            $this->api->sendMessage($chatId, "\u{2705} \u{421}\u{435}\u{440}\u{438}\u{438} \u{441}\u{43E}\u{445}\u{440}\u{430}\u{43D}\u{435}\u{43D}\u{44B}. \u{41E}\u{43D}\u{438} \u{443}\u{436}\u{435} \u{432}\u{438}\u{434}\u{43D}\u{44B} \u{432} \u{43F}\u{440}\u{438}\u{43B}\u{43E}\u{436}\u{435}\u{43D}\u{438}\u{438} \u{43D}\u{430} \u{441}\u{442}\u{440}\u{430}\u{43D}\u{438}\u{446}\u{435} \u{441}\u{435}\u{440}\u{438}\u{430}\u{43B}\u{430}.");
            return true;
        }
        if ($data === 'ep:cancel') {
            $this->api->answerCallbackQuery($cbId, "\u{41E}\u{442}\u{43C}\u{435}\u{43D}\u{435}\u{43D}\u{43E}");
            $this->store->clear($tid);
            $this->api->sendMessage($chatId, "\u{274C} \u{41E}\u{442}\u{43C}\u{435}\u{43D}\u{435}\u{43D}\u{43E}.");
            return true;
        }
        return false;
    }

    private function cancelInline(): array
    {
        return ['reply_markup' => json_encode([
            'inline_keyboard' => [[['text' => "\u{274C} \u{41E}\u{442}\u{43C}\u{435}\u{43D}\u{430}", 'callback_data' => 'ep:cancel']]],
        ])];
    }
}
