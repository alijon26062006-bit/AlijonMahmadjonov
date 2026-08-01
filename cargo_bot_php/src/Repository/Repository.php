<?php

namespace CargoBot\Repository;

use CargoBot\Database;

/** Универсальный доступ к любой таблице. */
class Repository
{
    private Database $db;
    private string $table;

    public function __construct(Database $db, string $table)
    {
        $this->db = $db;
        $this->table = $table;
    }

    public function get(int $id): ?array
    {
        return $this->db->one("SELECT * FROM {$this->table} WHERE id = :id", ['id' => $id]);
    }

    /**
     * @param array<string,mixed> $where простые равенства (значение null -> IS NULL)
     */
    public function all(array $where = [], string $orderBy = 'id', ?int $limit = null, int $offset = 0): array
    {
        [$sql, $params] = $this->whereSql($where);
        $q = "SELECT * FROM {$this->table}{$sql} ORDER BY {$orderBy}";
        if ($limit !== null) {
            $q .= " LIMIT {$limit} OFFSET {$offset}";
        }
        return $this->db->all($q, $params);
    }

    public function count(array $where = []): int
    {
        [$sql, $params] = $this->whereSql($where);
        return (int) $this->db->value("SELECT COUNT(*) FROM {$this->table}{$sql}", $params);
    }

    public function insert(array $data): int
    {
        return $this->db->insert($this->table, $data);
    }

    public function update(int $id, array $data): void
    {
        $this->db->update($this->table, $id, $data);
    }

    public function delete(int $id): void
    {
        $this->db->delete($this->table, $id);
    }

    private function whereSql(array $where): array
    {
        if (!$where) {
            return ['', []];
        }
        $parts = [];
        $params = [];
        foreach ($where as $col => $value) {
            if ($value === null) {
                $parts[] = "$col IS NULL";
            } else {
                $parts[] = "$col = :w_$col";
                $params["w_$col"] = $value;
            }
        }
        return [' WHERE ' . implode(' AND ', $parts), $params];
    }
}
