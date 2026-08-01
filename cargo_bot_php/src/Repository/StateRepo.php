<?php

namespace CargoBot\Repository;

use CargoBot\Database;

/**
 * Пошаговые диалоги (аналог FSM в aiogram).
 * PHP не помнит контекст между запросами, поэтому состояние
 * и промежуточные данные хранятся в таблице states.
 */
class StateRepo
{
    private Database $db;

    public function __construct(Database $db)
    {
        $this->db = $db;
    }

    public function state(int $chatId): ?string
    {
        $row = $this->db->one('SELECT state FROM states WHERE chat_id = :c', ['c' => $chatId]);
        return $row && $row['state'] !== null && $row['state'] !== '' ? (string) $row['state'] : null;
    }

    /** @return array<string,mixed> */
    public function data(int $chatId): array
    {
        $row = $this->db->one('SELECT data FROM states WHERE chat_id = :c', ['c' => $chatId]);
        if (!$row || !$row['data']) {
            return [];
        }
        $data = json_decode((string) $row['data'], true);
        return is_array($data) ? $data : [];
    }

    /** Устанавливает состояние; данные заменяются, если переданы. */
    public function set(int $chatId, ?string $state, ?array $data = null): void
    {
        $row = $this->db->one('SELECT id, data FROM states WHERE chat_id = :c', ['c' => $chatId]);
        $json = $data === null
            ? ($row['data'] ?? null)
            : json_encode($data, JSON_UNESCAPED_UNICODE);
        if ($row) {
            $this->db->update('states', (int) $row['id'], [
                'state'      => $state,
                'data'       => $json,
                'updated_at' => $this->db->now(),
            ]);
        } else {
            $this->db->insert('states', [
                'chat_id'    => $chatId,
                'state'      => $state,
                'data'       => $json,
                'updated_at' => $this->db->now(),
            ]);
        }
    }

    /** Дописывает значения в данные, не затрагивая состояние. */
    public function merge(int $chatId, array $values): array
    {
        $data = array_merge($this->data($chatId), $values);
        $this->set($chatId, $this->state($chatId), $data);
        return $data;
    }

    public function clear(int $chatId): void
    {
        $this->db->run('DELETE FROM states WHERE chat_id = :c', ['c' => $chatId]);
    }
}
