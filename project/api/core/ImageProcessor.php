<?php

declare(strict_types=1);

namespace Core;

use GdImage;

/**
 * Image pipeline built on GD. From a single uploaded poster it produces an
 * optimised set of WebP renditions tailored to the Mini App design:
 *
 *   - poster      2:3  vertical card         (500 x 750)
 *   - thumbnail   2:3  small list image      (200 x 300)
 *   - banner     16:9  hero / wide banner    (1280 x 720)
 *   - background 16:9  detail-page backdrop  (1920 x 1080)
 *
 * Behaviour:
 *   - detects orientation;
 *   - Smart Crop that respects an optional focal region (face / title) so those
 *     are never cut off;
 *   - when the source is vertical and a wide banner is needed, composes a
 *     cinematic banner (blurred, darkened cover + the full poster on top) so no
 *     face or title is ever cropped;
 *   - encodes to WebP with quality optimisation, falling back to JPEG when the
 *     WebP encoder is unavailable.
 */
final class ImageProcessor
{
    private const MAX_SOURCE = 2200;   // downscale huge uploads first (memory safety)
    private const QUALITY    = 82;

    private const SIZES = [
        'poster'     => [500, 750],
        'thumbnail'  => [200, 300],
        'banner'     => [1280, 720],
        'background' => [1920, 1080],
    ];

    private string $uploadsDir;
    private bool $webp;

    public function __construct(string $uploadsDir)
    {
        $this->uploadsDir = rtrim($uploadsDir, '/');
        $this->webp = function_exists('imagewebp');
    }

    public function available(): bool
    {
        return extension_loaded('gd');
    }

    /**
     * Process a source image into all renditions.
     *
     * @param array{x:float,y:float,w:float,h:float}|null $focal Normalised focus box.
     * @return array{orientation:string,width:int,height:int,poster:?string,thumbnail:?string,banner:?string,background:?string}
     */
    public function process(string $sourcePath, ?array $focal = null): array
    {
        $src = $this->load($sourcePath);
        if (!$src instanceof GdImage) {
            return [
                'orientation' => 'unknown', 'width' => 0, 'height' => 0,
                'poster' => null, 'thumbnail' => null, 'banner' => null, 'background' => null,
            ];
        }

        $src = $this->limitSize($src);
        $w = imagesx($src);
        $h = imagesy($src);
        $orientation = $this->orientation($w, $h);
        $portrait = $orientation !== 'landscape';

        $ext = $this->webp ? 'webp' : 'jpg';
        $stub = 'ai_' . bin2hex(random_bytes(6));

        // Poster & thumbnail: always a 2:3 crop, biased to the top to keep faces.
        $posterImg = $this->coverCrop($src, self::SIZES['poster'][0], self::SIZES['poster'][1], $focal, true);
        $thumbImg  = $this->resize($posterImg, self::SIZES['thumbnail'][0], self::SIZES['thumbnail'][1]);

        // Banner & background: crop when source is wide, compose when it is tall.
        if ($portrait) {
            $bannerImg = $this->composeWide($src, self::SIZES['banner'][0], self::SIZES['banner'][1]);
            $backImg   = $this->composeWide($src, self::SIZES['background'][0], self::SIZES['background'][1]);
        } else {
            $bannerImg = $this->coverCrop($src, self::SIZES['banner'][0], self::SIZES['banner'][1], $focal, false);
            $backImg   = $this->coverCrop($src, self::SIZES['background'][0], self::SIZES['background'][1], $focal, false);
        }

        $result = [
            'orientation' => $orientation,
            'width'       => $w,
            'height'      => $h,
            'poster'      => $this->save($posterImg, 'posters',     $stub . '_poster.' . $ext),
            'thumbnail'   => $this->save($thumbImg,  'thumbnails',  $stub . '_thumb.'  . $ext),
            'banner'      => $this->save($bannerImg, 'banners',     $stub . '_banner.' . $ext),
            'background'  => $this->save($backImg,   'backgrounds', $stub . '_bg.'     . $ext),
        ];

        foreach ([$src, $posterImg, $thumbImg, $bannerImg, $backImg] as $img) {
            if ($img instanceof GdImage) {
                imagedestroy($img);
            }
        }
        return $result;
    }

    // ---- Geometry -------------------------------------------------------

    private function orientation(int $w, int $h): string
    {
        if ($w >= $h * 1.15) {
            return 'landscape';
        }
        if ($h > $w * 1.05) {
            return 'portrait';
        }
        return 'square';
    }

    /**
     * Scale to cover the target box, then crop. When a focal box is supplied the
     * crop is centred on it (so faces / titles stay in frame); otherwise the crop
     * is centred, optionally biased toward the top for posters.
     */
    private function coverCrop(GdImage $src, int $tw, int $th, ?array $focal, bool $biasTop): GdImage
    {
        $sw = imagesx($src);
        $sh = imagesy($src);
        $scale = max($tw / $sw, $th / $sh);
        $rw = (int) ceil($sw * $scale);
        $rh = (int) ceil($sh * $scale);

        $scaled = $this->resize($src, $rw, $rh);

        // Horizontal / vertical crop offset within the scaled image.
        $maxX = $rw - $tw;
        $maxY = $rh - $th;

        if ($focal) {
            $fx = ($focal['x'] + $focal['w'] / 2) * $rw;   // focal centre in scaled px
            $fy = ($focal['y'] + $focal['h'] / 2) * $rh;
            $x = (int) round($fx - $tw / 2);
            $y = (int) round($fy - $th / 2);
        } else {
            $x = (int) round($maxX / 2);
            $y = $biasTop ? (int) round($maxY * 0.32) : (int) round($maxY / 2);
        }

        $x = max(0, min($maxX, $x));
        $y = max(0, min($maxY, $y));

        $out = $this->canvas($tw, $th);
        imagecopy($out, $scaled, 0, 0, $x, $y, $tw, $th);
        imagedestroy($scaled);
        return $out;
    }

