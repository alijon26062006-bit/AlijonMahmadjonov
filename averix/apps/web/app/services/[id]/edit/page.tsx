'use client';

import { use, useEffect, useState } from 'react';
import { TopBar } from '@/components/nav/TopBar';
import { BottomNav } from '@/components/nav/BottomNav';
import { ServiceForm } from '@/components/domain/ServiceForm';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ButtonLink } from '@/components/ui/Button';
import { IconAlert } from '@/components/ui/Icon';
import { get } from '@/lib/api';
import type { Service } from '@/lib/types';

export default function EditServicePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [service, setService] = useState<Service | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    get<Service>(`/services/${id}`)
      .then(setService)
      .catch(() => setFailed(true));
  }, [id]);

  return (
    <>
      <TopBar back={`/services/${id}`} title="Правка услуги" />
      <main id="main" className="av-page av-stack" style={{ maxWidth: 720, margin: '0 auto' }}>
        {failed ? (
          <EmptyState
            tone="error"
            icon={<IconAlert size={20} />}
            title="Услуга недоступна"
            description="Её либо нет, либо она не ваша."
            action={<ButtonLink href="/services/mine">К моим услугам</ButtonLink>}
          />
        ) : !service ? (
          <Skeleton height={320} />
        ) : (
          <ServiceForm existing={service} />
        )}
      </main>
      <BottomNav />
    </>
  );
}
