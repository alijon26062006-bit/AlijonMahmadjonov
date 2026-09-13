'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import styles from '../admin.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Sheet } from '@/components/ui/Sheet';
import { Select, Textarea } from '@/components/ui/Field';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconShield } from '@/components/ui/Icon';
import { ApiFailure, get, post } from '@/lib/api';
import { money, timeAgo } from '@/lib/format';
import type { DisputedMilestone } from '@/lib/types';

export default function DisputesPage() {
  const [items, setItems] = useState<DisputedMilestone[] | null>(null);
  const [open, setOpen] = useState<DisputedMilestone | null>(null);

  const load = useCallback(() => {
    get<DisputedMilestone[]>('/admin/disputes')
      .then((data) => setItems(data ?? []))
      .catch(() => setItems([]));
  }, []);

  useEffect(() => load(), [load]);

  return (
    <>
      <TopBar back="/admin" title="Споры" />
      <div className={`av-page av-stack ${styles.shell}`}>
        {items === null ? (
          <SkeletonList count={2} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={<IconShield size={20} />}
            title="Открытых споров нет"
            description="Спор открывает любая из сторон, когда договориться не вышло. Решение принимает платформа — и только оно двигает деньги."
          />
        ) : (
          items.map((item) => (
            <Card key={item.milestone_id}>
              <div className="av-row-between">
                <div className="av-grow">
                  <p className="av-strong">{item.title}</p>
                  <p className="av-small av-muted">
                    <Link href={`/contracts/${item.contract_id}`}>{item.contract_title}</Link> · открыт {timeAgo(item.disputed_at)}
                  </p>
                  <p className="av-xs av-faint">
                    Заказчик: {item.client.full_name} · Исполнитель: {item.developer.full_name}
                  </p>
                </div>
                <span className="av-strong av-numeric">{money(item.amount_minor, item.currency)}</span>
              </div>
              {item.note ? <p className={styles.excerpt}>{item.note}</p> : null}
              <div className="av-row">
                <Button size="sm" onClick={() => setOpen(item)}>
                  Вынести решение
                </Button>
              </div>
            </Card>
          ))
        )}
      </div>

      <ResolveSheet
        item={open}
        onClose={() => setOpen(null)}
        onDone={() => {
          setOpen(null);
          load();
        }}
      />
    </>
  );
}

function ResolveSheet({ item, onClose, onDone }: { item: DisputedMilestone | null; onClose: () => void; onDone: () => void }) {
  const [outcome, setOutcome] = useState('no_action');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  if (!item) return null;

  return (
    <Sheet
      open
      onClose={onClose}
      title="Решение по спору"
      description={`${item.title} · ${money(item.amount_minor, item.currency)}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button
            loading={busy}
            disabled={note.trim().length < 20}
            onClick={async () => {
              setBusy(true);
              setError('');
              try {
                await post(`/admin/disputes/${item.milestone_id}/resolve`, { outcome, note: note.trim() });
                onDone();
              } catch (failure) {
                setError(failure instanceof ApiFailure ? failure.fields.note || failure.message : 'Не получилось.');
              } finally {
                setBusy(false);
              }
            }}
          >
            Вынести решение
          </Button>
        </>
      }
    >
      <div className="av-stack">
        {error ? <p className={styles.alert}>{error}</p> : null}
        <Select label="Решение" value={outcome} onChange={(event) => setOutcome(event.target.value)}>
          <option value="no_action">Вернуть в работу — спор преждевременный</option>
          <option value="developer_favoured">В пользу исполнителя — работа принимается</option>
          <option value="client_favoured">В пользу заказчика — этап отменяется, деньги возвращаются</option>
        </Select>
        <Textarea
          label="Обоснование"
          hint="Не меньше 20 символов. Текст видят обе стороны."
          rows={5}
          max={4000}
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
        <p className="av-small av-faint">
          Деньги двигаются ровно так, как двигались бы без спора: приёмка выплачивает через платёжный
          модуль, отмена возвращает. Это решение никогда не переводит средства напрямую.
        </p>
      </div>
    </Sheet>
  );
}
