'use client';

import { useEffect, useState } from 'react';
import styles from '../../catalogue.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { BottomNav } from '@/components/nav/BottomNav';
import { FreelancerCard } from '@/components/domain/FreelancerCard';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ButtonLink } from '@/components/ui/Button';
import { IconUser } from '@/components/ui/Icon';
import { get } from '@/lib/api';
import type { FreelancerCard as FreelancerCardType } from '@/lib/types';

export default function SavedFreelancersPage() {
  const [cards, setCards] = useState<FreelancerCardType[] | null>(null);

  useEffect(() => {
    get<FreelancerCardType[]>('/me/saved-freelancers')
      .then((data) => setCards(data ?? []))
      .catch(() => setCards([]));
  }, []);

  return (
    <>
      <TopBar back="/freelancers" title="Избранные исполнители" />
      <main id="main" className={`av-page ${styles.shell}`}>
        {cards === null ? (
          <SkeletonList count={3} />
        ) : cards.length === 0 ? (
          <EmptyState
            icon={<IconUser size={20} />}
            title="Список пуст"
            description="Сохраняйте подходящих исполнителей из каталога — они будут ждать здесь, когда появится задача."
            action={<ButtonLink href="/freelancers">Открыть каталог</ButtonLink>}
          />
        ) : (
          <div className={styles.list}>
            {cards.map((card) => (
              <FreelancerCard key={card.user_id} card={card} />
            ))}
          </div>
        )}
      </main>
      <BottomNav />
    </>
  );
}
