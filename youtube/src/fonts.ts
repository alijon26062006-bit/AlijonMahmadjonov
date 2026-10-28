import {loadFont} from '@remotion/fonts';
import {staticFile} from 'remotion';

const LATIN =
  'U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD';
const CYRILLIC = 'U+0301,U+0400-045F,U+0490-0491,U+04B0-04B1,U+2116';

const families: [string, string, string[]][] = [
  ['Unbounded', 'unbounded', ['700', '800']],
  ['Manrope', 'manrope', ['500', '600', '700', '800']],
  ['JetBrains Mono', 'jetbrains-mono', ['400', '600', '700']],
];

for (const [family, file, weights] of families) {
  for (const weight of weights) {
    for (const [subset, unicodeRange] of [
      ['latin', LATIN],
      ['cyrillic', CYRILLIC],
    ]) {
      loadFont({
        family,
        url: staticFile(`fonts/${file}-${subset}-${weight}-normal.woff2`),
        weight,
        unicodeRange,
      });
    }
  }
}
