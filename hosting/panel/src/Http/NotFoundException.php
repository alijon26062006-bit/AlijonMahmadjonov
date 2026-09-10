<?php
declare(strict_types=1);

namespace Hosting\Http;

final class NotFoundException extends HttpException
{
    public function __construct(string $message = 'Не найдено')
    {
        parent::__construct($message);
    }

    public function status(): int
    {
        return 404;
    }
}
