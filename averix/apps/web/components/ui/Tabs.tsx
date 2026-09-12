'use client';

import type { ReactNode } from 'react';
import styles from './Tabs.module.css';

export type TabItem = { key: string; label: string; count?: number };

/**
 * A scrollable row of tabs.
 *
 * On a phone the row scrolls sideways rather than wrapping onto three lines or
 * shrinking the labels into abbreviations nobody can read.
 */
export function Tabs({
  items,
  active,
  onChange,
  ariaLabel,
}: {
  items: TabItem[];
  active: string;
  onChange: (key: string) => void;
  ariaLabel: string;
}) {
  return (
    <div className={styles.wrapper} role="tablist" aria-label={ariaLabel}>
      {items.map((item) => {
        const selected = item.key === active;
        return (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={selected}
            className={[styles.tab, selected ? styles.selected : ''].join(' ')}
            onClick={() => onChange(item.key)}
          >
            {item.label}
            {item.count !== undefined ? <span className={styles.count}>{item.count}</span> : null}
          </button>
        );
      })}
    </div>
  );
}

export function TabPanel({ children }: { children: ReactNode }) {
  return <div role="tabpanel">{children}</div>;
}
