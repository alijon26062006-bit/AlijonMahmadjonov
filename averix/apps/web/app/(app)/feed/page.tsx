'use client';

import { useCallback, useEffect, useState } from 'react';
import styles from './feed.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Tabs } from '@/components/ui/Tabs';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { ProjectCard } from '@/components/domain/ProjectCard';
import { Button } from '@/components/ui/Button';
import { IconCompass, IconAlert } from '@/components/ui/Icon';
import { get, list } from '@/lib/api';
import { plural } from '@/lib/format';
import { useRoleGuard } from '@/lib/session';
import type { FeedCard } from '@/lib/types';

// The tabs are per developer: the category ones come from what this person
// actually works in, so a Telegram developer gets a Telegram tab and an iOS
// developer does not.
const FALLBACK_TABS = [
  { key: 'for_you', label: 'Для вас' },
  { key: 'recent', label: 'Новые' },
  { key: 'saved', label: 'Сохранённые' },
];

export default function FeedPage() {
  const isDeveloper = useRoleGuard('developer');
  const [tabs, setTabs] = useState(FALLBACK_TABS);
  const [tab, setTab] = useState('for_you');
  const [cards, setCards] = useState<FeedCard[] | null>(null);
  const [meta, setMeta] = useState<Record<string, unknown>>({});
  const [failed, setFailed] = useState(false);

  const load = useCallback(async (key: string) => {
    if (!isDeveloper) return;
    setCards(null);
    setFailed(false);
    try {
      const response = await list<FeedCard[]>(`/projects?tab=${encodeURIComponent(key)}`);
      setCards(response.data ?? []);
      setMeta(response.meta ?? {});
    } catch {
      setFailed(true);
    }
  }, [isDeveloper]);

  useEffect(() => {
    void load(tab);
  }, [tab, load]);

  useEffect(() => {
    let cancelled = false;
    get<{ key: string; label: string; count?: number }[]>('/projects/feed/tabs')
      .then((data) => {
        if (!cancelled && data?.length) setTabs(data);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <TopBar />
      <div className="av-page">
        <header className={styles.intro}>
          <h1 className={styles.heading}>Найти заказ</h1>
          <p className={styles.subheading}>
            Заказы по вашему профилю, а не всё подряд.
          </p>
        </header>

        <div className={styles.tabs}>
          <Tabs items={tabs} active={tab} onChange={setTab} ariaLabel="Разделы ленты" />
        </div>

        {typeof meta.count === 'number' && cards?.length ? (
          <p className={styles.count}>
            {plural(meta.count, 'заказ', 'заказа', 'заказов')} по вашему профилю
          </p>
        ) : null}

        <div className={styles.list}>
          {failed ? (
            <EmptyState
              tone="error"
              icon={<IconAlert size={20} />}
              title="Не удалось загрузить ленту"
              description="Это на нашей стороне. Попробуйте через минуту."
              action={
                <Button variant="secondary" onClick={() => void load(tab)}>
                  Повторить
                </Button>
              }
            />
          ) : cards === null ? (
            <SkeletonList count={4} />
          ) : cards.length === 0 ? (
            <EmptyState
              icon={<IconCompass size={20} />}
              title={emptyTitle(tab)}
              description={emptyBody(tab)}
              action={
                tab === 'for_you' ? (
                  <Button variant="secondary" onClick={() => setTab('recent')}>
                    Смотреть все новые
                  </Button>
                ) : undefined
              }
            />
          ) : (
            cards.map((card) => <ProjectCard key={card.id} card={card} />)
          )}
        </div>
      </div>
    </>
  );
}

function emptyTitle(tab: string) {
  if (tab === 'saved') return 'Пока ничего не сохранено';
  if (tab === 'for_you') return 'Подходящих заказов пока нет';
  return 'Здесь пока пусто';
}

function emptyBody(tab: string) {
  if (tab === 'saved') {
    return 'Сохраните заказ на его странице — он будет ждать вас здесь.';
  }
  if (tab === 'for_you') {
    return 'Заказы по вашей специализации и навыкам появятся здесь, как только заказчики их разместят. Добавьте навыки в профиль — и заказов станет больше.';
  }
  return 'Заказчики размещают работу в течение дня. Загляните чуть позже.';
}
