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
          <h1 className={styles.heading}>Доходы</h1>
          <p className="av-muted av-small">
            <IconLock size={13} /> Только для вас. Ничего отсюда не попадает в публичный профиль.
          </p>
        </header>

        {!balance ? (
          <Skeleton height={150} radius="var(--av-radius-xl)" />
        ) : (
          <>
            <div className={styles.figures}>
              <Card>
                <p className={styles.figureLabel}>Ожидает выплаты</p>
                <p className={styles.figure}>{money(balance.pending_minor, balance.currency)}</p>
                <p className="av-xs av-faint">Принятая работа, выплата ещё не отправлена</p>
              </Card>
              <Card>
                <p className={styles.figureLabel}>Выплачено</p>
                <p className={styles.figure}>
                  {money(balance.lifetime_minor - balance.fees_minor, balance.currency)}
                </p>
                <p className="av-xs av-faint">
                  За вычетом комиссии платформы {money(balance.fees_minor, balance.currency)}
                </p>
              </Card>
            </div>

            <Card>
              <h2 className={styles.sectionTitle}>История операций</h2>
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
                  title="Доходов пока нет"
                  description="Когда заказчик примет этап и выплата будет отправлена, каждая строка появится здесь: сколько заработано, сколько удержала платформа и сколько выплачено."
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
      return 'Начислено за этап';
    case 'fee':
      return 'Комиссия платформы';
    case 'payout':
      return 'Выплата вам';
    case 'refund':
      return 'Возврат';
    default:
      return kind;
  }
}
