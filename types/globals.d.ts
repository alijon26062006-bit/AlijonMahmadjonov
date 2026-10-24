// Что браузер или подключённые скрипты добавляют к window — чтобы проверка типов знала о них.
// Код проекта — обычный JavaScript; TypeScript здесь только проверяет его (tsc --noEmit), ничего не собирая.

interface Window {
  /** Карта Leaflet — грузится с unpkg, когда нужна карта. */
  L?: any;
  /** Библиотека Supabase — js/vendor/supabase.js. */
  supabase?: any;
  /** Подмена Supabase в тестах (tests/mock-supabase.js). */
  __SUPABASE_MOCK__?: any;
  /** Есть внутри APK, собранного через Capacitor. */
  Capacitor?: any;
  /** Старые Safari. */
  webkitAudioContext?: typeof AudioContext;
}
interface Navigator {
  /** iPhone: сайт открыт как приложение с экрана «Домой». */
  standalone?: boolean;
}
interface NotificationOptions {
  /** Узор вибрации уведомления (Android). */
  vibrate?: number | number[];
}
interface Error {
  /** Ошибка из-за отсутствия связи. */
  net?: boolean;
}
// Поиск по странице возвращает «любой» элемент: проект сам знает, что под селектором поле ввода или кнопка.
interface ParentNode {
  querySelector(selectors: string): any;
}
interface EventTarget {
  value?: any; checked?: boolean; files?: FileList; id?: string; name?: string; dataset?: DOMStringMap;
  closest?(selectors: string): any; matches?(selectors: string): boolean; blur?(): void;
}
interface Node {
  matches?(selectors: string): boolean;
  closest?(selectors: string): any;
}
