import { openSheet, toast } from '../ui/dom.js';

// Установка кабинета на телефон как приложения (иконка на экране, открывается без адресной строки)
let deferred = null;
window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); deferred = e; });
export const installed = () => matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;

export async function install() {
  if (installed()) return toast('Кабинет уже установлен на этот телефон');
  if (deferred) {
    deferred.prompt();
    const { outcome } = await deferred.userChoice; deferred = null;
    if (outcome === 'accepted') toast('Готово! Иконка «Продавец» появилась на экране');
    return;
  }
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const steps = ios
    ? ['Откройте кабинет в Safari', 'Нажмите кнопку «Поделиться» внизу экрана (квадрат со стрелкой)', 'Выберите «На экран Домой»', 'Нажмите «Добавить»']
    : ['Откройте кабинет в Chrome', 'Нажмите ⋮ в правом верхнем углу', 'Выберите «Установить приложение» или «Добавить на главный экран»', 'Подтвердите установку'];
  openSheet('Установить на телефон', `
    <p style="margin:0">Кабинет будет открываться с иконки, как обычное приложение, во весь экран.</p>
    <ol class="steps">${steps.map(s => `<li>${s}</li>`).join('')}</ol>`, '');
}

if ('serviceWorker' in navigator && (location.protocol === 'https:' || ['localhost', '127.0.0.1'].includes(location.hostname))) {
  navigator.serviceWorker.register('sw.js').catch(() => { /* без офлайн-режима кабинет тоже работает */ });
}
