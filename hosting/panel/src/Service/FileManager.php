<?php
declare(strict_types=1);

namespace Hosting\Service;

use Hosting\Support\Path;

/**
 * Файловый менеджер клиента. Работает только внутри его домашнего каталога:
 * каждый путь прогоняется через Path::resolve, который ловит «..» и симлинки наружу.
 */
final class FileManager
{
    /** Файлы больше этого размера не открываем в редакторе. */
    public const MAX_EDIT_BYTES = 2 * 1024 * 1024;

    /** Расширения, которые нельзя загружать на хостинг. */
    public const BLOCKED_EXTENSIONS = ['php3', 'php4', 'phtml', 'so', 'exe', 'sh'];

    public function __construct(private string $home)
    {
        if (!is_dir($this->home)) {
            throw new \RuntimeException('Домашний каталог не найден: ' . $this->home);
        }
    }

    public function home(): string
    {
        return $this->home;
    }

    public function absolute(string $relative): string
    {
        return Path::resolve($this->home, $relative);
    }

    /**
     * Содержимое каталога: сначала папки, потом файлы, обе группы по алфавиту.
     *
     * @return list<array{name:string,path:string,is_dir:bool,size:int,modified:int}>
     */
    public function listDirectory(string $relative = ''): array
    {
        $absolute = $this->absolute($relative);
        if (!is_dir($absolute)) {
            throw new \RuntimeException('Это не каталог');
        }

        $prefix = Path::normalize($relative);
        $entries = [];

        foreach ((array) scandir($absolute) as $name) {
            if ($name === '.' || $name === '..') {
                continue;
            }
            $full = $absolute . '/' . $name;
            $entries[] = [
                'name'     => $name,
                'path'     => $prefix === '' ? $name : $prefix . '/' . $name,
                'is_dir'   => is_dir($full),
                'size'     => is_dir($full) ? 0 : (int) @filesize($full),
                'modified' => (int) @filemtime($full),
            ];
        }

        usort($entries, static function (array $a, array $b): int {
            if ($a['is_dir'] !== $b['is_dir']) {
                return $a['is_dir'] ? -1 : 1;
            }
            return strnatcasecmp($a['name'], $b['name']);
        });

        return $entries;
    }

    /** Хлебные крошки для навигации: [['Корень',''], ['sites','sites'], ...] */
    public function breadcrumbs(string $relative): array
    {
        $crumbs = [['name' => 'Корень', 'path' => '']];
        $walked = '';

        foreach (explode('/', Path::normalize($relative)) as $part) {
            if ($part === '') {
                continue;
            }
            $walked = $walked === '' ? $part : $walked . '/' . $part;
            $crumbs[] = ['name' => $part, 'path' => $walked];
        }

        return $crumbs;
    }

    public function makeDirectory(string $parent, string $name): string
    {
        $this->assertName($name);
        $target = $this->absolute(Path::normalize($parent) . '/' . $name);

        if (file_exists($target)) {
            throw new \RuntimeException('Такая папка или файл уже есть');
        }
        if (!@mkdir($target, 0o750)) {
            throw new \RuntimeException('Не удалось создать папку');
        }

        return $target;
    }

    public function createFile(string $parent, string $name, string $contents = ''): string
    {
        $this->assertName($name);
        $this->assertAllowedExtension($name);
        $target = $this->absolute(Path::normalize($parent) . '/' . $name);

        if (file_exists($target)) {
            throw new \RuntimeException('Такой файл уже есть');
        }
        if (@file_put_contents($target, $contents) === false) {
            throw new \RuntimeException('Не удалось создать файл');
        }

        return $target;
    }

    public function read(string $relative): string
    {
        $path = $this->absolute($relative);
        if (!is_file($path)) {
            throw new \RuntimeException('Файл не найден');
        }
        if (filesize($path) > self::MAX_EDIT_BYTES) {
            throw new \RuntimeException('Файл слишком большой для редактора (больше 2 МБ)');
        }

        $contents = @file_get_contents($path);
        if ($contents === false) {
            throw new \RuntimeException('Не удалось прочитать файл');
        }

        return $contents;
    }

    public function write(string $relative, string $contents): void
    {
        $path = $this->absolute($relative);
        if (!is_file($path)) {
            throw new \RuntimeException('Файл не найден');
        }
        if (@file_put_contents($path, $contents) === false) {
            throw new \RuntimeException('Не удалось сохранить файл');
        }
    }

    public function delete(string $relative): void
    {
        $path = $this->absolute($relative);
        if ($path === realpath($this->home)) {
            throw new \RuntimeException('Домашний каталог удалить нельзя');
        }
        if (!file_exists($path) && !is_link($path)) {
            throw new \RuntimeException('Файл не найден');
        }
        Path::removeTree($path);
    }

    public function rename(string $relative, string $newName): string
    {
        $this->assertName($newName);
        $path = $this->absolute($relative);
        if (!file_exists($path)) {
            throw new \RuntimeException('Файл не найден');
        }
        if (is_file($path)) {
            $this->assertAllowedExtension($newName);
        }

        $target = dirname($path) . '/' . $newName;
        if (file_exists($target)) {
            throw new \RuntimeException('Файл с таким именем уже есть');
        }
        if (!@rename($path, $target)) {
            throw new \RuntimeException('Не удалось переименовать');
        }

        return $target;
    }

