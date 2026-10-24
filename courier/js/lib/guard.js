// Защита от падений. Ошибка в коде не должна оставлять человека с белым экраном или «зависшей» кнопкой:
//   * экран не нарисовался — показываем понятный экран с кнопкой «Обновить», данные на телефоне целы;
//   * ошибка в фоне (кнопка, таймер, запрос) — короткая подсказка, приложение работает дальше;
//   * последние 20 ошибок лежат в памяти телефона (ключ zud-errors) — по ним найдём и исправим причину.
// Один и тот же файл в кабинете продавца, у покупателя и у курьера.

const KEY = 'zud-errors';
const isNet = e => /fetch|network|load failed|timed? ?out|abort/i.test(String(e?.message || e || ''));

/** Записать ошибку: в консоль и в память телефона. */
export function report(e, where = '') {
  console.error('[' + where + ']', e);
  try {
    const list = JSON.parse(localStorage.getItem(KEY) || '[]');
    list.unshift({ at: new Date().toISOString(), where, msg: String(e?.message || e).slice(0, 300), stack: String(e?.stack || '').slice(0, 800), url: location.href });
    localStorage.setItem(KEY, JSON.stringify(list.slice(0, 20)));
  } catch { /* память недоступна — хватит консоли */ }
}

/** Экран вместо белого: что случилось и что нажать. */
export function crashScreen(root, e) {
  report(e, 'render');
  if (!root) return;
  root.innerHTML = `<main class="crash" role="alert" style="min-height:100dvh;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;padding:24px;text-align:center;font-family:system-ui,sans-serif">
    <div style="width:72px;height:72px;border-radius:50%;background:#fff7cc;display:grid;place-items:center;font-size:36px" aria-hidden="true">!</div>
    <h1 style="margin:0;font-size:24px">Что-то пошло не так</h1>
    <p style="margin:0;max-width:340px;color:#6b6862">Ваши данные на месте. Нажмите «Обновить» — обычно этого достаточно.</p>
    <button type="button" data-crash="reload" style="min-height:52px;padding:0 28px;border:0;border-radius:14px;background:#fce000;color:#1f1e1c;font:inherit;font-weight:700;font-size:17px">Обновить</button>
    <button type="button" data-crash="home" style="min-height:44px;padding:0 20px;border:0;background:none;color:inherit;font:inherit;font-weight:600;text-decoration:underline">На главную</button></main>`;
  root.querySelector('[data-crash="reload"]')?.addEventListener('click', () => location.reload());
  root.querySelector('[data-crash="home"]')?.addEventListener('click', () => { location.hash = '#/'; location.reload(); });
}

/** Ловить ошибки в фоне. say(текст) — как показать подсказку (toast приложения). */
export function guardGlobal(say) {
  let last = 0;
  const tell = e => { if (isNet(e) || Date.now() - last < 5000) return; last = Date.now(); try { say('Что-то пошло не так. Попробуйте ещё раз'); } catch { /* подсказку показать нельзя */ } };
  addEventListener('error', ev => { if (!ev.error) return; report(ev.error, 'error'); tell(ev.error); });   // без ev.error — не загрузилась картинка или шрифт, это не ошибка кода
  addEventListener('unhandledrejection', ev => { report(ev.reason, 'promise'); tell(ev.reason); });
}
