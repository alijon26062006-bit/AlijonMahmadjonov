'use client';

import { useEffect, useState } from 'react';
import { TopBar } from '@/components/nav/TopBar';
import { BottomNav } from '@/components/nav/BottomNav';
import { Card } from '@/components/ui/Card';
import { ButtonLink } from '@/components/ui/Button';
import { useRoleGuard } from '@/lib/session';
import { ServiceForm } from '@/components/domain/ServiceForm';
import { get } from '@/lib/api';
import type { OwnProfile } from '@/lib/types';

export default function NewServicePage() {
  useRoleGuard('developer');
  const [profile, setProfile] = useState<OwnProfile | null>(null);

  useEffect(() => {
    get<OwnProfile>('/developers/me')
      .then(setProfile)
      .catch(() => undefined);
  }, []);

  return (
    <>
      <TopBar back="/services/mine" title="Новая услуга" />
      <main id="main" className="av-page av-stack" style={{ maxWidth: 720, margin: '0 auto' }}>
        <p className="av-muted">
          Услуга — это готовое предложение: заказчик видит цену и срок и покупает без переговоров.
          Опубликовать можно после того, как заполнены пакеты и навыки.
        </p>

        {/* Сказать об этом до формы, а не после публикации в пустоту. */}
        {profile && !profile.is_searchable ? (
          <Card>
            <div className="av-stack-sm">
              <p className="av-strong">Сначала анкета</p>
              <p className="av-small av-muted">
                Услугу можно создать и сейчас, но в каталоге она появится только когда будет
                опубликована ваша анкета: заказчик покупает у человека, а не у карточки.
              </p>
              <div>
                <ButtonLink href="/onboarding" size="sm" variant="secondary">
                  Заполнить анкету
                </ButtonLink>
              </div>
            </div>
          </Card>
        ) : null}

        <ServiceForm />
      </main>
      <BottomNav />
    </>
  );
}
