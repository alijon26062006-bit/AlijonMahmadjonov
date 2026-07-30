<?php

declare(strict_types=1);

namespace Bot;

use Core\ImageProcessor;
use Core\OpenAiClient;

/**
 * AI-assisted "add movie" wizard for administrators.
 *
 * Scenario:
 *   1. Admin sends a poster.
 *   2. The image is saved, its orientation detected, Smart-Cropped and rendered
 *      into WebP poster / thumbnail / banner / background renditions.
 *   3. The AI recognises the film from the poster; if it cannot, the admin is
 *      asked to type the title.
 *   4. The AI fills the whole card (title, descriptions, year, genres, country,
 *      director, actors, duration, age rating, rating, type, status, keywords,
 *      similar titles). Unknown fields stay empty for the admin to complete.
 *   5. An optional video (Telegram file) or watch link is attached — large video
 *      files are NOT stored on the web server, only the Telegram File ID / URL.
 *   6. A preview card is shown with ✅ Publish / ✏ Edit / ❌ Cancel.
 *
 * All state is kept in the `bot_states` table via StateStore.
 */
final class AiFlow
{
    private const CAT_LABELS = [
        'movie' => "\u{424}\u{438}\u{43B}\u{44C}\u{43C}", 'series' => "\u{421}\u{435}\u{440}\u{438}\u{430}\u{43B}",
        'anime' => "\u{410}\u{43D}\u{438}\u{43C}\u{435}", 'cartoon' => "\u{41C}\u{443}\u{43B}\u{44C}\u{442}\u{444}\u{438}\u{43B}\u{44C}\u{43C}",
    ];
    private const STATUS_LABELS = [
        'published' => "\u{41E}\u{43F}\u{443}\u{431}\u{43B}\u{438}\u{43A}\u{43E}\u{432}\u{430}\u{43D}", 'coming_soon' => "\u{421}\u{43A}\u{43E}\u{440}\u{43E} \u{432}\u{44B}\u{439}\u{434}\u{435}\u{442}",
        'in_cinema' => "\u{421}\u{435}\u{439}\u{447}\u{430}\u{441} \u{432} \u{43A}\u{438}\u{43D}\u{43E}", 'draft' => "\u{427}\u{435}\u{440}\u{43D}\u{43E}\u{432}\u{438}\u{43A}",
    ];

    public function __construct(
        private TelegramApi $api,
        private Media $media,
        private ContentRepo $repo,
        private StateStore $store,
        private ImageProcessor $img,
        private OpenAiClient $ai,
        private string $uploadsDir,
        private string $miniappUrl
    ) {}

    /** Start the AI wizard. */
    public function start(int $chatId, int $tid): void
    {
        $this->store->set($tid, 'ai_poster', ['data' => [], 'images' => []]);
        $note = $this->ai->isEnabled()
            ? "AI \u{440}\u{430}\u{441}\u{43F}\u{43E}\u{437}\u{43D}\u{430}\u{435}\u{442} \u{444}\u{438}\u{43B}\u{44C}\u{43C} \u{438} \u{441}\u{430}\u{43C} \u{437}\u{430}\u{43F}\u{43E}\u{43B}\u{43D}\u{438}\u{442} \u{43A}\u{430}\u{440}\u{442}\u{43E}\u{447}\u{43A}\u{443}."
            : "\u{26A0}\u{FE0F} AI-\u{43A}\u{43B}\u{44E}\u{447} \u{43D}\u{435} \u{43D}\u{430}\u{441}\u{442}\u{440}\u{43E}\u{435}\u{43D} \u{2014} \u{43A}\u{430}\u{440}\u{442}\u{43E}\u{447}\u{43A}\u{443} \u{43D}\u{443}\u{436}\u{43D}\u{43E} \u{431}\u{443}\u{434}\u{435}\u{442} \u{437}\u{430}\u{43F}\u{43E}\u{43B}\u{43D}\u{438}\u{442}\u{44C} \u{432}\u{440}\u{443}\u{447}\u{43D}\u{443}\u{44E}, \u{43D}\u{43E} \u{43F}\u{43E}\u{441}\u{442}\u{435}\u{440} \u{43E}\u{431}\u{440}\u{430}\u{431}\u{43E}\u{442}\u{430}\u{435}\u{442}\u{441}\u{44F} \u{430}\u{432}\u{442}\u{43E}\u{43C}\u{430}\u{442}\u{438}\u{447}\u{435}\u{441}\u{43A}\u{438}.";
        $this->api->sendMessage(
            $chatId,
            "\u{1F916} <b>AI-\u{434}\u{43E}\u{431}\u{430}\u{432}\u{43B}\u{435}\u{43D}\u{438}\u{435} \u{444}\u{438}\u{43B}\u{44C}\u{43C}\u{430}</b>\n\n<b>\u{428}\u{430}\u{433} 1.</b> \u{41E}\u{442}\u{43F}\u{440}\u{430}\u{432}\u{44C}\u{442}\u{435} \u{43F}\u{43E}\u{441}\u{442}\u{435}\u{440} \u{444}\u{438}\u{43B}\u{44C}\u{43C}\u{430} \u{1F5BC}\n\n{$note}\n\n"
            . "\u{412} \u{43B}\u{44E}\u{431}\u{43E}\u{439} \u{43C}\u{43E}\u{43C}\u{435}\u{43D}\u{442} \u{43C}\u{43E}\u{436}\u{43D}\u{43E} \u{43D}\u{430}\u{436}\u{430}\u{442}\u{44C} \u{AB}\u{274C} \u{41E}\u{442}\u{43C}\u{435}\u{43D}\u{430}\u{BB} \u{438}\u{43B}\u{438} \u{43E}\u{442}\u{43F}\u{440}\u{430}\u{432}\u{438}\u{442}\u{44C} /start.",
            $this->cancelInline()
        );
    }

