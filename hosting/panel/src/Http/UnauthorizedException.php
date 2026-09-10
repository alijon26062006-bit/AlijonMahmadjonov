<?php
declare(strict_types=1);

namespace Hosting\Http;

/** Пользователь не вошёл — front controller отправляет на /login. */
final class UnauthorizedException extends HttpException
{
    public function __construct(string $message = 'Требуется вход')
    {
        parent::__construct($message);
    }

    public function status(): int
    {
        return 401;
    }
}
