<?php

namespace CargoBot\Service;

use CargoBot\Database;
use CargoBot\Repository\UserRepo;
use CargoBot\Telegram\Api;

/** Уведомления администраторов и клиентов. */
class Notify
{
    private Database $db;
    private Api $api;
    /** @var int[] */
    private array $configAdmins;

    public function __construct(Database $db, Api $api, array $configAdmins)
    {
        $this->db = $db;
        $this->api = $api;
        $this->configAdmins = $configAdmins;
    }

    /** @return int[] ID из config.php + активные из таблицы admins. */
    public function adminIds(): array
    {
        $ids = array_merge($this->configAdmins, (new UserRepo($this->db))->adminTgIds());
        return array_values(array_unique(array_map('intval', $ids)));
    }

    public function isAdmin(int $tgId): bool
    {
        return in_array($tgId, $this->adminIds(), true);
    }

    public function toAdmins(string $text): void
    {
        foreach ($this->adminIds() as $id) {
            $this->api->sendMessage($id, $text);
        }
    }

    public function toUser(int $tgId, string $text): bool
    {
        return $this->api->sendMessage($tgId, $text) !== null;
    }
}
