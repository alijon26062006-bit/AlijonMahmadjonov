<?php
declare(strict_types=1);

namespace Bot;

use Core\Logger;

/**
 * Downloads Telegram media (photos, videos) into the uploads directory and
 * returns a path relative to the uploads root (e.g. "posters/abc.jpg").
 */
final class Media
{
    public function __construct(
        private TelegramApi $api,
        private string $uploadsDir
    ) {}

    /**
     * @param string $fileId   Telegram file_id
     * @param string $subdir   posters|banners|trailers|screenshots
     * @param string $ext      target extension
     */
    public function save(string $fileId, string $subdir, string $ext = 'jpg'): ?string
    {
        $url = $this->api->getFileUrl($fileId);
        if ($url === null) {
            return null;
        }

        $bytes = @file_get_contents($url);
        if ($bytes === false) {
            Logger::error('Media download failed for ' . $fileId);
            return null;
        }

        $dir = rtrim($this->uploadsDir, '/') . '/' . $subdir;
        if (!is_dir($dir)) {
            @mkdir($dir, 0775, true);
        }

        $name = $subdir . '_' . bin2hex(random_bytes(8)) . '.' . $ext;
        $rel  = $subdir . '/' . $name;
        $abs  = rtrim($this->uploadsDir, '/') . '/' . $rel;

        if (@file_put_contents($abs, $bytes) === false) {
            Logger::error('Media write failed: ' . $abs);
            return null;
        }
        return $rel;
    }

    /** Pick the largest PhotoSize from a message's `photo` array. */
    public static function largestPhotoId(array $photos): ?string
    {
        if (!$photos) {
            return null;
        }
        usort($photos, static fn ($a, $b) => ($b['file_size'] ?? 0) <=> ($a['file_size'] ?? 0));
        return $photos[0]['file_id'] ?? null;
    }
}
