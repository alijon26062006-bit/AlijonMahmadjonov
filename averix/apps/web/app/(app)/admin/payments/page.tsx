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
  { key: 'charge', label: 'Входящие переводы' },
  { key: 'payout', label: 'Выплаты исполнителям' },
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
          <h1 className={styles.heading}>Платежи</h1>
          <p className="av-muted av-small">
            Деньги идут банковским переводом, AVERIX ведёт учёт. Ни один этап не считается
            оплаченным, пока здесь не подтвердят, что перевод действительно пришёл.
          </p>
        </header>

        <Tabs items={TABS} active={direction} onChange={setDirection} ariaLabel="Очереди платежей" />

        {items === null ? (
          <SkeletonList count={2} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={<IconWallet size={20} />}
            title={direction === 'charge' ? 'Переводов в ожидании нет' : 'Выплат в ожидании нет'}
            description={
              direction === 'charge'
                ? 'Когда заказчик сообщит о переводе, он появится здесь с номером, который нужно найти в выписке.'
                : 'Когда заказчик примет этап, выплата исполнителю появится здесь.'
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
                        ? `от ${item.payer_name}`
                        : `для ${item.payee_name ?? item.payee_username}`}
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
                  <span className="av-small av-muted">Номер платежа для сверки</span>
                  <code className={styles.code}>{item.reference}</code>
                </div>

                <footer className={styles.footer}>
                  <span className="av-xs av-faint">Создан {timeAgo(item.created_at)}</span>
                  <Button size="sm" onClick={() => setConfirming(item)}>
                    {direction === 'charge' ? 'Подтвердить поступление' : 'Подтвердить выплату'}
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
      title={direction === 'charge' ? 'Подтвердить поступление перевода' : 'Подтвердить отправку выплаты'}
      description={`${item.reference} · ${item.contract_reference ?? ''}`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Отмена
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
                  setMessage('Не получилось. Попробуйте ещё раз.');
                }
              } finally {
                setBusy(false);
              }
            }}
          >
            Подтвердить
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
          Это единственная запись о движении денег. Она попадает в журнал аудита с вашим именем,
          суммой и номером — и потом её нельзя изменить.
        </p>

        <Input
          label={`Фактическая сумма (${item.currency})`}
          inputMode="decimal"
          value={amount}
          error={error.amount_minor}
          hint="Должна совпадать с платежом точно. Если нет — отклоните и уточните, что было отправлено."
          onChange={(event) => setAmount(event.target.value)}
        />
        <Input
          label="Банковский идентификатор"
          placeholder="Строка выписки или номер транзакции"
          value={reference}
          onChange={(event) => setReference(event.target.value)}
        />
        <Textarea
          label="Примечание"
          optional
          rows={3}
          max={400}
          placeholder="Что стоит зафиксировать: когда пришло, с какого счёта."
          value={note}
          onChange={(event) => setNote(event.target.value)}
        />
      </div>
    </Sheet>
  );
}
