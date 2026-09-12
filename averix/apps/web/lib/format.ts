// Formatting people actually read.

/** Money arrives as integer minor units with an explicit currency, always. */
export function money(minor: number | null | undefined, currency = 'USD'): string {
  if (minor === null || minor === undefined) return '';
  const symbol: Record<string, string> = { USD: '$', EUR: '€', GBP: '£' };
  const prefix = symbol[currency] ?? `${currency} `;
  const whole = Math.trunc(minor / 100);
  const cents = Math.abs(minor % 100);
  const grouped = whole.toLocaleString('en-US');
  return cents === 0 ? `${prefix}${grouped}` : `${prefix}${grouped}.${String(cents).padStart(2, '0')}`;
}

/** A compact form for cards, where "$1,200" beats "$1,200.00". */
export function moneyShort(minor: number | null | undefined, currency = 'USD'): string {
  if (minor === null || minor === undefined) return '';
  return money(Math.round(minor / 100) * 100, currency);
}

export function budgetRange(
  min: number | null | undefined,
  max: number | null | undefined,
  currency = 'USD',
): string {
  if (min && max) return `${moneyShort(min, currency)} – ${moneyShort(max, currency)}`;
  if (max) return `up to ${moneyShort(max, currency)}`;
  if (min) return `from ${moneyShort(min, currency)}`;
  return 'Budget to discuss';
}

/** Relative time, stopping at a date once "days ago" stops being useful. */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const seconds = Math.round((Date.now() - then) / 1000);

  if (seconds < 45) return 'just now';
  if (seconds < 90) return 'a minute ago';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} ${hours === 1 ? 'hour' : 'hours'} ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days} ${days === 1 ? 'day' : 'days'} ago`;
  if (days < 30) return `${Math.round(days / 7)} weeks ago`;
  return shortDate(iso);
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const sameYear = date.getFullYear() === new Date().getFullYear();
  return date.toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'short',
    year: sameYear ? undefined : 'numeric',
  });
}

export function clockTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });
}

export function initials(name: string | null | undefined): string {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((part) => part.charAt(0).toUpperCase()).join('') || '?';
}

export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** "3 proposals" without the awkward "1 proposals". */
export function plural(count: number, one: string, many?: string): string {
  return `${count} ${count === 1 ? one : many ?? `${one}s`}`;
}
