<?php
declare(strict_types=1);

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

        $release = $d['release_date'] ?? null;
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
            ':release_date' => $d['release_date'] ?? null,
            ':priority'     => (int) ($d['priority'] ?? 10),
        ]);
        $annId = (int) $this->db->lastInsertId();

        // Also surface as a hero banner if a backdrop is present
        if (!empty($d['backdrop']) || !empty($d['poster'])) {
            $this->db->prepare(
                "INSERT INTO banners (title, subtitle, image, announcement_id, priority, is_active)
                 VALUES (?, ?, ?, ?, ?, 1)"
            )->execute([
                $d['title'],
                $d['genre'] ?? null,
                $d['backdrop'] ?: $d['poster'],
                $annId,
                (int) ($d['priority'] ?? 10),
            ]);
        }
        return $annId;
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
        $one = fn (string $sql) => (int) $this->db->query($sql)->fetchColumn();
        return [
            'users'         => $one("SELECT COUNT(*) FROM users"),
            'movies'        => $one("SELECT COUNT(*) FROM movies"),
            'series'        => $one("SELECT COUNT(*) FROM movies WHERE category='series'"),
            'anime'         => $one("SELECT COUNT(*) FROM movies WHERE category='anime'"),
            'cartoons'      => $one("SELECT COUNT(*) FROM movies WHERE category='cartoon'"),
            'announcements' => $one("SELECT COUNT(*) FROM announcements"),
            'favorites'     => $one("SELECT COUNT(*) FROM favorites"),
            'views'         => $one("SELECT COUNT(*) FROM views"),
        ];
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