    /**
     * Feed an incoming message to the active AI dialog.
     * @return bool true if the message was consumed.
     */
    public function handle(int $chatId, int $tid, array $message): bool
    {
        $state = $this->store->get($tid);
        if (!in_array($state['state'], ['ai_poster', 'ai_title', 'ai_video', 'ai_edit', 'ai_confirm'], true)) {
            return false;
        }

        $text = trim((string) ($message['text'] ?? ''));
        if (in_array($text, ['/cancel', "\u{2716}\u{FE0F} \u{41E}\u{442}\u{43C}\u{435}\u{43D}\u{430}"], true)) {
            $this->cleanup($state['payload']);
            $this->store->clear($tid);
            $this->api->sendMessage($chatId, "\u{274C} \u{414}\u{43E}\u{431}\u{430}\u{432}\u{43B}\u{435}\u{43D}\u{438}\u{435} \u{43E}\u{442}\u{43C}\u{435}\u{43D}\u{435}\u{43D}\u{43E}.", $this->removeKeyboard());
            return true;
        }

        return match ($state['state']) {
            'ai_poster' => $this->onPoster($chatId, $tid, $message, $state['payload']),
            'ai_title'  => $this->onTitle($chatId, $tid, $text, $state['payload']),
            'ai_video'  => $this->onVideo($chatId, $tid, $message, $text, $state['payload']),
            'ai_edit'   => $this->onEditValue($chatId, $tid, $message, $text, $state['payload']),
            'ai_confirm'=> $this->onConfirmStray($chatId),
            default     => false,
        };
    }

    // ---- Steps ----------------------------------------------------------

    private function onPoster(int $chatId, int $tid, array $message, array $payload): bool
    {
        $fileId = Media::largestPhotoId($message['photo'] ?? []);
        if (!$fileId && !empty($message['document']['file_id'])
            && str_starts_with((string) ($message['document']['mime_type'] ?? ''), 'image/')) {
            $fileId = $message['document']['file_id'];
        }
        if (!$fileId) {
            $this->api->sendMessage($chatId, "\u{26A0}\u{FE0F} \u{41F}\u{440}\u{438}\u{448}\u{43B}\u{438}\u{442}\u{435} \u{438}\u{43C}\u{435}\u{43D}\u{43D}\u{43E} \u{438}\u{437}\u{43E}\u{431}\u{440}\u{430}\u{436}\u{435}\u{43D}\u{438}\u{435} (\u{43F}\u{43E}\u{441}\u{442}\u{435}\u{440}).");
            return true;
        }

        $this->api->call('sendChatAction', ['chat_id' => $chatId, 'action' => 'upload_photo']);
        $this->api->sendMessage($chatId, "\u{23F3} \u{41E}\u{431}\u{440}\u{430}\u{431}\u{430}\u{442}\u{44B}\u{432}\u{430}\u{44E} \u{43F}\u{43E}\u{441}\u{442}\u{435}\u{440}: Smart Crop, \u{431}\u{430}\u{43D}\u{43D}\u{435}\u{440}, WebP\u{2026}");

        // Download the original for processing (removed afterwards).
        $rel = $this->media->save($fileId, 'tmp', 'jpg');
        if ($rel === null) {
            $this->api->sendMessage($chatId, "\u{26A0}\u{FE0F} \u{41D}\u{435} \u{443}\u{434}\u{430}\u{43B}\u{43E}\u{441}\u{44C} \u{441}\u{43E}\u{445}\u{440}\u{430}\u{43D}\u{438}\u{442}\u{44C} \u{438}\u{437}\u{43E}\u{431}\u{440}\u{430}\u{436}\u{435}\u{43D}\u{438}\u{435}. \u{41F}\u{43E}\u{43F}\u{440}\u{43E}\u{431}\u{443}\u{439}\u{442}\u{435} \u{435}\u{449}\u{451} \u{440}\u{430}\u{437}.");
            return true;
        }
        $originalAbs = $this->uploadsDir . '/' . $rel;

        // Run all image + AI work on the original, then delete it.
        $focal  = $this->ai->focalPoint($originalAbs);      // protect faces / title
        $images = $this->img->process($originalAbs, $focal);
        $ident  = $this->ai->identifyTitle($originalAbs);   // recognise the film
        @unlink($originalAbs);

        $payload['images']         = $images;
        $payload['poster_file_id'] = $fileId; // used for the preview (free, no upload)

        if ($ident && $ident['title'] !== '') {
            $payload['data']['title']          = $ident['title'];
            $payload['data']['original_title'] = $ident['original_title'];
            if ($ident['year']) {
                $payload['data']['year'] = $ident['year'];
            }
            $this->api->sendMessage(
                $chatId,
                "\u{1F50E} \u{420}\u{430}\u{441}\u{43F}\u{43E}\u{437}\u{43D}\u{430}\u{43D}\u{43E}: <b>{$ident['title']}</b>"
                . ($ident['year'] ? " ({$ident['year']})" : '')
                . "\n\u{1F916} \u{417}\u{430}\u{43F}\u{43E}\u{43B}\u{43D}\u{44F}\u{44E} \u{43A}\u{430}\u{440}\u{442}\u{43E}\u{447}\u{43A}\u{443}\u{2026}"
            );
            $this->enrichAndAskVideo($chatId, $tid, $ident['title'], $ident['year'] ?? null, $ident['type'] ?? null, $payload);
            return true;
        }

        // Could not recognise -> ask for the title manually.
        $this->store->set($tid, 'ai_title', $payload);
        $this->api->sendMessage(
            $chatId,
            "\u{1F914} \u{41D}\u{435} \u{443}\u{434}\u{430}\u{43B}\u{43E}\u{441}\u{44C} \u{442}\u{43E}\u{447}\u{43D}\u{43E} \u{440}\u{430}\u{441}\u{43F}\u{43E}\u{437}\u{43D}\u{430}\u{442}\u{44C} \u{444}\u{438}\u{43B}\u{44C}\u{43C}.\n<b>\u{41D}\u{430}\u{43F}\u{438}\u{448}\u{438}\u{442}\u{435} \u{43D}\u{430}\u{437}\u{432}\u{430}\u{43D}\u{438}\u{435} \u{432}\u{440}\u{443}\u{447}\u{43D}\u{443}\u{44E}:</b>",
            $this->cancelInline()
        );
        return true;
    }

