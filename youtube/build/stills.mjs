// Рендер нескольких кадров за один проход: node build/stills.mjs <id> <сек> <сек> ...
import {bundle} from '@remotion/bundler';
import {renderStill, selectComposition} from '@remotion/renderer';
import path from 'node:path';

const [id, ...secs] = process.argv.slice(2);
const exe = process.env.REMOTION_CHROME;
const serveUrl = await bundle({entryPoint: path.resolve('src/index.ts')});
const composition = await selectComposition({serveUrl, id, browserExecutable: exe});
for (const s of secs) {
  const frame = Math.round(Number(s) * composition.fps);
  await renderStill({composition, serveUrl, output: `out/s_${s}.png`, frame, browserExecutable: exe});
  console.log('ok', s);
}
