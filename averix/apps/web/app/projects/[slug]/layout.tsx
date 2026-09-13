import type { Metadata } from 'next';

type Params = { slug: string };

/**
 * Заголовок ссылки на заказ.
 *
 * Заказ — публичная страница, и ссылку на неё кидают в чат: она должна
 * разворачиваться в название задачи и бюджет, а не в общий слоган площадки.
 * Если API не отвечает, остаётся честное «Заказ».
 */
export async function generateMetadata({ params }: { params: Promise<Params> }): Promise<Metadata> {
  const { slug } = await params;
  const api = process.env.AVERIX_API_URL ?? 'http://api:8080';
  try {
    const response = await fetch(`${api}/api/v1/projects/${encodeURIComponent(slug)}`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) throw new Error('unavailable');
    const project = (await response.json()).data as {
      title?: string;
      summary?: string;
      description?: string;
      category?: { name?: string };
      budget?: { display?: string };
    };
    const budget = project.budget?.display ? ` · ${project.budget.display}` : '';
    return {
      title: `${project.title ?? 'Заказ'}${project.category?.name ? ` — ${project.category.name}` : ''}`,
      description:
        ((project.summary || project.description) ?? '').slice(0, 200) ||
        `Открытый заказ на AVERIX${budget}.`,
    };
  } catch {
    return { title: 'Заказ' };
  }
}

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  return children;
}
