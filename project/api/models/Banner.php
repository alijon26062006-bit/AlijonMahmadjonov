<?php
declare(strict_types=1);

namespace Models;

/**
 * Hero banners. If no explicit banner rows exist, the API falls back to
 * active announcements so the hero is never empty.
 */
final class Banner extends Model
{
    public function active(int $limit = 8): array
    {
        $sql = "SELECT b.id, b.title, b.subtitle, b.image, b.movie_id, b.announcement_id,
                       m.rating AS movie_rating, m.year AS movie_year, m.description AS movie_desc,
                       a.rating AS ann_rating, a.description AS ann_desc,
                       a.release_date AS ann_release, a.genre AS ann_genre
                FROM banners b
                LEFT JOIN movies m        ON m.id = b.movie_id
                LEFT JOIN announcements a ON a.id = b.announcement_id
                WHERE b.is_active = 1
                ORDER BY b.priority DESC, b.created_at DESC
                LIMIT $limit";
        $stmt = $this->db->query($sql);
        $rows = $stmt->fetchAll();

        $cfg  = $GLOBALS['APP_CONFIG'] ?? [];
        $base = $cfg['app']['uploads_url'] ?? '';
        $media = static fn (?string $v) => $v
            ? (preg_match('#^https?://#', $v) ? $v : rtrim($base, '/') . '/' . ltrim($v, '/'))
            : null;

        return array_map(static function ($r) use ($media) {
            return [
                'id'          => (int) $r['id'],
                'title'       => $r['title'],
                'subtitle'    => $r['subtitle'],
                'image'       => $media($r['image']),
                'description' => $r['movie_desc'] ?? $r['ann_desc'],
                'rating'      => (float) ($r['movie_rating'] ?? $r['ann_rating'] ?? 0),
                'genre'       => $r['ann_genre'],
                'year'        => $r['movie_year'],
                'release_date'=> $r['ann_release'],
                'movie_id'    => $r['movie_id'] ? (int) $r['movie_id'] : null,
            ];
        }, $rows);
    }
}
