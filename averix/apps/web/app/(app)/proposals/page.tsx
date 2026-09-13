'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button, ButtonLink } from '@/components/ui/Button';
import { Tabs } from '@/components/ui/Tabs';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconSend } from '@/components/ui/Icon';
import { ApiFailure, get, post } from '@/lib/api';
import { useRoleGuard } from '@/lib/session';
import { days, money, timeAgo } from '@/lib/format';
import { PROPOSAL_STATUS } from '@/lib/labels';
import type { OwnProposal } from '@/lib/types';

const TABS = [
  { key: '', label: 'Все' },
  { key: 'submitted', label: 'Отправленные' },
  { key: 'shortlisted', label: 'В шорт-листе' },
  { key: 'accepted', label: 'Принятые' },
  { key: 'declined', label: 'Отклонённые' },
];

export default function MyProposalsPage() {
  useRoleGuard('developer');
  const [status, setStatus] = useState('');
  const [items, setItems] = useState<OwnProposal[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(async (nextStatus: string) => {
    setItems(null);
    try {
      setItems(await get<OwnProposal[]>(`/proposals/mine${nextStatus ? `?status=${nextStatus}` : ''}`));
    } catch {
      setItems([]);
    }
  }, []);

  useEffect(() => {
    void load(status);
  }, [status, load]);

  async function withdraw(id: string) {
    if (!window.confirm('Отозвать отклик? Вернуть его будет нельзя.')) return;
    setBusy(id);
    setError('');
    try {
      await post(`/proposals/${id}/withdraw`);
      void load(status);
    } catch (failure) {
      setError(failure instanceof ApiFailure ? failure.message : 'Не получилось отозвать отклик.');
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <TopBar title="Мои отклики" />
      <div className="av-page av-stack">
        <Tabs items={TABS} active={status} onChange={setStatus} ariaLabel="Статус откликов" />

        {error ? (
          <p role="alert" style={{ color: 'var(--av-danger)' }}>
            {error}
          </p>
        ) : null}

        {items === null ? (
          <SkeletonList count={3} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={<IconSend size={20} />}
            title={status ? 'В этом разделе пусто' : 'Откликов пока нет'}
            description="Найдите подходящий заказ в ленте и отправьте отклик — заказчик увидит вашу цену, срок и опыт."
            action={<ButtonLink href="/feed">Открыть ленту заказов</ButtonLink>}
          />
        ) : (
          items.map((proposal) => (
            <Card key={proposal.id}>
              <div className="av-row-between">
                <div className="av-grow">
                  {proposal.project_slug ? (
                    <Link href={`/projects/${proposal.project_slug}`} className="av-strong">
                      {proposal.project_title ?? 'Заказ'}
                    </Link>
                  ) : (
                    <p className="av-strong">{proposal.project_title ?? 'Заказ'}</p>
                  )}
                  <p className="av-small av-muted">
                    {proposal.amount_display} · {days(proposal.delivery_days)} · отправлен {timeAgo(proposal.created_at)}
                  </p>
                  <p className="av-xs av-faint">
                    Вы получите {money(proposal.payout_minor, proposal.currency)} после комиссии
                  </p>
                </div>
                <Badge tone={tone(proposal.status)} size="sm">
                  {PROPOSAL_STATUS[proposal.status] ?? proposal.status}
                </Badge>
              </div>

              {proposal.decline_reason ? (
                <p className="av-small av-muted">Причина отказа: {proposal.decline_reason}</p>
              ) : null}
              {proposal.client_note ? <p className="av-small av-muted">Заказчик: {proposal.client_note}</p> : null}

              {proposal.status === 'submitted' || proposal.status === 'shortlisted' ? (
                <div className="av-row">
                  <Button size="sm" variant="ghost" loading={busy === proposal.id} onClick={() => void withdraw(proposal.id)}>
                    Отозвать
                  </Button>
                </div>
              ) : null}
            </Card>
          ))
        )}
      </div>
    </>
  );
}

function tone(status: string) {
  switch (status) {
    case 'accepted':
      return 'success' as const;
    case 'shortlisted':
      return 'brand' as const;
    case 'declined':
    case 'withdrawn':
      return 'neutral' as const;
    default:
      return 'info' as const;
  }
}