    private function onTitle(int $chatId, int $tid, string $text, array $payload): bool
    {
        if ($text === '') {
            $this->api->sendMessage($chatId, "\u{26A0}\u{FE0F} \u{412}\u{432}\u{435}\u{434}\u{438}\u{442}\u{435} \u{43D}\u{430}\u{437}\u{432}\u{430}\u{43D}\u{438}\u{435} \u{442}\u{435}\u{43A}\u{441}\u{442}\u{43E}\u{43C}.");
            return true;
        }
        $payload['data']['title'] = $text;
        $this->api->sendMessage($chatId, "\u{1F916} \u{421}\u{43E}\u{431}\u{438}\u{440}\u{430}\u{44E} \u{438}\u{43D}\u{444}\u{43E}\u{440}\u{43C}\u{430}\u{446}\u{438}\u{44E} \u{43E} \u{AB}<b>{$text}</b>\u{BB}\u{2026}");
        $this->enrichAndAskVideo($chatId, $tid, $text, $payload['data']['year'] ?? null, null, $payload);
        return true;
    }

    private function onVideo(int $chatId, int $tid, array $message, string $text, array $payload): bool
    {
        if (!empty($message['video']['file_id'])) {
            $payload['data']['telegram_file_id'] = $message['video']['file_id'];
        } elseif (!empty($message['document']['file_id'])
            && str_starts_with((string) ($message['document']['mime_type'] ?? ''), 'video/')) {
            $payload['data']['telegram_file_id'] = $message['document']['file_id'];
        } elseif (preg_match('#^https?://#i', $text)) {
            $payload['data']['watch_url'] = $text;
        } elseif (!$this->isSkip($text)) {
            $this->api->sendMessage($chatId, "\u{26A0}\u{FE0F} \u{41F}\u{440}\u{438}\u{448}\u{43B}\u{438}\u{442}\u{435} \u{432}\u{438}\u{434}\u{435}\u{43E}\u{444}\u{430}\u{439}\u{43B}, \u{441}\u{441}\u{44B}\u{43B}\u{43A}\u{443} (http\u{2026}) \u{438}\u{43B}\u{438} \u{AB}-\u{BB}, \u{447}\u{442}\u{43E}\u{431}\u{44B} \u{43F}\u{440}\u{43E}\u{43F}\u{443}\u{441}\u{442}\u{438}\u{442}\u{44C}.");
            return true;
        }
        $this->showConfirmation($chatId, $tid, $payload);
        return true;
    }

    // ---- AI enrichment --------------------------------------------------

    private function enrichAndAskVideo(int $chatId, int $tid, string $title, ?int $year, ?string $type, array $payload): void
    {
        $enriched = $this->ai->enrich($title, $year, $type);
        if ($enriched) {
            // Keep any values already captured (title/year/original from vision).
            foreach ($enriched as $k => $v) {
                if ($v === '' || $v === null || (is_array($v) && !$v)) {
                    continue;
                }
                if (!isset($payload['data'][$k]) || $payload['data'][$k] === '' || $payload['data'][$k] === null) {
                    $payload['data'][$k] = $v;
                }
            }
        }
        $payload['data']['title']    = $payload['data']['title'] ?? $title;
        $payload['data']['category'] = $payload['data']['category'] ?? ($type ?? 'movie');
        $payload['data']['status']   = $payload['data']['status'] ?? 'published';
        if (!isset($payload['data']['genres'])) {
            $payload['data']['genres'] = [];
        }

        $this->store->set($tid, 'ai_video', $payload);
        $this->api->sendMessage(
            $chatId,
            "<b>\u{428}\u{430}\u{433} 2.</b> \u{412}\u{438}\u{434}\u{435}\u{43E} \u{444}\u{438}\u{43B}\u{44C}\u{43C}\u{430} (\u{447}\u{442}\u{43E}\u{431}\u{44B} \u{440}\u{430}\u{431}\u{43E}\u{442}\u{430}\u{43B}\u{430} \u{43A}\u{43D}\u{43E}\u{43F}\u{43A}\u{430} \u{AB}\u{421}\u{43C}\u{43E}\u{442}\u{440}\u{435}\u{442}\u{44C}\u{BB}):\n"
            . "\u{2022} <b>\u{43F}\u{435}\u{440}\u{435}\u{448}\u{43B}\u{438}\u{442}\u{435} \u{432}\u{438}\u{434}\u{435}\u{43E} \u{438}\u{437} \u{432}\u{430}\u{448}\u{435}\u{433}\u{43E} \u{437}\u{430}\u{43A}\u{440}\u{44B}\u{442}\u{43E}\u{433}\u{43E} \u{43A}\u{430}\u{43D}\u{430}\u{43B}\u{430}</b>, \u{438}\u{43B}\u{438}\n"
            . "\u{2022} \u{43E}\u{442}\u{43F}\u{440}\u{430}\u{432}\u{44C}\u{442}\u{435} \u{432}\u{438}\u{434}\u{435}\u{43E}\u{444}\u{430}\u{439}\u{43B}, \u{438}\u{43B}\u{438}\n"
            . "\u{2022} \u{43F}\u{440}\u{438}\u{448}\u{43B}\u{438}\u{442}\u{435} \u{441}\u{441}\u{44B}\u{43B}\u{43A}\u{443}.\n\n"
            . "\u{411}\u{43E}\u{43B}\u{44C}\u{448}\u{438}\u{435} \u{432}\u{438}\u{434}\u{435}\u{43E} \u{43D}\u{430} \u{441}\u{435}\u{440}\u{432}\u{435}\u{440}\u{435} \u{43D}\u{435} \u{445}\u{440}\u{430}\u{43D}\u{44F}\u{442}\u{441}\u{44F} \u{2014} \u{431}\u{43E}\u{442} \u{43E}\u{442}\u{434}\u{430}\u{451}\u{442} \u{438}\u{445} \u{441}\u{430}\u{43C}, \u{432}\u{43D}\u{443}\u{442}\u{440}\u{438} \u{447}\u{430}\u{442}\u{430}.\n"
            . "\u{41C}\u{43E}\u{436}\u{43D}\u{43E} \u{AB}\u{23ED} \u{41F}\u{440}\u{43E}\u{43F}\u{443}\u{441}\u{442}\u{438}\u{442}\u{44C}\u{BB}.",
            $this->skipCancelInline()
        );
    }

