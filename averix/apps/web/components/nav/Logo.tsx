import styles from './Logo.module.css';

/**
 * The AVERIX mark: three chamfered bars climbing to the right, the ascent of
 * an A. Two violet, one green — the supplied logo, traced, not redrawn.
 */
export function LogoMark({ size = 22 }: { size?: number }) {
  return (
    <svg
      width={(size * 336) / 463}
      height={size}
      viewBox="0 0 336 463"
      role="img"
      aria-label="AVERIX"
      className={styles.mark}
    >
      <polygon fill="var(--av-brand)" points="134,0 214,0 148,144 71,144" />
      <polygon fill="var(--av-brand)" points="35,233 300,233 330,302 6,302" />
      <polygon fill="var(--av-accent)" points="30,393 307,393 336,463 0,463" />
    </svg>
  );
}

export function Wordmark({ size = 20 }: { size?: number }) {
  return (
    <span className={styles.wordmark} style={{ fontSize: size }}>
      <LogoMark size={size} />
      <span className={styles.word}>AVERIX</span>
    </span>
  );
}
