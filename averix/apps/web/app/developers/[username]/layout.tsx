import type { Metadata } from 'next';

type Params = { username: string };

/**
 * The title of a shared profile link.
 *
 * Read from the API at request time: a link to a person should carry their
 * name and what they do, not the product's generic tagline. When the API is
 * not answering, the username alone is still true.
 */
export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { username } = await params;
  const api = process.env.AVERIX_API_URL ?? 'http://api:8080';
  try {
    const response = await fetch(`${api}/api/v1/developers/${encodeURIComponent(username)}`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) throw new Error('unavailable');
    const profile = (await response.json()).data as {
      full_name?: string;
      professional_title?: string;
      primary_specialisation?: { name?: string };
      bio?: string;
    };
    const role = profile.professional_title || profile.primary_specialisation?.name || 'Исполнитель';
    return {
      title: `${profile.full_name ?? username} — ${role}`,
      description: (profile.bio ?? '').slice(0, 200) || `Профиль исполнителя на AVERIX: ${role}.`,
    };
  } catch {
    return { title: `@${username}` };
  }
}

export default function DeveloperLayout({ children }: { children: React.ReactNode }) {
  return children;
}
