<?php
namespace Bot;

use Core\Database;
use PDO;

/**
 * Write-side persistence used by the admin bot: create/delete movies and
 * announcements, gather statistics, list broadcast recipients.
 */
final class ContentRepo
{
    private PDO $db;

    public function __construct()
    {
        $this->db = Database::pdo();
    }

    public function createMovie(array $d): int
    {
        $sql = "INSERT INTO movies
                    (title, original_title, slug, description, poster, thumbnail, backdrop,
                     banner, trailer, watch_url, telegram_file_id,
                     category, country, release_date, year, age_rating, duration,
                     rating, language, director, actors, keywords, similar_titles, status,
                     is_new, is_popular, is_recommended)
                VALUES
                    (:title, :original_title, :slug, :description, :poster, :thumbnail, :backdrop,
                     :banner, :trailer, :watch_url, :telegram_file_id,
                     :category, :country, :release_date, :year, :age_rating, :duration,
                     :rating, :language, :director, :actors, :keywords, :similar_titles, :status,
                     :is_new, :is_popular, :is_recommended)";

        $release = $this->normalizeDate($d['release_date'] ?? null);
        $year    = $release ? (int) substr($release, 0, 4) : ($d['year'] ?? null);

        $similar = $d['similar_titles'] ?? null;
        if (is_array($similar)) {
            $similar = $similar ? json_encode(array_values($similar), JSON_UNESCAPED_UNICODE) : null;
        }

        // Reflect the requested status onto the home-page flags.
        $status = $d['status'] ?? 'published';
        $flags  = [
            'is_new'         => array_key_exists('is_new', $d) ? (int) $d['is_new'] : 1,
            'is_popular'     => !empty($d['is_popular']) ? 1 : 0,
            'is_recommended' => !empty($d['is_recommended']) ? 1 : 0,
        ];

        $stmt = $this->db->prepare($sql);
        $stmt->execute([
            ':title'          => $d['title'],
            ':original_title' => $d['original_title'] ?? null,
            ':slug'           => $this->slugify($d['title']),
            ':description'    => $d['description'] ?? null,
            ':poster'         => $d['poster'] ?? null,
            ':thumbnail'      => $d['thumbnail'] ?? null,
            ':backdrop'       => $d['backdrop'] ?? null,
            ':banner'         => $d['banner'] ?? null,
            ':trailer'        => $d['trailer'] ?? null,
            ':watch_url'      => $d['watch_url'] ?? null,
            ':telegram_file_id' => $d['telegram_file_id'] ?? null,
            ':category'       => $d['category'] ?? 'movie',
            ':country'        => $d['country'] ?? null,
            ':release_date'   => $release ?: null,
            ':year'           => $year,
            ':age_rating'     => $d['age_rating'] ?? null,
            ':duration'       => isset($d['duration']) ? (int) $d['duration'] : null,
            ':rating'         => isset($d['rating']) ? (float) $d['rating'] : 0,
            ':language'       => $d['language'] ?? null,
            ':director'       => $d['director'] ?? null,
            ':actors'         => $d['actors'] ?? null,
            ':keywords'       => $d['keywords'] ?? null,
            ':similar_titles' => $similar,
            ':status'         => $status,
            ':is_new'         => $flags['is_new'],
            ':is_popular'     => $flags['is_popular'],
            ':is_recommended' => $flags['is_recommended'],
        ]);

        $movieId = (int) $this->db->lastInsertId();

        if (!empty($d['genres'])) {
            $this->attachGenres($movieId, (array) $d['genres']);
        }

        // If a wide banner was produced, register it as an active hero banner.
        if (!empty($d['banner'])) {
            $this->db->prepare(
                "INSERT INTO banners (title, subtitle, image, movie_id, priority, is_active)
                 VALUES (?, ?, ?, ?, ?, 1)"
            )->execute([
                $d['title'],
                $d['country'] ?? null,
                $d['banner'],
                $movieId,
                20,
            ]);
        }

        return $movieId;
    }

    /** Read one value from the settings table. */
    public function getSetting(string $key): ?string
    {
        $stmt = $this->db->prepare("SELECT `value` FROM settings WHERE `key` = ?");
        $stmt->execute([$key]);
        $v = $stmt->fetchColumn();
        return $v === false ? null : (string) $v;
    }

    /** Write one value into the settings table. */
    public function setSetting(string $key, string $value): void
    {
        $sql = "INSERT INTO settings (`key`, `value`) VALUES (:k, :v)
                ON DUPLICATE KEY UPDATE `value` = :v2";
        $this->db->prepare($sql)->execute([':k' => $key, ':v' => $value, ':v2' => $value]);
    }

