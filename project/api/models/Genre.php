<?php
declare(strict_types=1);

namespace Models;

final class Genre extends Model
{
    public function all(): array
    {
        return $this->db->query("SELECT id, name, slug FROM genres ORDER BY name")->fetchAll();
    }

    public function findBySlug(string $slug): ?array
    {
        $stmt = $this->db->prepare("SELECT id, name, slug FROM genres WHERE slug = ?");
        $stmt->execute([$slug]);
        return $stmt->fetch() ?: null;
    }
}
