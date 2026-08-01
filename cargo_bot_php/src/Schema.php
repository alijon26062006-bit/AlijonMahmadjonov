<?php

namespace CargoBot;

/**
 * Схема базы данных. Один и тот же набор таблиц создаётся
 * и в MySQL, и в SQLite — различия подставляются автоматически.
 */
class Schema
{
    /** @return string[] */
    public static function statements(string $driver): array
    {
        $mysql = ($driver === 'mysql');
        $pk    = $mysql ? 'INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY'
                        : 'INTEGER PRIMARY KEY AUTOINCREMENT';
        $big   = $mysql ? 'BIGINT' : 'INTEGER';
        $opt   = $mysql ? ' ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci' : '';
        $money = 'DECIMAL(14,4)';

        $t = [];

        $t['users'] = "CREATE TABLE IF NOT EXISTS users (
            id $pk,
            tg_id $big NOT NULL UNIQUE,
            username VARCHAR(128) NULL,
            full_name VARCHAR(256) NULL,
            phone VARCHAR(32) NULL,
            language VARCHAR(8) NOT NULL DEFAULT 'ru',
            is_blocked TINYINT NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )$opt";

        $t['admins'] = "CREATE TABLE IF NOT EXISTS admins (
            id $pk,
            tg_id $big NOT NULL UNIQUE,
            name VARCHAR(256) NULL,
            is_active TINYINT NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )$opt";

        $t['delivery_types'] = "CREATE TABLE IF NOT EXISTS delivery_types (
            id $pk,
            name VARCHAR(128) NOT NULL,
            emoji VARCHAR(16) NULL,
            is_active TINYINT NOT NULL DEFAULT 1,
            sort_order INT NOT NULL DEFAULT 0
        )$opt";

        $t['categories'] = "CREATE TABLE IF NOT EXISTS categories (
            id $pk,
            name VARCHAR(128) NOT NULL,
            is_active TINYINT NOT NULL DEFAULT 1,
            sort_order INT NOT NULL DEFAULT 0
        )$opt";

        $t['currencies'] = "CREATE TABLE IF NOT EXISTS currencies (
            id $pk,
            code VARCHAR(8) NOT NULL UNIQUE,
            name VARCHAR(64) NOT NULL,
            symbol VARCHAR(8) NULL,
            is_base TINYINT NOT NULL DEFAULT 0,
            is_active TINYINT NOT NULL DEFAULT 1
        )$opt";

        $t['exchange_rates'] = "CREATE TABLE IF NOT EXISTS exchange_rates (
            id $pk,
            currency_id INT NOT NULL,
            rate $money NOT NULL,
            updated_by $big NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )$opt";

        $t['tariffs'] = "CREATE TABLE IF NOT EXISTS tariffs (
            id $pk,
            name VARCHAR(256) NOT NULL,
            delivery_type_id INT NOT NULL,
            category_id INT NULL,
            price_per_kg $money NOT NULL,
            min_order_cost $money NOT NULL DEFAULT 0,
            min_weight $money NOT NULL DEFAULT 0,
            currency_code VARCHAR(8) NOT NULL DEFAULT 'USD',
            delivery_time VARCHAR(128) NULL,
            is_active TINYINT NOT NULL DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NULL
        )$opt";

        $t['coefficients'] = "CREATE TABLE IF NOT EXISTS coefficients (
            id $pk,
            name VARCHAR(256) NOT NULL,
            code VARCHAR(32) NOT NULL DEFAULT 'volumetric',
            delivery_type_id INT NULL,
            category_id INT NULL,
            value $money NOT NULL,
            is_active TINYINT NOT NULL DEFAULT 1
        )$opt";

        $t['extra_services'] = "CREATE TABLE IF NOT EXISTS extra_services (
            id $pk,
            name VARCHAR(256) NOT NULL,
            kind VARCHAR(16) NOT NULL DEFAULT 'fee',
            calc_type VARCHAR(16) NOT NULL DEFAULT 'fixed',
            value $money NOT NULL,
            delivery_type_id INT NULL,
            category_id INT NULL,
            is_active TINYINT NOT NULL DEFAULT 1
        )$opt";

        $t['orders'] = "CREATE TABLE IF NOT EXISTS orders (
            id $pk,
            number VARCHAR(32) NOT NULL,
            user_id INT NULL,
            name VARCHAR(256) NOT NULL,
            phone VARCHAR(64) NOT NULL,
            product_url TEXT NULL,
            description TEXT NULL,
            weight $money NULL,
            volume DECIMAL(14,6) NULL,
            comment TEXT NULL,
            status VARCHAR(64) NOT NULL DEFAULT 'Новая',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NULL
        )$opt";

        $t['tracks'] = "CREATE TABLE IF NOT EXISTS tracks (
            id $pk,
            track_number VARCHAR(64) NOT NULL UNIQUE,
            user_id INT NULL,
            order_id INT NULL,
            status VARCHAR(128) NOT NULL DEFAULT 'Получен на складе',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NULL
        )$opt";

        $t['track_history'] = "CREATE TABLE IF NOT EXISTS track_history (
            id $pk,
            track_id INT NOT NULL,
            status VARCHAR(128) NOT NULL,
            comment TEXT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )$opt";

        $t['calculations'] = "CREATE TABLE IF NOT EXISTS calculations (
            id $pk,
            user_id INT NULL,
            tariff_id INT NULL,
            delivery_type VARCHAR(128) NULL,
            category VARCHAR(128) NULL,
            weight $money NULL,
            volume DECIMAL(14,6) NULL,
            chargeable_weight $money NULL,
            total $money NULL,
            currency_code VARCHAR(8) NULL,
            details TEXT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )$opt";

        $t['faq'] = "CREATE TABLE IF NOT EXISTS faq (
            id $pk,
            question VARCHAR(512) NOT NULL,
            answer TEXT NOT NULL,
            is_active TINYINT NOT NULL DEFAULT 1,
            sort_order INT NOT NULL DEFAULT 0
        )$opt";

        $t['contacts'] = "CREATE TABLE IF NOT EXISTS contacts (
            id $pk,
            title VARCHAR(256) NOT NULL,
            value TEXT NOT NULL,
            is_active TINYINT NOT NULL DEFAULT 1,
            sort_order INT NOT NULL DEFAULT 0
        )$opt";

        $t['warehouses'] = "CREATE TABLE IF NOT EXISTS warehouses (
            id $pk,
            name VARCHAR(256) NOT NULL,
            address TEXT NOT NULL,
            note TEXT NULL,
            is_active TINYINT NOT NULL DEFAULT 1,
            sort_order INT NOT NULL DEFAULT 0
        )$opt";

        $t['logs'] = "CREATE TABLE IF NOT EXISTS logs (
            id $pk,
            actor_tg_id $big NULL,
            action VARCHAR(64) NOT NULL,
            entity VARCHAR(64) NOT NULL,
            entity_id INT NULL,
            old_data TEXT NULL,
            new_data TEXT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )$opt";

        $t['broadcasts'] = "CREATE TABLE IF NOT EXISTS broadcasts (
            id $pk,
            admin_tg_id $big NOT NULL,
            text TEXT NOT NULL,
            total INT NOT NULL DEFAULT 0,
            sent INT NOT NULL DEFAULT 0,
            failed INT NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )$opt";

        $t['settings'] = "CREATE TABLE IF NOT EXISTS settings (
            id $pk,
            `key` VARCHAR(64) NOT NULL UNIQUE,
            value TEXT NOT NULL,
            description TEXT NULL
        )$opt";

        // Состояния пошаговых диалогов (аналог FSM): PHP не помнит контекст между запросами
        $t['states'] = "CREATE TABLE IF NOT EXISTS states (
            id $pk,
            chat_id $big NOT NULL UNIQUE,
            state VARCHAR(64) NULL,
            data TEXT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )$opt";

        if (!$mysql) {
            // в SQLite обратные кавычки для `key` тоже допустимы, но приведём к общему виду
            $t['settings'] = str_replace('`key`', '"key"', $t['settings']);
        }

        $out = array_values($t);
        $out[] = 'CREATE INDEX IF NOT EXISTS idx_orders_number ON orders (number)';
        $out[] = 'CREATE INDEX IF NOT EXISTS idx_track_history_track ON track_history (track_id)';
        $out[] = 'CREATE INDEX IF NOT EXISTS idx_logs_actor ON logs (actor_tg_id)';
        return $out;
    }

    /** Имя колонки key с правильным экранированием для драйвера. */
    public static function keyCol(string $driver): string
    {
        return $driver === 'mysql' ? '`key`' : '"key"';
    }
}
