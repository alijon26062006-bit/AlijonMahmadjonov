<?php
declare(strict_types=1);

namespace Hosting\Http;

/** Ресурс существует, но не принадлежит текущему пользователю (IDOR-защита). */
final class ForbiddenException extends HttpException
{
    public function __construct(string $message = 'Доступ запрещён')
    {
        parent::__construct($message);
    }

    public function status(): int
    {
        return 403;
    }
}
