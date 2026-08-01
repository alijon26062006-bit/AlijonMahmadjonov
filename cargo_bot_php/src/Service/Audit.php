<?php

namespace CargoBot\Service;

use CargoBot\Database;

/** Журнал изменений: кто, когда, что было и что стало. */
class Audit
{
    private Database $db;

    public function __construct(Database $db)
    {
        $this->db = $db;
    }

    public function log(?int $actorTgId, string $action, string $entity,
                        ?int $entityId = null, ?array $old = null, ?array $new = null): void
    {
        $this->db->insert('logs', [
            'actor_tg_id' => $actorTgId,
            'action'      => $action,
            'entity'      => $entity,
            'entity_id'   => $entityId,
            'old_data'    => $old ? json_encode($old, JSON_UNESCAPED_UNICODE) : null,
            'new_data'    => $new ? json_encode($new, JSON_UNESCAPED_UNICODE) : null,
            'created_at'  => $this->db->now(),
        ]);
    }

    /** Снимок записи для журнала (значения приводятся к строкам). */
    public static function snapshot(?array $row, array $only = []): array
    {
        if (!$row) {
            return [];
        }
        $out = [];
        foreach ($row as $key => $value) {
            if ($only && !in_array($key, $only, true)) {
                continue;
            }
            $out[$key] = $value === null ? null : (string) $value;
        }
        return $out;
    }
}
