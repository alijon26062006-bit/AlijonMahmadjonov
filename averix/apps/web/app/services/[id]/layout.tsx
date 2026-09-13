import type { Metadata } from 'next';

type Params = { id: string };

/** A shared service link should say what is on offer and from whom. */
export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { id } = await params;
  const api = process.env.AVERIX_API_URL ?? 'http://api:8080';
  try {
    const response = await fetch(`${api}/api/v1/services/${encodeURIComponent(id)}`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) throw new Error('unavailable');
    const service = (await response.json()).data as {
      title?: string;
      summary?: string;
      from_display?: string;
      seller?: { full_name?: string };
    };
    const price = service.from_display ? ` — от ${service.from_display}` : '';
    return {
      title: `${service.title ?? 'Услуга'}${price}`,
      description:
        service.summary ??
        `Готовая услуга на AVERIX${service.seller?.full_name ? ` от ${service.seller.full_name}` : ''}.`,
    };
  } catch {
    return { title: 'Услуга' };
  }
}

export default function ServiceLayout({ children }: { children: React.ReactNode }) {
  return children;
}
