/* Панель внутри Telegram.

   Telegram открывает страницу в своём окне и даёт скрипт с настройками:
   тема, кнопка «назад», отклик на нажатие. Пользуемся, чтобы панель не
   выглядела вставленным сайтом. Вне Telegram файл просто ничего не делает —
   та же страница открывается в обычном браузере. */

(function () {
  const tg = window.Telegram && window.Telegram.WebApp;
  if (!tg || !tg.initData) return;

  const root = document.documentElement;
  root.classList.add('in-tg');

  tg.ready();
  tg.expand();

  /* Полосы Telegram красим в свой чёрный, иначе сверху и снизу светлые куски. */
  const ink = '#0c0b0a';
  try {
    tg.setHeaderColor(ink);
    tg.setBackgroundColor(ink);
    if (tg.setBottomBarColor) tg.setBottomBarColor('#171512');
  } catch (e) { /* старое приложение — обойдётся */ }

  /* Высота окна Telegram меняется при открытии клавиатуры. */
  const fit = () => root.style.setProperty('--tg-height', (tg.viewportStableHeight || 0) + 'px');
  fit();
  tg.onEvent('viewportChanged', fit);

  /* Кнопка «назад» вместо нашей шапки: на главной её нет. */
  const home = ['/admin', '/courier'].includes(location.pathname);
  if (home) {
    tg.BackButton.hide();
  } else {
    tg.BackButton.show();
    tg.BackButton.onClick(() => (history.length > 1 ? history.back() : (location.href = '/admin')));
  }

  /* Короткий отклик на нажатие — как в обычном приложении. */
  const buzz = () => { try { tg.HapticFeedback.impactOccurred('light'); } catch (e) {} };
  document.addEventListener('click', e => {
    if (e.target.closest('button, a.btn, .tabbar a, .chips a, [data-take], [data-done]')) buzz();
  }, { passive: true });
})();
