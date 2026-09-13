import type { MetadataRoute } from 'next';

// Generated per request rather than baked at build time, so the origin below
// is the one the container was started with — a staging deployment must not
// advertise the production hostname to a crawler.
export const dynamic = 'force-dynamic';
export const revalidate = 0;

type Freelancer = { username: string; last_seen_at?: string };
type Service = { id: string; created_at?: string };

/**
 * The sitemap lists what is genuinely public: the two catalogues, and the
 * profiles and services inside them.
 *
 * The entries are read from the API rather than guessed. If the API is not
 * answering, the catalogues are still listed and the individual pages are
 * simply left out — a sitemap that is short is useful; one that sends
 * crawlers to pages that do not exist is worse than none.
 */
export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const site = (process.env.AVERIX_APP_URL ?? 'https://averix.dev').replace(/\/$/, '');
  const api = process.env.AVERIX_API_URL ?? 'http://api:8080';
  const now = new Date();

  const entries: MetadataRoute.Sitemap = [
    { url: site, lastModified: now, changeFrequency: 'daily', priority: 1 },
    { url: `${site}/freelancers`, lastModified: now, changeFrequency: 'daily', priority: 0.9 },
    { url: `${site}/services`, lastModified: now, changeFrequency: 'daily', priority: 0.9 },
  ];

  const [freelancers, services] = await Promise.all([
    read<Freelancer[]>(`${api}/api/v1/freelancers?limit=200&sort=newest`),
    read<Service[]>(`${api}/api/v1/services?limit=200&sort=newest`),
  ]);

  for (const person of freelancers ?? []) {
    entries.push({
      url: `${site}/developers/${encodeURIComponent(person.username)}`,
      lastModified: person.last_seen_at ? new Date(person.last_seen_at) : now,
      changeFrequency: 'weekly',
      priority: 0.7,
    });
  }
  for (const service of services ?? []) {
    entries.push({
      url: `${site}/services/${service.id}`,
      lastModified: service.created_at ? new Date(service.created_at) : now,
      changeFrequency: 'weekly',
      priority: 0.6,
    });
  }

  return entries;
}

async function read<T>(url: string): Promise<T | null> {
  try {
    const response = await fetch(url, { cache: 'no-store', signal: AbortSignal.timeout(4000) });
    if (!response.ok) return null;
    return ((await response.json()) as { data: T }).data;
  } catch {
    // A crawler asking for the sitemap must never be the thing that surfaces
    // an API outage as a 500.
    return null;
  }
}
