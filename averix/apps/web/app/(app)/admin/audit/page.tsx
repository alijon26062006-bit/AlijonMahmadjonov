'use client';

import { useCallback, useEffect, useState } from 'react';
import styles from '../admin.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Field';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconFolder, IconSearch } from '@/components/ui/Icon';
import { list } from '@/lib/api';
import { timeAgo } from '@/lib/format';
import type { AuditRow } from '@/lib/types';

export default function AuditPage() {
  const [action, setAction] = useState('');
  const [rows, setRows] = useState<AuditRow[] | null>(null);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);

  const load = useCallback(
    async (nextOffset: number, append: boolean) => {
      if (!append) setRows(null);
      const query = new URLSearchParams({ limit: '50', offset: String(nextOffset) });
      if (action.trim()) query.set('action', action.trim());
      try {
        const response = await list<AuditRow[]>(`/admin/audit?${query.toString()}`);
        setRows((current) => (append && current ? [...current, ...(response.data ?? [])] : response.data ?? []));
        setTotal(Number(response.meta?.total ?? 0));
        setOffset(nextOffset);
      } catch {
        if (!append) setRows([]);
      }
    },
    [action],
  );

  useEffect(() => {
    void load(0, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <TopBar back="/admin" title="Журнал действий" />
      <div className={`av-page av-stack ${styles.shell}`}>
        <Card>
          <form
            className="av-row av-wrap"
            onSubmit={(event) => {
              event.preventDefault();
              void load(0, false);
            }}
          >
            <Input
              label="Фильтр по действию"
              placeholder="user. / payment. / moderation."
              hint="Начало названия действия, например user.suspended"
              value={action}
              onChange={(event) => setAction(event.target.value)}
            />
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <Button type="submit" icon={<IconSearch size={16} />}>
                Показать
              </Button>
            </div>
          </form>
        </Card>

        {rows === null ? (
          <SkeletonList count={5} />
        ) : rows.length === 0 ? (
          <EmptyState icon={<IconFolder size={20} />} title="Записей нет" description="Под этот фильтр ничего не попало." />
        ) : (
          <Card>
            <p className="av-small av-muted">Всего записей: {total}</p>
            {rows.map((row) => (
              <div key={row.id} className={styles.auditRow}>
                <div className="av-row-between">
                  <span className={styles.code}>{row.action}</span>
                  <span className="av-xs av-faint">{timeAgo(row.created_at)}</span>
                </div>
                <span className="av-xs av-muted">
                  {row.actor_name ? `${row.actor_name}` : 'система'}
                  {row.actor_role ? ` (${row.actor_role})` : ''}
                  {row.subject_type ? ` → ${row.subject_type}` : ''}
                  {row.outcome ? ` · ${row.outcome}` : ''}
                  {row.ip ? ` · ${row.ip}` : ''}
                </span>
                {row.detail ? <span className="av-small">{row.detail}</span> : null}
              </div>
            ))}
            {rows.length < total ? (
              <Button variant="secondary" onClick={() => void load(offset + 50, true)}>
                Показать ещё
              </Button>
            ) : null}
          </Card>
        )}
      </div>
    </>
  );
}
