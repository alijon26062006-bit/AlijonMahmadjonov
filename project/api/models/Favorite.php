<?php
namespace Models;

final class Favorite extends Model
{
    /** Toggle a favorite. Returns true if now favorited, false if removed. */
    public function toggle(int $userId, int $movieId): bool
    {
        $stmt = $this->db->prepare("SELECT id FROM favorites WHERE user_id = ? AND movie_id = ?");
        $stmt->execute([$userId, $movieId]);
        if ($stmt->fetch()) {
            $this->db->prepare("DELETE FROM favorites WHERE user_id = ? AND movie_id = ?")
                     ->execute([$userId, $movieId]);
            return false;
        }
        $this->db->prepare("INSERT INTO favorites (user_id, movie_id) VALUES (?, ?)")
                 ->execute([$userId, $movieId]);
        return true;
    }

    /** Movie ids favorited by a user. */
    public function idsFor(int $userId): array
    {
        $stmt = $this->db->prepare("SELECT movie_id FROM favorites WHERE user_id = ?");
        $stmt->execute([$userId]);
        return array_map('intval', $stmt->fetchAll(\PDO::FETCH_COLUMN));
    }
}
