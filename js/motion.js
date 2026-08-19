/* ===========================================================
   Движение: появление при скролле, фон навигации, мобильное меню.
   Всё выключается системной настройкой «уменьшить движение».
   =========================================================== */

const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');

/* --- фон навигации при прокрутке ------------------------------ */
const nav = document.getElementById('nav');
const onScroll = () => nav.classList.toggle('scrolled', window.scrollY > 24);
onScroll();
window.addEventListener('scroll', onScroll, { passive: true });

/* --- мобильное меню -------------------------------------------- */
const burger = document.getElementById('burger');
const menu = document.getElementById('menu');

function setMenu(open) {
  menu.classList.toggle('open', open);
  burger.setAttribute('aria-expanded', String(open));
  document.body.style.overflow = open ? 'hidden' : '';
}

burger.addEventListener('click', () => setMenu(!menu.classList.contains('open')));
menu.addEventListener('click', e => { if (e.target.tagName === 'A') setMenu(false); });
document.addEventListener('keydown', e => { if (e.key === 'Escape') setMenu(false); });

/* --- появление блоков ------------------------------------------ */
let observer = null;

function watchReveals() {
  if (reduceMotion.matches) {
    document.querySelectorAll('.reveal').forEach(n => n.classList.add('in'));
    return;
  }
  if (!observer) {
    observer = new IntersectionObserver(entries => {
      entries.forEach((entry, i) => {
        if (!entry.isIntersecting) return;
        // Небольшая лесенка: соседние карточки появляются друг за другом.
        entry.target.style.transitionDelay = Math.min(i * 40, 200) + 'ms';
        entry.target.classList.add('in');
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px' });
  }
  document.querySelectorAll('.reveal:not(.in)').forEach(n => observer.observe(n));
}

// Блоки создаются рендером, поэтому наблюдение вешаем после каждой отрисовки.
document.addEventListener('site:rendered', watchReveals);
watchReveals();