    // ---- Confirmation ---------------------------------------------------

    private function showConfirmation(int $chatId, int $tid, array $payload): void
    {
        $this->store->set($tid, 'ai_confirm', $payload);
        $d = $payload['data'];

        $caption = $this->cardCaption($d);
        $kb = ['inline_keyboard' => [
            [['text' => "\u{2705} \u{41E}\u{43F}\u{443}\u{431}\u{43B}\u{438}\u{43A}\u{43E}\u{432}\u{430}\u{442}\u{44C}", 'callback_data' => 'aic:pub']],
            [['text' => "\u{270F} \u{420}\u{435}\u{434}\u{430}\u{43A}\u{442}\u{438}\u{440}\u{43E}\u{432}\u{430}\u{442}\u{44C}", 'callback_data' => 'aic:edit'],
             ['text' => "\u{274C} \u{41E}\u{442}\u{43C}\u{435}\u{43D}\u{430}", 'callback_data' => 'aic:cancel']],
        ]];

        $extra = ['reply_markup' => json_encode($kb)];
        // Remove the reply keyboard first, then show the preview card with poster.
        $this->api->sendMessage($chatId, "\u{1F447} \u{41F}\u{440}\u{43E}\u{432}\u{435}\u{440}\u{44C}\u{442}\u{435} \u{43A}\u{430}\u{440}\u{442}\u{43E}\u{447}\u{43A}\u{443} \u{43F}\u{435}\u{440}\u{435}\u{434} \u{43F}\u{443}\u{431}\u{43B}\u{438}\u{43A}\u{430}\u{446}\u{438}\u{435}\u{439}:", $this->removeKeyboard());

        if (!empty($payload['poster_file_id'])) {
            $this->api->sendPhoto($chatId, $payload['poster_file_id'], $caption, $extra);
        } else {
            $this->api->sendMessage($chatId, $caption, $extra);
        }
    }

    private function cardCaption(array $d): string
    {
        $e = static fn ($v) => htmlspecialchars((string) $v, ENT_QUOTES);
        $genres = !empty($d['genres'])
            ? implode(', ', array_map($e, (array) $d['genres']))
            : "\u{2014}";
        $meta = array_filter([
            !empty($d['rating']) ? "\u{2B50} " . number_format((float) $d['rating'], 1) : null,
            !empty($d['age_rating']) ? $e($d['age_rating']) : null,
            !empty($d['duration']) ? $d['duration'] . " \u{43C}\u{438}\u{43D}" : null,
        ]);
        $desc = $d['description_short'] ?? $d['description'] ?? '';
        if (mb_strlen((string) $desc) > 350) {
            $desc = mb_substr((string) $desc, 0, 350) . "\u{2026}";
        }

        return "\u{1F3AC} <b>" . $e($d['title'] ?? '') . "</b>"
            . (!empty($d['year']) ? " ({$d['year']})" : '') . "\n"
            . (!empty($d['original_title']) ? '<i>' . $e($d['original_title']) . "</i>\n" : '')
            . (!empty($meta) ? implode(" \u{2022} ", $meta) . "\n" : '')
            . "\n\u{1F3F7} " . (self::CAT_LABELS[$d['category'] ?? 'movie'] ?? "\u{424}\u{438}\u{43B}\u{44C}\u{43C}")
            . " \u{B7} " . (self::STATUS_LABELS[$d['status'] ?? 'published'] ?? "\u{41E}\u{43F}\u{443}\u{431}\u{43B}\u{438}\u{43A}\u{43E}\u{432}\u{430}\u{43D}") . "\n"
            . "\u{1F3AD} {$genres}\n"
            . (!empty($d['country']) ? "\u{1F30D} " . $e($d['country']) . "\n" : '')
            . (!empty($d['director']) ? "\u{1F3A5} " . $e($d['director']) . "\n" : '')
            . (!empty($d['actors']) ? "\u{1F465} " . $e($d['actors']) . "\n" : '')
            . ($desc !== '' ? "\n\u{1F4DD} " . $e($desc) : '');
    }

