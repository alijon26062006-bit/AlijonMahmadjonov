import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Открытые заказы',
  description:
    'Все опубликованные заказы AVERIX: дизайн, тексты, разработка, реклама, видео, ' +
    'бухгалтерия. Смотреть можно без регистрации — она нужна только чтобы откликнуться.',
};

export default function ProjectsLayout({ children }: { children: React.ReactNode }) {
  return children;
}
