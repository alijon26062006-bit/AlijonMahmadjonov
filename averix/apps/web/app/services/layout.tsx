import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Готовые услуги',
  description:
    'Услуги с фиксированной ценой и сроком: логотип, лендинг, тексты, монтаж ролика, ' +
    'настройка рекламы. Выбираете пакет, описываете задачу — работа начинается без переговоров.',
};

export default function ServicesLayout({ children }: { children: React.ReactNode }) {
  return children;
}