    /** Insert or update one episode of a series/anime. */
    public function createEpisode(int $movieId, int $season, int $episode, ?string $fileId, ?string $url, ?string $title = null): int
    {
        $sql = "INSERT INTO episodes (movie_id, season, episode, title, telegram_file_id, watch_url)
                VALUES (:m, :s, :e, :t, :fid, :url)
                ON DUPLICATE KEY UPDATE
                    title = VALUES(title),
                    telegram_file_id = VALUES(telegram_file_id),
                    watch_url = VALUES(watch_url)";
        $this->db->prepare($sql)->execute([
            ':m' => $movieId, ':s' => $season, ':e' => $episode,
            ':t' => $title, ':fid' => $fileId, ':url' => $url,
        ]);
        return (int) $this->db->lastInsertId();
    }

    public function episodeCount(int $movieId): int
    {
        $stmt = $this->db->prepare("SELECT COUNT(*) FROM episodes WHERE movie_id = ?");
        $stmt->execute([$movieId]);
        return (int) $stmt->fetchColumn();
    }

    /** Playable source of one episode addressed by movie/season/episode numbers. */
    public function episodePlayable(int $movieId, int $season, int $episode): ?array
    {
        $stmt = $this->db->prepare(
            "SELECT e.telegram_file_id, e.watch_url, e.season, e.episode, m.title
             FROM episodes e JOIN movies m ON m.id = e.movie_id
             WHERE e.movie_id = ? AND e.season = ? AND e.episode = ?"
        );
        $stmt->execute([$movieId, $season, $episode]);
        return $stmt->fetch() ?: null;
    }

    /** Recent series / anime titles (for the "add episodes" picker). */
    public function recentSeries(int $limit = 15): array
    {
        $limit = max(1, min(50, $limit));
        return $this->db->query(
            "SELECT id, title, category FROM movies
             WHERE category IN ('series','anime')
             ORDER BY id DESC LIMIT $limit"
        )->fetchAll();
    }

    /** Playable source for a movie (server-side use in video delivery). */
    public function playable(int $id): ?array
    {
        $stmt = $this->db->prepare(
            "SELECT id, title, telegram_file_id, watch_url, trailer FROM movies WHERE id = ?"
        );
        $stmt->execute([$id]);
        return $stmt->fetch() ?: null;
    }

    public function createAnnouncement(array $d): int
    {
        $sql = "INSERT INTO announcements
                    (title, description, poster, backdrop, trailer, category, genre,
                     rating, release_date, priority, is_active)
                VALUES
                    (:title, :description, :poster, :backdrop, :trailer, :category, :genre,
                     :rating, :release_date, :priority, 1)";
        $stmt = $this->db->prepare($sql);
        $stmt->execute([
            ':title'        => $d['title'],
            ':description'  => $d['description'] ?? null,
            ':poster'       => $d['poster'] ?? null,
            ':backdrop'     => $d['backdrop'] ?? null,
            ':trailer'      => $d['trailer'] ?? null,
            ':category'     => $d['category'] ?? 'movie',
            ':genre'        => $d['genre'] ?? null,
            ':rating'       => isset($d['rating']) ? (float) $d['rating'] : 0,
            ':release_date' => $this->normalizeDate($d['release_date'] ?? null),
            ':priority'     => (int) ($d['priority'] ?? 10),
        ]);
        $annId = (int) $this->db->lastInsertId();

        // Also surface as a hero banner if an image is present
        $image = ($d['backdrop'] ?? null) ?: ($d['poster'] ?? null);
        if ($image) {
            $this->db->prepare(
                "INSERT INTO banners (title, subtitle, image, announcement_id, priority, is_active)
                 VALUES (?, ?, ?, ?, ?, 1)"
            )->execute([
                $d['title'],
                $d['genre'] ?? null,
                $image,
                $annId,
                (int) ($d['priority'] ?? 10),
            ]);
        }
        return $annId;
    }

    /**
     * Accepts a date typed by a human and returns a MySQL DATE or null.
     * Supports YYYY-MM-DD, DD.MM.YYYY (also / and -), and a bare year;
     * anything unrecognised becomes null instead of failing the INSERT.
     */
    private function normalizeDate($value): ?string
    {
        $v = trim((string) $value);
        if ($v === '' || $v === '-') {
            return null;
        }
        if (preg_match('/^(\d{4})-(\d{1,2})-(\d{1,2})$/', $v, $m)) {
            return checkdate((int) $m[2], (int) $m[3], (int) $m[1])
                ? sprintf('%04d-%02d-%02d', $m[1], $m[2], $m[3])
                : null;
        }
        if (preg_match('#^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$#', $v, $m)) {
            return checkdate((int) $m[2], (int) $m[1], (int) $m[3])
                ? sprintf('%04d-%02d-%02d', $m[3], $m[2], $m[1])
                : null;
        }
        if (preg_match('/^(\d{4})$/', $v, $m)) {
            return $m[1] . '-01-01';
        }
        $ts = strtotime($v);
        return $ts !== false ? date('Y-m-d', $ts) : null;
    }

