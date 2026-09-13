'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import styles from '../admin.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Sheet } from '@/components/ui/Sheet';
import { Select, Textarea } from '@/components/ui/Field';
import { Tabs } from '@/components/ui/Tabs';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconShield } from '@/components/ui/Icon';
import { ApiFailure, get, post } from '@/lib/api';
import { timeAgo } from '@/lib/format';
import type { ModerationItem, ModerationReport } from '@/lib/types';

const TABS = [
  { key: 'queue', label: 'Очередь' },
  { key: 'reports', label: 'Жалобы' },
];

const SUBJECT: Record<string, string> = {
  service: 'Услуга',
  project: 'Заказ',
  proposal: 'Отклик',
  message: 'Сообщение',
  user: 'Пользователь',
  review: 'Отзыв',
  portfolio_project: 'Работа в портфолио',
};

export default function ModerationPage() {
  const [tab, setTab] = useState('queue');
  const [items, setItems] = useState<ModerationItem[] | null>(null);
  const [reports, setReports] = useState<ModerationReport[] | null>(null);
  const [deciding, setDeciding] = useState<ModerationItem | null>(null);
  const [resolving, setResolving] = useState<ModerationReport | null>(null);

  const load = useCallback(() => {
    get<ModerationItem[]>('/admin/moderation/queue')
      .then((data) => setItems(data ?? []))
      .catch(() => setItems([]));
    get<ModerationReport[]>('/admin/moderation/reports')
      .then((data) => setReports(data ?? []))
      .catch(() => setReports([]));
  }, []);

  useEffect(() => load(), [load]);

  return (
    <>
      <TopBar back="/admin" title="Модерация" />
      <div className={`av-page av-stack ${styles.shell}`}>
        <Tabs items={TABS} active={tab} onChange={setTab} ariaLabel="Разделы модерации" />

        {tab === 'queue' ? (
          items === null ? (
            <SkeletonList count={3} />
          ) : items.length === 0 ? (
            <EmptyState
              icon={<IconShield size={20} />}
              title="Очередь пуста"
              description="Сюда попадает то, что система сочла подозрительным, и то, на что пожаловались люди."
            />
          ) : (
            items.map((item) => (
              <Card key={item.id}>
                <div className="av-row-between">
                  <div className="av-grow">
                    <p className="av-strong">{item.preview.title || SUBJECT[item.subject_type] || item.subject_type}</p>
                    <p className="av-small av-muted">
                      {SUBJECT[item.subject_type] ?? item.subject_type}
                      {item.preview.owner_username ? ` · @${item.preview.owner_username}` : ''}
                      {' · '}
                      {item.origin === 'automatic' ? 'найдено автоматически' : 'по жалобе'}
                      {' · '}
                      {timeAgo(item.created_at)}
                    </p>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    {item.reports ? (
                      <Badge tone="warning" size="sm">
                        Жалоб: {item.reports}
                      </Badge>
                    ) : null}
                  </div>
                </div>
                <p className="av-small av-muted">Причина: {item.reason}</p>
                {item.preview.excerpt ? <p className={styles.excerpt}>{item.preview.excerpt}</p> : null}
                <div className="av-row av-wrap">
                  {item.href ? (
                    <Link href={item.href} className="av-small">
                      Открыть
                    </Link>
                  ) : null}
                  <Button size="sm" onClick={() => setDeciding(item)}>
                    Решить
                  </Button>
                </div>
              </Card>
            ))
          )
        ) : reports === null ? (
          <SkeletonList count={3} />
        ) : reports.length === 0 ? (
          <EmptyState icon={<IconShield size={20} />} title="Открытых жалоб нет" description="Всё разобрано." />
        ) : (
          reports.map((report) => (
            <Card key={report.id}>
              <div className="av-row-between">
                <div className="av-grow">
                  <p className="av-strong">{report.preview.title || SUBJECT[report.subject_type] || report.subject_type}</p>
                  <p className="av-small av-muted">
                    {report.reason_label}
                    {report.reporter ? ` · от @${report.reporter.username}` : ''} · {timeAgo(report.created_at)}
                  </p>
                </div>
              </div>
              {report.detail ? <p className={styles.excerpt}>{report.detail}</p> : null}
              <div className="av-row">
                <Button size="sm" onClick={() => setResolving(report)}>
                  Закрыть жалобу
                </Button>
              </div>
            </Card>
          ))
        )}
      </div>

      <DecideSheet item={deciding} onClose={() => setDeciding(null)} onDone={() => { setDeciding(null); load(); }} />
      <ResolveSheet report={resolving} onClose={() => setResolving(null)} onDone={() => { setResolving(null); load(); }} />
    </>
  );
}

