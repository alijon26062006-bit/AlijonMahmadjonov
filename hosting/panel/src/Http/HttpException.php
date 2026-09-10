<?php
declare(strict_types=1);

namespace Hosting\Http;

abstract class HttpException extends \RuntimeException
{
    abstract public function status(): int;
}
