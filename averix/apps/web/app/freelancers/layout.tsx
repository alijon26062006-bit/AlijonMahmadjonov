import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Исполнители',
  description:
    'Каталог исполнителей AVERIX: дизайнеры, авторы, разработчики, маркетологи, монтажёры, ' +
    'бухгалтеры и репетиторы. Рейтинг и завершённые сделки видно до первого сообщения.',
};

export default function FreelancersLayout({ children }: { children: React.ReactNode }) {
  return children;
}
