// Форматирование, которое люди читают.

const SYMBOL: Record<string, { sign: string; after: boolean }> = {
  RUB: { sign: '₽', after: true },
  USD: { sign: '$', after: false },
  EUR: { sign: '€', after: false },
  GBP: { sign: '£', after: false },
  UZS: { sign: 'сум', after: true },
  KZT: { sign: '₸', after: true },
  UAH: { sign: '₴', after: true },
};

/** Деньги всегда приходят целым числом в минорных единицах с явной валютой. */
export function money(minor: number | null | undefined, currency = 'RUB'): string {
  if (minor === null || minor === undefined) return '';
  const unit = SYMBOL[currency] ?? { sign: currency, after: true };
  const whole = Math.trunc(minor / 100);
  const cents = Math.abs(minor % 100);
  const grouped = whole.toLocaleString('ru-RU');
  const number = cents === 0 ? grouped : `${grouped},${String(cents).padStart(2, '0')}`;
  return unit.after ? `${number} ${unit.sign}` : `${unit.sign}${number}`;
}

/** Компактная форма для карточек: «1 200 ₽» лучше, чем «1 200,00 ₽». */
export function moneyShort(minor: number | null | undefined, currency = 'RUB'): string {
  if (minor === null || minor === undefined) return '';
  return money(Math.round(minor / 100) * 100, currency);
}

export function budgetRange(
  min: number | null | undefined,
  max: number | null | undefined,
  currency = 'RUB',
): string {
  if (min && max) return `${moneyShort(min, currency)} – ${moneyShort(max, currency)}`;
  if (max) return `до ${moneyShort(max, currency)}`;
  if (min) return `от ${moneyShort(min, currency)}`;
  return 'Бюджет обсуждается';
}

/** Относительное время; после недели — дата, потому что «19 дней назад» никому не нужно. */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const seconds = Math.round((Date.now() - then) / 1000);

  if (seconds < 45) return 'только что';
  if (seconds < 90) return 'минуту назад';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${plural(minutes, 'минуту', 'минуты', 'минут')} назад`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${plural(hours, 'час', 'часа', 'часов')} назад`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${plural(days, 'день', 'дня', 'дней')} назад`;
  if (days < 30) return `${plural(Math.round(days / 7), 'неделю', 'недели', 'недель')} назад`;
  return shortDate(iso);
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const sameYear = date.getFullYear() === new Date().getFullYear();
  return date.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'short',
    year: sameYear ? undefined : 'numeric',
  });
}

export function longDate(iso: string | null | undefined): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
}

export function clockTime(iso: string | null | undefined): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
}

export function initials(name: string | null | undefined): string {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((part) => part.charAt(0).toUpperCase()).join('') || '?';
}

export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

/**
 * Русское склонение: plural(3, 'отклик', 'отклика', 'откликов') → «3 отклика».
 * Если передана только одна форма, число ставится перед ней как есть.
 */
export function plural(count: number, one: string, few?: string, many?: string): string {
  return `${count.toLocaleString('ru-RU')} ${pluralWord(count, one, few, many)}`;
}

export function pluralWord(count: number, one: string, few?: string, many?: string): string {
  if (!few || !many) return one;
  const n = Math.abs(count) % 100;
  const last = n % 10;
  if (n > 10 && n < 20) return many;
  if (last > 1 && last < 5) return few;
  if (last === 1) return one;
  return many;
}

/** «3 дня», «12 дней» — срок выполнения. */
export function days(count: number): string {
  return plural(count, 'день', 'дня', 'дней');
}
