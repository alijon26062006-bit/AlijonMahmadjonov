'use client';

import { useEffect, useState } from 'react';
import styles from './FundSheet.module.css';
import { Sheet } from '@/components/ui/Sheet';
import { Button } from '@/components/ui/Button';
import { IconCheck, IconInfo, IconShield } from '@/components/ui/Icon';
import { ApiFailure, post } from '@/lib/api';
import { money } from '@/lib/format';
import type { Milestone, Payment } from '@/lib/types';

/**
 * Funding a milestone.
 *
 * On this deployment the money moves by bank transfer and an administrator
 * confirms it, so this screen's job is to show exactly what to send and which
 * reference to quote — and to be honest that the milestone is not funded until
 * the transfer is confirmed.
 */
export function FundSheet({
  milestone,
  onClose,
  onFunded,
}: {
  milestone: Milestone | null;
  onClose: () => void;
  onFunded: () => void;
}) {
  const [payment, setPayment] = useState<Payment | null>(null);
  const [error, setError] = useState<{ message: string; configurable?: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    if (!milestone) {
      setPayment(null);
      setError(null);
    }
  }, [milestone]);

  if (!milestone) return null;

  async function start() {
    if (!milestone) return;
    setBusy(true);
    setError(null);
    try {
      setPayment(await post<Payment>(`/milestones/${milestone.id}/fund`));
    } catch (failure) {
      if (failure instanceof ApiFailure) {
        setError({
          message: failure.message,
          configurable: failure.code === 'payments_not_configured',
        });
      } else {
        setError({ message: "We couldn't start that payment. Please try again." });
      }
    } finally {
      setBusy(false);
    }
  }

  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(value);
      setTimeout(() => setCopied(null), 1600);
    } catch {
      // Clipboard access can be refused; the value is on screen either way.
    }
  }

  return (
    <Sheet
      open
      onClose={onClose}
      title={payment ? 'Send the transfer' : 'Fund this milestone'}
      description={milestone.title}
      footer={
        payment ? (
          <Button onClick={onFunded}>Done</Button>
        ) : (
          <>
            <Button variant="secondary" onClick={onClose}>
              Cancel
            </Button>
            <Button loading={busy} onClick={() => void start()} disabled={Boolean(error?.configurable)}>
              Continue
            </Button>
          </>
        )
      }
    >
      <div className="av-stack">
        {error ? (
          <div className={styles.problem} role="alert">
            <IconInfo size={18} />
            <div>
              <p className="av-strong">{error.message}</p>
              {error.configurable ? (
                <p className="av-small av-muted">
                  An administrator has to add the transfer details before anyone can fund a
                  milestone. Nothing has been charged.
                </p>
              ) : null}
            </div>
          </div>
        ) : null}

        {payment ? (
          <>
            <div className={styles.amountBlock}>
              <span className="av-small av-muted">Send exactly</span>
              <span className={styles.amount}>{money(payment.amount_minor, payment.currency)}</span>
              <span className={styles.status}>{payment.status_label}</span>
            </div>

            <ul className={styles.instructions}>
              {payment.instructions?.map((instruction) => (
                <li key={instruction.label} className={instruction.critical ? styles.critical : ''}>
                  <span className={styles.instructionLabel}>{instruction.label}</span>
                  <button
                    type="button"
                    className={styles.value}
                    onClick={() => void copy(instruction.value)}
                    title="Copy"
                  >
                    {instruction.value}
                    {copied === instruction.value ? <IconCheck size={14} /> : null}
                  </button>
                </li>
              ))}
            </ul>

            <p className={styles.note}>
              <IconShield size={15} />
              Quote the payment reference exactly — that is how your transfer is matched to this
              milestone. Once an administrator confirms it arrived, the developer can start. AVERIX
              does not hold the funds.
            </p>
          </>
        ) : !error ? (
          <>
            <div className={styles.amountBlock}>
              <span className="av-small av-muted">Amount for this milestone</span>
              <span className={styles.amount}>
                {money(milestone.amount_minor, milestone.currency)}
              </span>
            </div>
            <p className={styles.explain}>
              You will get the transfer details and a reference to quote. The milestone becomes
              funded once an administrator confirms the money arrived, and the developer starts
              then — not before.
            </p>
          </>
        ) : null}
      </div>
    </Sheet>
  );
}