    /**
     * Принимает файл из формы загрузки.
     *
     * @param array{name:string,tmp_name:string,error:int,size:int} $upload
     */
    public function saveUpload(string $parent, array $upload): string
    {
        if (($upload['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_OK) {
            throw new \RuntimeException('Файл не загрузился (код ' . (int) $upload['error'] . ')');
        }

        $name = basename((string) $upload['name']);
        $this->assertName($name);
        $this->assertAllowedExtension($name);

        $target = $this->absolute(Path::normalize($parent) . '/' . $name);
        $moved = is_uploaded_file($upload['tmp_name'])
            ? @move_uploaded_file($upload['tmp_name'], $target)
            : @rename($upload['tmp_name'], $target);

        if (!$moved) {
            throw new \RuntimeException('Не удалось сохранить файл');
        }

        return $target;
    }

    /** Не больше стольких записей в архиве — иначе распаковка «зип-бомбы» из миллиона файлов. */
    public const MAX_ZIP_ENTRIES = 20_000;

    /** Не больше стольких байт после распаковки — вторая линия защиты от зип-бомб, помимо квоты диска. */
    public const MAX_ZIP_UNCOMPRESSED_BYTES = 1_073_741_824; // 1 ГБ

    /**
     * Распаковывает ZIP в тот же каталог. Пути внутри архива нормализуются, за пределы
     * каталога назначения ничего не выпускается (Zip Slip). Перед распаковкой проверяются
     * заявленные в архиве число файлов и суммарный несжатый размер — если они превышают
     * лимиты (или переданную $maxTotalBytes — например, остаток дисковой квоты клиента),
     * архив не распаковывается вообще, а не обрывается на середине.
     *
     * @return int сколько файлов распаковано
     */
    public function unzip(string $relative, ?int $maxTotalBytes = null): int
    {
        if (!class_exists(\ZipArchive::class)) {
            throw new \RuntimeException('На сервере не включено расширение zip');
        }

        $archive = $this->absolute($relative);
        if (!is_file($archive)) {
            throw new \RuntimeException('Архив не найден');
        }

        $limitBytes = $maxTotalBytes !== null
            ? min($maxTotalBytes, self::MAX_ZIP_UNCOMPRESSED_BYTES)
            : self::MAX_ZIP_UNCOMPRESSED_BYTES;

        $destination = dirname($archive);
        $zip = new \ZipArchive();
        if ($zip->open($archive) !== true) {
            throw new \RuntimeException('Не удалось открыть архив');
        }

        if ($zip->numFiles > self::MAX_ZIP_ENTRIES) {
            $zip->close();
            throw new \RuntimeException(
                "В архиве слишком много файлов ({$zip->numFiles}), лимит — " . self::MAX_ZIP_ENTRIES
            );
        }

        // Первый проход — только смотрим заявленные размеры, ничего не пишем на диск.
        $totalUncompressed = 0;
        for ($i = 0; $i < $zip->numFiles; $i++) {
            $stat = $zip->statIndex($i);
            $totalUncompressed += (int) ($stat['size'] ?? 0);
            if ($totalUncompressed > $limitBytes) {
                $zip->close();
                throw new \RuntimeException(
                    'Архив после распаковки превысит допустимый размер (' . Path::humanSize($limitBytes) . ')'
                );
            }
        }

        $extracted = 0;
        for ($i = 0; $i < $zip->numFiles; $i++) {
            $entry = (string) $zip->getNameIndex($i);
            $safe = Path::normalize($entry);
            if ($safe === '') {
                continue;
            }

            $target = $destination . '/' . $safe;
            if (!Path::isInside($destination, $target)) {
                continue;
            }

            if (str_ends_with($entry, '/')) {
                if (!is_dir($target)) {
                    @mkdir($target, 0o750, true);
                }
                continue;
            }

            $parent = dirname($target);
            if (!is_dir($parent) && !@mkdir($parent, 0o750, true) && !is_dir($parent)) {
                continue;
            }

            $stream = $zip->getStream($entry);
            if ($stream === false) {
                continue;
            }
            $out = @fopen($target, 'wb');
            if ($out === false) {
                fclose($stream);
                continue;
            }
            stream_copy_to_stream($stream, $out);
            fclose($stream);
            fclose($out);
            $extracted++;
        }

        $zip->close();

        return $extracted;
    }

    private function assertName(string $name): void
    {
        if (!Path::isSafeName($name)) {
            throw new \RuntimeException(
                'Недопустимое имя. Разрешены буквы, цифры, точка, дефис и подчёркивание'
            );
        }
    }

    private function assertAllowedExtension(string $name): void
    {
        $extension = strtolower(pathinfo($name, PATHINFO_EXTENSION));
        if (in_array($extension, self::BLOCKED_EXTENSIONS, true)) {
            throw new \RuntimeException('Файлы с расширением .' . $extension . ' загружать нельзя');
        }
    }
}