    /**
     * Compose a wide banner from a tall poster: a blurred, darkened cover fills
     * the frame, the full (un-cropped) poster sits centred on top, and a gradient
     * grounds the composition. No face or title is ever cropped.
     */
    private function composeWide(GdImage $src, int $tw, int $th): GdImage
    {
        // Background: cover-crop then blur + darken.
        $bg = $this->coverCrop($src, $tw, $th, null, false);
        $this->blur($bg);
        $this->darken($bg, 0.45);

        // Foreground: contain the poster by height, centred.
        $sw = imagesx($src);
        $sh = imagesy($src);
        $fgH = (int) round($th * 0.92);
        $fgW = (int) round($sw * ($fgH / $sh));
        $fg  = $this->resize($src, $fgW, $fgH);
        $dx  = (int) round(($tw - $fgW) / 2);
        $dy  = (int) round(($th - $fgH) / 2);
        imagecopy($bg, $fg, $dx, $dy, 0, 0, $fgW, $fgH);
        imagedestroy($fg);

        $this->bottomGradient($bg);
        return $bg;
    }

    // ---- GD helpers -----------------------------------------------------

    private function load(string $path): ?GdImage
    {
        if (!is_file($path)) {
            return null;
        }
        $info = @getimagesize($path);
        $mime = $info['mime'] ?? '';
        $img = match ($mime) {
            'image/jpeg' => @imagecreatefromjpeg($path),
            'image/png'  => @imagecreatefrompng($path),
            'image/webp' => $this->webp ? @imagecreatefromwebp($path) : null,
            'image/gif'  => @imagecreatefromgif($path),
            default      => null,
        };
        return $img instanceof GdImage ? $img : null;
    }

    private function limitSize(GdImage $src): GdImage
    {
        $w = imagesx($src);
        $h = imagesy($src);
        $longest = max($w, $h);
        if ($longest <= self::MAX_SOURCE) {
            return $src;
        }
        $scale = self::MAX_SOURCE / $longest;
        $small = $this->resize($src, (int) round($w * $scale), (int) round($h * $scale));
        imagedestroy($src);
        return $small;
    }

    private function resize(GdImage $src, int $w, int $h): GdImage
    {
        $dst = $this->canvas($w, $h);
        imagecopyresampled($dst, $src, 0, 0, 0, 0, $w, $h, imagesx($src), imagesy($src));
        return $dst;
    }

    private function canvas(int $w, int $h): GdImage
    {
        $img = imagecreatetruecolor($w, $h);
        imagealphablending($img, true);
        imagefilledrectangle($img, 0, 0, $w, $h, imagecolorallocate($img, 12, 12, 16));
        return $img;
    }

    private function blur(GdImage $img): void
    {
        // Fast blur: shrink then grow, then a few Gaussian passes.
        $w = imagesx($img);
        $h = imagesy($img);
        $tiny = $this->resize($img, max(1, (int) ($w / 12)), max(1, (int) ($h / 12)));
        $back = $this->resize($tiny, $w, $h);
        imagedestroy($tiny);
        for ($i = 0; $i < 3; $i++) {
            @imagefilter($back, IMG_FILTER_GAUSSIAN_BLUR);
        }
        imagecopy($img, $back, 0, 0, 0, 0, $w, $h);
        imagedestroy($back);
    }

    private function darken(GdImage $img, float $amount): void
    {
        $amount = max(0.0, min(1.0, $amount));
        @imagefilter($img, IMG_FILTER_BRIGHTNESS, (int) round(-255 * $amount));
    }

    private function bottomGradient(GdImage $img): void
    {
        $w = imagesx($img);
        $h = imagesy($img);
        $start = (int) ($h * 0.45);
        imagealphablending($img, true);
        for ($y = $start; $y < $h; $y++) {
            $t = ($y - $start) / max(1, $h - $start);
            $alpha = (int) round(127 * (1 - $t)); // 127 transparent .. 0 opaque
            $col = imagecolorallocatealpha($img, 8, 8, 11, $alpha);
            imageline($img, 0, $y, $w, $y, $col);
        }
    }

    /** Encode to WebP (or JPEG fallback) and return the uploads-relative path. */
    private function save(GdImage $img, string $subdir, string $name): ?string
    {
        $dir = $this->uploadsDir . '/' . $subdir;
        if (!is_dir($dir)) {
            @mkdir($dir, 0775, true);
        }
        $rel = $subdir . '/' . $name;
        $abs = $this->uploadsDir . '/' . $rel;

        $ok = $this->webp
            ? @imagewebp($img, $abs, self::QUALITY)
            : @imagejpeg($img, $abs, self::QUALITY);

        return $ok ? $rel : null;
    }
}
