'use client';

import { TopBar } from '@/components/nav/TopBar';
import { BottomNav } from '@/components/nav/BottomNav';
import { ServiceForm } from '@/components/domain/ServiceForm';

export default function NewServicePage() {
  return (
    <>
      <TopBar back="/services/mine" title="Новая услуга" />
      <main id="main" className="av-page av-stack" style={{ maxWidth: 720, margin: '0 auto' }}>
        <p className="av-muted">
          Услуга — это готовое предложение: заказчик видит цену и срок и покупает без переговоров.
          Опубликовать можно после того, как заполнены пакеты и навыки.
        </p>
        <ServiceForm />
      </main>
      <BottomNav />
    </>
  );
}
