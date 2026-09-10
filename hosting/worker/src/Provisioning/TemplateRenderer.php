<?php
declare(strict_types=1);

namespace Hosting\Worker\Provisioning;

/** Подстановка {{KEY}} → значение в текстовых шаблонах nginx/php-fpm/systemd. */
final class TemplateRenderer
{
    public function __construct(private string $templateDir)
    {
    }

    /** @param array<string,string> $vars */
    public function render(string $template, array $vars): string
    {
        $path = $this->templateDir . '/' . $template;
        $contents = @file_get_contents($path);
        if ($contents === false) {
            throw new \RuntimeException('Шаблон не найден: ' . $path);
        }

        foreach ($vars as $key => $value) {
            $contents = str_replace('{{' . $key . '}}', $value, $contents);
        }

        if (preg_match('~\{\{[A-Z_]+\}\}~', $contents, $m) === 1) {
            throw new \RuntimeException("Шаблон {$template}: не подставлена переменная {$m[0]}");
        }

        return $contents;
    }
}
