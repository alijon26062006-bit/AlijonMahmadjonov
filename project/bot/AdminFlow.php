<?php
declare(strict_types=1);

namespace Bot;

/**
 * Step-by-step (finite-state-machine) dialogs for administrators:
 *   - add a movie / series / cartoon / anime
 *   - add an announcement
 *   - broadcast a message
 *
 * State lives in the `bot_states` table via StateStore. Each active dialog
 * stores {flow, category, step, data}. A schema array drives the prompts, so
 * the same engine serves every "add" wizard.
 */
final class AdminFlow
{
    public function __construct(
        private TelegramApi $api,
        private Media $media,
        private ContentRepo $repo,
        private StateStore $store,
        private string $miniappUrl
    ) {}

    // ---- Schemas --------------------------------------------------------

    private function schema(string $flow): array
    {
        $status = [
            'type' => 'choice', 'key' => 'status', 'prompt' => '📌 Выберите статус:',
            'choices' => [
                'Опубликовать' => 'published',
                'Скоро выйдет' => 'coming_soon',
                'Сейчас в кино' => 'in_cinema',
                'Черновик' => 'draft',
            ],
        ];
        $category = [
            'type' => 'choice', 'key' => 'category', 'prompt' => '🎞 Выберите категорию:',
            'choices' => [
                'Фильм' => 'movie', 'Сериал' => 'series',
                'Мультфильм' => 'cartoon', 'Аниме' => 'anime',
            ],
        ];

        if ($flow === 'announcement') {
            return [
                ['type' => 'text',  'key' => 'title',        'prompt' => '📝 Название анонса:'],
                ['type' => 'text',  'key' => 'description',  'prompt' => '📄 Описание:'],
                ['type' => 'photo', 'key' => 'poster',       'prompt' => '🖼 Отправьте постер (фото):', 'subdir' => 'posters'],
                ['type' => 'photo', 'key' => 'backdrop',     'prompt' => '🌄 Отправьте фоновое изображение (фото):', 'subdir' => 'banners'],
                ['type' => 'text',  'key' => 'trailer',      'prompt' => '🎬 Ссылка на трейлер (или «-»):', 'skip' => true],
                ['type' => 'text',  'key' => 'genre',        'prompt' => '🎭 Жанр (или «-»):', 'skip' => true],
                ['type' => 'text',  'key' => 'release_date', 'prompt' => '📅 Дата выхода ГГГГ-ММ-ДД (или «-»):', 'skip' => true],
                $category,
            ];
        }

        // movie / series / cartoon / anime share the same wizard
        return [
            ['type' => 'text',  'key' => 'title',        'prompt' => '📝 Название:'],
            ['type' => 'text',  'key' => 'description',  'prompt' => '📄 Описание:'],
            ['type' => 'photo', 'key' => 'poster',       'prompt' => '🖼 Отправьте постер (фото):', 'subdir' => 'posters'],
            ['type' => 'photo', 'key' => 'backdrop',     'prompt' => '🌄 Отправьте фоновое изображение (фото):', 'subdir' => 'banners'],
            ['type' => 'text',  'key' => 'trailer',      'prompt' => '🎬 Ссылка на трейлер (или «-»):', 'skip' => true],
            ['type' => 'text',  'key' => 'genres',       'prompt' => '🎭 Жанры через запятую, напр. «Боевик, Драма» (или «-»):', 'skip' => true],
            ['type' => 'text',  'key' => 'country',      'prompt' => '🌍 Страна (или «-»):', 'skip' => true],
            ['type' => 'text',  'key' => 'release_date', 'prompt' => '📅 Дата выхода ГГГГ-ММ-ДД (или «-»):', 'skip' => true],
            ['type' => 'text',  'key' => 'age_rating',   'prompt' => '🔞 Возраст: 0+, 6+, 12+, 16+, 18+ (или «-»):', 'skip' => true],
            ['type' => 'text',  'key' => 'duration',     'prompt' => '⏱ Длительность в минутах (или «-»):', 'skip' => true],
            ['type' => 'text',  'key' => 'rating',       'prompt' => '⭐ Рейтинг 0–10 (или «-»):', 'skip' => true],
            ['type' => 'text',  'key' => 'language',     'prompt' => '🗣 Язык (или «-»):', 'skip' => true],
            ['type' => 'text',  'key' => 'director',     'prompt' => '🎥 Режиссёр (или «-»):', 'skip' => true],
            ['type' => 'text',  'key' => 'actors',       'prompt' => '👥 Актёры через запятую (или «-»):', 'skip' => true],
            ['type' => 'text',  'key' => 'watch_url',    'prompt' => '▶️ Ссылка для просмотра (или «-»):', 'skip' => true],
            $status,
        ];
    }

    // ---- Public entry points -------------------------------------------

    /** Begin an add-content wizard. $flow: movie|announcement, $category preset. */
    public function start(int $chatId, int $tid, string $flow, ?string $category = null): void
    {
        $this->store->set($tid, 'flow', [
            'flow' => $flow, 'category' => $category, 'step' => 0, 'data' => [],
        ]);
        $this->prompt($chatId, $flow, 0);
    }

    public function startBroadcast(int $chatId, int $tid): void
    {
        $this->store->set($tid, 'broadcast', []);
        $this->api->sendMessage($chatId, '📢 Отправьте текст рассылки. Он будет доставлен всем пользователям.', [
            'reply_markup' => json_encode(['keyboard' => [[['text' => '✖️ Отмена']]], 'resize_keyboard' => true]),
        ]);
    }

