'use client';

import { useId } from 'react';
import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from 'react';
import styles from './Field.module.css';

type FieldShell = {
  label: string;
  hint?: string;
  error?: string;
  /** Shown under a textarea as "180 / 8000". */
  counter?: string;
  optional?: boolean;
  children: (id: string, describedBy: string | undefined) => ReactNode;
};

function Shell({ label, hint, error, counter, optional, children }: FieldShell) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [errorId, hintId].filter(Boolean).join(' ') || undefined;

  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.label}>
        {label}
        {optional ? <span className={styles.optional}>необязательно</span> : null}
      </label>
      {children(id, describedBy)}
      <div className={styles.footer}>
        <div>
          {error ? (
            // Announced when it appears, so a screen-reader user is not left
            // wondering why the form did not submit.
            <p id={errorId} className={styles.error} role="alert">
              {error}
            </p>
          ) : hint ? (
            <p id={hintId} className={styles.hint}>
              {hint}
            </p>
          ) : null}
        </div>
        {counter ? <span className={styles.counter}>{counter}</span> : null}
      </div>
    </div>
  );
}

type InputProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> & {
  label: string;
  hint?: string;
  error?: string;
  optional?: boolean;
  prefix?: ReactNode;
};

export function Input({ label, hint, error, optional, prefix, ...rest }: InputProps) {
  return (
    <Shell label={label} hint={hint} error={error} optional={optional}>
      {(id, describedBy) => (
        <div className={[styles.control, error ? styles.invalid : ''].join(' ')}>
          {prefix ? <span className={styles.prefix}>{prefix}</span> : null}
          <input
            id={id}
            className={styles.input}
            aria-describedby={describedBy}
            aria-invalid={error ? true : undefined}
            {...rest}
          />
        </div>
      )}
    </Shell>
  );
}

type TextareaProps = Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, 'id'> & {
  label: string;
  hint?: string;
  error?: string;
  optional?: boolean;
  /** Renders "120 / 8000" and turns amber as the limit approaches. */
  max?: number;
  value?: string;
};

export function Textarea({ label, hint, error, optional, max, value, ...rest }: TextareaProps) {
  const length = typeof value === 'string' ? value.length : 0;
  const counter = max ? `${length} / ${max}` : undefined;

  return (
    <Shell label={label} hint={hint} error={error} optional={optional} counter={counter}>
      {(id, describedBy) => (
        <div className={[styles.control, styles.area, error ? styles.invalid : ''].join(' ')}>
          <textarea
            id={id}
            className={styles.textarea}
            aria-describedby={describedBy}
            aria-invalid={error ? true : undefined}
            value={value}
            rows={5}
            {...rest}
          />
        </div>
      )}
    </Shell>
  );
}

export function Select({
  label,
  hint,
  error,
  optional,
  children,
  ...rest
}: Omit<InputHTMLAttributes<HTMLSelectElement>, 'id'> & {
  label: string;
  hint?: string;
  error?: string;
  optional?: boolean;
  children: ReactNode;
}) {
  return (
    <Shell label={label} hint={hint} error={error} optional={optional}>
      {(id, describedBy) => (
        <div className={[styles.control, error ? styles.invalid : ''].join(' ')}>
          <select id={id} className={styles.select} aria-describedby={describedBy} {...rest}>
            {children}
          </select>
        </div>
      )}
    </Shell>
  );
}

/** A tappable choice, used for the onboarding pickers and filters. */
export function ChoiceChip({
  selected,
  onToggle,
  children,
  disabled,
}: {
  selected: boolean;
  onToggle: () => void;
  children: ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      className={[styles.chip, selected ? styles.chipSelected : ''].join(' ')}
      onClick={onToggle}
      aria-pressed={selected}
      disabled={disabled}
    >
      {children}
    </button>
  );
}
