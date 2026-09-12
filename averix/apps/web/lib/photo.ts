import type { PhotoSet } from './types';

/**
 * Picks an avatar URL out of the photo set.
 *
 * WebP first, JPEG second, and the smallest size that is at least what the
 * layout asked for — so a 40px avatar in a list does not download the 512px
 * portrait twenty times.
 */
export function avatarURL(photo: PhotoSet | undefined | null, wanted = 128): string | undefined {
  if (!photo?.sources) return undefined;
  for (const format of ['webp', 'jpeg']) {
    const sizes = photo.sources[format];
    if (!sizes) continue;
    const widths = Object.keys(sizes)
      .map(Number)
      .filter((value) => Number.isFinite(value))
      .sort((a, b) => a - b);
    const match = widths.find((width) => width >= wanted) ?? widths[widths.length - 1];
    if (match !== undefined) return sizes[String(match)];
  }
  return undefined;
}
