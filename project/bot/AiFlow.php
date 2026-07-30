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
        'movie' => 'Фильм', 'series' => 'Сериал',
        'anime' => 'Аниме', 'cartoon' => 'Мультфильм',
    ];
    private const STATUS_LABELS = [
        'published' => 'Опубликован', 'coming_soon' => 'Скоро выйдет',
        'in_cinema' => 'Сейчас в кино', 'draft' => 'Черновик',
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
            ? 'AI распознает фильм и сам заполнит карточку.'
            : '⚠️ AI-ключ не настроен — карточку нужно будет заполнить вручную, но постер обработается автоматически.';
        $this->api->sendMessage(
            $chatId,
            "🤖 <b>AI-добавление фильма</b>\n\n<b>Шаг 1.</b> Отправьте постер фильма 🖼\n\n{$note}\n\n"
            . "В любой момент можно нажать «❌ Отмена» или отправить /start.",
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
        if (in_array($text, ['/cancel', '✖️ Отмена'], true)) {
            $this->cleanup($state['payload']);
            $this->store->clear($tid);
            $this->api->sendMessage($chatId, '❌ Добавление отменено.', $this->removeKeyboard());
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
            $this->api->sendMessage($chatId, '⚠️ Пришлите именно изображение (постер).');
            return true;
        }

        $this->api->call('sendChatAction', ['chat_id' => $chatId, 'action' => 'upload_photo']);
        $this->api->sendMessage($chatId, '⏳ Обрабатываю постер: Smart Crop, баннер, WebP…');

        // Download the original for processing (removed afterwards).
        $rel = $this->media->save($fileId, 'tmp', 'jpg');
        if ($rel === null) {
            $this->api->sendMessage($chatId, '⚠️ Не удалось сохранить изображение. Попробуйте ещё раз.');
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
                "🔎 Распознано: <b>{$ident['title']}</b>"
                . ($ident['year'] ? " ({$ident['year']})" : '')
                . "\n🤖 Заполняю карточку…"
            );
            $this->enrichAndAskVideo($chatId, $tid, $ident['title'], $ident['year'] ?? null, $ident['type'] ?? null, $payload);
            return true;
        }

        // Could not recognise -> ask for the title manually.
        $this->store->set($tid, 'ai_title', $payload);
        $this->api->sendMessage(
            $chatId,
            "🤔 Не удалось точно распознать фильм.\n<b>Напишите название вручную:</b>",
            $this->cancelInline()
        );
        return true;
    }

    private function onTitle(int $chatId, int $tid, string $text, array $payload): bool
    {
        if ($text === '') {
            $this->api->sendMessage($chatId, '⚠️ Введите название текстом.');
            return true;
        }
        $payload['data']['title'] = $text;
        $this->api->sendMessage($chatId, "🤖 Собираю информацию о «<b>{$text}</b>»…");
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
            $this->api->sendMessage($chatId, '⚠️ Пришлите видеофайл, ссылку (http…) или «-», чтобы пропустить.');
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
            "<b>Шаг 2.</b> Видео фильма (чтобы работала кнопка «Смотреть»):\n"
            . "• <b>перешлите видео из вашего закрытого канала</b>, или\n"
            . "• отправьте видеофайл, или\n"
            . "• пришлите ссылку.\n\n"
            . "Большие видео на сервере не хранятся — бот отдаёт их сам, внутри чата.\n"
            . "Можно «⏭ Пропустить».",
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
            [['text' => '✅ Опубликовать', 'callback_data' => 'aic:pub']],
            [['text' => '✏ Редактировать', 'callback_data' => 'aic:edit'],
             ['text' => '❌ Отмена', 'callback_data' => 'aic:cancel']],
        ]];

        $extra = ['reply_markup' => json_encode($kb)];
        // Remove the reply keyboard first, then show the preview card with poster.
        $this->api->sendMessage($chatId, '👇 Проверьте карточку перед публикацией:', $this->removeKeyboard());

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
            : '—';
        $meta = array_filter([
            !empty($d['rating']) ? '⭐ ' . number_format((float) $d['rating'], 1) : null,
            !empty($d['age_rating']) ? $e($d['age_rating']) : null,
            !empty($d['duration']) ? $d['duration'] . ' мин' : null,
        ]);
        $desc = $d['description_short'] ?? $d['description'] ?? '';
        if (mb_strlen((string) $desc) > 350) {
            $desc = mb_substr((string) $desc, 0, 350) . '…';
        }

        return "🎬 <b>" . $e($d['title'] ?? '') . "</b>"
            . (!empty($d['year']) ? " ({$d['year']})" : '') . "\n"
            . (!empty($d['original_title']) ? '<i>' . $e($d['original_title']) . "</i>\n" : '')
            . (!empty($meta) ? implode(' • ', $meta) . "\n" : '')
            . "\n🏷 " . (self::CAT_LABELS[$d['category'] ?? 'movie'] ?? 'Фильм')
            . " · " . (self::STATUS_LABELS[$d['status'] ?? 'published'] ?? 'Опубликован') . "\n"
            . "🎭 {$genres}\n"
            . (!empty($d['country']) ? '🌍 ' . $e($d['country']) . "\n" : '')
            . (!empty($d['director']) ? '🎥 ' . $e($d['director']) . "\n" : '')
            . (!empty($d['actors']) ? '👥 ' . $e($d['actors']) . "\n" : '')
            . ($desc !== '' ? "\n📝 " . $e($desc) : '');
    }

    private function onConfirmStray(int $chatId): bool
    {
        $this->api->sendMessage($chatId, 'Используйте кнопки под карточкой: ✅ / ✏ / ❌');
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
            $this->api->answerCallbackQuery($cbId, 'Отменено');
            $this->cleanup($payload);
            $this->store->clear($tid);
            $this->api->sendMessage($chatId, '❌ Добавление отменено.');
            return true;
        }

        if ($data === 'aic:skipvideo') {
            $this->api->answerCallbackQuery($cbId, 'Пропущено');
            if ($state['state'] === 'ai_video') {
                $this->showConfirmation($chatId, $tid, $payload);
            }
            return true;
        }

        if ($data === 'aic:pub') {
            $this->api->answerCallbackQuery($cbId, 'Публикую…');
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
            [$b('📝 Название', 'title'), $b('🗓 Год', 'year')],
            [$b('📄 Описание', 'description'), $b('🎭 Жанры', 'genres')],
            [$b('🌍 Страна', 'country'), $b('🎥 Режиссёр', 'director')],
            [$b('👥 Актёры', 'actors'), $b('⏱ Длительность', 'duration')],
            [$b('⭐ Рейтинг', 'rating'), $b('🔞 Возраст', 'age_rating')],
            [$b('🏷 Категория', 'category'), $b('📌 Статус', 'status')],
            [$b('▶️ Видео/ссылка', 'video')],
            [['text' => '⬅️ Назад к карточке', 'callback_data' => 'aic:back']],
        ]];
        $this->api->sendMessage($chatId, '✏ <b>Что изменить?</b>', ['reply_markup' => json_encode($kb)]);
    }

    private function promptEdit(int $chatId, int $tid, string $field, array $payload): void
    {
        $payload['edit_field'] = $field;
        $this->store->set($tid, 'ai_edit', $payload);

        if ($field === 'category') {
            $rows = [[['text' => 'Фильм']], [['text' => 'Сериал']], [['text' => 'Мультфильм']], [['text' => 'Аниме']], [['text' => '✖️ Отмена']]];
            $this->api->sendMessage($chatId, 'Выберите категорию:', ['reply_markup' => json_encode(['keyboard' => $rows, 'resize_keyboard' => true, 'one_time_keyboard' => true])]);
            return;
        }
        if ($field === 'status') {
            $rows = [[['text' => 'Опубликовать']], [['text' => 'Скоро выйдет']], [['text' => 'Сейчас в кино']], [['text' => '✖️ Отмена']]];
            $this->api->sendMessage($chatId, 'Выберите статус:', ['reply_markup' => json_encode(['keyboard' => $rows, 'resize_keyboard' => true, 'one_time_keyboard' => true])]);
            return;
        }

        $prompts = [
            'title' => '📝 Новое название:', 'year' => '🗓 Год (число):',
            'description' => '📄 Описание:', 'genres' => '🎭 Жанры через запятую:',
            'country' => '🌍 Страна:', 'director' => '🎥 Режиссёр:',
            'actors' => '👥 Актёры через запятую:', 'duration' => '⏱ Длительность в минутах:',
            'rating' => '⭐ Рейтинг 0–10:', 'age_rating' => '🔞 Возраст (0+,6+,12+,16+,18+):',
            'video' => '▶️ Пришлите видеофайл или ссылку (http…):',
        ];
        $this->api->sendMessage($chatId, $prompts[$field] ?? 'Новое значение:', ['reply_markup' => json_encode(['keyboard' => [[['text' => '✖️ Отмена']]], 'resize_keyboard' => true])]);
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
                $map = ['Фильм' => 'movie', 'Сериал' => 'series', 'Мультфильм' => 'cartoon', 'Аниме' => 'anime'];
                $payload['data']['category'] = $map[$text] ?? ($payload['data']['category'] ?? 'movie');
                break;
            case 'status':
                $map = ['Опубликовать' => 'published', 'Скоро выйдет' => 'coming_soon', 'Сейчас в кино' => 'in_cinema'];
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
            'title'          => $d['title'] ?? 'Без названия',
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

        $label = self::CAT_LABELS[$movie['category']] ?? 'Контент';

        $rows = [];
        // For series / anime offer to add seasons & episodes right away.
        if (in_array($movie['category'], ['series', 'anime'], true)) {
            $rows[] = [['text' => '➕ Добавить серии', 'callback_data' => 'ep:add:' . $id]];
        }
        $rows[] = [['text' => '🎬 Открыть кино', 'web_app' => ['url' => $this->miniappUrl]]];

        $extra = in_array($movie['category'], ['series', 'anime'], true)
            ? "\n\nТеперь добавьте сезоны и серии кнопкой ниже."
            : '';

        $this->api->sendMessage(
            $chatId,
            "✅ {$label} <b>«{$movie['title']}»</b> (#{$id}) опубликован!\n"
            . "Уже виден на главной Mini App: Hero-баннер, Новинки, Категории, Поиск.{$extra}",
            ['reply_markup' => json_encode(['inline_keyboard' => $rows])]
        );
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
        return in_array(mb_strtolower($text), ['-', '—', 'skip', '/skip', 'нет', 'пропустить'], true);
    }

    private function removeKeyboard(): array
    {
        return ['reply_markup' => json_encode(['remove_keyboard' => true])];
    }

    private function cancelInline(): array
    {
        return ['reply_markup' => json_encode([
            'inline_keyboard' => [[['text' => '❌ Отмена', 'callback_data' => 'aic:cancel']]],
        ])];
    }

    private function skipCancelInline(): array
    {
        return ['reply_markup' => json_encode([
            'inline_keyboard' => [
                [['text' => '⏭ Пропустить', 'callback_data' => 'aic:skipvideo']],
                [['text' => '❌ Отмена', 'callback_data' => 'aic:cancel']],
            ],
        ])];
    }
}
