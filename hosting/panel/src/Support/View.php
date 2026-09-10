<?php
declare(strict_types=1);

namespace Hosting\Support;

/** Простой рендер view-файлов (обычный PHP + htmlspecialchars, без движка шаблонов). */
final class View
{
    /** @var (callable():array<string,mixed>)|null */
    private $globalVars;

    /** @param (callable():array<string,mixed>)|null $globalVars например currentUser/flashes/panelName для layout */
    public function __construct(private string $viewsDir, ?callable $globalVars = null)
    {
        $this->globalVars = $globalVars;
    }

    /** @param array<string,mixed> $vars */
    public function render(string $template, array $vars = []): string
    {
        $path = $this->viewsDir . '/' . $template . '.php';
        if (!is_file($path)) {
            throw new \RuntimeException('View не найден: ' . $template);
        }

        $vars['view'] = function (string $template, array $vars = []): string {
            return $this->render($template, $vars);
        };

        return (static function (string $__path, array $__vars) {
            extract($__vars, EXTR_SKIP);
            ob_start();
            require $__path;
            return (string) ob_get_clean();
        })($path, $vars);
    }

    /**
     * Оборачивает содержимое в общий layout (шапка, меню, сообщения) для страниц панели.
     * currentUser/flashes/panelName добавляются автоматически (см. $globalVars в конструкторе),
     * явные $vars того же имени имеют приоритет.
     */
    public function page(string $template, array $vars = []): string
    {
        $globals = $this->globalVars !== null ? ($this->globalVars)() : [];
        $vars = $vars + $globals;
        $content = $this->render($template, $vars);
        return $this->render('layout/base', $vars + ['content' => $content]);
    }
}
