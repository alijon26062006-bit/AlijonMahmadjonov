'use client';

import { useState } from 'react';
import styles from './MatchExplainer.module.css';
import { IconCheck, IconChevronDown, IconClose } from '@/components/ui/Icon';
import type { MatchReason } from '@/lib/types';

/**
 * "94% match" with the reasons behind it.
 *
 * A percentage with nothing behind it is a number somebody made up. This one
 * opens in place and lists what was met and what was not, in the same words
 * the matching engine used to compute it.
 */
export function MatchExplainer({
  score,
  highlights,
  compact,
}: {
  score: number;
  highlights?: MatchReason[];
  compact?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const reasons = highlights ?? [];
  const tone = score >= 85 ? styles.strong : score >= 60 ? styles.fair : styles.weak;

  if (reasons.length === 0) {
    return <span className={[styles.pill, tone].join(' ')}>{score}% match</span>;
  }

  return (
    <div className={styles.wrapper}>
      <button
        type="button"
        className={[styles.pill, tone, styles.button].join(' ')}
        onClick={(event) => {
          // The card around this is usually a link.
          event.preventDefault();
          event.stopPropagation();
          setOpen((value) => !value);
        }}
        aria-expanded={open}
      >
        {score}% match
        <IconChevronDown size={13} className={open ? styles.flip : undefined} />
      </button>

      {open ? (
        <ul className={[styles.reasons, compact ? styles.compact : ''].join(' ')}>
          {reasons.map((reason) => (
            <li key={reason.label} className={reason.met ? styles.met : styles.missing}>
              {reason.met ? <IconCheck size={14} /> : <IconClose size={14} />}
              <span>
                {reason.label}
                {reason.detail ? <span className={styles.detail}> — {reason.detail}</span> : null}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
