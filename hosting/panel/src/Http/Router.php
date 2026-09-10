<?php
declare(strict_types=1);

namespace Hosting\Http;

/** Маршрутизатор: точные пути и один вид параметра — {id}. */
final class Router
{
    /** @var list<array{method:string,pattern:string,regex:string,handler:callable}> */
    private array $routes = [];

    public function get(string $pattern, callable $handler): void
    {
        $this->add('GET', $pattern, $handler);
    }

    public function post(string $pattern, callable $handler): void
    {
        $this->add('POST', $pattern, $handler);
    }

    public function add(string $method, string $pattern, callable $handler): void
    {
        // Части между {параметрами} экранируем, сами параметры — числовые группы.
        $literals = preg_split('~\{[a-z_]+\}~', $pattern) ?: [$pattern];
        $quoted = array_map(static fn (string $part): string => preg_quote($part, '~'), $literals);

        $this->routes[] = [
            'method'  => $method,
            'pattern' => $pattern,
            'regex'   => '~^' . implode('([0-9]+)', $quoted) . '$~',
            'handler' => $handler,
        ];
    }

    /**
     * @return array{handler:callable,params:list<string>}|null
     */
    public function match(string $method, string $path): ?array
    {
        foreach ($this->routes as $route) {
            if ($route['method'] !== $method) {
                continue;
            }
            if (preg_match($route['regex'], $path, $matches) === 1) {
                array_shift($matches);
                return ['handler' => $route['handler'], 'params' => $matches];
            }
        }

        return null;
    }

    public function hasPath(string $path): bool
    {
        foreach ($this->routes as $route) {
            if (preg_match($route['regex'], $path) === 1) {
                return true;
            }
        }
        return false;
    }
}
