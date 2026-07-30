<?php

namespace Core;

/**
 * Server-side OpenAI client. The API key lives only here (loaded from config /
 * environment) and is never exposed to JavaScript or the Telegram Mini App.
 *
 * Used as an intelligent assistant for the administrator:
 *   - identifyTitle()  recognises a film from its poster image (vision)
 *   - enrich()         fills a full movie card from a known title (text)
 *   - focalPoint()     finds the subject/face region to protect during cropping
 *
 * Every method degrades gracefully: on any failure it returns null / an empty
 * result so the bot can fall back to manual input.
 */
final class OpenAiClient
{
    private string $apiKey;
    private string $endpoint;
    private string $visionModel;
    private string $textModel;
    private int $timeout;

    public function __construct(array $cfg)
    {
        $this->apiKey      = (string) ($cfg['api_key'] ?? '');
        $this->endpoint    = rtrim((string) ($cfg['endpoint'] ?? 'https://api.openai.com/v1'), '/');
        $this->visionModel = (string) ($cfg['model_vision'] ?? 'gpt-4o-mini');
        $this->textModel   = (string) ($cfg['model_text'] ?? 'gpt-4o-mini');
        $this->timeout     = (int) ($cfg['timeout'] ?? 45);
    }

    public function isEnabled(): bool
    {
        return $this->apiKey !== '' && !str_starts_with($this->apiKey, 'PUT_');
    }

    /**
     * Recognise a film from its poster.
     *
     * @return array{title:string,original_title:string,year:?int,type:?string,confidence:float}|null
     */
    public function identifyTitle(string $imagePath): ?array
    {
        if (!$this->isEnabled()) {
            return null;
        }
        $dataUrl = $this->toDataUrl($imagePath);
        if ($dataUrl === null) {
            return null;
        }

        $system = 'You are a film recognition expert. Identify the movie, series, '
            . 'anime or cartoon shown on the poster. Respond ONLY as compact JSON with keys: '
            . 'title (localized Russian title if well known, else the on-poster title), '
            . 'original_title, year (integer or null), '
            . 'type (one of movie, series, anime, cartoon), '
            . 'confidence (0..1). If you are not reasonably sure, set title to "" and confidence to 0.';

        $messages = [
            ['role' => 'system', 'content' => $system],
            ['role' => 'user', 'content' => [
                ['type' => 'text', 'text' => 'Определи тайтл по этому постеру.'],
                ['type' => 'image_url', 'image_url' => ['url' => $dataUrl, 'detail' => 'low']],
            ]],
        ];

        $json = $this->chatJson($this->visionModel, $messages, 300);
        if (!is_array($json)) {
            return null;
        }

        $title = trim((string) ($json['title'] ?? ''));
        $conf  = (float) ($json['confidence'] ?? 0);
        if ($title === '' || $conf < 0.35) {
            return null;
        }

        return [
            'title'          => $title,
            'original_title' => trim((string) ($json['original_title'] ?? '')),
            'year'           => isset($json['year']) && $json['year'] ? (int) $json['year'] : null,
            'type'           => $this->normalizeType($json['type'] ?? null),
            'confidence'     => $conf,
        ];
    }

    /**
     * Build a full movie card from a known title.
     *
     * @return array<string,mixed> Normalised card fields (empty string / null when unknown).
     */
    public function enrich(string $title, ?int $year = null, ?string $type = null): array
    {
        if (!$this->isEnabled()) {
            return [];
        }

        $hint = $year ? " ({$year})" : '';
        $system = 'You are a film database expert. Given a movie/series/anime/cartoon title, '
            . 'return factual metadata as compact JSON. Use Russian for text fields '
            . '(title, description, genres, country, director, actors, keywords). '
            . 'Keys: title, original_title, description_short (<=160 chars), description_full, '
            . 'year (int or null), genres (array of Russian genre names), country, director, '
            . 'actors (array of names), duration (minutes int or null), '
            . 'age_rating (one of "0+","6+","12+","16+","18+" or ""), rating (0..10 float), '
            . 'type (movie|series|anime|cartoon), status (published|coming_soon|in_cinema), '
            . 'language, keywords (array), similar_titles (array of titles). '
            . 'Leave a field empty ("" or null or []) if you are not sure. Do NOT invent facts.';

        $messages = [
            ['role' => 'system', 'content' => $system],
            ['role' => 'user', 'content' => "Заполни карточку для: «{$title}»{$hint}"
                . ($type ? " . Тип: {$type}." : '')],
        ];

        $json = $this->chatJson($this->textModel, $messages, 900);
        if (!is_array($json)) {
            return [];
        }
        return $this->normalizeCard($json, $title, $type);
    }

