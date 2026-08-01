<?php

namespace CargoBot\Repository;

use CargoBot\Database;
use CargoBot\Schema;

/** Настройки: правила округления, списки статусов, приветствие и т.д. */
class SettingsRepo
{
    private Database $db;
    private string $keyCol;

    public function __construct(Database $db)
    {
        $this->db = $db;
        $this->keyCol = Schema::keyCol($db->driver());
    }

    public function get(string $key, ?string $default = null): ?string
    {
        $row = $this->db->one(
            "SELECT value FROM settings WHERE {$this->keyCol} = :k",
            ['k' => $key]
        );
        return $row ? (string) $row['value'] : $default;
    }

    /** @return mixed */
    public function getJson(string $key, $default = null)
    {
        $raw = $this->get($key);
        if ($raw === null) {
            return $default;
        }
        $data = json_decode($raw, true);
        return $data === null ? $default : $data;
    }

    public function set(string $key, string $value, ?string $description = null): void
    {
        $row = $this->db->one(
            "SELECT id FROM settings WHERE {$this->keyCol} = :k",
            ['k' => $key]
        );
        if ($row) {
            $data = ['value' => $value];
            if ($description !== null) {
                $data['description'] = $description;
            }
            $this->db->update('settings', (int) $row['id'], $data);
        } else {
            $this->db->run(
                "INSERT INTO settings ({$this->keyCol}, value, description) VALUES (:k, :v, :d)",
                ['k' => $key, 'v' => $value, 'd' => $description]
            );
        }
    }
}
