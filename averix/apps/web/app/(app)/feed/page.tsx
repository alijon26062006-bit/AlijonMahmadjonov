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
import type { FeedCard } from '@/lib/types';

// The tabs are per developer: the category ones come from what this person
// actually works in, so a Telegram developer gets a Telegram tab and an iOS
// developer does not.
const FALLBACK_TABS = [
  { key: 'for_you', label: 'For you' },
  { key: 'recent', label: 'Recent' },
  { key: 'saved', label: 'Saved' },
];

export default function FeedPage() {
  const [tabs, setTabs] = useState(FALLBACK_TABS);
  const [tab, setTab] = useState('for_you');
  const [cards, setCards] = useState<FeedCard[] | null>(null);
  const [meta, setMeta] = useState<Record<string, unknown>>({});
  const [failed, setFailed] = useState(false);

  const load = useCallback(async (key: string) => {
    setCards(null);
    setFailed(false);
    try {
      const response = await list<FeedCard[]>(`/projects?tab=${encodeURIComponent(key)}`);
      setCards(response.data ?? []);
      setMeta(response.meta ?? {});
    } catch {
      setFailed(true);
    }
  }, []);

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
          <h1 className={styles.heading}>Find work</h1>
          <p className={styles.subheading}>
            Projects aimed at what you do, not everything posted today.
          </p>
        </header>

        <div className={styles.tabs}>
          <Tabs items={tabs} active={tab} onChange={setTab} ariaLabel="Feed sections" />
        </div>

        {typeof meta.count === 'number' && cards?.length ? (
          <p className={styles.count}>
            {meta.count} {meta.count === 1 ? 'project' : 'projects'} matched
          </p>
        ) : null}

        <div className={styles.list}>
          {failed ? (
            <EmptyState
              tone="error"
              icon={<IconAlert size={20} />}
              title="We couldn't load your feed"
              description="This is on us, not on you. Try again in a moment."
              action={
                <Button variant="secondary" onClick={() => void load(tab)}>
                  Try again
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
                    Browse everything recent
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
  if (tab === 'saved') return 'Nothing saved yet';
  if (tab === 'for_you') return 'No matching projects right now';
  return 'No projects here yet';
}

function emptyBody(tab: string) {
  if (tab === 'saved') {
    return 'Save a project from its page and it will wait for you here.';
  }
  if (tab === 'for_you') {
    return 'Projects that match your specialisation and technologies will appear here as clients post them. Adding technologies to your profile widens what reaches you.';
  }
  return 'Clients post work throughout the day. Check back shortly.';
}
