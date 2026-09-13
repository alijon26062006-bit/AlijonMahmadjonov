'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import styles from './notifications.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Avatar } from '@/components/ui/Avatar';
import { Button, ButtonLink } from '@/components/ui/Button';
import { Tabs } from '@/components/ui/Tabs';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconBell } from '@/components/ui/Icon';
import { list, post } from '@/lib/api';
import { timeAgo } from '@/lib/format';
import { useRealtime } from '@/lib/realtime';
import type { Notification } from '@/lib/types';

const TABS = [
  { key: 'all', label: 'Все' },
  { key: 'unread', label: 'Непрочитанные' },
];

export default function NotificationsPage() {
  const router = useRouter();
  const [tab, setTab] = useState('all');
  const [items, setItems] = useState<Notification[] | null>(null);
  const [unread, setUnread] = useState(0);
  const [nextBefore, setNextBefore] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(
    async (before: string | null, append: boolean, onlyUnread: boolean) => {
      if (!append) setItems(null);
      const query = new URLSearchParams({ limit: '30' });
      if (before) query.set('before', before);
      if (onlyUnread) query.set('unread', 'true');
      try {
        const response = await list<Notification[]>(`/notifications?${query.toString()}`);
        setItems((current) => (append && current ? [...current, ...(response.data ?? [])] : response.data ?? []));
        setUnread(Number(response.meta?.unread ?? 0));
        setNextBefore((response.meta?.next_before as string) ?? null);
      } catch {
        if (!append) setItems([]);
      }
    },
    [],
  );

  useEffect(() => {
    void load(null, false, tab === 'unread');
  }, [tab, load]);

  useRealtime((event) => {
    if (event.type === 'notification' && event.notification) {
      const incoming = event.notification;
      setItems((current) => (current && !current.some((item) => item.id === incoming.id) ? [incoming, ...current] : current));
      setUnread((count) => count + 1);
    }
  });

  async function open(notification: Notification) {
    if (!notification.read_at) {
      setUnread((count) => Math.max(0, count - 1));
      setItems((current) =>
        current ? current.map((item) => (item.id === notification.id ? { ...item, read_at: new Date().toISOString() } : item)) : current,
      );
      void post(`/notifications/${notification.id}/read`).catch(() => undefined);
    }
    if (notification.href) router.push(notification.href);
  }

  return (
    <>
      <TopBar
        title="Уведомления"
        action={
          <ButtonLink href="/settings#notifications" size="sm" variant="ghost">
            Настроить
          </ButtonLink>
        }
      />
      <div className={`av-page av-stack ${styles.shell}`}>
        <div className="av-row-between">
          <Tabs items={TABS} active={tab} onChange={setTab} ariaLabel="Фильтр уведомлений" />
          {unread > 0 ? (
            <Button
              variant="secondary"
              size="sm"
              loading={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await post('/notifications/read-all');
                  setUnread(0);
                  setItems((current) =>
                    current ? current.map((item) => ({ ...item, read_at: item.read_at ?? new Date().toISOString() })) : current,
                  );
                } finally {
                  setBusy(false);
                }
              }}
            >
              Прочитать всё
            </Button>
          ) : null}
        </div>

        {items === null ? (
          <SkeletonList count={5} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={<IconBell size={20} />}
            title={tab === 'unread' ? 'Непрочитанных нет' : 'Уведомлений пока нет'}
            description="Сюда приходят отклики, сообщения, изменения по этапам и решения по оплатам. Что именно присылать — вы решаете в настройках."
          />
        ) : (
          <div className="av-stack-sm">
            {items.map((notification) => (
              <button
                key={notification.id}
                type="button"
                className={[styles.row, notification.read_at ? '' : styles.unread].join(' ')}
                onClick={() => void open(notification)}
              >
                {notification.read_at ? <span className={styles.spacer} /> : <span className={styles.dot} aria-hidden="true" />}
                {notification.actor ? (
                  <Avatar src={notification.actor.photo_url} name={notification.actor.full_name} size={32} />
                ) : null}
                <div className={styles.body}>
                  <p className={styles.title}>{notification.title}</p>
                  {notification.body ? <p className={styles.text}>{notification.body}</p> : null}
                  <span className={styles.time}>{timeAgo(notification.created_at)}</span>
                </div>
              </button>
            ))}
            {nextBefore ? (
              <Button variant="secondary" onClick={() => void load(nextBefore, true, tab === 'unread')}>
                Показать ещё
              </Button>
            ) : null}
          </div>
        )}
      </div>
    </>
  );
}
