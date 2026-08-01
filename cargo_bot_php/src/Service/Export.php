<?php

namespace CargoBot\Service;

use CargoBot\Database;

/**
 * Экспорт в CSV с BOM — открывается в Excel двойным щелчком
 * и не требует библиотек, которых может не быть на хостинге.
 */
class Export
{
    private Database $db;
    private string $dir;

    public function __construct(Database $db, string $dir)
    {
        $this->db = $db;
        $this->dir = rtrim($dir, '/');
        if (!is_dir($this->dir)) {
            @mkdir($this->dir, 0775, true);
        }
    }

    public function orders(): string
    {
        $rows = $this->db->all('SELECT * FROM orders ORDER BY id');
        $data = [['№', 'Номер', 'Имя', 'Телефон', 'Ссылка', 'Описание',
                  'Вес, кг', 'Объём, м3', 'Комментарий', 'Статус', 'Создана']];
        foreach ($rows as $r) {
            $data[] = [
                $r['id'], $r['number'], $r['name'], $r['phone'], $r['product_url'],
                $r['description'], $r['weight'], $r['volume'], $r['comment'],
                $r['status'], $r['created_at'],
            ];
        }
        return $this->write('orders', $data);
    }

    public function users(): string
    {
        $rows = $this->db->all('SELECT * FROM users ORDER BY id');
        $data = [['№', 'Telegram ID', 'Username', 'Имя', 'Телефон', 'Язык', 'Регистрация']];
        foreach ($rows as $r) {
            $data[] = [
                $r['id'], $r['tg_id'], $r['username'], $r['full_name'],
                $r['phone'], $r['language'], $r['created_at'],
            ];
        }
        return $this->write('users', $data);
    }

    private function write(string $prefix, array $rows): string
    {
        $path = sprintf('%s/%s_%s.csv', $this->dir, $prefix, date('Ymd_His'));
        $fh = fopen($path, 'w');
        fwrite($fh, "\xEF\xBB\xBF"); // BOM, чтобы Excel правильно понял UTF-8
        foreach ($rows as $row) {
            fputcsv($fh, $row, ';');
        }
        fclose($fh);
        return $path;
    }
}