    private function onConfirmStray(int $chatId): bool
    {
        $this->api->sendMessage($chatId, "\u{418}\u{441}\u{43F}\u{43E}\u{43B}\u{44C}\u{437}\u{443}\u{439}\u{442}\u{435} \u{43A}\u{43D}\u{43E}\u{43F}\u{43A}\u{438} \u{43F}\u{43E}\u{434} \u{43A}\u{430}\u{440}\u{442}\u{43E}\u{447}\u{43A}\u{43E}\u{439}: \u{2705} / \u{270F} / \u{274C}");
        return true;
    }

    // ---- Callbacks ------------------------------------------------------

    /** @return bool true if the callback belonged to the AI wizard. */
    public function handleCallback(int $chatId, int $tid, int $msgId, string $data, string $cbId): bool
    {
        if ($data === 'ai:add') {
            $this->api->answerCallbackQuery($cbId);
            $this->start($chatId, $tid);
            return true;
        }

        $state = $this->store->get($tid);
        $inAi  = str_starts_with($data, 'aic:') || str_starts_with($data, 'aif:');
        if (!$inAi) {
            return false;
        }
        $payload = $state['payload'];

        if ($data === 'aic:cancel') {
            $this->api->answerCallbackQuery($cbId, "\u{41E}\u{442}\u{43C}\u{435}\u{43D}\u{435}\u{43D}\u{43E}");
            $this->cleanup($payload);
            $this->store->clear($tid);
            $this->api->sendMessage($chatId, "\u{274C} \u{414}\u{43E}\u{431}\u{430}\u{432}\u{43B}\u{435}\u{43D}\u{438}\u{435} \u{43E}\u{442}\u{43C}\u{435}\u{43D}\u{435}\u{43D}\u{43E}.");
            return true;
        }

        if ($data === 'aic:skipvideo') {
            $this->api->answerCallbackQuery($cbId, "\u{41F}\u{440}\u{43E}\u{43F}\u{443}\u{449}\u{435}\u{43D}\u{43E}");
            if ($state['state'] === 'ai_video') {
                $this->showConfirmation($chatId, $tid, $payload);
            }
            return true;
        }

        if ($data === 'aic:pub') {
            $this->api->answerCallbackQuery($cbId, "\u{41F}\u{443}\u{431}\u{43B}\u{438}\u{43A}\u{443}\u{44E}\u{2026}");
            $this->publish($chatId, $tid, $payload);
            return true;
        }

        if ($data === 'aic:back') {
            $this->api->answerCallbackQuery($cbId);
            $this->showConfirmation($chatId, $tid, $payload);
            return true;
        }

        if ($data === 'aic:edit') {
            $this->api->answerCallbackQuery($cbId);
            $this->sendEditMenu($chatId);
            return true;
        }

        if (str_starts_with($data, 'aif:')) {
            $this->api->answerCallbackQuery($cbId);
            $field = substr($data, 4);
            $this->promptEdit($chatId, $tid, $field, $payload);
            return true;
        }

        return false;
    }

    private function sendEditMenu(int $chatId): void
    {
        $b = static fn (string $label, string $f) => ['text' => $label, 'callback_data' => 'aif:' . $f];
        $kb = ['inline_keyboard' => [
            [$b("\u{1F4DD} \u{41D}\u{430}\u{437}\u{432}\u{430}\u{43D}\u{438}\u{435}", 'title'), $b("\u{1F5D3} \u{413}\u{43E}\u{434}", 'year')],
            [$b("\u{1F4C4} \u{41E}\u{43F}\u{438}\u{441}\u{430}\u{43D}\u{438}\u{435}", 'description'), $b("\u{1F3AD} \u{416}\u{430}\u{43D}\u{440}\u{44B}", 'genres')],
            [$b("\u{1F30D} \u{421}\u{442}\u{440}\u{430}\u{43D}\u{430}", 'country'), $b("\u{1F3A5} \u{420}\u{435}\u{436}\u{438}\u{441}\u{441}\u{451}\u{440}", 'director')],
            [$b("\u{1F465} \u{410}\u{43A}\u{442}\u{451}\u{440}\u{44B}", 'actors'), $b("\u{23F1} \u{414}\u{43B}\u{438}\u{442}\u{435}\u{43B}\u{44C}\u{43D}\u{43E}\u{441}\u{442}\u{44C}", 'duration')],
            [$b("\u{2B50} \u{420}\u{435}\u{439}\u{442}\u{438}\u{43D}\u{433}", 'rating'), $b("\u{1F51E} \u{412}\u{43E}\u{437}\u{440}\u{430}\u{441}\u{442}", 'age_rating')],
            [$b("\u{1F3F7} \u{41A}\u{430}\u{442}\u{435}\u{433}\u{43E}\u{440}\u{438}\u{44F}", 'category'), $b("\u{1F4CC} \u{421}\u{442}\u{430}\u{442}\u{443}\u{441}", 'status')],
            [$b("\u{25B6}\u{FE0F} \u{412}\u{438}\u{434}\u{435}\u{43E}/\u{441}\u{441}\u{44B}\u{43B}\u{43A}\u{430}", 'video')],
            [['text' => "\u{2B05}\u{FE0F} \u{41D}\u{430}\u{437}\u{430}\u{434} \u{43A} \u{43A}\u{430}\u{440}\u{442}\u{43E}\u{447}\u{43A}\u{435}", 'callback_data' => 'aic:back']],
        ]];
        $this->api->sendMessage($chatId, "\u{270F} <b>\u{427}\u{442}\u{43E} \u{438}\u{437}\u{43C}\u{435}\u{43D}\u{438}\u{442}\u{44C}?</b>", ['reply_markup' => json_encode($kb)]);
    }

