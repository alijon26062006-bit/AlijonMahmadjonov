<?php
namespace Models;

final class Episode extends Model
{
    /**
     * Episodes for a movie, grouped by season.
     *
     * @return array<int, array{season:int, episodes:array}>
     */
    public function forMovie(int $movieId): array
    {
        $stmt = $this->db->prepare(
            "SELECT id, season, episode, title, duration
             FROM episodes
             WHERE movie_id = ?
             ORDER BY season ASC, episode ASC"
        );
        $stmt->execute([$movieId]);

        $seasons = [];
        foreach ($stmt->fetchAll() as $row) {
            $s = (int) $row['season'];
            if (!isset($seasons[$s])) {
                $seasons[$s] = ['season' => $s, 'episodes' => []];
            }
            $seasons[$s]['episodes'][] = [
                'id'       => (int) $row['id'],
                'episode'  => (int) $row['episode'],
                'title'    => $row['title'],
                'duration' => $row['duration'] !== null ? (int) $row['duration'] : null,
            ];
        }
        return array_values($seasons);
    }

    public function count(int $movieId): int
    {
        $stmt = $this->db->prepare("SELECT COUNT(*) FROM episodes WHERE movie_id = ?");
        $stmt->execute([$movieId]);
        return (int) $stmt->fetchColumn();
    }

    /** Server-side playback source for one episode. */
    public function playable(int $id): ?array
    {
        $stmt = $this->db->prepare(
            "SELECT e.id, e.season, e.episode, e.telegram_file_id, e.watch_url,
                    m.title AS movie_title
             FROM episodes e JOIN movies m ON m.id = e.movie_id
             WHERE e.id = ?"
        );
        $stmt->execute([$id]);
        return $stmt->fetch() ?: null;
    }
}
