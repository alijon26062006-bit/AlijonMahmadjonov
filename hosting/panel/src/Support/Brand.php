<?php
declare(strict_types=1);

namespace Hosting\Support;

/**
 * Название хостинга и его разбивка на две части для двухцветного логотипа
 * (первая часть тёмная, вторая — синяя).
 */
final class Brand
{
    /**
     * Делит название на «тёмную» и «цветную» части.
     *
     * Логика по убыванию надёжности:
     *   1. Заглавная буква внутри слова — DiyorHost → Diyor + Host.
     *   2. Известное окончание — diyorhost → diyor + host (домены пишут строчными).
     *   3. Ничего не нашли — всё слово тёмное, без искусственного разреза.
     *
     * @return array{0:string,1:string} [голова, хвост]
     */
    public static function split(string $name): array
    {
        $name = trim($name);
        if ($name === '') {
            return ['', ''];
        }

        // Заглавная внутри слова: делим по последней из них.
        if (preg_match('~^(.*\p{L})(\p{Lu}\p{L}*)$~u', $name, $m) === 1) {
            return [$m[1], $m[2]];
        }

        foreach (['host', 'хост', 'cloud', 'server'] as $suffix) {
            $len = mb_strlen($suffix);
            if (mb_strlen($name) > $len && mb_strtolower(mb_substr($name, -$len)) === $suffix) {
                return [mb_substr($name, 0, -$len), mb_substr($name, -$len)];
            }
        }

        return [$name, ''];
    }

    /**
     * Название по домену: diyorhost.com → DiyorHost.
     *
     * Домен — то единственное, что владелец хостинга точно уже выбрал и купил,
     * поэтому имя панели берётся из него, а не остаётся значением из примера.
     */
    public static function fromDomain(string $domain): string
    {
        // mb_strtolower, а не strtolower: обычный не знает про кириллицу и
        // оставляет «ЭлитХост» как есть. Класс символов — по Unicode-свойствам,
        // иначе фильтр выбрасывает все заглавные не-латинские буквы.
        $label = explode('.', trim($domain))[0] ?? '';
        $label = mb_strtolower($label);
        $label = preg_replace('~[^\p{L}\p{N}-]~u', '', $label) ?? '';
        if ($label === '') {
            return '';
        }

        [$head, $tail] = self::split($label);

        return $tail === ''
            ? self::ucfirst($head)
            : self::ucfirst($head) . self::ucfirst($tail);
    }

    private static function ucfirst(string $value): string
    {
        return $value === '' ? '' : mb_strtoupper(mb_substr($value, 0, 1)) . mb_substr($value, 1);
    }
}
