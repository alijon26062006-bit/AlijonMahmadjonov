import styles from './Avatar.module.css';
import { initials } from '@/lib/format';

type AvatarProps = {
  src?: string | null;
  name?: string | null;
  size?: 24 | 32 | 40 | 48 | 64 | 96;
  /** A ring marks the person as verified, without adding another chip. */
  verified?: boolean;
};

export function Avatar({ src, name, size = 40, verified }: AvatarProps) {
  const style = { width: size, height: size, fontSize: Math.round(size * 0.38) };

  return (
    <span
      className={[styles.avatar, verified ? styles.verified : ''].filter(Boolean).join(' ')}
      style={style}
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element -- avatars come
        // from our own storage at a known size; the optimiser adds nothing.
        <img src={src} alt="" width={size} height={size} className={styles.image} loading="lazy" />
      ) : (
        <span aria-hidden="true">{initials(name)}</span>
      )}
    </span>
  );
}
