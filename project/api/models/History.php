<?php
declare(strict_types=1);

namespace Models;

final class History extends Model
{
    /** Upsert watch progress for a user/movie. */
    public function record(int $userId, int $movieId, int $progress = 0): void
    {
        $progress = max(0, min(100, $progress));
        $sql = "INSERT INTO history (user_id, movie_id, progress)
                VALUES (:u, :m, :p)
                ON DUPLICATE KEY UPDATE progress = :p2, updated_at = NOW()";
        $this->db->prepare($sql)->execute([
            ':u' => $userId, ':m' => $movieId, ':p' => $progress, ':p2' => $progress,
        ]);
    }

    /** "Continue watching" — recent movies joined with progress. */
    public function recent(int $userId, int $limit = 20): array
    {
        $sql = "SELECT h.progress, h.updated_at,
                       m.id, m.title, m.poster, m.backdrop, m.category, m.year,
                       m.rating, m.age_rating, m.duration
                FROM history h
                JOIN movies m ON m.id = h.movie_id
                WHERE h.user_id = :u AND m.status = 'published'
                ORDER BY h.updated_at DESC
                LIMIT $limit";
        $stmt = $this->db->prepare($sql);
        $stmt->execute([':u' => $userId]);

        $cfg  = $GLOBALS['APP_CONFIG'] ?? [];
        $base = $cfg['app']['uploads_url'] ?? '';
        $media = static fn (?string $v) => $v
            ? (preg_match('#^https?://#', $v) ? $v : rtrim($base, '/') . '/' . ltrim($v, '/'))
            : null;

        return array_map(static function ($r) use ($media) {
            $r['poster']   = $media($r['poster']);
            $r['backdrop'] = $media($r['backdrop']);
            $r['rating']   = (float) $r['rating'];
            $r['progress'] = (int) $r['progress'];
            return $r;
        }, $stmt->fetchAll());
    }
}
