// Renders the brand SVGs into Android resources with headless Chromium.
//
//   node tool/brand/render_icons.js     (run from the project root)
//
// Needs Playwright with Chromium (`npm i -g playwright && npx playwright
// install chromium`).
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..', '..');
const res = path.join(root, 'android', 'app', 'src', 'main', 'res');
const densities = { mdpi: 1, hdpi: 1.5, xhdpi: 2, xxhdpi: 3, xxxhdpi: 4 };

const jobs = [];
for (const [d, k] of Object.entries(densities)) {
  jobs.push({ svg: 'icon.svg', size: 48 * k, out: `mipmap-${d}/ic_launcher.png` });
  jobs.push({ svg: 'adaptive_foreground.svg', size: 108 * k, out: `drawable-${d}/ic_launcher_foreground.png` });
  jobs.push({ svg: 'splash_icon.svg', size: 288 * k, out: `drawable-${d}/splash_icon.png` });
}
jobs.push({ svg: 'icon.svg', size: 512, out: path.join('..', '..', '..', '..', '..', 'tool', 'brand', 'play_store_icon_512.png') });

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  for (const job of jobs) {
    const svg = fs.readFileSync(path.join(__dirname, job.svg), 'utf8')
      .replace(/width="\d+" height="\d+"/, `width="${job.size}" height="${job.size}"`);
    await page.setViewportSize({ width: job.size, height: job.size });
    await page.setContent(
      `<html><body style="margin:0;background:transparent">${svg}</body></html>`,
    );
    const out = path.join(res, job.out);
    fs.mkdirSync(path.dirname(out), { recursive: true });
    await page.locator('svg').screenshot({ path: out, omitBackground: true });
    console.log('wrote', path.relative(root, out));
  }
  await browser.close();
})();
