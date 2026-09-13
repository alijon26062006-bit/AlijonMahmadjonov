'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import styles from '../../catalogue.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { BottomNav } from '@/components/nav/BottomNav';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button, ButtonLink } from '@/components/ui/Button';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconLayers } from '@/components/ui/Icon';
import { ApiFailure, get, post } from '@/lib/api';
import { days, plural } from '@/lib/format';
import { SERVICE_STATUS } from '@/lib/labels';
import type { ServiceCard } from '@/lib/types';

export default function MyServicesPage() {
  const [items, setItems] = useState<ServiceCard[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(() => {
    get<ServiceCard[]>('/services/mine/list')
      .then((data) => setItems(data ?? []))
      .catch(() => setItems([]));
  }, []);

  useEffect(() => load(), [load]);

  async function move(id: string, action: 'publish' | 'pause' | 'archive') {
    setBusy(id);
    setError('');
    try {
      await post(`/services/${id}/${action}`);
      load();
    } catch (failure) {
      setError(failure instanceof ApiFailure ? failure.message : 'Не получилось. Попробуйте ещё раз.');
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <TopBar
        back="/feed"
        title="Мои услуги"
        action={
          <ButtonLink href="/services/new" size="sm">
            Создать
          </ButtonLink>
        }
      />
      <main id="main" className={`av-page av-stack ${styles.shell}`}>
        {error ? (
          <p role="alert" style={{ color: 'var(--av-danger)' }}>
            {error}
          </p>
        ) : null}

        {items === null ? (
          <SkeletonList count={3} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={<IconLayers size={20} />}
            title="У вас пока нет услуг"
            description="Услуга — это готовое предложение с фиксированной ценой и сроком. Заказчик покупает её в один шаг, без переписки и торга."
            action={<ButtonLink href="/services/new">Создать услугу</ButtonLink>}
          />
        ) : (
          items.map((item) => (
            <Card key={item.id}>
              <div className="av-row-between">
                <div className="av-grow">
                  <Link href={`/services/${item.id}`} className="av-strong">
                    {item.title}
                  </Link>
                  <p className="av-small av-muted">
                    {item.category.name} · от {item.from_display} · {days(item.delivery_days)}
                  </p>
                  <p className="av-xs av-faint">
                    {plural(item.orders_count, 'заказ', 'заказа', 'заказов')}
                    {item.rating_avg ? ` · ${item.rating_avg.toFixed(1)} ★` : ''}
                  </p>
                </div>
                <Badge tone={item.status === 'active' ? 'success' : item.status === 'draft' ? 'warning' : 'neutral'} size="sm">
                  {SERVICE_STATUS[item.status] ?? item.status}
                </Badge>
              </div>
              <div className="av-row av-wrap">
                <ButtonLink href={`/services/${item.id}/edit`} size="sm" variant="secondary">
                  Редактировать
                </ButtonLink>
                {item.status !== 'active' ? (
                  <Button size="sm" loading={busy === item.id} onClick={() => void move(item.id, 'publish')}>
                    Опубликовать
                  </Button>
                ) : (
                  <Button size="sm" variant="secondary" loading={busy === item.id} onClick={() => void move(item.id, 'pause')}>
                    На паузу
                  </Button>
                )}
                {item.status !== 'archived' ? (
                  <Button size="sm" variant="ghost" loading={busy === item.id} onClick={() => void move(item.id, 'archive')}>
                    В архив
                  </Button>
                ) : null}
              </div>
            </Card>
          ))
        )}
      </main>
      <BottomNav />
    </>
  );
}
