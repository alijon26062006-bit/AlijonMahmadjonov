<?php
declare(strict_types=1);

namespace Core;

/**
 * Tiny routing table mapping "METHOD /path" to a controller callback.
 */
final class Router
{
    /** @var array<string, callable> */
    private array $routes = [];

    public function add(string $method, string $path, callable $handler): void
    {
        $this->routes[strtoupper($method) . ' ' . $path] = $handler;
    }

    public function get(string $path, callable $handler): void
    {
        $this->add('GET', $path, $handler);
    }

    public function post(string $path, callable $handler): void
    {
        $this->add('POST', $path, $handler);
    }

    public function dispatch(string $method, string $path): void
    {
        $path = '/' . trim($path, '/');
        $key  = strtoupper($method) . ' ' . $path;

        if (isset($this->routes[$key])) {
            ($this->routes[$key])();
            return;
        }

        Response::error('Not found: ' . $method . ' ' . $path, 404);
    }
}
