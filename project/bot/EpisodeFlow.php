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
            "📺 <b>Добавление серии</b>\n\nВведите номер <b>сезона</b> (число):",
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
        if (in_array($text, ['/cancel', '✖️ Отмена'], true)) {
            $this->store->clear($tid);
            $this->api->sendMessage($chatId, '❌ Отменено.', ['reply_markup' => json_encode(['remove_keyboard' => true])]);
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
            $this->api->sendMessage($chatId, '⚠️ Введите номер сезона числом (например 1).', $this->cancelInline());
            return true;
        }
        $payload['season'] = $season;
        $this->store->set($tid, 'ep_episode', $payload);
        $this->api->sendMessage($chatId, "Сезон {$season}. Теперь введите номер <b>серии</b> (число):", $this->cancelInline());
        return true;
    }

    private function onEpisode(int $chatId, int $tid, string $text, array $payload): bool
    {
        $episode = (int) preg_replace('/\D/', '', $text);
        if ($episode <= 0) {
            $this->api->sendMessage($chatId, '⚠️ Введите номер серии числом (например 1).', $this->cancelInline());
            return true;
        }
        $payload['episode'] = $episode;
        $this->store->set($tid, 'ep_video', $payload);
        $this->api->sendMessage(
            $chatId,
            "Сезон {$payload['season']}, серия {$episode}.\n\n"
            . "Теперь пришлите видео серии:\n"
            . "• <b>перешлите из закрытого канала</b>, или\n"
            . "• отправьте видеофайл, или\n"
            . "• пришлите ссылку.",
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
            $this->api->sendMessage($chatId, '⚠️ Пришлите видео (можно переслать из канала) или ссылку http…', $this->cancelInline());
            return true;
        }

        $movieId = (int) $payload['movie_id'];
        $season  = (int) $payload['season'];
        $episode = (int) $payload['episode'];
        $this->repo->createEpisode($movieId, $season, $episode, $fileId, $url);

        $total = $this->repo->episodeCount($movieId);
        $this->store->clear($tid);

        $kb = ['inline_keyboard' => [
            [['text' => '➕ Ещё серия', 'callback_data' => 'ep:add:' . $movieId]],
            [['text' => '✅ Готово', 'callback_data' => 'ep:done']],
        ]];
        $this->api->sendMessage(
            $chatId,
            "✅ Сохранено: Сезон {$season}, серия {$episode}.\nВсего серий у сериала: <b>{$total}</b>.",
            ['reply_markup' => json_encode($kb)]
        );
        return true;
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
            $this->api->answerCallbackQuery($cbId, 'Готово ✅');
            $this->store->clear($tid);
            $this->api->sendMessage($chatId, '✅ Серии сохранены. Они уже видны в приложении на странице сериала.');
            return true;
        }
        if ($data === 'ep:cancel') {
            $this->api->answerCallbackQuery($cbId, 'Отменено');
            $this->store->clear($tid);
            $this->api->sendMessage($chatId, '❌ Отменено.');
            return true;
        }
        return false;
    }

    private function cancelInline(): array
    {
        return ['reply_markup' => json_encode([
            'inline_keyboard' => [[['text' => '❌ Отмена', 'callback_data' => 'ep:cancel']]],
        ])];
    }
}
