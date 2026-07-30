<?php
declare(strict_types=1);

namespace Models;

final class Movie extends Model
{
    /** Columns returned in list views (lightweight). */
    private const LIST_COLS =
        'id, title, slug, poster, backdrop, category, country, year, release_date,
         age_rating, duration, rating, status, is_new, is_popular, is_recommended, views_count';

    /**
     * Fetch a single movie with genres and formatted fields.
     */
    public function find(int $id): ?array
    {
        $stmt = $this->db->prepare("SELECT * FROM movies WHERE id = ?");
        $stmt->execute([$id]);
        $row = $stmt->fetch();
        if (!$row) {
            return null;
        }
        return $this->hydrate($row, true);
    }

    /**
     * Generic filtered listing.
     *
     * @param array $f  Supported keys: category, status, genre (slug), country,
     *                  year, min_rating, type_flag (new|popular|recommended),
     *                  sort, search, limit, offset
     */
    public function all(array $f = []): array
    {
        $cols = self::LIST_COLS;
        $sql  = "SELECT DISTINCT $cols FROM movies m";
        $where = [];
        $args  = [];

        if (!empty($f['genre'])) {
            $sql .= " JOIN movie_genres mg ON mg.movie_id = m.id
                      JOIN genres g ON g.id = mg.genre_id AND g.slug = :genre";
            $args[':genre'] = $f['genre'];
        }

        // Default: only published titles are visible in the app
        $status = $f['status'] ?? 'published';
        if ($status !== 'any') {
            $where[] = 'm.status = :status';
            $args[':status'] = $status;
        }

        if (!empty($f['category'])) {
            $where[] = 'm.category = :category';
            $args[':category'] = $f['category'];
        }
        if (!empty($f['country'])) {
            $where[] = 'm.country LIKE :country';
            $args[':country'] = '%' . $f['country'] . '%';
        }
        if (!empty($f['year'])) {
            $where[] = 'm.year = :year';
            $args[':year'] = (int) $f['year'];
        }
        if (!empty($f['min_rating'])) {
            $where[] = 'm.rating >= :min_rating';
            $args[':min_rating'] = (float) $f['min_rating'];
        }
        if (!empty($f['type_flag'])) {
            $flagCol = ['new' => 'is_new', 'popular' => 'is_popular', 'recommended' => 'is_recommended'][$f['type_flag']] ?? null;
            if ($flagCol) {
                $where[] = "m.$flagCol = 1";
            }
        }
        if (!empty($f['search'])) {
            $where[] = '(m.title LIKE :search OR m.description LIKE :search OR m.actors LIKE :search)';
            $args[':search'] = '%' . $f['search'] . '%';
        }

        // The columns list already prefixes with m. via SELECT DISTINCT — rewrite bare cols
        $sql = str_replace(self::LIST_COLS, $this->prefix(self::LIST_COLS, 'm'), $sql);

        if ($where) {
            $sql .= ' WHERE ' . implode(' AND ', $where);
        }

        $sql .= ' ORDER BY ' . $this->orderBy($f['sort'] ?? 'newest');

        $limit  = min(60, max(1, (int) ($f['limit'] ?? 20)));
        $offset = max(0, (int) ($f['offset'] ?? 0));
        $sql .= " LIMIT $limit OFFSET $offset";

        $stmt = $this->db->prepare($sql);
        $stmt->execute($args);
        $rows = $stmt->fetchAll();

        return array_map(fn ($r) => $this->hydrate($r, false), $rows);
    }

    /** Movies similar to $id (same category, sharing a genre). */
    public function similar(int $id, int $limit = 12): array
    {
        $sql = "SELECT DISTINCT " . $this->prefix(self::LIST_COLS, 'm') . "
                FROM movies m
                JOIN movie_genres mg ON mg.movie_id = m.id
                WHERE mg.genre_id IN (SELECT genre_id FROM movie_genres WHERE movie_id = :id)
                  AND m.id <> :id2
                  AND m.status = 'published'
                ORDER BY m.rating DESC
                LIMIT $limit";
        $stmt = $this->db->prepare($sql);
        $stmt->execute([':id' => $id, ':id2' => $id]);
        return array_map(fn ($r) => $this->hydrate($r, false), $stmt->fetchAll());
    }

    public function incrementViews(int $id, ?int $userId = null): void
    {
        $this->db->prepare("UPDATE movies SET views_count = views_count + 1 WHERE id = ?")->execute([$id]);
        $this->db->prepare("INSERT INTO views (movie_id, user_id) VALUES (?, ?)")->execute([$id, $userId]);
    }

    public function totalCount(): int
    {
        return (int) $this->db->query("SELECT COUNT(*) FROM movies")->fetchColumn();
    }

    // --------------------------------------------------------------------

    private function orderBy(string $sort): string
    {
        return match ($sort) {
            'rating'  => 'm.rating DESC, m.id DESC',
            'popular' => 'm.views_count DESC, m.id DESC',
            'year'    => 'm.year DESC, m.id DESC',
            'title'   => 'm.title ASC',
            'soon'    => 'm.release_date ASC',
            default   => 'm.created_at DESC, m.id DESC', // newest
        };
    }

    private function prefix(string $cols, string $alias): string
    {
        $parts = array_map('trim', explode(',', $cols));
        return implode(', ', array_map(fn ($c) => "$alias.$c", $parts));
    }

    private function genresFor(int $movieId): array
    {
        $stmt = $this->db->prepare(
            "SELECT g.id, g.name, g.slug
             FROM genres g JOIN movie_genres mg ON mg.genre_id = g.id
             WHERE mg.movie_id = ?"
        );
        $stmt->execute([$movieId]);
        return $stmt->fetchAll();
    }

    /** Format a DB row for the API (absolute media URLs, decoded JSON, genres). */
    private function hydrate(array $row, bool $full): array
    {
        $cfg = $GLOBALS['APP_CONFIG'] ?? [];
        $base = $cfg['app']['uploads_url'] ?? '';

        $media = static function (?string $v) use ($base): ?string {
            if (!$v) {
                return null;
            }
            return preg_match('#^https?://#', $v) ? $v : rtrim($base, '/') . '/' . ltrim($v, '/');
        };

        $row['poster']   = $media($row['poster']   ?? null);
        $row['backdrop'] = $media($row['backdrop'] ?? null);

        if (array_key_exists('rating', $row)) {
            $row['rating'] = (float) $row['rating'];
        }
        foreach (['is_new', 'is_popular', 'is_recommended'] as $b) {
            if (isset($row[$b])) {
                $row[$b] = (bool) $row[$b];
            }
        }

        $row['genres'] = $this->genresFor((int) $row['id']);

        if ($full) {
            $row['trailer'] = $media($row['trailer'] ?? null);
            $shots = json_decode($row['screenshots'] ?? '[]', true) ?: [];
            $row['screenshots'] = array_map($media, is_array($shots) ? $shots : []);
            $row['actors'] = array_values(array_filter(array_map('trim', explode(',', (string) ($row['actors'] ?? '')))));
        }

        return $row;
    }
}
