import type { ReactNode } from 'react';
import styles from './Badge.module.css';

type Tone = 'neutral' | 'brand' | 'success' | 'warning' | 'danger' | 'info' | 'verified';

export function Badge({
  children,
  tone = 'neutral',
  icon,
  size = 'md',
}: {
  children: ReactNode;
  tone?: Tone;
  icon?: ReactNode;
  size?: 'sm' | 'md';
}) {
  return (
    <span className={[styles.badge, styles[tone], styles[size]].join(' ')}>
      {icon}
      {children}
    </span>
  );
}

/** A small coloured dot with a label, for statuses in lists. */
export function StatusDot({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span className={styles.status}>
      <span className={[styles.dot, styles[tone]].join(' ')} aria-hidden="true" />
      {children}
    </span>
  );
}

/** A technology tag. Deliberately quiet: a card with eight loud chips is noise. */
export function Tag({ children }: { children: ReactNode }) {
  return <span className={styles.tag}>{children}</span>;
}
