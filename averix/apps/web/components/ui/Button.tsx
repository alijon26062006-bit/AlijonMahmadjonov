'use client';

import { forwardRef } from 'react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import Link from 'next/link';
import styles from './Button.module.css';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'accent';
type Size = 'sm' | 'md' | 'lg';

type BaseProps = {
  variant?: Variant;
  size?: Size;
  /** Fills the row, which is what a primary action does on a phone. */
  block?: boolean;
  loading?: boolean;
  icon?: ReactNode;
  iconEnd?: ReactNode;
  children?: ReactNode;
  className?: string;
};

export type ButtonProps = BaseProps & ButtonHTMLAttributes<HTMLButtonElement>;

function classes({ variant = 'primary', size = 'md', block, loading, className }: BaseProps) {
  return [
    styles.button,
    styles[variant],
    styles[size],
    block ? styles.block : '',
    loading ? styles.loading : '',
    className ?? '',
  ]
    .filter(Boolean)
    .join(' ');
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant, size, block, loading, icon, iconEnd, children, className, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      className={classes({ variant, size, block, loading, className })}
      disabled={disabled || loading}
      // A button that is working says so to a screen reader too, not only by
      // spinning.
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <span className={styles.spinner} aria-hidden="true" /> : icon}
      {children ? <span className={styles.label}>{children}</span> : null}
      {iconEnd}
    </button>
  );
});

type ButtonLinkProps = BaseProps & {
  href: string;
  prefetch?: boolean;
  target?: string;
  rel?: string;
  onClick?: () => void;
};

/** The same shape as a link, because a navigation is not a button. */
export function ButtonLink({
  href,
  variant,
  size,
  block,
  icon,
  iconEnd,
  children,
  className,
  ...rest
}: ButtonLinkProps) {
  return (
    <Link href={href} className={classes({ variant, size, block, className })} {...rest}>
      {icon}
      {children ? <span className={styles.label}>{children}</span> : null}
      {iconEnd}
    </Link>
  );
}
