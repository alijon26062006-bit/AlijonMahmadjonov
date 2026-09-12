import type { ReactNode } from 'react';
import Link from 'next/link';
import styles from './Card.module.css';

type CardProps = {
  children: ReactNode;
  /** A card that is itself a link gets the whole surface as the target. */
  href?: string;
  padded?: boolean;
  className?: string;
};

export function Card({ children, href, padded = true, className }: CardProps) {
  const cls = [styles.card, padded ? styles.padded : '', href ? styles.interactive : '', className ?? '']
    .filter(Boolean)
    .join(' ');

  if (href) {
    return (
      <Link href={href} className={cls}>
        {children}
      </Link>
    );
  }
  return <section className={cls}>{children}</section>;
}

export function CardHeader({
  title,
  subtitle,
  action,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <header className={styles.header}>
      <div className={styles.headerText}>
        <h2 className={styles.title}>{title}</h2>
        {subtitle ? <p className={styles.subtitle}>{subtitle}</p> : null}
      </div>
      {action}
    </header>
  );
}

/** A section title outside a card, for lists that are not boxed. */
export function SectionHeading({
  title,
  count,
  action,
}: {
  title: ReactNode;
  count?: number;
  action?: ReactNode;
}) {
  return (
    <div className={styles.sectionHeading}>
      <h2 className={styles.sectionTitle}>
        {title}
        {count !== undefined ? <span className={styles.count}>{count}</span> : null}
      </h2>
      {action}
    </div>
  );
}