    private function promptEdit(int $chatId, int $tid, string $field, array $payload): void
    {
        $payload['edit_field'] = $field;
        $this->store->set($tid, 'ai_edit', $payload);

        if ($field === 'category') {
            $rows = [[['text' => "\u{424}\u{438}\u{43B}\u{44C}\u{43C}"]], [['text' => "\u{421}\u{435}\u{440}\u{438}\u{430}\u{43B}"]], [['text' => "\u{41C}\u{443}\u{43B}\u{44C}\u{442}\u{444}\u{438}\u{43B}\u{44C}\u{43C}"]], [['text' => "\u{410}\u{43D}\u{438}\u{43C}\u{435}"]], [['text' => "\u{2716}\u{FE0F} \u{41E}\u{442}\u{43C}\u{435}\u{43D}\u{430}"]]];
            $this->api->sendMessage($chatId, "\u{412}\u{44B}\u{431}\u{435}\u{440}\u{438}\u{442}\u{435} \u{43A}\u{430}\u{442}\u{435}\u{433}\u{43E}\u{440}\u{438}\u{44E}:", ['reply_markup' => json_encode(['keyboard' => $rows, 'resize_keyboard' => true, 'one_time_keyboard' => true])]);
            return;
        }
        if ($field === 'status') {
            $rows = [[['text' => "\u{41E}\u{43F}\u{443}\u{431}\u{43B}\u{438}\u{43A}\u{43E}\u{432}\u{430}\u{442}\u{44C}"]], [['text' => "\u{421}\u{43A}\u{43E}\u{440}\u{43E} \u{432}\u{44B}\u{439}\u{434}\u{435}\u{442}"]], [['text' => "\u{421}\u{435}\u{439}\u{447}\u{430}\u{441} \u{432} \u{43A}\u{438}\u{43D}\u{43E}"]], [['text' => "\u{2716}\u{FE0F} \u{41E}\u{442}\u{43C}\u{435}\u{43D}\u{430}"]]];
            $this->api->sendMessage($chatId, "\u{412}\u{44B}\u{431}\u{435}\u{440}\u{438}\u{442}\u{435} \u{441}\u{442}\u{430}\u{442}\u{443}\u{441}:", ['reply_markup' => json_encode(['keyboard' => $rows, 'resize_keyboard' => true, 'one_time_keyboard' => true])]);
            return;
        }

        $prompts = [
            'title' => "\u{1F4DD} \u{41D}\u{43E}\u{432}\u{43E}\u{435} \u{43D}\u{430}\u{437}\u{432}\u{430}\u{43D}\u{438}\u{435}:", 'year' => "\u{1F5D3} \u{413}\u{43E}\u{434} (\u{447}\u{438}\u{441}\u{43B}\u{43E}):",
            'description' => "\u{1F4C4} \u{41E}\u{43F}\u{438}\u{441}\u{430}\u{43D}\u{438}\u{435}:", 'genres' => "\u{1F3AD} \u{416}\u{430}\u{43D}\u{440}\u{44B} \u{447}\u{435}\u{440}\u{435}\u{437} \u{437}\u{430}\u{43F}\u{44F}\u{442}\u{443}\u{44E}:",
            'country' => "\u{1F30D} \u{421}\u{442}\u{440}\u{430}\u{43D}\u{430}:", 'director' => "\u{1F3A5} \u{420}\u{435}\u{436}\u{438}\u{441}\u{441}\u{451}\u{440}:",
            'actors' => "\u{1F465} \u{410}\u{43A}\u{442}\u{451}\u{440}\u{44B} \u{447}\u{435}\u{440}\u{435}\u{437} \u{437}\u{430}\u{43F}\u{44F}\u{442}\u{443}\u{44E}:", 'duration' => "\u{23F1} \u{414}\u{43B}\u{438}\u{442}\u{435}\u{43B}\u{44C}\u{43D}\u{43E}\u{441}\u{442}\u{44C} \u{432} \u{43C}\u{438}\u{43D}\u{443}\u{442}\u{430}\u{445}:",
            'rating' => "\u{2B50} \u{420}\u{435}\u{439}\u{442}\u{438}\u{43D}\u{433} 0\u{2013}10:", 'age_rating' => "\u{1F51E} \u{412}\u{43E}\u{437}\u{440}\u{430}\u{441}\u{442} (0+,6+,12+,16+,18+):",
            'video' => "\u{25B6}\u{FE0F} \u{41F}\u{440}\u{438}\u{448}\u{43B}\u{438}\u{442}\u{435} \u{432}\u{438}\u{434}\u{435}\u{43E}\u{444}\u{430}\u{439}\u{43B} \u{438}\u{43B}\u{438} \u{441}\u{441}\u{44B}\u{43B}\u{43A}\u{443} (http\u{2026}):",
        ];
        $this->api->sendMessage($chatId, $prompts[$field] ?? "\u{41D}\u{43E}\u{432}\u{43E}\u{435} \u{437}\u{43D}\u{430}\u{447}\u{435}\u{43D}\u{438}\u{435}:", ['reply_markup' => json_encode(['keyboard' => [[['text' => "\u{2716}\u{FE0F} \u{41E}\u{442}\u{43C}\u{435}\u{43D}\u{430}"]]], 'resize_keyboard' => true])]);
    }