    /**
     * Feed an incoming message to the active dialog.
     * @return bool true if a dialog consumed the message.
     */
    public function handle(int $chatId, int $tid, array $message): bool
    {
        $state = $this->store->get($tid);
        $text  = trim((string) ($message['text'] ?? ''));

        // Universal cancel
        if ($state['state'] && in_array($text, ['/cancel', '✖️ Отмена'], true)) {
            $this->store->clear($tid);
            $this->api->sendMessage($chatId, '❌ Действие отменено.', $this->removeKeyboard());
            return true;
        }

        if ($state['state'] === 'broadcast') {
            $this->doBroadcast($chatId, $tid, $text);
            return true;
        }

        if ($state['state'] !== 'flow') {
            return false;
        }

        $payload = $state['payload'];
        $schema  = $this->schema($payload['flow']);
        $step    = (int) $payload['step'];
        $field   = $schema[$step] ?? null;
        if (!$field) {
            $this->store->clear($tid);
            return false;
        }

        // ---- Validate & capture the current step ----
        $value = null;

        if ($field['type'] === 'photo') {
            $photoId = Media::largestPhotoId($message['photo'] ?? []);
            if (!$photoId && !empty($message['document']['file_id'])) {
                $photoId = $message['document']['file_id'];
            }
            if (!$photoId) {
                if (!empty($field['skip']) && $this->isSkip($text)) {
                    $value = null;
                } else {
                    $this->api->sendMessage($chatId, '⚠️ Пришлите изображение (фото).');
                    return true;
                }
            } else {
                $value = $this->media->save($photoId, $field['subdir'] ?? 'posters');
                if ($value === null) {
                    $this->api->sendMessage($chatId, '⚠️ Не удалось сохранить файл, попробуйте ещё раз.');
                    return true;
                }
            }
        } elseif ($field['type'] === 'choice') {
            $map = $field['choices'];
            if (!isset($map[$text])) {
                $this->prompt($chatId, $payload['flow'], $step); // re-ask
                return true;
            }
            $value = $map[$text];
        } else { // text
            if ($text === '') {
                $this->api->sendMessage($chatId, '⚠️ Введите текст.');
                return true;
            }
            $value = (!empty($field['skip']) && $this->isSkip($text)) ? null : $text;
        }

        $payload['data'][$field['key']] = $value;
        $payload['step'] = $step + 1;

        // ---- Finished? ----
        if ($payload['step'] >= count($schema)) {
            $this->finish($chatId, $tid, $payload);
            return true;
        }

        $this->store->set($tid, 'flow', $payload);
        $this->prompt($chatId, $payload['flow'], $payload['step']);
        return true;
    }

    // ---- Internals ------------------------------------------------------

    private function prompt(int $chatId, string $flow, int $step): void
    {
        $field = $this->schema($flow)[$step];
        $extra = $this->removeKeyboard();

        if ($field['type'] === 'choice') {
            $rows = array_map(static fn ($label) => [['text' => $label]], array_keys($field['choices']));
            $rows[] = [['text' => '✖️ Отмена']];
            $extra = ['reply_markup' => json_encode(['keyboard' => $rows, 'resize_keyboard' => true, 'one_time_keyboard' => true])];
        }

        $total = count($this->schema($flow));
        $this->api->sendMessage($chatId, sprintf("<b>Шаг %d/%d</b>\n%s", $step + 1, $total, $field['prompt']), $extra);
    }

    private function finish(int $chatId, int $tid, array $payload): void
    {
        $data = $payload['data'];
        if ($payload['category']) {
            $data['category'] = $payload['category'];
        }

        if ($payload['flow'] === 'announcement') {
            $id = $this->repo->createAnnouncement($data);
            $this->store->clear($tid);
            $this->api->sendMessage(
                $chatId,
                "✅ Анонс <b>#{$id}</b> сохранён и уже виден на главной Mini App.",
                $this->openAppKeyboard()
            );
            return;
        }

        if (!empty($data['genres']) && is_string($data['genres'])) {
            $data['genres'] = array_map('trim', explode(',', $data['genres']));
        }

        $id = $this->repo->createMovie($data);
        $this->store->clear($tid);
        $label = [
            'movie' => 'Фильм', 'series' => 'Сериал',
            'cartoon' => 'Мультфильм', 'anime' => 'Аниме',
        ][$data['category'] ?? 'movie'] ?? 'Контент';
        $this->api->sendMessage(
            $chatId,
            "✅ {$label} <b>«{$data['title']}»</b> (#{$id}) добавлен в каталог.",
            $this->openAppKeyboard()
        );
    }

    private function doBroadcast(int $chatId, int $tid, string $text): void
    {
        $this->store->clear($tid);
        if ($text === '') {
            $this->api->sendMessage($chatId, '⚠️ Пустое сообщение, рассылка отменена.', $this->removeKeyboard());
            return;
        }
        $ids  = $this->repo->allUserIds();
        $sent = 0;
        foreach ($ids as $uid) {
            $res = $this->api->sendMessage($uid, $text);
            if (!empty($res['ok'])) {
                $sent++;
            }
            usleep(40000); // ~25 msg/s, stay within Telegram limits
        }
        $this->api->sendMessage($chatId, "📢 Рассылка завершена: доставлено {$sent}/" . count($ids) . '.', $this->removeKeyboard());
    }

    private function isSkip(string $text): bool
    {
        return in_array(mb_strtolower($text), ['-', '—', 'skip', '/skip', 'нет'], true);
    }

    private function removeKeyboard(): array
    {
        return ['reply_markup' => json_encode(['remove_keyboard' => true])];
    }

    private function openAppKeyboard(): array
    {
        return ['reply_markup' => json_encode([
            'inline_keyboard' => [[
                ['text' => '🎬 Открыть кино', 'web_app' => ['url' => $this->miniappUrl]],
            ]],
        ])];
    }
}
