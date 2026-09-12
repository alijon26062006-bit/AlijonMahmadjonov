'use client';

import { useCallback, useEffect, useState } from 'react';
import styles from './payments.module.css';
import { TopBar } from '@/components/nav/TopBar';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Sheet } from '@/components/ui/Sheet';
import { Input, Textarea } from '@/components/ui/Field';
import { Tabs } from '@/components/ui/Tabs';
import { SkeletonList } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { IconCheck, IconWallet } from '@/components/ui/Icon';
import { ApiFailure, get, post } from '@/lib/api';
import { money, timeAgo } from '@/lib/format';
import type { PendingPayment } from '@/lib/types';

const TABS = [
  { key: 'charge', label: 'Incoming transfers' },
  { key: 'payout', label: 'Payouts to send' },
];

export default function AdminPaymentsPage() {
  const [direction, setDirection] = useState('charge');
  const [items, setItems] = useState<PendingPayment[] | null>(null);
  const [confirming, setConfirming] = useState<PendingPayment | null>(null);

  const load = useCallback(async (kind: string) => {
    setItems(null);
    try {
      setItems(await get<PendingPayment[]>(`/admin/payments/queue?direction=${kind}`));
    } catch {
      setItems([]);
    }
  }, []);

  useEffect(() => {
    void load(direction);
  }, [direction, load]);

  return (
    <>
      <TopBar />
      <div className="av-page av-stack">
        <header>
          <h1 className={styles.heading}>Payments</h1>
          <p className="av-muted av-small">
            Money moves by bank transfer; AVERIX records it. Nothing is funded or paid until someone
            here confirms it actually happened.
          </p>
        </header>

        <Tabs items={TABS} active={direction} onChange={setDirection} ariaLabel="Payment queues" />

        {items === null ? (
          <SkeletonList count={2} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={<IconWallet size={20} />}
            title={direction === 'charge' ? 'No transfers waiting' : 'No payouts waiting'}
            description={
              direction === 'charge'
                ? 'When a client says they have sent a transfer, it appears here with the reference to look for on the statement.'
                : 'When a client approves a milestone, the payout to the developer appears here to be sent.'
            }
          />
        ) : (
          <div className="av-stack-sm">
            {items.map((item) => (
              <Card key={item.id}>
                <div className="av-row-between">
                  <div className="av-grow">
                    <p className="av-strong">{item.milestone_title || item.contract_title}</p>
                    <p className="av-small av-muted">
                      {item.contract_reference} ·{' '}
                      {direction === 'charge'
                        ? `from ${item.payer_name}`
                        : `to ${item.payee_name ?? item.payee_username}`}
                    </p>
                  </div>
                  <div className={styles.amountBlock}>
                    <span className={styles.amount}>
                      {money(
                        direction === 'charge' ? item.amount_minor : item.amount_minor - item.fee_minor,
                        item.currency,
                      )}
                    </span>
                    <Badge tone="warning" size="sm">
                      {item.status_label}
                    </Badge>
                  </div>
                </div>

                <div className={styles.reference}>
                  <span className="av-small av-muted">Reference to match</span>
                  <code className={styles.code}>{item.reference}</code>
                </div>

                <footer className={styles.footer}>
                  <span className="av-xs av-faint">Requested {timeAgo(item.created_at)}</span>
                  <Button size="sm" onClick={() => setConfirming(item)}>
                    {direction === 'charge' ? 'Confirm receipt' : 'Confirm payout sent'}
                  </Button>
                </footer>
              </Card>
            ))}
          </div>
        )}
      </div>

      <ConfirmSheet
        item={confirming}
        direction={direction}
        onClose={() => setConfirming(null)}
        onDone={() => {
          setConfirming(null);
          void load(direction);
        }}
      />
    </>
  );
}

function ConfirmSheet({
  item,
  direction,
  onClose,
  onDone,
}: {
  item: PendingPayment | null;
  direction: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const [amount, setAmount] = useState('');
  const [reference, setReference] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<Record<string, string>>({});
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!item) return;
    const expected = direction === 'charge' ? item.amount_minor : item.amount_minor - item.fee_minor;
    setAmount((expected / 100).toFixed(2));
    setReference('');
    setNote('');
    setError({});
    setMessage('');
  }, [item, direction]);

  if (!item) return null;

  const path = direction === 'charge' ? 'confirm' : 'confirm-payout';

  return (
    <Sheet
      open
      onClose={onClose}
      title={direction === 'charge' ? 'Confirm the transfer arrived' : 'Confirm the payout was sent'}
      description={`${item.reference} · ${item.contract_reference ?? ''}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            loading={busy}
            icon={<IconCheck size={16} />}
            onClick={async () => {
              setBusy(true);
              setError({});
              setMessage('');
              try {
                await post(`/admin/payments/${item.id}/${path}`, {
                  amount_minor: Math.round(Number(amount) * 100),
                  reference: reference.trim(),
                  note: note.trim(),
                });
                onDone();
              } catch (failure) {
                if (failure instanceof ApiFailure) {
                  setError(failure.fields);
                  setMessage(Object.keys(failure.fields).length ? '' : failure.message);
                } else {
                  setMessage("That didn't go through. Please try again.");
                }
              } finally {
                setBusy(false);
              }
            }}
          >
            Confirm
          </Button>
        </>
      }
    >
      <div className="av-stack">
        {message ? (
          <p className={styles.alert} role="alert">
            {message}
          </p>
        ) : null}

        <p className={styles.warning}>
          This is the only record that the money moved. It is written to the audit log with your
          name, the amount and the reference — and it cannot be edited afterwards.
        </p>

        <Input
          label="Amount actually received"
          inputMode="decimal"
          prefix="$"
          value={amount}
          error={error.amount_minor}
          hint="Must match the payment exactly. If it doesn't, reject it and ask what was sent."
          onChange={(event) => setAmount(event.target.value)}
        />
        <Input
          label="Bank reference"
          placeholder="Statement line or transaction id"
          value={reference}
          onChange={(event) => setReference(event.target.value)}
        />
        <Textarea
          label="Note"
          optional
          rows={3}
          max={400}
          placeholder="Anything worth recording — when it arrived, which account it came from."
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </div>
    </Sheet>
  );
}