    private function onEditValue(int $chatId, int $tid, array $message, string $text, array $payload): bool
    {
        $field = $payload['edit_field'] ?? '';
        unset($payload['edit_field']);

        switch ($field) {
            case 'year':
            case 'duration':
                $payload['data'][$field] = (int) preg_replace('/\D/', '', $text) ?: null;
                break;
            case 'rating':
                $payload['data']['rating'] = max(0, min(10, (float) str_replace(',', '.', $text)));
                break;
            case 'genres':
                $payload['data']['genres'] = array_values(array_filter(array_map('trim', explode(',', $text))));
                break;
            case 'category':
                $map = ["\u{424}\u{438}\u{43B}\u{44C}\u{43C}" => 'movie', "\u{421}\u{435}\u{440}\u{438}\u{430}\u{43B}" => 'series', "\u{41C}\u{443}\u{43B}\u{44C}\u{442}\u{444}\u{438}\u{43B}\u{44C}\u{43C}" => 'cartoon', "\u{410}\u{43D}\u{438}\u{43C}\u{435}" => 'anime'];
                $payload['data']['category'] = $map[$text] ?? ($payload['data']['category'] ?? 'movie');
                break;
            case 'status':
                $map = ["\u{41E}\u{43F}\u{443}\u{431}\u{43B}\u{438}\u{43A}\u{43E}\u{432}\u{430}\u{442}\u{44C}" => 'published', "\u{421}\u{43A}\u{43E}\u{440}\u{43E} \u{432}\u{44B}\u{439}\u{434}\u{435}\u{442}" => 'coming_soon', "\u{421}\u{435}\u{439}\u{447}\u{430}\u{441} \u{432} \u{43A}\u{438}\u{43D}\u{43E}" => 'in_cinema'];
                $payload['data']['status'] = $map[$text] ?? ($payload['data']['status'] ?? 'published');
                break;
            case 'video':
                if (!empty($message['video']['file_id'])) {
                    $payload['data']['telegram_file_id'] = $message['video']['file_id'];
                    $payload['data']['watch_url'] = null;
                } elseif (preg_match('#^https?://#i', $text)) {
                    $payload['data']['watch_url'] = $text;
                    $payload['data']['telegram_file_id'] = null;
                }
                break;
            default:
                if ($text !== '') {
                    $payload['data'][$field] = $text;
                }
        }

        $this->showConfirmation($chatId, $tid, $payload);
        return true;
    }

    // ---- Publish --------------------------------------------------------

    private function publish(int $chatId, int $tid, array $payload): void
    {
        $d   = $payload['data'];
        $img = $payload['images'] ?? [];

        $movie = [
            'title'          => $d['title'] ?? "\u{411}\u{435}\u{437} \u{43D}\u{430}\u{437}\u{432}\u{430}\u{43D}\u{438}\u{44F}",
            'original_title' => $d['original_title'] ?? null,
            'description'    => $d['description'] ?? ($d['description_short'] ?? null),
            'poster'         => $img['poster'] ?? null,
            'thumbnail'      => $img['thumbnail'] ?? null,
            'backdrop'       => $img['background'] ?? null,
            'banner'         => $img['banner'] ?? null,
            'watch_url'      => $d['watch_url'] ?? null,
            'telegram_file_id' => $d['telegram_file_id'] ?? null,
            'category'       => $d['category'] ?? 'movie',
            'country'        => $d['country'] ?? null,
            'year'           => $d['year'] ?? null,
            'age_rating'     => $d['age_rating'] ?? null,
            'duration'       => $d['duration'] ?? null,
            'rating'         => $d['rating'] ?? 0,
            'language'       => $d['language'] ?? null,
            'director'       => $d['director'] ?? null,
            'actors'         => $d['actors'] ?? null,
            'keywords'       => $d['keywords'] ?? null,
            'genres'         => $d['genres'] ?? [],
            'similar_titles' => $d['similar_titles'] ?? null,
            'status'         => $d['status'] ?? 'published',
            'is_new'         => 1,
            'is_popular'     => in_array(($d['status'] ?? ''), ['in_cinema'], true) ? 1 : 0,
        ];

        $id = $this->repo->createMovie($movie);
        $this->store->clear($tid);

        $label = self::CAT_LABELS[$movie['category']] ?? "\u{41A}\u{43E}\u{43D}\u{442}\u{435}\u{43D}\u{442}";

        $rows = [];
        // For series / anime offer to add seasons & episodes right away.
        if (in_array($movie['category'], ['series', 'anime'], true)) {
            $rows[] = [['text' => "\u{2795} \u{414}\u{43E}\u{431}\u{430}\u{432}\u{438}\u{442}\u{44C} \u{441}\u{435}\u{440}\u{438}\u{438}", 'callback_data' => 'ep:add:' . $id]];
        }
        $rows[] = [['text' => "\u{1F3AC} \u{41E}\u{442}\u{43A}\u{440}\u{44B}\u{442}\u{44C} \u{43A}\u{438}\u{43D}\u{43E}", 'web_app' => ['url' => $this->miniappUrl]]];

        $extra = in_array($movie['category'], ['series', 'anime'], true)
            ? "\n\n\u{422}\u{435}\u{43F}\u{435}\u{440}\u{44C} \u{434}\u{43E}\u{431}\u{430}\u{432}\u{44C}\u{442}\u{435} \u{441}\u{435}\u{437}\u{43E}\u{43D}\u{44B} \u{438} \u{441}\u{435}\u{440}\u{438}\u{438} \u{43A}\u{43D}\u{43E}\u{43F}\u{43A}\u{43E}\u{439} \u{43D}\u{438}\u{436}\u{435}."
            : '';

        $this->api->sendMessage(
            $chatId,
            "\u{2705} {$label} <b>\u{AB}{$movie['title']}\u{BB}</b> (#{$id}) \u{43E}\u{43F}\u{443}\u{431}\u{43B}\u{438}\u{43A}\u{43E}\u{432}\u{430}\u{43D}!\n"
            . "\u{423}\u{436}\u{435} \u{432}\u{438}\u{434}\u{435}\u{43D} \u{43D}\u{430} \u{433}\u{43B}\u{430}\u{432}\u{43D}\u{43E}\u{439} Mini App: Hero-\u{431}\u{430}\u{43D}\u{43D}\u{435}\u{440}, \u{41D}\u{43E}\u{432}\u{438}\u{43D}\u{43A}\u{438}, \u{41A}\u{430}\u{442}\u{435}\u{433}\u{43E}\u{440}\u{438}\u{438}, \u{41F}\u{43E}\u{438}\u{441}\u{43A}.{$extra}",
            ['reply_markup' => json_encode(['inline_keyboard' => $rows])]
        );

        // Auto-publish the film into the private archive channel, if connected.
        $this->postToArchive($chatId, $id, $d, $payload);
    }