    /**
     * Locate the main subject / face region to protect during a smart crop.
     *
     * @return array{x:float,y:float,w:float,h:float}|null Normalised 0..1 box.
     */
    public function focalPoint(string $imagePath): ?array
    {
        if (!$this->isEnabled()) {
            return null;
        }
        $dataUrl = $this->toDataUrl($imagePath);
        if ($dataUrl === null) {
            return null;
        }

        $system = 'Return ONLY JSON with the bounding box of the most important region to keep '
            . '(main face/character and the title text) as normalized coordinates 0..1: '
            . 'keys x, y, w, h (top-left origin). If unsure, return the poster center: '
            . '{"x":0.25,"y":0.15,"w":0.5,"h":0.6}.';

        $messages = [
            ['role' => 'system', 'content' => $system],
            ['role' => 'user', 'content' => [
                ['type' => 'text', 'text' => 'Где главный объект/лицо и название?'],
                ['type' => 'image_url', 'image_url' => ['url' => $dataUrl, 'detail' => 'low']],
            ]],
        ];

        $json = $this->chatJson($this->visionModel, $messages, 150);
        if (!is_array($json) || !isset($json['x'], $json['y'], $json['w'], $json['h'])) {
            return null;
        }

        $clamp = static fn ($v) => max(0.0, min(1.0, (float) $v));
        return [
            'x' => $clamp($json['x']),
            'y' => $clamp($json['y']),
            'w' => $clamp($json['w']),
            'h' => $clamp($json['h']),
        ];
    }

    // ---- Internals ------------------------------------------------------

    /**
     * POST a chat completion requesting a JSON object and return the decoded array.
     */
    private function chatJson(string $model, array $messages, int $maxTokens): ?array
    {
        $payload = [
            'model'           => $model,
            'messages'        => $messages,
            'temperature'     => 0.2,
            'max_tokens'      => $maxTokens,
            'response_format' => ['type' => 'json_object'],
        ];

        $ch = curl_init($this->endpoint . '/chat/completions');
        curl_setopt_array($ch, [
            CURLOPT_RETURNTRANSFER => true,
            CURLOPT_POST           => true,
            CURLOPT_HTTPHEADER     => [
                'Content-Type: application/json',
                'Authorization: Bearer ' . $this->apiKey,
            ],
            CURLOPT_POSTFIELDS     => json_encode($payload, JSON_UNESCAPED_UNICODE),
            CURLOPT_TIMEOUT        => $this->timeout,
        ]);
        $raw  = curl_exec($ch);
        $err  = curl_error($ch);
        $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);

        if ($raw === false) {
            Logger::error('OpenAI cURL error: ' . $err);
            return null;
        }
        if ($code >= 400) {
            Logger::error('OpenAI HTTP ' . $code . ': ' . substr((string) $raw, 0, 500));
            return null;
        }

        $body    = json_decode((string) $raw, true);
        $content = $body['choices'][0]['message']['content'] ?? null;
        if (!is_string($content)) {
            Logger::error('OpenAI: unexpected response shape');
            return null;
        }

        $decoded = json_decode($content, true);
        return is_array($decoded) ? $decoded : null;
    }

    private function toDataUrl(string $path): ?string
    {
        if (!is_file($path)) {
            return null;
        }
        $bytes = @file_get_contents($path);
        if ($bytes === false) {
            return null;
        }
        $mime = 'image/jpeg';
        if (function_exists('getimagesize')) {
            $info = @getimagesize($path);
            if (!empty($info['mime'])) {
                $mime = $info['mime'];
            }
        }
        return 'data:' . $mime . ';base64,' . base64_encode($bytes);
    }

    private function normalizeType($type): ?string
    {
        $type = is_string($type) ? strtolower(trim($type)) : '';
        $map = [
            'movie' => 'movie', 'film' => 'movie', 'фильм' => 'movie',
            'series' => 'series', 'сериал' => 'series', 'tv' => 'series',
            'anime' => 'anime', 'аниме' => 'anime',
            'cartoon' => 'cartoon', 'мультфильм' => 'cartoon', 'animation' => 'cartoon',
        ];
        return $map[$type] ?? null;
    }

    private function normalizeCard(array $j, string $fallbackTitle, ?string $type): array
    {
        $arr = static function ($v): array {
            if (is_array($v)) {
                return array_values(array_filter(array_map(
                    static fn ($x) => trim((string) $x),
                    $v
                ), static fn ($x) => $x !== ''));
            }
            if (is_string($v) && $v !== '') {
                return array_values(array_filter(array_map('trim', explode(',', $v))));
            }
            return [];
        };

        $status = strtolower((string) ($j['status'] ?? 'published'));
        if (!in_array($status, ['published', 'coming_soon', 'in_cinema'], true)) {
            $status = 'published';
        }

        $rating = (float) ($j['rating'] ?? 0);
        $rating = max(0.0, min(10.0, $rating));

        return [
            'title'          => trim((string) ($j['title'] ?? '')) ?: $fallbackTitle,
            'original_title' => trim((string) ($j['original_title'] ?? '')),
            'description'    => trim((string) ($j['description_full'] ?? $j['description'] ?? '')),
            'description_short' => trim((string) ($j['description_short'] ?? '')),
            'year'           => isset($j['year']) && $j['year'] ? (int) $j['year'] : null,
            'genres'         => $arr($j['genres'] ?? null),
            'country'        => trim((string) ($j['country'] ?? '')),
            'director'       => trim((string) ($j['director'] ?? '')),
            'actors'         => implode(', ', $arr($j['actors'] ?? null)),
            'duration'       => isset($j['duration']) && $j['duration'] ? (int) $j['duration'] : null,
            'age_rating'     => trim((string) ($j['age_rating'] ?? '')),
            'rating'         => $rating,
            'category'       => $this->normalizeType($j['type'] ?? $type) ?? ($type ?? 'movie'),
            'status'         => $status,
            'language'       => trim((string) ($j['language'] ?? '')),
            'keywords'       => implode(', ', $arr($j['keywords'] ?? null)),
            'similar_titles' => $arr($j['similar_titles'] ?? null),
        ];
    }
}
