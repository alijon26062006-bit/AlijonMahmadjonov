'use client';

import { useEffect, useState } from 'react';
import styles from './contracts.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Avatar } from '@/components/ui/Avatar';
import { Badge } from '@/components/ui/Badge';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { Tabs } from '@/components/ui/Tabs';
import { IconBriefcase } from '@/components/ui/Icon';
import { get } from '@/lib/api';
import { money, shortDate, timeAgo } from '@/lib/format';
import type { ContractCard } from '@/lib/types';

const TABS = [
  { key: 'active', label: 'Active' },
  { key: 'completed', label: 'Completed' },
  { key: 'all', label: 'All' },
];

export default function ContractsPage() {
  const [contracts, setContracts] = useState<ContractCard[] | null>(null);
  const [tab, setTab] = useState('active');

  useEffect(() => {
    let cancelled = false;
    setContracts(null);
    get<ContractCard[]>('/contracts')
      .then((data) => !cancelled && setContracts(data))
      .catch(() => !cancelled && setContracts([]));
    return () => {
      cancelled = true;
    };
  }, []);

  const visible = (contracts ?? []).filter((contract) => {
    if (tab === 'all') return true;
    if (tab === 'completed') return contract.status === 'completed' || contract.status === 'cancelled';
    return contract.status !== 'completed' && contract.status !== 'cancelled';
  });

  return (
    <>
      <TopBar />
      <div className="av-page av-stack">
        <header>
          <h1 className={styles.heading}>Contracts</h1>
          <p className="av-muted av-small">Signed work, its milestones and what has been paid.</p>
        </header>

        <Tabs items={TABS} active={tab} onChange={setTab} ariaLabel="Contract filters" />

        {contracts === null ? (
          <SkeletonList count={2} />
        ) : visible.length === 0 ? (
          <EmptyState
            icon={<IconBriefcase size={20} />}
            title={tab === 'completed' ? 'Nothing finished yet' : 'No active contracts'}
            description={
              tab === 'completed'
                ? 'Completed contracts stay here, and attach themselves to your profile as verified work.'
                : 'When a proposal is accepted, the contract and its workspace appear here.'
            }
          />
        ) : (
          <div className="av-stack-sm">
            {visible.map((contract) => (
              <Card key={contract.id} href={`/contracts/${contract.id}`}>
                <div className="av-row-between">
                  <div className="av-row av-grow">
                    <Avatar
                      src={contract.counterparty.photo_url}
                      name={contract.counterparty.full_name}
                      size={40}
                    />
                    <div className="av-grow">
                      <p className="av-strong">{contract.title}</p>
                      <p className="av-small av-muted">
                        {contract.counterparty.full_name} · {contract.reference}
                      </p>
                    </div>
                  </div>
                  <div className={styles.right}>
                    {contract.amount_minor !== undefined ? (
                      <span className={styles.amount}>
                        {money(contract.amount_minor, contract.currency)}
                      </span>
                    ) : null}
                    {contract.needs_my_action ? (
                      <Badge tone="brand" size="sm">
                        Needs you
                      </Badge>
                    ) : (
                      <span className="av-xs av-faint">{timeAgo(contract.updated_at)}</span>
                    )}
                  </div>
                </div>

                <div className={styles.progress}>
                  <div className={styles.track} aria-hidden="true">
                    <span className={styles.fill} style={{ width: `${contract.progress_percent}%` }} />
                  </div>
                  <span className="av-xs av-numeric av-muted">{contract.progress_percent}%</span>
                </div>

                <p className="av-small av-muted">
                  {contract.next_milestone
                    ? `Next: ${contract.next_milestone.title}`
                    : contract.status === 'completed'
                      ? 'Completed'
                      : 'No open milestones'}
                  {contract.due_on ? ` · due ${shortDate(contract.due_on)}` : ''}
                </p>
              </Card>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