    /**
     * Post the published movie into the private archive channel:
     * card (poster + caption), then the video itself. Order: card first, film last.
     */
    private function postToArchive(int $adminChatId, int $movieId, array $d, array $payload): void
    {
        $channel = $this->repo->getSetting('archive_channel_id');
        if (!$channel) {
            return; // no archive channel connected
        }

        $caption = $this->cardCaption($d);
        if (mb_strlen($caption) > 1000) {
            $caption = mb_substr($caption, 0, 1000) . "\u{2026}";
        }
        $caption .= "\n\n#" . $movieId;

        if (!empty($payload['poster_file_id'])) {
            $res = $this->api->sendPhoto($channel, $payload['poster_file_id'], $caption);
        } else {
            $res = $this->api->sendMessage($channel, $caption);
        }
        $ok = !empty($res['ok']);

        if ($ok && !empty($d['telegram_file_id'])) {
            $v = $this->api->sendVideo(
                $channel,
                (string) $d['telegram_file_id'],
                "\u{1F3AC} <b>" . htmlspecialchars((string) ($d['title'] ?? ''), ENT_QUOTES) . "</b>"
            );
            $ok = !empty($v['ok']);
        }

        if ($ok) {
            $this->api->sendMessage($adminChatId, "\u{1F4E1} \u{424}\u{438}\u{43B}\u{44C}\u{43C} \u{43E}\u{442}\u{43F}\u{440}\u{430}\u{432}\u{43B}\u{435}\u{43D} \u{432} \u{43A}\u{430}\u{43D}\u{430}\u{43B}-\u{430}\u{440}\u{445}\u{438}\u{432}.");
        } else {
            $this->api->sendMessage(
                $adminChatId,
                "\u{26A0}\u{FE0F} \u{41D}\u{435} \u{443}\u{434}\u{430}\u{43B}\u{43E}\u{441}\u{44C} \u{43E}\u{43F}\u{443}\u{431}\u{43B}\u{438}\u{43A}\u{43E}\u{432}\u{430}\u{442}\u{44C} \u{432} \u{43A}\u{430}\u{43D}\u{430}\u{43B}-\u{430}\u{440}\u{445}\u{438}\u{432}. \u{41F}\u{440}\u{43E}\u{432}\u{435}\u{440}\u{44C}\u{442}\u{435}, \u{447}\u{442}\u{43E} \u{431}\u{43E}\u{442} \u{2014} \u{430}\u{434}\u{43C}\u{438}\u{43D}\u{438}\u{441}\u{442}\u{440}\u{430}\u{442}\u{43E}\u{440} \u{43A}\u{430}\u{43D}\u{430}\u{43B}\u{430} (/admin \u{2192} \u{1F4E1} \u{41A}\u{430}\u{43D}\u{430}\u{43B}-\u{430}\u{440}\u{445}\u{438}\u{432})."
            );
        }
    }

    // ---- Helpers --------------------------------------------------------

    private function cleanup(array $payload): void
    {
        foreach (($payload['images'] ?? []) as $key => $rel) {
            if (is_string($rel) && $rel !== '' && in_array($key, ['poster', 'thumbnail', 'banner', 'background'], true)) {
                @unlink($this->uploadsDir . '/' . $rel);
            }
        }
    }

    private function isSkip(string $text): bool
    {
        return in_array(mb_strtolower($text), ['-', "\u{2014}", 'skip', '/skip', "\u{43D}\u{435}\u{442}", "\u{43F}\u{440}\u{43E}\u{43F}\u{443}\u{441}\u{442}\u{438}\u{442}\u{44C}"], true);
    }

    private function removeKeyboard(): array
    {
        return ['reply_markup' => json_encode(['remove_keyboard' => true])];
    }

    private function cancelInline(): array
    {
        return ['reply_markup' => json_encode([
            'inline_keyboard' => [[['text' => "\u{274C} \u{41E}\u{442}\u{43C}\u{435}\u{43D}\u{430}", 'callback_data' => 'aic:cancel']]],
        ])];
    }

    private function skipCancelInline(): array
    {
        return ['reply_markup' => json_encode([
            'inline_keyboard' => [
                [['text' => "\u{23ED} \u{41F}\u{440}\u{43E}\u{43F}\u{443}\u{441}\u{442}\u{438}\u{442}\u{44C}", 'callback_data' => 'aic:skipvideo']],
                [['text' => "\u{274C} \u{41E}\u{442}\u{43C}\u{435}\u{43D}\u{430}", 'callback_data' => 'aic:cancel']],
            ],
        ])];
    }
}
