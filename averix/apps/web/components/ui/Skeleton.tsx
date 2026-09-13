import styles from './Skeleton.module.css';

/**
 * A loading placeholder shaped like the thing it replaces.
 *
 * Screens never go blank white: the layout is drawn immediately and filled in,
 * so a slow connection sees the page arrive rather than nothing happening.
 */
export function Skeleton({
  width,
  height = 14,
  radius = 'var(--av-radius-sm)',
  className,
}: {
  width?: number | string;
  height?: number | string;
  radius?: string;
  className?: string;
}) {
  return (
    <span
      className={[styles.skeleton, className ?? ''].join(' ')}
      style={{ width: width ?? '100%', height, borderRadius: radius }}
      aria-hidden="true"
    />
  );
}

export function SkeletonCard() {
  return (
    <div className={styles.card} aria-hidden="true">
      <div className={styles.row}>
        <Skeleton width={40} height={40} radius="50%" />
        <div className={styles.lines}>
          <Skeleton width="55%" height={13} />
          <Skeleton width="35%" height={11} />
        </div>
      </div>
      <Skeleton height={12} />
      <Skeleton width="80%" height={12} />
      <div className={styles.chips}>
        <Skeleton width={64} height={20} radius="var(--av-radius-sm)" />
        <Skeleton width={52} height={20} radius="var(--av-radius-sm)" />
        <Skeleton width={70} height={20} radius="var(--av-radius-sm)" />
      </div>
    </div>
  );
}

export function SkeletonList({ count = 3 }: { count?: number }) {
  return (
    <div className={styles.list} role="status" aria-label="Загрузка">
      {Array.from({ length: count }, (_, index) => (
        <SkeletonCard key={index} />
      ))}
      <span className="av-sr-only">Загрузка…</span>
    </div>
  );
}
