<?php

declare(strict_types=1);

/**
 * Minifies the CSS and JS assets for production.
 *
 * Run:  php assets/build.php
 *
 * Produces assets/css/app.min.css and assets/js/app.min.js. The Mini App uses
 * the minified files automatically when they exist (see miniapp/index.php).
 * JS minification is intentionally conservative — it strips comments, blank
 * lines and indentation while preserving line breaks, so template literals and
 * automatic-semicolon-insertion keep working.
 */

$base = __DIR__;

$minifyCss = static function (string $css): string {
    $css = preg_replace('#/\*.*?\*/#s', '', $css) ?? $css;      // block comments
    $css = preg_replace('/\s+/', ' ', $css) ?? $css;            // collapse whitespace
    $css = preg_replace('/\s*([{}:;,>~+])\s*/', '$1', $css) ?? $css;
    $css = str_replace([';}', ' !important'], ['}', '!important'], $css);
    return trim($css);
};

$minifyJs = static function (string $js): string {
    $lines = preg_split('/\r?\n/', $js) ?: [];
    $out = [];
    foreach ($lines as $line) {
        $trimmed = trim($line);
        if ($trimmed === '') {
            continue;                       // drop blank lines
        }
        if (str_starts_with($trimmed, '//')) {
            continue;                       // drop full-line comments
        }
        $out[] = $trimmed;                  // drop indentation (safe: kept newlines)
    }
    return implode("\n", $out);
};

$jobs = [
    ['css/app.css', 'css/app.min.css', $minifyCss],
    ['js/app.js',   'js/app.min.js',   $minifyJs],
];

foreach ($jobs as [$in, $out, $fn]) {
    $src = @file_get_contents($base . '/' . $in);
    if ($src === false) {
        fwrite(STDERR, "skip: {$in} not found\n");
        continue;
    }
    $min = $fn($src);
    file_put_contents($base . '/' . $out, $min);
    $before = strlen($src);
    $after  = strlen($min);
    $pct = $before ? round(100 - $after / $before * 100) : 0;
    printf("%-16s %6d -> %6d bytes (-%d%%)\n", $out, $before, $after, $pct);
}
