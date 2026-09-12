'use client';

import { useEffect, useState } from 'react';
import styles from './earnings.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconLock, IconWallet } from '@/components/ui/Icon';
import { get } from '@/lib/api';
import { money, shortDate } from '@/lib/format';
import type { Balance } from '@/lib/types';

export default function EarningsPage() {
  const [balance, setBalance] = useState<Balance | null>(null);

  useEffect(() => {
    get<Balance>('/me/balance')
      .then(setBalance)
      .catch(() => setBalance(null));
  }, []);

  return (
    <>
      <TopBar />
      <div className="av-page av-stack">
        <header>
          <h1 className={styles.heading}>Earnings</h1>
          <p className="av-muted av-small">
            <IconLock size={13} /> Private to you. Nothing here appears on your public profile.
          </p>
        </header>

        {!balance ? (
          <Skeleton height={150} radius="var(--av-radius-xl)" />
        ) : (
          <>
            <div className={styles.figures}>
              <Card>
                <p className={styles.figureLabel}>Pending</p>
                <p className={styles.figure}>{money(balance.pending_minor, balance.currency)}</p>
                <p className="av-xs av-faint">Approved work, payout not yet sent</p>
              </Card>
              <Card>
                <p className={styles.figureLabel}>Paid out</p>
                <p className={styles.figure}>
                  {money(balance.lifetime_minor - balance.fees_minor, balance.currency)}
                </p>
                <p className="av-xs av-faint">
                  After {money(balance.fees_minor, balance.currency)} in platform fees
                </p>
              </Card>
            </div>

            <Card>
              <h2 className={styles.sectionTitle}>Ledger</h2>
              {balance.entries?.length ? (
                <ul className={styles.entries}>
                  {balance.entries.map((entry) => (
                    <li key={entry.id}>
                      <div className="av-grow">
                        <p className="av-small av-strong">{describe(entry.kind)}</p>
                        <p className="av-xs av-faint">
                          {entry.description ? `${entry.description} · ` : ''}
                          {shortDate(entry.created_at)}
                        </p>
                      </div>
                      <span
                        className={[
                          styles.entryAmount,
                          entry.amount_minor < 0 ? styles.negative : styles.positive,
                        ].join(' ')}
                      >
                        {entry.amount_minor > 0 ? '+' : ''}
                        {money(entry.amount_minor, entry.currency)}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState
                  icon={<IconWallet size={20} />}
                  title="No earnings yet"
                  description="When a client approves a milestone and the payout is sent, every line of it appears here — what you earned, what the platform took, and what was paid."
                />
              )}
            </Card>
          </>
        )}
      </div>
    </>
  );
}

function describe(kind: string) {
  switch (kind) {
    case 'earning':
      return 'Milestone earned';
    case 'fee':
      return 'Platform fee';
    case 'payout':
      return 'Paid out to you';
    case 'refund':
      return 'Refunded';
    default:
      return kind;
  }
}
