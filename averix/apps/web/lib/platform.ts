'use client';

import { useEffect, useState } from 'react';
import { get } from './api';

/**
 * Настройки площадки, которые разрешено знать браузеру.
 *
 * Числа вроде комиссии и срока приёмки печатаются на экранах, поэтому они
 * приходят с сервера, а не живут константой в коде: администратор меняет их
 * в панели, и интерфейс обязан говорить правду в тот же день.
 */
export type PlatformSettings = Record<string, unknown>;

let pending: Promise<PlatformSettings> | null = null;

export function loadPlatform(): Promise<PlatformSettings> {
  // Один запрос на вкладку: настройки меняются раз в месяц, а читают их
  // почти все экраны.
  if (!pending) {
    pending = get<PlatformSettings>('/platform/settings').catch(() => ({}));
  }
  return pending;
}

export function usePlatform(): PlatformSettings | null {
  const [values, setValues] = useState<PlatformSettings | null>(null);
  useEffect(() => {
    let alive = true;
    void loadPlatform().then((next) => alive && setValues(next));
    return () => {
      alive = false;
    };
  }, []);
  return values;
}

function number(values: PlatformSettings | null, key: string, fallback: number): number {
  const raw = Number(values?.[key]);
  return Number.isFinite(raw) ? raw : fallback;
}

/** Доля комиссии: 0.1 — это 10%, 0 — площадка бесплатна. */
export function feeRate(values: PlatformSettings | null): number {
  const basisPoints = number(values, 'platform.fee_basis_points', 0);
  return basisPoints > 0 ? basisPoints / 10000 : 0;
}

/** Комиссия с суммы, в копейках. */
export function feeOn(values: PlatformSettings | null, amountMinor: number): number {
  return Math.round(amountMinor * feeRate(values));
}

/** Через сколько дней сданная работа принимается сама. */
export function autoApproveDays(values: PlatformSettings | null): number {
  return number(values, 'contracts.auto_approve_days', 3);
}

/** Сколько часов у исполнителя есть на подтверждение заказа. */
export function confirmHours(values: PlatformSettings | null): number {
  return number(values, 'contracts.confirm_hours', 24);
}
