import type { ReactNode } from 'react';
import styles from './EmptyState.module.css';

/**
 * An empty state that says what will appear here and what to do about it.
 *
 * Never "No data": a person who sees an empty screen deserves to know whether
 * something is broken, whether they have to act, or whether they are simply
 * early.
 */
export function EmptyState({
  title,
  description,
  action,
  icon,
  tone = 'neutral',
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  icon?: ReactNode;
  tone?: 'neutral' | 'error';
}) {
  return (
    <div className={[styles.empty, tone === 'error' ? styles.error : ''].join(' ')}>
      {icon ? <span className={styles.icon}>{icon}</span> : null}
      <h3 className={styles.title}>{title}</h3>
      {description ? <p className={styles.description}>{description}</p> : null}
      {action ? <div className={styles.action}>{action}</div> : null}
    </div>
  );
}
