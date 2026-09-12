import type { MetadataRoute } from 'next';

// Generated per request rather than baked at build time, so the origin below
// is the one the container was started with — a staging deployment must not
// advertise the production hostname to a crawler.
export const dynamic = 'force-dynamic';

/**
 * The sitemap covers only the pages that are genuinely public. Developer
 * profiles and open projects are public too, but their URLs come from the API
 * and are listed here once the public directory endpoints are wired up —
 * listing a guess would send crawlers to 404s.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const site = process.env.AVERIX_APP_URL ?? 'https://averix.dev';
  return [
    {
      url: site,
      lastModified: new Date(),
      changeFrequency: 'weekly',
      priority: 1,
    },
  ];
}
