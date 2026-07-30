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
            'type' => 'choice', 'key' => 'status', 'prompt' => "\u{1F4CC} \u{412}\u{44B}\u{431}\u{435}\u{440}\u{438}\u{442}\u{435} \u{441}\u{442}\u{430}\u{442}\u{443}\u{441}:",
            'choices' => [
                "\u{41E}\u{43F}\u{443}\u{431}\u{43B}\u{438}\u{43A}\u{43E}\u{432}\u{430}\u{442}\u{44C}" => 'published',
                "\u{421}\u{43A}\u{43E}\u{440}\u{43E} \u{432}\u{44B}\u{439}\u{434}\u{435}\u{442}" => 'coming_soon',
                "\u{421}\u{435}\u{439}\u{447}\u{430}\u{441} \u{432} \u{43A}\u{438}\u{43D}\u{43E}" => 'in_cinema',
                "\u{427}\u{435}\u{440}\u{43D}\u{43E}\u{432}\u{438}\u{43A}" => 'draft',
            ],
        ];
        $category = [
            'type' => 'choice', 'key' => 'category', 'prompt' => "\u{1F39E} \u{412}\u{44B}\u{431}\u{435}\u{440}\u{438}\u{442}\u{435} \u{43A}\u{430}\u{442}\u{435}\u{433}\u{43E}\u{440}\u{438}\u{44E}:",
            'choices' => [
                "\u{424}\u{438}\u{43B}\u{44C}\u{43C}" => 'movie', "\u{421}\u{435}\u{440}\u{438}\u{430}\u{43B}" => 'series',
                "\u{41C}\u{443}\u{43B}\u{44C}\u{442}\u{444}\u{438}\u{43B}\u{44C}\u{43C}" => 'cartoon', "\u{410}\u{43D}\u{438}\u{43C}\u{435}" => 'anime',
            ],
        ];

        if ($flow === 'announcement') {
            return [
                ['type' => 'text',  'key' => 'title',        'prompt' => "\u{1F4DD} \u{41D}\u{430}\u{437}\u{432}\u{430}\u{43D}\u{438}\u{435} \u{430}\u{43D}\u{43E}\u{43D}\u{441}\u{430}:"],
                ['type' => 'text',  'key' => 'description',  'prompt' => "\u{1F4C4} \u{41E}\u{43F}\u{438}\u{441}\u{430}\u{43D}\u{438}\u{435}:"],
                ['type' => 'photo', 'key' => 'poster',       'prompt' => "\u{1F5BC} \u{41E}\u{442}\u{43F}\u{440}\u{430}\u{432}\u{44C}\u{442}\u{435} \u{43F}\u{43E}\u{441}\u{442}\u{435}\u{440} (\u{444}\u{43E}\u{442}\u{43E}):", 'subdir' => 'posters'],
                ['type' => 'photo', 'key' => 'backdrop',     'prompt' => "\u{1F304} \u{41E}\u{442}\u{43F}\u{440}\u{430}\u{432}\u{44C}\u{442}\u{435} \u{444}\u{43E}\u{43D}\u{43E}\u{432}\u{43E}\u{435} \u{438}\u{437}\u{43E}\u{431}\u{440}\u{430}\u{436}\u{435}\u{43D}\u{438}\u{435} (\u{444}\u{43E}\u{442}\u{43E}):", 'subdir' => 'banners'],
                ['type' => 'text',  'key' => 'trailer',      'prompt' => "\u{1F3AC} \u{421}\u{441}\u{44B}\u{43B}\u{43A}\u{430} \u{43D}\u{430} \u{442}\u{440}\u{435}\u{439}\u{43B}\u{435}\u{440} (\u{438}\u{43B}\u{438} \u{AB}-\u{BB}):", 'skip' => true],
                ['type' => 'text',  'key' => 'genre',        'prompt' => "\u{1F3AD} \u{416}\u{430}\u{43D}\u{440} (\u{438}\u{43B}\u{438} \u{AB}-\u{BB}):", 'skip' => true],
                ['type' => 'text',  'key' => 'release_date', 'prompt' => "\u{1F4C5} \u{414}\u{430}\u{442}\u{430} \u{432}\u{44B}\u{445}\u{43E}\u{434}\u{430} \u{413}\u{413}\u{413}\u{413}-\u{41C}\u{41C}-\u{414}\u{414} (\u{438}\u{43B}\u{438} \u{AB}-\u{BB}):", 'skip' => true],
                $category,
            ];
        }

        // movie / series / cartoon / anime share the same wizard
        return [
            ['type' => 'text',  'key' => 'title',        'prompt' => "\u{1F4DD} \u{41D}\u{430}\u{437}\u{432}\u{430}\u{43D}\u{438}\u{435}:"],
            ['type' => 'text',  'key' => 'description',  'prompt' => "\u{1F4C4} \u{41E}\u{43F}\u{438}\u{441}\u{430}\u{43D}\u{438}\u{435}:"],
            ['type' => 'photo', 'key' => 'poster',       'prompt' => "\u{1F5BC} \u{41E}\u{442}\u{43F}\u{440}\u{430}\u{432}\u{44C}\u{442}\u{435} \u{43F}\u{43E}\u{441}\u{442}\u{435}\u{440} (\u{444}\u{43E}\u{442}\u{43E}):", 'subdir' => 'posters'],
            ['type' => 'photo', 'key' => 'backdrop',     'prompt' => "\u{1F304} \u{41E}\u{442}\u{43F}\u{440}\u{430}\u{432}\u{44C}\u{442}\u{435} \u{444}\u{43E}\u{43D}\u{43E}\u{432}\u{43E}\u{435} \u{438}\u{437}\u{43E}\u{431}\u{440}\u{430}\u{436}\u{435}\u{43D}\u{438}\u{435} (\u{444}\u{43E}\u{442}\u{43E}):", 'subdir' => 'banners'],
            ['type' => 'text',  'key' => 'trailer',      'prompt' => "\u{1F3AC} \u{421}\u{441}\u{44B}\u{43B}\u{43A}\u{430} \u{43D}\u{430} \u{442}\u{440}\u{435}\u{439}\u{43B}\u{435}\u{440} (\u{438}\u{43B}\u{438} \u{AB}-\u{BB}):", 'skip' => true],
            ['type' => 'text',  'key' => 'genres',       'prompt' => "\u{1F3AD} \u{416}\u{430}\u{43D}\u{440}\u{44B} \u{447}\u{435}\u{440}\u{435}\u{437} \u{437}\u{430}\u{43F}\u{44F}\u{442}\u{443}\u{44E}, \u{43D}\u{430}\u{43F}\u{440}. \u{AB}\u{411}\u{43E}\u{435}\u{432}\u{438}\u{43A}, \u{414}\u{440}\u{430}\u{43C}\u{430}\u{BB} (\u{438}\u{43B}\u{438} \u{AB}-\u{BB}):", 'skip' => true],
            ['type' => 'text',  'key' => 'country',      'prompt' => "\u{1F30D} \u{421}\u{442}\u{440}\u{430}\u{43D}\u{430} (\u{438}\u{43B}\u{438} \u{AB}-\u{BB}):", 'skip' => true],
            ['type' => 'text',  'key' => 'release_date', 'prompt' => "\u{1F4C5} \u{414}\u{430}\u{442}\u{430} \u{432}\u{44B}\u{445}\u{43E}\u{434}\u{430} \u{413}\u{413}\u{413}\u{413}-\u{41C}\u{41C}-\u{414}\u{414} (\u{438}\u{43B}\u{438} \u{AB}-\u{BB}):", 'skip' => true],
            ['type' => 'text',  'key' => 'age_rating',   'prompt' => "\u{1F51E} \u{412}\u{43E}\u{437}\u{440}\u{430}\u{441}\u{442}: 0+, 6+, 12+, 16+, 18+ (\u{438}\u{43B}\u{438} \u{AB}-\u{BB}):", 'skip' => true],
            ['type' => 'text',  'key' => 'duration',     'prompt' => "\u{23F1} \u{414}\u{43B}\u{438}\u{442}\u{435}\u{43B}\u{44C}\u{43D}\u{43E}\u{441}\u{442}\u{44C} \u{432} \u{43C}\u{438}\u{43D}\u{443}\u{442}\u{430}\u{445} (\u{438}\u{43B}\u{438} \u{AB}-\u{BB}):", 'skip' => true],
            ['type' => 'text',  'key' => 'rating',       'prompt' => "\u{2B50} \u{420}\u{435}\u{439}\u{442}\u{438}\u{43D}\u{433} 0\u{2013}10 (\u{438}\u{43B}\u{438} \u{AB}-\u{BB}):", 'skip' => true],
            ['type' => 'text',  'key' => 'language',     'prompt' => "\u{1F5E3} \u{42F}\u{437}\u{44B}\u{43A} (\u{438}\u{43B}\u{438} \u{AB}-\u{BB}):", 'skip' => true],
            ['type' => 'text',  'key' => 'director',     'prompt' => "\u{1F3A5} \u{420}\u{435}\u{436}\u{438}\u{441}\u{441}\u{451}\u{440} (\u{438}\u{43B}\u{438} \u{AB}-\u{BB}):", 'skip' => true],
            ['type' => 'text',  'key' => 'actors',       'prompt' => "\u{1F465} \u{410}\u{43A}\u{442}\u{451}\u{440}\u{44B} \u{447}\u{435}\u{440}\u{435}\u{437} \u{437}\u{430}\u{43F}\u{44F}\u{442}\u{443}\u{44E} (\u{438}\u{43B}\u{438} \u{AB}-\u{BB}):", 'skip' => true],
            ['type' => 'text',  'key' => 'watch_url',    'prompt' => "\u{25B6}\u{FE0F} \u{421}\u{441}\u{44B}\u{43B}\u{43A}\u{430} \u{434}\u{43B}\u{44F} \u{43F}\u{440}\u{43E}\u{441}\u{43C}\u{43E}\u{442}\u{440}\u{430} (\u{438}\u{43B}\u{438} \u{AB}-\u{BB}):", 'skip' => true],
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
        $this->api->sendMessage($chatId, "\u{1F4E2} \u{41E}\u{442}\u{43F}\u{440}\u{430}\u{432}\u{44C}\u{442}\u{435} \u{442}\u{435}\u{43A}\u{441}\u{442} \u{440}\u{430}\u{441}\u{441}\u{44B}\u{43B}\u{43A}\u{438}. \u{41E}\u{43D} \u{431}\u{443}\u{434}\u{435}\u{442} \u{434}\u{43E}\u{441}\u{442}\u{430}\u{432}\u{43B}\u{435}\u{43D} \u{432}\u{441}\u{435}\u{43C} \u{43F}\u{43E}\u{43B}\u{44C}\u{437}\u{43E}\u{432}\u{430}\u{442}\u{435}\u{43B}\u{44F}\u{43C}.", [
            'reply_markup' => json_encode(['keyboard' => [[['text' => "\u{2716}\u{FE0F} \u{41E}\u{442}\u{43C}\u{435}\u{43D}\u{430}"]]], 'resize_keyboard' => true]),
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
        if ($state['state'] && in_array($text, ['/cancel', "\u{2716}\u{FE0F} \u{41E}\u{442}\u{43C}\u{435}\u{43D}\u{430}"], true)) {
            $this->store->clear($tid);
            $this->api->sendMessage($chatId, "\u{274C} \u{414}\u{435}\u{439}\u{441}\u{442}\u{432}\u{438}\u{435} \u{43E}\u{442}\u{43C}\u{435}\u{43D}\u{435}\u{43D}\u{43E}.", $this->removeKeyboard());
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
                    $this->api->sendMessage($chatId, "\u{26A0}\u{FE0F} \u{41F}\u{440}\u{438}\u{448}\u{43B}\u{438}\u{442}\u{435} \u{438}\u{437}\u{43E}\u{431}\u{440}\u{430}\u{436}\u{435}\u{43D}\u{438}\u{435} (\u{444}\u{43E}\u{442}\u{43E}).");
                    return true;
                }
            } else {
                $value = $this->media->save($photoId, $field['subdir'] ?? 'posters');
                if ($value === null) {
                    $this->api->sendMessage($chatId, "\u{26A0}\u{FE0F} \u{41D}\u{435} \u{443}\u{434}\u{430}\u{43B}\u{43E}\u{441}\u{44C} \u{441}\u{43E}\u{445}\u{440}\u{430}\u{43D}\u{438}\u{442}\u{44C} \u{444}\u{430}\u{439}\u{43B}, \u{43F}\u{43E}\u{43F}\u{440}\u{43E}\u{431}\u{443}\u{439}\u{442}\u{435} \u{435}\u{449}\u{451} \u{440}\u{430}\u{437}.");
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
                $this->api->sendMessage($chatId, "\u{26A0}\u{FE0F} \u{412}\u{432}\u{435}\u{434}\u{438}\u{442}\u{435} \u{442}\u{435}\u{43A}\u{441}\u{442}.");
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
            $rows[] = [['text' => "\u{2716}\u{FE0F} \u{41E}\u{442}\u{43C}\u{435}\u{43D}\u{430}"]];
            $extra = ['reply_markup' => json_encode(['keyboard' => $rows, 'resize_keyboard' => true, 'one_time_keyboard' => true])];
        }

        $total = count($this->schema($flow));
        $this->api->sendMessage($chatId, sprintf("<b>\u{428}\u{430}\u{433} %d/%d</b>\n%s", $step + 1, $total, $field['prompt']), $extra);
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
                "\u{2705} \u{410}\u{43D}\u{43E}\u{43D}\u{441} <b>#{$id}</b> \u{441}\u{43E}\u{445}\u{440}\u{430}\u{43D}\u{451}\u{43D} \u{438} \u{443}\u{436}\u{435} \u{432}\u{438}\u{434}\u{435}\u{43D} \u{43D}\u{430} \u{433}\u{43B}\u{430}\u{432}\u{43D}\u{43E}\u{439} Mini App.",
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
            'movie' => "\u{424}\u{438}\u{43B}\u{44C}\u{43C}", 'series' => "\u{421}\u{435}\u{440}\u{438}\u{430}\u{43B}",
            'cartoon' => "\u{41C}\u{443}\u{43B}\u{44C}\u{442}\u{444}\u{438}\u{43B}\u{44C}\u{43C}", 'anime' => "\u{410}\u{43D}\u{438}\u{43C}\u{435}",
        ][$data['category'] ?? 'movie'] ?? "\u{41A}\u{43E}\u{43D}\u{442}\u{435}\u{43D}\u{442}";
        $this->api->sendMessage(
            $chatId,
            "\u{2705} {$label} <b>\u{AB}{$data['title']}\u{BB}</b> (#{$id}) \u{434}\u{43E}\u{431}\u{430}\u{432}\u{43B}\u{435}\u{43D} \u{432} \u{43A}\u{430}\u{442}\u{430}\u{43B}\u{43E}\u{433}.",
            $this->openAppKeyboard()
        );

        // Notify the private archive channel, if connected.
        $channel = $this->repo->getSetting('archive_channel_id');
        if ($channel) {
            $safeTitle = htmlspecialchars((string) $data['title'], ENT_QUOTES);
            $this->api->sendMessage($channel, "\u{1F3AC} <b>{$safeTitle}</b> (#{$id}) \u{434}\u{43E}\u{431}\u{430}\u{432}\u{43B}\u{435}\u{43D} \u{432} \u{43A}\u{430}\u{442}\u{430}\u{43B}\u{43E}\u{433}.");
        }
    }

    private function doBroadcast(int $chatId, int $tid, string $text): void
    {
        $this->store->clear($tid);
        if ($text === '') {
            $this->api->sendMessage($chatId, "\u{26A0}\u{FE0F} \u{41F}\u{443}\u{441}\u{442}\u{43E}\u{435} \u{441}\u{43E}\u{43E}\u{431}\u{449}\u{435}\u{43D}\u{438}\u{435}, \u{440}\u{430}\u{441}\u{441}\u{44B}\u{43B}\u{43A}\u{430} \u{43E}\u{442}\u{43C}\u{435}\u{43D}\u{435}\u{43D}\u{430}.", $this->removeKeyboard());
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
        $this->api->sendMessage($chatId, "\u{1F4E2} \u{420}\u{430}\u{441}\u{441}\u{44B}\u{43B}\u{43A}\u{430} \u{437}\u{430}\u{432}\u{435}\u{440}\u{448}\u{435}\u{43D}\u{430}: \u{434}\u{43E}\u{441}\u{442}\u{430}\u{432}\u{43B}\u{435}\u{43D}\u{43E} {$sent}/" . count($ids) . '.', $this->removeKeyboard());
    }

    private function isSkip(string $text): bool
    {
        return in_array(mb_strtolower($text), ['-', "\u{2014}", 'skip', '/skip', "\u{43D}\u{435}\u{442}"], true);
    }

    private function removeKeyboard(): array
    {
        return ['reply_markup' => json_encode(['remove_keyboard' => true])];
    }

    private function openAppKeyboard(): array
    {
        return ['reply_markup' => json_encode([
            'inline_keyboard' => [[
                ['text' => "\u{1F3AC} \u{41E}\u{442}\u{43A}\u{440}\u{44B}\u{442}\u{44C} \u{43A}\u{438}\u{43D}\u{43E}", 'web_app' => ['url' => $this->miniappUrl]],
            ]],
        ])];
    }
}
