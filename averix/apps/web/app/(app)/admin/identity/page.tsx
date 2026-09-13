'use client';

import Link from 'next/link';
import { useCallback, useEffect, useState } from 'react';
import styles from '../admin.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Field';
import { Tabs } from '@/components/ui/Tabs';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconLock, IconShield } from '@/components/ui/Icon';
import { ApiFailure, list, post } from '@/lib/api';
import { longDate, pluralWord } from '@/lib/format';
import { countryName } from '@/lib/labels';
import { identityStatusLabel, identityTone } from '@/lib/admin';
import type { IdentityQueueItem } from '@/lib/types';

// Значения ровно те, что понимает API: «Ждут проверки» — это отправленные и
// взятые в работу вместе, иначе дело исчезает из очереди ровно в тот момент,
// когда его кто-то открыл.
const FILTERS = [
  { key: 'waiting', label: 'Ждут проверки' },
  { key: 'resubmit_requested', label: 'Просили переснять' },
  { key: 'approved', label: 'Подтверждены' },
  { key: 'rejected', label: 'Отказано' },
  { key: 'all', label: 'Все' },
];

export default function IdentityQueuePage() {
  const [tab, setTab] = useState('waiting');
  const [items, setItems] = useState<IdentityQueueItem[] | null>(null);
  const [gate, setGate] = useState<'ok' | 'locked' | 'denied'>('ok');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setItems(null);
    try {
      const response = await list<IdentityQueueItem[]>(
        `/admin/identity/queue?status=${tab === 'waiting' ? '' : tab}&limit=50`,
      );
      setItems(response.data ?? []);
      setGate('ok');
    } catch (failure) {
      setItems([]);
      if (failure instanceof ApiFailure && failure.code === 'identity_locked') setGate('locked');
      else setGate('denied');
    }
  }, [tab]);

  useEffect(() => {
    void load();
  }, [load]);

  async function unlock(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await post('/admin/identity/unlock', { password });
      setPassword('');
      await load();
    } catch (failure) {
      setError(failure instanceof ApiFailure ? failure.fields.password || failure.message : 'Не получилось.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <TopBar back="/admin" title="Проверка личности" />
      <div className={`av-page av-stack ${styles.shell}`}>
        {gate === 'denied' ? (
          <EmptyState
            icon={<IconShield size={20} />}
            title="Раздел вам не открыт"
            description="Нужно именное разрешение identity_verification.view. Роль администратора его не даёт."
          />
        ) : gate === 'locked' ? (
          <Card>
            <p className="av-small av-muted">
              Раздел с документами открывается повторным вводом пароля на десять минут.
            </p>
            <form className="av-stack-sm" onSubmit={unlock} style={{ marginTop: 'var(--av-space-3)' }}>
              <Input
                label="Ваш пароль"
                type="password"
                autoComplete="current-password"
                value={password}
                error={error || undefined}
                onChange={(event) => setPassword(event.target.value)}
              />
              <div>
                <Button type="submit" loading={busy} disabled={!password} icon={<IconLock size={16} />}>
                  Открыть доступ
                </Button>
              </div>
            </form>
          </Card>
        ) : (
          <>
            <Tabs items={FILTERS} active={tab} onChange={setTab} ariaLabel="Состояние проверки" />
            {items === null ? (
              <SkeletonList count={4} />
            ) : items.length === 0 ? (
              <EmptyState icon={<IconShield size={20} />} title="Здесь пусто" description="Ни одного дела в этом состоянии." />
            ) : (
              <Card>
                {items.map((item) => (
                  <div key={item.id} className={styles.row}>
                    <div className="av-grow">
                      <Link href={`/admin/users/${item.user_id}`} className="av-strong">
                        {item.full_name}
                      </Link>{' '}
                      <span className="av-faint">@{item.username}</span>
                      <p className="av-xs av-faint">
                        {item.document_label || item.document_type
                          ? `${item.document_label || item.document_type} · `
                          : ''}
                        {item.country_code ? `${countryName(item.country_code)} · ` : ''}
                        {item.documents} {pluralWord(item.documents, 'изображение', 'изображения', 'изображений')}
                        {item.submitted_at ? ` · отправлено ${longDate(item.submitted_at)}` : ''}
                      </p>
                      {item.waiting_hours > 0 ? (
                        <p className="av-xs av-faint">
                          ждёт {item.waiting_hours} {pluralWord(item.waiting_hours, 'час', 'часа', 'часов')}
                        </p>
                      ) : null}
                    </div>
                    <Badge tone={identityTone(item.status)} size="sm">
                      {item.status_label || identityStatusLabel(item.status)}
                    </Badge>
                  </div>
                ))}
              </Card>
            )}
          </>
        )}
      </div>
    </>
  );
}
