<?php

declare(strict_types=1);

/**
 * Тесты на сами миграции. Нужны потому, что остальные тесты гоняются на SQLite,
 * а он гораздо терпимее MariaDB: например, спокойно принимает таблицу с именем
 * `databases`, на которой боевая MariaDB падает с syntax error 1064. Один раз мы
 * на это уже наступили при установке на сервер — здесь ловим заранее.
 */

/**
 * Зарезервированные слова MariaDB/MySQL, которые реально хочется использовать как
 * имена таблиц или колонок. Полный список длиннее, здесь — то, обо что спотыкаются.
 */
const HOSTING_RESERVED_WORDS = [
    'databases', 'database', 'tables', 'table', 'columns', 'column',
    'order', 'group', 'key', 'keys', 'index', 'indexes', 'primary', 'foreign',
    'select', 'insert', 'update', 'delete', 'from', 'where', 'having', 'join',
    'left', 'right', 'inner', 'outer', 'union', 'values', 'default', 'check',
    'condition', 'interval', 'read', 'write', 'range', 'partition', 'lines',
    'references', 'option', 'usage', 'grant', 'revoke', 'lock', 'unlock',
    'schema', 'schemas', 'trigger', 'procedure', 'function', 'call',
    'int', 'integer', 'float', 'double', 'decimal', 'char', 'varchar', 'blob',
    'match', 'against', 'rank', 'row', 'rows', 'when', 'then', 'else', 'case',
    'current_date', 'current_time', 'current_timestamp', 'localtime',
];

/** @return array<string,string> имя таблицы => файл миграции */
function hosting_migration_tables(): array
{
    $files = glob(dirname(__DIR__) . '/migrations/*.sql') ?: [];
    $tables = [];

    foreach ($files as $file) {
        $sql = (string) file_get_contents($file);
        preg_match_all(
            '~CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?([A-Za-z_][A-Za-z0-9_]*)`?~i',
            $sql,
            $matches
        );
        foreach ($matches[1] as $table) {
            $tables[strtolower($table)] = basename($file);
        }
    }

    return $tables;
}

/** @return list<string> имена таблиц в SQLite-зеркале для тестов */
function hosting_sqlite_tables(): array
{
    $sql = (string) file_get_contents(__DIR__ . '/schema.sqlite.sql');
    preg_match_all(
        '~CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?([A-Za-z_][A-Za-z0-9_]*)`?~i',
        $sql,
        $matches
    );
    return array_map('strtolower', $matches[1]);
}

function test_migrations_have_no_reserved_table_names(): void
{
    $tables = hosting_migration_tables();
    assert_true($tables !== [], 'Миграции должны находиться и парситься');

    foreach ($tables as $table => $file) {
        assert_false(
            in_array($table, HOSTING_RESERVED_WORDS, true),
            "Таблица `{$table}` ({$file}) названа зарезервированным словом MariaDB — "
            . 'на боевой базе это syntax error 1064, хотя SQLite такое проглотит'
        );
    }
}

function test_migration_column_names_avoid_reserved_words(): void
{
    $files = glob(dirname(__DIR__) . '/migrations/*.sql') ?: [];
    $problems = [];

    foreach ($files as $file) {
        foreach (preg_split('~\R~', (string) file_get_contents($file)) ?: [] as $line) {
            $line = trim($line);
            // Строка описания колонки: имя, пробел, тип. Пропускаем комментарии,
            // ключи, ограничения и всё, что не похоже на объявление колонки.
            if ($line === '' || str_starts_with($line, '--') || str_starts_with($line, ')')) {
                continue;
            }
            // \b в конце обязателен: без него тип INT совпадает с началом слова
            // INTO, и строка «INSERT INTO plans» принимается за объявление колонки.
            if (preg_match('~^`?([A-Za-z_][A-Za-z0-9_]*)`?\s+(BIGINT|TINYINT|INT|INTEGER|VARCHAR|TEXT|ENUM|TIMESTAMP|DATETIME|DATE|DECIMAL|CHAR|JSON)\b~i', $line, $m) !== 1) {
                continue;
            }
            $column = strtolower($m[1]);
            if (in_array($column, HOSTING_RESERVED_WORDS, true)) {
                $problems[] = basename($file) . ': ' . $column;
            }
        }
    }

    assert_equals([], $problems, 'Колонки названы зарезервированными словами MariaDB');
}

function test_sqlite_mirror_covers_same_tables_as_migrations(): void
{
    // Зеркало для тестов должно описывать ровно те же таблицы, что и боевые
    // миграции, иначе тесты зелёные, а прод падает (и наоборот).
    $migrationTables = array_keys(hosting_migration_tables());
    $sqliteTables = hosting_sqlite_tables();

    sort($migrationTables);
    sort($sqliteTables);

    $missingInSqlite = array_values(array_diff($migrationTables, $sqliteTables));
    $extraInSqlite = array_values(array_diff($sqliteTables, $migrationTables));

    assert_equals([], $missingInSqlite, 'Таблицы есть в миграциях, но их нет в SQLite-зеркале');
    assert_equals([], $extraInSqlite, 'Таблицы есть в SQLite-зеркале, но их нет в миграциях');
}