function DecideSheet({ item, onClose, onDone }: { item: ModerationItem | null; onClose: () => void; onDone: () => void }) {
  const [outcome, setOutcome] = useState('approve');
  const [note, setNote] = useState('');
  const [warn, setWarn] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  if (!item) return null;

  return (
    <Sheet
      open
      onClose={onClose}
      title="Решение модератора"
      description={item.preview.title}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button
            loading={busy}
            disabled={note.trim().length < 10}
            onClick={async () => {
              setBusy(true);
              setError('');
              try {
                await post(`/admin/moderation/queue/${item.id}/decide`, { outcome, note: note.trim(), warn });
                onDone();
              } catch (failure) {
                setError(failure instanceof ApiFailure ? failure.fields.note || failure.message : 'Не получилось.');
              } finally {
                setBusy(false);
              }
            }}
          >
            Применить
          </Button>
        </>
      }
    >
      <div className="av-stack">
        {error ? <p className={styles.alert}>{error}</p> : null}
        <Select label="Решение" value={outcome} onChange={(event) => setOutcome(event.target.value)}>
          <option value="approve">Оставить — нарушения нет</option>
          <option value="reject">Скрыть — нарушение</option>
          <option value="escalate">Передать выше</option>
        </Select>
        <Textarea
          label="Обоснование"
          hint="Не меньше 10 символов. Владелец увидит его, если содержимое скрыто."
          rows={4}
          max={2000}
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
        {outcome === 'reject' ? (
          <label className="av-row" style={{ gap: 'var(--av-space-2)', alignItems: 'center' }}>
            <input type="checkbox" checked={warn} onChange={(event) => setWarn(event.target.checked)} />
            <span className="av-small">Вынести предупреждение владельцу</span>
          </label>
        ) : null}
      </div>
    </Sheet>
  );
}

function ResolveSheet({ report, onClose, onDone }: { report: ModerationReport | null; onClose: () => void; onDone: () => void }) {
  const [status, setStatus] = useState('actioned');
  const [resolution, setResolution] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  if (!report) return null;

  return (
    <Sheet
      open
      onClose={onClose}
      title="Закрыть жалобу"
      description={report.reason_label}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button
            loading={busy}
            disabled={resolution.trim().length < 5}
            onClick={async () => {
              setBusy(true);
              setError('');
              try {
                await post(`/admin/moderation/reports/${report.id}/resolve`, { status, resolution: resolution.trim() });
                onDone();
              } catch (failure) {
                setError(failure instanceof ApiFailure ? failure.message : 'Не получилось.');
              } finally {
                setBusy(false);
              }
            }}
          >
            Закрыть
          </Button>
        </>
      }
    >
      <div className="av-stack">
        {error ? <p className={styles.alert}>{error}</p> : null}
        <Select label="Итог" value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="actioned">Меры приняты</option>
          <option value="dismissed">Нарушения нет</option>
        </Select>
        <Textarea
          label="Что сделано"
          rows={4}
          max={2000}
          value={resolution}
          onChange={(event) => setResolution(event.target.value)}
        />
      </div>
    </Sheet>
  );
}
