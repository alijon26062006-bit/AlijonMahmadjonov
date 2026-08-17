/** Обёртка Telegram WebApp: определение режима, тема, кнопки, haptics. */

type TgWebApp = {
  initData: string;
  initDataUnsafe: { start_param?: string; user?: { id: number } };
  colorScheme: 'light' | 'dark';
  themeParams: Record<string, string>;
  expand(): void;
  ready(): void;
  close(): void;
  openTelegramLink(url: string): void;
  disableVerticalSwipes?: () => void;
  onEvent(event: string, cb: () => void): void;
  BackButton: { show(): void; hide(): void; onClick(cb: () => void): void; offClick(cb: () => void): void };
  MainButton: {
    setText(t: string): void; show(): void; hide(): void;
    onClick(cb: () => void): void; offClick(cb: () => void): void;
    showProgress(): void; hideProgress(): void; enable(): void; disable(): void;
  };
  HapticFeedback?: {
    impactOccurred(style: 'light' | 'medium' | 'heavy'): void;
    notificationOccurred(type: 'success' | 'warning' | 'error'): void;
  };
};

declare global {
  interface Window { Telegram?: { WebApp?: TgWebApp } }
}

export const tg: TgWebApp | undefined = window.Telegram?.WebApp;

/** Настоящий Mini App: есть подписанные данные и в них — пользователь.
 *  Внутренний браузер Telegram тоже подключает telegram-web-app.js, но
 *  initData там пустая — это обычный сайт, вход по коду. */
export const inTelegram = Boolean(tg && tg.initData && tg.initDataUnsafe?.user?.id);

/** Идентификатор владельца сессии — чтобы не подставить чужую из кэша. */
export const tgUserId: number | null = tg?.initDataUnsafe?.user?.id ?? null;

export function initTelegram(): void {
  document.body.classList.toggle('in-telegram', inTelegram);
  if (!tg || !inTelegram) {
    // Браузер: тема из localStorage либо системная
    const saved = localStorage.getItem('theme');
    const dark = saved ? saved === 'dark'
      : window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.dataset.theme = dark ? 'dark' : 'light';
    return;
  }
  tg.ready();
  tg.expand();
  tg.disableVerticalSwipes?.();          // свайп по галерее/карте не закрывает Mini App
  applyTgTheme();
  tg.onEvent('themeChanged', applyTgTheme);
}

function applyTgTheme(): void {
  if (!tg) return;
  document.documentElement.dataset.theme = tg.colorScheme;
  const root = document.documentElement.style;
  for (const [k, v] of Object.entries(tg.themeParams || {})) {
    root.setProperty(`--tg-theme-${k.replace(/_/g, '-')}`, v);
  }
}

export function toggleTheme(): void {
  const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = next;
  localStorage.setItem('theme', next);
}

export function haptic(style: 'light' | 'medium' = 'light'): void {
  tg?.HapticFeedback?.impactOccurred(style);
}

export function hapticSuccess(): void {
  tg?.HapticFeedback?.notificationOccurred('success');
}

export function openTgLink(url: string): void {
  if (inTelegram && tg) tg.openTelegramLink(url);
  else window.open(url, '_blank');
}

/** start_param вида l_<uuid-hex> → uuid с дефисами */
export function parseStartParam(): string | null {
  const p = tg?.initDataUnsafe?.start_param;
  if (!p || !p.startsWith('l_')) return null;
  const hex = p.slice(2);
  if (!/^[0-9a-f]{32}$/i.test(hex)) return null;
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
