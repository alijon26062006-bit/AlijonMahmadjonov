<?php
declare(strict_types=1);

namespace Models;

final class Announcement extends Model
{
    public function active(int $limit = 10): array
    {
        $stmt = $this->db->prepare(
            "SELECT * FROM announcements
             WHERE is_active = 1
             ORDER BY priority DESC, created_at DESC
             LIMIT $limit"
        );
        $stmt->execute();
        return array_map([$this, 'hydrate'], $stmt->fetchAll());
    }

    public function find(int $id): ?array
    {
        $stmt = $this->db->prepare("SELECT * FROM announcements WHERE id = ?");
        $stmt->execute([$id]);
        $row = $stmt->fetch();
        return $row ? $this->hydrate($row) : null;
    }

    private function hydrate(array $row): array
    {
        $cfg  = $GLOBALS['APP_CONFIG'] ?? [];
        $base = $cfg['app']['uploads_url'] ?? '';
        $media = static fn (?string $v) => $v
            ? (preg_match('#^https?://#', $v) ? $v : rtrim($base, '/') . '/' . ltrim($v, '/'))
            : null;

        $row['poster']   = $media($row['poster']);
        $row['backdrop'] = $media($row['backdrop']);
        $row['trailer']  = $media($row['trailer']);
        $row['rating']   = (float) $row['rating'];
        $row['is_active'] = (bool) $row['is_active'];
        return $row;
    }
}