    public function attachGenres(int $movieId, array $genreNames): void
    {
        foreach ($genreNames as $name) {
            $name = trim((string) $name);
            if ($name === '') {
                continue;
            }
            $stmt = $this->db->prepare("SELECT id FROM genres WHERE name = ? OR slug = ? LIMIT 1");
            $stmt->execute([$name, $this->slugify($name)]);
            $gid = $stmt->fetchColumn();
            if (!$gid) {
                $this->db->prepare("INSERT INTO genres (name, slug) VALUES (?, ?)")
                         ->execute([$name, $this->slugify($name)]);
                $gid = (int) $this->db->lastInsertId();
            }
            $this->db->prepare(
                "INSERT IGNORE INTO movie_genres (movie_id, genre_id) VALUES (?, ?)"
            )->execute([$movieId, (int) $gid]);
        }
    }

    public function deleteMovie(int $id): bool
    {
        return $this->db->prepare("DELETE FROM movies WHERE id = ?")->execute([$id]);
    }

    public function recentMovies(int $limit = 10): array
    {
        $limit = max(1, min(50, $limit));
        return $this->db->query(
            "SELECT id, title, category, status FROM movies ORDER BY id DESC LIMIT $limit"
        )->fetchAll();
    }

    public function stats(): array
    {
        // Each metric is isolated so a missing table (e.g. episodes before the
        // upgrade) degrades to 0 instead of breaking the whole report.
        $one = function (string $sql): int {
            try {
                return (int) $this->db->query($sql)->fetchColumn();
            } catch (\Throwable $e) {
                return 0;
            }
        };

        return [
            'users'          => $one("SELECT COUNT(*) FROM users"),
            'users_today'    => $one("SELECT COUNT(*) FROM users WHERE DATE(created_at) = CURDATE()"),
            'users_week'     => $one("SELECT COUNT(*) FROM users WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"),
            'users_active'   => $one("SELECT COUNT(*) FROM users WHERE last_seen_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"),

            'total'          => $one("SELECT COUNT(*) FROM movies"),
            'movies'         => $one("SELECT COUNT(*) FROM movies WHERE category='movie'"),
            'series'         => $one("SELECT COUNT(*) FROM movies WHERE category='series'"),
            'anime'          => $one("SELECT COUNT(*) FROM movies WHERE category='anime'"),
            'cartoons'       => $one("SELECT COUNT(*) FROM movies WHERE category='cartoon'"),
            'coming_soon'    => $one("SELECT COUNT(*) FROM movies WHERE status='coming_soon'"),
            'episodes'       => $one("SELECT COUNT(*) FROM episodes"),
            'with_video'     => $one("SELECT COUNT(*) FROM movies WHERE telegram_file_id IS NOT NULL AND telegram_file_id <> ''"),
            'announcements'  => $one("SELECT COUNT(*) FROM announcements"),

            'favorites'      => $one("SELECT COUNT(*) FROM favorites"),
            'history'        => $one("SELECT COUNT(*) FROM history"),
            'views'          => $one("SELECT COUNT(*) FROM views"),
            'views_today'    => $one("SELECT COUNT(*) FROM views WHERE DATE(viewed_at) = CURDATE()"),
            'views_week'     => $one("SELECT COUNT(*) FROM views WHERE viewed_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"),
        ];
    }

    /** Most viewed titles, for the admin statistics screen. */
    public function topMovies(int $limit = 5): array
    {
        $limit = max(1, min(20, $limit));
        try {
            return $this->db->query(
                "SELECT title, views_count FROM movies
                 WHERE views_count > 0
                 ORDER BY views_count DESC LIMIT $limit"
            )->fetchAll();
        } catch (\Throwable $e) {
            return [];
        }
    }

    /** @return int[] telegram_ids of all users */
    public function allUserIds(): array
    {
        return array_map('intval', $this->db->query("SELECT telegram_id FROM users")->fetchAll(PDO::FETCH_COLUMN));
    }

    private function slugify(string $s): string
    {
        $s = mb_strtolower(trim($s));
        $s = preg_replace('/[^\p{L}\p{Nd}]+/u', '-', $s) ?? $s;
        return trim($s, '-') . '-' . substr(bin2hex(random_bytes(3)), 0, 5);
    }
}
