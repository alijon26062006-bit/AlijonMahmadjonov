<?php
declare(strict_types=1);

namespace Hosting\Support;

/** Запуск внешних команд с захватом вывода (без shell-интерполяции аргументов). */
final class Shell
{
    /** @return array{code:int,out:string,err:string} */
    public static function run(string $command, int $timeoutSeconds = 60): array
    {
        $descriptors = [1 => ['pipe', 'w'], 2 => ['pipe', 'w']];
        $process = @proc_open($command, $descriptors, $pipes);

        if (!is_resource($process)) {
            return ['code' => 127, 'out' => '', 'err' => 'Не удалось запустить: ' . $command];
        }

        stream_set_blocking($pipes[1], false);
        stream_set_blocking($pipes[2], false);

        $out = '';
        $err = '';
        $deadline = microtime(true) + $timeoutSeconds;

        while (true) {
            $out .= (string) stream_get_contents($pipes[1]);
            $err .= (string) stream_get_contents($pipes[2]);

            $status = proc_get_status($process);
            if (!$status['running']) {
                break;
            }
            if (microtime(true) > $deadline) {
                proc_terminate($process, 9);
                $err .= "\nКоманда превысила лимит времени";
                break;
            }
            usleep(20_000);
        }

        $out .= (string) stream_get_contents($pipes[1]);
        $err .= (string) stream_get_contents($pipes[2]);

        fclose($pipes[1]);
        fclose($pipes[2]);
        $code = proc_close($process);

        return ['code' => $code, 'out' => trim($out), 'err' => trim($err)];
    }
}
